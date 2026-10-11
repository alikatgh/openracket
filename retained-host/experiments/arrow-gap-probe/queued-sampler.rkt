#lang racket/base
;; Bounded diagnostic only. The GUI writes an immutable scalar pending token;
;; this observer reads it without locks, retaining no editor, syntax, trace, or
;; continuation marks. There are no stock logger/custodian changes.
(provide sampler-start! sampler-stop! sampler-done-evt sampler-summary)

(define sample-period-ms 100.0)
(define attempt-cap 1024)
(define frame-cap 8)
(define text-cap 240)
(struct sampler (worker stop-semaphore enabled result started) #:mutable)

(define counter-names
  '(attempts stored_samples race_discarded stop_discarded invalid_token_discarded
    attempt_errors_discarded
    capture_errors absent_handlers collected_handlers dead_handlers invalid_handlers
    died_during_capture missing_frames frames_truncated text_fields_truncated
    usable_source_samples cadence_ticks idle_ticks early_wakes missed_cadence_ticks
    scheduling_delay_ms max_scheduling_delay_ms capture_duration_ms
    max_capture_duration_ms sampler_errors))
(define (tick) (current-inexact-monotonic-milliseconds))
(define (clip s)
  ;; Copies into immutable bounded text even when test context strings are mutable.
  (string->immutable-string (substring s 0 (min text-cap (string-length s)))))
(define (error-text e)
  (if (exn? e) (clip (exn-message e)) "<non-exception raised value>"))
(define (error-truncated? e)
  (and (exn? e) (> (string-length (exn-message e)) text-cap)))
