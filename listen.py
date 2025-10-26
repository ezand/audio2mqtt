"""Real-time audio classification listener CLI."""

import argparse
import sys
from pathlib import Path

import tensorflow as tf

from audio_device import list_audio_devices, print_devices, select_device
from stream_classifier import start_listening as start_listening_ml
from yamnet_classifier import load_yamnet_model
from fingerprinting.engine import FingerprintEngine
from fingerprinting.storage_config import DatabaseType
from fingerprinting.recognizer import start_listening as start_listening_fingerprint


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
        description='Real-time audio recognition using ML or fingerprinting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available audio devices
  python listen.py --list

  # Use ML method (default)
  python listen.py

  # Use fingerprinting method
  python listen.py --method fingerprint

  # Fingerprinting with PostgreSQL database
  python listen.py --method fingerprint --db-type postgresql

  # Fingerprinting with custom config
  python listen.py --method fingerprint --config config.yaml

  # Listen to microphone instead of system audio
  python listen.py --microphone

  # Select specific device with fingerprinting
  python listen.py --method fingerprint --device "BlackHole" --verbose

Note: For fingerprinting, register audio first:
  python register_fingerprints.py training/ --by-class
        """
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available audio devices and exit'
    )

    parser.add_argument(
        '--method',
        type=str,
        choices=['ml', 'fingerprint'],
        default='ml',
        help='Recognition method: ml (YAMNet transfer learning) or fingerprint (Dejavu) (default: ml)'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (for fingerprinting database configuration)'
    )

    parser.add_argument(
        '--db-type',
        type=str,
        choices=['memory', 'postgresql', 'mysql'],
        default='memory',
        help='Database type for fingerprinting (default: memory). Ignored if --config is provided.'
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

    parser.add_argument(
        '--window-duration',
        type=float,
        default=2.0,
        help='Sliding window duration in seconds for classification (default: 2.0). '
             'Should match your training audio length for best results.'
    )

    parser.add_argument(
        '--energy-threshold',
        type=float,
        default=-40.0,
        help='Minimum audio energy in dB to process (default: -40.0, lower=more sensitive)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (shows audio detection and non-matches)'
    )

    parser.add_argument(
        '--microphone',
        action='store_true',
        help='Listen to microphone instead of loopback device'
    )

    args = parser.parse_args()

    # List devices and exit
    if args.list:
        devices = list_audio_devices(include_loopback=True)
        print_devices(devices)
        sys.exit(0)

    # Select audio device
    print("Selecting audio device...")
    device = select_device(
        device_id=args.device_id,
        device_name=args.device,
        auto_select_loopback=not args.microphone,
        prefer_microphone=args.microphone
    )

    if device is None:
        print("\nNo suitable audio device found.")
        print("Use --list to see available devices.")
        print("Use --device or --device-id to select a specific device.")
        if args.microphone:
            print("Or remove --microphone flag to use loopback device.")
        sys.exit(1)

    # Method-specific initialization and listening
    if args.method == 'ml':
        # ML method: Load YAMNet and classifier
        print("\nMethod: ML (YAMNet transfer learning)")
        print("Loading YAMNet model...")
        yamnet_model = load_yamnet_model()

        print("Loading custom classifier...")
        classifier, class_names = load_custom_model(args.model, args.classes)

        # Start listening with ML
        start_listening_ml(
            device=device,
            yamnet_model=yamnet_model,
            classifier=classifier,
            class_names=class_names,
            chunk_duration=args.chunk_duration,
            window_duration=args.window_duration,
            confidence_threshold=args.threshold,
            energy_threshold_db=args.energy_threshold,
            verbose=args.verbose
        )

    elif args.method == 'fingerprint':
        # Fingerprinting method: Initialize engine
        print("\nMethod: Fingerprinting (Dejavu)")

        # Parse database type
        if args.db_type == 'memory':
            db_type = DatabaseType.MEMORY
        elif args.db_type == 'postgresql':
            db_type = DatabaseType.POSTGRESQL
        elif args.db_type == 'mysql':
            db_type = DatabaseType.MYSQL
        else:
            db_type = DatabaseType.MEMORY

        # Initialize engine
        try:
            if args.config:
                print(f"Loading config from: {args.config}")
                if not Path(args.config).exists():
                    print(f"Error: Config file not found: {args.config}")
                    sys.exit(1)
                engine = FingerprintEngine(config_path=args.config)
            else:
                print(f"Using database type: {args.db_type}")
                engine = FingerprintEngine(db_type=db_type)
        except Exception as e:
            print(f"Error initializing fingerprint engine: {e}")
            print("\nIf using PostgreSQL/MySQL, make sure the database is running.")
            print("You can start PostgreSQL with: docker-compose up -d")
            sys.exit(1)

        # Check if any fingerprints are registered
        song_count = engine.get_song_count()
        if song_count == 0:
            print("\nWarning: No fingerprints registered in database!")
            print("Register audio first: python register_fingerprints.py training/ --by-class")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                sys.exit(0)
        else:
            print(f"Found {song_count} registered fingerprints in database")

        # Start listening with fingerprinting
        start_listening_fingerprint(
            device=device,
            engine=engine,
            chunk_duration=args.chunk_duration,
            window_duration=args.window_duration,
            confidence_threshold=args.threshold,
            energy_threshold_db=args.energy_threshold,
            verbose=args.verbose
        )


if __name__ == "__main__":
    main()
