"""Controller for the build-pinned native tempo prototype (Windows x64).

Only install loads a DLL. All mutations are explicit exported control operations;
no thread is suspended, no executable instruction bytes are overwritten.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import hashlib
from pathlib import Path
import struct
import time

from observe_tempo import Process, ROOT, EXPECTED

MAGIC = 0x52425131
DLL = ROOT / 'build' / 'rb_bpm.dll'


def exports(path):
    """Read PE export RVAs without loading or executing a local DLL."""
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', data, pe+4)[0] != 0x8664:
        raise ValueError('Expected an x64 PE file')
    count = struct.unpack_from('<H', data, pe+6)[0]
    opt_size = struct.unpack_from('<H', data, pe+20)[0]
    opt = pe+24
    if struct.unpack_from('<H', data, opt)[0] != 0x20b:
        raise ValueError('Expected PE32+')
    sections = []
    for i in range(count):
        off = opt+opt_size+i*40
        size, rva, rawsize, raw = struct.unpack_from('<IIII', data, off+8)
        sections.append((rva, max(size, rawsize), raw))
    def offset(rva):
        for start, size, raw in sections:
            if start <= rva < start+size:
                return raw+rva-start
        raise ValueError('Export RVA is outside sections')
    export_rva, export_size = struct.unpack_from('<II', data, opt+112)
    directory = offset(export_rva)
    functions, names, ordinals = struct.unpack_from('<III', data, directory+28)
    name_count = struct.unpack_from('<I', data, directory+24)[0]
    result = {}
    for i in range(name_count):
        name_rva = struct.unpack_from('<I', data, offset(names)+i*4)[0]
        name_off = offset(name_rva)
        name = data[name_off:data.index(b'\0', name_off)].decode('ascii')
        ordinal = struct.unpack_from('<H', data, offset(ordinals)+i*2)[0]
        rva = struct.unpack_from('<I', data, offset(functions)+ordinal*4)[0]
        if export_rva <= rva < export_rva+export_size:
            raise ValueError('Forwarded exports are not supported')
        result[name] = rva
    return result


def modules(process):
    array = (W.HMODULE*2048)()
    needed = W.DWORD()
    if not process.p.EnumProcessModulesEx(process.handle, array, C.sizeof(array), C.byref(needed), 3):
        raise C.WinError(C.get_last_error())
    if needed.value > C.sizeof(array):
        raise RuntimeError('Module array exceeded')
    process.p.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
    result = []
    for base in array[:needed.value//C.sizeof(W.HMODULE)]:
        name = C.create_unicode_buffer(32768)
        if not process.p.GetModuleFileNameExW(process.handle, base, name, len(name)):
            raise C.WinError(C.get_last_error())
        result.append((Path(name.value), base))
    return result


class Remote(Process):
    def enable_control(self, pid):
        # Create thread, VM operation/write/read, query. No PROCESS_ALL_ACCESS.
        handle = self.k.OpenProcess(0x043a, False, pid)
        if not handle:
            raise C.WinError(C.get_last_error())
        self.close()
        self.handle = handle
        self.k.VirtualAllocEx.argtypes = [W.HANDLE, C.c_void_p, C.c_size_t, W.DWORD, W.DWORD]
        self.k.VirtualAllocEx.restype = C.c_void_p
        self.k.VirtualFreeEx.argtypes = [W.HANDLE, C.c_void_p, C.c_size_t, W.DWORD]
        self.k.WriteProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        self.k.CreateRemoteThread.argtypes = [W.HANDLE, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
        self.k.CreateRemoteThread.restype = W.HANDLE
        self.k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        self.k.GetExitCodeThread.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]

    def invoke(self, address, payload=b'', argument=None):
        if payload and argument is not None:
            raise ValueError('Use payload or direct argument, not both')
        allocation = None
        thread = None
        completed = False
        started = False
        try:
            if payload:
                allocation = self.k.VirtualAllocEx(self.handle, None, len(payload), 0x3000, 4)
                if not allocation:
                    raise C.WinError(C.get_last_error())
                written = C.c_size_t()
                buffer = C.create_string_buffer(payload)
                if not self.k.WriteProcessMemory(self.handle, allocation, buffer, len(payload), C.byref(written)) or written.value != len(payload):
                    raise C.WinError(C.get_last_error())
            thread = self.k.CreateRemoteThread(self.handle, None, 0, address, allocation if payload else argument, 0, None)
            if not thread:
                raise C.WinError(C.get_last_error())
            started = True
            wait = self.k.WaitForSingleObject(thread, 15000)
            if wait != 0:
                raise RuntimeError('Remote operation did not complete; parameter allocation retained for thread safety. Do not retry blindly.')
            completed = True
            code = W.DWORD()
            if not self.k.GetExitCodeThread(thread, C.byref(code)):
                raise C.WinError(C.get_last_error())
            return code.value
        finally:
            if thread:
                self.k.CloseHandle(thread)
            if allocation and (completed or not started):
                self.k.VirtualFreeEx(self.handle, allocation, 0, 0x8000)

    def load_dll(self, dll_path=DLL):
        # Resolve forwarded kernel32 exports to their actual owning module first.
        k = self.k
        k.GetModuleHandleW.argtypes = [W.LPCWSTR]
        k.GetModuleHandleW.restype = W.HMODULE
        k.GetProcAddress.argtypes = [W.HMODULE, C.c_char_p]
        k.GetProcAddress.restype = C.c_void_p
        k.GetModuleHandleExW.argtypes = [W.DWORD, C.c_void_p, C.POINTER(W.HMODULE)]
        k.GetModuleFileNameW.argtypes = [W.HMODULE, W.LPWSTR, W.DWORD]
        address = k.GetProcAddress(k.GetModuleHandleW('kernel32.dll'), b'LoadLibraryW')
        owner = W.HMODULE()
        if not address or not k.GetModuleHandleExW(6, address, C.byref(owner)):
            raise C.WinError(C.get_last_error())
        path = C.create_unicode_buffer(32768)
        if not k.GetModuleFileNameW(owner, path, len(path)):
            raise C.WinError(C.get_last_error())
        remote_modules = modules(self)
        matches = [base for name, base in remote_modules if name.name.lower() == Path(path.value).name.lower()]
        if len(matches) != 1:
            raise RuntimeError('Cannot uniquely resolve remote LoadLibraryW module')
        remote_address = matches[0]+address-owner.value
        # GetExitCodeThread truncates HMODULE to 32 bits; enumerate modules instead.
        self.invoke(remote_address, (str(dll_path.resolve())+'\0').encode('utf-16-le'))
        return find_dll(self, dll_path)


def find_dll(process, expected_path=DLL):
    candidates = [(path, base) for path, base in modules(process) if path.name.lower() == expected_path.name.lower()]
    if not candidates:
        return None
    if len(candidates) != 1 or candidates[0][0].resolve() != expected_path.resolve():
        raise RuntimeError('A different rb_bpm.dll is already loaded; restart Rekordbox')
    return candidates[0][1]


def status(process, base, symbols):
    if base is None:
        return {'loaded': False, 'installed': False}
    data = process.read(base+symbols['rbqTelemetry'], 40+8*64)
    magic, abi, installed, mode, calls, rejected, concurrent = struct.unpack_from('<IIIIQQQ', data)
    if magic != MAGIC or abi != 1:
        raise RuntimeError('Unsupported loaded DLL ABI')
    records = []
    for i in range(8):
        owner, count, changed, bypass, raw, output, bpm, target, thread, selected, grid = struct.unpack_from('<QQQQffffIIQ', data, 40+i*64)
        if owner:
            records.append(dict(owner=hex(owner), calls=count, quantized=changed, bypass=bypass,
                                input_delta=raw, output_delta=output, bpm=bpm, target_bpm=target,
                                thread=thread, mode=selected, grid=hex(grid)))
    return dict(loaded=True, installed=bool(installed), mode=mode, calls=calls,
                rejected=rejected, concurrent=concurrent, records=records)


def active_extension(process):
    candidates=[(path,base) for path,base in modules(process) if path.name.lower()=='rb_bpm_patch.dll']
    if candidates:
        if len(candidates)!=1 or candidates[0][0].parent.resolve()!=process.path.parent.resolve():
            raise RuntimeError('Unexpected permanent extension path')
        path,base=candidates[0]
        manifest=json.loads((ROOT/'build'/'permanent'/'rb-bpm.patch.json').read_text(encoding='utf-8'))
        if manifest.get('original_sha256')!=EXPECTED or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest.get('dll_sha256'):
            raise RuntimeError('Unsupported permanent extension checksum')
        return path,base,True
    return DLL,find_dll(process),False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('action', choices=['install', 'default', 'tenth', 'integer', 'status', 'stop'])
    args = parser.parse_args()
    process = Remote(args.pid)  # First validates exact host SHA-256 and loaded code.
    try:
        path,base,permanent = active_extension(process)
        symbols = exports(path)
        owners = []
        if args.action == 'install' and base is not None:
            if status(process, base, symbols)['installed']:
                raise RuntimeError('Hook is already installed; select Default, 0.1 or 1 instead')
            raise RuntimeError('This session already loaded the DLL. Restart Rekordbox before reinstalling the hook.')
        if args.action == 'install' and not status(process, base, symbols)['installed']:
            owners, _ = process.discover(10)
            if not owners or len(owners) > 8:
                raise RuntimeError('Expected one to eight validated player objects')
        if args.action != 'status':
            if permanent and args.action in ('install','stop'):
                raise RuntimeError('The permanent patch is already installed. Use Default to disable quantization or Patch-Rekordbox.ps1 -Action Restore to remove it.')
            process.enable_control(args.pid)
            if base is None:
                if args.action != 'install':
                    raise RuntimeError('Install the diagnostic hook first')
                base = process.load_dll()
                if base is None:
                    raise RuntimeError('LoadLibraryW did not load the expected DLL')
            selected = {'default':0, 'tenth':1, 'integer':2}.get(args.action, 0)
            payload = struct.pack('<II8Q', MAGIC, selected, *(owners+[0]*(8-len(owners))))
            function = {'install':'rbqInstall', 'stop':'rbqStop'}.get(args.action, 'rbqConfigure')
            if permanent:
                function='rbqSetPreference'
                payload=struct.pack('<I',selected)
            code = process.invoke(base+symbols[function], b'' if args.action == 'stop' else payload)
            if code:
                raise RuntimeError(f'{function} returned error {code}; read status before continuing')
        result = dict(time=time.time(), pid=args.pid, action=args.action, permanent=permanent,
                      **status(process, base, symbols))
        print(json.dumps(result, indent=2, allow_nan=False))
        artifact = ROOT/'artifacts'/'native-control.jsonl'
        artifact.parent.mkdir(exist_ok=True)
        with artifact.open('a', encoding='utf-8') as log:
            log.write(json.dumps(result, allow_nan=False)+'\n')
    finally:
        process.close()


if __name__ == '__main__':
    main()
