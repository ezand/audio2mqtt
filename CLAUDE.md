# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom audio classification system using YAMNet transfer learning. Records audio in real-time (system audio via loopback or microphone), classifies using trained model, outputs events to console.

YAMNet (pre-trained on AudioSet) is used as a frozen feature extractor, outputting 1,024-dimensional embeddings. A small custom classifier is trained on these embeddings to recognize custom audio classes.

## Commands

### Training
```bash
python train.py [training_dir] [output_dir]
```
Trains a custom classifier on audio files in `training/` directory. Folder names become class labels. Outputs to `models/classifier.keras` and `models/class_names.txt`.

### Batch Classification
```bash
# Base YAMNet (521 AudioSet classes)
python main.py <wav_file>

# Custom trained model
python main.py <wav_file> --custom
```

### Real-time Listening
```bash
# List available audio devices
python listen.py --list

# Auto-select loopback device (system audio)
python listen.py

# Listen to microphone
python listen.py --microphone

# Adjust window duration, thresholds, and enable verbose mode
python listen.py --window-duration 1.5 --threshold 0.8 --energy-threshold -35 --verbose
```

**Key parameter**: `--window-duration` should match training audio length for optimal accuracy.

### Generate Background Samples
```bash
# Generate synthetic noise (white, pink, brown, silence)
python generate_background.py synthetic training/background/ --num-samples 20

# Extract random segments from audio file
python generate_background.py extract podcast.mp3 training/background/ --num-segments 30
```
Creates background/negative samples to solve single-class training problem.

### Audio Conversion
```bash
python audio_util.py convert <input_dir> <output_dir>
```
Converts audio files (WAV, MP3, M4A, OGG, FLAC, AAC, WMA) to YAMNet-compatible format (16kHz mono).

## Architecture

### Two-Stage Pipeline
1. **Feature Extraction (YAMNet)**: Audio → 1024-dim embeddings per frame (~0.48s)
2. **Classification (Custom)**: Embeddings → class predictions

### Real-time Streaming Pipeline
```
Audio Input (loopback/mic) → Ring Buffer (3s history) → Sliding Window (2s)
→ YAMNet Embeddings → Classifier → Per-frame Predictions → Debouncing → Events
```

### Key Design Pattern
- YAMNet is **never retrained**, only used for feature extraction
- Training data is processed through YAMNet to extract embeddings **once** in `train.py:extract_embeddings_from_dataset()`
- The custom classifier trains on pre-computed embeddings, not raw audio
- This separation is critical: `dataset.py` handles audio loading, `model.py` handles embedding extraction, `train.py` orchestrates the pipeline

### Module Responsibilities

**Core Inference:**
- **yamnet_classifier.py**: YAMNet model loading, audio loading, normalization, batch classification
- **class_map.py**: Load YAMNet's 521 AudioSet class names from CSV

**Training:**
- **audio_util.py**: Audio preprocessing (mono conversion, resampling to 16kHz, multi-format support)
- **dataset.py**: Scan `training/` directory, load WAV files, create TF datasets. Uses `padded_batch()` for variable-length audio
- **model.py**: Build classifier architecture, extract embeddings, prediction functions (batch and streaming)
- **train.py**: Training loop - loads data, extracts embeddings eagerly (not in graph), trains classifier, saves model

**Real-time Streaming:**
- **audio_device.py**: Device discovery with auto-detection for loopback devices (BlackHole, WASAPI, monitor) and microphones
- **stream_classifier.py**: Real-time classification engine with ring buffer, energy gating, event debouncing
- **listen.py**: CLI entry point for real-time listening

**Batch Classification:**
- **main.py**: CLI for batch classification with base YAMNet or custom model

**Utilities:**
- **generate_background.py**: Generate background/negative samples (synthetic noise or extracted from audio files)

### Training Data Structure
```
training/
├── class_name_1/
│   ├── sample1.wav
│   └── sample2.wav
└── class_name_2/
    └── ...
```
Folder name = class label. `dataset.scan_training_directory()` automatically discovers classes.

