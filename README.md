![Banner](docs/assets/audio2mqtt_banner.png)

[![GitHub License](https://img.shields.io/github/license/ezand/launchbox2mqtt)](https://choosealicense.com/licenses/mit/)
![GitHub top language](https://img.shields.io/github/languages/top/ezand/audio2mqtt)

> ⚠️ **Work in Progress**: This project is under active development and not ready for production use. Features may be
> incomplete, APIs may change, and bugs are expected.

# audio2mqtt

**Audio Classification with YAMNet Transfer Learning**

A custom audio classification system built on Google's YAMNet model using transfer learning.

## Concepts

### YAMNet
YAMNet is a pre-trained deep neural network for audio event detection. It:
- Uses MobileNetV1 architecture
- Is trained on AudioSet (521 audio event classes)
- Outputs 1,024-dimensional embeddings per audio frame
- Expects 16kHz mono audio input

### Transfer Learning Approach
Instead of training a full audio classification model from scratch, we:
1. **Use YAMNet as a frozen feature extractor** - Extract high-level audio features (embeddings)
2. **Train a small classifier** - Learn to map embeddings to custom classes
3. **Require minimal training data** - YAMNet already understands audio, we just teach it new categories

This is efficient because:
- YAMNet embeddings capture general audio features (pitch, timbre, rhythm)
- Only the final classification layer needs training
- Works with small datasets (20-50 samples per class)

### Architecture
```
Audio Input (16kHz mono)
    ↓
YAMNet Model (frozen)
    ↓
Embeddings (1024-dim per frame)
    ↓
Custom Classifier
  - Dense(512, relu)
  - Dense(num_classes)
    ↓
Class Predictions
```

## Project Structure

```
audio2mqtt/
├── training/                # Training data organized by class
│   ├── mario_dies/         # Class name = folder name
│   │   ├── death_001.wav
│   │   ├── death_002.wav
│   │   └── ...
│   └── background/         # Background/negative samples (recommended)
│       ├── noise_001.wav
│       └── ...
├── models/                 # Saved trained models
│   ├── classifier.keras    # Trained classifier
│   └── class_names.txt     # Class name mapping
├── audio_util.py           # Audio preprocessing utilities
├── class_map.py            # YAMNet class name loading
├── yamnet_classifier.py    # YAMNet inference functions
├── dataset.py              # Training data loading
├── model.py                # Transfer learning model
├── train.py                # Training script
├── main.py                 # Batch classification script
├── audio_device.py         # Audio device discovery
├── stream_classifier.py    # Real-time classification engine
├── listen.py               # Real-time listening CLI
└── generate_background.py  # Background sample generation utility
```

## Training Process

### 1. Prepare Training Data
Organize audio files by class in the `training/` directory:
```
training/
├── mario_dies/
│   ├── sample1.wav
│   ├── sample2.wav
│   └── ...
├── coin_sound/
│   └── ...
├── jump_sound/
│   └── ...
└── background/         # IMPORTANT: Add background class
    ├── noise_001.wav
    └── ...
```

**Requirements:**
- 16kHz mono WAV files (will be auto-converted if different)
- 20+ samples per class recommended
- Folder name becomes the class label
- **At least 2 classes required** (including background/negative samples)

**Generate background samples:**
```bash
# Generate synthetic noise (white, pink, brown, silence)
python generate_background.py synthetic training/background/ --num-samples 20

# Or extract from ambient audio
python generate_background.py extract ambient.mp3 training/background/ --num-segments 30
```

### 2. Run Training
```bash
python train.py [training_dir] [output_dir]
```

**What happens:**
1. Scans `training/` directory for class folders
2. Loads YAMNet model
3. Extracts embeddings from all training audio (batched)
4. Builds classifier with Dense layers
5. Trains classifier on embeddings for 50 epochs
6. Saves trained model to `models/classifier/`
7. Saves class names to `models/class_names.txt`

**Training output:**
- Model accuracy per epoch
- Final training accuracy
- Saved model location

### 3. Why This Works
- **YAMNet embeddings are time-distributed**: Each ~0.48s of audio generates an embedding frame
- **Averaging embeddings**: We average across time to get one prediction per file (batch mode)
- **Data augmentation effect**: Multiple frames per file effectively increases training samples
- **Multi-class discrimination**: Model learns to distinguish between your classes by comparing their embeddings
- **Background class critical**: Without negative samples, softmax has no alternative and always outputs 100% confidence for the only class

## Classification

### Batch Classification

**Base YAMNet (521 classes)**
```bash
python main.py audio_file.wav
```

**Custom Trained Model**
```bash
python main.py audio_file.wav --custom
```

### Real-time Audio Stream Listening

Listen to audio in real-time and detect events as they happen. Supports both **system audio** (via loopback) and **microphone** input.

#### Prerequisites

**For System Audio (Loopback):**
- **macOS**: [BlackHole](https://github.com/ExistentialAudio/BlackHole) (free, open-source)
  - Install BlackHole 2ch
  - Create Multi-Output Device in Audio MIDI Setup with your speakers + BlackHole
  - Set system output to Multi-Output Device
- **Windows**: VB-CABLE or enable "Stereo Mix" in audio settings
- **Linux**: PulseAudio monitor (usually built-in)

**For Microphone:**
- No additional setup needed - uses built-in microphone

#### Basic Usage

**List available audio devices:**
```bash
python listen.py --list
```

**Listen to system audio (auto-selects loopback device):**
```bash
python listen.py
```

**Listen to microphone:**
```bash
python listen.py --microphone
```

**Select specific device:**
```bash
# By name (substring match)
python listen.py --device "BlackHole"
python listen.py --device "MacBook Pro Microphone"

# By device ID from --list
python listen.py --device-id 1
```

#### Advanced Options

```bash
# Adjust confidence threshold (0.0-1.0, default: 0.7)
python listen.py --threshold 0.8

# Adjust energy threshold to filter silence/noise (default: -40 dB)
python listen.py --energy-threshold -35  # less sensitive, only louder sounds
python listen.py --energy-threshold -50  # more sensitive, quieter sounds

# Enable verbose logging (shows audio detection and non-matches)
python listen.py --verbose

# Microphone with verbose mode
python listen.py --microphone --verbose

# Combine options
python listen.py --microphone --threshold 0.6 --energy-threshold -45 --verbose
```

#### Output Examples

**System audio (loopback):**
```
Auto-selected loopback device: BlackHole 2ch
Loading model: models/classifier.keras
Listening... (Press Ctrl+C to stop)

[2025-10-26 01:30:45] Event detected: mario_dies (confidence: 0.89)
[2025-10-26 01:30:52] Event detected: mario_dies (confidence: 0.91)

^C
Statistics:
  Total chunks: 1250
  Processed chunks: 45
  Skipped (silent): 1205
  Total detections: 2
```

**Microphone:**
```
Auto-selected microphone: MacBook Pro Microphone
Loading model: models/classifier.keras
Listening... (Press Ctrl+C to stop)

[2025-10-26 01:31:15] Event detected: mario_dies (confidence: 0.92)
```

**Verbose mode output:**
```bash
python listen.py --verbose

[2025-10-26 01:30:45.123] Audio detected (energy: -32.1 dB) - processing...
  → No match (best: mario_dies @ 0.45, threshold: 0.7)
[2025-10-26 01:30:46.234] Audio detected (energy: -28.5 dB) - processing...
[2025-10-26 01:30:46] Event detected: mario_dies (confidence: 0.89)
```

#### How It Works

- **Audio Source**: Captures from loopback device (system audio) or microphone
- **Energy Gating**: Calculates RMS energy in dB, skips chunks below threshold (saves CPU, prevents false positives)
- **Capture**: Records audio in 0.5 second chunks
- **Ring Buffer**: Maintains 3-second history with sliding window
- **Inference**: Processes 2-second windows with 50% overlap
- **Per-Frame Classification**: Each frame (~0.48s) classified separately, not averaged
- **Event Debouncing**: Prevents duplicate detections within 1 second
- **Latency**: ~100-200ms from audio to detection

#### Use Cases

**System Audio (Loopback):**
- Detect events in games, videos, or any computer audio output
- Monitor streaming audio for specific sounds
- Trigger actions based on application audio

**Microphone:**
- Detect real-world environmental sounds
- Voice command recognition (with appropriate training data)
- Home automation based on ambient audio events

## Utilities

### Generate Background Samples

**Important:** Training with only 1 class causes the model to always output 100% confidence regardless of input. You need at least 2 classes (target + background) for the model to learn discrimination.

Generate background/negative samples to improve model accuracy:

**Generate synthetic noise samples:**
```bash
# Creates white, pink, brown noise + silence samples
python generate_background.py synthetic training/background/ --num-samples 20
```

**Extract random segments from audio:**
```bash
# Extract 30 random 2-second segments from a podcast/music file
python generate_background.py extract podcast.mp3 training/background/ --num-segments 30
```

**Combine both approaches for best results:**
```bash
# 10 synthetic samples of each noise type (40 total)
python generate_background.py synthetic training/background/ --num-samples 10

# 20 segments from ambient audio
python generate_background.py extract ambient_sounds.mp3 training/background/ --num-segments 20
```

After generating background samples, retrain your model:
```bash
python train.py training/ models/
```

### Convert Audio Files
Convert directory of audio files to YAMNet format (16kHz mono):
```bash
python audio_util.py convert input_dir/ output_dir/
```

**Supported formats:** WAV, MP3, M4A, OGG, FLAC, AAC, WMA

**Note:** Non-WAV formats require `pydub` and `ffmpeg`:
```bash
pip install pydub
brew install ffmpeg  # macOS
# or apt-get install ffmpeg  # Linux
```

## Model Details

### Classifier Architecture
```python
Sequential([
    Input(shape=(1024,)),      # YAMNet embedding
    Dense(512, activation='relu'),
    Dense(num_classes)          # Logits output
])
```

### Training Configuration
- **Loss**: SparseCategoricalCrossentropy (multi-class)
- **Optimizer**: Adam (default learning rate)
- **Metrics**: Accuracy
- **Epochs**: 50 (configurable in train.py)
- **Batch size**: 32 embeddings (configurable)

### Inference Pipeline
1. Load audio file → 16kHz mono waveform
2. Pass through YAMNet → Extract embeddings
3. Average embeddings across time → Single 1024-dim vector
4. Pass through classifier → Get logits
5. Softmax → Convert to probabilities
6. Argmax → Get predicted class

## Extending the System

### Add More Classes
1. Create new folder in `training/` with class name
2. Add WAV files to folder
3. Re-run `python train.py`

### Improve Accuracy
- Add more training samples per class
- Ensure audio quality (minimal background noise)
- Use data augmentation (pitch shift, time stretch)
- Adjust classifier architecture in `model.py`
- Increase training epochs in `train.py`

### Export for Production
The trained classifier is a standard Keras model and can be:
- Converted to TensorFlow Lite for mobile/edge deployment
- Served via TensorFlow Serving
- Exported to ONNX for other frameworks

## Technical Notes

### Why Transfer Learning?
Training a full audio model from scratch requires:
- 100,000+ labeled samples
- Days of GPU training time
- Complex data augmentation
- Expertise in audio ML

Transfer learning with YAMNet requires:
- 20+ samples per class
- Minutes of CPU training time
- Minimal preprocessing
- Straightforward implementation

### Limitations
- Works best for sounds similar to AudioSet categories
- May struggle with very domain-specific sounds
- Single-label classification (one class per audio clip)
- Streaming mode requires loopback device for system audio capture

### Performance
- **Batch Inference**: ~100ms per audio file on CPU
- **Streaming Inference**: ~100-200ms latency from audio to detection
- **Training**: ~1-2 minutes for 20 samples on CPU
- **Model size**: ~5MB (classifier only, YAMNet not included)

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Eirik Sand
