"""Real-time audio classification listener CLI."""

import argparse
import sys
from pathlib import Path

import tensorflow as tf

from audio_device import list_audio_devices, print_devices, select_device
from stream_classifier import start_listening
from yamnet_classifier import load_yamnet_model


def load_custom_model(model_path: str, class_names_path: str):
    """Load custom trained model and class names.

    Args:
        model_path: Path to classifier model (.keras file).
        class_names_path: Path to class names file.

    Returns:
        Tuple of (classifier, class_names).
    """
    if not Path(model_path).exists():
        print(f"Error: Model not found at {model_path}")
        print("Train a model first using: python train.py")
        sys.exit(1)

    if not Path(class_names_path).exists():
        print(f"Error: Class names file not found at {class_names_path}")
        sys.exit(1)

    print(f"Loading model from {model_path}...")
    classifier = tf.keras.models.load_model(model_path)

    with open(class_names_path, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]

    print(f"Loaded {len(class_names)} classes: {class_names}")

    return classifier, class_names


def main():
    """Main entry point for audio listener."""
    parser = argparse.ArgumentParser(
        description='Real-time audio classification using YAMNet transfer learning',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available audio devices
  python listen.py --list

  # Auto-select loopback device and start listening
  python listen.py

  # Select specific device by name
  python listen.py --device "BlackHole"

  # Select device by ID with custom threshold
  python listen.py --device-id 1 --threshold 0.8

  # Use custom model
  python listen.py --model models/classifier.keras --classes models/class_names.txt
        """
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available audio devices and exit'
    )

    parser.add_argument(
        '--device',
        type=str,
        help='Audio device name (substring match)'
    )

    parser.add_argument(
        '--device-id',
        type=int,
        help='Audio device ID from --list'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='models/classifier.keras',
        help='Path to trained classifier model (default: models/classifier.keras)'
    )

    parser.add_argument(
        '--classes',
        type=str,
        default='models/class_names.txt',
        help='Path to class names file (default: models/class_names.txt)'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.7,
        help='Confidence threshold for event detection (default: 0.7)'
    )

    parser.add_argument(
        '--chunk-duration',
        type=float,
        default=0.5,
        help='Audio chunk duration in seconds (default: 0.5)'
    )

    args = parser.parse_args()

    # List devices and exit
    if args.list:
        devices = list_audio_devices(include_loopback=True)
        print_devices(devices)
        sys.exit(0)

    # Load models
    print("Loading YAMNet model...")
    yamnet_model = load_yamnet_model()

    print("Loading custom classifier...")
    classifier, class_names = load_custom_model(args.model, args.classes)

    # Select audio device
    print("\nSelecting audio device...")
    device = select_device(
        device_id=args.device_id,
        device_name=args.device,
        auto_select_loopback=True
    )

    if device is None:
        print("\nNo suitable audio device found.")
        print("Use --list to see available devices.")
        print("Use --device or --device-id to select a specific device.")
        sys.exit(1)

    # Start listening
    start_listening(
        device=device,
        yamnet_model=yamnet_model,
        classifier=classifier,
        class_names=class_names,
        chunk_duration=args.chunk_duration,
        confidence_threshold=args.threshold
    )


if __name__ == "__main__":
    main()
