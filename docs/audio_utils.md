# Audio Utilities

Utilities for preparing audio files for optimal fingerprinting performance.

## Overview

The `audio_utils.py` module provides tools to batch convert audio files to the optimal format for Dejavu fingerprinting. This ensures maximum fingerprint generation and recognition accuracy.

## Optimal Format

Dejavu fingerprinting works best with:

- **Sample rate**: 44,100 Hz (44.1kHz)
- **Channels**: Mono (1 channel)
- **Format**: WAV (uncompressed)
- **Bit depth**: 16-bit PCM

**Why this matters**: Audio at lower sample rates (e.g., 16kHz) produces significantly fewer fingerprints. For example, a 3-second audio clip at 16kHz generates only ~36 fingerprints, while the same clip at 44.1kHz generates ~500+ fingerprints. This directly impacts recognition accuracy and matching reliability.

## Commands

### Create YAML Metadata Scaffolds

Generate YAML metadata files for audio files with minimal default values:

```bash
# Create YAML for single file
python audio_utils.py create-yaml source_sounds/mario_dies_001.wav

# Create YAMLs for all audio files in directory
python audio_utils.py create-yaml source_sounds/ --recursive

# Add metadata fields using --meta KEY=VALUE
python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta category=game_event

# Add multiple metadata fields
python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta category=game_event --meta artist=Nintendo --meta year=1990

# Set MQTT debounce duration
python audio_utils.py create-yaml source_sounds/ --recursive --debounce 10.0

# Combine metadata and debounce
python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta category=game_event --debounce 15.0

# Overwrite existing YAML files
python audio_utils.py create-yaml source_sounds/ --recursive --overwrite

# Include files that already have YAML
python audio_utils.py create-yaml source_sounds/ --recursive --include-existing
```

**Default YAML structure:**
```yaml
source: mario_dies_001.wav
metadata:
  song: mario_dies_001
```

**With additional metadata:**
```yaml
source: mario_dies_001.wav
metadata:
  song: mario_dies_001
  game: Super Mario Bros
  category: game_event
  artist: Nintendo
  year: '1990'
```

**With debounce setting:**
```yaml
source: mario_dies_001.wav
metadata:
  song: mario_dies_001
  game: Super Mario Bros
  category: game_event
debounce_seconds: 15.0
```

**Output:**
```
Found 20 audio file(s) in source_sounds/mario_dies

[1/20] ✓ Created: mario_dies_001.yaml
[2/20] SKIP: mario_dies_002.wav (YAML exists)
[3/20] ✓ Created: mario_dies_003.yaml
...

============================================================
YAML Creation Summary:
  Total files:     20
  Created:         18
  Skipped:         2
  Failed:          0
```

**Notes:**
- The `song` field is automatically set to the filename without extension
- Use `--meta KEY=VALUE` to add any metadata field (can be used multiple times)
- Use `--debounce SECONDS` to set per-song MQTT debounce duration
- Numeric values in `--meta` are quoted as strings (e.g., `year: '1990'`)
- The `debounce_seconds` field is stored as a number at the top level (not in metadata)
- You can manually edit the YAML files afterward to add more metadata
- Skips files that already have YAML by default (use `--include-existing` to override)

### Check File Information

View audio file properties and whether conversion is needed:

```bash
python audio_utils.py info source_sounds/mario_dies_002.wav
```

**Output:**
```
Audio File: mario_dies_002.wav
  Sample rate:  44100 Hz
  Channels:     1
  Codec:        pcm_s16le
  Duration:     2.93s
  Format:       .wav

Optimal format: 44100Hz, 1ch, .wav
Needs conversion: False
```

### Preview Conversions (Dry Run)

See what would be converted without making changes:

```bash
# Preview all files in directory
python audio_utils.py convert source_sounds/ --dry-run

# Preview with recursive search
python audio_utils.py convert source_sounds/ --recursive --dry-run
```

**Output:**
```
Found 8 audio file(s) in source_sounds
DRY RUN MODE - No files will be converted

[1/8] SKIP: mario_dies_002.wav (Already optimal)
[2/8] WOULD CONVERT: song.mp3 (48000Hz → 44100Hz, 2ch → 1ch, .mp3 → .wav)
                   → source_sounds/song.wav
[3/8] WOULD CONVERT: background.m4a (16000Hz → 44100Hz, 1ch → 1ch, .m4a → .wav)
                   → source_sounds/background.wav
...
```

