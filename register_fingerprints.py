"""CLI tool to register audio fingerprints for recognition."""

import argparse
import sys
from pathlib import Path

from fingerprinting.engine import FingerprintEngine
from fingerprinting.storage_config import DatabaseType


def main():
    """Main entry point for fingerprint registration."""
    parser = argparse.ArgumentParser(
        description='Register audio fingerprints for recognition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Register all files in a directory (flat structure)
  python register_fingerprints.py audio_samples/

  # Register files organized by class (training/class_name/*.wav)
  python register_fingerprints.py training/ --by-class

  # Use specific config file
  python register_fingerprints.py training/ --config config.yaml

  # Use PostgreSQL database directly
  python register_fingerprints.py training/ --db-type postgresql

  # List registered fingerprints
  python register_fingerprints.py --list

  # Clear all fingerprints
  python register_fingerprints.py --clear

Note: Make sure database is running before registering (if using PostgreSQL/MySQL).
      For in-memory database, fingerprints are lost on restart.
        """
    )

    parser.add_argument(
        'directory',
        type=str,
        nargs='?',
        help='Directory containing audio files to register'
    )

    parser.add_argument(
        '--by-class',
        action='store_true',
        help='Register files organized by class folders (training/class_name/*.wav)'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (config.yaml)'
    )

    parser.add_argument(
        '--db-type',
        type=str,
        choices=['memory', 'postgresql', 'mysql'],
        default='memory',
        help='Database type (default: memory). Ignored if --config is provided.'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all registered fingerprints'
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear all fingerprints from database'
    )

    parser.add_argument(
        '--extensions',
        type=str,
        default='.wav,.mp3,.m4a,.ogg,.flac',
        help='Comma-separated list of file extensions (default: .wav,.mp3,.m4a,.ogg,.flac)'
    )

    args = parser.parse_args()

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

    # List registered fingerprints
    if args.list:
        songs = engine.get_songs()
        if not songs:
            print("No fingerprints registered.")
        else:
            print(f"\nRegistered fingerprints ({len(songs)} total):")
            print("-" * 60)
            for song in songs:
                print(f"  [{song['id']}] {song['name']}")
            print("-" * 60)
        sys.exit(0)

    # Clear all fingerprints
    if args.clear:
        response = input("Are you sure you want to clear ALL fingerprints? (yes/no): ")
        if response.lower() == 'yes':
            print("Clearing all fingerprints...")
            engine.clear_database()
            print("All fingerprints cleared.")
        else:
            print("Cancelled.")
        sys.exit(0)

    # Validate directory argument
    if not args.directory:
        print("Error: directory argument required (unless using --list or --clear)")
        parser.print_help()
        sys.exit(1)

    if not Path(args.directory).exists():
        print(f"Error: Directory not found: {args.directory}")
        sys.exit(1)

    if not Path(args.directory).is_dir():
        print(f"Error: Not a directory: {args.directory}")
        sys.exit(1)

    # Parse extensions
    extensions = [ext.strip() if ext.startswith('.') else f'.{ext.strip()}'
                  for ext in args.extensions.split(',')]

    print(f"\nRegistering audio files from: {args.directory}")
    print(f"Extensions: {', '.join(extensions)}")
    print()

    # Register files
    try:
        if args.by_class:
            print("Mode: By-class registration (training/class_name/*.wav)")
            results_by_class = engine.register_directory_by_class(
                args.directory,
                extensions=extensions
            )

            # Print results
            total_success = 0
            total_errors = 0

            for class_name, results in results_by_class.items():
                success_count = sum(1 for r in results if r['status'] == 'registered')
                error_count = sum(1 for r in results if r['status'] == 'error')

                print(f"\nClass: {class_name}")
                print(f"  Registered: {success_count}")
                if error_count > 0:
                    print(f"  Errors: {error_count}")
                    for result in results:
                        if result['status'] == 'error':
                            print(f"    - {result['file']}: {result['error']}")

                total_success += success_count
                total_errors += error_count

            print(f"\n{'='*60}")
            print(f"Total registered: {total_success}")
            if total_errors > 0:
                print(f"Total errors: {total_errors}")
            print(f"{'='*60}")

        else:
            print("Mode: Flat directory registration")
            results = engine.register_directory(
                args.directory,
                extensions=extensions,
                recursive=True
            )

            # Print results
            success_count = sum(1 for r in results if r['status'] == 'registered')
            error_count = sum(1 for r in results if r['status'] == 'error')

            print(f"\nRegistered: {success_count}")
            if error_count > 0:
                print(f"Errors: {error_count}")
                for result in results:
                    if result['status'] == 'error':
                        print(f"  - {result['file']}: {result['error']}")

        # Show total count
        total_songs = engine.get_song_count()
        print(f"\nTotal fingerprints in database: {total_songs}")

    except Exception as e:
        print(f"\nError during registration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nNext steps:")
    print("  1. Start listening: python listen.py --method fingerprint")
    print("  2. List registered: python register_fingerprints.py --list")


if __name__ == "__main__":
    main()
