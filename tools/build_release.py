"""Bundle the tested extension, existing installer and a local isolated CPython."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import zipfile

from check_compatibility import load_registry

ROOT = Path(__file__).resolve().parents[1]
BUILD_ID = '7.2.18.0311-windows-x64'
VERSION = '1.0.0'
NAME = f'RB-PLUS-v{VERSION}-Rekordbox-7.2.18.0311-Windows-x64'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release(dll, output):
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('Run with Windows x64 CPython.')
    profile = next(item for item in load_registry() if item['id'] == BUILD_ID)
    if digest(dll) not in profile['tested_extension_sha256']:
        raise RuntimeError('Only a recorded, runtime-tested DLL may be released.')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rb-plus-release-') as folder:
        stage = Path(folder)/NAME
        stage.mkdir()
        shutil.copyfile(dll, stage/'rb_bpm_patch.dll')
        for name in ('Setup.ps1', 'README.txt'):
            shutil.copyfile(ROOT/'release'/name, stage/name)
        for name in ('patch_app.py', 'pe_startup_patch.py', 'observe_tempo.py',
                     'check_compatibility.py', 'release_patch.py'):
            target = stage/'tools'/name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(ROOT/'tools'/name, target)
        for name in ('builds.json', 'reports/7.2.18.0311-windows-x64.md'):
            target = stage/'compatibility'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/'compatibility'/name, target)
        for name, action in (('Install', 'Install'), ('Uninstall', 'Restore'),
                             ('Check-Compatibility', 'Check')):
            (stage/f'{name}.cmd').write_text(
                '@echo off\nsetlocal\n'
                'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -STA '
                f'-File "%~dp0Setup.ps1" -Action {action}\n'
                'set "RBQ_RESULT=%ERRORLEVEL%"\npause\nexit /b %RBQ_RESULT%\n',
                encoding='ascii', newline='\r\n')

        runtime = stage/'runtime'
        runtime.mkdir()
        base = Path(sys.base_prefix)
        tag = f'python{sys.version_info.major}{sys.version_info.minor}'
        for name in ('python.exe', f'{tag}.dll', 'python3.dll', 'vcruntime140.dll',
                     'vcruntime140_1.dll', 'LICENSE.txt'):
            shutil.copyfile(base/name, runtime/name)
        # Keep CPython's own native modules; no development-environment packages.
        for source in (base/'DLLs').iterdir():
            if source.suffix in ('.pyd', '.dll'):
                shutil.copyfile(source, runtime/source.name)
        excluded = {'site-packages', '__pycache__', 'ensurepip', 'idlelib',
                    'tkinter', 'turtledemo', 'test', 'tests'}
        with zipfile.ZipFile(runtime/f'{tag}.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for source in sorted((base/'Lib').rglob('*.py')):
                relative = source.relative_to(base/'Lib')
                if not excluded.intersection(relative.parts):
                    archive.write(source, relative.as_posix())
        (runtime/f'{tag}._pth').write_text(f'{tag}.zip\n.\n../tools\n', encoding='ascii')
        (stage/'release.json').write_text(json.dumps(dict(
            version=VERSION, build=BUILD_ID, extension_sha256=digest(dll), python=sys.version,
            runtime_tested_this_run=False,
            runtime_basis='Registered runtime-tested extension; see compatibility/reports/7.2.18.0311-windows-x64.md for this DLL hash and coverage',
        ), indent=2)+'\n', encoding='utf-8')
        entries = sorted(path for path in stage.rglob('*') if path.is_file())
        (stage/'SHA256SUMS.txt').write_text(''.join(
            f'{digest(path)}  {path.relative_to(stage).as_posix()}\n' for path in entries
        ), encoding='utf-8')
        target = output/f'{NAME}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(stage.rglob('*')):
                if source.is_file():
                    archive.write(source, source.relative_to(stage.parent).as_posix())
    checksum = digest(target)
    target.with_suffix('.zip.sha256').write_text(f'{checksum}  {target.name}\n', encoding='ascii')
    print(f'{target}\n{target.stat().st_size:,} bytes\nSHA-256: {checksum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'packages')
    args = parser.parse_args()
    build_release(args.dll.resolve(strict=True), args.output.resolve())


if __name__ == '__main__':
    main()
