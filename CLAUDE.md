# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dual-method real-time audio recognition system supporting:

**1. ML Method (YAMNet Transfer Learning):**
- YAMNet as frozen feature extractor (1,024-dim embeddings)
- Small custom classifier trained on embeddings
- Best for sound categories and pattern recognition

**2. Fingerprinting Method (Dejavu):**
- FFT-based spectral peak hashing (like Shazam)
- Exact audio matching with near-zero false positives
- Best for specific sounds (game audio, alerts, jingles)

Records audio in real-time (system audio via loopback or microphone), recognizes using selected method, outputs events to console.

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

**ML Method:**
```bash
# Auto-select loopback device (system audio) with ML
python listen.py

# Or explicitly specify ML method
python listen.py --method ml

# Adjust window duration, thresholds, and enable verbose mode
python listen.py --window-duration 1.5 --threshold 0.8 --energy-threshold -35 --verbose
```

**Fingerprinting Method:**
```bash
# Use fingerprinting with in-memory database
python listen.py --method fingerprint

# Use fingerprinting with PostgreSQL
python listen.py --method fingerprint --db-type postgresql

# Use fingerprinting with config file
python listen.py --method fingerprint --config config.yaml
```

**Key parameters**:
- ML: `--window-duration` should match training audio length
- Fingerprinting: `--threshold` lower (0.2-0.3) works well, window 2s+ recommended

### Fingerprinting with Metadata (Recommended)
```bash
# 1. Generate fingerprint files from YAML metadata + audio (version-controlled)
python generate_fingerprint_files.py source_sounds/fingerprining/ training/fingerprints/

# 2. Import fingerprints + metadata into database
docker-compose up -d
python import_fingerprint_files.py training/fingerprints/ --db-type postgresql
```

### Register Fingerprints (Legacy)
```bash
# Start PostgreSQL database
docker-compose up -d

# Register audio by class (without metadata)
python register_fingerprints.py training/ --by-class --db-type postgresql

# List registered fingerprints
python register_fingerprints.py --list --db-type postgresql

# Clear all fingerprints
python register_fingerprints.py --clear --db-type postgresql
```

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

### Dual-Method Architecture

**ML Pipeline:**
```
Audio Input → Ring Buffer → Sliding Window → YAMNet Embeddings → Classifier → Per-frame Predictions → Debouncing → Events
```

**Fingerprinting Pipeline:**
```
Audio Input → Ring Buffer → Sliding Window → FFT + Peak Detection → Hash Matching → Database Query → Debouncing → Events
```

### Key Design Patterns

**ML Method:**
- YAMNet is **never retrained**, only used for feature extraction
- Training data is processed through YAMNet to extract embeddings **once** in `train.py:extract_embeddings_from_dataset()`
- The custom classifier trains on pre-computed embeddings, not raw audio
- This separation is critical: `dataset.py` handles audio loading, `model.py` handles embedding extraction, `train.py` orchestrates the pipeline

**Fingerprinting Method:**
- No training required, just registration of reference audio
- Dejavu library handles FFT, peak detection, and hashing automatically
- Database stores fingerprint hashes with metadata in separate tables:
  - `songs` table: song_id, song_name (Dejavu native)
  - `fingerprints` table: hash, song_id, offset (Dejavu native)
  - `song_metadata` table: song_name, metadata (JSONB), source_file (custom)
- Metadata is flexible JSONB - store any fields (game, song, artist, year, etc.)
- Real-time matching queries database for hash collisions, returns results with metadata
- Exact matching provides near-zero false positives

### Module Responsibilities

**ML Method:**
- **yamnet_classifier.py**: YAMNet model loading, audio loading, normalization, batch classification
- **class_map.py**: Load YAMNet's 521 AudioSet class names from CSV
- **audio_util.py**: Audio preprocessing (mono conversion, resampling to 16kHz, multi-format support)
- **dataset.py**: Scan `training/` directory, load WAV files, create TF datasets. Uses `padded_batch()` for variable-length audio
- **model.py**: Build classifier architecture, extract embeddings, prediction functions (batch and streaming)
- **train.py**: Training loop - loads data, extracts embeddings eagerly (not in graph), trains classifier, saves model
- **stream_classifier.py**: Real-time ML classification engine with ring buffer, energy gating, event debouncing
- **main.py**: CLI for batch classification with base YAMNet or custom model
- **generate_background.py**: Generate background/negative samples (synthetic noise or extracted from audio files)

