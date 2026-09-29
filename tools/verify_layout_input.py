"""Exercise layout permutations with real input and read back native component positions.

Requires an idle 4Deck Horizontal test session with the RB PLUS page open.
Changes both orders temporarily and restores their original selections.
"""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys

from observe_layout import snapshot
from observe_tempo import Process
from preferences_mouse import u, send


def verify(state, waves, decks):
    assert state['layout'] == 0x14 and state['app_mode'] & 2
    wave_order = [deck for pair in state['pairs'] for deck in pair['sources'][:2]]
    assert wave_order == list(waves), state
    sorted_decks = sorted(state['decks'], key=lambda d: (d['area'][1], d['area'][0]))
    assert [d['deck'] for d in sorted_decks] == list(decks), state
    for d in state['decks']:
        assert d['area'] == d['active'] == d['drop'], d
        assert d['area'][:2] == d['track_info'][:2], d
        x, y, width, height = d['area']
        cx, cy, cw, ch = d['controls']
        assert x <= cx < cx+cw <= x+width and y <= cy < cy+ch <= y+height, d
        row = list(waves).index(d['deck'])
        assert d['wave_parent'] == row//2, d
        others = [item for item in state['decks'] if item['wave_parent'] == row//2]
        assert sorted(others, key=lambda item: item['wave'][1])[row%2]['deck'] == d['deck'], d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--preferences', type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    panel = u.GetPropW(args.preferences, 'RBQ.TempoPanel')
    controls = [1002, 1003]
    original = [send(u.GetDlgItem(panel, control), 0x147) for control in controls]
    if not panel or any(index > 24 for index in original):
        raise RuntimeError('Open RB PLUS first')
    choices = [tuple(range(1, 5)), *itertools.permutations(range(1, 5))]
    p = Process(args.pid)
    rows = []
    def select(control, selected, extra=()):
        result = subprocess.run([sys.executable, str(root/'tools/preferences_mouse.py'),
                                 '--preferences', str(args.preferences), '--control', str(control),
                                 '--select', str(selected), '--hover-ms', '120', *extra],
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)
        return json.loads(result.stdout)
    current = list(original)
    try:
        owners, _ = p.discover(8)
        if not owners or any(p.snapshot(owner)['playing'] for owner in owners):
            raise RuntimeError('All players must be paused for the permutation test')
        assert snapshot(p)['layout'] == 0x14
        for kind, control in enumerate(controls):
            for selected in range(25):
                input_result = select(control, selected)
                current[kind] = selected
                state = snapshot(p)
                verify(state, choices[current[0]], choices[current[1]])
                rows.append(dict(control=control, selection=selected, input=input_result, state=state))
                print(f'{control}: {selected}/24 passed', flush=True)
            for cancel in ('escape', 'outside'):
                select(control, 1, ('--cancel', cancel))
                verify(snapshot(p), choices[current[0]], choices[current[1]])
            select(control, 13, ('--keyboard',))
            current[kind] = 13
            verify(snapshot(p), choices[current[0]], choices[current[1]])
    finally:
        try:
            for control, index in zip(controls, original):
                select(control, index, ('--keyboard',))
        finally:
            p.close()
            (root/'artifacts/layout-input-verification.json').write_text(json.dumps(rows, indent=2))
    print('All permutations, cancellation and keyboard passed; original settings restored.')


if __name__ == '__main__':
    main()
