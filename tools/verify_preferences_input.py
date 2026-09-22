"""Integration check against an open RB PLUS page (changes/restores the setting)."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempo_control import Remote, active_extension, exports, status

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--preferences', type=int, required=True)
parser.add_argument('--restore-mode', type=int, choices=range(3))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
p = Remote(args.pid)
try:
    dll, base, permanent = active_extension(p)
    if not permanent: raise RuntimeError('Permanent extension required')
    symbols = exports(dll)
    original = status(p, base, symbols)['mode'] if args.restore_mode is None else args.restore_mode
    cases = [(n, []) for n in (0, 1, 2)]
    cases += [(2, ['--cancel', n]) for n in ('escape', 'outside')]
    cases += [(n, ['--keyboard']) for n in (0, 2, original)]
    rows = []
    try:
        for selected, extra in cases:
            result = subprocess.run([sys.executable, str(root/'tools/preferences_mouse.py'),
                                     '--preferences', str(args.preferences), '--select', str(selected),
                                     '--hover-ms', '700', *extra], capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            row = json.loads(result.stdout)
            row['input'] = extra or ['mouse']
            row['hook_mode'] = status(p, base, symbols)['mode']
            row['ini'] = (p.path.parent/'rb-bpm.ini').read_text().strip()
            assert row['passed'] and row['hook_mode'] == row['expected'], row
            assert 'Step='+['default','0.1','1'][row['expected']] in row['ini'], row
            rows.append(row)
            print(json.dumps({'input': row['input'], 'mode': row['hook_mode'], 'passed': True}), flush=True)
    finally:
        (root/'artifacts/combo-input-verification.json').write_text(json.dumps(rows, indent=2))
finally:
    p.close()
