#!/usr/bin/env python3
"""Reproduce only the two additive host seams against the exact delivered host."""
import argparse, difflib, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tests/reference-host-0520.rkt'
PIN='5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448'
def generate():
    raw=BASE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Base host pin mismatch')
    s=raw.decode()
    anchor='(define-runtime-path returning-stop-module "independent-native-stop-returning.rkt")'
    if s.count(anchor)!=1:raise ValueError('Unique import seam required')
    s=s.replace(anchor,anchor+'\n(define-runtime-path binding-postflight-module "binding-postflight.rkt")')
    anchor='  ;; A low-priority event turn allows actual paint work to follow the last update.\n'
    if s.count(anchor)!=1:raise ValueError('Unique completed-work seam required')
    s=s.replace(anchor,'  ;; Read-only graph export and real arrow navigation after genuine Check Syntax.\n  (on-gui (lambda ()\n            ((dynamic-require binding-postflight-module \'run-binding-postflight!) frame)))\n\n'+anchor)
    return s.encode()
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    out=ROOT/'tests/independent-native-host.rkt';expected=generate()
    if args.check:
        if out.read_bytes()!=expected:raise ValueError('Host differs from exact additive derivation')
    else:out.write_bytes(expected)
    pins=json.loads((ROOT/'tests/binding-native-pins.json').read_text())
    if hashlib.sha256(expected).hexdigest()!=pins['host']:raise ValueError('Host metadata pin mismatch')
    print('Exact native binding host derivation verified')
if __name__=='__main__':main()
