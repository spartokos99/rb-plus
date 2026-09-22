"""Read-only, bounded inspection of player pointer graphs; logs numeric matches only."""
import argparse
from collections import deque
import json
import struct

from observe_tempo import Process


def type_name(process, address):
    try:
        vt = process.pointer(address)
        if not process.base <= vt < process.base+0x6000000:
            return None
        col = process.pointer(vt-8)
        if not process.base <= col < process.base+0x6000000:
            return None
        header = process.read(col,24)
        sig,offset,cd,td,chd,self_rva = struct.unpack('<6I',header)
        if sig!=1 or self_rva!=col-process.base:
            return None
        name = process.read(process.base+td+16,256).split(b'\0',1)[0]
        return name.decode('ascii') if name.startswith(b'.?A') else None
    except (OSError,UnicodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--root',type=lambda v:int(v,0),required=True)
    parser.add_argument('--bpm',type=float,required=True)
    parser.add_argument('--depth',type=int,default=2)
    parser.add_argument('--nodes',type=int,default=200)
    args=parser.parse_args()
    if not 0<=args.depth<=3 or not 1<=args.nodes<=500:
        parser.error('depth must be 0..3 and nodes 1..500')
    p=Process(args.pid)
    try:
        queue=deque([(args.root,'root',0)])
        visited=set()
        patterns={fmt:struct.pack(fmt,args.bpm if fmt!='<I' else round(args.bpm*100))
                  for fmt in ['<f','<d','<I']}
        while queue and len(visited)<args.nodes:
            address,path,depth=queue.popleft()
            if address in visited:
                continue
            visited.add(address)
            try:
                data=p.read(address,0x400)
            except OSError:
                continue
            name=type_name(p,address)
            hits=[]
            for fmt,pattern in patterns.items():
                start=0
                while (offset:=data.find(pattern,start))>=0:
                    if offset%4==0:
                        hits.append({'offset':hex(offset),'format':fmt})
                    start=offset+1
            if name or hits or depth==0:
                print(json.dumps({'address':hex(address),'path':path,'type':name,'bpm_hits':hits}),flush=True)
            if depth<args.depth:
                for offset in range(0,0x400,8):
                    ptr=struct.unpack_from('<Q',data,offset)[0]
                    if 0x10000<=ptr<0x700000000000 and ptr%8==0 and ptr not in visited:
                        queue.append((ptr,path+'->'+hex(offset),depth+1))
        print(json.dumps({'visited':len(visited),'remaining':len(queue)}))
    finally:
        p.close()


if __name__=='__main__':
    main()
