"""Generate background/negative audio samples for training.

This utility helps create a diverse 'background' class to solve the single-class
training problem. Without negative samples, softmax always outputs 100% confidence
for the only trained class.

Strategies:
1. Extract random segments from long audio files (podcasts, music, ambient noise)
2. Generate synthetic noise (white, pink, brown)
3. Record system audio for a period and auto-segment it
"""

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
from scipy.io import wavfile

# Optional imports
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


def generate_white_noise(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate white noise audio.

    Args:
        duration_seconds: Duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Audio samples as float32 array in range [-1, 1].
    """
    num_samples = int(duration_seconds * sample_rate)
    noise = np.random.uniform(-1.0, 1.0, num_samples).astype(np.float32)
    return noise


def generate_pink_noise(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate pink noise audio (1/f noise, more natural sounding).

    Args:
        duration_seconds: Duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Audio samples as float32 array in range [-1, 1].
    """
    num_samples = int(duration_seconds * sample_rate)

    # Generate white noise
    white = np.random.randn(num_samples)

    # Apply 1/f filter via FFT
    fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(num_samples, 1.0 / sample_rate)

    # Avoid division by zero
    freqs[0] = 1.0

    # Apply 1/sqrt(f) scaling for pink noise
    fft = fft / np.sqrt(freqs)

    # Convert back to time domain
    pink = np.fft.irfft(fft, num_samples)

    # Normalize to [-1, 1]
    pink = pink / np.abs(pink).max()

    return pink.astype(np.float32)


def generate_brown_noise(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate brown noise audio (1/f^2 noise, deeper rumble).

    Args:
        duration_seconds: Duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Audio samples as float32 array in range [-1, 1].
    """
    num_samples = int(duration_seconds * sample_rate)

    # Generate white noise
    white = np.random.randn(num_samples)

    # Apply 1/f^2 filter via FFT
    fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(num_samples, 1.0 / sample_rate)

    # Avoid division by zero
    freqs[0] = 1.0

    # Apply 1/f scaling for brown noise
    fft = fft / freqs

    # Convert back to time domain
    brown = np.fft.irfft(fft, num_samples)

    # Normalize to [-1, 1]
    brown = brown / np.abs(brown).max()

    return brown.astype(np.float32)


def generate_silence(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate silence with very low amplitude noise.

    Args:
        duration_seconds: Duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Audio samples as float32 array.
    """
    num_samples = int(duration_seconds * sample_rate)
    # Very low amplitude noise to simulate recording silence
    silence = np.random.uniform(-0.001, 0.001, num_samples).astype(np.float32)
    return silence


def extract_random_segments(input_file: str,
                            output_dir: str,
                            segment_duration: float = 2.0,
                            num_segments: int = 20,
                            sample_rate: int = 16000) -> List[str]:
    """Extract random segments from audio file.

    Args:
        input_file: Path to input audio file.
        output_dir: Directory to save segments.
        segment_duration: Duration of each segment in seconds.
        num_segments: Number of segments to extract.
        sample_rate: Target sample rate.

    Returns:
        List of output file paths.
    """
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load audio file
    if input_path.suffix.lower() == '.wav':
        sr, audio = wavfile.read(input_file)

        # Convert to mono
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Convert to float32 [-1, 1]
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        else:
            audio = audio.astype(np.float32)

    else:
        if not PYDUB_AVAILABLE:
            raise ImportError("pydub required for non-WAV formats")

        audio_segment = AudioSegment.from_file(input_file)

        # Convert to mono
        if audio_segment.channels > 1:
            audio_segment = audio_segment.set_channels(1)

        sr = audio_segment.frame_rate

        # Convert to numpy array
        audio = np.array(audio_segment.get_array_of_samples()).astype(np.float32)

        # Normalize based on sample width
        if audio_segment.sample_width == 2:  # 16-bit
            audio = audio / 32768.0
        elif audio_segment.sample_width == 4:  # 32-bit
            audio = audio / 2147483648.0

    # Resample if needed
    if sr != sample_rate:
        from scipy import signal
        num_samples = int(len(audio) * sample_rate / sr)
        audio = signal.resample(audio, num_samples)

    # Calculate segment size in samples
    segment_samples = int(segment_duration * sample_rate)

    # Check if audio is long enough
    if len(audio) < segment_samples:
        print(f"Warning: Audio file too short ({len(audio)/sample_rate:.1f}s), "
              f"need at least {segment_duration}s")
        return []

    # Extract random segments
    output_files = []
    max_start = len(audio) - segment_samples

    for i in range(num_segments):
        start_idx = np.random.randint(0, max_start)
        segment = audio[start_idx:start_idx + segment_samples]

        # Save segment
        output_file = output_path / f"{input_path.stem}_segment_{i:03d}.wav"

        # Convert to int16 for saving
        segment_int16 = (segment * 32767).astype(np.int16)
        wavfile.write(output_file, sample_rate, segment_int16)

        output_files.append(str(output_file))

    return output_files


def generate_synthetic_backgrounds(output_dir: str,
                                   num_samples: int = 20,
                                   duration: float = 2.0,
                                   sample_rate: int = 16000) -> List[str]:
    """Generate synthetic background noise samples.

    Args:
        output_dir: Directory to save samples.
        num_samples: Number of samples to generate per noise type.
        duration: Duration of each sample in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        List of output file paths.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_files = []

    # Generate different types of noise
    noise_generators = {
        'white': generate_white_noise,
        'pink': generate_pink_noise,
        'brown': generate_brown_noise,
        'silence': generate_silence
    }

    for noise_type, generator in noise_generators.items():
        for i in range(num_samples):
            # Generate noise
            noise = generator(duration, sample_rate)

            # Add random amplitude variation (50%-100%)
            amplitude = np.random.uniform(0.5, 1.0)
            noise = noise * amplitude

            # Save
            output_file = output_path / f"{noise_type}_noise_{i:03d}.wav"
            noise_int16 = (noise * 32767).astype(np.int16)
            wavfile.write(output_file, sample_rate, noise_int16)

            output_files.append(str(output_file))

    return output_files


def main():
    """CLI for background sample generation."""
    parser = argparse.ArgumentParser(
        description='Generate background/negative samples for audio classification training',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 20 synthetic noise samples
  python generate_background.py synthetic training/background/

  # Extract 30 random 2-second segments from a podcast
  python generate_background.py extract podcast.mp3 training/background/ --num-segments 30

  # Generate both synthetic noise (10 samples each) and extract from audio
  python generate_background.py synthetic training/background/ --num-samples 10
  python generate_background.py extract music.mp3 training/background/ --num-segments 20

Note: After generating background samples, retrain your model:
  python train.py training/ models/
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Synthetic noise generation
    synthetic_parser = subparsers.add_parser('synthetic', help='Generate synthetic noise samples')
    synthetic_parser.add_argument(
        'output_dir',
        type=str,
        help='Output directory for background samples (e.g., training/background/)'
    )
    synthetic_parser.add_argument(
        '--num-samples',
        type=int,
        default=20,
        help='Number of samples per noise type (default: 20)'
    )
    synthetic_parser.add_argument(
        '--duration',
        type=float,
        default=2.0,
        help='Duration of each sample in seconds (default: 2.0)'
    )

    # Audio segment extraction
    extract_parser = subparsers.add_parser('extract', help='Extract random segments from audio file')
    extract_parser.add_argument(
        'input_file',
        type=str,
        help='Input audio file (WAV, MP3, M4A, etc.)'
    )
    extract_parser.add_argument(
        'output_dir',
        type=str,
        help='Output directory for segments (e.g., training/background/)'
    )
    extract_parser.add_argument(
        '--num-segments',
        type=int,
        default=20,
        help='Number of segments to extract (default: 20)'
    )
    extract_parser.add_argument(
        '--duration',
        type=float,
        default=2.0,
        help='Duration of each segment in seconds (default: 2.0)'
    )

    args = parser.parse_args()

    if args.command == 'synthetic':
        print(f"Generating synthetic background samples...")
        print(f"Output directory: {args.output_dir}")
        print(f"Samples per type: {args.num_samples}")
        print(f"Duration: {args.duration}s")
        print()

        output_files = generate_synthetic_backgrounds(
            output_dir=args.output_dir,
            num_samples=args.num_samples,
            duration=args.duration
        )

        print(f"\nGenerated {len(output_files)} samples:")
        print(f"  - {args.num_samples} white noise")
        print(f"  - {args.num_samples} pink noise")
        print(f"  - {args.num_samples} brown noise")
        print(f"  - {args.num_samples} silence")
        print(f"\nTotal: {len(output_files)} files in {args.output_dir}")

    elif args.command == 'extract':
        if not Path(args.input_file).exists():
            print(f"Error: Input file not found: {args.input_file}")
            sys.exit(1)

        print(f"Extracting segments from: {args.input_file}")
        print(f"Output directory: {args.output_dir}")
        print(f"Number of segments: {args.num_segments}")
        print(f"Segment duration: {args.duration}s")
        print()

        output_files = extract_random_segments(
            input_file=args.input_file,
            output_dir=args.output_dir,
            segment_duration=args.duration,
            num_segments=args.num_segments
        )

        if output_files:
            print(f"\nExtracted {len(output_files)} segments to {args.output_dir}")
        else:
            print("\nNo segments extracted (audio file too short?)")
            sys.exit(1)

    print("\nNext steps:")
    print("  1. Review generated samples in output directory")
    print("  2. Optionally add more background samples from other sources")
    print("  3. Retrain model: python train.py training/ models/")


if __name__ == "__main__":
    main()
