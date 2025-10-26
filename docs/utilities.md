# Utilities

Helper tools for audio preprocessing, conversion, and background sample generation.

## Audio Conversion

Convert audio files to YAMNet-compatible format (16kHz mono WAV).

### Usage

```bash
python audio_util.py convert <input_dir> <output_dir>
```

### Supported Formats

- **WAV** - Native support
- **MP3** - Requires `pydub` + `ffmpeg`
- **M4A** - Requires `pydub` + `ffmpeg`
- **OGG** - Requires `pydub` + `ffmpeg`
- **FLAC** - Requires `pydub` + `ffmpeg`
- **AAC** - Requires `pydub` + `ffmpeg`
- **WMA** - Requires `pydub` + `ffmpeg`

### Install Optional Dependencies

For non-WAV format support:

```bash
# Install Python library
pip install pydub

# Install ffmpeg
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Linux (Fedora)
sudo dnf install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
# Add to PATH
```

### Examples

**Convert entire directory:**
```bash
python audio_util.py convert input_samples/ training/mario_dies/
```

**What it does:**
- Converts to 16kHz sample rate
- Converts to mono (stereo downmixed)
- Outputs as WAV format
- Preserves file names

**Input:**
```
input_samples/
├── death1.mp3
├── death2.m4a
└── death3.wav
```

**Output:**
```
training/mario_dies/
├── death1.wav  (16kHz mono)
├── death2.wav  (16kHz mono)
└── death3.wav  (16kHz mono)
```

## Generate Background Samples

**Critical for ML training**: Training with only 1 class causes the model to always output 100% confidence regardless of input. You need at least 2 classes (target + background) for the model to learn discrimination.

Generate background/negative samples to improve model accuracy and enable proper classification.

### Synthetic Noise Generation

Generate synthetic noise samples (white, pink, brown noise + silence):

```bash
python generate_background.py synthetic <output_dir> [options]
```

**Options:**
- `--num-samples N` - Number of samples per noise type (default: 10)
- `--duration D` - Duration of each sample in seconds (default: 2.0)
- `--sample-rate SR` - Sample rate in Hz (default: 16000)

**Examples:**

```bash
# Generate 20 samples per noise type (80 total)
python generate_background.py synthetic training/background/ --num-samples 20

# Generate shorter samples (1 second each)
python generate_background.py synthetic training/background/ --duration 1.0 --num-samples 15

# Custom sample rate
python generate_background.py synthetic training/background/ --sample-rate 44100 --num-samples 10
```

**Output files:**
```
training/background/
├── white_noise_001.wav
├── white_noise_002.wav
├── ...
├── pink_noise_001.wav
├── pink_noise_002.wav
├── ...
├── brown_noise_001.wav
├── brown_noise_002.wav
├── ...
├── silence_001.wav
└── silence_002.wav
```

**Noise types:**
- **White noise**: Equal energy across all frequencies (hiss)
- **Pink noise**: More energy in lower frequencies (rain, wind)
- **Brown noise**: Even more energy in lower frequencies (waterfall, rumble)
- **Silence**: Zero amplitude (helps model learn "no sound")

### Extract from Audio File

Extract random segments from existing audio (podcasts, music, ambient sounds):

```bash
python generate_background.py extract <audio_file> <output_dir> [options]
```

**Options:**
- `--num-segments N` - Number of segments to extract (default: 20)
- `--segment-duration D` - Duration of each segment in seconds (default: 2.0)
- `--sample-rate SR` - Sample rate in Hz (default: 16000)

**Examples:**

```bash
# Extract 30 random 2-second segments from podcast
python generate_background.py extract podcast.mp3 training/background/ --num-segments 30

# Extract shorter segments
python generate_background.py extract ambient_sounds.wav training/background/ --segment-duration 1.0 --num-segments 40

# Extract from music file
python generate_background.py extract background_music.m4a training/background/ --num-segments 25
```

**Output files:**
```
training/background/
├── segment_001.wav
├── segment_002.wav
├── segment_003.wav
└── ...
```

**Use cases:**
- **Podcasts/speech**: Background speech that's not your target class
- **Music**: Generic music to distinguish from specific sound effects
- **Ambient audio**: Environmental sounds, room tone, general noise
- **Game audio**: Other game sounds that aren't your target events

### Combine Approaches

Best results come from combining both methods:

```bash
# Step 1: Generate 10 synthetic samples of each type (40 total)
python generate_background.py synthetic training/background/ --num-samples 10

# Step 2: Extract 20 segments from ambient audio
python generate_background.py extract ambient_recording.mp3 training/background/ --num-segments 20

# Step 3: Extract 10 segments from music
python generate_background.py extract background_music.wav training/background/ --num-segments 10

# Result: 70 total background samples (40 synthetic + 20 ambient + 10 music)
```

