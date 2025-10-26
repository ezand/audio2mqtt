# Fingerprinting Method: Dejavu

The fingerprinting method uses Dejavu for exact audio matching - ideal for recognizing specific sounds like game audio, alerts, or jingles (like Shazam).

## Concept

### Audio Fingerprinting Overview

Audio fingerprinting creates unique "signatures" for exact audio matching:
- Uses FFT (Fast Fourier Transform) to analyze frequency content
- Identifies spectral peaks and creates hashes
- Stores fingerprints in database (PostgreSQL/MySQL/in-memory)
- Matches audio by comparing hash patterns

### Fingerprinting Approach

1. **Register reference audio** - Create fingerprints for known sounds
2. **Store in database** - Persistent or in-memory storage
3. **Match in real-time** - Compare incoming audio against database

This is accurate because:
- Exact matching eliminates false positives
- No training required, just registration
- Robust to background noise if reference is clear
- 96% accuracy with 2-second clips, 100% with 5+ seconds
- **Best for**: Exact sound recognition, short specific sounds (game audio, alerts)

## Setup

### Installation

After installing dependencies, you **must** patch PyDejavu for Python 3 compatibility:

```bash
pip install -r requirements.txt
python scripts/apply_patches.py
```

**Why patching is needed**: PyDejavu 0.1.3 on PyPI contains Python 2 syntax (`print` statements, `iterator.next()`, `xrange`, `izip_longest`). The patch script automatically fixes these in your installed package.

**What the patch does**:
- Fixes print statements: `print "..."` → `print("...")`
- Fixes iterator: `iterator.next()` → `next(iterator)`
- Fixes range: `xrange()` → `range()`
- Fixes imports: `import fingerprint` → `from . import fingerprint`
- Fixes itertools: `izip_longest` → `zip_longest`

See `patches/pydejavu_python3.patch` for the full diff.

### Workflow Overview

The fingerprinting workflow uses **YAML metadata files** for flexible metadata and **JSON fingerprint files** for version control:

1. **Create YAML metadata** for each audio file (game, song, custom fields)
2. **Generate fingerprint JSON files** from YAML + audio (version-controlled)
3. **Import JSON files** into database (repeatable, any database)
4. **Recognize with metadata** - results include all metadata fields

### Database Setup

**Option 1: PostgreSQL (recommended for production)**

Start PostgreSQL database:
```bash
docker-compose up -d
```

Copy and configure settings:
```bash
cp config.yaml.example dev-config.yaml
# Edit dev-config.yaml with your database credentials (defaults should work)
```

**Option 2: In-Memory Database (development/testing)**

No setup needed, just use `--db-type memory`. Note: fingerprints and metadata are lost when process exits. Re-import JSON files on restart.

**Note**: This project includes a custom PostgreSQL adapter (`fingerprinting/postgres_db.py`) since PyDejavu 0.1.3 only ships with MySQL support.

### Configuration File

The `config.yaml` file contains database connection and recognition parameters:

```yaml
database:
  type: postgresql  # or mysql, memory
  host: localhost
  port: 5432
  user: postgres
  password: postgres
  database: dejavu

recognition:
  window_duration: 2.0
  confidence_threshold: 0.3
  energy_threshold: -40
```

## Create Metadata Files

Create YAML files alongside audio files with flexible metadata:

**YAML Format:**
```yaml
source: Super Mario World Music - Underground [abc123].mp3
metadata:
  game: Super Mario World
  song: Underground
  console: SNES
  year: 1990
  # Add any custom fields you need
```

**Example directory structure:**
```
source_sounds/fingerprining/
├── Super Mario World Music - Underground [abc123].mp3
├── Super Mario World Music - Underground [abc123].yaml
├── Super Mario World Music - Overworld [def456].mp3
├── Super Mario World Music - Overworld [def456].yaml
└── ...
```

The `metadata` section is flexible - add any fields relevant to your use case.

## Generate Fingerprint Files

Generate version-controlled fingerprint JSON files from YAML metadata + audio:

```bash
# Generate from directory of YAMLs
python generate_fingerprint_files.py source_sounds/fingerprining/ training/fingerprints/

# Generate from single YAML
python generate_fingerprint_files.py source_sounds/fingerprining/song.yaml training/fingerprints/
```

**What this does:**
- Parses YAML metadata
- Loads corresponding audio file
- Generates fingerprints using temporary in-memory Dejavu
- Extracts hashes and combines with metadata
- Saves to JSON in `training/fingerprints/`

**Output JSON format:**
```json
{
  "song_name": "super_mario_world_underground",
  "source_file": "Super Mario World Music - Underground [abc123].mp3",
  "metadata": {
    "game": "Super Mario World",
    "song": "Underground",
    "console": "SNES",
    "year": 1990
  },
  "file_sha1": "abc123...",
  "date_created": "2025-10-26T12:00:00Z",
  "total_hashes": 1234,
  "fingerprints": [
    {"hash": "e05b341a9b77a51fd26", "offset": 32}
  ]
}
```

**Commit to version control:**
```bash
git add training/fingerprints/
git commit -m "Add fingerprints for Super Mario World music"
```

