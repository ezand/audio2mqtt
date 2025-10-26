# Audio Device Setup

This guide covers setting up audio input devices for real-time audio recognition.

## Audio Input Methods

audio2mqtt supports two types of audio input:

1. **System Audio (Loopback)** - Capture audio output from your computer (games, videos, applications)
2. **Microphone** - Capture ambient/environmental sounds

## System Audio (Loopback) Setup

To capture system audio, you need a virtual audio device that creates a "loopback" - routing your computer's audio output back as an input.

### macOS

**Install BlackHole (Free & Open Source):**

1. Download [BlackHole 2ch](https://github.com/ExistentialAudio/BlackHole/releases)
2. Install the DMG package
3. Configure Multi-Output Device:
   - Open **Audio MIDI Setup** (Applications → Utilities → Audio MIDI Setup)
   - Click the **+** button at bottom-left
   - Select **Create Multi-Output Device**
   - Check both:
     - Your speakers/headphones (e.g., "MacBook Pro Speakers")
     - **BlackHole 2ch**
   - Right-click the Multi-Output Device → **Use This Device For Sound Output**
4. Set system output:
   - Open **System Preferences → Sound → Output**
   - Select the **Multi-Output Device** you created

**What this does:**
- Audio plays through your speakers/headphones normally
- Audio is also routed to BlackHole 2ch (which audio2mqtt can read)

**Verify setup:**
```bash
python listen.py --list
```
You should see "BlackHole 2ch" in the device list.

### Windows

**Option 1: Stereo Mix (Built-in)**

1. Right-click speaker icon in taskbar → **Open Sound settings**
2. Scroll down → **Sound Control Panel** (or **More sound settings**)
3. Go to **Recording** tab
4. Right-click in empty space → **Show Disabled Devices**
5. Right-click **Stereo Mix** → **Enable**
6. Set as default recording device (right-click → **Set as Default Device**)

**Option 2: VB-CABLE (Virtual Audio Cable)**

1. Download [VB-CABLE](https://vb-audio.com/Cable/)
2. Install the driver
3. Set **CABLE Output** as your default playback device
4. Set **CABLE Input** as your default recording device
5. (Optional) Use VB-Audio control panel to monitor audio through speakers

### Linux

**PulseAudio Monitor (Usually Built-in)**

PulseAudio provides monitor devices by default. List available devices:

```bash
pactl list sources short
```

Look for devices with `.monitor` suffix (e.g., `alsa_output.pci-0000_00_1f.3.analog-stereo.monitor`).

**Verify setup:**
```bash
python listen.py --list
```
You should see monitor devices in the list.

**Alternative: Create Loopback Manually**

```bash
# Load loopback module
pactl load-module module-loopback latency_msec=1

# Unload when done
pactl unload-module module-loopback
```

## Microphone Setup

No special setup required for microphone input. Just ensure your microphone is working:

### macOS
- **System Preferences → Security & Privacy → Microphone**
- Grant microphone access to Terminal or your Python environment

### Windows
- **Settings → Privacy → Microphone**
- Ensure "Allow apps to access your microphone" is enabled

### Linux
- Test microphone with `arecord` or `pavucontrol`
- Ensure correct device is set as default input

## Device Discovery

### List Available Devices

```bash
python listen.py --list
```

**Example output:**
```
Available audio input devices:
  [0] MacBook Pro Microphone (2 channels)
  [1] BlackHole 2ch (2 channels)
  [2] External Microphone (1 channel)
```

### Auto-Selection

**Auto-select loopback device (system audio):**
```bash
python listen.py
```
Looks for keywords: "BlackHole", "CABLE", "Loopback", "Stereo Mix", "monitor"

**Auto-select microphone:**
```bash
python listen.py --microphone
```
Looks for keywords: "Microphone", "Built-in", "Internal"

### Manual Selection

**By device name (substring match):**
```bash
python listen.py --device "BlackHole"
python listen.py --device "Stereo Mix"
python listen.py --device "MacBook Pro Microphone"
```

**By device ID:**
```bash
# List devices first to get IDs
python listen.py --list

# Select by ID
python listen.py --device-id 1
```

## Troubleshooting

### No Loopback Device Found

**macOS:**
- Ensure BlackHole is installed and Multi-Output Device is created
- Check that Multi-Output Device includes both speakers and BlackHole
- Verify system output is set to Multi-Output Device

**Windows:**
- Try both Stereo Mix and VB-CABLE methods
- Ensure driver is installed and device is enabled
- Check default recording device in Sound Control Panel

**Linux:**
- Verify PulseAudio is running: `pulseaudio --check`
- List sources: `pactl list sources short`
- Load loopback module manually if needed

### No Audio Detected

**Check energy threshold:**
```bash
# Lower threshold for quieter audio
python listen.py --energy-threshold -50 --verbose
```

**Verify audio is playing:**
- Play audio and check if device is receiving signal in system settings
- macOS: Audio MIDI Setup → Configure Speakers → Test
- Windows: Sound Control Panel → Recording → Watch level meter

**Test with different device:**
```bash
python listen.py --device "Different Device" --verbose
```

### Permission Errors

**macOS:**
- Grant microphone access in System Preferences → Security & Privacy
- Restart Terminal after granting access

**Linux:**
- Add user to `audio` group: `sudo usermod -a -G audio $USER`
- Logout and login for changes to take effect

### Audio Clipping / Distortion

**Reduce system volume:**
- High volume can cause clipping and false detections
- Keep system volume at 50-70% for best results

**Adjust energy threshold:**
```bash
python listen.py --energy-threshold -35
```

## Use Cases

### System Audio (Loopback)

**Best for:**
- Game audio events
- Video/streaming audio detection
- Application sound monitoring
- Browser tab audio (music, podcasts)
- System notification sounds

**Examples:**
```bash
# Detect game sounds
python listen.py --method fingerprint

# Detect music/songs playing
python listen.py --method fingerprint --window-duration 3.0

# Detect system alerts
python listen.py --method fingerprint --threshold 0.4
```

### Microphone

**Best for:**
- Environmental sound detection
- Voice command recognition
- Ambient audio monitoring
- Real-world event detection

**Examples:**
```bash
# Detect environmental sounds
python listen.py --microphone --method ml

# Voice commands
python listen.py --microphone --threshold 0.8

# Quiet ambient sounds
python listen.py --microphone --energy-threshold -50
```

## Audio Format Requirements

Both methods expect **16kHz mono audio** internally:

- **Sample rate**: 16,000 Hz (16kHz)
- **Channels**: Mono (1 channel)
- **Bit depth**: 16-bit (standard WAV format)

**Automatic conversion:**
- `audio_util.py` handles conversion automatically
- Stereo is downmixed to mono
- Sample rate is resampled to 16kHz
- Non-WAV formats supported with `pydub` + `ffmpeg`

## Performance Considerations

### CPU Usage

**Loopback devices:**
- Lower CPU usage (dedicated audio capture)
- More reliable for continuous monitoring

**Microphones:**
- Similar CPU usage
- May require more aggressive energy gating to filter noise

### Latency

**Typical latency**: ~100-200ms from audio event to detection

**Factors affecting latency:**
- Chunk duration (default 0.5s)
- Window duration (default 2.0s)
- Processing time (inference)
- Energy gating (can skip chunks)

**Reduce latency:**
```bash
# Shorter chunk duration (more CPU, less latency)
python listen.py --chunk-duration 0.3

# Shorter window duration (may reduce accuracy)
python listen.py --window-duration 1.0
```

## Next Steps

Once audio devices are set up:

1. **ML Method**: See [docs/ml.md](ml.md) for training and real-time classification
2. **Fingerprinting Method**: See [docs/fingerprinting.md](fingerprinting.md) for registration and recognition
3. **Utilities**: See [docs/utilities.md](utilities.md) for audio conversion and background generation