#!/usr/bin/env python3
"""Apply patches to installed packages.

This script applies necessary patches to fix Python 2/3 compatibility issues
in installed packages (specifically PyDejavu 0.1.3).
"""

import os
import sys
import site
from pathlib import Path


def find_dejavu_init():
    """Find the dejavu/__init__.py file in installed packages.

    Returns:
        Path to dejavu/__init__.py or None if not found.
    """
    # Check all site-packages directories
    for site_dir in site.getsitepackages() + [site.getusersitepackages()]:
        dejavu_init = Path(site_dir) / 'dejavu' / '__init__.py'
        if dejavu_init.exists():
            return dejavu_init

    # Also check virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a virtual environment
        venv_site = Path(sys.prefix) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
        dejavu_init = venv_site / 'dejavu' / '__init__.py'
        if dejavu_init.exists():
            return dejavu_init

    return None


def apply_patch(file_path, patch_content):
    """Apply simple string replacements to fix Python 2/3 issues.

    Args:
        file_path: Path to file to patch.
        patch_content: Dictionary of {old_string: new_string} replacements.

    Returns:
        True if patched successfully, False otherwise.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content

        # Apply replacements
        for old, new in patch_content.items():
            content = content.replace(old, new)

        if content == original_content:
            return False  # No changes needed

        # Write patched content
        with open(file_path, 'w') as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"Error applying patch: {e}")
        return False


def patch_pydejavu():
    """Patch PyDejavu for Python 3 compatibility."""
    print("=" * 60)
    print("PyDejavu Python 3 Compatibility Patcher")
    print("=" * 60)
    print()

    # Find dejavu/__init__.py
    dejavu_init = find_dejavu_init()
    if not dejavu_init:
        print("❌ ERROR: Could not find PyDejavu installation")
        print("   Make sure PyDejavu is installed: pip install PyDejavu==0.1.3")
        return False

    dejavu_dir = dejavu_init.parent
    dejavu_database_sql = dejavu_dir / 'database_sql.py'
    dejavu_database = dejavu_dir / 'database.py'
    dejavu_recognize = dejavu_dir / 'recognize.py'
    dejavu_decoder = dejavu_dir / 'decoder.py'
    dejavu_wavio = dejavu_dir / 'wavio.py'
    dejavu_fingerprint = dejavu_dir / 'fingerprint.py'

    print(f"Found PyDejavu at: {dejavu_dir}")
    print()

    success_count = 0
    patch_count = 0

    # Patch __init__.py
    print("Patching __init__.py...")
    with open(dejavu_init, 'r') as f:
        init_content = f.read()

    if 'print "%s already fingerprinted' in init_content:
        patches_init = {
            # Fix print statements
            'print "%s already fingerprinted, continuing..." % filename':
                'print("%s already fingerprinted, continuing..." % filename)',
            'print "%s already fingerprinted, continuing..." % song_name':
                'print("%s already fingerprinted, continuing..." % song_name)',

            # Fix iterator.next() → next(iterator)
            'song_name, hashes, file_hash = iterator.next()':
                'song_name, hashes, file_hash = next(iterator)',

            # Fix xrange → range
            'for i in xrange(n)':
                'for i in range(n)',

            # Fix relative import
            'import fingerprint\nimport multiprocessing':
                'from . import fingerprint\nimport multiprocessing'
        }

        if apply_patch(dejavu_init, patches_init):
            print("  ✓ __init__.py patched")
            success_count += 1
        patch_count += 1
    else:
        print("  ✓ __init__.py already patched")
        success_count += 1

    # Patch database_sql.py
    print("Patching database_sql.py...")
    if dejavu_database_sql.exists():
        with open(dejavu_database_sql, 'r') as f:
            db_content = f.read()

        if 'from itertools import izip_longest' in db_content or 'import Queue' in db_content:
            patches_db = {
                # Fix izip_longest → zip_longest
                'from itertools import izip_longest':
                    'from itertools import zip_longest',
                'izip_longest(':
                    'zip_longest(',

                # Fix Queue → queue
                'import Queue':
                    'import queue as Queue'
            }

            if apply_patch(dejavu_database_sql, patches_db):
                print("  ✓ database_sql.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ database_sql.py already patched")
            success_count += 1
    else:
        print("  ⚠ database_sql.py not found")

    # Patch database.py
    print("Patching database.py...")
    if dejavu_database.exists():
        with open(dejavu_database, 'r') as f:
            db_content = f.read()

        if 'import dejavu.database_sql' in db_content and 'try:' not in db_content.split('import dejavu.database_sql')[0][-50:]:
            patches_database = {
                # Make MySQLdb import optional
                '# Import our default database handler\nimport dejavu.database_sql':
                    '# Import our default database handler\ntry:\n    import dejavu.database_sql\nexcept ImportError:\n    # MySQLdb not available, database_sql won\'t work\n    pass'
            }

            if apply_patch(dejavu_database, patches_database):
                print("  ✓ database.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ database.py already patched")
            success_count += 1
    else:
        print("  ⚠ database.py not found")

    # Patch recognize.py
    print("Patching recognize.py...")
    if dejavu_recognize.exists():
        with open(dejavu_recognize, 'r') as f:
            rec_content = f.read()

        if 'np.fromstring' in rec_content:
            patches_recognize = {
                # Fix np.fromstring → np.frombuffer
                'nums = np.fromstring(data, np.int16)':
                    'nums = np.frombuffer(data, np.int16)'
            }

            if apply_patch(dejavu_recognize, patches_recognize):
                print("  ✓ recognize.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ recognize.py already patched")
            success_count += 1
    else:
        print("  ⚠ recognize.py not found")

    # Patch decoder.py
    print("Patching decoder.py...")
    if dejavu_decoder.exists():
        with open(dejavu_decoder, 'r') as f:
            dec_content = f.read()

        if 'np.fromstring' in dec_content or 'xrange' in dec_content:
            patches_decoder = {
                # Fix np.fromstring → np.frombuffer
                'data = np.fromstring(audiofile._data, np.int16)':
                    'data = np.frombuffer(audiofile._data, np.int16)',

                # Fix xrange → range
                'for chn in xrange(audiofile.channels):':
                    'for chn in range(audiofile.channels):'
            }

            if apply_patch(dejavu_decoder, patches_decoder):
                print("  ✓ decoder.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ decoder.py already patched")
            success_count += 1
    else:
        print("  ⚠ decoder.py not found")

    # Patch wavio.py
    print("Patching wavio.py...")
    if dejavu_wavio.exists():
        with open(dejavu_wavio, 'r') as f:
            wavio_content = f.read()

        if '_np.fromstring' in wavio_content:
            patches_wavio = {
                # Fix _np.fromstring → _np.frombuffer (two occurrences)
                'raw_bytes = _np.fromstring(data, dtype=_np.uint8)':
                    'raw_bytes = _np.frombuffer(data, dtype=_np.uint8)',
                "a = _np.fromstring(data, dtype='<%s%d' % (dt_char, sampwidth))":
                    "a = _np.frombuffer(data, dtype='<%s%d' % (dt_char, sampwidth))"
            }

            if apply_patch(dejavu_wavio, patches_wavio):
                print("  ✓ wavio.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ wavio.py already patched")
            success_count += 1
    else:
        print("  ⚠ wavio.py not found")

    # Patch fingerprint.py
    print("Patching fingerprint.py...")
    if dejavu_fingerprint.exists():
        with open(dejavu_fingerprint, 'r') as f:
            fp_content = f.read()

        needs_patch = ('detected_peaks = local_max - eroded_background' in fp_content or
                      'peaks = zip(i, j, amps)' in fp_content or
                      'h = hashlib.sha1(\n                        "%s|%s|%s"' in fp_content or
                      'return generate_hashes(local_maxima, fan_value=fan_value)' in fp_content or
                      'arr2D = 10 * np.log10(arr2D)' in fp_content)

        if needs_patch:
            patches_fingerprint = {
                # Fix boolean subtract → XOR (NumPy 2.0+ compatibility)
                'detected_peaks = local_max - eroded_background':
                    'detected_peaks = local_max ^ eroded_background',

                # Fix zip() returns iterator in Python 3, need list for sorting
                'peaks = zip(i, j, amps)':
                    'peaks = list(zip(i, j, amps))',
                'return zip(frequency_idx, time_idx)':
                    'return list(zip(frequency_idx, time_idx))',

                # Fix hashlib.sha1() requires bytes in Python 3
                'h = hashlib.sha1(\n                        "%s|%s|%s" % (str(freq1), str(freq2), str(t_delta)))':
                    'h = hashlib.sha1(\n                        ("%s|%s|%s" % (str(freq1), str(freq2), str(t_delta))).encode("utf-8"))',

                # Fix fingerprint() returns generator but code expects list
                'return generate_hashes(local_maxima, fan_value=fan_value)':
                    'return list(generate_hashes(local_maxima, fan_value=fan_value))',

                # Suppress expected divide-by-zero warning (zeros are handled on next line)
                'arr2D = 10 * np.log10(arr2D)\n    arr2D[arr2D == -np.inf] = 0':
                    'with np.errstate(divide=\'ignore\'):\n        arr2D = 10 * np.log10(arr2D)\n    arr2D[arr2D == -np.inf] = 0'
            }

            if apply_patch(dejavu_fingerprint, patches_fingerprint):
                print("  ✓ fingerprint.py patched")
                success_count += 1
            patch_count += 1
        else:
            print("  ✓ fingerprint.py already patched")
            success_count += 1
    else:
        print("  ⚠ fingerprint.py not found")

    print()
    if success_count > 0:
        print("Patches applied:")
        print("  - Fixed print statements for Python 3")
        print("  - Fixed iterator.next() → next(iterator)")
        print("  - Fixed xrange → range")
        print("  - Fixed relative import")
        print("  - Fixed izip_longest → zip_longest")
        print("  - Fixed Queue → queue")
        print("  - Made MySQLdb import optional (use PostgreSQL or in-memory)")
        print("  - Fixed np.fromstring → np.frombuffer")
        print("  - Fixed boolean subtract (NumPy 2.0+ compatibility)")
        print()
        return True
    else:
        print("❌ Failed to apply patches")
        return False


def main():
    """Main entry point."""
    success = patch_pydejavu()

    print("=" * 60)
    if success:
        print("✓ All patches applied successfully!")
        print()
        print("You can now use fingerprinting:")
        print("  python generate_fingerprint_files.py source_sounds/fingerprining/ training/fingerprints/")
    else:
        print("❌ Patching failed")
        print()
        print("Try reinstalling PyDejavu:")
        print("  pip uninstall PyDejavu")
        print("  pip install PyDejavu==0.1.3")
        print("  python scripts/apply_patches.py")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
