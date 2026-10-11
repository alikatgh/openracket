#!/usr/bin/env python3
"""Reconstruct and verify bounded readable replay evidence from a GitHub job log."""
import hashlib,json,pathlib,re,sys

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def decode(log,output):
    active={};written=[]
    for raw in log.splitlines():
        line=re.sub(r'^\ufeff?(?:\d{4}-\d\d-\d\dT\S+\s+)?','',raw)
        match=re.search(r'OPENRACKET_REPLAY_(DOCUMENT_BEGIN|DOCUMENT_JSON|ARRAY_JSON|DOCUMENT_END) (\{.*\})$',line)
        if not match:continue
        kind,data=match.group(1),json.loads(match.group(2));label=data['label']
        assert re.fullmatch(r'[a-z0-9_-]+',label),label
        if kind=='DOCUMENT_BEGIN':
            assert label not in active,'Repeated begin without end';active[label]={'header':data,'arrays':{},'data':None}
        else:
            state=active[label]
            if kind=='DOCUMENT_JSON':assert state['data'] is None;state['data']=data['data']
            elif kind=='ARRAY_JSON':
                rows=state['arrays'].setdefault(data['id'],[]);assert data['index']==len(rows),'Missing/reordered array chunk';rows.extend(data['items'])
            else:
                seen=set()
                def restore(value):
                    if isinstance(value,dict):
                        if '__openracket_log_array__' in value:
                            ident=value['__openracket_log_array__'];assert ident not in seen;seen.add(ident);items=[restore(v) for v in state['arrays'][ident]]
                            assert len(items)==value['length'] and hashlib.sha256(packed(items).encode()).hexdigest()==value['sha256']
                            return items
                        return {k:restore(v) for k,v in value.items()}
                    if isinstance(value,list):return [restore(v) for v in value]
                    return value
                document=restore(state['data']);assert len(seen)==state['header']['arrays']==len(state['arrays'])
                digest=hashlib.sha256(packed(document).encode()).hexdigest();assert digest==state['header']['sha256'],'Whole-document hash mismatch'
                output.mkdir(parents=True,exist_ok=True);path=output/(label+'.json')
                if path.exists() and json.loads(path.read_text())!=document:path=output/(label+'-'+digest[:12]+'.json')
                path.write_text(json.dumps(document,indent=2)+'\n');written.append({'label':label,'path':str(path),'canonical_sha256':digest});del active[label]
    assert not active,'Truncated evidence document(s): '+str(list(active))
    return written
if __name__=='__main__':
    print(json.dumps(decode(pathlib.Path(sys.argv[1]).read_text(),pathlib.Path(sys.argv[2])),indent=2))
