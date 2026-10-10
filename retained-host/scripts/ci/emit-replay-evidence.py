#!/usr/bin/env python3
"""Lossless bounded JSON evidence in readable log chunks; never serialized requests."""
import hashlib,json,pathlib,sys
ALLOWED={'capture-summary.json','capture-host.json','capture-supervisor.json','replay.json','supervisor.json'}

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def encode(value):
    chunks=[]
    def walk(node,path):
        if isinstance(node,dict):return {k:walk(v,path+[k]) for k,v in node.items()}
        if isinstance(node,list):
            if len(node)>40:
                ident=len(chunks);body=packed(node)
                rows=[{'id':ident,'index':i,'items':node[i:i+20]} for i in range(0,len(node),20)]
                assert all(len(packed(row))<60000 for row in rows),'Evidence row exceeds readable line bound'
                chunks.append({'id':ident,'path':path,'length':len(node),'sha256':hashlib.sha256(body.encode()).hexdigest(),'rows':rows})
                return {'__openracket_log_array__':ident,'length':len(node),'sha256':hashlib.sha256(body.encode()).hexdigest()}
            return [walk(v,path+[i]) for i,v in enumerate(node)]
        return node
    skeleton=walk(value,[])
    assert len(packed(skeleton))<60000,'Evidence skeleton exceeds line bound'
    return skeleton,chunks

def emit(path):
    assert path.name in ALLOWED and path.is_file() and not path.is_symlink()
    raw=path.read_bytes();assert len(raw)<=6*1024*1024,'Bounded diagnostic JSON exceeds6MiB'
    value=json.loads(raw);skeleton,chunks=encode(value)
    label=path.parent.name+'-'+path.stem
    print('OPENRACKET_REPLAY_DOCUMENT_BEGIN '+packed({'label':label,'sha256':hashlib.sha256(packed(value).encode()).hexdigest(),'arrays':len(chunks)}),flush=True)
    print('OPENRACKET_REPLAY_DOCUMENT_JSON '+packed({'label':label,'data':skeleton}),flush=True)
    for chunk in chunks:
        for row in chunk['rows']:print('OPENRACKET_REPLAY_ARRAY_JSON '+packed({'label':label,**row}),flush=True)
    print('OPENRACKET_REPLAY_DOCUMENT_END '+packed({'label':label}),flush=True)
if __name__=='__main__':
    for arg in sys.argv[1:]:emit(pathlib.Path(arg))
