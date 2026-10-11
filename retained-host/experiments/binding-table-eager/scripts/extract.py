#!/usr/bin/env python3
"""Generate small native classes from the exact actual gui.rkt forms, not models."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def form_at(text, needle):
    start = text.index(needle)
    depth = 0; string = False; escape = False; comment = False
    for i in range(start, len(text)):
        ch = text[i]
        if comment:
            if ch == '\n': comment = False
            continue
        if string:
            if escape: escape = False
            elif ch == '\\': escape = True
            elif ch == '"': string = False
            continue
        if ch == ';': comment = True
        elif ch == '"': string = True
        elif ch in '([{': depth += 1
        elif ch in ')]}':
            depth -= 1
            if depth == 0: return text[start:i+1]
    raise ValueError(f'Incomplete actual form: {needle}')

FAULT_HOOKS = (
    ('                          ;; Commit auxiliary caches only after the public write succeeded.',
     '                          (test-after-public-write)\n'),
    ('                            ;; Both auxiliary commits belong to this same state token.',
     '                            (test-after-first-cache)\n'),
)

def extract(source, candidate, fault=False):
    text = source.decode()
    fields_start = text.index('            (define bindings-table (make-hash))')
    fields_end = text.index('            ;; unused-require-table', fields_start)
    fields = text[fields_start:fields_end]
    add = form_at(text, '(define/private (add-to-bindings-table ')
    getter = form_at(text, '(define/public (syncheck:get-bindings-table ')
    init = form_at(text, '(define/public (syncheck:init-arrows)')
    extra_fields = ''
    extra_methods = ''
    if fault:
        if candidate:
            for anchor, hook in FAULT_HOOKS:
                if add.count(anchor) != 1: raise ValueError('Fault seam must be unique')
                add = add.replace(anchor, hook + anchor)
        # In both arms, this test-only hook is inside the third hash-set!
        # argument, after the original set-add result and before publication.
        add = add.replace('(set-add priors new)',
                          '(let ([result (set-add priors new)]) (test-after-set-add) result)')
        extra_fields = '(define test-after-public-write void)\n(define test-after-first-cache void)\n(define test-after-set-add void)'
        extra_methods = '''
    (define/public (test:arm-public! thunk) (set! test-after-public-write thunk))
    (define/public (test:arm-cache! thunk) (set! test-after-first-cache thunk))
    (define/public (test:arm-set-add! thunk) (set! test-after-set-add thunk))
'''
    activation = ''
    if candidate:
        activation = form_at(text, '(define openracket-binding-table-eager-enabled?')
    else:
        activation = '(define openracket-binding-table-eager-enabled? #f)'
    return f'''#lang racket/base
;; Generated from the actual pinned gui.rkt forms. Only the surrounding GUI
;; dependencies are replaced by inert test fields. The add/get/reset bodies
;; and candidate private state/witness are extracted verbatim in normal modules.
;; Explicit *-fault modules insert only the declared deterministic test hooks.
(require racket/class racket/set racket/list racket/dict)
(provide make-test-class openracket-binding-table-eager-enabled?)
{activation}
(struct tooltip-info (pos-left pos-right msg) #:transparent)
(define (make-test-class super%)
  (class super%
    (super-new)
    (define tacked-hash-table #f)
    (define arrow-records (make-hasheq))
    (define cleanup-texts #f)
    (define definition-targets (make-hash))
    (define unused-require-table (make-hash))
{extra_fields}
{fields}
{add}
{getter}
{init}
    (define/public (test:add a b c d e f) (add-to-bindings-table a b c d e f))
    (define/public (test:peek) bindings-table)
    (define/public (test:tooltip)
      (hash-set! arrow-records this
                 (hash '(0 . 1) (list (tooltip-info 4 5 "tip")))))
    (define/public (test:state)
      {'(openracket:get-binding-table-eager-state)' if candidate else '#f'})
{extra_methods}))
'''.encode()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for arm,relative,pin in [('stock','vendor/gui.rkt','original_sha256'),
                             ('candidate','overlay/gui.rkt','patched_sha256')]:
        source=(ROOT/relative).read_bytes()
        if hashlib.sha256(source).hexdigest()!=manifest[pin]:
            raise ValueError(f'{arm} source pin mismatch')
        (a.output/f'{arm}.rkt').write_bytes(extract(source, arm=='candidate'))
        print(f'{arm}: {manifest[pin]} -> {a.output/ (arm+".rkt")}')
        (a.output/f'{arm}-fault.rkt').write_bytes(extract(source, arm=='candidate', fault=True))
if __name__=='__main__': main()
