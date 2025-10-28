"""Tests for audio_utils module."""

import pytest
from pathlib import Path

from audio_utils import (
    get_audio_info,
    needs_conversion,
    create_yaml_scaffold,
    find_audio_files,
    OPTIMAL_SAMPLE_RATE,
    OPTIMAL_CHANNELS,
    OPTIMAL_FORMAT
)


def test_get_audio_info(sample_audio_file):
    """Test getting audio file information."""
    info = get_audio_info(sample_audio_file)

    assert info is not None
    assert info['sample_rate'] == 44100
    assert info['channels'] == 1
    assert info['codec'] in ['pcm_s16le', 'pcm_s16be']
    assert info['duration'] > 0


def test_get_audio_info_16khz(sample_audio_file_16khz):
    """Test getting audio info for 16kHz file."""
    info = get_audio_info(sample_audio_file_16khz)

    assert info is not None
    assert info['sample_rate'] == 16000
    assert info['channels'] == 1


def test_get_audio_info_nonexistent_file(temp_dir):
    """Test getting audio info for non-existent file."""
    fake_path = temp_dir / "nonexistent.wav"
    info = get_audio_info(fake_path)

    assert info is None


def test_needs_conversion_optimal_file(sample_audio_file):
    """Test that optimal format file doesn't need conversion."""
    needs_conv, reason = needs_conversion(sample_audio_file)

    assert needs_conv == False
    assert reason == "Already optimal"


def test_needs_conversion_16khz_file(sample_audio_file_16khz):
    """Test that 16kHz file needs conversion."""
    needs_conv, reason = needs_conversion(sample_audio_file_16khz)

    assert needs_conv == True
    assert "16000Hz → 44100Hz" in reason


def test_needs_conversion_nonexistent_file(temp_dir):
    """Test needs_conversion with non-existent file."""
    fake_path = temp_dir / "nonexistent.wav"
    needs_conv, reason = needs_conversion(fake_path)

    assert needs_conv == True
    assert "Unable to read audio info" in reason


def test_create_yaml_scaffold_basic(temp_dir, sample_audio_file):
    """Test creating basic YAML scaffold."""
    success, message = create_yaml_scaffold(sample_audio_file)

    assert success == True
    assert "Created" in message

    yaml_path = sample_audio_file.with_suffix('.yaml')
    assert yaml_path.exists()

    # Read and verify content
    import yaml
    with open(yaml_path) as f:
        content = yaml.safe_load(f)

    assert content['source'] == sample_audio_file.name
    assert 'metadata' in content
    assert content['metadata']['song'] == sample_audio_file.stem


def test_create_yaml_scaffold_with_metadata(temp_dir, sample_audio_file):
    """Test creating YAML scaffold with additional metadata."""
    metadata = {
        'game': 'Test Game',
        'artist': 'Test Artist'
    }

    success, message = create_yaml_scaffold(
        sample_audio_file,
        metadata=metadata
    )

    assert success == True

    yaml_path = sample_audio_file.with_suffix('.yaml')

    import yaml
    with open(yaml_path) as f:
        content = yaml.safe_load(f)

    assert content['metadata']['game'] == 'Test Game'
    assert content['metadata']['artist'] == 'Test Artist'
    assert content['metadata']['song'] == sample_audio_file.stem


def test_create_yaml_scaffold_with_debounce(temp_dir, sample_audio_file):
    """Test creating YAML scaffold with debounce setting."""
    success, message = create_yaml_scaffold(
        sample_audio_file,
        debounce_seconds=10.0
    )

    assert success == True

    yaml_path = sample_audio_file.with_suffix('.yaml')

    import yaml
    with open(yaml_path) as f:
        content = yaml.safe_load(f)

    assert content['debounce_seconds'] == 10.0


def test_create_yaml_scaffold_no_overwrite(temp_dir, sample_audio_file):
    """Test that scaffold creation fails without overwrite flag."""
    # Create first scaffold
    create_yaml_scaffold(sample_audio_file)

    # Try to create again without overwrite
    success, message = create_yaml_scaffold(sample_audio_file, overwrite=False)

    assert success == False
    assert "already exists" in message


def test_create_yaml_scaffold_with_overwrite(temp_dir, sample_audio_file):
    """Test that scaffold can be overwritten with flag."""
    # Create first scaffold
    create_yaml_scaffold(sample_audio_file)

    # Overwrite with new metadata
    success, message = create_yaml_scaffold(
        sample_audio_file,
        overwrite=True,
        metadata={'new_field': 'new_value'}
    )

    assert success == True

    yaml_path = sample_audio_file.with_suffix('.yaml')

    import yaml
    with open(yaml_path) as f:
        content = yaml.safe_load(f)

    assert content['metadata']['new_field'] == 'new_value'


def test_find_audio_files_single_file(temp_dir, sample_audio_file):
    """Test finding audio files in directory."""
    files = find_audio_files(temp_dir, recursive=False)

    assert len(files) == 1
    assert sample_audio_file in files


def test_find_audio_files_multiple_files(temp_dir):
    """Test finding multiple audio files."""
    # Create multiple files
    (temp_dir / "file1.wav").write_text("")
    (temp_dir / "file2.mp3").write_text("")
    (temp_dir / "file3.txt").write_text("")  # Non-audio file

    files = find_audio_files(temp_dir, recursive=False)

    assert len(files) >= 2
    # Should find .wav and .mp3, but not .txt
    assert any(f.suffix == '.wav' for f in files)
    assert any(f.suffix == '.mp3' for f in files)
    assert not any(f.suffix == '.txt' for f in files)


def test_find_audio_files_recursive(temp_dir):
    """Test finding audio files recursively."""
    # Create subdirectory with audio file
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.wav").write_text("")
    (temp_dir / "root.wav").write_text("")

    files = find_audio_files(temp_dir, recursive=True)

    assert len(files) == 2
    assert any('nested.wav' in str(f) for f in files)
    assert any('root.wav' in str(f) for f in files)


def test_find_audio_files_non_recursive(temp_dir):
    """Test finding audio files non-recursively."""
    # Create subdirectory with audio file
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.wav").write_text("")
    (temp_dir / "root.wav").write_text("")

    files = find_audio_files(temp_dir, recursive=False)

    assert len(files) == 1
    assert any('root.wav' in str(f) for f in files)
    assert not any('nested.wav' in str(f) for f in files)


def test_find_audio_files_empty_directory(temp_dir):
    """Test finding audio files in empty directory."""
    empty_dir = temp_dir / "empty"
    empty_dir.mkdir()

    files = find_audio_files(empty_dir, recursive=True)

    assert len(files) == 0
