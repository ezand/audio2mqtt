"""Audio utility functions for fingerprinting preparation.

This module provides utilities for:
- Recording audio from devices (loopback or microphone)
- Batch converting audio files to optimal format (44.1kHz mono WAV)
- Creating YAML metadata scaffolds for fingerprinting workflow
"""

import argparse
import json
import subprocess
import sys
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
import soundcard as sc
import yaml

from audio_device import select_device, list_audio_devices, print_devices


# Optimal format for Dejavu fingerprinting
OPTIMAL_SAMPLE_RATE = 44100  # Hz (Dejavu DEFAULT_FS)
OPTIMAL_CHANNELS = 1  # Mono
OPTIMAL_FORMAT = 'wav'
OPTIMAL_BIT_DEPTH = 16  # 16-bit PCM

# Supported input formats
SUPPORTED_EXTENSIONS = ['.mp3', '.m4a', '.ogg', '.flac', '.wav', '.aiff', '.aac', '.wma']


def get_audio_info(file_path: Path) -> Optional[Dict]:
    """Get audio file information using ffprobe.

    Args:
        file_path: Path to audio file.

    Returns:
        Dictionary with sample_rate, channels, codec, duration, or None if error.
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'stream=sample_rate,channels,codec_name,duration',
                '-of', 'json',
                str(file_path)
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        streams = data.get('streams', [])

        if not streams:
            return None

        # Get first audio stream
        audio_stream = next((s for s in streams if 'sample_rate' in s), None)
        if not audio_stream:
            return None

        return {
            'sample_rate': int(audio_stream.get('sample_rate', 0)),
            'channels': int(audio_stream.get('channels', 0)),
            'codec': audio_stream.get('codec_name', 'unknown'),
            'duration': float(audio_stream.get('duration', 0))
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return None


def needs_conversion(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Check if audio file needs conversion to optimal format.

    Args:
        file_path: Path to audio file.

    Returns:
        Tuple of (needs_conversion, reason).
    """
    info = get_audio_info(file_path)

    if info is None:
        return (True, "Unable to read audio info")

    issues = []

    if info['sample_rate'] != OPTIMAL_SAMPLE_RATE:
        issues.append(f"{info['sample_rate']}Hz → {OPTIMAL_SAMPLE_RATE}Hz")

    if info['channels'] != OPTIMAL_CHANNELS:
        issues.append(f"{info['channels']}ch → {OPTIMAL_CHANNELS}ch")

    if file_path.suffix.lower() != f'.{OPTIMAL_FORMAT}':
        issues.append(f"{file_path.suffix} → .{OPTIMAL_FORMAT}")

    if issues:
        return (True, ", ".join(issues))

    return (False, "Already optimal")


