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


def print_progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '',
                       length: int = 40, fill: str = '█', end: str = '\r'):
    """Print a progress bar to terminal.

    Args:
        iteration: Current iteration (0 to total).
        total: Total iterations.
        prefix: Prefix string.
        suffix: Suffix string.
        length: Character length of bar.
        fill: Bar fill character.
        end: End character (e.g. '\r', '\n').
    """
    if total == 0:
        percent = 100.0
        filled_length = length
    else:
        percent = 100 * (iteration / float(total))
        filled_length = int(length * iteration // total)

    bar = fill * filled_length + '░' * (length - filled_length)
    print(f'\r  {prefix} |{bar}| {percent:.1f}% {suffix}', end=end)

    # Print newline on complete
    if iteration == total:
        print()


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
        file_sha1 = data.get('file_sha1', '0' * 40)  # Default if missing
        fingerprints = data.get('fingerprints', [])

        if not song_name:
            return {
                'file': str(json_path),
                'status': 'error',
                'error': 'Missing song_name in JSON'
            }

        if not fingerprints:
            return {
                'file': str(json_path),
                'song_name': song_name,
                'status': 'error',
                'error': 'No fingerprints in JSON'
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

        # Direct database insertion using Dejavu's database API
        db = engine.dejavu.db

        # Insert song into songs table
        print(f"  Inserting song: {song_name}...")
        song_id = db.insert_song(song_name, file_sha1)

        # Insert fingerprints in batches for performance
        print(f"  Inserting {len(fingerprints):,} fingerprints...")
        batch_size = 1000
        for i in range(0, len(fingerprints), batch_size):
            batch = fingerprints[i:i + batch_size]
            for fp in batch:
                hash_value = fp.get('hash')
                offset = fp.get('offset')
                if hash_value is not None and offset is not None:
                    db.insert(hash_value, song_id, offset)

            # Visual progress bar with count
            progress = min(i + batch_size, len(fingerprints))
            count_str = f'{progress:,}/{len(fingerprints):,}'
            print_progress_bar(progress, len(fingerprints), prefix=f'  Progress {count_str}', suffix='')

        # Final newline
        print()

        # Mark song as fingerprinted
        db.set_song_fingerprinted(song_id)

        # Store metadata if provided
        if metadata:
            engine.metadata_db.insert_metadata(
                song_name=song_name,
                metadata=metadata,
                source_file=source_file or ''
            )

        return {
            'file': str(json_path),
            'song_name': song_name,
            'fingerprint_count': len(fingerprints),
            'metadata_fields': list(metadata.keys()) if metadata else [],
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
  - Uses pre-computed fingerprints from JSON (no audio files required)
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

    # Parse database type enum
    db_type = DatabaseType(args.db_type)

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
    total_files = len(json_files)

    for idx, json_file in enumerate(json_files, start=1):
        # File progress header
        print(f"\n[{idx}/{total_files}] Processing: {json_file.name}")

        result = import_fingerprint_file(json_file, engine)
        results.append(result)

        if result['status'] == 'success':
            print(f"  ✓ Imported: {result['song_name']}")
            print(f"    Fingerprints: {result.get('fingerprint_count', 0):,}")
            if result.get('metadata_fields'):
                print(f"    Metadata fields: {', '.join(result['metadata_fields'])}")
        elif result['status'] == 'skipped':
            print(f"  → Skipped: {result['song_name']} ({result['reason']})")
        else:
            print(f"  ✗ Error: {result['error']}")

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
