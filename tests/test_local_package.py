"""Opt-in installer test on temporary copies; never writes the real installation.

RBQ_TEST_ORIGINAL must point to the exact original/backup. Build the extension first.
Vendor binaries are not repository fixtures and are not needed by the other tests.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import patch_app
from check_compatibility import load_registry


@unittest.skipUnless(os.environ.get('RBQ_TEST_ORIGINAL'), 'Local original EXE not supplied')
class LocalPackageTests(unittest.TestCase):
    def test_prepare_install_upgrade_rollback_restore(self):
        source = Path(os.environ['RBQ_TEST_ORIGINAL'])
        baseline = next(b for b in load_registry() if b['id']=='7.2.18.0311-windows-x64')
        self.assertEqual(patch_app.digest(source), baseline['original_sha256'])
        with tempfile.TemporaryDirectory(prefix='rb-plus-test-') as folder:
            root = Path(folder)
            exe = root/'install/rekordbox.exe'
            exe.parent.mkdir()
            exe.write_bytes(source.read_bytes())
            package = root/'package'
            with patch.object(patch_app, 'PACKAGE', package), contextlib.redirect_stdout(io.StringIO()):
                patch_app.prepare(source)
                self.assertIn(patch_app.digest(package/'rekordbox.exe'), baseline['patched_sha256'])
                patch_app.install(exe)
                patch_app.install(exe)
                ini = exe.with_name('rb-bpm.ini')
                ini.write_bytes(b'[Tempo]\r\nStep=0.1\r\n')
                previous_dll = exe.with_name('rb_bpm_patch.dll').read_bytes()
                # File-lifecycle test only: the temporary DLL is never executed.
                (package/'rb_bpm_patch.dll').write_bytes(b'new-test-extension')
                manifest = json.loads((package/patch_app.MANIFEST).read_text())
                manifest['dll_sha256'] = hashlib.sha256(b'new-test-extension').hexdigest()
                (package/patch_app.MANIFEST).write_text(json.dumps(manifest))
                real_write = patch_app.atomic_write
                def fail_manifest(path, data):
                    if path.name == patch_app.MANIFEST:
                        raise OSError('Simulated manifest replacement failure')
                    return real_write(path, data)
                with patch.object(patch_app, 'atomic_write', side_effect=fail_manifest):
                    with self.assertRaises(OSError):
                        patch_app.install(exe)
                self.assertEqual(exe.with_name('rb_bpm_patch.dll').read_bytes(), previous_dll)
                patch_app.install(exe)
                self.assertEqual(exe.with_name('rb_bpm_patch.dll').read_bytes(), b'new-test-extension')
                patch_app.restore(exe)
                patch_app.restore(exe)
                self.assertEqual(patch_app.digest(exe), baseline['original_sha256'])
                self.assertEqual(ini.read_bytes(), b'[Tempo]\r\nStep=0.1\r\n')
                self.assertEqual(patch_app.digest(exe.with_name(patch_app.BACKUP)), baseline['original_sha256'])
                self.assertFalse(exe.with_name('rb_bpm_patch.dll').exists())


if __name__ == '__main__':
    unittest.main()
