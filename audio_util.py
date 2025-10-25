import os
import sys
import csv
import numpy as np
from pathlib import Path
from scipy.io import wavfile
import scipy.signal
import tensorflow as tf

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


def class_names_from_csv(class_map_csv_text):
    """Returns list of class names corresponding to score vector."""
    class_namez = []
    with tf.io.gfile.GFile(class_map_csv_text) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            class_namez.append(row['display_name'])

    return class_namez


def convert_to_mono(audio_data):
    """Convert stereo audio to mono by averaging channels."""
    if len(audio_data.shape) == 2:
        return audio_data.mean(axis=1)
    return audio_data


def resample_audio(sample_rate, audio_data, target_rate=16000):
    """Resample audio to target sample rate."""
    if sample_rate != target_rate:
        num_samples = int(round(len(audio_data) * target_rate / sample_rate))
        audio_data = scipy.signal.resample(audio_data, num_samples)
    return audio_data


def convert_audio_to_yamnet_format(input_path, output_path, target_rate=16000):
    """
    Convert an audio file to YAMNet-compatible format (mono, 16kHz WAV).

    Supports: WAV, MP3, M4A, OGG, FLAC, and other formats supported by pydub.

    Args:
        input_path: Path to input audio file
        output_path: Path to output WAV file
        target_rate: Target sample rate (default: 16000 Hz)
    """
    input_ext = Path(input_path).suffix.lower()

    # If input is WAV, use scipy (faster)
    if input_ext == '.wav':
        sample_rate, audio_data = wavfile.read(input_path)
        audio_data = convert_to_mono(audio_data)
        audio_data = resample_audio(sample_rate, audio_data, target_rate)
        wavfile.write(output_path, target_rate, audio_data.astype(np.int16))
        return

    # For other formats, use pydub
    if not PYDUB_AVAILABLE:
        raise ImportError(
            f"pydub is required to convert {input_ext} files. "
            "Install it with: pip install pydub\n"
            "For MP3 support, also install ffmpeg: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
        )

    # Load audio with pydub
    audio = AudioSegment.from_file(input_path)

    # Convert to mono
    if audio.channels > 1:
        audio = audio.set_channels(1)

    # Resample to target rate
    if audio.frame_rate != target_rate:
        audio = audio.set_frame_rate(target_rate)

    # Export as 16-bit PCM WAV
    audio.export(output_path, format='wav', parameters=['-acodec', 'pcm_s16le'])


def convert_wav_to_yamnet_format(input_path, output_path, target_rate=16000):
    """
    Convert a WAV file to YAMNet-compatible format (mono, 16kHz).

    Deprecated: Use convert_audio_to_yamnet_format instead.

    Args:
        input_path: Path to input WAV file
        output_path: Path to output WAV file
        target_rate: Target sample rate (default: 16000 Hz)
    """
    convert_audio_to_yamnet_format(input_path, output_path, target_rate)


def convert_directory_to_yamnet_format(input_dir, output_dir, target_rate=16000):
    """
    Convert all audio files in a directory to YAMNet-compatible format.

    Supports: WAV, MP3, M4A, OGG, FLAC, and other formats.

    Args:
        input_dir: Directory containing input audio files
        output_dir: Directory for output WAV files
        target_rate: Target sample rate (default: 16000 Hz)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Supported audio extensions
    audio_extensions = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac', '.wma'}

    audio_files = [
        f for f in os.listdir(input_dir)
        if Path(f).suffix.lower() in audio_extensions
    ]

    if not audio_files:
        print(f"No audio files found in {input_dir}")
        return

    print(f"Found {len(audio_files)} audio files")

    for audio_file in audio_files:
        input_path = os.path.join(input_dir, audio_file)
        # Change output extension to .wav
        output_file = Path(audio_file).stem + '.wav'
        output_path = os.path.join(output_dir, output_file)

        try:
            convert_audio_to_yamnet_format(input_path, output_path, target_rate)
            print(f"Converted: {audio_file} -> {output_file}")
        except Exception as e:
            print(f"Error converting {audio_file}: {e}")


def ensure_sample_rate(original_sample_rate, waveform,
                       desired_sample_rate=16000):
    """Resample waveform if required."""
    if original_sample_rate != desired_sample_rate:
        desired_length = int(round(float(len(waveform)) /
                                   original_sample_rate * desired_sample_rate))
        waveform = scipy.signal.resample(waveform, desired_length)
    return desired_sample_rate, waveform


def main():
    if len(sys.argv) < 2:
        print("Usage: python audio_util.py <action> [args...]")
        print("Actions:")
        print("  convert <input_dir> <output_dir>  - Convert audio files to YAMNet format")
        print("\nSupported formats: WAV, MP3, M4A, OGG, FLAC, AAC, WMA")
        print("Note: Non-WAV formats require pydub (pip install pydub) and ffmpeg")
        sys.exit(1)

    action = sys.argv[1]

    if action == "convert":
        if len(sys.argv) != 4:
            print("Usage: python audio_util.py convert <input_dir> <output_dir>")
            sys.exit(1)

        input_dir = sys.argv[2]
        output_dir = sys.argv[3]

        if not os.path.isdir(input_dir):
            print(f"Error: {input_dir} is not a valid directory")
            sys.exit(1)

        if not PYDUB_AVAILABLE:
            print("Warning: pydub not installed. Only WAV files will be converted.")
            print("To convert MP3, M4A, OGG, etc., install: pip install pydub")
            print("For MP3 support, also install ffmpeg.")

        convert_directory_to_yamnet_format(input_dir, output_dir)
        print(f"\nConversion complete. Files saved to {output_dir}")
    else:
        print(f"Error: Unknown action '{action}'")
        print("Available actions: convert")
        sys.exit(1)


if __name__ == "__main__":
    main()
