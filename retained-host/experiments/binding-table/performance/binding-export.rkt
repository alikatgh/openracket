#lang racket/base
;; Separately measure deferred public exposure after normal application readiness.
;; The helper does no file I/O, yield, or direct editor mutation. The public
;; getter may materialize pending bindings through the original insertion path.
;; Only scalar summaries escape; raw tables and graph rows are not retained.
(require racket/class racket/list racket/set
         (only-in "gui-observer.rkt" digest))
(provide measure-binding-export)

(define state-method 'openracket:get-binding-table-index-state)
(define (point)
  (hash 'monotonic_ms (current-inexact-monotonic-milliseconds)
        'allocation_bytes (current-memory-use 'cumulative)
        'managed_bytes (current-memory-use)
        'gc_ms (current-gc-milliseconds)
        'cpu_all_places_ms (current-process-milliseconds #f)))
(define (state editor arm)
  (define available? (object-method-arity-includes? editor state-method 0))
  (cond
    [(equal? arm "stock")
     (when available? (error 'binding-export "Stock editor unexpectedly has candidate state method"))
     'null]
    [(equal? arm "candidate")
     (unless available? (error 'binding-export "Candidate editor lacks state method"))
     (define s (dynamic-send editor state-method))
     (unless (and (hash? s) (immutable? s))
       (error 'binding-export "Candidate state must be an immutable scalar hash"))
     (unless (equal? (sort (hash-keys s) symbol<?)
                     (sort '(enabled active accepted duplicates pending materializations stock_calls
                             unsupported_fallbacks generation fallback_reason) symbol<?))
       (error 'binding-export "Candidate index state has missing or extra fields"))
     (for ([(k v) (in-hash s)])
       (unless (and (symbol? k) (or (boolean? v) (symbol? v) (exact-nonnegative-integer? v)))
         (error 'binding-export "Non-scalar candidate index state")))
     ;; JSON does not accept symbol values; preserve the declared enum faithfully.
     (for/hash ([(k v) (in-hash s)]) (values k (if (symbol? v) (symbol->string v) v)))]
    [else (error 'binding-export "Unknown arm")]))

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

(define (initial-state-valid? s)
  (and (eq? (hash-ref s 'enabled) #t) (eq? (hash-ref s 'active) #t)
       (exact-positive-integer? (hash-ref s 'accepted))
       (equal? (hash-ref s 'accepted) (hash-ref s 'pending))
       (exact-nonnegative-integer? (hash-ref s 'duplicates))
       (equal? (hash-ref s 'materializations) 0)
       (equal? (hash-ref s 'stock_calls) 0)
       (equal? (hash-ref s 'unsupported_fallbacks) 0)
       (exact-positive-integer? (hash-ref s 'generation))
       (eq? (hash-ref s 'fallback_reason) #f)))
(define (materialized-state-valid? before after)
  (and (eq? (hash-ref after 'enabled) #t) (eq? (hash-ref after 'active) #f)
       (for/and ([key (in-list '(accepted duplicates generation unsupported_fallbacks))])
         (equal? (hash-ref before key) (hash-ref after key)))
       (equal? (hash-ref after 'pending) 0)
       (equal? (hash-ref after 'materializations) 1)
       (equal? (hash-ref after 'stock_calls) (hash-ref before 'pending))
       (equal? (hash-ref after 'fallback_reason) "public-exposure")))

(define (measure-binding-export editor arm source-length #:on-progress [on-progress void])
  (unless (exact-positive-integer? source-length)
    (error 'binding-export "Expected positive source length"))
  (define report (hash 'schema_version 1 'kind "binding-table-public-exposure" 'arm arm
                       'verified #f 'status "started"
                       'scope "Separate post-readiness synchronous public getter; export walking is outside command timing"))
  (define (record! key value)
    (set! report (hash-set report key value))
    (on-progress report))
  (on-progress report)
  (with-handlers ([exn? (lambda (e)
                         (record! 'error (exn-message e))
                         (record! 'status "failed")
                         (raise e))])
    (define before-state (state editor arm))
    (record! 'before_state before-state)
    (when (and (equal? arm "candidate") (not (initial-state-valid? before-state)))
      (error 'binding-export "Candidate did not retain active pending fast-path work before exposure"))
    ;; No progress callback, reporting, state read or full traversal is inside a
    ;; command's start/end snapshots. Counter deltas have whole-runtime scope.
    (define first-start (point))
    (define first-table (send editor syncheck:get-bindings-table))
    (define first-end (point))
    (record! 'first_start first-start)
    (record! 'first_end first-end)
    (define first-state (state editor arm))
    (record! 'after_first_state first-state)
    (when (and (equal? arm "candidate") (not (materialized-state-valid? before-state first-state)))
      (error 'binding-export "First public getter did not materialize exactly the pending candidate edges"))
    (define second-start (point))
    (define second-table (send editor syncheck:get-bindings-table))
    (define second-end (point))
    (record! 'second_start second-start)
    (record! 'second_end second-end)
    (define second-state (state editor arm))
    (record! 'after_second_state second-state)
    (unless (and (eq? first-table second-table) (equal? first-state second-state))
      (error 'binding-export "Repeated getter changed public hash identity or index state"))
    (record! 'same_public_hash_identity #t)
    (define summary (export-summary first-table editor source-length))
    (record! 'export summary)
    (when (and (equal? arm "candidate")
               (not (= (hash-ref summary 'edge_count) (hash-ref before-state 'accepted))))
      (error 'binding-export "Public export edge count differs from accepted pending work"))
    (record! 'verified_monotonic_ms (current-inexact-monotonic-milliseconds))
    (record! 'status "complete")
    (record! 'verified #t)
    report))

(module+ test-support (provide export-summary quad<?))
