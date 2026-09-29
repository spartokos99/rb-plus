"""Portable release entry point; reuse the existing hash-pinned installer."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import patch_app
from check_compatibility import inspect, load_registry

ROOT = Path(__file__).resolve().parents[1]
BUILD_ID = '7.2.18.0311-windows-x64'


def run(action, exe):
    exe = Path(exe).resolve(strict=True)
    if exe.is_dir():
        exe = exe/'rekordbox.exe'
    if exe.name.lower() != 'rekordbox.exe':
        raise RuntimeError('Please select your installed rekordbox.exe.')
    builds = load_registry()
    report = inspect(exe, builds)
    if not report['static_match'] or report.get('build') != BUILD_ID:
        raise RuntimeError('Not compatible: ' + '; '.join(report['errors']))
    print('Verified: Rekordbox 7.2.18.0311 / Windows x64 (' + report['kind'] + ').')
    if action == 'check':
        print('Static checks passed. This is not an audio or hardware test.')
        return
    if action == 'restore':
        patch_app.restore(exe)
        return

    build = next(item for item in builds if item['id'] == BUILD_ID)
    dll = ROOT/'rb_bpm_patch.dll'
    if patch_app.digest(dll) not in build['tested_extension_sha256']:
        raise RuntimeError('The release DLL does not match the tested build.')
    original = exe if report['kind'] == 'original' else exe.with_name(patch_app.BACKUP)
    previous_root, previous_package = patch_app.ROOT, patch_app.PACKAGE
    try:
        with tempfile.TemporaryDirectory(prefix='rb-plus-install-') as folder:
            patch_app.ROOT = Path(folder)
            patch_app.PACKAGE = Path(folder)/'build/permanent'
            (Path(folder)/'build').mkdir()
            shutil.copyfile(dll, Path(folder)/'build/rb_bpm_patch.dll')
            patch_app.prepare(original)
            patch_app.install(exe)
    finally:
        patch_app.ROOT, patch_app.PACKAGE = previous_root, previous_package
    # The extension stores its mode beside the EXE, also under Program Files.
    # Only this data file needs user write access; keep executable ACLs intact.
    permissions = subprocess.run([
        str(Path(os.environ['SystemRoot'])/'System32/icacls.exe'),
        str(exe.with_name('rb-bpm.ini')), '/grant', '*S-1-5-32-545:W',
    ], capture_output=True)
    if permissions.returncode:
        raise RuntimeError('Patch installed, but write access to the INI file could not be granted. '
                           'Please run Install.cmd again as administrator.')
    print('Done. Start Rekordbox normally: Preferences > Extensions > RB PLUS.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'restore', 'check'])
    parser.add_argument('--exe', required=True, type=Path)
    args = parser.parse_args()
    try:
        run(args.action, args.exe)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('ERROR: ' + str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
