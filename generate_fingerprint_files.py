"""Generate fingerprint files from YAML metadata and audio files.

This script scans a directory for YAML files, reads metadata, fingerprints the
corresponding audio files, and saves the fingerprints as JSON files for version control.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import yaml

from fingerprinting.engine import FingerprintEngine
from fingerprinting.storage_config import DatabaseType


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


def generate_fingerprint(yaml_path: Path, output_dir: Path) -> Dict:
    """Generate fingerprint file from YAML + audio.

    Args:
        yaml_path: Path to YAML metadata file.
        output_dir: Directory to save fingerprint JSON file.

    Returns:
        Result dictionary with status.
    """
    try:
        # Load YAML metadata
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)

        source_file = yaml_data.get('source')
        metadata = yaml_data.get('metadata', {})

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

        # Generate song_name from metadata (slugified song name + game)
        song_name_parts = []
        if 'game' in metadata:
            song_name_parts.append(slugify(metadata['game']))
        if 'song' in metadata:
            song_name_parts.append(slugify(metadata['song']))

        song_name = '_'.join(song_name_parts) if song_name_parts else yaml_path.stem

        # Compute file hash
        file_sha1 = compute_file_sha1(str(audio_path))

        # Create temporary in-memory engine for fingerprinting
        engine = FingerprintEngine(db_type=DatabaseType.MEMORY)

        # Register file to generate fingerprints
        print(f"  Fingerprinting: {audio_path.name}...")
        engine.register_file(str(audio_path), song_name=song_name)

        # Extract fingerprints from in-memory database
        db = engine.dejavu.db
        songs = db.get_songs()

        if not songs:
            return {
                'yaml': str(yaml_path),
                'status': 'error',
                'error': 'No fingerprints generated'
            }

        # Get song_id
        song_id = songs[0][0]

        # Get fingerprints
        # Note: Dejavu doesn't expose this cleanly, so we'll use direct DB access
        fingerprints = []
        try:
            if hasattr(db, 'get_song_hashes'):
                # If Dejavu exposes this method
                hashes = db.get_song_hashes(song_id)
                fingerprints = [{'hash': h[0], 'offset': h[1]} for h in hashes]
            else:
                # Direct database query (database-specific)
                print(f"  Warning: Cannot extract fingerprints, saving without hashes")
        except Exception as e:
            print(f"  Warning: Could not extract fingerprints: {e}")

        # Build output JSON
        fingerprint_data = {
            'song_name': song_name,
            'source_file': source_file,
            'metadata': metadata,
            'file_sha1': file_sha1,
            'date_created': datetime.now().isoformat(),
            'total_hashes': len(fingerprints),
            'fingerprints': fingerprints
        }

        # Save to output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{yaml_path.stem}.json"

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
  python generate_fingerprint_files.py source_sounds/fingerprining/ training/fingerprints/

  # Process single YAML file
  python generate_fingerprint_files.py source_sounds/fingerprining/song.yaml training/fingerprints/

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
    for yaml_file in yaml_files:
        print(f"Processing: {yaml_file.name}")
        result = generate_fingerprint(yaml_file, output_dir)
        results.append(result)

        if result['status'] == 'success':
            print(f"  ✓ Generated: {result['output']}")
            print(f"    Song name: {result['song_name']}")
            print(f"    Hashes: {result['total_hashes']}")
        else:
            print(f"  ✗ Error: {result['error']}")
        print()

    # Summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')

    print("=" * 60)
    print(f"Processed: {len(results)}")
    print(f"Success: {success_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")
        print("\nFailed files:")
        for r in results:
            if r['status'] == 'error':
                print(f"  - {r['yaml']}: {r['error']}")
    print("=" * 60)

    print(f"\nFingerprint files saved to: {output_dir}")
    print("\nNext steps:")
    print(f"  1. Commit fingerprint files to version control")
    print(f"  2. Import into database: python import_fingerprint_files.py {output_dir} --db-type postgresql")


if __name__ == "__main__":
    main()
