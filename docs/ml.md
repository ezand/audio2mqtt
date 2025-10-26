# ML Method: YAMNet Transfer Learning

The ML method uses YAMNet transfer learning for sound pattern recognition and generalization.

## Concept

### YAMNet Overview
YAMNet is a pre-trained deep neural network for audio event detection:
- Uses MobileNetV1 architecture
- Trained on AudioSet (521 audio event classes)
- Outputs 1,024-dimensional embeddings per audio frame (~0.48s)
- Expects 16kHz mono audio input

### Transfer Learning Approach

Instead of training a full audio model from scratch, we:
1. **Use YAMNet as a frozen feature extractor** - Extract high-level audio features (embeddings)
2. **Train a small classifier** - Learn to map embeddings to custom classes
3. **Require minimal training data** - YAMNet already understands audio, we just teach it new categories

This is efficient because:
- YAMNet embeddings capture general audio features (pitch, timbre, rhythm)
- Only the final classification layer needs training
- Works with small datasets (20-50 samples per class)
- **Best for**: Sound categories, generalization, variations of same sound

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

**Critical**: Training with only 1 class causes the model to always output 100% confidence regardless of input. You need at least 2 classes (target + background) for the model to learn discrimination.

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
6. Saves trained model to `models/classifier.keras`
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

### Real-time Listening

Listen to audio in real-time and detect events as they happen. Supports both **system audio** (via loopback) and **microphone** input.

#### Basic Usage

**List available audio devices:**
```bash
python listen.py --list
```

**Listen to system audio (auto-selects loopback device):**
```bash
python listen.py
# Or explicitly specify ML method
python listen.py --method ml
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

# Adjust window duration to match training audio length (default: 2.0s)
python listen.py --window-duration 1.0  # for short sounds (0.5-1s)
python listen.py --window-duration 3.0  # for longer sounds (2-3s)

# Adjust energy threshold to filter silence/noise (default: -40 dB)
python listen.py --energy-threshold -35  # less sensitive, only louder sounds
python listen.py --energy-threshold -50  # more sensitive, quieter sounds

# Enable verbose logging (shows audio detection and non-matches)
python listen.py --verbose

# Microphone with verbose mode
python listen.py --microphone --verbose

# Combine options for fine-tuning
python listen.py --window-duration 1.5 --threshold 0.85 --energy-threshold -35 --verbose
```

**Tuning Tips:**
- **Window duration**: Should match your training audio length. Shorter windows = faster response but may miss long sounds. Longer windows = more context but slower response.
- **Confidence threshold**: Increase (0.8-0.9) to reduce false positives, decrease (0.5-0.6) to catch more events.
- **Energy threshold**: Increase (-30 to -35 dB) if detecting too much background noise, decrease (-45 to -50 dB) for quieter sounds.

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
- **Capture**: Records audio in 0.5 second chunks (configurable via `--chunk-duration`)
- **Ring Buffer**: Maintains audio history with sliding window
- **Inference**: Processes configurable window duration (default 2.0s, adjustable via `--window-duration`)
- **Per-Frame Classification**: Each YAMNet frame (~0.48s) classified separately, not averaged
- **Event Debouncing**: Prevents duplicate detections within 1 second
- **Latency**: ~100-200ms from audio to detection

**Critical**: Set `--window-duration` to match your training audio length for optimal accuracy.

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
3. Average embeddings across time → Single 1024-dim vector (batch mode)
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
- Can have false positives with similar sounds (5-15%)

### Performance
- **Batch Inference**: ~100ms per audio file on CPU
- **Streaming Inference**: ~100-200ms latency from audio to detection
- **Training**: ~1-2 minutes for 20 samples on CPU
- **Model size**: ~5MB (classifier only, YAMNet not included)
- **Accuracy**: 70-95% for exact sounds (depends on training data quality)

## Use Cases

**ML Method is best for:**
- Sound categories and pattern recognition (any dog bark, any door slam)
- Generalizing to variations of the same sound
- When you have 20+ samples per class for training
- Voice command categories
- Environmental sound detection

**Not recommended for:**
- Exact sound matching (use fingerprinting instead)
- Very short, specific sounds like game audio
- When zero false positives is critical