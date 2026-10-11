#lang racket/base
;; Equal, default-off observation for matched native DrRacket GUI trials.
;; No logger receivers, worker protocol changes, auxiliary threads, or payload retention.
(require json racket/file racket/list racket/path racket/port syntax/modresolve)
(provide observer-register-final! observer-summary observer-final-terminals observer-final-outcome
         observer-request! observer-status! observer-terminal!
         observer-response! observer-monitor!
         observer-callback-enter! observer-callback-delivered! observer-worker-init!)

(define schema-version 1)
(define max-requests 512)
(struct configuration (snapshot source sha generation registration-ms) #:transparent)
(struct observation (count dropped errors error-count calls elapsed records latest-final) #:transparent)
(define configured (box #f))
(define state (box (observation 0 0 '() 0 0 0.0 (hasheq) #f)))
;; Private test seam: disabled by default, no threads or synchronization added.
(define observer-test-commit-hook (make-parameter #f))
(module+ test-support (provide observer-test-commit-hook))
(define (now) (current-inexact-monotonic-milliseconds))
(define (hex b)
  (apply string-append
         (for/list ([v (in-bytes b)])
           (define s (number->string v 16))
           (if (= (string-length s) 1) (string-append "0" s) s))))
(define (digest b) (hex (sha256-bytes b)))
(define (enabled?) (equal? (getenv "OPENRACKET_COMPACT_OBSERVER") "1"))
(define (source-key source)
  (cond [(path? source) (path->string (simplify-path (path->complete-path source) #f))]
        [(string? source) (path->string (simplify-path (path->complete-path source) #f))]
        [else #f]))
(define (short-string x)
  (define s (if (string? x) x (format "~s" x)))
  (substring s 0 (min 512 (string-length s))))
(define (observed started transform)
  ;; Pure transitions + atomic commit. A killed/suspended hook cannot leave any
  ;; lock, half-written record, or cleanup obligation behind. Readers only unbox.
  (let loop ()
    (define old (unbox state))
    (define-values (changed result)
      (with-handlers ([exn:fail?
                       (lambda (e)
                         (values
                          (struct-copy observation old
                            [error-count (add1 (observation-error-count old))]
                            [errors (if (< (length (observation-errors old)) 8)
                                        (cons (short-string (exn-message e)) (observation-errors old))
                                        (observation-errors old))])
                          #f))])
        (transform old)))
    (define completed
      (struct-copy observation changed
        [calls (add1 (observation-calls old))]
        [elapsed (+ (observation-elapsed old) (- (now) started))]))
    (define test-hook (observer-test-commit-hook))
    (when test-hook (test-hook 'before))
    (cond
      [(box-cas! state old completed)
       (when test-hook (test-hook 'after))
       result]
      [else (loop)])))

;; Register once before opening/editing the fixture. No request source survives
;; classification. The single registered immutable final source is hashed once.
(define (observer-register-final! snapshot #:generation gen #:source source)
  (unless (enabled?) (error 'observer-register-final! "Observer flag is not enabled"))
  (unless (and (string? snapshot) (or (string? gen) (exact-nonnegative-integer? gen))
               (or (path? source) (string? source)))
    (error 'observer-register-final! "Expected plain string, JSON generation, and source path"))
  (when (or (unbox configured) (positive? (observation-count (unbox state))))
    (error 'observer-register-final! "Register once before any native request"))
  (define started (now))
  (define expected (string->immutable-string snapshot))
  (define sha (digest (string->bytes/utf-8 expected)))
  (define config (configuration expected (source-key source) sha
                                (if (string? gen) (string->immutable-string gen) gen)
                                (- (now) started)))
  (unless (box-cas! configured #f config)
    (error 'observer-register-final! "Final snapshot is already registered"))
  sha)

(define (observer-request! actual [started (now)])
  (observed
   started
   (lambda (old)
     (define config (unbox configured))
     (unless config (error 'observer-request! "Final snapshot was not registered before opening the fixture"))
     (unless (and (vector? actual) (= (vector-length actual) 6))
       (error 'observer-request! "Malformed original six-field request"))
     (define id (add1 (observation-count old)))
     (cond
       [(> id max-requests)
        (values (struct-copy observation old [count id] [dropped (add1 (observation-dropped old))]) #f)]
       [else
        (define snapshot (vector-ref actual 0))
        (define source-matches? (equal? (source-key (vector-ref actual 1)) (configuration-source config)))
        (define expected (configuration-snapshot config))
        (define matches?
          (and source-matches? (string? snapshot)
               (= (string-length snapshot) (string-length expected))
               (string=? snapshot expected)))
        ;; One extra character makes truncation unambiguous. Only field 3 is
        ;; formatted, never the request vector, snapshot, or trace payload.
        (define settings-text
          (parameterize ([error-print-width 1025]) (format "~.s" (vector-ref actual 3))))
        (define rec
          (hasheq 'request_id id 'generation (configuration-generation config) 'request_ms (now)
                  'snapshot_kind (if (string? snapshot) "string" "wxme-or-other")
                  'snapshot_units (cond [(string? snapshot) (string-length snapshot)]
                                        [(bytes? snapshot) (bytes-length snapshot)] [else 0])
                  'source_match source-matches? 'final_match matches?
                  'snapshot_sha256 (if matches? (configuration-sha config) 'null)
                  'actual_prefab (substring settings-text 0 (min 1024 (string-length settings-text)))
                  'actual_prefab_truncated (> (string-length settings-text) 1024)
                  'status 'null 'status_ms 'null
                  'monitor_messages 0 'monitor_pair_messages 0 'monitor_empty_messages 0
                  'monitor_string_errors 0 'monitor_other_messages 0 'monitor_errors '()
                  'terminal 'null 'terminal_ms 'null
                  'callback_entered_ms 'null 'callback_current 'null
                  'callback_delivered_ms 'null))
        (values (struct-copy observation old
                  [count id] [records (hash-set (observation-records old) id rec)]
                  [latest-final (if matches? id (observation-latest-final old))])
                id)]))))

(define (update-record old id f)
  (define rec (hash-ref (observation-records old) id #f))
  (unless rec (error 'compact-observer "Unknown native request ID"))
  (struct-copy observation old [records (hash-set (observation-records old) id (f rec))]))
(define (observer-status! id status [started (now)])
  (observed started
            (lambda (old)
              (values (update-record old id (lambda (r)
                        (hash-set (hash-set r 'status (symbol->string status)) 'status_ms (now))))
                      (void)))))
(define (terminal-summary result)
  (unless (and (vector? result) (positive? (vector-length result))
               (symbol? (vector-ref result 0)))
    (error 'compact-observer "Malformed terminal response"))
  (define tag (vector-ref result 0))
  (when (eq? tag 'monitor-message) (error 'compact-observer "Monitor payload reached terminal observer"))
  (define abnormal? (eq? tag 'abnormal-termination))
  (define msg (and abnormal? (vector-ref result 1)))
  (hasheq 'tag (symbol->string tag)
          'explicit_out_of_memory (and msg (regexp-match? #rx"out of memory" msg) #t)
          'abnormal_message (if msg (short-string msg) 'null)))
(define (observer-terminal! id result [started (now)])
  (observed started
            (lambda (old)
              (define terminal (terminal-summary result))
              (values (update-record old id (lambda (r)
                        (unless (eq? (hash-ref r 'terminal) 'null)
                          (error 'compact-observer "Duplicate terminal for native request"))
                        (hash-set (hash-set r 'terminal terminal) 'terminal_ms (now))))
                      (void)))))
(define (observer-monitor! id result [started (now)])
  (observed
   started
   (lambda (old)
     (define value (vector-ref result 2))
     (define counter (cond [(string? value) 'monitor_string_errors]
                           [(pair? value) 'monitor_pair_messages]
                           [(null? value) 'monitor_empty_messages]
                           [else 'monitor_other_messages]))
     (values
      (update-record
       old id
       (lambda (r)
         (define counted
           (hash-set (hash-set r 'monitor_messages (add1 (hash-ref r 'monitor_messages)))
                     counter (add1 (hash-ref r counter))))
         (cond
           [(and (string? value) (< (length (hash-ref r 'monitor_errors)) 4))
            (hash-set counted 'monitor_errors
                      (append (hash-ref r 'monitor_errors)
                              (list (hasheq 'message (short-string value)
                                            'truncated (> (string-length value) 512)
                                            'handler_key (short-string (vector-ref result 1))))))]
           [else counted])))
      (void)))))
(define (observer-response! id result [started (now)])
  ;; Constant-time payload shape tests only: never traverse or retain traces.
  (if (eq? (vector-ref result 0) 'monitor-message)
      (observer-monitor! id result started)
      (observer-terminal! id result started)))
(define (observer-callback-enter! id current? [started (now)])
  (observed started
            (lambda (old)
              (values (update-record old id (lambda (r)
                        (hash-set (hash-set r 'callback_current (and current? #t))
                                  'callback_entered_ms (now))))
                      (void)))))
(define (observer-callback-delivered! id [started (now)])
  (observed started
            (lambda (old)
              (values (update-record old id (lambda (r) (hash-set r 'callback_delivered_ms (now))))
                      (void)))))

(define (records/list snapshot)
  (for/list ([id (in-range 1 (add1 (min (observation-count snapshot) max-requests)))])
    (hash-ref (observation-records snapshot) id)))
(define (observer-final-terminals)
  (define snapshot (unbox state))
  (for/list ([r (in-list (records/list snapshot))]
             #:when (and (hash-ref r 'final_match) (not (eq? (hash-ref r 'terminal) 'null)))) r))
(define (observer-final-outcome)
  ;; One atomic snapshot read, no locks, waits, copying, or CAS retry loop.
  (define snapshot (unbox state))
  (define id (observation-latest-final snapshot))
  (and id (zero? (observation-dropped snapshot)) (zero? (observation-error-count snapshot))
       (let ([r (hash-ref (observation-records snapshot) id)])
         (and (not (eq? (hash-ref r 'terminal) 'null))
              (eq? (hash-ref r 'callback_current) #t)
              (not (eq? (hash-ref r 'callback_delivered_ms) 'null)) r))))
(define (observer-summary)
  ;; Capture one consistent immutable state, then make the bounded return list.
  (define snapshot (unbox state))
  (define config (unbox configured))
  (hasheq 'schema_version schema-version 'observer "compact-native-online-expansion-v1"
          'enabled (enabled?) 'generation (if config (configuration-generation config) 'null)
          'expected_source (if config (configuration-source config) 'null)
          'expected_sha256 (if config (configuration-sha config) 'null)
          'expected_characters (if config (string-length (configuration-snapshot config)) 0)
          'request_count (observation-count snapshot)
          'retained_request_count (min (observation-count snapshot) max-requests)
          'request_cap max-requests 'dropped_requests (observation-dropped snapshot)
          'observer_error_count (observation-error-count snapshot)
          'observer_errors (reverse (observation-errors snapshot))
          'complete_observation (and config (zero? (observation-dropped snapshot))
                                     (zero? (observation-error-count snapshot)) #t)
          'registration_ms (if config (configuration-registration-ms config) 0.0)
          'hook_calls (observation-calls snapshot) 'hook_self_ms (observation-elapsed snapshot)
          'records (records/list snapshot)))

;; Called inside expanding-place immediately AFTER all actual handler imports.
;; module->namespace proves prior instantiation; dynamic-require is never used to
;; manufacture positive evidence by loading xref for the first time.
(define (observer-worker-init! actual-handler-entries child-limit [started (now)])
  (with-handlers ([exn:fail?
                   (lambda (e)
                     (eprintf "compact worker observer failed; no valid activation evidence: ")
                     ((error-display-handler) (exn-message e) e)
                     #f)])
    (unless (enabled?) (error 'compact-observer "Worker observer is not enabled"))
    (define xref-module 'drracket/private/syncheck/xref)
    ;; Do not turn lookup/load errors into stock "missing export" evidence.
    ;; Lookup/load errors stay explicit observer failures, never stock "missing
    ;; export" evidence. The outer guard reports the actual exception, keeps
    ;; native worker behavior running, and creates no successful init evidence.
    ;; Only the explicit failure thunk below
    ;; classifies an absent export from an already instantiated stock module.
    (define already-instantiated? (and (module->namespace xref-module) #t))
    (define resolved (resolve-module-path xref-module #f))
    (define exported
      (if already-instantiated?
          (dynamic-require xref-module 'openracket-xref-reply-cell-enabled? (lambda () 'missing))
          'not-instantiated))
    (define rec
      (hasheq 'schema_version schema-version 'event "worker-init-after-handler-imports"
              'observer "compact-native-online-expansion-v1"
              'worker_context #t 'racket_version (version)
              'actual_handler_registry
              (for/list ([entry (in-list actual-handler-entries)])
                (define key (car entry))
                (define module-spec (car key))
                (define module-file (resolve-module-path module-spec #f))
                (hasheq 'module (if (path? module-file) (path->string module-file) (format "~s" module-file))
                        'module_spec (format "~s" module-spec)
                        'export (symbol->string (cadr key)) 'monitor (and (cadr entry) #t)))
              'xref_already_instantiated already-instantiated?
              'xref_path (if (path? resolved) (path->string resolved) (short-string resolved))
              'xref_sha256 (if (path? resolved) (call-with-input-file resolved (lambda (in) (hex (sha256-bytes in)))) 'null)
              'xref_export_status (cond [(boolean? exported) "boolean"]
                                        [(eq? exported 'missing) "missing"]
                                        [(eq? exported 'not-instantiated) "not-instantiated"] [else "non-boolean"])
              'xref_reply_cell_enabled (if (boolean? exported) exported 'null)
              'xref_flag (or (getenv "OPENRACKET_XREF_REPLY_CELL") 'null)
              'child_memory_limit child-limit
              'memory_accounting_available (custodian-memory-accounting-available?)
              'observer_before_write_ms (- (now) started)))
    (define output (getenv "OPENRACKET_COMPACT_OBSERVER_OUTPUT"))
    (unless output (error 'compact-observer "Missing worker output directory"))
    ;; One worker, one evidence-file write. Existing evidence is never overwritten.
    (define before-write (now))
    (call-with-output-file (build-path output "worker-init.json") #:exists 'error
      (lambda (out) (write-json rec out) (newline out)))
    (define after-write (now))
    ;; A separate one-shot timing file avoids rewriting the evidence file or
    ;; changing a native channel. Its own small write is explicitly not measured.
    (call-with-output-file (build-path output "worker-init-overhead.json") #:exists 'error
      (lambda (out)
        (write-json
         (hasheq 'schema_version schema-version
                 'event "worker-observer-one-shot-cost"
                 'primary_write_and_close_ms (- after-write before-write)
                 'observer_through_primary_write_ms (- after-write started)
                 'timing_file_write_measured #f
                 'indirect_gc_and_scheduling_effects_measured #f) out)
        (newline out)))
    rec))
