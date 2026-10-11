#lang racket/base
;; Full public graph compatibility check AFTER ordinary readiness and heartbeat join.
;; No getter timing, candidate binding hooks, synthetic graph, or hidden-work claim.
(require racket/class racket/list racket/set
         (only-in "gui-observer.rkt" digest))
(provide verify-binding-export)

(define (quad<? a b)
  (cond [(null? a) #f]
        [(< (car a) (car b)) #t]
        [(> (car a) (car b)) #f]
        [else (quad<? (cdr a) (cdr b))]))
(define (endpoint value editor source-length)
  (unless (and (list? value) (= (length value) 3) (eq? (car value) editor)
               (exact-integer? (cadr value)) (exact-integer? (caddr value))
               (<= 0 (cadr value) (caddr value) source-length))
    (error 'binding-export "Export endpoint is not an in-range owning-editor triple"))
  (cdr value))
(define (export-summary table editor source-length)
  (unless (and (hash? table) (not (immutable? table)) (hash-equal? table)
               (hash-strong? table) (<= 1 (hash-count table) 300000))
    (error 'binding-export "Expected nonempty mutable strong equal? public hash"))
  (define edges 0)
  (define rows
    (for*/list ([(from targets) (in-hash table)]
                [target (in-list
                         (begin
                           (endpoint from editor source-length)
                           (unless (and (set? targets) (set-equal? targets)
                                        (not (set-mutable? targets)) (not (set-weak? targets))
                                        (positive? (set-count targets)) (not (impersonator? targets)))
                             (error 'binding-export "Expected original immutable equal? set values"))
                           (set->list targets)))])
      (set! edges (add1 edges))
      (when (> edges 300000) (error 'binding-export "Export edge bound exceeded"))
      (append (cdr from) (endpoint target editor source-length))))
  (unless (> edges 0) (error 'binding-export "Empty exported graph"))
  (define out (open-output-bytes))
  (write (sort rows quad<?) out)
  (hash 'key_count (hash-count table) 'edge_count edges
        'canonical_format "racket-written-sorted-exact-integer-quadruples-v1"
        'canonical_sha256 (digest (get-output-bytes out))
        'owning_editor_endpoints #t 'mutable_strong_equal_hash #t
        'immutable_equal_set_values #t))


(define (verify-binding-export editor arm source-length #:on-progress [on-progress void])
  (unless (and (member arm '("stock" "candidate")) (exact-positive-integer? source-length))
    (error 'binding-export "Invalid arm or source length"))
  (define report (hash 'schema_version 1 'kind "post-readiness-binding-graph" 'arm arm
                       'verified #f 'status "started" 'timed #f))
  (define (record! key value)
    (set! report (hash-set report key value))
    (on-progress report))
  (on-progress report)
  (with-handlers ([exn? (lambda (e)
                         (record! 'error (exn-message e))
                         (record! 'status "failed")
                         (raise e))])
    (record! 'started_monotonic_ms (current-inexact-monotonic-milliseconds))
    (define table (send editor syncheck:get-bindings-table))
    (unless (eq? table (send editor syncheck:get-bindings-table))
      (error 'binding-export "Repeated getter changed public hash identity"))
    (record! 'same_public_hash_identity #t)
    (record! 'export (export-summary table editor source-length))
    (record! 'verified_monotonic_ms (current-inexact-monotonic-milliseconds))
    (record! 'status "complete")
    (record! 'verified #t)
    report))
(module+ test-support (provide export-summary quad<?))
