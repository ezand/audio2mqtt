# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time audio fingerprinting recognition system using Dejavu (like Shazam).

Records audio in real-time (system audio via loopback or microphone), recognizes using exact audio matching, outputs events to console with flexible metadata.

## Commands

### Fingerprinting with Metadata (Recommended)
```bash
# 1. Generate fingerprint files from YAML metadata + audio (version-controlled)
python generate_fingerprint_files.py source_sounds/ training/fingerprints/

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

### Real-time Listening

```bash
# Use in-memory database (quick start)
python listen.py

# Use PostgreSQL
python listen.py --db-type postgresql

# Use config file
python listen.py --config config.yaml

# Adjust window duration, thresholds, and enable verbose mode
python listen.py --window-duration 2.0 --threshold 0.5 --energy-threshold -40 --verbose
```

**Key parameters**:
- `--threshold`: Lower (0.3-0.4) for more sensitive matching
- `--window-duration`: 2s+ recommended for best accuracy

## Architecture

### Fingerprinting Pipeline
```
Audio Input (44.1kHz) → Ring Buffer → Sliding Window → FFT + Peak Detection → Hash Matching → Database Query → Debouncing → Events
```

### Key Design Patterns

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

**Fingerprinting Method:**
- **fingerprinting/engine.py**: Dejavu wrapper with metadata support - initialize engine, register audio with metadata, recognize audio from buffers
- **fingerprinting/metadata_db.py**: Metadata database manager - stores flexible JSONB metadata for songs (PostgreSQL/MySQL/SQLite)
- **fingerprinting/storage_config.py**: Database configuration (PostgreSQL, MySQL, in-memory) with environment variable support
- **fingerprinting/recognizer.py**: Real-time fingerprint recognition with metadata - ring buffer, energy gating, event debouncing
- **fingerprinting/postgres_db.py**: Custom PostgreSQL adapter for Dejavu (PyDejavu 0.1.3 only ships with MySQL)
- **fingerprinting/memory_db.py**: In-memory database adapter for Dejavu
- **register_fingerprints.py**: CLI for registering audio fingerprints by class or flat directory structure (legacy, no metadata)
- **generate_fingerprint_files.py**: Generate fingerprint JSON files from YAML metadata + audio (for version control)
- **import_fingerprint_files.py**: Import fingerprint JSON files into database with metadata

**Shared Components:**
- **audio_device.py**: Device discovery with auto-detection for loopback devices (BlackHole, WASAPI, monitor) and microphones
- **listen.py**: CLI entry point for real-time listening

**Infrastructure:**
- **docker-compose.yml**: PostgreSQL database setup for fingerprinting persistence
- **config.yaml.example**: Configuration template for database connection and recognition parameters
- **source_sounds/**: Source audio files with YAML metadata files
- **training/fingerprints/**: Generated fingerprint JSON files (version-controlled)

### Training Data Structure

**Fingerprinting Method:**
```
source_sounds/
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

## Critical Implementation Details

### Energy Gating (recognizer.py)
RMS energy calculation in dB filters silence/noise before inference:
```python
rms = np.sqrt(np.mean(audio**2))
db = 20 * np.log10(rms) if rms > 1e-10 else -100.0
```
Skips inference if below threshold (default -40dB). Significantly reduces false positives and CPU usage.

### Confidence Calculation
- Dejavu returns raw hash match count as "confidence"
- Normalized to 0.0-1.0 using `min(matched_hashes / 50.0, 1.0)`
- 50+ matches = 100% confidence
- Typical threshold: 0.3-0.5 for reliable matches

### PostgreSQL memoryview Bug (Solved)
**Problem**: PostgreSQL's psycopg2 returns bytea columns as `memoryview` objects, not `bytes`.
**Solution**: Handle both types in `postgres_db.py:return_matches()`:
```python
if isinstance(row[0], memoryview):
    hash_hex = row[0].tobytes().hex()
elif isinstance(row[0], bytes):
    hash_hex = row[0].hex()
```

## Method Details

### When to Use Fingerprinting

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

**Performance:**
- Setup time: Instant registration
- Accuracy for exact sounds: 96-100%
- False positive rate: Near-zero (<1%)
- Generalization: No (exact matches only)
- Database required: Yes (PostgreSQL recommended)
- CPU usage: Medium-High
- Latency: ~100-200ms

## Audio Setup

### macOS
Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) 2ch, create Multi-Output Device in Audio MIDI Setup combining speakers + BlackHole, set system output to Multi-Output Device.

### Windows
Enable "Stereo Mix" in audio settings or install VB-CABLE.

### Linux
Use PulseAudio monitor (usually built-in).

## Dependencies

**Core:**
- PyDejavu 0.1.3 (Dejavu audio fingerprinting, requires Python 3 patching)
- psycopg2-binary 2.9.11 (PostgreSQL driver)
- librosa 0.11.0 (audio processing)
- soundcard 0.4.5 (audio capture)
- scipy, numpy (audio processing)
- PyYAML 6.0.3 (configuration)

See `requirements.txt` for exact versions.

## Code Style

- Pure functions preferred
- Type hints on function signatures
- Docstrings in Google style
- Separation of concerns: one module per logical unit

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
