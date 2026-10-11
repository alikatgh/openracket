#!/usr/bin/env python3
"""Lossless byte-bounded JSON log chunks; never serialized source requests."""
import hashlib,json,pathlib,re,sys
ALLOWED={'capture-summary.json','capture-host.json','capture-supervisor.json','replay.json','supervisor.json','trace.json','measurements.json','summary.json','worker-init.json','worker-init-overhead.json','memory-profile.json','acceptance.json','gui-observation.json','worker-phase-1.json','activation.json','heartbeat.json','docs-map.json','ready.json'}
LINE_LIMIT=60000
ARRAY_LIMIT=4096
ROW_LIMIT=45000

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(value):return hashlib.sha256(packed(value).encode()).hexdigest()
def encode(value):
    chunks=[]
    def walk(node,path):
        if isinstance(node,dict):
            assert '__openracket_log_array__' not in node,'Reserved transport key in evidence'
            return {k:walk(v,path+[k]) for k,v in node.items()}
        if isinstance(node,list):
            # Recurse first so a trial containing large nested arrays is bounded too.
            items=[walk(v,path+[i]) for i,v in enumerate(node)]
            if len(items)>40 or len(packed(items).encode())>ARRAY_LIMIT:
                ident=len(chunks);rows=[];index=0;batch=[]
                for item in items:
                    proposed={'id':ident,'index':index,'items':batch+[item]}
                    if batch and (len(batch)==20 or len(packed(proposed).encode())>ROW_LIMIT):
                        rows.append({'id':ident,'index':index,'items':batch});index+=len(batch);batch=[]
                    batch.append(item)
                    assert len(packed({'id':ident,'index':index,'items':batch}).encode())<=ROW_LIMIT,'Single evidence item exceeds readable line bound'
                if batch:rows.append({'id':ident,'index':index,'items':batch})
                checksum=digest(node)
                chunks.append({'id':ident,'path':path,'length':len(node),'sha256':checksum,'rows':rows})
                return {'__openracket_log_array__':ident,'length':len(node),'sha256':checksum}
            return items
        return node
    skeleton=walk(value,[])
    assert len(packed(skeleton).encode())<ROW_LIMIT,'Evidence skeleton exceeds line bound'
    return skeleton,chunks

def emit(path):
    assert path.name in ALLOWED and path.is_file() and not path.is_symlink()
    raw=path.read_bytes();assert len(raw)<=24*1024*1024,'Bounded diagnostic JSON exceeds24MiB'
    value=json.loads(raw);skeleton,chunks=encode(value)
    label=path.parent.name+'-'+path.stem
    assert re.fullmatch(r'[a-z0-9_-]{1,128}',label),'Invalid evidence label'
    lines=[]
    def line(marker,data):
        out=marker+' '+packed(data)
        assert len(out.encode())<LINE_LIMIT,'Complete evidence log line exceeds bound'
        lines.append(out)
    line('OPENRACKET_REPLAY_DOCUMENT_BEGIN',{'label':label,'sha256':digest(value),'arrays':len(chunks)})
    line('OPENRACKET_REPLAY_DOCUMENT_JSON',{'label':label,'data':skeleton})
    for chunk in chunks:
        for row in chunk['rows']:line('OPENRACKET_REPLAY_ARRAY_JSON',{'label':label,**row})
    line('OPENRACKET_REPLAY_DOCUMENT_END',{'label':label})
    for out in lines:print(out,flush=True)
if __name__=='__main__':
    for arg in sys.argv[1:]:emit(pathlib.Path(arg))
