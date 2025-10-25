import os
import sys
import csv
import numpy as np
from scipy.io import wavfile
import scipy.signal
import tensorflow as tf


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


def convert_wav_to_yamnet_format(input_path, output_path, target_rate=16000):
    """
    Convert a WAV file to YAMNet-compatible format (mono, 16kHz).

    Args:
        input_path: Path to input WAV file
        output_path: Path to output WAV file
        target_rate: Target sample rate (default: 16000 Hz)
    """
    sample_rate, audio_data = wavfile.read(input_path)

    # Convert to mono
    audio_data = convert_to_mono(audio_data)

    # Resample to target rate
    audio_data = resample_audio(sample_rate, audio_data, target_rate)

    # Save as 16-bit PCM WAV
    wavfile.write(output_path, target_rate, audio_data.astype(np.int16))


def convert_directory_to_yamnet_format(input_dir, output_dir, target_rate=16000):
    """
    Convert all WAV files in a directory to YAMNet-compatible format.

    Args:
        input_dir: Directory containing input WAV files
        output_dir: Directory for output WAV files
        target_rate: Target sample rate (default: 16000 Hz)
    """
    os.makedirs(output_dir, exist_ok=True)

    wav_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.wav')]

    for wav_file in wav_files:
        input_path = os.path.join(input_dir, wav_file)
        output_path = os.path.join(output_dir, wav_file)

        try:
            convert_wav_to_yamnet_format(input_path, output_path, target_rate)
            print(f"Converted: {wav_file}")
        except Exception as e:
            print(f"Error converting {wav_file}: {e}")


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
        print("  convert <input_dir> <output_dir>  - Convert directory of WAV files")
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

        convert_directory_to_yamnet_format(input_dir, output_dir)
        print(f"Conversion complete. Files saved to {output_dir}")
    else:
        print(f"Error: Unknown action '{action}'")
        print("Available actions: convert")
        sys.exit(1)


if __name__ == "__main__":
    main()
