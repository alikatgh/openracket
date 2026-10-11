#!/usr/bin/env python3
"""Reproduce the default-off, stock-owned eager binding read-cache experiment."""
import difflib
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PIN = '5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e'
FLAG = 'OPENRACKET_BINDING_TABLE_EAGER'
ACTIVATION = '''
;; Default-off experiment for the retained stock built-in editor only.
;; Custom equality/hash callback counts and ordering are outside enabled parity.
(define openracket-binding-table-eager-enabled?
  (equal? (getenv "OPENRACKET_BINDING_TABLE_EAGER") "1"))
(provide openracket-binding-table-eager-enabled?)
'''
STATE = '''
            ;; A single generation-owned reference holds the numeric equal?
            ;; duplicate index and start-range -> current immutable-set cache.
            ;; The real public hash is updated immediately and stays authoritative.
            (define binding-eager-state
              (and openracket-binding-table-eager-enabled?
                   (cons (make-hash) (make-hash))))
            (define binding-eager-in-flight #f)
            (define binding-eager-generation 0)
            (define binding-eager-accepted 0)
            (define binding-eager-duplicates 0)
            (define binding-eager-writes 0)
            (define binding-eager-stock-calls 0)
            (define binding-eager-unsupported-fallbacks 0)
            (define binding-eager-failure-fallbacks 0)
            (define binding-eager-exposed? #f)
            (define binding-eager-fallback-reason #f)

            (define/private (disable-binding-eager! state reason)
              (when (and state (eq? state binding-eager-state))
                ;; Drop both caches together before any diagnostic updates.
                (set! binding-eager-state #f)
                (set! binding-eager-fallback-reason reason)
                (case reason
                  [(unsupported-input reentrant-call)
                   (set! binding-eager-unsupported-fallbacks
                         (add1 binding-eager-unsupported-fallbacks))]
                  [(interrupted)
                   (set! binding-eager-failure-fallbacks
                         (add1 binding-eager-failure-fallbacks))])))

            ;; Constant-time, read-only evidence. No table traversal or exposure.
            (define/public (openracket:get-binding-table-eager-state)
              (hash 'enabled openracket-binding-table-eager-enabled?
                    'active (and binding-eager-state #t)
                    'in_flight (and binding-eager-in-flight #t)
                    'generation binding-eager-generation
                    'accepted binding-eager-accepted
                    'duplicates binding-eager-duplicates
                    'eager_writes binding-eager-writes
                    'stock_calls binding-eager-stock-calls
                    'pending 0
                    'materializations 0
                    'public_keys (hash-count bindings-table)
                    'indexed_edges (if binding-eager-state
                                       (hash-count (car binding-eager-state)) 0)
                    'cached_starts (if binding-eager-state
                                       (hash-count (cdr binding-eager-state)) 0)
                    'exposed binding-eager-exposed?
                    'unsupported_fallbacks binding-eager-unsupported-fallbacks
                    'failure_fallbacks binding-eager-failure-fallbacks
                    'fallback_reason binding-eager-fallback-reason))
'''
OLD_ADD = '''                [else
                 (define key (list start-text start-left start-right))
                 (define priors (hash-ref bindings-table key (λ () (set))))'''
NEW_ADD = '''                [(and binding-eager-state
                      (not binding-eager-in-flight)
                      (eq? start-text this) (eq? end-text this)
                      (exact-integer? start-left) (exact-integer? start-right)
                      (exact-integer? end-left) (exact-integer? end-right))
                 (define state binding-eager-state)
                 (define generation binding-eager-generation)
                 (define completed? #f)
                 (define entered? #f)
                 (dynamic-wind
                   (lambda ()
                     (parameterize-break #f
                       ;; A resumed continuation must not reuse old cache reads.
                       (when entered? (disable-binding-eager! state 'interrupted))
                       (set! entered? #t)
                       (set! completed? #f)
                       (when (eq? state binding-eager-state)
                         (set! binding-eager-in-flight state))))
                   (lambda ()
                     (define edge (list start-left start-right end-left end-right))
                     (define result
                       (cond
                         [(hash-ref (car state) edge #f)
                          (when (= generation binding-eager-generation)
                            (set! binding-eager-duplicates (add1 binding-eager-duplicates)))
                          #f]
                         [else
                          (define key (list start-text start-left start-right))
                          (define start-key (list start-left start-right))
                          (define priors (hash-ref (cdr state) start-key (λ () (set))))
                          (define new (list end-text end-left end-right))
                          (define next-priors #f)
                          (define target bindings-table)
                          ;; Preserve stock argument order: capture the target
                          ;; table before evaluating the original set-add.
                          (hash-set! bindings-table key
                                     (let ([updated (set-add priors new)])
                                       (set! next-priors updated)
                                       updated))
                          (when (= generation binding-eager-generation)
                            (set! binding-eager-writes (add1 binding-eager-writes)))
                          ;; Commit auxiliary caches only after the public write succeeded.
                          (when (and (eq? state binding-eager-state)
                                     (eq? target bindings-table)
                                     (not binding-eager-exposed?))
                            (hash-set! (cdr state) start-key next-priors)
                            ;; Both auxiliary commits belong to this same state token.
                            (hash-set! (car state) edge #t))
                          (when (= generation binding-eager-generation)
                            (set! binding-eager-accepted (add1 binding-eager-accepted)))
                          #t]))
                     (set! completed? #t)
                     result)
                   (lambda ()
                     (parameterize-break #f
                       ;; Covers arbitrary raises, breaks and continuation escape.
                       ;; Never roll back a successful real-table write or revive
                       ;; a state cleared by exposure, reset or a nested operation.
                       (unless completed? (disable-binding-eager! state 'interrupted))
                       (when (eq? binding-eager-in-flight state)
                         (set! binding-eager-in-flight #f)))))]
                [else
                 (disable-binding-eager! binding-eager-state
                                        (if binding-eager-in-flight
                                            'reentrant-call 'unsupported-input))
                 (set! binding-eager-stock-calls (add1 binding-eager-stock-calls))
                 (define key (list start-text start-left start-right))
                 (define priors (hash-ref bindings-table key (λ () (set))))'''