**Critical**: Train with ≥2 classes. Single-class training causes softmax to always output 100% confidence regardless of input.

### Embedding Extraction Strategy

**Batch Inference** (`model.predict_batch()`):
- Each audio file generates multiple embedding frames (one per ~0.48s)
- Embeddings are **averaged across time** to produce single prediction per file
- Used in `main.py` for batch classification

**Streaming Inference** (`model.predict_streaming()`):
- Each embedding frame classified **separately** (no averaging)
- Detects events within continuous audio stream
- Used in `stream_classifier.py` for real-time classification

**Training**:
- All frames from all files used (data augmentation effect)
- Extracted eagerly in `train.py:extract_embeddings_from_dataset()` to avoid TensorFlow graph scope errors

## Critical Implementation Details

### Window Duration Configuration
**Critical for accuracy**: The sliding window duration (`--window-duration`) should match your training audio length.

**Problem**: If training samples are 0.8s but window is 2.0s, then 60% of each analyzed window is non-target audio, diluting the signal and causing false positives.

**Solution**:
- Short sounds (0.5-1s): `--window-duration 1.0`
- Medium sounds (1-2s): `--window-duration 1.5` or `2.0` (default)
- Long sounds (2-3s): `--window-duration 3.0`

Implemented in `listen.py` and `stream_classifier.py` with configurable window_duration parameter.

### Energy Gating (stream_classifier.py:69-87)
RMS energy calculation in dB filters silence/noise before inference:
```python
rms = np.sqrt(np.mean(audio**2))
db = 20 * np.log10(rms) if rms > 1e-10 else -100.0
```
Skips inference if below threshold (default -40dB). Significantly reduces false positives and CPU usage.

### TensorFlow Scope Issue (Solved)
**Problem**: Using Python loops inside graph functions causes `InaccessibleTensorError`.
**Solution**: Extract embeddings eagerly in `train.py:extract_embeddings_from_dataset()`, then create new dataset from extracted embeddings.

### Variable-Length Audio (Solved)
**Problem**: Regular `batch()` requires same shape, audio files have different lengths.
**Solution**: Use `padded_batch()` with padding values in `dataset.py`.

### Tensor to String Conversion (Solved)
**Problem**: `tf.py_function` passes TensorFlow tensor to `load_wav_16k_mono()`, but `wavfile.read()` expects string.
**Solution**: Check `isinstance(filename, tf.Tensor)` and convert with `.numpy().decode('utf-8')` in `dataset.py:20-22`.

### Model Save Format
Always use `.keras` extension: `models/classifier.keras` (not `models/classifier`).

### Streaming vs Batch Inference
- **Batch**: Averages embeddings across time → single prediction per file
- **Streaming**: Classifies each frame separately → detects events within continuous audio

### Single-Class Training Problem
**Critical limitation**: Training with only 1 class causes softmax to always output 100% confidence regardless of input audio. Model needs ≥2 classes (target + background/negative samples) to learn discrimination. This is a fundamental ML requirement, not a bug.

**Solutions**:
1. Add `training/background/` folder with 20+ non-target sounds
2. Implement YAMNet pre-filtering to skip custom classifier on clearly wrong audio
3. Add validation warning in `train.py` when detecting single-class training

## Audio Setup

### macOS
Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) 2ch, create Multi-Output Device in Audio MIDI Setup combining speakers + BlackHole, set system output to Multi-Output Device.

### Windows
Enable "Stereo Mix" in audio settings or install VB-CABLE.

### Linux
Use PulseAudio monitor (usually built-in).

## Dependencies

Core: TensorFlow 2.20, TensorFlow Hub, TensorFlow I/O, soundcard 0.4.5, scipy, numpy
Optional: pydub 0.25.1 (multi-format conversion requires ffmpeg)

See `requirements.txt` for exact versions.

## Code Style

- Pure functions preferred (see `class_map.py`, most of `audio_util.py`)
- Type hints on function signatures
- Docstrings in Google style
- Separation of concerns: one module per logical unit
