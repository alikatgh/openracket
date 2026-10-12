#!/usr/bin/env python3
"""Generate/check source pins. Never asserts native readiness."""
import argparse,json,re
from generate import ROOT,sha,generate
from generate_host import generate as generate_host
from generate_native_forms import generate as generate_native_forms
RUNTIME_BASE=ROOT/'vendor/runtime-pins-reference.json'

def generate_pins(check=False):
    generate(True);generate_host(True);generate_native_forms(True)
    runtime=json.loads(RUNTIME_BASE.read_text())
    runtime['racket/snip/private/style']=runtime['racket/snip/private/style']['stock']
    runtime['racket/private/class-internal']=sha((ROOT/'generated/class-internal.rkt').read_bytes())
    runtime_bytes=(json.dumps(runtime,indent=2)+'\n').encode()
    runtime_path=ROOT/'RUNTIME-PINS.json'
    if check:
        if runtime_path.read_bytes()!=runtime_bytes:raise ValueError('runtime pins drift')
    else:runtime_path.write_bytes(runtime_bytes)
    files={str(p.relative_to(ROOT)):sha(p.read_bytes()) for directory in ('native','vendor','templates','scripts','generated','tests')
           for p in sorted((ROOT/directory).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    files['RUNTIME-PINS.json']=sha(runtime_bytes)
    for name in ('README.md','SOURCE-REVIEW.md'):
        files[name]=sha((ROOT/name).read_bytes())
    match=re.search(rb'\(define openracket-object-hash-probe-build-id "([0-9a-f]{64})"\)',(ROOT/'generated/class-internal.rkt').read_bytes())
    pins={'schema':'openracket-object-hash-source-pins/v1','build_id':match.group(1).decode(),'files':files,'native_run':False}
    data=(json.dumps(pins,indent=2)+'\n').encode();out=ROOT/'SOURCE-PINS.json'
    if check:
        if out.read_bytes()!=data:raise ValueError('package source closure/digest drift')
    else:out.write_bytes(data)
    return pins
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    result=generate_pins(a.check);print(json.dumps({'files':len(result['files']),'build_id':result['build_id'],'native_run':False},indent=2))
