#!/usr/bin/env python3
"""Reproduce one default-off, stock-scope binding-index source experiment."""
import difflib
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PIN = '5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e'
FLAG = 'OPENRACKET_BINDING_TABLE_INDEX'
ACTIVATION = '''
;; Default-off experiment; enabled scope is the retained stock built-in editor.
;; Custom equality/hash callbacks may observe deferred/reduced calls. See the
;; experiment contract; this does not establish arbitrary extension parity.
(define openracket-binding-table-index-enabled?
  (equal? (getenv "OPENRACKET_BINDING_TABLE_INDEX") "1"))
(provide openracket-binding-table-index-enabled?)
'''
STATE = '''
            ;; The public hash keeps its identity. Only the unexposed, same-owner,
            ;; exact-integer path can use this private numeric equal? index.
            (define binding-index
              (and openracket-binding-table-index-enabled? (make-hash)))
            (define binding-pending '())
            (define binding-pending-count 0)
            (define binding-index-accepted 0)
            (define binding-index-duplicates 0)
            (define binding-materializations 0)
            (define binding-stock-calls 0)
            (define binding-unsupported-fallbacks 0)
            (define binding-generation 0)
            (define binding-fallback-reason #f)

            (define/private (materialize-bindings-table! reason)
              (when binding-index
                ;; Switch before replay: the original method's stock branch is
                ;; the only writer of immutable sets into the public table.
                (define pending (reverse binding-pending))
                (set! binding-index #f)
                (set! binding-pending '())
                (set! binding-pending-count 0)
                (set! binding-fallback-reason reason)
                (set! binding-materializations (add1 binding-materializations))
                (for ([entry (in-list pending)])
                  (add-to-bindings-table this (list-ref entry 0) (list-ref entry 1)
                                         this (list-ref entry 2) (list-ref entry 3)))))

            ;; Read-only bounded evidence. It does not expose or materialize data.
            (define/public (openracket:get-binding-table-index-state)
              (hash 'enabled openracket-binding-table-index-enabled?
                    'active (and binding-index #t)
                    'accepted binding-index-accepted
                    'duplicates binding-index-duplicates
                    'pending binding-pending-count
                    'materializations binding-materializations
                    'stock_calls binding-stock-calls
                    'unsupported_fallbacks binding-unsupported-fallbacks
                    'generation binding-generation
                    'fallback_reason binding-fallback-reason))
'''
OLD_ADD = '''                [else
                 (define key (list start-text start-left start-right))
                 (define priors (hash-ref bindings-table key (λ () (set))))'''
NEW_ADD = '''                [(and binding-index
                      (eq? start-text this) (eq? end-text this)
                      (exact-integer? start-left) (exact-integer? start-right)
                      (exact-integer? end-left) (exact-integer? end-right))
                 (define key (list start-left start-right end-left end-right))
                 (cond
                   [(hash-ref binding-index key #f)
                    (set! binding-index-duplicates (add1 binding-index-duplicates))
                    #f]
                   [else
                    (hash-set! binding-index key #t)
                    (set! binding-pending (cons key binding-pending))
                    (set! binding-pending-count (add1 binding-pending-count))
                    (set! binding-index-accepted (add1 binding-index-accepted))
                    #t])]
                [else
                 (when binding-index
                   (set! binding-unsupported-fallbacks (add1 binding-unsupported-fallbacks))
                   (materialize-bindings-table! 'unsupported-input))
                 (set! binding-stock-calls (add1 binding-stock-calls))
                 (define key (list start-text start-left start-right))
                 (define priors (hash-ref bindings-table key (λ () (set))))'''
OLD_GET = '''                [else
                 bindings-table]))'''
NEW_GET = '''                [else
                 (materialize-bindings-table! 'public-exposure)
                 bindings-table]))'''
RESET_ANCHOR = '              (set! bindings-table (make-hash))\n'
RESET = '''              (set! binding-index
                    (and openracket-binding-table-index-enabled? (make-hash)))
              (set! binding-pending '())
              (set! binding-pending-count 0)
              (set! binding-index-accepted 0)
              (set! binding-index-duplicates 0)
              (set! binding-materializations 0)
              (set! binding-stock-calls 0)
              (set! binding-unsupported-fallbacks 0)
              (set! binding-generation (add1 binding-generation))
              (set! binding-fallback-reason #f)
'''
SEAMS = (
    ('(provide tool@)\n', '(provide tool@)\n' + ACTIVATION),
    ('            (define bindings-table (make-hash))\n',
     '            (define bindings-table (make-hash))\n' + STATE),
    (OLD_ADD, NEW_ADD), (OLD_GET, NEW_GET),
    (RESET_ANCHOR, RESET_ANCHOR + RESET),
)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def generate(source):
    if sha(source) != PIN:
        raise ValueError('Stock gui.rkt differs from exact official 9.3 pin')
    value = source.decode()
    for old, new in SEAMS:
        if value.count(old) != 1:
            raise ValueError('Source seam is not unique')
        value = value.replace(old, new)
    return value.encode()
def restore(patched):
    value = patched.decode()
    for old, new in reversed(SEAMS):
        if value.count(new) != 1:
            raise ValueError('Patched source seam is not unique')
        value = value.replace(new, old)
    return value.encode()
def main():
    original = (ROOT / 'vendor/gui.rkt').read_bytes()
    patched = generate(original)
    assert restore(patched) == original
    (ROOT / 'overlay/gui.rkt').write_bytes(patched)
    manifest = {
        'experiment': 'same-owner-binding-table-index', 'racket_version': '9.3',
        'package': 'drracket-core-lib', 'package_version': '1.17',
        'upstream_commit': '1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6',
        'source_url': 'https://github.com/racket/drracket/blob/1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6/drracket-core-lib/drracket/private/syncheck/gui.rkt',
        'relative_target': 'drracket/private/syncheck/gui.rkt',
        'flag': FLAG, 'enabled_value': '1', 'default_enabled': False,
        'activation_export': 'openracket-binding-table-index-enabled?',
        'witness_method': 'openracket:get-binding-table-index-state',
        'scope': 'stock built-in retained editor, same owning object, exact integer positions; custom equality/hash callback parity excluded',
        'original_sha256': PIN, 'patched_sha256': sha(patched),
        'unchanged_support_sha256_relative_to_syncheck': {
            f: sha((ROOT / 'vendor' / f).read_bytes()) for f in ('intf.rkt', 'local-member-names.rkt')},
        'reference_runtime_commit': 'bbf7dea831df95922db23aaa51e13eed17dcf881',
        'reference_source_sha256': {
            f: sha((ROOT / 'vendor' / f).read_bytes()) for f in ('class-internal.rkt', 'set-types.rkt')},
    }
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'patch.diff').write_text(''.join(difflib.unified_diff(
        original.decode().splitlines(True), patched.decode().splitlines(True),
        'official-9.3/drracket/private/syncheck/gui.rkt',
        'experiment/drracket/private/syncheck/gui.rkt')))
    print(json.dumps(manifest, indent=2))
if __name__ == '__main__':
    main()
