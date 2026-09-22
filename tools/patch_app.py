"""Prepare/install/restore the explicitly requested Rekordbox 7.2.18 patch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from observe_tempo import EXPECTED, ROOT
from pe_startup_patch import patch_image

PACKAGE = ROOT/'build'/'permanent'
BACKUP = 'rekordbox.exe.rb-bpm-original'
MANIFEST = 'rb-bpm.patch.json'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, data):
    temporary = path.with_name(path.name+'.rbq-new')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def prepare(exe):
    original=exe.read_bytes()
    if hashlib.sha256(original).hexdigest()!=EXPECTED:
        raise RuntimeError('Preparation requires the exact original 7.2.18.0311 executable')
    dll=ROOT/'build'/'rb_bpm_patch.dll'
    if not dll.is_file(): raise RuntimeError('Build rb_bpm_patch.dll first')
    patched,layout=patch_image(original)
    PACKAGE.mkdir(parents=True,exist_ok=True)
    (PACKAGE/'rekordbox.exe').write_bytes(patched)
    shutil.copyfile(dll,PACKAGE/dll.name)
    (PACKAGE/'rb-bpm.ini').write_bytes(b'[Tempo]\r\nStep=default\r\n')
    manifest=dict(format=1,version='7.2.18.0311',original_sha256=EXPECTED,
                  patched_sha256=hashlib.sha256(patched).hexdigest(),dll_sha256=digest(dll),
                  dll_name=dll.name,backup_name=BACKUP,layout=layout)
    (PACKAGE/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


def install(exe):
    manifest=json.loads((PACKAGE/MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('format')!=1 or manifest.get('original_sha256')!=EXPECTED or manifest.get('dll_name')!='rb_bpm_patch.dll':
        raise RuntimeError('Unsupported package manifest')
    if digest(PACKAGE/'rekordbox.exe')!=manifest['patched_sha256'] or digest(PACKAGE/'rb_bpm_patch.dll')!=manifest['dll_sha256']:
        raise RuntimeError('Package file checksum differs')
    current=digest(exe)
    if current==manifest['patched_sha256']:
        target_dll=exe.with_name('rb_bpm_patch.dll')
        target_manifest=exe.with_name(MANIFEST)
        previous_manifest=target_manifest.read_bytes()
        previous=json.loads(previous_manifest)
        if (previous.get('format')!=1 or previous.get('original_sha256')!=EXPECTED or
            previous.get('patched_sha256')!=current or previous.get('dll_name')!='rb_bpm_patch.dll' or
            digest(exe.with_name(BACKUP))!=EXPECTED):
            raise RuntimeError('Installed patch or original backup is not recognized')
        if digest(target_dll)!=previous.get('dll_sha256'):
            raise RuntimeError('Installed extension differs from its manifest')
        if digest(target_dll)==manifest['dll_sha256']:
            print('Already installed.'); return
        previous_dll=target_dll.read_bytes()
        # Only replace the extension for this same verified patched EXE.
        # Preserve the original EXE backup and the user's existing INI.
        atomic_write(target_dll,(PACKAGE/'rb_bpm_patch.dll').read_bytes())
        try:
            atomic_write(target_manifest,(PACKAGE/MANIFEST).read_bytes())
        except Exception:
            atomic_write(target_dll,previous_dll)
            raise
        print('Extension updated. Original backup and settings retained.'); return
    if current!=EXPECTED: raise RuntimeError('Target EXE is not the supported unmodified build')
    backup=exe.with_name(BACKUP)
    if backup.exists() and digest(backup)!=EXPECTED:
        raise RuntimeError('Existing backup is not the exact original; refusing to overwrite it')
    for name in ('rb_bpm_patch.dll',MANIFEST):
        target=exe.with_name(name)
        if target.exists() and target.read_bytes()!=(PACKAGE/name).read_bytes():
            raise RuntimeError('Existing target file differs: '+str(target))
    if not backup.exists():
        with backup.open('xb') as stream:
            stream.write(exe.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    if digest(backup)!=EXPECTED: raise RuntimeError('Backup verification failed')
    for name in ('rb_bpm_patch.dll',MANIFEST,'rb-bpm.ini'):
        target=exe.with_name(name)
        if not target.exists(): atomic_write(target,(PACKAGE/name).read_bytes())
    # Commit the modified EXE last. The original is already backed up and verified.
    atomic_write(exe,(PACKAGE/'rekordbox.exe').read_bytes())
    if digest(exe)!=manifest['patched_sha256']: raise RuntimeError('Installed EXE checksum differs')
    print('Installed. Verified original backup: '+str(backup))


def restore(exe):
    backup=exe.with_name(BACKUP)
    if not backup.is_file() or digest(backup)!=EXPECTED:
        raise RuntimeError('Missing or invalid original backup')
    manifest=json.loads(exe.with_name(MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('original_sha256')!=EXPECTED: raise RuntimeError('Unknown installed manifest')
    current=digest(exe)
    if current not in (EXPECTED,manifest.get('patched_sha256')):
        raise RuntimeError('EXE was changed or updated since patching; refusing to overwrite it')
    if current!=EXPECTED: atomic_write(exe,backup.read_bytes())
    if digest(exe)!=EXPECTED: raise RuntimeError('Restoration verification failed')
    # Retain backup and INI; neither is loaded by the restored executable.
    dll=exe.with_name('rb_bpm_patch.dll')
    if dll.exists() and digest(dll)==manifest.get('dll_sha256'): dll.unlink()
    print('Original EXE restored and verified. Backup and settings retained.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','install','restore'])
    parser.add_argument('--exe',type=Path,required=True)
    args=parser.parse_args()
    exe=args.exe.resolve(strict=True)
    if exe.name.lower()!='rekordbox.exe': parser.error('Target must be named rekordbox.exe')
    globals()[args.action](exe)


if __name__=='__main__': main()
