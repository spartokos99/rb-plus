"""Explicit live integration test; controls the prepared single loaded Deck 1.

Requires already playing Performance mode and an installed diagnostic hook.
Always restores Default and 174 BPM in finally. Does not start/stop playback.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

from observe_tempo import Process, ROOT
from tempo_control import exports, find_dll, status, DLL


def ps(script, *args):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                             '-File', str(ROOT/script), *map(str, args)],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    args = parser.parse_args()
    process = Process(args.pid)
    try:
        owners, _ = process.discover(10)
        loaded = [owner for owner in owners if process.snapshot(owner)['grid_bpm'] is not None]
        if len(loaded) != 1:
            raise RuntimeError('Test requires exactly one loaded deck')
        owner = loaded[0]
        first = process.snapshot(owner)
        if first['grid_bpm'] != 174 or not first['playing']:
            raise RuntimeError('Prepared Deck 1 must be playing with original BPM 174')
        base, symbols = find_dll(process), exports(DLL)
        if not status(process, base, symbols)['installed']:
            raise RuntimeError('Install the diagnostic hook first')
        cases = [('1',175.37,175), ('1',175.59,175), ('1',175.61,176),
                 ('1',175.41,176), ('1',175.39,175), ('1',184.44,184),
                 ('1',163.56,164), ('0.1',175.37,175.4), ('0.1',175.349,175.4),
                 ('0.1',175.33,175.3), ('Default',175.37,175.37), ('Default',174,174)]
        path = ROOT/'artifacts'/('live-verification-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl')
        with path.open('x',encoding='utf-8') as log:
            previous_mode = None
            try:
                for selected, requested, expected in cases:
                    if selected != previous_mode:
                        ps(Path('Set-TempoStep.ps1'), '-Step', selected)
                        previous_mode = selected
                    ps(Path('tools/deck1_probe.ps1'), '-Action', 'Bpm', '-Bpm', requested)
                    time.sleep(0.15)
                    sample = process.snapshot(owner)
                    hook = status(process, base, symbols)
                    assert sample['playing'], 'Playback stopped during verification'
                    assert sample['grid_bpm'] == 174 and sample['grid'] == first['grid'], 'Track/grid changed'
                    assert abs(sample['nominal_bpm']-expected) < 0.0001, sample
                    assert sample['audio_part_bpms'] and all(abs(bpm-expected)<0.0001 for bpm in sample['audio_part_bpms']), sample
                    assert hook['concurrent'] == 0
                    assert all(record['bypass'] == 0 for record in hook['records'])
                    row = dict(mode=selected, requested=requested, expected=expected, state=sample, hook=hook)
                    log.write(json.dumps(row)+'\n'); log.flush()
                    print(f'{selected}: {requested} -> audio {sample["audio_part_bpms"]}: OK',flush=True)
            finally:
                ps(Path('Set-TempoStep.ps1'), '-Step', 'Default')
                ps(Path('tools/deck1_probe.ps1'), '-Action', 'Bpm', '-Bpm', 174)
        print('Evidence:',path)
    finally:
        process.close()


if __name__ == '__main__':
    main()