def convert_to_fingerprint_format(
    input_path: Path,
    output_path: Optional[Path] = None,
    overwrite: bool = False
) -> Tuple[bool, str]:
    """Convert audio file to optimal fingerprinting format.

    Args:
        input_path: Path to input audio file.
        output_path: Path to output file (defaults to input_path with .wav extension).
        overwrite: Whether to overwrite existing output file.

    Returns:
        Tuple of (success, message).
    """
    if not input_path.exists():
        return (False, f"Input file not found: {input_path}")

    # Determine output path
    if output_path is None:
        output_path = input_path.with_suffix('.wav')

    # Check if trying to convert file to itself
    use_temp_file = (input_path == output_path and overwrite)

    if input_path == output_path and not overwrite:
        return (False, "Input and output are the same file (use --overwrite or --output)")

    # Check if output exists
    if output_path.exists() and not overwrite and not use_temp_file:
        return (False, f"Output file exists (use --overwrite): {output_path}")

    # If converting to same file, use temp file as intermediate
    # Use .tmp.wav so ffmpeg recognizes the format
    if use_temp_file:
        actual_output = output_path.parent / f"{output_path.stem}.tmp.wav"
    else:
        actual_output = output_path

    # Convert using ffmpeg
    temp_file_created = False
    try:
        result = subprocess.run(
            [
                'ffmpeg',
                '-i', str(input_path),
                '-ar', str(OPTIMAL_SAMPLE_RATE),  # Sample rate
                '-ac', str(OPTIMAL_CHANNELS),     # Channels (mono)
                '-sample_fmt', 's16',              # 16-bit PCM
                '-y' if (overwrite or use_temp_file) else '-n',  # Overwrite or not
                str(actual_output)
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            error_msg = result.stderr.split('\n')[-2] if result.stderr else 'Unknown error'
            # Clean up temp file on error
            if use_temp_file and actual_output.exists():
                actual_output.unlink()
            return (False, f"ffmpeg error: {error_msg}")

        temp_file_created = use_temp_file

        # If using temp file, replace original with converted version
        if use_temp_file:
            actual_output.replace(output_path)

        return (True, f"Converted: {output_path.name}")

    except subprocess.TimeoutExpired:
        # Clean up temp file on timeout
        if use_temp_file and actual_output.exists():
            actual_output.unlink()
        return (False, "Conversion timeout (>60s)")
    except subprocess.SubprocessError as e:
        # Clean up temp file on error
        if use_temp_file and actual_output.exists():
            actual_output.unlink()
        return (False, f"Conversion error: {e}")
    except Exception as e:
        # Clean up temp file on any unexpected error
        if temp_file_created and actual_output.exists():
            actual_output.unlink()
        return (False, f"Unexpected error: {e}")


def find_audio_files(directory: Path, recursive: bool = True) -> List[Path]:
    """Find all audio files in directory.

    Args:
        directory: Directory to search.
        recursive: Search subdirectories recursively.

    Returns:
        List of audio file paths.
    """
    audio_files = []

    pattern = '**/*' if recursive else '*'

    for ext in SUPPORTED_EXTENSIONS:
        audio_files.extend(directory.glob(f"{pattern}{ext}"))
        audio_files.extend(directory.glob(f"{pattern}{ext.upper()}"))

    return sorted(set(audio_files))


def batch_convert_directory(
    directory: Path,
    output_dir: Optional[Path] = None,
    recursive: bool = True,
    overwrite: bool = False,
    in_place: bool = False,
    dry_run: bool = False,
    skip_optimal: bool = True
) -> Dict:
    """Batch convert audio files in directory to optimal format.

    Args:
        directory: Directory containing audio files.
        output_dir: Output directory (if not in_place).
        recursive: Search subdirectories recursively.
        overwrite: Overwrite existing output files.
        in_place: Convert files in place (replace originals).
        dry_run: Preview changes without converting.
        skip_optimal: Skip files already in optimal format.

    Returns:
        Dictionary with conversion statistics.
    """
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return {'error': 'Directory not found'}

    # Find all audio files
    audio_files = find_audio_files(directory, recursive=recursive)

    if not audio_files:
        print(f"No audio files found in {directory}")
        return {'total': 0, 'converted': 0, 'skipped': 0, 'failed': 0}

    stats = {
        'total': len(audio_files),
        'converted': 0,
        'skipped': 0,
        'failed': 0,
        'errors': []
    }

    print(f"\nFound {len(audio_files)} audio file(s) in {directory}")
    if dry_run:
        print("DRY RUN MODE - No files will be converted\n")
    else:
        print()

    for i, input_file in enumerate(audio_files, 1):
        # Check if needs conversion
        needs_conv, reason = needs_conversion(input_file)

        prefix = f"[{i}/{len(audio_files)}]"

        if not needs_conv and skip_optimal:
            print(f"{prefix} SKIP: {input_file.name} ({reason})")
            stats['skipped'] += 1
            continue

        # Determine output path
        if in_place:
            output_file = input_file.with_suffix('.wav')
        elif output_dir:
            # Preserve directory structure relative to input directory
            relative_path = input_file.relative_to(directory)
            output_file = output_dir / relative_path.with_suffix('.wav')
            output_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_file = input_file.with_suffix('.wav')

        if dry_run:
            print(f"{prefix} WOULD CONVERT: {input_file.name} ({reason})")
            print(f"                 → {output_file.relative_to(directory.parent)}")
            stats['converted'] += 1
        else:
            print(f"{prefix} CONVERTING: {input_file.name} ({reason})")
            success, message = convert_to_fingerprint_format(
                input_file,
                output_file,
                overwrite=overwrite
            )

            if success:
                print(f"             ✓ {message}")
                stats['converted'] += 1
            else:
                print(f"             ✗ {message}")
                stats['failed'] += 1
                stats['errors'].append(f"{input_file.name}: {message}")

    # Print summary
    print(f"\n{'='*60}")
    print("Conversion Summary:")
    print(f"  Total files:     {stats['total']}")
    print(f"  Converted:       {stats['converted']}")
    print(f"  Skipped:         {stats['skipped']}")
    print(f"  Failed:          {stats['failed']}")

    if stats['errors']:
        print(f"\nErrors:")
        for error in stats['errors']:
            print(f"  - {error}")

    return stats


def create_yaml_scaffold(
    audio_file: Path,
    overwrite: bool = False,
    metadata: Optional[Dict] = None,
    debounce_seconds: Optional[float] = None
) -> Tuple[bool, str]:
    """Create YAML metadata scaffold file for audio file.

    Args:
        audio_file: Path to audio file.
        overwrite: Whether to overwrite existing YAML file.
        metadata: Optional additional metadata fields to include.
        debounce_seconds: Optional MQTT debounce duration in seconds.

    Returns:
        Tuple of (success, message).
    """
    if not audio_file.exists():
        return (False, f"Audio file not found: {audio_file}")

    # Determine YAML path
    yaml_path = audio_file.with_suffix('.yaml')

    # Check if YAML exists
    if yaml_path.exists() and not overwrite:
        return (False, f"YAML file already exists (use --overwrite): {yaml_path}")

    # Create scaffold with minimal metadata
    song_name = audio_file.stem

    scaffold = {
        'source': audio_file.name,
        'metadata': {
            'song': song_name
        }
    }

    # Add any additional metadata fields
    if metadata:
        scaffold['metadata'].update(metadata)

    # Add debounce_seconds at top level if specified
    if debounce_seconds is not None:
        scaffold['debounce_seconds'] = debounce_seconds

    # Write YAML file
    try:
        with open(yaml_path, 'w') as f:
            yaml.dump(scaffold, f, default_flow_style=False, sort_keys=False)
        return (True, f"Created: {yaml_path.name}")
    except Exception as e:
        return (False, f"Error writing YAML: {e}")


def batch_create_yaml_scaffolds(
    directory: Path,
    recursive: bool = True,
    overwrite: bool = False,
    skip_existing: bool = True,
    metadata: Optional[Dict] = None,
    debounce_seconds: Optional[float] = None
) -> Dict:
    """Create YAML metadata scaffolds for audio files in directory.

    Args:
        directory: Directory containing audio files.
        recursive: Search subdirectories recursively.
        overwrite: Overwrite existing YAML files.
        skip_existing: Skip files that already have YAML metadata.
        metadata: Optional additional metadata fields to include.
        debounce_seconds: Optional MQTT debounce duration in seconds.

    Returns:
        Dictionary with creation statistics.
    """
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return {'error': 'Directory not found'}

    # Find all audio files
    audio_files = find_audio_files(directory, recursive=recursive)

    if not audio_files:
        print(f"No audio files found in {directory}")
        return {'total': 0, 'created': 0, 'skipped': 0, 'failed': 0}

    stats = {
        'total': len(audio_files),
        'created': 0,
        'skipped': 0,
        'failed': 0,
        'errors': []
    }

    print(f"\nFound {len(audio_files)} audio file(s) in {directory}\n")

    for i, audio_file in enumerate(audio_files, 1):
        prefix = f"[{i}/{len(audio_files)}]"

        # Check if YAML already exists
        yaml_path = audio_file.with_suffix('.yaml')
        if yaml_path.exists() and skip_existing and not overwrite:
            print(f"{prefix} SKIP: {audio_file.name} (YAML exists)")
            stats['skipped'] += 1
            continue

        # Create YAML scaffold
        success, message = create_yaml_scaffold(
            audio_file,
            overwrite=overwrite,
            metadata=metadata,
            debounce_seconds=debounce_seconds
        )

        if success:
            print(f"{prefix} ✓ {message}")
            stats['created'] += 1
        else:
            print(f"{prefix} ✗ {message}")
            stats['failed'] += 1
            stats['errors'].append(f"{audio_file.name}: {message}")

    # Print summary
    print(f"\n{'='*60}")
    print("YAML Creation Summary:")
    print(f"  Total files:     {stats['total']}")
    print(f"  Created:         {stats['created']}")
    print(f"  Skipped:         {stats['skipped']}")
    print(f"  Failed:          {stats['failed']}")

    if stats['errors']:
        print(f"\nErrors:")
        for error in stats['errors']:
            print(f"  - {error}")

    return stats


# Global flag for handling interrupt signal
_recording_active = False


def signal_handler(signum, frame):
    """Handle Ctrl+C interrupt signal."""
    global _recording_active
    if _recording_active:
        print("\n\nRecording interrupted by user. Saving file...")
        _recording_active = False


def record_audio(
    output_path: Path,
    device_id: Optional[int] = None,
    device_name: Optional[str] = None,
    use_microphone: bool = False,
    duration: Optional[float] = None,
    sample_rate: int = OPTIMAL_SAMPLE_RATE
) -> Tuple[bool, str]:
    """Record audio from specified device to WAV file.

    Args:
        output_path: Path to output WAV file.
        device_id: Device ID to record from.
        device_name: Device name to search for (substring match).
        use_microphone: If True, auto-select microphone instead of loopback.
        duration: Recording duration in seconds (None = record until interrupted).
        sample_rate: Sample rate in Hz (default: 44100).

    Returns:
        Tuple of (success, message).
    """
    global _recording_active

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Select device
    device = select_device(
        device_id=device_id,
        device_name=device_name,
        auto_select_loopback=not use_microphone,
        prefer_microphone=use_microphone
    )

    if device is None:
        return (False, "No suitable device found")

    # Check if output file already exists
    if output_path.exists():
        return (False, f"Output file already exists: {output_path}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nRecording to: {output_path}")
    print(f"Sample rate: {sample_rate} Hz")
    if duration:
        print(f"Duration: {duration:.1f}s")
    else:
        print("Duration: Until interrupted (Ctrl+C)")
    print(f"\nPress Ctrl+C to stop recording...\n")

    # Get device's native channel count
    device_channels = device.channels
    print(f"Device channels: {device_channels}")

    # Start recording
    _recording_active = True
    start_time = time.time()
    chunks = []

    try:
        # Record at device's native channel count
        with device.recorder(samplerate=sample_rate, channels=device_channels) as recorder:
            while _recording_active:
                # Record in 0.5s chunks
                chunk = recorder.record(numframes=int(sample_rate * 0.5))
                chunks.append(chunk)

                elapsed = time.time() - start_time

                # Print progress
                print(f"\rRecording... {elapsed:.1f}s", end='', flush=True)

                # Check duration limit
                if duration and elapsed >= duration:
                    break

    except Exception as e:
        return (False, f"Recording error: {e}")

    # Concatenate all chunks
    if not chunks:
        return (False, "No audio data recorded")

    audio_data = np.concatenate(chunks, axis=0)

    # Convert to mono if stereo/multi-channel
    if audio_data.ndim > 1 and audio_data.shape[1] > 1:
        # Average all channels to mono
        audio_data = np.mean(audio_data, axis=1)
    elif audio_data.ndim > 1:
        # Single channel, flatten
        audio_data = audio_data[:, 0]

    duration_actual = len(audio_data) / sample_rate

    # Save to WAV file
    try:
        # Ensure audio is mono at this point
        if audio_data.ndim > 1:
            audio_data = audio_data.flatten()

        # Write WAV file
        import wave
        with wave.open(str(output_path), 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            # Convert float32 to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())

        print(f"\n\n✓ Recording saved: {output_path.name}")
        print(f"  Duration: {duration_actual:.2f}s")
        print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")

        return (True, f"Recorded {duration_actual:.2f}s to {output_path}")

    except Exception as e:
        return (False, f"Error saving file: {e}")
    finally:
        _recording_active = False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Audio utilities for Dejavu fingerprinting (conversion, recording, metadata)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record audio from device
  python audio_utils.py record output.wav
  python audio_utils.py record output.wav --microphone --duration 10

  # Preview conversions (dry run)
  python audio_utils.py convert source_sounds/ --dry-run

  # Convert all files recursively
  python audio_utils.py convert source_sounds/ --recursive

  # Check file info
  python audio_utils.py info audio.mp3

  # Create YAML metadata scaffolds
  python audio_utils.py create-yaml source_sounds/ --recursive
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert audio files')
    convert_parser.add_argument('path', type=Path, help='File or directory to convert')
    convert_parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    convert_parser.add_argument('-r', '--recursive', action='store_true', help='Search subdirectories recursively')
    convert_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output files')
    convert_parser.add_argument('--in-place', action='store_true', help='Convert files in place (replace originals)')
    convert_parser.add_argument('--dry-run', action='store_true', help='Preview changes without converting')
    convert_parser.add_argument('--include-optimal', action='store_true', help='Include files already in optimal format')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show audio file information')
    info_parser.add_argument('path', type=Path, help='Audio file path')

    # Create-yaml command
    yaml_parser = subparsers.add_parser('create-yaml', help='Create YAML metadata scaffolds')
    yaml_parser.add_argument('path', type=Path, help='File or directory')
    yaml_parser.add_argument('-r', '--recursive', action='store_true', help='Search subdirectories recursively')
    yaml_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing YAML files')
    yaml_parser.add_argument('--include-existing', action='store_true', help='Include files that already have YAML')
    yaml_parser.add_argument('--meta', action='append', metavar='KEY=VALUE',
                           help='Add metadata field (can be used multiple times, e.g., --meta game="Super Mario" --meta year=1990)')
    yaml_parser.add_argument('--debounce', type=float, metavar='SECONDS',
                           help='Set MQTT debounce duration in seconds (e.g., --debounce 10.0)')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record audio from device')
    record_parser.add_argument('output', type=Path, help='Output WAV file path')
    record_parser.add_argument('--device-id', type=int, metavar='ID', help='Device ID to record from')
    record_parser.add_argument('--device', type=str, metavar='NAME', help='Device name to search for (substring match)')
    record_parser.add_argument('--microphone', action='store_true', help='Use microphone instead of loopback device')
    record_parser.add_argument('--duration', type=float, metavar='SECONDS', help='Recording duration in seconds (default: until Ctrl+C)')
    record_parser.add_argument('--sample-rate', type=int, metavar='HZ', default=OPTIMAL_SAMPLE_RATE,
                             help=f'Sample rate in Hz (default: {OPTIMAL_SAMPLE_RATE})')
    record_parser.add_argument('--list-devices', action='store_true', help='List available devices and exit')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == 'info':
        if not args.path.exists():
            print(f"Error: File not found: {args.path}")
            return 1

        info = get_audio_info(args.path)
        if info is None:
            print(f"Error: Unable to read audio info from {args.path}")
            return 1

        needs_conv, reason = needs_conversion(args.path)

        print(f"\nAudio File: {args.path.name}")
        print(f"  Sample rate:  {info['sample_rate']} Hz")
        print(f"  Channels:     {info['channels']}")
        print(f"  Codec:        {info['codec']}")
        print(f"  Duration:     {info['duration']:.2f}s")
        print(f"  Format:       {args.path.suffix}")
        print(f"\nOptimal format: {OPTIMAL_SAMPLE_RATE}Hz, {OPTIMAL_CHANNELS}ch, .{OPTIMAL_FORMAT}")
        print(f"Needs conversion: {needs_conv}")
        if needs_conv:
            print(f"  Changes: {reason}")

        return 0

    if args.command == 'convert':
        if args.path.is_file():
            # Single file conversion
            success, message = convert_to_fingerprint_format(
                args.path,
                args.output,
                overwrite=args.overwrite
            )
            print(message)
            return 0 if success else 1

        elif args.path.is_dir():
            # Batch conversion
            stats = batch_convert_directory(
                args.path,
                output_dir=args.output,
                recursive=args.recursive,
                overwrite=args.overwrite,
                in_place=args.in_place,
                dry_run=args.dry_run,
                skip_optimal=not args.include_optimal
            )
            return 0 if stats.get('failed', 0) == 0 else 1

        else:
            print(f"Error: Path not found: {args.path}")
            return 1

    if args.command == 'create-yaml':
        # Build additional metadata from --meta KEY=VALUE arguments
        additional_metadata = {}
        if args.meta:
            for item in args.meta:
                if '=' not in item:
                    print(f"Error: Invalid --meta format: '{item}' (expected KEY=VALUE)")
                    return 1
                key, value = item.split('=', 1)
                additional_metadata[key] = value

        if args.path.is_file():
            # Single file YAML creation
            success, message = create_yaml_scaffold(
                args.path,
                overwrite=args.overwrite,
                metadata=additional_metadata if additional_metadata else None,
                debounce_seconds=args.debounce
            )
            print(message)
            return 0 if success else 1

        elif args.path.is_dir():
            # Batch YAML creation
            stats = batch_create_yaml_scaffolds(
                args.path,
                recursive=args.recursive,
                overwrite=args.overwrite,
                skip_existing=not args.include_existing,
                metadata=additional_metadata if additional_metadata else None,
                debounce_seconds=args.debounce
            )
            return 0 if stats.get('failed', 0) == 0 else 1

        else:
            print(f"Error: Path not found: {args.path}")
            return 1

    if args.command == 'record':
        # List devices if requested
        if args.list_devices:
            devices = list_audio_devices(include_loopback=True)
            print_devices(devices)
            return 0

        # Record audio
        success, message = record_audio(
            output_path=args.output,
            device_id=args.device_id,
            device_name=args.device,
            use_microphone=args.microphone,
            duration=args.duration,
            sample_rate=args.sample_rate
        )

        if not success:
            print(f"Error: {message}")
            return 1

        return 0


if __name__ == '__main__':
    sys.exit(main())
