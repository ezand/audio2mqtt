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

        if 'from itertools import izip_longest' in db_content:
            patches_db = {
                # Fix izip_longest → zip_longest
                'from itertools import izip_longest':
                    'from itertools import zip_longest',
                'izip_longest(':
                    'zip_longest('
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

    print()
    if success_count > 0:
        print("Patches applied:")
        print("  - Fixed print statements for Python 3")
        print("  - Fixed iterator.next() → next(iterator)")
        print("  - Fixed xrange → range")
        print("  - Fixed relative import")
        print("  - Fixed izip_longest → zip_longest")
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
