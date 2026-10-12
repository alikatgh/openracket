#!/usr/bin/env python3
"""Mechanical reference/fault forms; actual native execution remains pending."""
import argparse,json
from generate import ROOT,ORIGINAL_HELPER,ORIGINAL_HASH,support,once

def forms():
    helper=once(ORIGINAL_HELPER,b'(define (inspectable-struct->vector v)',b'(lambda (v)')
    body=ORIGINAL_HASH.split(b'\n',1)[1][:-1]
    reference=b'(let ([inspectable-struct->vector '+helper+b'])\n  (lambda (obj recur)\n'+body+b'))\n'
    text=support()
    start=text.index(b'(define (probe-note-vector! category length)')
    end=text.index(b'\n(define (probe-note-result!',start)
    observer=once(text[start:end],b'(define (probe-note-vector! category length)',b'(lambda (category length)')
    # The predicate, diagnostic failure handler, and complete scalar update body
    # remain exact; the controlled injection is inside that observer-only handler.
    injection=b'    ;; Only length is observed;'
    observer=once(observer,injection,b'    (raise probe-test-fault)\n'+injection)
    faulty=b'(lambda (probe-test-fault)\n'+observer+b')\n'
    return {'original-reference.rktd':reference,'observer-fault-form.rktd':faulty}

def generate(check=False):
    for name,data in forms().items():
        p=ROOT/'native'/name
        if check:
            if p.read_bytes()!=data:raise ValueError('native form drift')
        else:p.write_bytes(data)
    return {'actual_source_forms':list(forms()),'native_run':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    print(json.dumps(generate(a.check),indent=2))