(define (any-raised? _) #t)
(define (finite-nonnegative-real? v)
  (and (real? v) (<= 0 v) (< v +inf.0)))
(define (pending-token? v)
  (and (vector? v) (immutable? v) (= (vector-length v) 4)
       (exact-nonnegative-integer? (vector-ref v 0))
       (exact-nonnegative-integer? (vector-ref v 1))
       (exact-nonnegative-integer? (vector-ref v 2))
       (finite-nonnegative-real? (vector-ref v 3))))
(define (source-text+kind source)
  (cond [(path? source) (values (path->string source) "path")]
        [(string? source) (values source "string")]
        [(symbol? source) (values (symbol->string source) "symbol")]
        [(not source) (values #f "missing")]
        [else (values #f "unsupported")]))
(define (name-text name)
  (cond [(symbol? name) (symbol->string name)]
        [(string? name) name]
        [(not name) #f]
        [else "<non-symbol-name>"]))
(define (render-context context)
  ;; The public conversion may create an arbitrarily deep transient context.
  ;; Walk at most eight cells and keep only bounded immutable text/scalars.
  (let loop ([rest context] [left frame-cap] [out '()]
             [text-truncations 0] [missing-sources 0] [usable-sources 0])
    (cond
      [(or (null? rest) (zero? left))
       (hasheq 'frames (reverse out) 'frames_truncated (not (null? rest))
               'text_fields_truncated text-truncations
               'missing_frame_sources missing-sources
               'usable_source_frames usable-sources)]
      [else
       (unless (and (pair? rest) (pair? (car rest)))
         (error 'queued-sampler "Malformed continuation context"))
       (define frame (car rest))
       (define name (name-text (car frame)))
       (define loc (cdr frame))
       (unless (or (not loc) (srcloc? loc))
         (error 'queued-sampler "Malformed continuation source location"))
       (define-values (source kind) (source-text+kind (and loc (srcloc-source loc))))
       (define name-truncated? (and name (> (string-length name) text-cap)))
       (define source-truncated? (and source (> (string-length source) text-cap)))
       (define usable? (and source (positive? (string-length source))))
       (define row
         (hasheq 'name (if name (clip name) 'null)
                 'source (if source (clip source) 'null)
                 'name_truncated (and name-truncated? #t)
                 'source_truncated (and source-truncated? #t)
                 'source_kind kind
                 'line (or (and loc (srcloc-line loc)) 'null)
                 'column (or (and loc (srcloc-column loc)) 'null)
                 'position (or (and loc (srcloc-position loc)) 'null)))
       (loop (cdr rest) (sub1 left) (cons row out)
             (+ text-truncations (if name-truncated? 1 0) (if source-truncated? 1 0))
             (+ missing-sources (if usable? 0 1))
             (+ usable-sources (if usable? 1 0)))])))
(define (empty-capture state [message 'null] [truncated? #f] [performed? #f])
  (hasheq 'state state 'capture_performed performed? 'frames '()
          'frames_truncated #f 'text_fields_truncated 0
          'missing_frame_sources 0 'usable_source_frames 0
          'error message 'error_truncated truncated?))
(define (public-context actual)
  ;; Established public API, also used by stock abort-job.
  (continuation-mark-set->context (continuation-marks actual)))
(define (capture-render weak-handler capture render)
  ;; `actual` is strong only for this call, never across a wait or in a row.
  (define performed? #f)
  (with-handlers ([any-raised?
                   (lambda (e) (empty-capture "sampling_error" (error-text e)
                                              (error-truncated? e) performed?))])
    (define actual (and weak-handler (weak-box-value weak-handler)))
    (cond [(not weak-handler) (empty-capture "not_registered")]
          [(not actual) (empty-capture "weak_reference_collected")]
          [(not (thread? actual)) (empty-capture "invalid_handler")]
          [(thread-dead? actual) (empty-capture "dead")]
          [else
           (set! performed? #t)
           (define rendered (render (capture actual)))
           (hash-set
            (hash-set
             (hash-set
              (hash-set rendered 'state (if (thread-dead? actual)
                                           "died_during_sample" "live_at_sample"))
              'capture_performed #t)
             'error 'null)
            'error_truncated #f)])))
(define (default-wait planned stop-event clock)
  (sync/timeout (max 0 (/ (- planned (clock)) 1000.0)) stop-event))
(define (stop-requested? h)
  (and (sync/timeout 0 (semaphore-peek-evt (sampler-stop-semaphore h))) #t))
(define (base-summary h quiescent?)
  (hasheq 'schema_version 1 'kind "genuine-gui-pending-continuation-samples"
          'enabled (sampler-enabled h) 'snapshot_quiescent quiescent?
          'sample_period_ms sample-period-ms 'attempt_cap attempt-cap
          'frame_cap frame-cap 'text_cap text-cap
          'started_monotonic_ms (sampler-started h)
          'scope "Sparse wall-clock-biased raw stacks while a replay continuation was pending; not complete gap ownership or CPU shares"
          'counter_scope "Capture errors, handler states, missing frames and truncations count all captures, including subsequently discarded races or stops"
          'missed_cadence_scope "Scheduled instants after this tick and at or before capture completion are skipped, without catch-up samples"
          'transient_cost_bound "Retained attempts, frames and text are capped; continuation capture/conversion, rendering time and scheduler delay are not hard-bounded"
          'thread_references "Only a weak GUI-handler reference survives between samples"
          'stock_logger_subscription #f))
(define (start/internal pending-box weak-handler enabled? clock wait capture render)
  (unless (and (box? pending-box) (not (immutable? pending-box)))
    (raise-argument-error 'sampler-start! "mutable box?" pending-box))
  (unless (or (not weak-handler) (weak-box? weak-handler))
    (raise-argument-error 'sampler-start! "(or/c #f weak-box?)" weak-handler))
  (define started (if enabled? (clock) 'null))
  (define h (sampler #f (make-semaphore 0) (and enabled? #t) (box #f) started))
  ;; Only the sampler thread mutates these counters/rows. Readers can access only
  ;; the immutable final result published before the worker exits.
  (define counters (make-hasheq))
  (for ([key (in-list counter-names)]) (hash-set! counters key 0))
  (define samples '())
  (define reason (if enabled? "running" "disabled"))
  (define sampler-error 'null)
  (define (count key) (hash-ref counters key))
  (define (add! key [amount 1]) (hash-set! counters key (+ (count key) amount)))
  (define (max! key value) (hash-set! counters key (max (count key) value)))
  (define (finish!)
    (define finished
      (if enabled?
          (with-handlers ([any-raised?
                           (lambda (e)
                             (set! reason "sampler_error")
                             (set! sampler-error (error-text e))
                             (add! 'sampler_errors)
                             'null)])
            (clock))
          'null))
    (define incomplete?
      (and enabled?
           (or (not (equal? reason "stopped"))
               (positive? (count 'sampler_errors)) (positive? (count 'capture_errors))
               (positive? (count 'invalid_token_discarded))
               (for/or ([key '(absent_handlers collected_handlers dead_handlers
                              invalid_handlers died_during_capture)])
                 (positive? (count key)))
               (zero? (count 'usable_source_samples)))))
    (define base
      (hash-set
       (hash-set
        (hash-set
         (hash-set
          (hash-set
           (hash-set
            (hash-set (base-summary h #t) 'finished_monotonic_ms finished)
            'stopped (equal? reason "stopped"))
           'capped (>= (count 'attempts) attempt-cap))
          'incomplete (and incomplete? #t))
         'sampler_error sampler-error)
        'samples (reverse samples))
       'termination reason))
    (set-box! (sampler-result h)
              (for/fold ([out base]) ([(key value) (in-hash counters)])
                (hash-set out key value))))
  (define (observe-capture! data)
    (define state (hash-ref data 'state))
    (cond [(equal? state "sampling_error") (add! 'capture_errors)]
          [(equal? state "not_registered") (add! 'absent_handlers)]
          [(equal? state "weak_reference_collected") (add! 'collected_handlers)]
          [(equal? state "invalid_handler") (add! 'invalid_handlers)]
          [(equal? state "dead") (add! 'dead_handlers)]
          [(equal? state "died_during_sample") (add! 'died_during_capture)])
    (when (null? (hash-ref data 'frames)) (add! 'missing_frames))
    (when (hash-ref data 'frames_truncated) (add! 'frames_truncated))
    (add! 'text_fields_truncated (hash-ref data 'text_fields_truncated)))
  (define (missed planned finished)
    (inexact->exact (floor (/ (max 0 (- finished planned)) sample-period-ms))))
  (define (attempt! token planned actual delay)
    (add! 'attempts)
    (define settled? #f)
    (define (dispose! key) (add! key) (set! settled? #t))
    (with-handlers ([any-raised?
                     (lambda (e)
                       (unless settled? (add! 'attempt_errors_discarded))
                       (raise e))])
     (cond
      [(not (pending-token? token)) (dispose! 'invalid_token_discarded) actual]
      [else
       (define capture-started (clock))
       (cond
         ;; Re-read the same immutable identity immediately before sampling.
         [(not (eq? token (unbox pending-box)))
          (dispose! 'race_discarded) capture-started]
         [(stop-requested? h) (dispose! 'stop_discarded) capture-started]
         [else
          (define data (capture-render weak-handler capture render))
          (define capture-finished (clock))
          (define duration (max 0 (- capture-finished capture-started)))
          ;; The identity check covers capture AND rendering, not only capture.
          (define current? (eq? token (unbox pending-box)))
          (add! 'capture_duration_ms duration)
          (max! 'max_capture_duration_ms duration)
          (observe-capture! data)
          (cond
            [(not current?) (dispose! 'race_discarded)]
            [(stop-requested? h) (dispose! 'stop_discarded)]
            [else
             (define row
               (for/fold ([out
                           (hasheq 'request_id (vector-ref token 0)
                                   'application_generation (vector-ref token 1)
                                   'wait_ordinal (vector-ref token 2)
                                   'queued_monotonic_ms (vector-ref token 3)
                                   'planned_monotonic_ms planned 'actual_monotonic_ms actual
                                   'capture_started_monotonic_ms capture-started
                                   'capture_finished_monotonic_ms capture-finished
                                   'capture_duration_ms duration 'scheduling_delay_ms delay
                                   'missed_before_capture_ticks (missed planned actual)
                                   'missed_cadence_ticks (missed planned capture-finished))])
                         ([(key value) (in-hash data)])
                 (hash-set out key value)))
             (set! samples (cons row samples))
             (dispose! 'stored_samples)
             (when (positive? (hash-ref data 'usable_source_frames))
               (add! 'usable_source_samples))])
          capture-finished])])))
  (define (run!)
    (with-handlers ([any-raised?
                     (lambda (e)
                       (set! reason "sampler_error")
                       (set! sampler-error (error-text e))
                       (add! 'sampler_errors))])
      (let loop ([planned (+ started sample-period-ms)])
        (cond
          [(>= (count 'attempts) attempt-cap) (set! reason "capped")]
          [(stop-requested? h) (set! reason "stopped")]
          [else
           (wait planned (semaphore-peek-evt (sampler-stop-semaphore h)) clock)
           (cond
             [(stop-requested? h) (set! reason "stopped")]
             [else
              (define actual (clock))
              (cond
                [(< actual planned) (add! 'early_wakes) (loop planned)]
                [else
                 (add! 'cadence_ticks)
                 (define delay (- actual planned))
                 (add! 'scheduling_delay_ms delay)
                 (max! 'max_scheduling_delay_ms delay)
                 (define token (unbox pending-box))
                 (define finished
                   (if token (attempt! token planned actual delay)
                       (begin (add! 'idle_ticks) actual)))
                 (define skipped (missed planned finished))
                 (add! 'missed_cadence_ticks skipped)
                 ;; Preserve the original cadence; never emit catch-up bursts.
                 (loop (+ planned (* (add1 skipped) sample-period-ms)))])])]))))
  (cond [enabled?
         (set-sampler-worker! h
           (thread (lambda () (dynamic-wind void run! finish!))))]
        [else (finish!)])
  h)
(define (sampler-start! pending-box weak-handler)
  (start/internal pending-box weak-handler
                  (equal? (getenv "OPENRACKET_GUI_APPLICATION_POINTS") "1")
                  tick default-wait public-context render-context))
(define (sampler-stop! h)
  (unless (sampler? h) (raise-argument-error 'sampler-stop! "sampler?" h))
  ;; Cooperative and nonblocking. Semaphore-peek remains ready; no thread kill,
  ;; synchronous command/reply, spin lock, CAS, or custodian operation is used.
  (unless (stop-requested? h) (semaphore-post (sampler-stop-semaphore h)))
  (void))
(define (sampler-done-evt h)
  (unless (sampler? h) (raise-argument-error 'sampler-done-evt "sampler?" h))
  (if (sampler-worker h) (thread-dead-evt (sampler-worker h)) always-evt))
(define (sampler-summary h [quiescent? #t])
  (unless (sampler? h) (raise-argument-error 'sampler-summary "sampler?" h))
  (define joined? (and (sync/timeout 0 (sampler-done-evt h)) #t))
  (cond
    [(and quiescent? joined? (unbox (sampler-result h))) (unbox (sampler-result h))]
    [else
     ;; Do not inspect mutable counters, even when a caller incorrectly claims
     ;; quiescence. A failed/deadline snapshot remains explicit and unusable.
     (define partial
       (hasheq 'finished_monotonic_ms 'null 'stopped #f 'capped #f
               'incomplete #t 'termination "not_joined" 'sampler_error 'null
               'samples '()))
     (for/fold ([out (for/fold ([base (base-summary h #f)])
                              ([(key value) (in-hash partial)])
                      (hash-set base key value))])
               ([key (in-list counter-names)])
       (hash-set out key 'null))]))

;; Deterministic native tests can control time/capture without changing any
;; production bounds or environment switches. No injected hook is exported above.
(module+ test-support
  (provide sampler-start/injected! render-context)
  (define (sampler-start/injected! pending-box weak-handler
                                  #:enabled? [enabled? #t]
                                  #:clock [clock tick]
                                  #:wait [wait default-wait]
                                  #:capture [capture public-context]
                                  #:render [render render-context])
    (start/internal pending-box weak-handler enabled? clock wait capture render)))