**Fingerprinting Method:**
- **fingerprinting/engine.py**: Dejavu wrapper with metadata support - initialize engine, register audio with metadata, recognize audio from buffers
- **fingerprinting/metadata_db.py**: Metadata database manager - stores flexible JSONB metadata for songs (PostgreSQL/MySQL/SQLite)
- **fingerprinting/storage_config.py**: Database configuration (PostgreSQL, MySQL, in-memory) with environment variable support
- **fingerprinting/recognizer.py**: Real-time fingerprint recognition with metadata - ring buffer, energy gating, event debouncing (mirrors StreamClassifier interface)
- **register_fingerprints.py**: CLI for registering audio fingerprints by class or flat directory structure (legacy, no metadata)
- **generate_fingerprint_files.py**: Generate fingerprint JSON files from YAML metadata + audio (for version control)
- **import_fingerprint_files.py**: Import fingerprint JSON files into database with metadata

**Shared Components:**
- **audio_device.py**: Device discovery with auto-detection for loopback devices (BlackHole, WASAPI, monitor) and microphones
- **listen.py**: CLI entry point for real-time listening (both ML and fingerprinting methods, selectable via `--method`)

**Infrastructure:**
- **docker-compose.yml**: PostgreSQL database setup for fingerprinting persistence
- **config.yaml.example**: Configuration template for database connection and recognition parameters
- **source_sounds/fingerprining/**: Source audio files with YAML metadata files
- **training/fingerprints/**: Generated fingerprint JSON files (version-controlled)

### Training Data Structure

**ML Method:**
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

**Fingerprinting Method:**
```
source_sounds/fingerprining/
├── Song Title [id123].mp3
├── Song Title [id123].yaml      # Metadata
└── ...

training/fingerprints/           # Generated (version-controlled)
├── Song Title [id123].json      # Fingerprints + metadata
└── ...
```

**YAML Metadata Format:**
```yaml
source: Song Title [id123].mp3
metadata:
  game: Game Name
  song: Song Title
  # Any other custom fields (artist, year, console, etc.)
```

**JSON Fingerprint Format:**
```json
{
  "song_name": "game_name_song_title",
  "source_file": "Song Title [id123].mp3",
  "metadata": {"game": "Game Name", "song": "Song Title"},
  "file_sha1": "...",
  "total_hashes": 1234,
  "fingerprints": [{"hash": "...", "offset": 32}]
}
```

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

## Method Selection Guide

### When to Use ML (YAMNet Transfer Learning)

**Use ML when:**
- You want to recognize **sound categories** (any dog bark, any door slam)
- Need **generalization** to variations of the same sound
- Want to detect patterns rather than exact matches
- Have 20+ samples per class for training
- Can tolerate some false positives
- Don't need exact match precision

**Example use cases:**
- "Detect any crying baby sound"
- "Recognize door opening/closing"
- "Identify glass breaking sounds"
- Voice command categories

### When to Use Fingerprinting (Dejavu)

**Use Fingerprinting when:**
- You want to recognize **specific exact sounds** (like Shazam)
- Need **near-zero false positives**
- Have short, consistent audio clips (game sounds, alerts, jingles)
- Don't need generalization to variations
- Want simple setup without training
- Can provide reference recordings

**Example use cases:**
- Game audio events (mario_dies, level_complete, coin_sound)
- Specific alert/notification sounds
- Jingles or musical cues
- Exact voice phrases or commands

**Recommendation for game sounds**: Use fingerprinting - it's simpler, more accurate, and eliminates the false positive problem.

### Performance Comparison

| Metric | ML | Fingerprinting |
|--------|----|--------------|
| Setup time | 5-10 min training | Instant registration |
| Accuracy for exact sounds | 70-95% | 96-100% |
| False positive rate | Medium (5-15%) | Near-zero (<1%) |
| Generalization | Yes | No |
| Database required | No | Yes (PostgreSQL recommended) |
| CPU usage | Medium | Medium-High |
| Latency | ~100-200ms | ~100-200ms |

## Audio Setup

### macOS
Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) 2ch, create Multi-Output Device in Audio MIDI Setup combining speakers + BlackHole, set system output to Multi-Output Device.

### Windows
Enable "Stereo Mix" in audio settings or install VB-CABLE.

### Linux
Use PulseAudio monitor (usually built-in).

## Dependencies

**ML Method:**
- TensorFlow 2.20, TensorFlow Hub, TensorFlow I/O
- soundcard 0.4.5, scipy, numpy

**Fingerprinting Method:**
- PyDejavu 0.1.6 (Dejavu audio fingerprinting)
- psycopg2-binary 2.9.9 (PostgreSQL driver)
- librosa 0.10.1 (audio processing)
- PyYAML 6.0.1 (configuration)

**Optional:**
- pydub 0.25.1 (multi-format conversion requires ffmpeg)

See `requirements.txt` for exact versions.

## Code Style

- Pure functions preferred (see `class_map.py`, most of `audio_util.py`)
- Type hints on function signatures
- Docstrings in Google style
- Separation of concerns: one module per logical unit
