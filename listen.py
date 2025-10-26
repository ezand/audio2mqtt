"""Real-time audio fingerprinting listener CLI."""

import argparse
import sys
from pathlib import Path

from audio_device import list_audio_devices, print_devices, select_device
from fingerprinting.engine import FingerprintEngine
from fingerprinting.storage_config import DatabaseType, load_recognition_config, load_full_config
from fingerprinting.recognizer import start_listening
from fingerprinting.mqtt_client import MQTTPublisher


def main():
    """Main entry point for audio listener."""
    parser = argparse.ArgumentParser(
        description='Real-time audio recognition using fingerprinting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available audio devices
  python listen.py --list

  # Use in-memory database (quick start)
  python listen.py

  # Use PostgreSQL database
  python listen.py --db-type postgresql

  # Use custom config file
  python listen.py --config config.yaml

  # Listen to microphone instead of system audio
  python listen.py --microphone

  # Select specific device
  python listen.py --device "BlackHole" --verbose

Note: Register audio first using:
  # Generate fingerprints from YAML metadata
  python generate_fingerprint_files.py source_sounds/ training/fingerprints/

  # Import into database
  python import_fingerprint_files.py training/fingerprints/ --db-type postgresql
        """
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available audio devices and exit'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (for database configuration and recognition settings)'
    )

    parser.add_argument(
        '--db-type',
        type=str,
        choices=['memory', 'postgresql', 'mysql'],
        default='memory',
        help='Database type (default: memory). Ignored if --config is provided.'
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
        '--threshold',
        type=float,
        default=0.5,
        help='Confidence threshold for event detection (default: 0.5). '
             'Confidence is calculated as min(matched_hashes / 50, 1.0).'
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
        help='Sliding window duration in seconds for fingerprinting (default: 2.0). '
             'Longer windows = higher accuracy but slower response.'
    )

    parser.add_argument(
        '--energy-threshold',
        type=float,
        default=-40.0,
        help='Minimum audio energy in dB to process (default: -40.0, lower=more sensitive)'
    )

    parser.add_argument(
        '--debounce',
        type=float,
        default=5.0,
        help='MQTT debounce duration in seconds (default: 5.0). '
             'Prevents MQTT spam when same song detected repeatedly. '
             'Publishing a different song resets the timer.'
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

    # Initialize fingerprint engine
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

    # Initialize engine and load config
    mqtt_publisher = None
    try:
        if args.config:
            print(f"Loading config from: {args.config}")
            if not Path(args.config).exists():
                print(f"Error: Config file not found: {args.config}")
                sys.exit(1)
            engine = FingerprintEngine(config_path=args.config)

            # Load full config (including MQTT)
            full_config = load_full_config(args.config)
            recognition_config = load_recognition_config(args.config)

            # Use config values if command-line args are defaults
            # (user didn't explicitly override them)
            parser_defaults = {
                'threshold': 0.5,
                'chunk_duration': 0.5,
                'window_duration': 2.0,
                'debounce': 5.0,
            }

            confidence_threshold = recognition_config['confidence_threshold'] if args.threshold == parser_defaults['threshold'] else args.threshold
            chunk_duration = recognition_config['chunk_seconds'] if args.chunk_duration == parser_defaults['chunk_duration'] else args.chunk_duration
            window_duration = args.window_duration  # No config equivalent yet

            # Get debounce duration from config or CLI
            mqtt_config = full_config.get('mqtt', {})
            debounce_duration = mqtt_config.get('debounce_seconds', parser_defaults['debounce']) if args.debounce == parser_defaults['debounce'] else args.debounce

            # Initialize MQTT publisher if configured
            mqtt_publisher = MQTTPublisher.from_config(full_config)
            if mqtt_publisher:
                print("MQTT publishing: enabled")
                if mqtt_publisher.connect():
                    print(f"Connected to MQTT broker: {mqtt_publisher.broker}:{mqtt_publisher.port}")
                else:
                    print("Warning: Failed to connect to MQTT broker, publishing disabled")
                    mqtt_publisher = None
        else:
            print(f"Using database type: {args.db_type}")
            engine = FingerprintEngine(db_type=db_type)
            confidence_threshold = args.threshold
            chunk_duration = args.chunk_duration
            window_duration = args.window_duration
            debounce_duration = args.debounce
            print("MQTT publishing: disabled (no config file)")
    except Exception as e:
        print(f"Error initializing fingerprint engine: {e}")
        print("\nIf using PostgreSQL/MySQL, make sure the database is running.")
        print("You can start PostgreSQL with: docker-compose up -d")
        sys.exit(1)

    # Check if any fingerprints are registered
    song_count = engine.get_song_count()
    if song_count == 0:
        print("\nWarning: No fingerprints registered in database!")
        print("Register audio first:")
        print("  1. Generate fingerprints: python generate_fingerprint_files.py source_sounds/ training/fingerprints/")
        print("  2. Import into database: python import_fingerprint_files.py training/fingerprints/ --db-type postgresql")
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            sys.exit(0)
    else:
        print(f"Found {song_count} registered fingerprints in database")

    # Start listening with fingerprinting
    try:
        start_listening(
            device=device,
            engine=engine,
            chunk_duration=chunk_duration,
            window_duration=window_duration,
            confidence_threshold=confidence_threshold,
            energy_threshold_db=args.energy_threshold,
            debounce_duration=debounce_duration,
            verbose=args.verbose,
            mqtt_publisher=mqtt_publisher
        )
    finally:
        # Disconnect MQTT on exit
        if mqtt_publisher:
            mqtt_publisher.disconnect()


if __name__ == "__main__":
    main()
