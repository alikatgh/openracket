#lang racket/base
;; Scalar-only common GUI evidence. No worker protocol, logger, or extra threads.
(require json racket/file racket/list racket/path racket/place racket/port syntax/modresolve)
(provide gui-hook digest worker-init! observer-summary current-gui-request-id)
(define max-records 8)
(define (tick) (current-inexact-monotonic-milliseconds))
(define (metrics)
  (hasheq 'monotonic_ms (tick)
          'process_allocation_counter_bytes (current-memory-use 'cumulative)
          'gc_counter_ms (current-gc-milliseconds)
          'process_cpu_counter_ms_all_places (current-process-milliseconds)))
(define (digest bytes)
  (apply string-append (for/list ([b (in-bytes (sha256-bytes bytes))])
                         (define s (number->string b 16))
                         (if (= (string-length s) 1) (string-append "0" s) s))))
(define (clip s [limit 1024]) (substring s 0 (min limit (string-length s))))
(define (identity-text s)
  (when (> (string-length s) 1024) (error 'gui-observer "Identity evidence exceeds 1024 characters"))
  s)
(define (bounded-format value)
  (identity-text (parameterize ([error-print-width 1025]) (format "~.s" value))))
(define (source-text v)
  (identity-text (if (path? v) (path->string (simplify-path (path->complete-path v) #f)) (bounded-format v))))
(define current-request (make-parameter #f))
(define current-gui-request-id current-request)
(define state (box (hasheq 'request_count 0 'records (hasheq) 'actual_registry '()
                           'error_count 0 'errors '() 'dropped_records 0)))
(define (change! transition)
  (let loop ()
    (define old (unbox state))
    (define-values (new result) (transition old))
    (if (box-cas! state old new) result (loop))))
(define (record-error! e)
  (change! (lambda (old)
             (values (hash-set (hash-set old 'error_count (add1 (hash-ref old 'error_count)))
                               'errors (if (< (length (hash-ref old 'errors)) 8)
                                           (cons (clip (exn-message e) 240) (hash-ref old 'errors))
                                           (hash-ref old 'errors))) #f))))
(define (observer-summary)
  (define old (unbox state))
  (define records (hash-ref old 'records))
  (define ids (sort (hash-keys records) <))
  (hash-set (hash-set (hash-set old 'records (map (lambda (id) (hash-ref records id)) ids))
                      'matching_request_ids ids)
            'schema_version 1))
(define (output-path name)
  (build-path (or (getenv "OPENRACKET_GUI_OBSERVER_OUTPUT")
                 (error 'gui-observer "Missing explicit output directory")) name))
(define (write-atomic! name data)
  (define output (output-path name))
  (define tmp (make-temporary-file "gui-observer-~a.json" #f (path-only output)))
  (call-with-output-file tmp #:exists 'truncate/replace
    (lambda (out) (write-json data out) (newline out)))
  (rename-file-or-directory tmp output #t))
(define (safe thunk)
  (with-handlers ([exn:fail? (lambda (e) (record-error! e) #f)])
    (define answer (thunk))
    answer))
(define (registry-summary actual)
  (unless (and (list? actual) (<= (length actual) 64)) (error 'gui-observer "Registry evidence exceeds64 entries"))
  (for/list ([row (in-list actual)])
    (define mod (car row))
    (define path (resolve-module-path mod #f))
    (hasheq 'module_spec (bounded-format mod) 'export (symbol->string (cadr row))
            'monitor (and (caddr row) #t) 'source (source-text path)
            'source_sha256 (and (path? path) (digest (file->bytes path))))))
(define (worker-init! entries limit)
  (safe
   (lambda ()
     (write-atomic! "worker-init.json"
                    (hasheq 'schema_version 1 'event "actual-registry-initialized-no-barrier"
                            'child_limit_bytes limit
                            'memory_accounting_available (custodian-memory-accounting-available?)
                            'actual_registry (registry-summary
                                              (for/list ([entry (in-list entries)])
                                                (append (car entry) (list (cadr entry)))))
                            'metrics (metrics))))))
(define (record-ref old id) (hash-ref (hash-ref old 'records) id #f))
(define (update-record old id procedure)
  (define rec (record-ref old id))
  (if rec (hash-set old 'records (hash-set (hash-ref old 'records) id (procedure rec))) old))
(define (point rec name value)
  (define points (hash-ref rec 'gui_points))
  (hash-set (hash-set rec 'gui_points (hash-set points name value))
            'point_duplicates (+ (hash-ref rec 'point_duplicates) (if (hash-has-key? points name) 1 0))))
(define (token-live? old token stock-live?)
  (and stock-live? (vector? token) (= (vector-length token) 2)
       (= (vector-ref token 0) (hash-ref old 'request_count))
       (let ([rec (record-ref old (vector-ref token 0))])
         (and rec (not (hash-ref rec 'application_cancelled))
              (= (vector-ref token 1) (hash-ref rec 'application_generation))))))
(define (request! actual limit)
  (define sample (metrics))
  (unless (and (vector? actual) (= (vector-length actual) 6)
               (place-channel? (vector-ref actual 2)) (place-channel? (vector-ref actual 4)))
    (error 'gui-observer "Malformed actual request"))
  (define snapshot (vector-ref actual 0))
  (define matches?
    (and (string? snapshot)
         (= (string-length snapshot) (string->number (getenv "OPENRACKET_GUI_EXPECTED_CHARACTERS")))
         (equal? (source-text (vector-ref actual 1)) (getenv "OPENRACKET_GUI_EXPECTED_SOURCE"))
         (equal? (digest (string->bytes/utf-8 snapshot)) (getenv "OPENRACKET_GUI_EXPECTED_SHA256"))))
  (define settings (vector-ref actual 3))
  (define id
    (change!
     (lambda (old)
       (define id (add1 (hash-ref old 'request_count)))
       (define next (hash-set old 'request_count id))
       (cond
         [(not matches?) (values next #f)]
         [(>= (hash-count (hash-ref old 'records)) max-records)
          (values (hash-set next 'dropped_records (add1 (hash-ref old 'dropped_records))) #f)]
         [else
          (define settings-text (bounded-format settings))
          (define rec
            (hasheq 'request_id id 'snapshot_sha256 (getenv "OPENRACKET_GUI_EXPECTED_SHA256")
                    'snapshot_characters (string-length snapshot)
                    'snapshot_kind "string" 'source (source-text (vector-ref actual 1))
                    'actual_child_limit_bytes limit 'actual_prefab (clip settings-text)
                    'actual_prefab_truncated (> (string-length settings-text) 1024)
                    'prefab_annotations_none
                    (and (equal? (prefab-struct-key settings) 'prefab-module-settings)
                         (= (vector-length (struct->vector settings)) 7)
                         (eq? (vector-ref (struct->vector settings) 5) 'none))
                    'terminal 'null 'gui_points (hasheq 'request-observed sample) 'point_duplicates 0
                    'terminal_callback_current #f 'application_current #f 'application_generation 0
                    'application_cancelled #f 'stale_application_events 0
                    'monitor_evidence (hasheq 'messages 0 'trace_batches 0 'trace_entries 0
                                              'rename_capability_rows 0 'error_messages 0 'invalid_payloads 0)))
          (values (hash-set next 'records (hash-set (hash-ref old 'records) id rec)) id)]))))
  id)
(define (monitor-delta payload)
  (define trace? (and (list? payload)
                      (andmap (lambda (row) (and (vector? row) (positive? (vector-length row))
                                                (symbol? (vector-ref row 0))
                                                (regexp-match? #rx"^syncheck:" (symbol->string (vector-ref row 0))))) payload)))
  (hasheq 'messages 1 'trace_batches (if trace? 1 0) 'trace_entries (if trace? (length payload) 0)
          'error_messages (if (string? payload) 1 0)
          'invalid_payloads (if (or trace? (string? payload)) 0 1)
          'rename_capability_rows
          (if trace?
              (for/sum ([row (in-list payload)])
                (if (or (and (eq? (vector-ref row 0) 'syncheck:add-arrow/name-dup/pxpy)
                             (= (vector-length row) 14) (place-channel? (vector-ref row 12)))
                        (and (eq? (vector-ref row 0) 'syncheck:add-id-set)
                             (= (vector-length row) 4) (place-channel? (vector-ref row 2)))) 1 0)) 0)))
(define (response! id result)
  (define sample (metrics))
  (define monitor? (eq? (vector-ref result 0) 'monitor-message))
  (define recognized-monitor?
    (and monitor?
         (for/or ([entry (in-list (hash-ref (unbox state) 'actual_registry))])
           (and (hash-ref entry 'monitor)
                (equal? (hash-ref entry 'module_spec) (format "~s" (car (vector-ref result 1))))
                (equal? (hash-ref entry 'export) (symbol->string (cadr (vector-ref result 1))))))))
  (define detail
    (if monitor? (if recognized-monitor? (monitor-delta (vector-ref result 2))
                    (hasheq 'messages 1 'trace_batches 0 'trace_entries 0 'rename_capability_rows 0
                            'error_messages 0 'invalid_payloads 1))
        (hasheq 'tag (symbol->string (vector-ref result 0))
                'handler_keys (if (eq? (vector-ref result 0) 'handler-results)
                                  (for/list ([row (in-list (vector-ref result 1))]) (bounded-format (car row))) '())
                'compiled_bytes (if (and (eq? (vector-ref result 0) 'handler-results) (vector-ref result 3))
                                    (bytes-length (vector-ref (vector-ref result 3) 2)) #f))))
  (change! (lambda (old)
             (values
              (update-record old id
                             (lambda (rec)
                               (define with-point (point rec (if monitor? 'monitor-received 'terminal-received) sample))
                               (if monitor?
                                   (hash-set with-point 'monitor_evidence
                                             (for/hasheq ([(key value) (in-hash (hash-ref rec 'monitor_evidence))])
                                               (values key (+ value (hash-ref detail key)))))
                                   (hash-set with-point 'terminal detail)))) (void))))
  (void))
(define (gui-hook action . args)
  ;; with-monitor must propagate original application exceptions/return values;
  ;; every observer-only action is failure-contained and stores no input payload.
  (cond
    [(eq? action 'with-monitor)
     (parameterize ([current-request (car args)]) ((cadr args)))]
    [else
     (safe
      (lambda ()
        (case action
          [(registry)
           (define entries (registry-summary (car args)))
           (change! (lambda (old) (values (hash-set old 'actual_registry entries) (void))))
           (void)]
          [(request) (request! (car args) (cadr args))]
          [(response) (when (car args) (response! (car args) (cadr args)))]
          [(point)
           (define id (car args))
           (when id
             (define name (cadr args))
             (define sample (metrics))
             (change! (lambda (old)
                        (values (update-record old id
                                               (lambda (rec)
                                                 (define next (point rec name sample))
                                                 (if (eq? name 'terminal-callback-enter)
                                                     (hash-set next 'terminal_callback_current
                                                               (and (caddr args) (= id (hash-ref old 'request_count)))) next)))
                                (void))))
             (void))]
          [(application-enter)
           (define id (current-request))
           (and id
                (change! (lambda (old)
                           (define rec (record-ref old id))
                           (if rec
                               (let ([gen (add1 (hash-ref rec 'application_generation))])
                                 (values (update-record old id
                                                       (lambda (r)
                                                         (point
                                                          (hash-set
                                                           (hash-set
                                                            (hash-set
                                                             (hash-set r 'application_generation gen)
                                                             'application_current #f)
                                                            'application_cancelled #f)
                                                           'gui_points (hash-remove (hash-ref r 'gui_points) 'application-complete))
                                                          'application-enter (metrics))))
                                         (vector-immutable id gen)))
                               (values old #f)))))]
          [(application-live?) (and (token-live? (unbox state) (car args) (cadr args)) #t)]
          [(application-complete application-cancel)
           (define token (car args))
           (when token
             (define id (vector-ref token 0))
             (define sample (metrics))
             (change! (lambda (old)
                        (define rec (record-ref old id))
                        (define same-generation?
                          (and rec (= (vector-ref token 1) (hash-ref rec 'application_generation))
                               (= id (hash-ref old 'request_count))))
                        (define live? (and (eq? action 'application-complete)
                                           (token-live? old token (cadr args))))
                        (values
                         (update-record old id
                                        (lambda (rec)
                                          (if same-generation?
                                              (point
                                               (hash-set (hash-set rec 'application_current (and live? #t))
                                                         'application_cancelled (not live?))
                                               (if live? 'application-complete 'application-cancelled-or-stale) sample)
                                              (hash-set rec 'stale_application_events
                                                        (add1 (hash-ref rec 'stale_application_events))))))
                         (void))))
             (void))]
          [else (error 'gui-observer "Unknown scalar action")])))]))