OLD_GET = '''                [else
                 bindings-table]))'''
NEW_GET = '''                [else
                 (when openracket-binding-table-eager-enabled?
                   (set! binding-eager-exposed? #t)
                   (disable-binding-eager! binding-eager-state 'public-exposure))
                 bindings-table]))'''
RESET_ANCHOR = '              (set! bindings-table (make-hash))\n'
RESET = '''              (set! binding-eager-state
                    (and openracket-binding-table-eager-enabled?
                         (cons (make-hash) (make-hash))))
              (set! binding-eager-in-flight #f)
              (set! binding-eager-generation (add1 binding-eager-generation))
              (set! binding-eager-accepted 0)
              (set! binding-eager-duplicates 0)
              (set! binding-eager-writes 0)
              (set! binding-eager-stock-calls 0)
              (set! binding-eager-unsupported-fallbacks 0)
              (set! binding-eager-failure-fallbacks 0)
              (set! binding-eager-exposed? #f)
              (set! binding-eager-fallback-reason #f)
'''
SEAMS = (
    ('(provide tool@)\n', '(provide tool@)\n' + ACTIVATION),
    ('            (define bindings-table (make-hash))\n',
     '            (define bindings-table (make-hash))\n' + STATE),
    (OLD_ADD, NEW_ADD), (OLD_GET, NEW_GET),
    (RESET_ANCHOR, RESET_ANCHOR + RESET),
)
def sha(data): return hashlib.sha256(data).hexdigest()
def generate(source):
    if sha(source) != PIN: raise ValueError('Stock gui.rkt differs from exact official 9.3 pin')
    value=source.decode()
    for old,new in SEAMS:
        if value.count(old)!=1: raise ValueError('Source seam is not unique')
        value=value.replace(old,new)
    return value.encode()
def restore(patched):
    value=patched.decode()
    for old,new in reversed(SEAMS):
        if value.count(new)!=1: raise ValueError('Patched source seam is not unique')
        value=value.replace(new,old)
    return value.encode()
def main():
    original=(ROOT/'vendor/gui.rkt').read_bytes();patched=generate(original)
    assert restore(patched)==original
    (ROOT/'overlay/gui.rkt').write_bytes(patched)
    manifest={
        'experiment':'same-owner-eager-binding-read-cache','racket_version':'9.3',
        'package':'drracket-core-lib','package_version':'1.17',
        'upstream_commit':'1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6',
        'source_url':'https://github.com/racket/drracket/blob/1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6/drracket-core-lib/drracket/private/syncheck/gui.rkt',
        'relative_target':'drracket/private/syncheck/gui.rkt',
        'flag':FLAG,'enabled_value':'1','default_enabled':False,
        'activation_export':'openracket-binding-table-eager-enabled?',
        'witness_method':'openracket:get-binding-table-eager-state',
        'scope':'stock built-in retained editor, same owning object, exact integer positions; custom equality/hash callback parity excluded',
        'original_sha256':PIN,'patched_sha256':sha(patched),
        'unchanged_support_sha256_relative_to_syncheck':{f:sha((ROOT/'vendor'/f).read_bytes()) for f in ('intf.rkt','local-member-names.rkt')},
        'reference_runtime_commit':'bbf7dea831df95922db23aaa51e13eed17dcf881',
        'reference_source_sha256':{f:sha((ROOT/'vendor'/f).read_bytes()) for f in ('class-internal.rkt','set-types.rkt')},
    }
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),patched.decode().splitlines(True),
        'official-9.3/drracket/private/syncheck/gui.rkt','eager-experiment/drracket/private/syncheck/gui.rkt')))
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
