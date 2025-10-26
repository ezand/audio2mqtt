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

### Database Setup

**Option 1: PostgreSQL (recommended for persistence)**

Start PostgreSQL database:
```bash
docker-compose up -d
```

Copy and configure settings:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your database credentials
```

**Option 2: In-Memory Database (development only)**

No setup needed, just use `--db-type memory`. Note: fingerprints are lost when process exits.

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

## Register Audio Fingerprints

### Register by Class (Recommended)

Register all audio organized in class directories:

```bash
# Register training/ directory (training/class_name/*.wav)
python register_fingerprints.py training/ --by-class

# With PostgreSQL
python register_fingerprints.py training/ --by-class --db-type postgresql

# With config file
python register_fingerprints.py training/ --by-class --config config.yaml
```

**Directory structure:**
```
training/
├── mario_dies/
│   ├── death_001.wav
│   ├── death_002.wav
│   └── ...
├── coin_sound/
│   └── ...
└── jump_sound/
    └── ...
```

The folder name becomes the class/song name in the database.

### Register Flat Directory

Register all audio files in a single directory:

```bash
# Register all files in audio_samples/
python register_fingerprints.py audio_samples/

# With PostgreSQL
python register_fingerprints.py audio_samples/ --db-type postgresql
```

File names (without extension) become the song names in the database.

### Manage Fingerprints

**List registered fingerprints:**
```bash
python register_fingerprints.py --list

# With PostgreSQL
python register_fingerprints.py --list --db-type postgresql
```

**Clear all fingerprints:**
```bash
python register_fingerprints.py --clear

# With PostgreSQL
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
- **Default**: `0.3` works well for most cases
- **Lower (0.2-0.25)**: More sensitive, may get false positives
- **Higher (0.4-0.5)**: More strict, only very confident matches
- Fingerprinting naturally has low false positive rate

**Energy Threshold:**
- **Default**: `-40 dB` filters most background noise
- **Increase (-30 to -35 dB)**: If detecting too much noise
- **Decrease (-45 to -50 dB)**: For quieter sounds

### Output Examples

**Basic output:**
```
Method: Fingerprinting (Dejavu)
Using database type: postgresql
Found 45 registered fingerprints in database

Listening to: BlackHole 2ch
Method: Fingerprinting
Sample rate: 16000 Hz
Window duration: 2.0s
Confidence threshold: 0.3

[2025-10-26 03:15:42] Event detected: mario_dies (confidence: 0.87)
[2025-10-26 03:15:49] Event detected: mario_dies (confidence: 0.91)

^C
Statistics:
  Total chunks: 850
  Processed chunks: 12
  Skipped (silent): 838
  Total detections: 2
```

**Verbose mode:**
```bash
python listen.py --method fingerprint --verbose

[2025-10-26 03:15:41.234] Audio detected (energy: -32.1 dB) - processing...
  → No match (no confident fingerprint matches)
[2025-10-26 03:15:42.123] Audio detected (energy: -28.5 dB) - processing...
[2025-10-26 03:15:42] Event detected: mario_dies (confidence: 0.87)
  → Matched hashes: 145/167, offset alignment: 0.12s
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