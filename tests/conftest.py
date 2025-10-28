"""Shared pytest fixtures for audio2mqtt tests."""

import sys
import tempfile
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import numpy as np
import pytest
import wave


# Mock soundcard module BEFORE any imports to avoid PulseAudio errors in CI
if 'soundcard' not in sys.modules:
    sys.modules['soundcard'] = MagicMock()


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_audio_file(temp_dir):
    """Create a sample WAV audio file at 44.1kHz mono."""
    audio_path = temp_dir / "test_audio.wav"

    # Generate 1 second of 440Hz sine wave
    sample_rate = 44100
    duration = 1.0
    frequency = 440.0

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(str(audio_path), 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    return audio_path


@pytest.fixture
def sample_audio_file_16khz(temp_dir):
    """Create a sample WAV audio file at 16kHz mono (non-optimal)."""
    audio_path = temp_dir / "test_audio_16k.wav"

    # Generate 1 second of 440Hz sine wave at 16kHz
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(str(audio_path), 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    return audio_path


@pytest.fixture
def sample_yaml_metadata(temp_dir):
    """Create a sample YAML metadata file."""
    yaml_path = temp_dir / "test_audio.yaml"
    yaml_content = """source: test_audio.wav
metadata:
  game: Test Game
  song: Test Song
  artist: Test Artist
debounce_seconds: 5.0
"""
    yaml_path.write_text(yaml_content)
    return yaml_path


@pytest.fixture
def mock_mqtt_config() -> Dict:
    """Provide a mock MQTT configuration."""
    return {
        'mqtt': {
            'broker': 'localhost',
            'port': 1883,
            'username': 'test_user',
            'password': 'test_pass',
            'topic_prefix': 'test_audio',
            'client_id_prefix': 'test_client',
            'keepalive': 60,
            'qos': 1,
            'retain': False,
            'debounce_seconds': 5.0
        }
    }


@pytest.fixture
def memory_db_config() -> Dict:
    """Provide an in-memory database configuration."""
    return {
        'database_type': 'memory',
        'database': {}
    }
