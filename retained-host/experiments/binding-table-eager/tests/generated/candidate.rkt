#lang racket/base
;; Generated from the actual pinned gui.rkt forms. Only the surrounding GUI
;; dependencies are replaced by inert test fields. The add/get/reset bodies
;; and candidate private state/witness are extracted verbatim in normal modules.
;; Explicit *-fault modules insert only the declared deterministic test hooks.
(require racket/class racket/set racket/list racket/dict)
(provide make-test-class openracket-binding-table-eager-enabled?)
(define openracket-binding-table-eager-enabled?
  (equal? (getenv "OPENRACKET_BINDING_TABLE_EAGER") "1"))
(struct tooltip-info (pos-left pos-right msg) #:transparent)
(define (make-test-class super%)
  (class super%
    (super-new)
    (define tacked-hash-table #f)
    (define arrow-records (make-hasheq))
    (define cleanup-texts #f)
    (define definition-targets (make-hash))
    (define unused-require-table (make-hash))

            (define bindings-table (make-hash))

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


(define/private (add-to-bindings-table start-text start-left start-right
                                                   end-text end-left end-right)
              (cond
                [(and (object=? start-text end-text)
                      (= start-left end-left)
                      (= start-right end-right))
                 #f]
                [(and binding-eager-state
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
                 (define priors (hash-ref bindings-table key (λ () (set))))
                 (define new (list end-text end-left end-right))
                 (cond
                   [(set-member? priors new)
                    #f]
                   [else
                    (hash-set! bindings-table key (set-add priors new))
                    #t])]))
(define/public (syncheck:get-bindings-table [tooltips? #f])
              (cond
                [tooltips?
                 (define unsorted
                   (apply 
                    append
                    (for/list ([(k interval-map) (in-hash arrow-records)])
                      (apply
                       append
                       (dict-map
                        interval-map
                        (λ (key x)
                          (for/list ([x (in-list x)]
                                     #:when (tooltip-info? x))
                            (list (tooltip-info-pos-left x)
                                  (tooltip-info-pos-right x)
                                  (tooltip-info-msg x)))))))))
                 (define (compare l1 l2)
                   (cond
                     [(equal? (list-ref l1 0) (list-ref l2 0))
                      (cond
                        [(equal? (list-ref l1 2) (list-ref l2 2))
                         (string<=? (list-ref l1 2) (list-ref l2 2))]
                        [else
                         (< (list-ref l1 1) (list-ref l2 1))])]
                     [else
                      (< (list-ref l1 0) (list-ref l2 0))]))
                 (sort unsorted compare)]
                [else
                 (when openracket-binding-table-eager-enabled?
                   (set! binding-eager-exposed? #t)
                   (disable-binding-eager! binding-eager-state 'public-exposure))
                 bindings-table]))
(define/public (syncheck:init-arrows)
              (set! tacked-hash-table (make-hasheq))
              (set! arrow-records (make-hasheq))
              (set! bindings-table (make-hash))
              (set! binding-eager-state
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
              (set! cleanup-texts '())
              (set! definition-targets (make-hash))
              (set! unused-require-table (make-hash)))
    (define/public (test:add a b c d e f) (add-to-bindings-table a b c d e f))
    (define/public (test:peek) bindings-table)
    (define/public (test:tooltip)
      (hash-set! arrow-records this
                 (hash '(0 . 1) (list (tooltip-info 4 5 "tip")))))
    (define/public (test:state)
      (openracket:get-binding-table-eager-state))
))
