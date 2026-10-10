#lang racket/base
;; Optional attribution only. Never mix its timings with ordinary benchmarks.
;; Uses Racket's existing statistical sampler and existing stock log messages.
(require racket/list racket/format racket/port)
(provide start-diagnostics)

(define (start-diagnostics gui-thread phase last-heartbeat #:logger [root-logger (current-logger)])
  (define create-sampler (dynamic-require 'profile/sampler 'create-sampler))
  (define analyze-samples (dynamic-require 'profile/analyzer 'analyze-samples))
  (define render (dynamic-require 'profile/render-text 'render))
  ;; Track only the actual GUI eventspace handler, without creating/changing the
  ;; stock execution custodian or changing program errortrace instrumentation.
  (define sampler (create-sampler gui-thread .010))
  (define receiver
    (make-log-receiver root-logger
                      'debug 'framework/colorer
                      'debug 'GC
                      'info 'online-expansion-state-machine))
  (define collecting? #t)
  (define records null)
  (define received 0)
  (define logger-error #f)
  (define stalled-samples null)
  (define last-stall-sample 0.0)
  (define (observe-stall!)
    (define time (current-inexact-monotonic-milliseconds))
    (when (and (> (- time (last-heartbeat)) 100)
               (>= (- time last-stall-sample) 50)
               (< (length stalled-samples) 100))
      (set! last-stall-sample time)
      (define stack
        (with-handlers ([exn:fail? (lambda (e) (list (exn-message e)))])
          (define context (continuation-mark-set->context (continuation-marks gui-thread)))
          (map (lambda (frame) (~s frame)) (take context (min 32 (length context))))))
      (set! stalled-samples
            (cons (hasheq 'phase (phase) 'heartbeat_age_ms (- time (last-heartbeat))
                          'observed_monotonic_ms time 'handler_stack stack)
                  stalled-samples))))
  (define started-wall (current-inexact-milliseconds))
  (define started-mono (current-inexact-monotonic-milliseconds))
  (define (short text [n 2048])
    (substring text 0 (min n (string-length text))))
  (define collector
    (thread
     (lambda ()
       (with-handlers ([exn:fail? (lambda (e) (set! logger-error (exn-message e)))])
         (let loop ()
           (when collecting?
             (define row (sync/timeout .050 receiver))
             (observe-stall!)
             (when row
               (set! received (add1 received))
               (when (<= received 20000)
                 (define payload (vector-ref row 2))
                 (set! records
                       (cons
                        (hasheq 'topic (~a (vector-ref row 3))
                                'level (~a (vector-ref row 0))
                                'message (short (vector-ref row 1))
                                'data (short (~s payload))
                                'source_wall_ms (if (real? payload) payload 'null)
                                'received_after_start_ms
                                (- (current-inexact-monotonic-milliseconds) started-mono)
                                'phase (phase))
                        records))))
             (loop)))))))
  (lambda ()
    ;; Pause avoids a cross-custodian kill; the short-lived process owns final
    ;; shutdown. The paused sampler no longer samples during report rendering.
    (sampler 'pause)
    (set! collecting? #f)
    (unless (sync/timeout 2 (thread-dead-evt collector))
      (error 'performance-diagnostics "logger collector did not stop cooperatively"))
    (define rendered
      (with-output-to-string
        (lambda () (render (analyze-samples (sampler 'get-snapshots))))))
    (hasheq 'measurement_kind "instrumented_attribution_only"
            'warning "Sampler/logging overhead is present; do not compare these timings to ordinary benchmarks."
            'sample_interval_seconds .010
            'sampled_thread "actual GUI eventspace handler only"
            'started_wall_ms started-wall
            'started_monotonic_ms started-mono
            'log_records_received received
            'log_records_dropped (max 0 (- received 20000))
            'logger_error (or logger-error 'null)
            'stalled_handler_samples (reverse stalled-samples)
            'profile_text_truncated (> (string-length rendered) 64000)
            'profile_text (short rendered 64000)
            'log_records (reverse records))))