### Convert Files

Convert audio files to optimal format:

```bash
# Convert all files in directory (non-recursive)
python audio_utils.py convert source_sounds/

# Convert recursively (includes subdirectories)
python audio_utils.py convert source_sounds/ --recursive

# Convert to separate output directory (preserves structure)
python audio_utils.py convert source_sounds/ --output converted/ --recursive

# Convert single file
python audio_utils.py convert audio.mp3 --output audio.wav

# Overwrite existing output files
python audio_utils.py convert source_sounds/ --overwrite

# Convert in-place (replace originals with WAV)
python audio_utils.py convert source_sounds/ --in-place

# Include files already in optimal format
python audio_utils.py convert source_sounds/ --include-optimal
```

### Conversion Output

```
Found 8 audio file(s) in source_sounds

[1/8] SKIP: mario_dies_002.wav (Already optimal)
[2/8] CONVERTING: song.mp3 (48000Hz → 44100Hz, 2ch → 1ch, .mp3 → .wav)
      ✓ Converted: song.wav
[3/8] CONVERTING: background.m4a (16000Hz → 44100Hz)
      ✓ Converted: background.wav
[4/8] CONVERTING: alert.ogg (22050Hz → 44100Hz, 2ch → 1ch)
      ✓ Converted: alert.wav
...

============================================================
Conversion Summary:
  Total files:     8
  Converted:       6
  Skipped:         2
  Failed:          0
```

## Command Reference

### `create-yaml` - Create YAML Metadata Scaffolds

```bash
python audio_utils.py create-yaml <path> [options]
```

**Arguments:**
- `path` - File or directory

**Options:**
- `-r, --recursive` - Search subdirectories recursively
- `--overwrite` - Overwrite existing YAML files
- `--include-existing` - Include files that already have YAML
- `--meta KEY=VALUE` - Add metadata field (can be used multiple times)
- `--debounce SECONDS` - Set MQTT debounce duration in seconds

**Examples:**
```bash
# Single file
python audio_utils.py create-yaml source_sounds/mario_dies_001.wav

# Batch with metadata
python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta category=game_event

# Set debounce duration
python audio_utils.py create-yaml source_sounds/ --recursive --debounce 10.0

# Multiple metadata fields with debounce
python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta artist=Nintendo --debounce 15.0
```

### `info` - Show File Information

```bash
python audio_utils.py info <file>
```

**Arguments:**
- `file` - Path to audio file

**Example:**
```bash
python audio_utils.py info source_sounds/mario_dies_002.wav
```

### `convert` - Convert Audio Files

```bash
python audio_utils.py convert <path> [options]
```

**Arguments:**
- `path` - File or directory to convert

**Options:**
- `-o, --output <path>` - Output file or directory
- `-r, --recursive` - Search subdirectories recursively
- `--overwrite` - Overwrite existing output files
- `--in-place` - Convert files in place (replace originals with WAV)
- `--dry-run` - Preview changes without converting
- `--include-optimal` - Include files already in optimal format

## Supported Formats

Input formats:
- MP3 (`.mp3`)
- M4A/AAC (`.m4a`, `.aac`)
- OGG Vorbis (`.ogg`)
- FLAC (`.flac`)
- WAV (`.wav`)
- AIFF (`.aiff`)
- WMA (`.wma`)

Output format:
- WAV (`.wav`) - 44.1kHz, mono, 16-bit PCM

## Workflow Integration

### Recommended Workflow

⚠️ **IMPORTANT**: `generate_fingerprint_files.py` does **NOT** automatically convert audio to the optimal format. You **MUST** convert audio files BEFORE fingerprint generation, otherwise you will get insufficient fingerprints and poor recognition accuracy.

1. **Organize source audio** in `source_sounds/` directory

2. **Convert to optimal format** (44.1kHz mono WAV) - **REQUIRED STEP**:
   ```bash
   python audio_utils.py convert source_sounds/ --recursive --overwrite
   ```

   **Why this is required:**
   - Audio at lower sample rates (e.g., 16kHz) produces only ~36 fingerprints
   - Audio at 44.1kHz produces ~500+ fingerprints for the same clip
   - More fingerprints = better matching reliability and accuracy
   - `generate_fingerprint_files.py` uses whatever sample rate your audio has

