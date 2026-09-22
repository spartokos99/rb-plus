"""Windows x64 observation via query/read rights only; never injects or writes.

All offsets refer exclusively to the SHA-256 pinned build. Addresses are not deck
numbers. Beatgrid BPM and the live rate were confirmed for the prepared Deck 1.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import math
from pathlib import Path
import struct
import time

EXPECTED = 'a99896cf26d5998e6ad4177796a467b83df14bf8ae7207df21ed01251e402493'
ROOT = Path(__file__).resolve().parents[1]


class MBI(C.Structure):
    _fields_ = [('base',C.c_void_p), ('allocation_base',C.c_void_p),
                ('allocation_protect',W.DWORD), ('partition',W.WORD),
                ('size',C.c_size_t), ('state',W.DWORD),
                ('protect',W.DWORD), ('kind',W.DWORD)]


class Process:
    def __init__(self, pid):
        if C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('64-bit Python required')
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.p = C.WinDLL('psapi', use_last_error=True)
        self.k.OpenProcess.argtypes = [W.DWORD,W.BOOL,W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.k.ReadProcessMemory.argtypes = [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
        self.k.VirtualQueryEx.argtypes = [W.HANDLE,C.c_void_p,C.POINTER(MBI),C.c_size_t]
        self.k.VirtualQueryEx.restype = C.c_size_t
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        self.p.EnumProcessModulesEx.argtypes = [W.HANDLE,C.POINTER(W.HMODULE),W.DWORD,C.POINTER(W.DWORD),W.DWORD]
        # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. No write/operation/thread rights.
        self.handle = self.k.OpenProcess(0x0400 | 0x0010, False, pid)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        try:
            path = C.create_unicode_buffer(32768)
            size = W.DWORD(len(path))
            if not self.k.QueryFullProcessImageNameW(self.handle,0,path,C.byref(size)):
                raise C.WinError(C.get_last_error())
            self.path = Path(path.value)
            if self.path.name.lower() != 'rekordbox.exe':
                raise RuntimeError('PID is not rekordbox.exe')
            self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
            if self.sha256 != EXPECTED:
                manifest_path = ROOT/'build'/'permanent'/'rb-bpm.patch.json'
                manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
                if (manifest.get('format') != 1 or manifest.get('original_sha256') != EXPECTED or
                        manifest.get('patched_sha256') != self.sha256 or manifest.get('dll_name') != 'rb_bpm_patch.dll'):
                    raise RuntimeError('Unsupported executable SHA-256')
            modules = (W.HMODULE*1024)()
            needed = W.DWORD()
            if not self.p.EnumProcessModulesEx(self.handle,modules,C.sizeof(modules),C.byref(needed),3):
                raise C.WinError(C.get_last_error())
            self.base = modules[0]
            if self.read(self.base,2) != b'MZ':
                raise RuntimeError('Invalid image base')
            expected = bytes.fromhex('40534883ec30448b812c010000')
            if self.read(self.base+0x2c07bd0,len(expected)) != expected:
                raise RuntimeError('Loaded tempo function signature differs')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None

    def read(self, address, size):
        buf = C.create_string_buffer(size)
        got = C.c_size_t()
        if not self.k.ReadProcessMemory(self.handle,address,buf,size,C.byref(got)):
            raise OSError('ReadProcessMemory failed at '+hex(address))
        if got.value != size:
            raise OSError('Incomplete memory read')
        return buf.raw

    def unpack(self, address, fmt):
        return struct.unpack(fmt,self.read(address,struct.calcsize(fmt)))[0]

    def pointer(self, address):
        return self.unpack(address,'<Q')

    def grid_context(self, core):
        """Read the same beat entry layout/time conversion used by the native player.

        This is an observation, not a lifetime guarantee for a future in-process
        hook. Track/unload races must be rejected by callers.
        """
        state = self.pointer(core+0x220)
        if self.pointer(state) != self.base+0x55716a8:
            raise ValueError('Unexpected player state type')
        holder = self.pointer(state+0x28)
        client = self.pointer(state+0x30)
        result = {'playing':bool(self.unpack(state+0x10,'<B')),
                  'control_client':hex(client), 'grid':None, 'grid_bpm':None}
        if not holder:
            return result
        if self.pointer(holder) != self.base+0x37af8f8:
            raise ValueError('Unexpected beatgrid holder type')
        grid = self.pointer(holder+0x18)
        if self.pointer(grid) != self.base+0x5559ad0:
            raise ValueError('Unexpected formatted beatgrid type')
        start = self.pointer(grid+0x18)
        end = self.pointer(grid+0x20)
        if end<start or (end-start)%16 or not 0<(end-start)//16<=1_000_000:
            raise ValueError('Invalid beatgrid vector')
        count = (end-start)//16
        # The native getter at 0x1032900 uses this exact constant from the EXE.
        factor = self.unpack(self.base+0x5b52288,'<d')
        position_ms = math.ceil(self.unpack(state+0x14,'<i')*factor)
        lo,hi = 0,count
        while lo<hi:
            middle=(lo+hi)//2
            if self.unpack(start+middle*16+8,'<d')<position_ms:
                lo=middle+1
            else:
                hi=middle
        index=min(lo,count-1)
        if index>0 and self.unpack(start+index*16+8,'<d')>position_ms:
            index-=1
        bpm=self.unpack(start+index*16,'<f')
        if not math.isfinite(bpm) or not 0<bpm<1000:
            raise ValueError('Invalid beatgrid BPM')
        # Reject a detected replacement/unload during the multi-read snapshot.
        if self.pointer(core+0x220)!=state or self.pointer(state+0x28)!=holder or self.pointer(holder+0x18)!=grid:
            raise ValueError('Beatgrid changed during observation')
        result.update(grid=hex(grid),grid_bpm=bpm)
        return result

    def snapshot(self, owner):
        if self.pointer(owner) != self.base+0x555c620:
            raise ValueError('Stale StretchBehavior object')
        if self.unpack(owner+0x130,'<I') != 0x5e715e28:
            raise ValueError('Invalid object marker')
        core = self.pointer(owner+0x48)
        if self.pointer(core) != self.base+0x556fb28:
            raise ValueError('Object does not own DjPlayerCore')
        pitch = self.unpack(owner+0xec,'<f')
        bend = self.unpack(owner+0xf0,'<f')
        candidate = self.unpack(core+0x218,'<d')
        if not all(math.isfinite(v) for v in [pitch,bend,candidate]):
            raise ValueError('Non-finite state')
        parts = []
        dsp = self.pointer(core+0x2c0)
        count = self.unpack(dsp+0x74,'<i')
        if not 0 <= count <= 16:
            raise ValueError('Unexpected part count')
        array = self.pointer(dsp+0x68)
        for i in range(count):
            part = self.pointer(array+i*8)
            if part:
                value = self.unpack(part+0x30,'<d')
                parts.append(value if math.isfinite(value) else None)
        grid = self.grid_context(core)
        bpm = grid['grid_bpm']
        return {'owner':hex(owner),'core':hex(core),'pitch_delta':pitch,
                'bend_delta':bend,'nominal_rate_without_bend':1.0+pitch,
                'unverified_core_218':candidate,'audio_part_rates':parts,
                **grid, 'nominal_bpm':None if bpm is None else bpm*(1.0+pitch),
                'audio_part_bpms':None if bpm is None else [None if v is None else bpm*v for v in parts]}

    def discover(self, seconds):
        """Bounded external scan. Candidate snapshots validate vtables/markers."""
        pattern = struct.pack('<Q',self.base+0x555c620)
        deadline = time.monotonic()+seconds
        address = 0
        found = set()
        scanned = 0
        while time.monotonic()<deadline:
            region = MBI()
            if not self.k.VirtualQueryEx(self.handle,address,C.byref(region),C.sizeof(region)):
                break
            end = (region.base or 0)+region.size
            if end<=address:
                break
            # Only committed private memory with ordinary read/write protection.
            if region.state==0x1000 and region.kind==0x20000 and region.protect in (4,8):
                for start in range(region.base,end,1024*1024):
                    if time.monotonic()>=deadline:
                        break
                    size = min(1024*1024+7,end-start)
                    try:
                        data = self.read(start,size)
                    except OSError:
                        continue
                    scanned += size
                    pos = data.find(pattern)
                    while pos>=0:
                        ptr = start+pos
                        if ptr%8==0:
                            try:
                                self.snapshot(ptr)
                                found.add(ptr)
                            except (OSError,ValueError):
                                pass
                        pos = data.find(pattern,pos+1)
            address = end
        return sorted(found), scanned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--seconds',type=float,default=180)
    parser.add_argument('--scan-seconds',type=float,default=10)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts'/'observation.jsonl')
    args = parser.parse_args()
    if args.seconds<=0 or not 0<args.scan_seconds<=60:
        parser.error('Positive duration and scan-seconds in (0,60] required')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    process = Process(args.pid)
    try:
        with args.output.open('x',encoding='utf-8') as log:
            def emit(kind, **data):
                row = {'type':kind,'time':time.time(),**data}
                text = json.dumps(row,allow_nan=False)
                log.write(text+'\n')
                log.flush()
                print(text,flush=True)
            emit('identity',pid=args.pid,path=str(process.path),sha256=process.sha256,base=hex(process.base))
            owners,scanned = process.discover(args.scan_seconds)
            emit('ready',owners=[hex(p) for p in owners],scanned_bytes=scanned,
                 note='Object IDs are not deck numbers. core+0x218 is unverified.')
            if not owners:
                raise RuntimeError('No validated player objects found; load PERFORMANCE mode and retry')
            previous = {}
            end = time.monotonic()+args.seconds
            while time.monotonic()<end:
                for owner in owners:
                    try:
                        state = process.snapshot(owner)
                        if previous.get(owner)!=state:
                            emit('state',**state)
                            previous[owner]=state
                    except (OSError,ValueError) as error:
                        emit('unavailable',owner=hex(owner),reason=str(error))
                        owners.remove(owner)
                        break
                if not owners:
                    break
                time.sleep(0.05)
            emit('stopped')
    finally:
        process.close()


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Observation stopped.')
