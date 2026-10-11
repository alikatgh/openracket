#lang racket/base
;; Generated from the actual pinned gui.rkt forms. Only the surrounding GUI
;; dependencies are replaced by inert test fields. The add/get/reset bodies
;; and candidate private state/materializer/witness are extracted verbatim.
(require racket/class racket/set racket/list racket/dict)
(provide make-test-class openracket-binding-table-index-enabled?)
(define openracket-binding-table-index-enabled?
  (equal? (getenv "OPENRACKET_BINDING_TABLE_INDEX") "1"))
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


(define/private (add-to-bindings-table start-text start-left start-right
                                                   end-text end-left end-right)
              (cond
                [(and (object=? start-text end-text)
                      (= start-left end-left)
                      (= start-right end-right))
                 #f]
                [(and binding-index
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
                 (materialize-bindings-table! 'public-exposure)
                 bindings-table]))
(define/public (syncheck:init-arrows)
              (set! tacked-hash-table (make-hasheq))
              (set! arrow-records (make-hasheq))
              (set! bindings-table (make-hash))
              (set! binding-index
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
              (set! cleanup-texts '())
              (set! definition-targets (make-hash))
              (set! unused-require-table (make-hash)))
    (define/public (test:add a b c d e f) (add-to-bindings-table a b c d e f))
    (define/public (test:peek) bindings-table)
    (define/public (test:tooltip)
      (hash-set! arrow-records this
                 (hash '(0 . 1) (list (tooltip-info 4 5 "tip")))))
    (define/public (test:state)
      (openracket:get-binding-table-index-state))))