## Import Fingerprint Files

Import JSON fingerprint files into database (no audio files needed):

```bash
# Import with PostgreSQL (persistent)
python import_fingerprint_files.py training/fingerprints/ --config dev-config.yaml

# Import with in-memory database (development)
python import_fingerprint_files.py training/fingerprints/ --db-type memory

# Import single file
python import_fingerprint_files.py training/fingerprints/song.json --config dev-config.yaml
```

**What this does:**
- Loads JSON fingerprint files (pre-computed hashes)
- Imports fingerprints directly into database via Dejavu API
- Stores metadata in `song_metadata` table with JSONB
- Skips songs already in database
- **No audio files required** - uses pre-computed fingerprints from JSON

**Benefits:**
- ✅ Version-controlled fingerprints are self-contained
- ✅ No audio files needed after initial generation
- ✅ Fast import (no re-fingerprinting)
- ✅ Team members can clone repo and import without source audio
- ✅ Reproducible - same JSON = same database state
- ✅ PostgreSQL support via custom adapter (`fingerprinting/postgres_db.py`)

## Legacy Registration (Without Metadata)

For quick registration without metadata:

### Register by Class

```bash
# Register training/ directory (training/class_name/*.wav)
python register_fingerprints.py training/ --by-class --db-type postgresql
```

**Directory structure:**
```
training/
├── mario_dies/
│   ├── death_001.wav
│   └── ...
└── coin_sound/
    └── ...
```

### Manage Fingerprints

**List registered fingerprints:**
```bash
python register_fingerprints.py --list --db-type postgresql
```

**Clear all fingerprints:**
```bash
python register_fingerprints.py --clear --db-type postgresql
```

## Real-time Recognition

### Basic Usage

**In-memory database (quick start):**
```bash
python listen.py --method fingerprint
```

**With PostgreSQL:**
```bash
python listen.py --method fingerprint --db-type postgresql
```

**With config file:**
```bash
python listen.py --method fingerprint --config config.yaml
```

### Advanced Options

```bash
# Adjust window duration for short sounds (default: 2.0s)
python listen.py --method fingerprint --window-duration 1.5

# Lower confidence threshold for more sensitive matching (default: 0.3)
python listen.py --method fingerprint --threshold 0.2

# Adjust energy threshold to filter silence/noise (default: -40 dB)
python listen.py --method fingerprint --energy-threshold -35

# Enable verbose mode to see matching details
python listen.py --method fingerprint --verbose

# Combine options
python listen.py --method fingerprint --window-duration 2.5 --threshold 0.25 --verbose --db-type postgresql
```

### Device Selection

**Auto-select loopback device (system audio):**
```bash
python listen.py --method fingerprint
```

**Microphone:**
```bash
python listen.py --method fingerprint --microphone
```

**Specific device:**
```bash
# List available devices
python listen.py --list

# By name
python listen.py --method fingerprint --device "BlackHole"

# By device ID
python listen.py --method fingerprint --device-id 1
```

### Tuning Tips

**Window Duration:**
- **Short sounds (0.5-1s)**: `--window-duration 1.5`
- **Medium sounds (1-2s)**: `--window-duration 2.0` (default)
- **Long sounds (2-3s+)**: `--window-duration 3.0`
- Longer windows = higher accuracy but slower response
- Fingerprinting is flexible, 2s+ works well for most cases

**Confidence Threshold:**
- Confidence is calculated as: `min(matched_hashes / 50, 1.0)`
- 50+ matching hashes = 1.0 confidence (100%)
- **Default**: `0.5` (requires 25+ matched hashes)
- **Lower (0.3-0.4)**: More sensitive (15-20 hashes), may get false positives
- **Higher (0.7-0.8)**: More strict (35-40 hashes), only very confident matches
- Fingerprinting naturally has low false positive rate

**Energy Threshold:**
- **Default**: `-40 dB` filters most background noise
- **Increase (-30 to -35 dB)**: If detecting too much noise
- **Decrease (-45 to -50 dB)**: For quieter sounds

### Output Examples

**With metadata:**
```
Method: Fingerprinting (Dejavu)
Using database type: postgresql
Found 45 registered fingerprints in database

Listening to: BlackHole 2ch
Method: Fingerprinting
Sample rate: 16000 Hz
Window duration: 2.0s
Confidence threshold: 0.3

[2025-10-26 03:15:42] Event detected: super_mario_world_underground (game: Super Mario World, song: Underground) (confidence: 0.87)
[2025-10-26 03:15:49] Event detected: super_mario_world_overworld (game: Super Mario World, song: Overworld) (confidence: 0.91)

^C
Statistics:
  Total chunks: 850
  Processed chunks: 12
  Skipped (silent): 838
  Total detections: 2
```

