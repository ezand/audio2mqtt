"""Generate fingerprint files from YAML metadata and audio files.

This script scans a directory for YAML files, reads metadata, fingerprints the
corresponding audio files, and saves the fingerprints as JSON files for version control.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import yaml

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


def compute_file_sha1(file_path: str) -> str:
    """Compute SHA1 hash of file.

    Args:
        file_path: Path to file.

    Returns:
        Hex-encoded SHA1 hash.
    """
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(65536)  # 64KB chunks
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def slugify(text: str) -> str:
    """Convert text to slug format.

    Args:
        text: Text to slugify.

    Returns:
        Slugified text (lowercase, underscores, alphanumeric).
    """
    # Simple slugification: lowercase, replace spaces with underscores
    slug = text.lower()
    slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in slug)
    slug = '_'.join(slug.split())
    return slug


def find_audio_file(yaml_path: Path, source_filename: str) -> Path:
    """Find audio file corresponding to YAML metadata.

    Args:
        yaml_path: Path to YAML file.
        source_filename: Source filename from YAML.

    Returns:
        Path to audio file.

    Raises:
        FileNotFoundError: If audio file not found.
    """
    # Check in same directory as YAML
    audio_path = yaml_path.parent / source_filename
    if audio_path.exists():
        return audio_path

    # Check common extensions if not found
    base_name = Path(source_filename).stem
    extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    for ext in extensions:
        audio_path = yaml_path.parent / f"{base_name}{ext}"
        if audio_path.exists():
            return audio_path

    raise FileNotFoundError(f"Audio file not found for {yaml_path.name}: {source_filename}")


def generate_fingerprint(yaml_path: Path, output_dir: Path, force: bool = False) -> Dict:
    """Generate fingerprint file from YAML + audio.

    Args:
        yaml_path: Path to YAML metadata file.
        output_dir: Directory to save fingerprint JSON file.
        force: If True, regenerate even if fingerprint exists with matching hash.

    Returns:
        Result dictionary with status.
    """
    try:
        # Load YAML metadata
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)

        source_file = yaml_data.get('source')
        metadata = yaml_data.get('metadata', {})
        debounce_seconds = yaml_data.get('debounce_seconds', 5.0)  # Default to 5.0

        # Validate debounce_seconds
        try:
            debounce_seconds = float(debounce_seconds)
            if debounce_seconds < 0:
                debounce_seconds = 5.0
        except (ValueError, TypeError):
            debounce_seconds = 5.0

        if not source_file:
            return {
                'yaml': str(yaml_path),
                'status': 'error',
                'error': 'Missing "source" field in YAML'
            }

        if not metadata:
            return {
                'yaml': str(yaml_path),
                'status': 'error',
                'error': 'Missing "metadata" field in YAML'
            }

        # Find audio file
        audio_path = find_audio_file(yaml_path, source_file)

        # Compute file hash
        file_sha1 = compute_file_sha1(str(audio_path))

        # Check if fingerprint already exists with matching hash
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{yaml_path.stem}.json"

        if not force and output_path.exists():
            try:
                with open(output_path, 'r') as f:
                    existing_data = json.load(f)
                existing_hash = existing_data.get('file_sha1')

                if existing_hash == file_sha1:
                    return {
                        'yaml': str(yaml_path),
                        'audio': str(audio_path),
                        'output': str(output_path),
                        'song_name': existing_data.get('song_name', ''),
                        'total_hashes': existing_data.get('total_hashes', 0),
                        'status': 'skipped',
                        'reason': 'hash_match'
                    }
            except (json.JSONDecodeError, KeyError):
                # If existing file is corrupt, regenerate
                pass

        # Generate song_name from metadata (slugified song name + game)
        song_name_parts = []
        if 'game' in metadata:
            song_name_parts.append(slugify(metadata['game']))
        if 'song' in metadata:
            song_name_parts.append(slugify(metadata['song']))

        song_name = '_'.join(song_name_parts) if song_name_parts else yaml_path.stem

        # Create temporary in-memory engine for fingerprinting
        engine = FingerprintEngine(db_type=DatabaseType.MEMORY)

        # Register file to generate fingerprints
        print(f"  Fingerprinting: {audio_path.name}...")
        engine.register_file(str(audio_path), song_name=song_name)

        # Extract fingerprints from in-memory database
        db = engine.dejavu.db
        songs = list(db.get_songs())  # Convert generator to list

        if not songs:
            return {
                'yaml': str(yaml_path),
                'status': 'error',
                'error': 'No fingerprints generated'
            }

        # Get song_id from dict
        song_id = songs[0].get('song_id') or songs[0].get(db.FIELD_SONG_ID)

        # Get fingerprints
        # Note: Dejavu doesn't expose this cleanly, so we'll use direct DB access
        fingerprints = []
        try:
            if hasattr(db, 'get_song_hashes'):
                # If Dejavu exposes this method
                hashes = db.get_song_hashes(song_id)
                fingerprints = [{'hash': str(h[0]), 'offset': int(h[1])} for h in hashes]
            else:
                # Direct database query (database-specific)
                print(f"  Warning: Cannot extract fingerprints, saving without hashes")
        except Exception as e:
            print(f"  Warning: Could not extract fingerprints: {e}")

        # Build output JSON (always include debounce_seconds)
        fingerprint_data = {
            'song_name': song_name,
            'source_file': source_file,
            'metadata': metadata,
            'debounce_seconds': debounce_seconds,
            'file_sha1': file_sha1,
            'date_created': datetime.now().isoformat(),
            'total_hashes': len(fingerprints),
            'fingerprints': fingerprints
        }

        # Save to output directory (path already created earlier)
        with open(output_path, 'w') as f:
            json.dump(fingerprint_data, f, indent=2)

        return {
            'yaml': str(yaml_path),
            'audio': str(audio_path),
            'output': str(output_path),
            'song_name': song_name,
            'total_hashes': len(fingerprints),
            'status': 'success'
        }

    except Exception as e:
        return {
            'yaml': str(yaml_path),
            'status': 'error',
            'error': str(e)
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate fingerprint files from YAML metadata + audio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate fingerprints from all YAMLs in directory
  python generate_fingerprint_files.py source_sounds/ training/fingerprints/

  # Process single YAML file
  python generate_fingerprint_files.py source_sounds/song.yaml training/fingerprints/

YAML Format:
  source: audio_file.mp3
  metadata:
    game: Super Mario World
    song: Underground
    # ... any other metadata fields

Output:
  Saves JSON files to output directory with fingerprints + metadata.
        """
    )

    parser.add_argument(
        'input_path',
        type=str,
        help='Directory containing YAML files or single YAML file path'
    )

    parser.add_argument(
        'output_dir',
        type=str,
        help='Directory to save fingerprint JSON files'
    )

    parser.add_argument(
        '--pattern',
        type=str,
        default='*.yaml',
        help='Glob pattern for YAML files (default: *.yaml)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if fingerprint exists with matching hash'
    )

    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"Error: Input path not found: {input_path}")
        sys.exit(1)

    # Collect YAML files
    yaml_files = []
    if input_path.is_file():
        if input_path.suffix in ['.yaml', '.yml']:
            yaml_files = [input_path]
        else:
            print(f"Error: File is not a YAML file: {input_path}")
            sys.exit(1)
    else:
        yaml_files = sorted(input_path.glob(args.pattern))

    if not yaml_files:
        print(f"No YAML files found in: {input_path}")
        sys.exit(0)

    print(f"Found {len(yaml_files)} YAML file(s)")
    print(f"Output directory: {output_dir}")
    print()

    # Process each YAML file
    results = []
    total_files = len(yaml_files)

    for idx, yaml_file in enumerate(yaml_files, start=1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total_files}] Processing: {yaml_file.name}")
        print_progress_bar(0, 100, prefix='Progress', suffix='Starting...')

        start_time = time.time()
        result = generate_fingerprint(yaml_file, output_dir, force=args.force)
        elapsed = time.time() - start_time
        results.append(result)

        print_progress_bar(100, 100, prefix='Progress', suffix='Complete!')

        if result['status'] == 'success':
            print(f"  ✓ Generated: {result['output']}")
            print(f"    Song name: {result['song_name']}")
            print(f"    Hashes: {result['total_hashes']:,}")
            print(f"    Time: {elapsed:.2f}s")
        elif result['status'] == 'skipped':
            print(f"  ⊘ Skipped: {result['output']}")
            print(f"    Reason: Audio file unchanged (matching SHA1)")
            print(f"    Song name: {result['song_name']}")
            print(f"    Hashes: {result['total_hashes']:,}")
            print(f"    Time: {elapsed:.2f}s")
        else:
            print(f"  ✗ Error: {result['error']}")
            print(f"    Time: {elapsed:.2f}s")

    # Summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    error_count = sum(1 for r in results if r['status'] == 'error')
    total_hashes = sum(r.get('total_hashes', 0) for r in results if r['status'] in ['success', 'skipped'])

    print("\n" + "=" * 60)
    print("                       SUMMARY")
    print("=" * 60)
    print(f"  Total files:     {len(results)}")
    print(f"  ✓ Generated:     {success_count}")
    if skipped_count > 0:
        print(f"  ⊘ Skipped:       {skipped_count}")
    if error_count > 0:
        print(f"  ✗ Errors:        {error_count}")
    if success_count + skipped_count > 0:
        print(f"  📊 Total hashes: {total_hashes:,}")
        avg_hashes = total_hashes / (success_count + skipped_count)
        print(f"  📈 Avg hashes:   {avg_hashes:,.0f} per file")

    if error_count > 0:
        print("\n" + "-" * 60)
        print("Failed files:")
        for r in results:
            if r['status'] == 'error':
                yaml_name = Path(r['yaml']).name
                print(f"  ✗ {yaml_name}: {r['error']}")
    print("=" * 60)

    print(f"\n📁 Fingerprint files saved to: {output_dir}")
    print("\n📝 Next steps:")
    print(f"  1. Commit fingerprint files to version control")
    print(f"  2. Import into database:")
    print(f"     python import_fingerprint_files.py {output_dir} --db-type postgresql")


if __name__ == "__main__":
    main()
