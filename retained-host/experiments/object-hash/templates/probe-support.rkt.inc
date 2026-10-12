;; SOURCE-ONLY DIAGNOSTIC. This is not the proposed hash optimization.
;; Only weak identities and bounded scalar observations survive a call.
(provide openracket-object-hash-probe-enabled?
         openracket-object-hash-probe-instance
         openracket-object-hash-probe-build-id
         openracket-object-hash-probe-arm!
         openracket-object-hash-probe-stop!
         openracket-object-hash-probe-state)
(define openracket-object-hash-probe-enabled?
  (equal? (getenv "OPENRACKET_OBJECT_HASH_PROBE") "1"))
(define openracket-object-hash-probe-instance (gensym 'object-hash-probe-v1))
(define openracket-object-hash-probe-build-id "@@BUILD-ID@@")
(define probe-match-cap 128)
(define probe-attempt-cap 20000)
(define probe-started? #f)
(define probe-active? #f)
(define probe-stop-reason 'not-armed)
(define probe-definitions #f)
(define probe-interactions #f)
(define probe-handler #f)
(define probe-attempts 0)
(define probe-matches 0)
(define probe-diagnostic-faults 0)
;; @@COUNTER-DEFINITIONS@@

(define (openracket-object-hash-probe-stop! [reason 'host-complete])
  (unless (memq reason '(host-complete host-aborted match-cap attempt-cap diagnostic-fault))
    (error 'object-hash-probe "Unsupported stop reason"))
  (when probe-active? (set! probe-stop-reason reason))
  (set! probe-active? #f)
  (set! probe-definitions #f)
  (set! probe-interactions #f)
  (set! probe-handler #f)
  (void))

(define (openracket-object-hash-probe-arm! definitions interactions handler)
  (unless (and openracket-object-hash-probe-enabled? (not probe-started?)
               (object? definitions) (object? interactions)
               (not (eq? definitions interactions))
               (thread? handler) (eq? handler (current-thread)))
    (error 'object-hash-probe "Requires enabled, once-only registration on the supplied handler"))
  (set! probe-definitions (make-weak-box definitions))
  (set! probe-interactions (make-weak-box interactions))
  (set! probe-handler (make-weak-box handler))
  (set! probe-started? #t)
  (set! probe-active? #t)
  (set! probe-stop-reason 'armed)
  (void))

;; These handlers cover diagnostic work only, never the original conversion,
;; sentinel scan, recursive callback or identity hash. No caught value is stored.
(define (probe-diagnostic-failure? v) (not (exn:break? v)))
(define (probe-fault! ignored)
  (set! probe-diagnostic-faults (add1 probe-diagnostic-faults))
  (openracket-object-hash-probe-stop! 'diagnostic-fault)
  #f)
(define (probe-claim! obj)
  (with-handlers ([probe-diagnostic-failure? probe-fault!])
    (cond
      [(not (and probe-active?
                 (eq? (current-thread) (weak-box-value probe-handler)))) #f]
      [else
       ;; The denominator is registered-handler default-hash entries only.
       (set! probe-attempts (add1 probe-attempts))
       (define role
         (cond [(eq? obj (weak-box-value probe-definitions)) 0]
               [(eq? obj (weak-box-value probe-interactions)) 1]
               [else #f]))
       (define sample
         (and role
              (let ([kind
                     (cond [(impersonator? obj) 0]
                           [else
                            ;; Do not unwrap or replace the call's inspector.
                            (with-handlers ([probe-diagnostic-failure? (lambda (v) 3)])
                              (define-values (type skipped?) (struct-info obj))
                              (if skipped? 1 2))])])
                (set! probe-matches (add1 probe-matches))
                (define category (+ (* role 4) kind))
                ;; @@COUNT-MATCH@@
                category)))
       (cond [(>= probe-matches probe-match-cap)
              (openracket-object-hash-probe-stop! 'match-cap)]
             [(>= probe-attempts probe-attempt-cap)
              (openracket-object-hash-probe-stop! 'attempt-cap)])
       sample])))

(define (probe-note-vector! category length)
  (with-handlers ([probe-diagnostic-failure? probe-fault!])
    ;; Only length is observed; no vector is passed to this procedure or stored.
    ;; @@COUNT-VECTOR@@
    (void)))
(define (probe-note-result! category visible?)
  (with-handlers ([probe-diagnostic-failure? probe-fault!])
    ;; A completed false helper result selects the existing eq-hash-code branch.
    ;; @@COUNT-RETURN@@
    (unless visible?
      ;; @@COUNT-FALLBACK@@
      (void))
    (void)))

(define (openracket-object-hash-probe-state)
  (hasheq 'schema "openracket-object-hash-probe/v1"
          'enabled openracket-object-hash-probe-enabled?
          'instance (symbol->string openracket-object-hash-probe-instance)
          'started probe-started? 'active probe-active?
          'stop_reason (symbol->string probe-stop-reason)
          'attempt_cap probe-attempt-cap 'match_cap probe-match-cap
          'attempts probe-attempts 'matches probe-matches
          'diagnostic_faults probe-diagnostic-faults
          'scope "registered-handler-default-hash-entries"
          'allocation_unit "original-struct-vector-slots"
          'eligibility (cond [(positive? probe-diagnostic-faults) "unresolved-diagnostic-fault"]
                             [(positive? (+ probe-definitions-inspection-failed-matches
                                            probe-interactions-inspection-failed-matches))
                              "unresolved-inspection-failure"]
                             [(zero? probe-matches) "unresolved-no-matching-calls"]
                             [(positive? (+ probe-definitions-skipped-fallbacks
                                            probe-interactions-skipped-fallbacks))
                              "plain-skipped-original-fallback-observed"]
                             [else "no-plain-skipped-fallback-observed-in-bounded-sample"])
          ;; @@STATE-COUNTERS@@
          ))
