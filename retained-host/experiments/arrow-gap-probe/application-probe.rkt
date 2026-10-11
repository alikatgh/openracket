#lang racket/base
;; Fixed scalar-only GUI application diagnostic. No input trace/editor/channel is retained.
(provide application-hook application-arrow-hook application-summary application-pending-box)
(define enabled? (equal? (getenv "OPENRACKET_GUI_APPLICATION_POINTS") "1"))
(define tags '(syncheck:add-arrow/name-dup/pxpy syncheck:add-tail-arrow
  syncheck:add-mouse-over-status syncheck:add-text-type syncheck:add-background-color
  syncheck:add-jump-to-definition/phase-level+space syncheck:add-require-open-menu
  syncheck:add-docs-menu syncheck:add-definition-target/phase-level+space
  syncheck:unused-binder syncheck:add-id-set syncheck:add-prefixed-require-reference
  syncheck:add-unused-require))
(define finals '(update-blue-boxes update-drawn-arrows remove-bkg-running-color set-syncheck-running-mode))
(define (tag-index tag)
  (case tag
    [(syncheck:add-arrow/name-dup/pxpy) 0] [(syncheck:add-tail-arrow) 1]
    [(syncheck:add-mouse-over-status) 2] [(syncheck:add-text-type) 3]
    [(syncheck:add-background-color) 4] [(syncheck:add-jump-to-definition/phase-level+space) 5]
    [(syncheck:add-require-open-menu) 6] [(syncheck:add-docs-menu) 7]
    [(syncheck:add-definition-target/phase-level+space) 8] [(syncheck:unused-binder) 9]
    [(syncheck:add-id-set) 10] [(syncheck:add-prefixed-require-reference) 11]
    [(syncheck:add-unused-require) 12] [else #f]))
;; Accumulators are count, sum, maximum. No per-entry or per-batch sample arrays.
(define (acc) (vector 0 0.0 0.0))
(define (add! a duration)
  (vector-set! a 0 (add1 (vector-ref a 0)))
  (when duration
    (vector-set! a 1 (+ (vector-ref a 1) duration))
    (vector-set! a 2 (max (vector-ref a 2) duration))))
(define (acc-json a timed?)
  (hasheq 'count (vector-ref a 0) 'wall_ms (if timed? (vector-ref a 1) 'null)
          'max_wall_ms (if timed? (vector-ref a 2) 'null)))
(struct record (id generation buckets final-buckets
  started ended depth index entry-start final-index final-start
  active? batch-start queued? queue-start batches waits yields resumed
  first-start last-end completed cancelled errors unknown reentrant stale unmatched
  arrow-buckets binding-true binding-false arrow-depth nested-index nested-start arrow-step arrow-binding-result) #:mutable)
;; Only the GUI handler writes this box; sampler reads the immutable scalar token.
;; It contains no application record, editor, trace, continuation or syntax root.
(define application-pending-box (box #f))
(define records (make-vector 8 #f))
(define selected-count 0)
(define dropped 0)
(define failures 0)
(define current #f)
(define (tick) (current-inexact-monotonic-milliseconds))
(define (fail! r kind)
  (set-record-errors! r (add1 (record-errors r)))
  (case kind
    [(unknown) (set-record-unknown! r (add1 (record-unknown r)))]
    [(reentrant) (set-record-reentrant! r (add1 (record-reentrant r)))]
    [(stale) (set-record-stale! r (add1 (record-stale r)))]
    [else (set-record-unmatched! r (add1 (record-unmatched r)))]))
(define (live-record? r)
  (cond [(not (record? r)) #f]
        [(or (not (eq? r current)) (record-completed r) (record-cancelled r))
         (fail! r 'stale) #f]
        [else #t]))
(define (begin! token)
  (cond
    [(not token) #f]
    [else
     (set! selected-count (add1 selected-count))
     (cond
       [(> selected-count 8) (set! dropped (add1 dropped)) #f]
       [else
        (define r (record (vector-ref token 0) (vector-ref token 1)
          (and enabled? (build-vector 13 (lambda (_) (acc))))
          (and enabled? (build-vector 4 (lambda (_) (acc))))
          0 0 0 #f #f #f #f #f #f #f #f (acc) (acc) 0 0
          #f #f #f #f 0 0 0 0 0
          (and enabled? (build-vector 3 (lambda (_) (acc)))) 0 0 0 #f #f 0 'unset))
        (when (and enabled? (unbox application-pending-box))
          (when current (fail! current 'stale))
          (set-box! application-pending-box #f))
        (set! current r)
        (vector-set! records (sub1 selected-count) r)
        r])]))
(define (batch-start! r now)
  (when (or (record-active? r) (record-queued? r)) (fail! r 'unmatched))
  (set-record-active?! r #t)
  (set-record-batch-start! r now)
  (unless (record-first-start r) (set-record-first-start! r now)))
(define (batch-end! r now)
  (unless (and (record-active? r) (zero? (record-depth r)) (not (record-final-index r)))
    (fail! r 'unmatched))
  (when (record-active? r)
    (add! (record-batches r) (and enabled? (- now (record-batch-start r)))))
  (set-record-active?! r #f)
  (set-record-batch-start! r #f)
  (set-record-last-end! r now))
(define (entry-before! r tag)
  (unless (record-active? r) (fail! r 'unmatched))
  (when (record-final-index r) (fail! r 'reentrant))
  (set-record-started! r (add1 (record-started r)))
  (set-record-depth! r (add1 (record-depth r)))
  (cond
    [(> (record-depth r) 1) (fail! r 'reentrant)]
    [else
     (define index (tag-index tag))
     (unless index (fail! r 'unknown))
     (set-record-index! r index)
     ;; Last operation before returning to the unchanged stock call.
     (set-record-entry-start! r (tick))]))
(define (entry-after! r now)
  (cond
    [(zero? (record-depth r)) (fail! r 'unmatched)]
    [else
     (set-record-ended! r (add1 (record-ended r)))
     (when (= (record-depth r) 1)
       (when (or (positive? (record-arrow-depth r)) (record-nested-index r))
         (fail! r 'unmatched))
       (when (record-index r)
         (add! (vector-ref (record-buckets r) (record-index r))
               (- now (record-entry-start r))))
       (set-record-index! r #f)
       (set-record-entry-start! r #f))
     (set-record-depth! r (sub1 (record-depth r)))]))
(define (arrow-context? r)
  (and (live-record? r)
       (cond [(not (and (record-active? r) (= (record-depth r) 1)
                        (equal? (record-index r) 0)))
              (fail! r 'unmatched) #f]
             [else #t])))
(define (arrow-select!)
  (cond
    [(or (not enabled?) (not current) (record-completed current)
         (record-cancelled current) (zero? (record-depth current))) #f]
    [(not (arrow-context? current)) #f]
    [else
     (when (positive? (record-arrow-depth current)) (fail! current 'reentrant))
     (set-record-arrow-depth! current (add1 (record-arrow-depth current)))
     (when (= (record-arrow-depth current) 1)
       (set-record-arrow-step! current 0)
       (set-record-arrow-binding-result! current 'unset))
     current]))
(define (application-arrow-hook action r [arg #f])
  ;; Fixed arity and scalar arguments only. Stock expressions are outside this
  ;; containment handler, so their exceptions/escapes propagate unchanged.
  (with-handlers ([exn:fail? (lambda (_) (set! failures (add1 failures)) #f)])
    (cond
      [(eq? action 'method-before) (arrow-select!)]
      [(or (not enabled?) (not r)) #f]
      [(not (arrow-context? r)) #f]
      [(eq? action 'method-after)
       (cond [(zero? (record-arrow-depth r)) (fail! r 'unmatched)]
             [else
              (when (and (= (record-arrow-depth r) 1)
                         (or (record-nested-index r)
                             (not (or (and (= (record-arrow-step r) 0)
                                           (eq? (record-arrow-binding-result r) 'unset))
                                      (and (= (record-arrow-step r) 2)
                                           (eq? (record-arrow-binding-result r) #f))
                                      (and (= (record-arrow-step r) 6)
                                           (eq? (record-arrow-binding-result r) #t))))))
                (fail! r 'unmatched))
              (set-record-arrow-depth! r (sub1 (record-arrow-depth r)))])]
      [(not (= (record-arrow-depth r) 1)) (fail! r 'reentrant)]
      [(eq? action 'before)
       (cond
         [(record-nested-index r) (fail! r 'reentrant)]
         [(not (and (exact-integer? arg) (<= 0 arg 2)
                    (= (record-arrow-step r) (* 2 arg))
                    (or (zero? arg) (eq? (record-arrow-binding-result r) #t)))) (fail! r 'unmatched)]
         [else
          (set-record-nested-index! r arg)
          (set-record-arrow-step! r (add1 (record-arrow-step r)))
          (set-record-nested-start! r (tick))])]
      [(memq action '(binding-after endpoint-after))
       (define now (tick))
       (define index (record-nested-index r))
       (cond
         [(not (and index
                    (if (eq? action 'binding-after)
                        (and (zero? index) (boolean? arg))
                        (and (positive? index) (equal? arg index)))))
          (fail! r 'unmatched)]
         [else
          (add! (vector-ref (record-arrow-buckets r) index)
                (- now (record-nested-start r)))
          (when (zero? index)
            (set-record-arrow-binding-result! r arg)
            (if arg (set-record-binding-true! r (add1 (record-binding-true r)))
                    (set-record-binding-false! r (add1 (record-binding-false r)))))
          (set-record-nested-index! r #f)
          (set-record-nested-start! r #f)
          (set-record-arrow-step! r (add1 (record-arrow-step r)))])]
      [else (fail! r 'unmatched)])))
(define (clear-resumed-token! r)
  ;; Callback entry clears only its own scalar wait identity. A stale callback
  ;; must never erase a newer generation's published token on a failed run.
  (define pending (unbox application-pending-box))
  (when (and (record? r) pending)
    (cond [(and (equal? (vector-ref pending 0) (record-id r))
                (equal? (vector-ref pending 1) (record-generation r))
                (equal? (vector-ref pending 2) (record-yields r)))
           (set-box! application-pending-box #f)]
          [(eq? r current) (fail! r 'unmatched)])))
(define (application-hook action r [arg #f])
  ;; Failure containment applies ONLY to scalar instrumentation, never stock work.
  ;; Fixed arity avoids a per-entry rest list/thunk; no continuation/payload roots.
  (with-handlers ([exn:fail? (lambda (_) (set! failures (add1 failures)) #f)])
    (cond
      [(eq? action 'begin) (begin! r)]
      [(and (eq? action 'callback-return) (record? r) (eq? r current)
            (or (record-completed r) (record-cancelled r))) (void)]
      [(not (begin
              (when (and enabled? (eq? action 'batch-resume))
                (clear-resumed-token! r))
              (live-record? r))) #f]
      [else
       (case action
         [(batch-start) (batch-start! r (and enabled? (tick)))]
         [(entry-before) (when enabled? (entry-before! r arg))]
         [(entry-after) (when enabled? (entry-after! r (tick)))]
         [(final-before)
          (when enabled?
            (unless (record-active? r) (fail! r 'unmatched))
            (when (or (record-final-index r) (positive? (record-depth r))) (fail! r 'reentrant))
            (set-record-final-index! r arg)
            (set-record-final-start! r (tick)))]
         [(final-after)
          (when enabled?
            (define now (tick))
            (if (equal? (record-final-index r) arg)
                (add! (vector-ref (record-final-buckets r) arg) (- now (record-final-start r)))
                (fail! r 'unmatched))
            (set-record-final-index! r #f)
            (set-record-final-start! r #f))]
         [(batch-yield)
          ;; Called AFTER the stock queue-callback returns: scheduling is active work.
          (define now (and enabled? (tick)))
          (batch-end! r now)
          (set-record-yields! r (add1 (record-yields r)))
          (set-record-queued?! r #t)
          (set-record-queue-start! r now)
          (when enabled?
            (when (unbox application-pending-box) (fail! r 'unmatched))
            (set-box! application-pending-box
                      (vector-immutable (record-id r) (record-generation r)
                                        (record-yields r) now)))]
         [(batch-resume)
          ;; First scalar hook in the unchanged callback, before its stock liveness test.
          (define now (and enabled? (tick)))
          (unless (record-queued? r) (fail! r 'unmatched))
          (when (record-queued? r)
            (add! (record-waits r) (and enabled? (- now (record-queue-start r)))))
          (set-record-queued?! r #f)
          (set-record-queue-start! r #f)
          (set-record-resumed! r (add1 (record-resumed r)))
          (batch-start! r now)]
         [(callback-return)
          ;; Successful loop return already closed the batch. A skipped callback did not.
          (when (record-active? r)
            (batch-end! r (and enabled? (tick)))
            (set-record-cancelled! r #t))]
         [(cancel)
          (batch-end! r (and enabled? (tick)))
          (set-record-cancelled! r #t)]
         [(finish)
          (unless arg (fail! r 'stale))
          (batch-end! r (and enabled? (tick)))
          (set-record-completed! r (and arg #t))]
         [else (fail! r 'unmatched)])
       (void)])))
(define (record-json r)
  (hasheq 'request_id (record-id r) 'application_generation (record-generation r)
    'completed (record-completed r) 'cancelled (record-cancelled r)
    'errors (record-errors r) 'unknown_tags (record-unknown r)
    'reentrant_entries (record-reentrant r) 'stale_events (record-stale r)
    'unmatched_events (record-unmatched r)
    'entries_started (record-started r) 'entries_completed (record-ended r)
    'open_entry_depth (record-depth r) 'open_final (and (record-final-index r) #t)
    'active_batch (record-active? r) 'queued_wait (record-queued? r)
    'yield_count (record-yields r) 'resume_count (record-resumed r)
    'batch_active (acc-json (record-batches r) enabled?)
    'requeue_wait (acc-json (record-waits r) enabled?)
    'first_batch_start_ms (or (record-first-start r) 'null)
    'last_batch_end_ms (or (record-last-end r) 'null)
     'arrow_detail (if enabled?
      (hasheq 'binding_true (record-binding-true r) 'binding_false (record-binding-false r)
              'open_method_depth (record-arrow-depth r)
              'open_nested (and (record-nested-index r) #t)
              'operations
              (for/list ([name (in-list '(add-to-bindings-table start-add-to-range/key end-add-to-range/key))]
                         [a (in-vector (record-arrow-buckets r))])
                (hash-set (acc-json a #t) 'operation (symbol->string name))))
      'null)
    'tag_buckets (if enabled?
      (for/list ([tag (in-list tags)] [a (in-vector (record-buckets r))])
        (hash-set (acc-json a #t) 'tag (symbol->string tag))) '())
    'final_updates (if enabled?
      (for/list ([name (in-list finals)] [a (in-vector (record-final-buckets r))])
        (hash-set (acc-json a #t) 'operation (symbol->string name))) '())))
(define (application-summary [quiescent? #f])
  (hasheq 'schema_version 1 'kind "genuine-gui-annotation-application"
    'probe_enabled enabled? 'common_batch_counts #t 'snapshot_quiescent quiescent?
    'selected_count selected-count 'dropped_records dropped 'observer_failures failures
    'records (for/list ([r (in-vector records)] #:when r) (record-json r))
    'scope "Inclusive observed call-wall milliseconds, including pauses/reentrancy; not exclusive CPU. Batch active includes loop/instrumentation/scheduling. Requeue wait starts after queue-callback returns."
    'completion_scope "Synchronous application only; blue-box coroutine/cache/timer, arrow timer/paint and running-indicator refresh can remain deferred. Pointer-dependent final work is unmeasured context."))
