#lang racket/base
;; Generated from the actual pinned gui.rkt forms. Only the surrounding GUI
;; dependencies are replaced by inert test fields. The add/get/reset bodies
;; and candidate private state/witness are extracted verbatim in normal modules.
;; Explicit *-fault modules insert only the declared deterministic test hooks.
(require racket/class racket/set racket/list racket/dict)
(provide make-test-class openracket-binding-table-eager-enabled?)
(define openracket-binding-table-eager-enabled? #f)
(struct tooltip-info (pos-left pos-right msg) #:transparent)
(define (make-test-class super%)
  (class super%
    (super-new)
    (define tacked-hash-table #f)
    (define arrow-records (make-hasheq))
    (define cleanup-texts #f)
    (define definition-targets (make-hash))
    (define unused-require-table (make-hash))
(define test-after-public-write void)
(define test-after-first-cache void)
(define test-after-set-add void)
            (define bindings-table (make-hash))


(define/private (add-to-bindings-table start-text start-left start-right
                                                   end-text end-left end-right)
              (cond
                [(and (object=? start-text end-text)
                      (= start-left end-left)
                      (= start-right end-right))
                 #f]
                [else
                 (define key (list start-text start-left start-right))
                 (define priors (hash-ref bindings-table key (λ () (set))))
                 (define new (list end-text end-left end-right))
                 (cond
                   [(set-member? priors new)
                    #f]
                   [else
                    (hash-set! bindings-table key (let ([result (set-add priors new)]) (test-after-set-add) result))
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
                 bindings-table]))
(define/public (syncheck:init-arrows)
              (set! tacked-hash-table (make-hasheq))
              (set! arrow-records (make-hasheq))
              (set! bindings-table (make-hash))
              (set! cleanup-texts '())
              (set! definition-targets (make-hash))
              (set! unused-require-table (make-hash)))
    (define/public (test:add a b c d e f) (add-to-bindings-table a b c d e f))
    (define/public (test:peek) bindings-table)
    (define/public (test:tooltip)
      (hash-set! arrow-records this
                 (hash '(0 . 1) (list (tooltip-info 4 5 "tip")))))
    (define/public (test:state)
      #f)

    (define/public (test:arm-public! thunk) (set! test-after-public-write thunk))
    (define/public (test:arm-cache! thunk) (set! test-after-first-cache thunk))
    (define/public (test:arm-set-add! thunk) (set! test-after-set-add thunk))
))
