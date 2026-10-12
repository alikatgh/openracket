#!/usr/bin/env python3
"""Exact-source diagnostic transform. No runtime installation or execution."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASS_PIN = '1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f'
REVIEW_PIN = '430bbd3c3f2b4b0cc8867fa8d69cfbc2b9572e7b0e3a6db4983365abcd2a2e16'
ORIGINAL_HELPER = b'''(define (inspectable-struct->vector v)
  (define vec (struct->vector v not-all-visible))
  (and (for/and ([elem (in-vector vec)])
         (not (eq? elem not-all-visible)))
       vec))'''
ORIGINAL_HASH = b'''(define (object-hash-code obj recur)
  (let ([vec (inspectable-struct->vector obj)])
    (if vec
        (recur (vector (object-ref obj) vec))
        (eq-hash-code obj))))'''
CATEGORIES = [f'{role}-{kind}' for role in ('definitions','interactions')
              for kind in ('impersonator','skipped','not-skipped','inspection-failed')]

def sha(data): return hashlib.sha256(data).hexdigest()
def once(data, old, new):
    if data.count(old) != 1: raise ValueError('exact source anchor not unique')
    return data.replace(old, new, 1)

def support():
    text = (ROOT / 'templates/probe-support.rkt.inc').read_text()
    build_id = sha(text.encode() + Path(__file__).read_bytes())
    text = once(text, '@@BUILD-ID@@', build_id)
    definitions = '\n'.join(f'(define probe-{cat}-{stat} 0)' for cat in CATEGORIES
                              for stat in ('matches','vectors','slots','max-slots','returns','fallbacks'))
    def case(lines):
        return '(case category\n' + '\n'.join(f'  [({i}) {lines(cat)}]' for i, cat in enumerate(CATEGORIES)) + ')'
    count = case(lambda c: f'(set! probe-{c}-matches (add1 probe-{c}-matches))')
    vectors = case(lambda c: f'(set! probe-{c}-vectors (add1 probe-{c}-vectors))\n'
                   f'       (set! probe-{c}-slots (+ probe-{c}-slots length))\n'
                   f'       (set! probe-{c}-max-slots (max probe-{c}-max-slots length))')
    returns = case(lambda c: f'(set! probe-{c}-returns (add1 probe-{c}-returns))')
    fallbacks = case(lambda c: f'(set! probe-{c}-fallbacks (add1 probe-{c}-fallbacks))')
    states = '\n          '.join(f"'{c.replace('-','_')}_{stat.replace('-','_')} probe-{c}-{stat}"
                                for c in CATEGORIES for stat in ('matches','vectors','slots','max-slots','returns','fallbacks'))
    for anchor, val in [('COUNTER-DEFINITIONS',definitions),('COUNT-MATCH',count),
                        ('COUNT-VECTOR',vectors),('COUNT-RETURN',returns),('COUNT-FALLBACK',fallbacks),('STATE-COUNTERS',states)]:
        text = once(text, f';; @@{anchor}@@', val)
    return text.encode()

def observed_helper():
    helper = once(ORIGINAL_HELPER, b'(inspectable-struct->vector v)',
                  b'(probe-inspectable-struct->vector v category)')
    line = b'  (define vec (struct->vector v not-all-visible))'
    return once(helper, line, line + b'\n  (probe-note-vector! category (vector-length vec))')

def instrumented_hash():
    # The complete original body is byte-identical; a lexical helper binding adds
    # only bounded scalar observations to its existing conversion path.
    body = ORIGINAL_HASH.split(b'\n',1)[1][:-1]
    return b'''(define (object-hash-code obj recur)
  (define sample (and openracket-object-hash-probe-enabled? (probe-claim! obj)))
  (let ([inspectable-struct->vector
         (if sample
             (lambda (v)
               (define result (probe-inspectable-struct->vector v sample))
               (probe-note-result! sample (and result #t))
               result)
             inspectable-struct->vector)])
''' + body + b'))'

def transform(data):
    if sha(data) != CLASS_PIN: raise ValueError('class-internal.rkt exact source SHA256 mismatch')
    result = once(data, ORIGINAL_HELPER, ORIGINAL_HELPER + b'\n\n' + support() + b'\n' + observed_helper())
    return once(result, ORIGINAL_HASH, instrumented_hash())

def restore(data):
    data = once(data, instrumented_hash(), ORIGINAL_HASH)
    data = once(data, ORIGINAL_HELPER + b'\n\n' + support() + b'\n' + observed_helper(), ORIGINAL_HELPER)
    if sha(data) != CLASS_PIN: raise ValueError('restored source pin mismatch')
    return data

def generate(check=False):
    original = (ROOT / 'vendor/class-internal.rkt').read_bytes()
    if sha((ROOT/'vendor/REVIEW.md').read_bytes()) != REVIEW_PIN: raise ValueError('review pin mismatch')
    result = transform(original)
    if restore(result) != original: raise AssertionError('non-reversible transform')
    out = ROOT/'generated/class-internal.rkt'
    if check:
        if out.read_bytes() != result: raise ValueError('generated source drift')
    else:
        out.write_bytes(result)
    return {'original_sha256': sha(original), 'instrumented_sha256': sha(result),
            'body_verbatim': True, 'custom_dispatch_unchanged': True,
            'observed_helper_single_original_conversion': True, 'native_run': False}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true')
    args=parser.parse_args(); print(json.dumps(generate(args.check),indent=2))
