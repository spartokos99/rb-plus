"""Read-only, hash-pinned preflight. Never starts, injects, patches or certifies runtime behavior."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'compatibility/builds.json'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_registry(path=REGISTRY):
    registry = json.loads(path.read_text(encoding='utf-8'))
    if registry.get('schema_version') != 1 or not isinstance(registry.get('builds'), list):
        raise ValueError('Unsupported build registry')
    ids, hashes = set(), set()
    for build in registry['builds']:
        if build['id'] in ids or build['architecture'] != 'x64':
            raise ValueError('Duplicate build ID or unsupported architecture')
        ids.add(build['id'])
        for digest in [build['original_sha256'], *build['patched_sha256']]:
            if not re.fullmatch('[0-9a-f]{64}', digest) or digest in hashes:
                raise ValueError('Invalid or ambiguous build checksum')
            hashes.add(digest)
        for digest in build['tested_extension_sha256']:
            if not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Invalid extension checksum')
        if not bytes.fromhex(build['checks']['setter_signature']):
            raise ValueError('Missing setter signature')
    return registry['builds']


class PeImage:
    def __init__(self, data):
        self.data = data
        if len(data) < 64 or data[:2] != b'MZ':
            raise ValueError('Not a PE executable')
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        if data[pe:pe+4] != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        machine, count = struct.unpack_from('<HH', data, pe+4)
        opt_size = struct.unpack_from('<H', data, pe+20)[0]
        opt = pe+24
        if machine != 0x8664 or opt_size < 112 or struct.unpack_from('<H', data, opt)[0] != 0x20b:
            raise ValueError('Expected Windows x64 PE32+')
        self.base = struct.unpack_from('<Q', data, opt+24)[0]
        self.sections = []
        for i in range(count):
            size, rva, raw_size, raw = struct.unpack_from('<4I', data, opt+opt_size+i*40+8)
            if raw+raw_size > len(data):
                raise ValueError('Truncated PE section')
            self.sections.append((rva, raw_size, raw))

    def read(self, rva, size):
        for start, length, raw in self.sections:
            if start <= rva and rva+size <= start+length:
                return self.data[raw+rva-start:raw+rva-start+size]
        raise ValueError('Checked RVA is outside file-backed sections')


def inspect(exe, builds):
    exe = Path(exe)
    if exe.is_dir():
        exe = exe/'rekordbox.exe'
    exe = exe.resolve(strict=True)
    data = exe.read_bytes()
    digest = sha256(data)
    report = dict(path=str(exe), sha256=digest, recognized=False, static_match=False,
                  runtime_tested_this_run=False, errors=[])
    matches = [b for b in builds if digest in [b['original_sha256'], *b['patched_sha256']]]
    if len(matches) != 1:
        report['errors'].append('Unknown or ambiguous executable hash; analysis required before any hook or patch')
        return report
    build = matches[0]
    report.update(recognized=True, build=build['id'], support_status=build['status'],
                  kind='original' if digest == build['original_sha256'] else 'patched',
                  known_limits=build['known_limits'], report=build['report'])
    try:
        pe = PeImage(data)
        checks = build['checks']
        setter = int(checks['setter_rva'], 0)
        signature = bytes.fromhex(checks['setter_signature'])
        if pe.read(setter, len(signature)) != signature:
            raise ValueError('Tempo setter signature differs')
        slot = struct.unpack('<Q', pe.read(int(checks['setter_slot_rva'], 0), 8))[0]
        if slot != pe.base+setter:
            raise ValueError('Tempo setter VTable slot differs')
        if report['kind'] == 'patched':
            manifest = json.loads(exe.with_name('rb-bpm.patch.json').read_text(encoding='utf-8'))
            if (manifest.get('format') != 1 or manifest.get('original_sha256') != build['original_sha256'] or
                    manifest.get('patched_sha256') != digest or manifest.get('version') != build['product_version'] or
                    manifest.get('dll_name') != 'rb_bpm_patch.dll' or
                    manifest.get('backup_name') != 'rekordbox.exe.rb-bpm-original'):
                raise ValueError('Installed manifest does not match the known build')
            if sha256(exe.with_name('rekordbox.exe.rb-bpm-original').read_bytes()) != build['original_sha256']:
                raise ValueError('Original backup checksum differs')
            dll_hash = sha256(exe.with_name('rb_bpm_patch.dll').read_bytes())
            if dll_hash != manifest.get('dll_sha256'):
                raise ValueError('Installed extension differs from its manifest')
            report.update(extension_integrity='matches_manifest', extension_sha256=dll_hash,
                          extension_tested_release=dll_hash in build['tested_extension_sha256'])
        report['static_match'] = True
    except (OSError, ValueError, KeyError, struct.error) as error:
        report['errors'].append(str(error))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', required=True, type=Path, help='Installation directory or executable')
    args = parser.parse_args()
    try:
        report = inspect(args.path, load_registry())
    except (OSError, ValueError, KeyError, struct.error) as error:
        report = dict(recognized=False, static_match=False, runtime_tested_this_run=False, errors=[str(error)])
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report['static_match'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
