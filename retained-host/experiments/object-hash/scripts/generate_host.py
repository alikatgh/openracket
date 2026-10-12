#!/usr/bin/env python3
"""Exact, tiny derivatives of the accepted retained host and workflow."""
import argparse, hashlib, json
from pathlib import Path
from generate import once, ROOT
HOST='tests/reference-host-0520.rkt'
WORKFLOW='tests/independent-native-workflows.rkt'
HOST_ANCHOR=b'''                 ((dynamic-require follow-on-module 'run-follow-on-check!)
                  frame (string->symbol follow-on-case))'''
HOST_REPLACEMENT=b'''                 ((dynamic-require "../host-probe.rkt" 'run-probed-follow-on-check!)
                  (dynamic-require follow-on-module 'run-follow-on-check!)
                  frame (string->symbol follow-on-case))'''
# Use a runtime path, because dynamic-require a string otherwise follows cwd.
PATH_ANCHOR=b'(define-runtime-path follow-on-module "independent-native-workflows.rkt")'
PATH_ADDITION=PATH_ANCHOR+b'\n(define-runtime-path hash-probe-module "../host-probe.rkt")'
HOST_REPLACEMENT=HOST_REPLACEMENT.replace(b'"../host-probe.rkt"',b'hash-probe-module')
ARM_ANCHOR=b'''     (await! "Check Syntax enabled" (lambda () (send button is-enabled?)))
     (send button command)'''
ARM_REPLACEMENT=ARM_ANCHOR.replace(b'     (send button command)',b'     (probe-begin! frame defs ints)\n     (send button command)')
END_ANCHOR=b'''                                                  (positive? (hash-count (send defs syncheck:get-bindings-table))))))
     (check-false (send frame syncheck:error-report-visible?))'''
END_REPLACEMENT=END_ANCHOR.replace(b'     (check-false',b'     (probe-end!)\n     (check-false')
REQUIRE_ANCHOR=b'         string-constants rackunit)'
REQUIRE_REPLACEMENT=b'         string-constants rackunit "../host-probe.rkt")'

def derivatives():
    source=ROOT/'vendor/host'; pins=json.loads((ROOT/'vendor/host-pins.json').read_text())
    expected={str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}
    if set(pins)!=expected: raise ValueError('host source closure mismatch')
    result={}
    for name,pin in pins.items():
        data=(source/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=pin: raise ValueError('host source pin drift')
        if name==HOST:
            data=once(data,PATH_ANCHOR,PATH_ADDITION)
            data=once(data,HOST_ANCHOR,HOST_REPLACEMENT)
        elif name==WORKFLOW:
            data=once(data,REQUIRE_ANCHOR,REQUIRE_REPLACEMENT)
            data=once(data,ARM_ANCHOR,ARM_REPLACEMENT)
            data=once(data,END_ANCHOR,END_REPLACEMENT)
        result[name]=data
    return result

def restore_host(name,data):
    if name==HOST:
        return once(once(data,HOST_REPLACEMENT,HOST_ANCHOR),PATH_ADDITION,PATH_ANCHOR)
    if name==WORKFLOW:
        return once(once(once(data,END_REPLACEMENT,END_ANCHOR),ARM_REPLACEMENT,ARM_ANCHOR),REQUIRE_REPLACEMENT,REQUIRE_ANCHOR)
    return data

def generate(check=False):
    result=derivatives()
    for name,data in result.items():
        if restore_host(name,data)!=(ROOT/'vendor/host'/name).read_bytes():raise AssertionError('host not reversible')
        out=ROOT/'native'/name
        if check:
            if out.read_bytes()!=data:raise ValueError('generated host drift')
        else:
            out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    return {'derivatives':[HOST,WORKFLOW],'unchanged_dependencies':len(result)-2,'native_run':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    print(json.dumps(generate(a.check),indent=2))
