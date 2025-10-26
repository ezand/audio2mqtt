![Banner](docs/assets/audio2mqtt_banner.png)

[![GitHub License](https://img.shields.io/github/license/ezand/launchbox2mqtt)](https://choosealicense.com/licenses/mit/)
![GitHub top language](https://img.shields.io/github/languages/top/ezand/audio2mqtt)

> ⚠️ **Work in Progress**: This project is under active development and not ready for production use. Features may be
> incomplete, APIs may change, and bugs are expected.

# audio2mqtt

**Real-time Audio Recognition: ML & Fingerprinting**

A dual-method audio recognition system for detecting audio events in real-time:
- **ML Method**: YAMNet transfer learning for sound pattern recognition and generalization
- **Fingerprinting Method**: Dejavu-based exact audio matching (like Shazam)

## Overview

### Two Recognition Methods

This system provides two distinct approaches for audio recognition, each optimized for different use cases:

#### ML Method: YAMNet Transfer Learning

Uses a pre-trained neural network (YAMNet) as a feature extractor, training only a small classifier on top:
- **Best for**: Sound categories, pattern recognition, generalization to variations
- **Setup**: Requires training with 20+ samples per class (5-10 minutes)
- **Accuracy**: 70-95% depending on training data quality
- **False positives**: Medium (5-15%) - can misclassify similar sounds
- **Example use cases**: "Any dog bark", "any door slam", voice command categories

#### Fingerprinting Method: Dejavu

Creates unique audio "signatures" for exact matching (like Shazam):
- **Best for**: Exact sound recognition, specific audio (game sounds, alerts, jingles)
- **Setup**: Just register reference audio (instant)
- **Accuracy**: 96-100% for exact matches
- **False positives**: Near-zero (<1%) - requires exact or very similar audio
- **Example use cases**: Game audio events, specific alerts, musical cues

### Which Method Should I Use?

**Use ML if you want:**
- Pattern recognition ("recognize any crying baby")
- Generalization to variations of sounds
- Sound categories rather than exact matches

**Use Fingerprinting if you want:**
- Exact sound matching ("recognize this specific mario death sound")
- Near-zero false positives
- Simple setup without training
- Game audio, alerts, or jingles

**Recommendation**: For specific sounds like game audio, use fingerprinting - it's simpler, more accurate, and eliminates false positives.

## Quick Start

### ML Method

```bash
# 1. Prepare training data
mkdir -p training/mario_dies training/background
# Add your audio samples to training/mario_dies/
python generate_background.py synthetic training/background/ --num-samples 20

# 2. Train model
python train.py

# 3. Listen in real-time
python listen.py --method ml
```

### Fingerprinting Method

```bash
# 1. Start database (optional, can use in-memory)
docker-compose up -d

# 2. Register audio fingerprints
python register_fingerprints.py training/ --by-class --db-type postgresql

# 3. Listen in real-time
python listen.py --method fingerprint --db-type postgresql
```

## Documentation

Detailed documentation for each component:

- **[ML Method](docs/ml.md)** - YAMNet transfer learning guide (training, classification, real-time listening)
- **[Fingerprinting Method](docs/fingerprinting.md)** - Dejavu fingerprinting guide (setup, registration, recognition)
- **[Audio Device Setup](docs/setup.md)** - Configure system audio loopback and microphone input
- **[Utilities](docs/utilities.md)** - Audio conversion, background sample generation, helper tools

## Real-time Listening

The `listen.py` script supports both methods with unified CLI:

```bash
# ML method (default)
python listen.py --method ml

# Fingerprinting method
python listen.py --method fingerprint

# Common options for both methods
python listen.py --list                    # List audio devices
python listen.py --microphone              # Use microphone instead of loopback
python listen.py --device "BlackHole"      # Select specific device
python listen.py --threshold 0.8           # Adjust confidence threshold
python listen.py --window-duration 2.0     # Set analysis window size
python listen.py --energy-threshold -40    # Filter silence/noise
python listen.py --verbose                 # Show detailed output
```

See method-specific docs for detailed usage.

## Project Structure

```
audio2mqtt/
├── docs/                      # Documentation
│   ├── ml.md                  # ML method guide
│   ├── fingerprinting.md      # Fingerprinting method guide
│   ├── setup.md               # Audio device setup
│   └── utilities.md           # Helper tools
├── training/                  # Training data (ML) or reference audio (fingerprinting)
│   ├── class_name/            # Audio samples organized by class
│   └── background/            # Background/negative samples (ML only)
├── models/                    # Trained models (ML only)
│   ├── classifier.keras
│   └── class_names.txt
├── fingerprinting/            # Fingerprinting module
│   ├── engine.py              # Dejavu wrapper
│   ├── recognizer.py          # Real-time recognition
│   └── storage_config.py      # Database configuration
├── listen.py                  # Real-time listening CLI (both methods)
├── train.py                   # Training script (ML)
├── register_fingerprints.py   # Registration CLI (fingerprinting)
├── generate_background.py     # Background sample generation (ML)
├── audio_util.py              # Audio preprocessing
└── config.yaml.example        # Configuration template
```

## Method Comparison

| Feature | ML (YAMNet) | Fingerprinting (Dejavu) |
|---------|-------------|------------------------|
| **Best for** | Sound categories, pattern recognition | Exact sounds, specific audio |
| **Setup** | Train model (5-10 min) | Register audio (instant) |
| **Accuracy** | 70-95% | 96-100% |
| **False positives** | Medium (5-15%) | Near-zero (<1%) |
| **Generalization** | Yes - recognizes variations | No - exact matches only |
| **Training data** | 20+ samples per class + background | Reference audio only |
| **Database** | Not required | PostgreSQL/MySQL recommended |

## Requirements

```bash
pip install -r requirements.txt
```

**Core dependencies:**
- TensorFlow 2.20+ (ML method)
- PyDejavu 0.1.6 (fingerprinting method)
- soundcard 0.4.5 (audio capture)
- numpy, scipy (audio processing)
- psycopg2-binary (PostgreSQL support)

**Optional:**
- pydub + ffmpeg (multi-format audio conversion)

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Eirik Sand
