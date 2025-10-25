"""YAMNet audio classification utilities."""

from typing import List, Tuple

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from scipy.io import wavfile

from audio_util import ensure_sample_rate
from class_map import load_class_names


YAMNET_MODEL_HANDLE = 'https://tfhub.dev/google/yamnet/1'


def load_yamnet_model():
    """Load YAMNet model from TensorFlow Hub.

    Returns:
        Loaded YAMNet model.
    """
    return hub.load(YAMNET_MODEL_HANDLE)


def load_audio(wav_file_path: str) -> Tuple[int, np.ndarray]:
    """Load and prepare audio file.

    Args:
        wav_file_path: Path to WAV file.

    Returns:
        Tuple of (sample_rate, waveform data).
    """
    sample_rate, wav_data = wavfile.read(wav_file_path, 'rb')
    return ensure_sample_rate(sample_rate, wav_data)


def normalize_waveform(wav_data: np.ndarray) -> np.ndarray:
    """Normalize waveform to [-1, 1] range.

    Args:
        wav_data: Raw waveform data.

    Returns:
        Normalized waveform.
    """
    return wav_data / tf.int16.max


def classify_audio(model, waveform: np.ndarray, class_names: List[str]) -> str:
    """Classify audio waveform using YAMNet model.

    Args:
        model: Loaded YAMNet model.
        waveform: Normalized audio waveform.
        class_names: List of class names.

    Returns:
        Inferred class name with highest mean score.
    """
    scores, embeddings, spectrogram = model(waveform)
    scores_np = scores.numpy()
    top_class_index = scores_np.mean(axis=0).argmax()
    return class_names[top_class_index]


def print_audio_info(sample_rate: int, wav_data: np.ndarray) -> None:
    """Print basic audio information.

    Args:
        sample_rate: Audio sample rate in Hz.
        wav_data: Raw waveform data.
    """
    duration = len(wav_data) / sample_rate
    print(f'Sample rate: {sample_rate} Hz')
    print(f'Total duration: {duration:.2f}s')
    print(f'Size of the input: {len(wav_data)}')