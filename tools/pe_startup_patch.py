"""Add an explicit rb-bpm startup import and entry-point call to an x64 PE.

Keeps every original section RVA and instruction unchanged. Adds separate code
and data sections; moves import/exception directories to the payload. The caller
must pin the source hash. No signature bypass: the invalidated certificate
directory is removed and the modified executable is explicitly unsigned.
"""
import struct


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def patch_image(original, dll_name=b'rb_bpm_patch.dll', export_name=b'rbqBootstrap'):
    data = bytearray(original)
    def u16(off): return struct.unpack_from('<H', data, off)[0]
    def u32(off): return struct.unpack_from('<I', data, off)[0]
    def put(off, value): struct.pack_into('<I', data, off, value)
    pe = u32(0x3c)
    if data[:2] != b'MZ' or data[pe:pe+4] != b'PE\0\0' or u16(pe+4) != 0x8664:
        raise ValueError('Expected x64 PE')
    opt = pe + 24
    if u16(opt) != 0x20b or u32(opt+108) < 16:
        raise ValueError('Expected PE32+ with standard data directories')
    if u32(pe+12) or u32(pe+16):
        raise ValueError('COFF symbol table is unsupported')
    count, opt_size = u16(pe+6), u16(pe+20)
    sections = []
    for index in range(count):
        off = opt+opt_size+index*40
        size, rva, raw_size, raw = struct.unpack_from('<4I', data, off+8)
        sections.append(dict(off=off, size=size, rva=rva, raw_size=raw_size, raw=raw, flags=u32(off+36)))
    if not sections: raise ValueError('Missing sections')
    last = sections[-1]
    if last['rva'] != max(s['rva'] for s in sections) or last['raw'] != max(s['raw'] for s in sections):
        raise ValueError('Last section is not last in both file and image')
    def offset(rva, size=1):
        for s in sections:
            relative = rva-s['rva']
            if relative >= 0 and relative+size <= s['raw_size']:
                result = s['raw']+relative
                if result+size <= len(original): return result
        raise ValueError('RVA outside original raw sections')
    def directory(index): return struct.unpack_from('<II', data, opt+112+8*index)
    entry = u32(opt+16)
    section_alignment, file_alignment = u32(opt+32), u32(opt+36)
    if not file_alignment or not section_alignment or file_alignment > section_alignment:
        raise ValueError('Invalid PE alignment')
    old_import, old_import_size = directory(1)
    import_start = offset(old_import, old_import_size)
    descriptors = []
    for pos in range(import_start, import_start+old_import_size, 20):
        row = bytes(data[pos:pos+20])
        if len(row) != 20: raise ValueError('Truncated import descriptor')
        if row == bytes(20): break
        ilt, timestamp, forwarder, name, iat = struct.unpack('<5I', row)
        if not ilt or timestamp: raise ValueError('Bound/original-thunk-less imports unsupported')
        descriptors.append(row)
    else: raise ValueError('Import directory lacks terminator')
    old_exception, exception_size = directory(3)
    if exception_size % 12: raise ValueError('Invalid x64 exception directory')
    exception_start = offset(old_exception, exception_size)
    exceptions = bytes(data[exception_start:exception_start+exception_size])
    # Reserve two headers; this build's original section table fills SizeOfHeaders.
    # Shift raw file offsets only. Section RVAs and image-relative data stay intact.
    old_headers = u32(opt+60)
    new_headers = align(max(old_headers+file_alignment,opt+opt_size+(count+2)*40),file_alignment)
    if new_headers > min(s['rva'] for s in sections):
        raise ValueError('Expanded headers would overlap first image section')
    shift = max(0,new_headers-old_headers)
    debug_rva, debug_size = directory(6)
    debug_adjustments = []
    if debug_size:
        if debug_size % 28: raise ValueError('Invalid debug directory')
        start = offset(debug_rva,debug_size)
        for pos in range(start,start+debug_size,28):
            pointer = u32(pos+24)
            if pointer: debug_adjustments.append((pos+24,pointer))
    if shift:
        if any(s['raw'] and s['raw'] < old_headers for s in sections):
            raise ValueError('Section overlaps headers')
        data[old_headers:old_headers] = bytes(shift)
        put(opt+60,old_headers+shift)
        for s in sections:
            if s['raw']: put(s['off']+20,s['raw']+shift)
            for field in (24,28):
                pointer=u32(s['off']+field)
                if pointer: put(s['off']+field,pointer+shift)
        for off,pointer in debug_adjustments: put(off+shift,pointer+shift)
    code_rva = align(u32(opt+56),section_alignment)
    payload_rva = code_rva+section_alignment
    code_raw = align(len(data),file_alignment)
    payload_raw = code_raw+file_alignment
    payload = bytearray()
    def reserve(size, alignment=8):
        start = align(len(payload),alignment)
        payload.extend(bytes(start+size-len(payload)))
        return start
    unwind = reserve(8,4)
    imports = reserve((len(descriptors)+2)*20,8)
    ilt = reserve(16)
    iat = reserve(16)
    hint_name = reserve(2+len(export_name)+1,2)
    name = reserve(len(dll_name)+1,1)
    runtime = reserve(len(exceptions)+12,4)
    rva = lambda off: payload_rva+off
    # x64: 32-byte shadow space + alignment, call imported bootstrap, original CRT entry.
    code = b'\x48\x83\xec\x28\xff\x15'+struct.pack('<i',rva(iat)-(code_rva+10))
    code += b'\x48\x83\xc4\x28\xe9'+struct.pack('<i',entry-(code_rva+19))
    # Version 1, prolog 4, one UWOP_ALLOC_SMALL(40) at prolog offset 4.
    payload[unwind:unwind+8] = bytes.fromhex('0104010004420000')
    for index, row in enumerate(descriptors): payload[imports+index*20:imports+(index+1)*20] = row
    struct.pack_into('<5I',payload,imports+len(descriptors)*20,rva(ilt),0,0,rva(name),rva(iat))
    struct.pack_into('<Q',payload,ilt,rva(hint_name))
    struct.pack_into('<Q',payload,iat,rva(hint_name))
    payload[hint_name+2:hint_name+2+len(export_name)] = export_name
    payload[name:name+len(dll_name)] = dll_name
    if exceptions and max(row[0] for row in struct.iter_unpack('<III',exceptions)) >= code_rva:
        raise ValueError('New runtime function would not be last')
    payload[runtime:runtime+len(exceptions)] = exceptions
    struct.pack_into('<III',payload,runtime+len(exceptions),code_rva,code_rva+19,rva(unwind))
    raw_end = align(payload_raw+len(payload),file_alignment)
    data.extend(bytes(raw_end-len(data)))
    data[code_raw:code_raw+len(code)] = code
    data[payload_raw:payload_raw+len(payload)] = payload
    headers=opt+opt_size+count*40
    struct.pack_into('<8sIIIIIIHHI',data,headers,b'.rbq',len(code),code_rva,file_alignment,code_raw,0,0,0,0,0x60000020)
    struct.pack_into('<8sIIIIIIHHI',data,headers+40,b'.rbqdat',len(payload),payload_rva,raw_end-payload_raw,payload_raw,0,0,0,0,0xc0000040)
    struct.pack_into('<H',data,pe+6,count+2)
    put(opt+16,code_rva)
    put(opt+56,align(payload_rva+len(payload),section_alignment))
    put(opt+4,u32(opt+4)+file_alignment)
    put(opt+8,u32(opt+8)+raw_end-payload_raw)
    for index, address, size in [(1,rva(imports),(len(descriptors)+2)*20),
                                 (3,rva(runtime),len(exceptions)+12),(4,0,0),(11,0,0)]:
        struct.pack_into('<II',data,opt+112+8*index,address,size)
    # Optional PE checksum; ImageHlp's algorithm is a folded 16-bit sum + file size.
    put(opt+64,0)
    checksum = sum(value[0] for value in struct.iter_unpack('<H',data))
    while checksum >> 16: checksum = (checksum & 0xffff)+(checksum >> 16)
    put(opt+64,(checksum+len(data)) & 0xffffffff)
    return bytes(data), dict(original_entry=hex(entry),patched_entry=hex(code_rva),header_shift=shift,
                             payload_rva=hex(payload_rva),payload_raw=payload_raw,
                             added_import=dll_name.decode(),certificate_removed=True)
