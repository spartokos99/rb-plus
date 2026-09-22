import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_compatibility import inspect, load_registry, sha256


def sample_pe():
    data = bytearray(0x400)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 0xf0)
    struct.pack_into('<H', data, 0x98, 0x20b)
    struct.pack_into('<Q', data, 0xb0, 0x140000000)
    struct.pack_into('<8sIIII', data, 0x188, b'.text', 0x200, 0x1000, 0x200, 0x200)
    data[0x200:0x204] = b'\x40\x53\x48\x83'
    struct.pack_into('<Q', data, 0x210, 0x140001000)
    return bytes(data)


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.exe = self.folder/'rekordbox.exe'
        self.original = sample_pe()
        self.exe.write_bytes(self.original)
        self.profile = dict(id='fixture-x64', product_version='fixture', architecture='x64',
                            status='test_only', original_sha256=sha256(self.original),
                            patched_sha256=[], tested_extension_sha256=[], known_limits=[], report='fixture.md',
                            checks=dict(setter_rva='0x1000', setter_signature='40534883', setter_slot_rva='0x1010'))

    def test_original_is_read_only_and_not_a_runtime_certificate(self):
        before = self.exe.stat().st_mtime_ns
        result = inspect(self.folder, [self.profile])
        self.assertTrue(result['static_match'])
        self.assertFalse(result['runtime_tested_this_run'])
        self.assertEqual(self.exe.read_bytes(), self.original)
        self.assertEqual(self.exe.stat().st_mtime_ns, before)
        self.assertEqual([p.name for p in self.folder.iterdir()], ['rekordbox.exe'])

    def test_same_signature_with_unknown_hash_is_rejected(self):
        self.exe.write_bytes(self.original+b'changed-build')
        result = inspect(self.exe, [self.profile])
        self.assertFalse(result['recognized'])
        self.assertFalse(result['static_match'])

    def test_additional_build_does_not_replace_previous_one(self):
        another = copy.deepcopy(self.profile)
        another.update(id='second-fixture', original_sha256=sha256(self.original+b'second'))
        profiles = [self.profile, another]
        self.assertEqual(inspect(self.exe, profiles)['build'], self.profile['id'])
        self.exe.write_bytes(self.original+b'second')
        self.assertTrue(inspect(self.exe, profiles)['static_match'])
        self.assertEqual(inspect(self.exe, profiles)['build'], another['id'])

    def test_signature_and_slot_are_checked(self):
        for field, wrong in [('setter_signature','00000000'), ('setter_slot_rva','0x1020')]:
            with self.subTest(field=field):
                profile = copy.deepcopy(self.profile)
                profile['checks'][field] = wrong
                self.assertFalse(inspect(self.exe, [profile])['static_match'])

    def prepare_patched(self):
        patched = self.original+b'patched-fixture'
        self.exe.write_bytes(patched)
        self.profile['patched_sha256'] = [sha256(patched)]
        (self.folder/'rekordbox.exe.rb-bpm-original').write_bytes(self.original)
        (self.folder/'rb_bpm_patch.dll').write_bytes(b'fixture-not-executable')
        manifest = dict(format=1, version='fixture', original_sha256=self.profile['original_sha256'],
                        patched_sha256=sha256(patched), dll_sha256=sha256(b'fixture-not-executable'),
                        dll_name='rb_bpm_patch.dll', backup_name='rekordbox.exe.rb-bpm-original')
        (self.folder/'rb-bpm.patch.json').write_text(json.dumps(manifest))

    def test_patched_integrity_is_distinct_from_tested_release(self):
        self.prepare_patched()
        result = inspect(self.exe, [self.profile])
        self.assertTrue(result['static_match'])
        self.assertFalse(result['extension_tested_release'])
        self.profile['tested_extension_sha256'] = [result['extension_sha256']]
        self.assertTrue(inspect(self.exe, [self.profile])['extension_tested_release'])

    def test_tampered_dll_and_backup_are_rejected(self):
        for name in ['rb_bpm_patch.dll', 'rekordbox.exe.rb-bpm-original']:
            with self.subTest(file=name):
                self.prepare_patched()
                (self.folder/name).write_bytes(b'tampered')
                self.assertFalse(inspect(self.exe, [self.profile])['static_match'])

    def test_missing_manifest_is_rejected(self):
        self.prepare_patched()
        (self.folder/'rb-bpm.patch.json').unlink()
        self.assertFalse(inspect(self.exe, [self.profile])['static_match'])

    def test_duplicate_registry_hash_rejected(self):
        another = copy.deepcopy(self.profile)
        another['id'] = 'another-id'
        path = self.folder/'builds.json'
        path.write_text(json.dumps(dict(schema_version=1, builds=[self.profile, another])))
        with self.assertRaises(ValueError):
            load_registry(path)

    def test_checked_in_registry_preserves_initial_backend_identity(self):
        profiles = load_registry()
        baseline = next(b for b in profiles if b['id']=='7.2.18.0311-windows-x64')
        self.assertEqual(baseline['original_sha256'], 'a99896cf26d5998e6ad4177796a467b83df14bf8ae7207df21ed01251e402493')
        for profile in profiles:
            self.assertTrue((ROOT/profile['report']).is_file())
            self.assertTrue((ROOT/profile['backend']).is_file())


if __name__ == '__main__':
    unittest.main()
