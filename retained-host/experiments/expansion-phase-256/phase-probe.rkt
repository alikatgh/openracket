#lang racket/base
;; Replay-only diagnostic. No stock logger subscriptions or payload retention.
(require racket/async-channel racket/match syntax/modresolve file/sha1)
(provide phase-hook! start-probe! existing-service-thread-reference)

(define sample-period-ms 250.0)
(define sample-cap 256)
(define point-cap 128)
(define frame-cap 8)
(define text-cap 240)
(define inbox (make-async-channel 128))
(define commands (make-channel))
(define generation (box 0))
(define dropped-input (box 0))
(define thread-generation (make-parameter #f))
(define controller #f)
(define (add-one! cell)
  (let loop ()
    (define old (unbox cell))
    (if (box-cas! cell old (add1 old)) (add1 old) (loop))))
(define (tick) (current-inexact-monotonic-milliseconds))
(define (metrics)
  (hasheq 'monotonic_ms (tick)
          'process_allocation_counter_bytes (current-memory-use 'cumulative)
          'gc_counter_ms_observed_from_worker_place (current-gc-milliseconds)
          'process_cpu_counter_ms_all_places (current-process-milliseconds)
          'managed_bytes_observed_from_worker_place (current-memory-use)))
(define (clip text) (substring text 0 (min text-cap (string-length text))))
(define (source-text v)
  (cond [(path? v) (clip (path->string v))]
        [(string? v) (clip v)] [(symbol? v) (clip (symbol->string v))]
        [(not v) #f] [else "<non-path-source>"]))
(define (source-truncated? v)
  (cond [(path? v) (> (string-length (path->string v)) text-cap)]
        [(string? v) (> (string-length v) text-cap)]
        [(symbol? v) (> (string-length (symbol->string v)) text-cap)]
        [else #f]))

;; Bound at module instantiation in each patched stock module, before the worker
;; switches namespaces. Job-scoped registered objects are the calling threads.
(define (phase-hook! label)
  (unless controller (error 'phase-probe "Hook called before probe readiness"))
  (when (eq? label 'worker-start)
    (thread-generation (add-one! generation)))
  (define gen (thread-generation))
  (unless gen (error 'phase-probe "Hook has no inherited job generation"))
  (define role (case label [(worker-start) 'working-thread] [(monitor-start) 'check-syntax-monitor] [else #f]))
  (define event (vector label gen (metrics) (and role (cons role (make-weak-box (current-thread))))))
  ;; Never block a stock job on diagnostic delivery. Overflow is explicitly counted.
  (unless (sync/timeout 0 (async-channel-put-evt inbox event)) (add-one! dropped-input))
  (void))

(define (thread-sample role ref)
  (define actual (and ref (weak-box-value ref)))
  (define started (tick))
  (define base (hasheq 'role (symbol->string role) 'sample_started_monotonic_ms started))
  (cond
    [(not ref) (hash-set base 'state "not_registered")]
    [(not actual) (hash-set base 'state "weak_reference_collected")]
    [(thread-dead? actual) (hash-set base 'state "dead")]
    [else
     (with-handlers ([exn:fail? (lambda (e)
                                (hash-set (hash-set (hash-set base 'state "sampling_error")
                                                    'error (clip (exn-message e)))
                                          'error_truncated (> (string-length (exn-message e)) text-cap)))])
       ;; This is the exact public API already used by stock abort-job. Conversion
       ;; is approximate and its transient work is NOT bounded by frame-cap.
       (define context (continuation-mark-set->context (continuation-marks actual)))
       (define-values (frames truncated?)
         (let loop ([rest context] [left frame-cap] [out '()])
           (cond [(or (null? rest) (zero? left)) (values (reverse out) (pair? rest))]
                 [else
                  (define frame (car rest))
                  (define name (car frame))
                  (define loc (cdr frame))
                  (define row
                    (hasheq 'name (and name (clip (symbol->string name)))
                            'source (and loc (source-text (srcloc-source loc)))
                            'name_truncated (and name (> (string-length (symbol->string name)) text-cap))
                            'source_truncated (and loc (source-truncated? (srcloc-source loc)))
                            'line (and loc (srcloc-line loc))
                            'column (and loc (srcloc-column loc))
                            'position (and loc (srcloc-position loc))))
                  (loop (cdr rest) (sub1 left) (cons row out))])))
       (hash-set
        (hash-set
         (hash-set
          (hash-set base 'state (if (thread-dead? actual) "died_during_sample" "live_at_sample"))
          'frames frames)
         'frames_truncated truncated?)
        'sample_finished_monotonic_ms (tick)))]))

;; Read only the already-instantiated registry dependency. module->namespace does
;; not instantiate an absent module. Never dynamic-require xref, export its private
;; binding, send a lookup request, or retain its namespace/continuation marks.
(define xref-source-pin "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7")
(define (existing-service-thread-reference module-path expected-pin)
  (with-handlers ([exn:fail?
                   (lambda (e)
                     (values #f (hasheq 'status "unavailable"
                                        'error (clip (exn-message e))
                                        'error_truncated (> (string-length (exn-message e)) text-cap))))])
    (define source (resolve-module-path module-path #f))
    (unless (path? source) (error 'phase-probe "xref did not resolve to a source file"))
    (define sha (call-with-input-file source
                 (lambda (in) (bytes->hex-string (sha256-bytes in)))))
    (unless (equal? sha expected-pin) (error 'phase-probe "xref source pin mismatch"))
    ;; The namespace is a temporary argument only. Only the weak box escapes.
    (define ref
      (let ([actual (namespace-variable-value
                     'thd #t (lambda () (error 'phase-probe "xref private thd unavailable"))
                     (module->namespace module-path))])
        (unless (thread? actual) (error 'phase-probe "xref thd is not a thread"))
        (when (thread-dead? actual) (error 'phase-probe "xref service thread is already dead"))
        (make-weak-box actual)))
    (values ref (hasheq 'status "registered_existing_service_thread"
                       'source (clip (path->string source)) 'source_sha256 sha
                       'source_truncated (> (string-length (path->string source)) text-cap)
                       'registration_metrics (metrics)
                       'lifetime "weak service reference; per-trial registration reset; cleared on stop"
                       'scope "Shared service observed during the active request; generation is observation interval, not proof of request ownership"))))

(define (start-probe! #:xref-module [xref-module 'drracket/private/syncheck/xref]
                      #:xref-pin [xref-pin xref-source-pin])
  (unless (and (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
               (equal? (getenv "OPENRACKET_EXPANSION_PHASE_PROBE") "1")
               (not (equal? (getenv "OPENRACKET_EXPANSION_CAPTURE") "1")))
    (error 'phase-probe "Only a separately enabled replay may start this observer"))
  (when controller (error 'phase-probe "Probe already initialized"))
  ;; Readiness runs under the worker's original custodian, before any limited job.
  ;; Only this surviving controller owns buffers/weak registrations.
  ;; Called only from post-registry readiness. Test keywords permit a fake
  ;; already-instantiated module; production has no environment override.
  (define-values (xref-ref xref-registration)
    (existing-service-thread-reference xref-module xref-pin))
  (define active? #f)
  (define trial 0)
  (define expected-generation 0)
  (define refs (make-hasheq))
  (define points (make-vector point-cap #f))
  (define samples (make-vector sample-cap #f))
  (define points-used 0)
  (define samples-used 0)
  (define points-dropped 0)
  (define samples-dropped 0)
  (define stale-events 0)
  (define dropped-before 0)
  (define begin-metrics #f)
  (define end-metrics #f)
  (define registrations (make-hasheq))
  (define latest-worker-phase #f)
  (define latest-monitor-phase #f)
  (define (accept-event! event)
    (match-define (vector label gen counters registration) event)
    (cond
      [(and active? (= gen expected-generation))
       (when registration
         (hash-set! refs (car registration) (cdr registration))
         (hash-set! registrations (car registration) #t))
       (if (regexp-match? #rx"^monitor-" (symbol->string label))
           (set! latest-monitor-phase (symbol->string label))
           (set! latest-worker-phase (symbol->string label)))
       (if (< points-used point-cap)
           (begin
             (vector-set! points points-used
                          (hasheq 'phase (symbol->string label) 'job_generation gen 'trial trial
                                  'source_metrics counters 'received_monotonic_ms (tick)))
             (set! points-used (add1 points-used)))
           (set! points-dropped (add1 points-dropped)))]
      [else (set! stale-events (add1 stale-events))]))
  (define (drain!)
    ;; The queue itself is bounded, and end/begin drains never loop indefinitely.
    (for ([i (in-range 128)])
      (define event (sync/timeout 0 inbox))
      (when event (accept-event! event))))
  (define (sample!)
    (when active?
      (cond
        [(< samples-used sample-cap)
         (define before (metrics))
         (define threads
           (for/list ([role (in-list '(working-thread check-syntax-monitor xref-service))])
             (thread-sample role (hash-ref refs role #f))))
         (define after (metrics))
         (vector-set! samples samples-used
                      (hasheq 'trial trial 'job_generation expected-generation
                              'before before 'after after 'threads threads
                              'latest_received_worker_phase latest-worker-phase
                              'latest_received_monitor_phase latest-monitor-phase))
         (set! samples-used (add1 samples-used))]
        [else (set! samples-dropped (add1 samples-dropped))])))
  (define (snapshot)
    (define worker-registered? (hash-ref registrations 'working-thread #f))
    (define monitor-registered? (hash-ref registrations 'check-syntax-monitor #f))
    (define xref-registered? (hash-ref registrations 'xref-service #f))
    (define usable-monitor-frames?
      (for/or ([i (in-range samples-used)])
        (for/or ([row (in-list (hash-ref (vector-ref samples i) 'threads))])
          (and (equal? (hash-ref row 'role) "check-syntax-monitor")
               (pair? (hash-ref row 'frames '()))))))
    (define usable-xref-frames?
      (for/or ([i (in-range samples-used)])
        (for/or ([row (in-list (hash-ref (vector-ref samples i) 'threads))])
          (and (equal? (hash-ref row 'role) "xref-service")
               (pair? (hash-ref row 'frames '()))))))
    (hasheq 'enabled #t 'trial trial 'job_generation expected-generation 'active active?
            'attribution_evidence
            (hasheq 'status (if (and worker-registered? monitor-registered? xref-registered?
                                    usable-monitor-frames? usable-xref-frames?)
                               "coarse_thread_context_available" "incomplete")
                    'working_thread_registered worker-registered?
                    'monitor_thread_registered monitor-registered?
                    'usable_monitor_frames usable-monitor-frames?
                    'xref_service_thread_registered xref-registered?
                    'usable_xref_frames usable-xref-frames?
                    'acceptance_scope "Registrations and approximate stack evidence only; replay/OOM success alone is not attribution success")
            'xref_service_registration xref-registration
            'begin_metrics (or begin-metrics 'null) 'end_metrics (or end-metrics 'null)
            'phase_points (for/list ([i (in-range points-used)]) (vector-ref points i))
            'thread_samples (for/list ([i (in-range samples-used)]) (vector-ref samples i))
            'phase_points_dropped points-dropped 'sample_ticks_dropped samples-dropped
            'input_events_dropped (- (unbox dropped-input) dropped-before) 'stale_events_discarded stale-events
            'sample_period_ms sample-period-ms 'sample_cap sample-cap 'phase_point_cap point-cap
            'frame_cap frame-cap 'text_cap text-cap 'thread_references "weak; per-trial refs cleared at end/begin; service weak ref cleared at stop"
            'stock_logger_subscription #f
            'scope "Runtime-wide counter observations and approximate wall-clock thread stacks; no CPU/allocation ownership or speedup claim"
            'overhead "Source hooks, counter reads, buffered records, cross-thread continuation capture/formatting and control queries are included in this separately instrumented diagnostic"
            'transient_cost_bound "Retained rows/frames/text are capped; continuation capture/context conversion transient cost and scheduler delay are not hard-bounded"
            'gc_visibility "Point counters are separate runtime observations. GC receiver records may lag or be missing; do not sum root/worker counters or infer no collection from missing events"))
  (set! controller
        (thread
         (lambda ()
           (let loop ([next-sample (+ (tick) sample-period-ms)])
             (define event
               (sync/timeout (max 0 (/ (- next-sample (tick)) 1000.0))
                             (handle-evt commands (lambda (v) (cons 'command v)))
                             (handle-evt inbox (lambda (v) (cons 'point v)))))
             (define stop? #f)
             (match event
               [(cons 'point data) (accept-event! data)]
               [(cons 'command (vector command arg reply))
                (define result
                  (case command
                    [(begin)
                     (drain!) (set! active? #f) (hash-clear! refs)
                     (hash-clear! registrations) (set! latest-worker-phase #f) (set! latest-monitor-phase #f)
                     (set! trial arg) (set! expected-generation (add1 (unbox generation)))
                     (when (and xref-ref (weak-box-value xref-ref))
                       (hash-set! refs 'xref-service xref-ref)
                       (hash-set! registrations 'xref-service #t))
                     (set! points (make-vector point-cap #f)) (set! samples (make-vector sample-cap #f))
                     (set! points-used 0) (set! samples-used 0)
                     (set! points-dropped 0) (set! samples-dropped 0) (set! stale-events 0)
                     (set! dropped-before (unbox dropped-input))
                     (set! begin-metrics (metrics)) (set! end-metrics #f) (set! active? #t)
                     'phase-begun]
                    [(end)
                     (unless (= arg trial) (error 'phase-probe "Wrong trial end"))
                     (drain!) (sample!) (set! end-metrics (metrics))
                     (set! active? #f) (hash-clear! refs) 'phase-ended]
                    [(snapshot) (drain!) (snapshot)]
                    [(stop) (set! active? #f) (hash-clear! refs) (set! xref-ref #f) (set! stop? #t) #t]
                    [else (error 'phase-probe "Unknown control command")]))
                (async-channel-put reply result)]
               [#f (sample!)])
             (unless stop?
               (loop (if (>= (tick) next-sample) (+ (tick) sample-period-ms) next-sample)))))))
  (lambda (command [arg #f] [timeout 2])
    (define until (+ (tick) (* 1000 timeout)))
    (define (remaining) (max 0 (/ (- until (tick)) 1000.0)))
    (define reply (make-async-channel 1))
    (unless (sync/timeout (remaining) (channel-put-evt commands (vector command arg reply)))
      (error 'phase-probe "Controller command timeout"))
    (define result (sync/timeout (remaining) reply))
    (unless result (error 'phase-probe "Controller response timeout"))
    (if (eq? command 'stop)
        (and (sync/timeout (remaining) (thread-dead-evt controller)) #t)
        result)))
