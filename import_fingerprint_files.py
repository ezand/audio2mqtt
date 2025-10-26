"""Import fingerprint files into database.

This script loads fingerprint JSON files and imports them into the
Dejavu fingerprint database along with metadata.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from fingerprinting.engine import FingerprintEngine
from fingerprinting.storage_config import DatabaseType


def import_fingerprint_file(json_path: Path, engine: FingerprintEngine) -> Dict:
    """Import single fingerprint file into database.

    Args:
        json_path: Path to fingerprint JSON file.
        engine: FingerprintEngine instance.

    Returns:
        Result dictionary with status.
    """
    try:
        # Load fingerprint data
        with open(json_path, 'r') as f:
            data = json.load(f)

        song_name = data.get('song_name')
        source_file = data.get('source_file')
        metadata = data.get('metadata', {})
        file_sha1 = data.get('file_sha1')
        fingerprints = data.get('fingerprints', [])

        if not song_name:
            return {
                'file': str(json_path),
                'status': 'error',
                'error': 'Missing song_name in JSON'
            }

        # Check if song already exists
        existing_songs = engine.get_songs()
        if any(s['name'] == song_name for s in existing_songs):
            return {
                'file': str(json_path),
                'song_name': song_name,
                'status': 'skipped',
                'reason': 'Already exists in database'
            }

        # Import into Dejavu database
        # Note: Dejavu doesn't support direct fingerprint import easily
        # For now, we'll need to re-fingerprint from source audio file
        # or implement custom database insertion

        # Find source audio file
        audio_file = None
        if source_file:
            # Check multiple possible locations
            possible_paths = [
                Path(source_file),
                json_path.parent.parent / 'fingerprining' / source_file,
                json_path.parent.parent / source_file,
                json_path.parent / source_file
            ]

            for path in possible_paths:
                if path.exists():
                    audio_file = path
                    break

        if not audio_file:
            return {
                'file': str(json_path),
                'song_name': song_name,
                'status': 'error',
                'error': f'Source audio file not found: {source_file}'
            }

        # Register audio file with metadata
        print(f"  Fingerprinting: {audio_file.name}...")
        result = engine.register_file(
            str(audio_file),
            song_name=song_name,
            metadata=metadata
        )

        return {
            'file': str(json_path),
            'song_name': song_name,
            'audio_file': str(audio_file),
            'metadata_fields': list(metadata.keys()),
            'status': 'success'
        }

    except Exception as e:
        return {
            'file': str(json_path),
            'status': 'error',
            'error': str(e)
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Import fingerprint files into database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import all fingerprints from directory (in-memory)
  python import_fingerprint_files.py training/fingerprints/

  # Import into PostgreSQL
  python import_fingerprint_files.py training/fingerprints/ --db-type postgresql

  # Import with config file
  python import_fingerprint_files.py training/fingerprints/ --config config.yaml

  # Import single file
  python import_fingerprint_files.py training/fingerprints/song.json

Notes:
  - Skips songs that already exist in database
  - Requires source audio files to be accessible
  - Stores metadata in separate song_metadata table
        """
    )

    parser.add_argument(
        'input_path',
        type=str,
        help='Directory containing fingerprint JSON files or single JSON file'
    )

    parser.add_argument(
        '--db-type',
        type=str,
        choices=['memory', 'postgresql', 'mysql'],
        default='memory',
        help='Database type (default: memory)'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (overrides --db-type)'
    )

    parser.add_argument(
        '--pattern',
        type=str,
        default='*.json',
        help='Glob pattern for JSON files (default: *.json)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-import even if song exists (not yet implemented)'
    )

    args = parser.parse_args()

    input_path = Path(args.input_path)

    if not input_path.exists():
        print(f"Error: Input path not found: {input_path}")
        sys.exit(1)

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

    # Collect JSON files
    json_files = []
    if input_path.is_file():
        if input_path.suffix == '.json':
            json_files = [input_path]
        else:
            print(f"Error: File is not a JSON file: {input_path}")
            sys.exit(1)
    else:
        json_files = sorted(input_path.glob(args.pattern))

    if not json_files:
        print(f"No JSON files found in: {input_path}")
        sys.exit(0)

    print(f"Found {len(json_files)} fingerprint file(s)")
    print()

    # Process each JSON file
    results = []
    for json_file in json_files:
        print(f"Processing: {json_file.name}")
        result = import_fingerprint_file(json_file, engine)
        results.append(result)

        if result['status'] == 'success':
            print(f"  ✓ Imported: {result['song_name']}")
            print(f"    Metadata fields: {', '.join(result['metadata_fields'])}")
        elif result['status'] == 'skipped':
            print(f"  → Skipped: {result['song_name']} ({result['reason']})")
        else:
            print(f"  ✗ Error: {result['error']}")
        print()

    # Summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    error_count = sum(1 for r in results if r['status'] == 'error')

    print("=" * 60)
    print(f"Processed: {len(results)}")
    print(f"Imported: {success_count}")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")
        print("\nFailed files:")
        for r in results:
            if r['status'] == 'error':
                print(f"  - {Path(r['file']).name}: {r['error']}")
    print("=" * 60)

    # Show database stats
    total_songs = engine.get_song_count()
    total_metadata = engine.metadata_db.count_metadata()

    print(f"\nDatabase stats:")
    print(f"  Total songs: {total_songs}")
    print(f"  Total metadata entries: {total_metadata}")

    print("\nNext steps:")
    print("  1. Start listening: python listen.py --method fingerprint")
    print("  2. List songs: python register_fingerprints.py --list")
    print("  3. Query by metadata: Use engine.query_songs_by_metadata('game', 'Super Mario World')")


if __name__ == "__main__":
    main()
