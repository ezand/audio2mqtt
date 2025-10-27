![Banner](docs/assets/audio2mqtt_banner.png)

[![GitHub License](https://img.shields.io/github/license/ezand/launchbox2mqtt)](https://choosealicense.com/licenses/mit/)
![GitHub top language](https://img.shields.io/github/languages/top/ezand/audio2mqtt)

> ⚠️ **Work in Progress**: This project is under active development and not ready for production use. Features may be
> incomplete, APIs may change, and bugs are expected.

# audio2mqtt

**Real-time Audio Fingerprinting Recognition**

Audio fingerprinting system for detecting specific audio events in real-time using Dejavu (like Shazam). Companion project to [retro2mqtt](https://github.com/ezand/retro2mqtt).

**Integration with retro2mqtt**: Combines video game state detection (via [retro2mqtt](https://github.com/ezand/retro2mqtt)) with audio event recognition for complete home automation control. While retro2mqtt tracks game state through memory scanning, audio2mqtt detects audio cues (like level complete, game over, power-up sounds). Together they enable rich automations: trigger smart lights when Mario dies, send notifications on level completion, track gameplay stats, or control scenes based on in-game events. Perfect for streamers, home arcade setups, or anyone wanting their retro gaming to interact with their smart home.

## Overview

This system uses audio fingerprinting to create unique "signatures" for exact audio matching:

- **Best for**: Exact sound recognition, specific audio (game sounds, alerts, jingles)
- **Setup**: Just register reference audio (instant)
- **Accuracy**: 96-100% for exact matches
- **False positives**: Near-zero (<1%) - requires exact or very similar audio
- **Example use cases**: Game audio events, specific alerts, musical cues, notification sounds

### How It Works

Audio fingerprinting creates unique "signatures" for exact matching:
- Uses FFT (Fast Fourier Transform) to analyze frequency content
- Identifies spectral peaks and creates hashes
- Stores fingerprints in database (PostgreSQL/MySQL/in-memory)
- Matches audio by comparing hash patterns
- 96% accuracy with 2-second clips, 100% with 5+ seconds

## Quick Start

```bash
# 0. (Optional) Record audio from system or microphone
python audio_utils.py record source_sounds/mario_dies_001.wav

# 1. Create YAML metadata files for each audio file
# source_sounds/song.yaml:
#   source: song.mp3
#   metadata:
#     game: Game Name
#     song: Song Title
#   debounce_seconds: 5.0  # Optional: per-song MQTT debounce override

# 2. Generate fingerprint files (version-controlled)
python generate_fingerprint_files.py source_sounds/ training/fingerprints/

# 3. Start database and import fingerprints + metadata
docker-compose up -d
python import_fingerprint_files.py training/fingerprints/ --config dev-config.yaml

# 4. Listen in real-time with MQTT publishing
python listen.py --config dev-config.yaml
```

## Documentation

Detailed documentation:

- **[Audio Utilities](docs/audio_utils.md)** - Record audio, batch convert to optimal format (44.1kHz mono WAV), create YAML scaffolds
- **[Fingerprinting Guide](docs/fingerprinting.md)** - Complete guide (YAML metadata, fingerprint generation, database import, recognition)
- **[MQTT Integration](docs/mqtt.md)** - Publish detection events to MQTT broker
- **[Audio Device Setup](docs/setup.md)** - Configure system audio loopback and microphone input

## Real-time Listening

```bash
# Quick start with in-memory database
python listen.py

# PostgreSQL database (persistent)
python listen.py --db-type postgresql

# With config file
python listen.py --config config.yaml

# Common options
python listen.py --list                    # List audio devices
python listen.py --microphone              # Use microphone instead of loopback
python listen.py --device "BlackHole"      # Select specific device
python listen.py --threshold 0.5           # Adjust confidence threshold
python listen.py --window-duration 2.0     # Set analysis window size
python listen.py --energy-threshold -40    # Filter silence/noise
python listen.py --verbose                 # Show detailed output
```

See [Fingerprinting Guide](docs/fingerprinting.md) for detailed usage and tuning tips.

## Project Structure

```
audio2mqtt/
├── docs/                      # Documentation
│   ├── fingerprinting.md      # Complete fingerprinting guide
│   └── setup.md               # Audio device setup
├── training/                  # Reference audio and fingerprints
│   └── fingerprints/          # Generated fingerprint JSON files (version-controlled)
├── fingerprinting/            # Fingerprinting module
│   ├── engine.py              # Dejavu wrapper with metadata
│   ├── metadata_db.py         # Metadata database (JSONB)
│   ├── postgres_db.py         # PostgreSQL adapter for Dejavu
│   ├── memory_db.py           # In-memory database for Dejavu
│   ├── recognizer.py          # Real-time recognition with metadata
│   └── storage_config.py      # Database configuration
├── listen.py                  # Real-time listening CLI
├── register_fingerprints.py   # Registration CLI (legacy, no metadata)
├── generate_fingerprint_files.py  # Generate fingerprint JSON from YAML
├── import_fingerprint_files.py    # Import fingerprints + metadata to DB
├── audio_device.py            # Audio device discovery
└── config.yaml.example        # Configuration template
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# IMPORTANT: Patch PyDejavu for Python 3 compatibility
python scripts/apply_patches.py
```

**Why patching is needed**: PyDejavu 0.1.3 on PyPI contains Python 2 syntax (print statements, `iterator.next()`, `xrange`). The patch script automatically fixes these compatibility issues in your installed package.

**Core dependencies:**
- PyDejavu 0.1.3 (fingerprinting, requires patching)
- soundcard 0.4.5 (audio capture)
- numpy, scipy (audio processing)
- psycopg2-binary (PostgreSQL support)
- librosa (audio processing)
- PyYAML (configuration)

## Features

- ✅ **Exact audio matching** - Shazam-like recognition with 96-100% accuracy
- ✅ **Flexible metadata** - Store custom fields (game, song, artist, etc.) in JSONB
- ✅ **MQTT publishing** - Publish detection events with metadata to MQTT topics
- ✅ **Version-controlled fingerprints** - JSON files work independently of source audio
- ✅ **Multiple database backends** - PostgreSQL, MySQL, or in-memory
- ✅ **Real-time recognition** - Low latency (~100-200ms)
- ✅ **Energy-based gating** - Filters silence/noise automatically
- ✅ **Near-zero false positives** - Exact matching eliminates false detections

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Eirik Sand
