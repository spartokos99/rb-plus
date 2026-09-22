"""Read-only PE/RTTI inspection for the locally installed executable."""
import argparse
import bisect
import hashlib
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.tools' / 'python'))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64


class Binary:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        self.pe = pefile.PE(data=self.data, fast_load=True)
        self.pe.parse_data_directories(directories=[3, 6])
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.functions = sorted((e.struct.BeginAddress, e.struct.EndAddress)
                                for e in self.pe.DIRECTORY_ENTRY_EXCEPTION)
        self.starts = [a for a, b in self.functions]

    def rva(self, offset):
        return self.pe.get_rva_from_offset(offset)

    def offset(self, rva):
        return self.pe.get_offset_from_rva(rva)

    def find(self, value):
        return [m.start() for m in re.finditer(re.escape(value), self.data)]

    def function(self, rva):
        i = bisect.bisect_right(self.starts, rva) - 1
        if i >= 0 and self.functions[i][0] <= rva < self.functions[i][1]:
            return self.functions[i]
        return rva, rva + 96

    def disasm(self, rva, size=None):
        if size is None:
            rva, end = self.function(rva)
            size = end - rva
        off = self.offset(rva)
        for i in self.md.disasm(self.data[off:off+size], self.base+rva):
            print(f'{i.address-self.base:08x}  {i.bytes.hex():24} {i.mnemonic:8} {i.op_str}')

    def rtti(self, pattern):
        for m in re.finditer(rb'\.\?A[UV][ -~]+?\x00', self.data):
            name = m.group()[:-1].decode('ascii')
            if not re.search(pattern, name, re.I):
                continue
            td = self.rva(m.start()-16)
            print(f'RTTI {td:#x} {name}')
            for ref in self.find(struct.pack('<I', td)):
                col = ref-12
                if col < 0:
                    continue
                sig, adj, cd, typ, hier, self_rva = struct.unpack_from('<6I', self.data, col)
                if sig != 1 or self_rva != self.rva(col):
                    continue
                for v in self.find(struct.pack('<Q', self.base+self_rva)):
                    vt = self.rva(v+8)
                    funcs = []
                    for j in range(24):
                        addr = struct.unpack_from('<Q', self.data, v+8+j*8)[0]-self.base
                        if not (0x1000 <= addr < 0x3600000):
                            break
                        funcs.append(f'{j}:{addr:x}')
                    print(f'  vtable={vt:#x} this_adjust={adj:#x} '+ ' '.join(funcs))

    def xrefs(self, target):
        """Find RIP-relative references/calls, validating candidate instruction decodes."""
        for sec in self.pe.sections:
            if not sec.Characteristics & 0x20000000:
                continue
            data = sec.get_data()
            for m in re.finditer(rb'[\xe8\xe9]|[\x48\x4c][\x8d\x8b\x89]', data):
                pos = m.start()
                n = 5 if data[pos] in (0xe8,0xe9) else 7
                if pos+n > len(data):
                    continue
                rel = struct.unpack_from('<i', data, pos+n-4)[0]
                rva = sec.VirtualAddress+pos
                if rva+n+rel == target:
                    self.disasm(rva, n)
                    print('  containing function:', hex(self.function(rva)[0]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--exe', default=r'D:\Programs\rekordbox 7.2.18\rekordbox.exe')
    p.add_argument('--rtti')
    p.add_argument('--disasm', type=lambda x:int(x,0))
    p.add_argument('--size', type=lambda x:int(x,0))
    p.add_argument('--xrefs', type=lambda x:int(x,0))
    p.add_argument('--strings')
    args = p.parse_args()
    b = Binary(args.exe)
    if args.rtti:
        b.rtti(args.rtti)
    elif args.disasm is not None:
        b.disasm(args.disasm,args.size)
    elif args.xrefs is not None:
        b.xrefs(args.xrefs)
    elif args.strings:
        for m in re.finditer(rb'[ -~]{6,}', b.data):
            s = m.group().decode('ascii')
            if re.search(args.strings,s,re.I):
                print(hex(b.rva(m.start())),s)
    else:
        print('SHA256',hashlib.sha256(b.data).hexdigest())
        print('ImageBase',hex(b.base))
        for s in b.pe.sections:
            print(s.Name,hex(s.VirtualAddress),hex(s.Misc_VirtualSize))
        for e in getattr(b.pe,'DIRECTORY_ENTRY_DEBUG',[]):
            print(e.entry)


if __name__ == '__main__':
    main()
