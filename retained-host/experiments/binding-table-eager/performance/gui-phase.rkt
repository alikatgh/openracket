#lang racket/base
;; Optional producer points only. No queues, logger receivers, or added threads.
(require json racket/file racket/path racket/list "gui-observer.rkt")
(provide phase-hook)
(define names '(worker-phase-09 worker-phase-10 worker-phase-11 worker-phase-12 worker-phase-13
               monitor-build-start monitor-built-send-start monitor-send-return monitor-ack
               terminal-send-return))
(define current-job (make-parameter #f))
(define selected-count 0)
(define overflow 0)
(define failures 0)
(define max-jobs 8)
(define collect-points? (equal? (getenv "OPENRACKET_GUI_PHASE_POINTS") "1"))
(define (metrics)
  (vector-immutable (current-inexact-monotonic-milliseconds)
                    (current-memory-use 'cumulative)
                    (current-gc-milliseconds)
                    (current-process-milliseconds)))
;; Each existing producer writes fixed independent slots. Only data survives.
(struct record (id sha source settings limit points repeats) #:transparent)
(define (begin-job snapshot source settings limit)
  (current-job #f)
  (when (and (string? snapshot)
             (= (string-length snapshot) (string->number (getenv "OPENRACKET_GUI_EXPECTED_CHARACTERS")))
             (path? source)
             (equal? (path->string (simplify-path (path->complete-path source) #f))
                     (getenv "OPENRACKET_GUI_EXPECTED_SOURCE")))
    (define sha (digest (string->bytes/utf-8 snapshot)))
    (when (equal? sha (getenv "OPENRACKET_GUI_EXPECTED_SHA256"))
      (set! selected-count (add1 selected-count))
      (cond
        [(> selected-count max-jobs) (set! overflow (add1 overflow))]
        [else
         (define settings-text (format "~s" settings))
         (when (> (string-length settings-text) 1024) (error 'gui-phase "Settings evidence exceeds bound"))
         (current-job (record selected-count sha (path->string source) settings-text limit
                              (make-vector (length names) #f) (make-vector (length names) 0)))]))))
(define (point! label)
  (define job (current-job))
  (when (and job collect-points?)
    (define index (index-of names label))
    (unless index (error 'gui-phase "Unknown phase label"))
    (when (vector-ref (record-points job) index)
      (vector-set! (record-repeats job) index (add1 (vector-ref (record-repeats job) index))))
    (vector-set! (record-points job) index (metrics))))
(define (report!)
  ;; Called only AFTER original handler-results send returns, by the existing
  ;; result-forwarding thread under the original custodian, never a new thread.
  (define job (current-job))
  (when job
    (point! 'terminal-send-return)
    (define result
      (hasheq 'schema_version 1 'kind "genuine-gui-producer-phases"
              'selected_job_id (record-id job) 'selected_job_count selected-count
              'dropped_jobs overflow 'observer_failures failures
              'snapshot_sha256 (record-sha job) 'source (record-source job)
              'actual_prefab (record-settings job) 'actual_child_limit_bytes (record-limit job)
              'memory_accounting_available (custodian-memory-accounting-available?)
              'terminal "handler-results" 'phase_points_enabled collect-points? 'emission_after_stock_terminal_send #t
              'phase_points
              (for/list ([name (in-list (if collect-points? names '()))] [row (in-vector (record-points job))]
                         [repeats (in-vector (record-repeats job))])
                (hasheq 'phase (symbol->string name) 'duplicate_writes repeats
                        'producer_metrics
                        (if row
                            (hasheq 'monotonic_ms (vector-ref row 0)
                                    'process_allocation_counter_bytes (vector-ref row 1)
                                    'gc_counter_ms (vector-ref row 2)
                                    'process_cpu_counter_ms_all_places (vector-ref row 3)) 'null)))
              'scope "Runtime-wide counters at producer boundaries, not thread allocation or CPU ownership"
              'overhead "Producer hooks and post-terminal report writing may affect GUI scheduling; no causal speedup claim"))
    (define directory (string->path (getenv "OPENRACKET_GUI_OBSERVER_OUTPUT")))
    (define output (build-path directory (format "worker-phase-~a.json" (record-id job))))
    (define temporary (make-temporary-file "worker-phase-~a.tmp" #f directory))
    (call-with-output-file temporary #:exists 'truncate/replace
      (lambda (out) (write-json result out) (newline out)))
    (rename-file-or-directory temporary output #f)))
(define (phase-hook action . args)
  ;; Never replace a stock result or exception with an observer failure.
  (with-handlers ([exn:fail? (lambda (_) (set! failures (add1 failures)) (void))])
    (case action
      [(begin) (apply begin-job args)]
      [(emit) (report!)]
      [else (point! action)])))
