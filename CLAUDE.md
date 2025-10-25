# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audio classification system using YAMNet transfer learning. YAMNet (pre-trained on AudioSet) is used as a frozen feature extractor, outputting 1,024-dimensional embeddings. A small custom classifier is trained on these embeddings to recognize custom audio classes.

## Commands

### Training
```bash
python train.py [training_dir] [output_dir]
```
Trains a custom classifier on audio files in `training/` directory. Folder names become class labels. Outputs to `models/classifier/` and `models/class_names.txt`.

### Classification
```bash
# Base YAMNet (521 AudioSet classes)
python main.py <wav_file>

# Custom trained model
python main.py <wav_file> --custom
```

### Audio Conversion
```bash
python audio_util.py convert <input_dir> <output_dir>
```
Converts WAV files to YAMNet-compatible format (16kHz mono).

## Architecture

### Two-Stage Pipeline
1. **Feature Extraction (YAMNet)**: Audio → 1024-dim embeddings per frame
2. **Classification (Custom)**: Embeddings → class predictions

### Key Design Pattern
- YAMNet is **never retrained**, only used for feature extraction
- Training data is processed through YAMNet to extract embeddings **once**, then embeddings are cached in the TensorFlow dataset
- The custom classifier trains on pre-computed embeddings, not raw audio
- This separation is critical: `dataset.py` handles audio loading, `model.py` handles embedding extraction, `train.py` orchestrates the pipeline

### Module Responsibilities
- **yamnet_classifier.py**: YAMNet model loading and inference utilities
- **class_map.py**: Load YAMNet's 521 class names from CSV
- **audio_util.py**: Audio preprocessing (mono conversion, resampling to 16kHz)
- **dataset.py**: Scan `training/` directory structure, load WAV files, create TF datasets
- **model.py**: Build classifier architecture, extract embeddings, prediction functions
- **train.py**: Training loop - loads data, extracts embeddings, trains classifier, saves model
- **main.py**: CLI for classification with base YAMNet or custom model

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

### Embedding Extraction Strategy
Each audio file generates multiple embedding frames (one per ~1 second). During training, all frames are used (data augmentation effect). During inference, embeddings are averaged across time to produce a single prediction per file. This is handled in `model.extract_embeddings()` and `model.predict_class()`.

## Dependencies

Core: TensorFlow 2.20, TensorFlow Hub, TensorFlow I/O, scipy, numpy
See `requirements.txt` for versions.

## Code Style

- Pure functions preferred (see `class_map.py`, most of `audio_util.py`)
- Type hints on function signatures
- Docstrings in Google style
- Separation of concerns: one module per logical unit
