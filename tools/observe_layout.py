"""Read-only layout/identity snapshot for the pinned Rekordbox 7.2.18.0311 build."""
import argparse
import json
import struct

from observe_tempo import Process
from tempo_control import modules, exports


def snapshot(process):
    p = process
    def read(address, fmt):
        return struct.unpack(fmt, p.read(address, struct.calcsize(fmt)))
    def rect(component):
        return read(component + 0x38, '<4i')
    main = p.pointer(p.base + 0x5d1f260)
    if p.pointer(main) != p.base + 0x3818028:
        raise RuntimeError('Unknown MainComponent')
    player = p.pointer(p.pointer(main + 0x490) + 0xe0)
    if p.pointer(player) != p.base + 0x384ec68:
        raise RuntimeError('Unknown PlayerComponent')
    children = p.pointer(player + 0x58)
    count = p.unpack(player + 0x64, '<i')
    if not 0 < count < 100:
        raise RuntimeError('Invalid child count')
    panel = next(c for c in read(children, '<' + 'Q'*count) if p.pointer(c) == p.base + 0x384f080)
    sources = read(p.pointer(panel + 0x5a8), '<4Q')
    waves = read(panel + 0x3b8, '<2Q')
    pairs = []
    for wave in waves:
        renderer = p.pointer(wave + 0x168)
        mapping = read(renderer + 0x130, '<4Q')
        pairs.append(dict(bounds=rect(wave), sources=[sources.index(s)+1 if s in sources else 0 for s in mapping]))
    decks = []
    for i in range(4):
        widget = sources[i] + 0x648
        parent = p.pointer(widget + 0x30)
        decks.append(dict(deck=i+1, area=read(panel+0x5c8+i*16, '<4i'),
                          track_info=rect(p.pointer(panel+0x398+i*8)),
                          controls=rect(p.pointer(panel+0x438+i*8)),
                          active=rect(p.pointer(p.pointer(panel+0x640)+i*8)),
                          drop=rect(p.pointer(p.pointer(panel+0x650)+i*8)),
                          wave=rect(widget), wave_parent=waves.index(parent) if parent in waves else hex(parent)))
    result = dict(layout=p.unpack(panel+0x5b8, '<i'),
                  app_mode=p.unpack(p.pointer(main+0x428)+0x98, '<I'), pairs=pairs, decks=decks)
    for path, dll_base in modules(p):
        if path.name.lower() == 'rb_bpm_patch.dll':
            symbols = exports(path)
            if 'rbqLayoutTelemetry' in symbols:
                result['telemetry'] = read(dll_base+symbols['rbqLayoutTelemetry'], '<8I')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    args = parser.parse_args()
    p = Process(args.pid)
    try:
        print(json.dumps(snapshot(p), indent=2))
    finally:
        p.close()


if __name__ == '__main__':
    main()
