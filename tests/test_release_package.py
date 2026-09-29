"""Opt-in test of the actual ZIP, without changing or launching Rekordbox."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.environ.get('RBQ_TEST_RELEASE') and os.environ.get('RBQ_TEST_ORIGINAL'),
                     'Release ZIP and local original EXE not supplied')
class ReleasePackageTests(unittest.TestCase):
    def test_portable_runtime_install_repeat_restore_and_rejections(self):
        with tempfile.TemporaryDirectory(prefix='rb-plus-release-test-') as folder:
            # Spaces and non-ASCII paths also occur on the destination laptop.
            root = Path(folder)/'Laptop Test ä'
            with zipfile.ZipFile(os.environ['RBQ_TEST_RELEASE']) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(root)
            package = next(root.iterdir())
            self.assertEqual({p.name for p in package.glob('*.cmd')},
                             {'Install.cmd', 'Uninstall.cmd', 'Check-Compatibility.cmd'})
            self.assertTrue((package/'README.txt').is_file())
            release = json.loads((package/'release.json').read_text(encoding='utf-8'))
            self.assertEqual(release['version'], '1.0.0')
            self.assertEqual(release['extension_sha256'], digest(package/'rb_bpm_patch.dll'))
            checksums = (package/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(checksums), len([p for p in package.rglob('*') if p.is_file()])-1)
            for line in checksums:
                expected, name = line.split('  ', 1)
                self.assertEqual(digest(package/name), expected, name)
            self.assertEqual([p.name for p in package.rglob('*.exe')], ['python.exe'])
            self.assertFalse(list(package.rglob('*.rb-bpm-original')))
            self.assertFalse(list(package.rglob('*.db')))
            self.assertFalse(list(package.rglob('site-packages')))
            profile = json.loads((package/'compatibility/builds.json').read_text())['builds'][0]
            python = str(package/'runtime/python.exe')
            env = dict(os.environ, PYTHONPATH=str(root/'unwanted'), PYTHONHOME=str(root/'unwanted'))
            env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
            result = subprocess.run([python, '-I', '-B', '-c',
                'import sys,ctypes,json; print(json.dumps(dict(paths=sys.path, isolated=sys.flags.isolated)))'],
                env=env, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            info = json.loads(result.stdout)
            self.assertEqual(info['isolated'], 1)
            self.assertTrue(all(Path(path).is_relative_to(package) for path in info['paths']))
            exe = root/'Own Installation/rekordbox.exe'
            exe.parent.mkdir()
            exe.write_bytes(Path(os.environ['RBQ_TEST_ORIGINAL']).read_bytes())
            self.assertEqual(digest(exe), profile['original_sha256'])
            ini = exe.with_name('rb-bpm.ini')
            ini.write_bytes(b'[Tempo]\r\nStep=0.1\r\n')
            backup = exe.with_name('rekordbox.exe.rb-bpm-original')

            def run(action, ok=True):
                result = subprocess.run([python, '-I', '-B', str(package/'tools/release_patch.py'),
                                         action, '--exe', str(exe)], env=env, cwd=root,
                                        capture_output=True, text=True)
                if ok:
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)

            run('check')
            self.assertFalse(backup.exists())
            run('install')
            self.assertIn(digest(exe), profile['patched_sha256'])
            self.assertEqual(digest(backup), profile['original_sha256'])
            self.assertIn(digest(exe.with_name('rb_bpm_patch.dll')), profile['tested_extension_sha256'])
            acl = subprocess.run([
                str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
                '-NoProfile', '-Command',
                '$rules = (Get-Acl -LiteralPath $env:RBQ_TEST_INI).Access; '
                '$writable = @($rules | Where-Object { '
                '$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value '
                '-eq "S-1-5-32-545" -and $_.AccessControlType -eq "Allow" -and '
                '($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Write) '
                '-eq [System.Security.AccessControl.FileSystemRights]::Write }); '
                'if (-not $writable.Count) { exit 1 }',
            ], env=dict(env, RBQ_TEST_INI=str(ini)), capture_output=True, text=True)
            self.assertEqual(acl.returncode, 0, acl.stdout+acl.stderr)
            backup_time = backup.stat().st_mtime_ns
            run('install')
            self.assertEqual(backup.stat().st_mtime_ns, backup_time)
            run('check')
            run('restore')
            run('restore')
            run('install')
            run('restore')
            self.assertEqual(digest(exe), profile['original_sha256'])
            self.assertFalse(exe.with_name('rb_bpm_patch.dll').exists())
            self.assertEqual(ini.read_bytes(), b'[Tempo]\r\nStep=0.1\r\n')
            self.assertEqual(backup.stat().st_mtime_ns, backup_time)

            # Unknown builds and a changed original backup must not be overwritten.
            exe.write_bytes(b'unsupported build')
            run('install', ok=False)
            run('restore', ok=False)
            self.assertEqual(exe.read_bytes(), b'unsupported build')
            exe.write_bytes(backup.read_bytes())
            backup.write_bytes(b'foreign backup')
            run('install', ok=False)
            self.assertEqual(digest(exe), profile['original_sha256'])
            self.assertEqual(backup.read_bytes(), b'foreign backup')
            backup.write_bytes(exe.read_bytes())
            (package/'rb_bpm_patch.dll').write_bytes(b'tampered extension')
            run('install', ok=False)
            self.assertEqual(digest(exe), profile['original_sha256'])


if __name__ == '__main__':
    unittest.main()
