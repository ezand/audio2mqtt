"""Dataset utilities for loading training audio data."""

import os
from pathlib import Path
from typing import List, Tuple

import tensorflow as tf

from audio_util import ensure_sample_rate
from scipy.io import wavfile


def scan_training_directory(training_dir: str) -> Tuple[List[str], List[str], List[str]]:
    """Scan training directory and extract files, labels, and classes.

    Expects structure: training_dir/class_name/*.wav

    Args:
        training_dir: Path to training directory.

    Returns:
        Tuple of (file_paths, labels, class_names) where labels are string class names.
    """
    training_path = Path(training_dir)

    if not training_path.exists():
        raise ValueError(f"Training directory does not exist: {training_dir}")

    class_dirs = [d for d in training_path.iterdir() if d.is_dir()]

    if not class_dirs:
        raise ValueError(f"No class directories found in {training_dir}")

    class_names = sorted([d.name for d in class_dirs])
    file_paths = []
    labels = []

    for class_dir in class_dirs:
        class_name = class_dir.name
        wav_files = list(class_dir.glob("*.wav"))

        for wav_file in wav_files:
            file_paths.append(str(wav_file))
            labels.append(class_name)

    return file_paths, labels, class_names


def load_wav_16k_mono(filename) -> tf.Tensor:
    """Load a WAV file and ensure it's 16kHz mono.

    Args:
        filename: Path to WAV file (str or tensor).

    Returns:
        Normalized waveform tensor in range [-1.0, 1.0].
    """
    # Convert tensor to string if needed
    if isinstance(filename, tf.Tensor):
        filename = filename.numpy().decode('utf-8')

    sample_rate, wav_data = wavfile.read(filename)
    sample_rate, wav_data = ensure_sample_rate(sample_rate, wav_data)

    # Normalize to [-1.0, 1.0]
    waveform = wav_data / tf.int16.max

    # Ensure it's a float32 tensor
    waveform = tf.cast(waveform, tf.float32)

    return waveform


def create_dataset(training_dir: str,
                   batch_size: int = 16) -> Tuple[tf.data.Dataset, List[str]]:
    """Create TensorFlow dataset from training directory.

    Args:
        training_dir: Path to training directory.
        batch_size: Batch size for dataset.

    Returns:
        Tuple of (dataset, class_names).
    """
    file_paths, labels, class_names = scan_training_directory(training_dir)

    # Create label to index mapping
    label_to_idx = {name: idx for idx, name in enumerate(class_names)}
    label_indices = [label_to_idx[label] for label in labels]

    # Create dataset
    filenames_ds = tf.data.Dataset.from_tensor_slices(file_paths)
    labels_ds = tf.data.Dataset.from_tensor_slices(label_indices)

    dataset = tf.data.Dataset.zip((filenames_ds, labels_ds))

    # Load audio files
    def load_audio_with_label(filename, label):
        waveform = tf.py_function(
            func=load_wav_16k_mono,
            inp=[filename],
            Tout=tf.float32
        )
        waveform.set_shape([None])
        return waveform, label

    dataset = dataset.map(load_audio_with_label, num_parallel_calls=tf.data.AUTOTUNE)

    # Use padded_batch to handle variable-length audio
    dataset = dataset.padded_batch(
        batch_size,
        padded_shapes=([None], []),
        padding_values=(0.0, 0)
    )
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    return dataset, class_names