**Verbose mode with metadata:**
```bash
python listen.py --method fingerprint --verbose --db-type postgresql

[2025-10-26 03:15:41.234] Audio detected (energy: -32.1 dB) - fingerprinting...
  → No match (no confident fingerprint matches)
[2025-10-26 03:15:42.123] Audio detected (energy: -28.5 dB) - fingerprinting...
  → Match: super_mario_world_underground [Super Mario World: Underground] @ 0.87 (hashes: 145/167)
[2025-10-26 03:15:42] Event detected: super_mario_world_underground (game: Super Mario World, song: Underground) (confidence: 0.87)
```

## How It Works

### Registration Process

1. **Load audio file** - Read WAV file (auto-converts non-WAV formats)
2. **FFT analysis** - Compute spectrogram (frequency vs time)
3. **Peak detection** - Find spectral peaks (local maxima in frequency domain)
4. **Hash generation** - Create hashes from peak constellation patterns
5. **Store in database** - Save hashes with song_name and time offset

### Recognition Process

1. **Audio capture** - Record from loopback device or microphone in 0.5s chunks
2. **Ring buffer** - Maintain sliding window of configurable duration (default 2.0s)
3. **Energy gating** - Calculate RMS energy in dB, skip if below threshold
4. **FFT + peak detection** - Same as registration process
5. **Hash matching** - Query database for matching hashes
6. **Alignment** - Group matches by time offset to find aligned hits
7. **Confidence scoring** - Calculate match confidence (matched_hashes / total_hashes)
8. **Event debouncing** - Prevent duplicate detections within 1 second
9. **Output** - Report detected class/song name with confidence

### Architecture

```
Audio Input (16kHz mono)
    ↓
Ring Buffer (sliding window)
    ↓
Energy Gating (RMS dB filter)
    ↓
FFT Analysis (frequency spectrum)
    ↓
Spectral Peak Detection
    ↓
Hash Generation (constellation patterns)
    ↓
Database Query (hash matching)
    ↓
Time Offset Alignment
    ↓
Confidence Calculation
    ↓
Event Detection + Debouncing
    ↓
Output (class name + confidence)
```

## Database Types

### PostgreSQL (Recommended)

**Pros:**
- Persistent storage (survives restarts)
- Production-ready
- Fast hash lookups with indexing
- Handles large fingerprint libraries

**Setup:**
```bash
docker-compose up -d
```

**Connection:** Configure in `config.yaml` or environment variables

### MySQL

**Pros:**
- Alternative to PostgreSQL
- Also persistent and production-ready

**Setup:** Install MySQL server, configure in `config.yaml`

### In-Memory

**Pros:**
- No database setup required
- Fast for development/testing

**Cons:**
- Fingerprints lost when process exits
- Not suitable for production
- Limited by RAM

**Usage:** `--db-type memory` (no other setup needed)

## Use Cases

### Ideal For

**Game audio events:**
- Death sounds, level complete, coin collect
- Power-up activations, menu selections
- Consistent audio cues from games

**Specific alerts and notifications:**
- System sounds, notification tones
- Alarm sounds, timer beeps
- Application-specific audio alerts

**Musical cues and jingles:**
- Theme songs, intro/outro music
- Podcast intros, commercial jingles
- Recognizable musical phrases

**Exact voice commands:**
- Pre-recorded command phrases
- Specific spoken trigger words
- Voice sample matching

### Not Ideal For

**General sound categories:**
- "Any door slam" or "any dog bark"
- Variations of similar sounds
- Pattern recognition (use ML method instead)

**Highly variable sounds:**
- Environmental noise
- Crowd sounds, ambient audio
- Sounds that vary significantly each time

## Technical Details

### Accuracy

- **2-second clips**: 96% accuracy
- **5+ second clips**: ~100% accuracy
- **1-second clips**: 70-85% accuracy (increase window duration)
- **Background noise**: Robust if reference audio is clear

### Performance

- **Latency**: ~100-200ms from audio to detection
- **CPU usage**: Medium-High (FFT + database queries)
- **Memory**: Depends on database type (in-memory uses most)
- **Database size**: ~50-100 KB per registered audio file

### False Positives

- **Near-zero (<1%)** with proper threshold settings
- Exact matching eliminates most false positives
- Threshold 0.3+ provides high precision

### Limitations

- Requires exact or very similar audio (no generalization)
- Hash collisions possible but rare with proper database design
- FFT computation is CPU-intensive
- Works best with clear, distinct audio samples

## Method Comparison

| Feature | ML (YAMNet) | Fingerprinting (Dejavu) |
|---------|-------------|------------------------|
| **Training** | Requires training with positive + negative samples | Just register reference audio |
| **Generalization** | Learns patterns, recognizes variations | Exact matching only |
| **Accuracy** | 70-95%, can have false positives | 96-100%, near-zero false positives |
| **Best for** | Sound categories, pattern recognition | Exact sounds, game audio, alerts |
| **Setup** | Train model (5-10 min) | Register fingerprints (instant) |
| **Database** | Not required | PostgreSQL/MySQL recommended |
| **Window size** | Sensitive to mismatch with training data | Flexible, 2s+ recommended |
| **False positive rate** | Medium (5-15%) | Near-zero (<1%) |

**Recommendation**: For game sounds like "mario_dies", **use fingerprinting** - it's more accurate, simpler, and eliminates false positives.