3. **Create YAML metadata scaffolds**:
   ```bash
   python audio_utils.py create-yaml source_sounds/ --recursive --meta game="Super Mario Bros" --meta category=game_event --debounce 10.0
   ```

4. **Edit YAML files** to add additional metadata (optional):
   - Modify `debounce_seconds` if you need different values per file
   - Add custom fields like `artist`, `year`, `console`, etc.
   - See [Fingerprinting Guide](fingerprinting.md) for full metadata options

5. **Generate fingerprints**:
   ```bash
   python generate_fingerprint_files.py source_sounds/ training/fingerprints/
   ```

6. **Import to database**:
   ```bash
   python import_fingerprint_files.py training/fingerprints/ --config dev-config.yaml
   ```

### Batch Processing Multiple Directories

```bash
# Convert multiple directories to a single output location
python audio_utils.py convert game_sounds/ --output converted/ --recursive
python audio_utils.py convert alerts/ --output converted/ --recursive
python audio_utils.py convert music/ --output converted/ --recursive
```

## Performance Impact

### Example: 16kHz vs 44.1kHz

**Before conversion (16kHz):**
- Sample rate: 16,000 Hz
- Fingerprints generated: ~36
- Matching reliability: Poor (needs 25/36 = 69% match rate at 0.5 threshold)
- Recognition: Unreliable

**After conversion (44.1kHz):**
- Sample rate: 44,100 Hz
- Fingerprints generated: ~511
- Matching reliability: Excellent (needs 25/511 = 5% match rate at 0.5 threshold)
- Recognition: Highly reliable

### Fingerprint Generation by Sample Rate

| Sample Rate | Frequency Range | Typical Fingerprints (3s clip) | Match Reliability |
|-------------|-----------------|--------------------------------|-------------------|
| 16 kHz      | 0-8 kHz         | 30-50                          | Poor              |
| 22.05 kHz   | 0-11 kHz        | 100-200                        | Fair              |
| 44.1 kHz    | 0-22 kHz        | 400-600                        | Excellent         |
| 48 kHz      | 0-24 kHz        | 450-650                        | Excellent         |

## Troubleshooting

### ffmpeg Not Found

**Error:** `ffmpeg: command not found`

**Solution:** Install ffmpeg:
- **macOS:** `brew install ffmpeg`
- **Linux:** `apt install ffmpeg` or `yum install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Conversion Timeout

**Error:** `Conversion timeout (>60s)`

**Solution:** Very long audio files may exceed the 60-second timeout. Convert them manually:
```bash
ffmpeg -i input.mp3 -ar 44100 -ac 1 -sample_fmt s16 output.wav
```

### Unable to Read Audio Info

**Error:** `Unable to read audio info`

**Solution:** File may be corrupted or unsupported. Try:
1. Play file in media player to verify it's valid
2. Check file extension matches actual format
3. Try converting manually with `ffmpeg -i input.ext output.wav`

### Output File Exists

**Error:** `Output file exists (use --overwrite)`

**Solution:** Use `--overwrite` flag or delete existing output files:
```bash
python audio_utils.py convert source_sounds/ --overwrite
```

## Technical Details

### Conversion Process

The utility uses ffmpeg with these parameters:
```bash
ffmpeg -i input.ext \
  -ar 44100 \           # Sample rate: 44.1kHz
  -ac 1 \               # Channels: mono
  -sample_fmt s16 \     # Format: 16-bit signed PCM
  output.wav
```

### Audio Quality Checks

The utility checks these properties to determine if conversion is needed:
1. **Sample rate** - Must be 44,100 Hz
2. **Channels** - Must be 1 (mono)
3. **Format** - Should be WAV for direct compatibility

Files passing all checks are marked as "Already optimal" and skipped by default.

### File Discovery

Recursive search uses glob patterns:
- Non-recursive: `source_sounds/*.mp3`
- Recursive: `source_sounds/**/*.mp3`

Searches for all supported extensions (case-insensitive).

## See Also

- [Fingerprinting Guide](fingerprinting.md) - Complete fingerprinting workflow
- [MQTT Integration](mqtt.md) - Publishing detection events
- [Audio Device Setup](setup.md) - Configure audio input
