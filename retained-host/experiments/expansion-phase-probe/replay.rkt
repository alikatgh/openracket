#lang racket/base
;; Standalone diagnostic process. All stock place channels and compiler locks stay here.
(require racket/file racket/path racket/place racket/list racket/format racket/match
         json compiler/cm "support.rkt" (only-in ffi/unsafe void/reference-sink))

(define config (string->jsexpr (or (getenv "OPENRACKET_REPLAY_CONFIG")
                                   (error 'replay "Missing supervisor configuration"))))
(define phase-probe? (hash-ref config 'phase_probe #f))
(define output (path->complete-path (hash-ref config 'output)))
(make-directory* output)
(define report (make-hasheq))
(define cust (make-custodian))
(define worker #f)
(define control #f)
(define root-stop #f)
(define last-terminal #f)
(define previous-capabilities (make-hasheq))
(define current-capabilities (make-hasheq))
(define (persist!)
  (call-with-output-file (build-path output "replay.json") #:exists 'truncate/replace
    (lambda (out) (write-json report out) (newline out))))
(define (phase event [trial 0] [outcome #f])
  (display "OPENRACKET_REPLAY_PHASE_JSON ")
  (write-json (hasheq 'event event 'trial trial
                      'monotonic_ms (current-inexact-monotonic-milliseconds)
                      'outcome (or outcome 'null)))
  (newline) (flush-output))
(define (metrics)
  (hasheq 'monotonic_ms (current-inexact-monotonic-milliseconds)
          'process_allocation_counter_bytes (current-memory-use 'cumulative)
          'gc_counter_ms_observed_from_root (current-gc-milliseconds)
          'process_cpu_counter_ms_all_places (current-process-milliseconds)
          'managed_bytes_observed_from_root (current-memory-use)))
(define (control-snapshot)
  (define sent (current-inexact-monotonic-milliseconds))
  (place-channel-put control 'snapshot)
  (define reply (or (sync/timeout 5 control) (error 'replay "Worker GC snapshot did not arrive within 5 seconds")))
  (define received (current-inexact-monotonic-milliseconds))
  (hash-set (hash-set (hash-set reply 'root_query_sent_monotonic_ms sent)
                     'root_query_received_monotonic_ms received)
            'worker_clock_within_root_query
            (<= sent (hash-ref reply 'monotonic_ms) received)))
(define (phase-control! action trial expected)
  (when phase-probe?
    (place-channel-put control (vector action trial))
    (unless (eq? (sync/timeout 5 control) expected)
      (error 'phase-probe "Missing exact phase control acknowledgement: ~s" action))))
(define (gc-json snapshot start end)
  (define compatible-clock? (hash-ref snapshot 'worker_clock_within_root_query #t))
  (hasheq 'gc_counter_ms_observation (hash-ref snapshot 'gc_ms)
          'worker_clock_within_root_query (hash-ref snapshot 'worker_clock_within_root_query 'null)
          'receipt_time_filter_valid compatible-clock?
          'records_dropped (hash-ref snapshot 'records_dropped)
          'interval_records
          (if compatible-clock?
              (for/list ([r (in-list (hash-ref snapshot 'records))]
                         #:when (<= start (vector-ref r 0) end))
                (hasheq 'received_monotonic_ms (vector-ref r 0) 'gc_info (vector-ref r 1)
                        'gc_info_truncated (vector-ref r 2)))
              'null)
          'counter_scope "Runtime GC counter sampled from this place; not an independent per-place ownership counter"
          'receiver_scope "GC log receiver in this place; no cross-place event sum or allocator ownership claim"))

(define (cleanup!)
  (phase "cleanup")
  (define cleanup-report (make-hasheq))
  (define errors '())
  (define deadline (+ (current-inexact-monotonic-milliseconds)
                       (* 1000 (hash-ref config 'cleanup_timeout_seconds 2))))
  (define (remaining) (max 0 (/ (- deadline (current-inexact-monotonic-milliseconds)) 1000.0)))
  (define (component key thunk)
    (with-handlers ([exn? (lambda (e)
                           (set! errors (cons (hasheq 'component (~a key) 'error (exn-message e)) errors))
                           (hash-set! cleanup-report key #f))])
      (define ok? (and (thunk) #t))
      (hash-set! cleanup-report key ok?)
      (unless ok?
        (set! errors (cons (hasheq 'component (~a key) 'error "Missing required cleanup acknowledgement") errors)))))
  (when control
    (component 'control_stopped
     (lambda ()
      (place-channel-put control 'stop)
      (define ack (sync/timeout (min .5 (remaining)) control))
      (hash-set! cleanup-report 'control_acknowledgement (~s ack))
      (eq? ack 'stopped))))
  (when worker
    (component 'place_dead
     (lambda ()
      (unless (sync/timeout 0 (place-dead-evt worker))
        (place-channel-put worker 'abort)
        (place-kill worker))
      (sync/timeout (remaining) (place-dead-evt worker)))))
  (when root-stop
    (component 'root_logger_stopped (lambda () (root-stop (remaining)))))
  (component 'diagnostic_custodian_shutdown
             (lambda () (custodian-shutdown-all cust) #t))
  (hash-set! cleanup-report 'errors (reverse errors))
  (hash-set! cleanup-report 'accepted (null? errors))
  (hash-set! report 'cleanup cleanup-report)
  (null? errors))

(hash-set! report 'schema_version 1)
(hash-set! report 'status "initializing")
(hash-set! report 'instrumented_stock_copy #t)
(hash-set! report 'phase_probe_enabled phase-probe?)
(when phase-probe?
  (hash-set! report 'phase_probe_sha256
             (file-hash (or (getenv "OPENRACKET_REPLAY_PHASE_MODULE")
                            (error 'phase-probe "Missing phase module path")))))
(hash-set! report 'measurement_scope
           "Isolated process interval including worker, handlers, compiler manager, result sink and observers; not causal allocation ownership in the integrated GUI run")
(hash-set! report 'gc_scope_warning
           "GC counters are runtime observations sampled from root/worker, not independent place ownership. Receivers are reported separately and events are not summed across places; receipt timestamps may lag collection. Missing records do not imply no collection.")

(with-handlers
    ([exn? (lambda (e)
             (hash-set! report 'status "driver_failure")
             (hash-set! report 'error (exn-message e))
             (cleanup!)
             (void/reference-sink last-terminal previous-capabilities current-capabilities)
             (persist!) (phase "finished" 0 "driver_failure") (exit 1))])
  (unless (and (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
               (not (equal? (getenv "OPENRACKET_EXPANSION_CAPTURE") "1")))
    (error 'replay "Replay-only flag required; capture flag must be absent"))
  (unless (equal? phase-probe? (equal? (getenv "OPENRACKET_EXPANSION_PHASE_PROBE") "1"))
    (error 'phase-probe "Configuration and process phase flag disagree"))
  (define capture-path (path->complete-path (hash-ref config 'capture)))
  (define record (validate-capture! (load-capture capture-path) #:runtime? #f))
  (hash-set! report 'disposable_preference_restoration (restore-disposable-preferences! record output))
  (validate-capture! record)
  (define capture-summary-path (build-path (path-only capture-path) "capture-summary.json"))
  (define captured-summary (call-with-input-file capture-summary-path read-json))
  (unless (equal? (hash-ref captured-summary 'status) "terminal_observed")
    (error 'replay "Integrated edited-snapshot capture has no actual terminal outcome"))
  (hash-set! report 'snapshot_sha256 (hash-ref record 'snapshot-sha256))
  (hash-set! report 'snapshot_bytes (hash-ref record 'snapshot-bytes))
  (hash-set! report 'snapshot_characters (hash-ref record 'snapshot-characters))
  (hash-set! report 'source (~s (hash-ref record 'source)))
  (hash-set! report 'prefab_settings (~s (hash-ref record 'settings)))
  (hash-set! report 'registry_sha256 (hash-ref record 'registry-sha256))
  (hash-set! report 'registry (map ~s (hash-ref record 'registry)))
  (hash-set! report 'capture_terminal (hash-ref captured-summary 'terminal))
  (hash-set! report 'racket_version (version))
  (hash-set! report 'os (~a (system-type 'os)))
  (hash-set! report 'vm (~a (system-type 'vm)))
  (phase "initializing")
  (define-values (root-snapshot stop-root) (make-gc-observer (current-logger)))
  (set! root-stop stop-root)
  (define initialization-start (current-inexact-monotonic-milliseconds))
  (parameterize ([current-custodian cust])
    (define lock (make-compile-lock))
    (set! worker (dynamic-place (hash-ref record 'worker-path) 'start))
    (place-channel-put worker lock)
    (place-channel-put worker (hash-ref record 'registry)))
  (define ready
    (sync/timeout (hash-ref config 'init_timeout_seconds 30)
                  (handle-evt worker values)
                  (handle-evt (place-dead-evt worker) (lambda (_) 'worker-died))))
  (match ready
    [(vector 'openracket-expansion-replay-ready (? place-channel? channel) 134217728)
     (set! control channel)]
    [#f (error 'replay "Initialization timed out before an actual ready acknowledgement")]
    ['worker-died (error 'replay "Worker died during initialization")]
    [_ (error 'replay "Unexpected ready protocol: ~s" ready)])
  (hash-set! report 'initialization_ms (- (current-inexact-monotonic-milliseconds) initialization-start))
  (hash-set! report 'actual_worker_child_limit_bytes 134217728)
  (define trial-results '())
  (define completed? #t)
  (for ([trial (in-range 1 (add1 (hash-ref config 'trials 2)))] #:break (not completed?))
    (define-values (response-in response-out) (place-channel))
    (define-values (status-in status-out) (place-channel))
    (define request (vector-immutable (hash-ref record 'snapshot) (hash-ref record 'source)
                                      response-in (hash-ref record 'settings) status-in
                                      (hash-ref record 'open-files)))
    (phase-control! 'phase-begin trial 'phase-begun)
    (define worker-before (control-snapshot))
    (define root-before (root-snapshot))
    (define capabilities (make-hasheq))
    (set! current-capabilities capabilities)
    (define prior-terminal-retained? (and last-terminal #t))
    (define prior-capabilities-retained (hash-count previous-capabilities))
    (define monitors 0)
    (define statuses '())
    (define terminal #f)
    (define outcome #f)
    (define first-response? #t)
    (define (release-prior!)
      (when first-response?
        (set! last-terminal #f)
        (set! previous-capabilities (make-hasheq))
        (set! first-response? #f)))
    (define (hold-capabilities! value)
      (define seen (make-hasheq))
      (define (walk v)
        (unless (hash-ref seen v #f)
          (hash-set! seen v #t)
          (cond
            [(place-channel? v) (hash-set! capabilities v #t)]
            [(pair? v) (walk (car v)) (walk (cdr v))]
            [(vector? v) (for ([x (in-vector v)]) (walk x))]
            [(box? v) (walk (unbox v))]
            [(hash? v) (for ([(k x) (in-hash v)]) (walk k) (walk x))]
            [(prefab-struct-key v) (walk (struct->vector v))]
            [(and (bytes? v) (not (immutable? v))) (hash-set! capabilities v #t)]
            [(or (number? v) (string? v) (bytes? v) (char? v) (boolean? v)
                 (symbol? v) (keyword? v) (path? v) (null? v) (void? v)) (void)]
            [else (hash-set! capabilities v #t)])))
      (walk value))
    (phase "interval_start" trial)
    (define before (metrics))
    (when (= trial 1) (place-channel-put worker 'openracket-expansion-replay-continue))
    (place-channel-put worker request)
    (define deadline (+ (current-inexact-monotonic-milliseconds)
                        (* 1000 (hash-ref config 'terminal_timeout_seconds 60))))
    (let loop ()
      (define remaining (max 0 (/ (- deadline (current-inexact-monotonic-milliseconds)) 1000.0)))
      (define event
        (sync/timeout remaining
                      (handle-evt response-out (lambda (v) (cons 'response v)))
                      (handle-evt status-out (lambda (v) (cons 'status v)))
                      (handle-evt (place-dead-evt worker) (lambda (_) '(dead)))))
      (match event
        [#f (set! outcome "supervisor_interval_timeout") (set! completed? #f)]
        [(list 'dead) (set! outcome "worker_place_died") (set! completed? #f)]
        [(cons 'status value)
         (release-prior!) (set! statuses (cons value statuses)) (loop)]
        [(cons 'response value)
         (release-prior!)
         (cond
           [(and (vector? value) (eq? (vector-ref value 0) 'monitor-message))
            (set! monitors (add1 monitors)) (hold-capabilities! value) (loop)]
           [else
            (unless (and (vector? value) (positive? (vector-length value))
                         (memq (vector-ref value 0)
                               '(handler-results abnormal-termination access-violation reader-in-defs-error exn:variable exn)))
              (error 'replay "Unknown terminal protocol"))
            (set! terminal value)
            (set! outcome (symbol->string (vector-ref value 0)))])]))
    ;; This endpoint precedes result hashing, JSON generation, GC queries and cleanup.
    (define after (metrics))
    (when terminal (set! last-terminal terminal))
    (phase "interval_end" trial outcome)
    (when phase-probe?
      ;; Preserve the real result even if a later optional probe query fails.
      (hash-set! report 'last_observed_terminal_before_probe_queries
                 (if terminal (summarize-result terminal) 'null)))
    (when completed? (phase-control! 'phase-end trial 'phase-ended))
    (define worker-after (and completed? (control-snapshot)))
    (define root-after (root-snapshot))
    (define terminal-summary (and terminal (summarize-result terminal)))
    ;; If replacement work never responded, retain the preceding result and its
    ;; capabilities through teardown. current-capabilities roots this new request.
    (unless first-response? (set! previous-capabilities capabilities))
    (define start (hash-ref before 'monotonic_ms))
    (define end (hash-ref after 'monotonic_ms))
    (define trial-report
      (hasheq 'trial trial
              'warmth (if (= trial 1) "fresh-process first expansion after initialization; not cold disk cache"
                          "same-process repeated expansion after the prior observed terminal outcome")
              'outcome outcome 'terminal (or terminal-summary 'null)
              'terminal_summary_matches_integrated_capture
              (and terminal-summary (equal? terminal-summary (hash-ref captured-summary 'terminal)))
              'elapsed_ms (- end start) 'before before 'after after
              'process_allocation_delta_during_isolated_expansion_interval
              (- (hash-ref after 'process_allocation_counter_bytes)
                 (hash-ref before 'process_allocation_counter_bytes))
              'gc_counter_delta_ms_observed_from_root
              (- (hash-ref after 'gc_counter_ms_observed_from_root) (hash-ref before 'gc_counter_ms_observed_from_root))
              'gc_counter_delta_ms_observed_from_worker
              (if worker-after (- (hash-ref worker-after 'gc_ms) (hash-ref worker-before 'gc_ms)) 'null)
              'worker_gc_query_boundary_warning "Worker counters bracket diagnostic queries outside the root allocation interval"
              'root_gc (gc-json root-after start end)
              'worker_gc (if worker-after (gc-json worker-after start end) 'null)
              'phase_probe (if worker-after (hash-ref worker-after 'phase_probe 'null) 'null)
              'monitor_messages monitors 'statuses (map ~a (reverse statuses))
              'prior_terminal_retained_before_request prior-terminal-retained?
              'prior_capabilities_retained_before_request prior-capabilities-retained
              'retained_capabilities (hash-count capabilities)))
    (set! trial-results (cons trial-report trial-results))
    (hash-set! report 'trials (reverse trial-results))
    (hash-set! report 'status (if completed? "running" "incomplete_terminal_protocol"))
    (persist!))
  ;; Prevent the optimizer from treating retained terminal/capabilities as dead before teardown.
  (hash-set! report 'last_terminal_retained_until_cleanup (and last-terminal #t))
  (hash-set! report 'last_capabilities_retained_until_cleanup (hash-count previous-capabilities))
  (define cleaned? (cleanup!))
  ;; Unlike booleans/counts or plain void, this stock helper cannot be optimized
  ;; away. Actual terminal/channel objects remain live across the entire teardown.
  (void/reference-sink last-terminal previous-capabilities current-capabilities)
  (hash-set! report 'status (cond [(not cleaned?) "cleanup_failed"]
                                 [completed? "complete"] [else "incomplete_terminal_protocol"]))
  (persist!) (phase "finished" 0 (hash-ref report 'status))
  (exit (if (and completed? cleaned?) 0 1)))
