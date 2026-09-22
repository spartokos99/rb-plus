"""Bounded input trace for the RB PLUS combo; stop removes both diagnostic hooks."""
import argparse
import json
from pathlib import Path
import struct
from tempo_control import Remote, exports, find_dll
from preferences_mouse import send

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['start', 'read', 'reset', 'forward', 'stop'])
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--preferences', type=int, required=True)
args = parser.parse_args()
p = Remote(args.pid)
dll = Path(__file__).resolve().parents[1]/'build/ui_input_probe.dll'
try:
    sym = exports(dll)
    base = find_dll(p, dll)
    if args.action == 'start':
        if base: raise RuntimeError('Diagnostic is already loaded; use reset')
        p.enable_control(args.pid)
        base = p.load_dll(dll)
        result = p.invoke(base+sym['probeStart'], struct.pack('<Q', args.preferences))
        print(json.dumps({'start': result}))
        if result: raise RuntimeError('Diagnostic hook failed')
    elif args.action == 'read':
        count = min(512, p.unpack(base+sym['probeCount'], '<I'))
        data = p.read(base+sym['probeEvents'], count*48)
        rows = [dict(zip(['kind','message','window','w','l','focus','capture'],
                         struct.unpack_from('<IIQQQQQ', data, i*48))) for i in range(count)]
        print(json.dumps(rows, indent=2))
    else:
        send(args.preferences, 0x8677, 3 if args.action=='stop' else 2, int(args.action=='forward'))
finally:
    p.close()