**Why combine?**
- Synthetic noise covers pure noise patterns
- Extracted segments cover real-world audio complexity
- Diverse background class improves model discrimination
- More robust to different types of non-target audio

### After Generating Background Samples

Retrain your model to incorporate the background class:

```bash
python train.py training/ models/
```

**Expected improvement:**
- Reduces false positives significantly
- Model learns what is NOT your target class
- Confidence scores become meaningful (not always 100%)
- Better performance in noisy environments

## Audio Utilities Module

The `audio_util.py` module provides functions for audio preprocessing used throughout the project.

### Key Functions

**`load_wav_16k_mono(filename)`**
- Loads audio file (WAV or other formats with pydub)
- Converts to 16kHz mono
- Returns numpy array normalized to [-1, 1]

**`convert_to_yamnet_format(input_path, output_path)`**
- Converts single audio file to YAMNet format
- Handles stereo to mono conversion
- Resamples to 16kHz

**`convert_directory(input_dir, output_dir)`**
- Batch converts all audio files in directory
- Preserves file names, changes extension to .wav
- Creates output directory if needed

**`ensure_mono(audio, channels)`**
- Converts stereo to mono by averaging channels
- No-op if already mono

**`resample_audio(audio, orig_sr, target_sr)`**
- Resamples audio to target sample rate
- Uses scipy's resample function
- Handles sample rate conversion accurately

### Usage in Code

```python
from audio_util import load_wav_16k_mono, convert_to_yamnet_format

# Load audio file
audio = load_wav_16k_mono("input.mp3")

# Convert format
convert_to_yamnet_format("input.m4a", "output.wav")
```

## Audio Device Discovery

The `audio_device.py` module provides device discovery with auto-detection.

### Key Functions

**`list_audio_devices()`**
- Lists all available audio input devices
- Returns list of device names and channel counts
- Used by `python listen.py --list`

**`select_loopback_device()`**
- Auto-selects loopback device (system audio)
- Looks for keywords: "BlackHole", "CABLE", "Loopback", "Stereo Mix", "monitor"
- Returns device ID or None

**`select_microphone_device()`**
- Auto-selects microphone device
- Looks for keywords: "Microphone", "Built-in", "Internal"
- Returns device ID or None

**`get_device_by_name(name_substring)`**
- Finds device by name substring match (case-insensitive)
- Returns device ID or None

### Usage in Code

```python
from audio_device import select_loopback_device, list_audio_devices

# List devices
devices = list_audio_devices()
for i, device in enumerate(devices):
    print(f"[{i}] {device['name']} ({device['channels']} channels)")

# Auto-select loopback
device_id = select_loopback_device()
```

## Tips and Best Practices

### Audio Conversion

**When to convert:**
- Before training if your samples are not 16kHz mono WAV
- When collecting audio from various sources
- To normalize audio format across dataset

**Quality considerations:**
- Original quality matters - garbage in, garbage out
- Avoid multiple re-conversions (converts once, use directly)
- Keep original files as backup

### Background Sample Generation

**How many samples?**
- **Minimum**: 20 background samples (10 synthetic + 10 extracted)
- **Recommended**: 50+ background samples for robust model
- **Balanced**: Match number of target class samples if possible

**Sample duration:**
- Match your target class duration
- If target sounds are 0.8s, generate 0.8s background samples
- Consistency helps model learn better

**Diversity:**
- Mix synthetic and extracted approaches
- Use multiple source files for extraction
- Include silence samples (important!)

### Troubleshooting

**Conversion fails:**
- Ensure `ffmpeg` is installed for non-WAV formats
- Check file is not corrupted
- Verify input file format is supported

**Background generation fails:**
- Check output directory exists and is writable
- Ensure input audio file is readable (for extract mode)
- Verify sufficient disk space

**Audio quality issues:**
- Check original audio quality
- Avoid extreme volume levels (clipping)
- Ensure sample rate is appropriate (16kHz is standard)

## Next Steps

After using these utilities:

1. **Audio Conversion**: Convert samples → organize into `training/` → train model
2. **Background Generation**: Generate samples → retrain model → test improved accuracy
3. **Device Setup**: Configure devices → start real-time listening

See also:
- [ML Method Documentation](ml.md) for training and classification
- [Fingerprinting Documentation](fingerprinting.md) for registration and recognition
- [Audio Device Setup](setup.md) for configuring input devices
