#lang racket/base
;; Diagnostic data only. No GUI imports. All live channels remain in this process.
(require racket/file racket/path racket/place racket/serialize racket/list racket/runtime-path
         racket/format racket/match racket/port json syntax/modresolve pkg/lib)
(provide capture-registry! capture-request! capture-result! capture-status!
         worker-ready! load-capture validate-capture! summarize-result
         runtime-context make-gc-observer file-hash digest write-datum-atomic
         relevant-environment captured-terminal? capture-complete?
         restore-disposable-preferences! make-monitor-evidence observe-monitor! monitor-evidence-json)
(define-runtime-path support-self "support.rkt")
(define-runtime-path phase-probe-self "phase-probe.rkt")

(define (digest b) (bytes->hex-string (sha256-bytes b)))
(define (file-hash path)
  (and (file-exists? path) (call-with-input-file path (lambda (p) (digest (port->bytes p))))))
(define (bytes->hex-string b)
  (apply string-append
         (for/list ([x (in-bytes b)])
           (define s (number->string x 16)) (if (= (string-length s) 1) (string-append "0" s) s))))
(define (datum-bytes x)
  (define out (open-output-bytes)) (write (serialize x) out) (get-output-bytes out))
(define (write-datum-atomic path data)
  (define tmp (make-temporary-file "capture-~a.rktd" #f (path-only path)))
  (call-with-output-file tmp #:exists 'truncate/replace
    (lambda (out) (write (serialize data) out) (newline out)))
  (rename-file-or-directory tmp path #t))
(define (load-capture path)
  (call-with-input-file path (lambda (in) (deserialize (read in)))))
(define (write-json-atomic path data)
  (define tmp (make-temporary-file "capture-~a.json" #f (path-only path)))
  (call-with-output-file tmp #:exists 'truncate/replace
    (lambda (out) (write-json data out) (newline out)))
  (rename-file-or-directory tmp path #t))

(define relevant-environment
  '("PLTUSERHOME" "PLTADDONDIR" "PLTCOLLECTS" "PLTCOMPILEDROOTS"
    "XDG_CONFIG_HOME" "XDG_CACHE_HOME" "XDG_DATA_HOME"))
(define (environment-snapshot)
  (for/hasheq ([key (in-list relevant-environment)])
    (values (string->symbol key) (or (getenv key) #f))))
(define (runtime-context)
  (define pref (find-system-path 'pref-file))
  (hasheq 'version (version) 'vm (system-type 'vm) 'os (system-type 'os)
          'system-library-subpath (system-library-subpath #f)
          'racket-executable (find-executable-path (find-system-path 'exec-file))
          'collection-paths (current-library-collection-paths)
          'collection-links (current-library-collection-links)
          'compiled-roots (current-compiled-file-roots)
          'compiled-paths (use-compiled-file-paths)
          'installed-package-tables
          (for/list ([scope (in-list (get-all-pkg-scopes))])
            (cons scope (installed-pkg-table #:scope scope)))
          'cwd (current-directory)
          'preferences-path pref 'preferences-sha256 (file-hash pref)
          'environment (environment-snapshot)
          'xref-and-traversals-sources
          (for/list ([name '("xref.rkt" "traversals.rkt")])
            (define source (collection-file-path name "drracket" "private" "syncheck"))
            (list source (file-hash source)))))
(define (module-file module-path)
  (define resolved (resolve-module-path module-path #f))
  (unless (path? resolved) (error 'capture "Handler did not resolve to a source path: ~s" module-path))
  resolved)
(define (registry-files registry)
  (for/list ([row (in-list registry)])
    (match row
      [(list (? module-path? mod) (? symbol? id) (? boolean? monitor?))
       (define path (module-file mod))
       (hasheq 'module mod 'id id 'monitor? monitor? 'path path 'sha256 (file-hash path))]
      [_ (error 'capture "Unexpected actual registry row: ~s" row)])))

;; Count the genuine monitor payload without retaining or serializing capabilities.
;; This establishes schema/clean completion only, never full trace equality.
(define (make-monitor-evidence registry)
  (define online (collection-file-path "online-comp.rkt" "drracket" "private" "syncheck"))
  (hasheq 'keys
          (for/list ([row (in-list registry)]
                     #:when (and (caddr row) (equal? (simplify-path (module-file (car row)))
                                                    (simplify-path online))))
            (list (car row) (cadr row)))
          'counts (make-hasheq '((messages . 0) (trace_batches . 0) (trace_entries . 0)
                                (rename_capability_rows . 0)
                                (error_messages . 0) (invalid_payloads . 0)
                                (other_monitor_messages . 0)))
          'errors (box '())))
(define (observe-monitor! evidence result)
  (define counts (hash-ref evidence 'counts))
  (define (inc! key [n 1]) (hash-update! counts key (lambda (old) (+ old n))))
  (unless (and (vector? result) (= (vector-length result) 3)
               (eq? (vector-ref result 0) 'monitor-message))
    (error 'monitor-evidence "Malformed monitor envelope"))
  (cond
    [(not (member (vector-ref result 1) (hash-ref evidence 'keys)))
     (inc! 'other_monitor_messages)]
    [else
     (inc! 'messages)
     (define payload (vector-ref result 2))
     (cond
       [(string? payload)
        (inc! 'error_messages)
        (define errors (hash-ref evidence 'errors))
        (when (< (length (unbox errors)) 4)
          (set-box! errors (cons (hasheq 'text (substring payload 0 (min 240 (string-length payload)))
                                        'truncated (> (string-length payload) 240))
                                (unbox errors))))]
       [(and (list? payload)
             (andmap (lambda (row)
                       (and (vector? row) (positive? (vector-length row))
                            (symbol? (vector-ref row 0))
                            (regexp-match? #rx"^syncheck:" (symbol->string (vector-ref row 0)))))
                     payload))
        (inc! 'trace_batches) (inc! 'trace_entries (length payload))
        (for ([row (in-list payload)])
          (when (or (and (eq? (vector-ref row 0) 'syncheck:add-arrow/name-dup/pxpy)
                         (= (vector-length row) 14) (place-channel? (vector-ref row 12)))
                    (and (eq? (vector-ref row 0) 'syncheck:add-id-set)
                         (= (vector-length row) 4) (place-channel? (vector-ref row 2))))
            (inc! 'rename_capability_rows)))]
       [else (inc! 'invalid_payloads)])]))
(define (monitor-evidence-json evidence)
  (define counts (hash-ref evidence 'counts))
  (hash-set
   (hash-set
    (hash-set (make-immutable-hasheq (hash->list counts))
              'check_syntax_monitor_registry_entries (length (hash-ref evidence 'keys)))
    'errors (reverse (unbox (hash-ref evidence 'errors))))
   'scope "Actual CheckSyntax monitor envelope/schema/error counts only; no full trace or capability equivalence"))

(define registry #f)
(define selected-record #f)
(define selected-id #f)
(define request-number 0)
(define observed-statuses '())
(define observed-monitors 0)
(define observed-monitor-evidence #f)
(define selected-terminal #f)
(define selected-attempts '())
(define output-dir #f)
(define state-lock (make-semaphore 1))
(define (capture-enabled!)
  (unless (equal? (getenv "OPENRACKET_EXPANSION_CAPTURE") "1")
    (error 'capture "Capture function called without its explicit diagnostic flag"))
  (when (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
    (error 'capture "Integrated capture must never enable the replay readiness path"))
  (unless output-dir
    (set! output-dir (path->complete-path (or (getenv "OPENRACKET_CAPTURE_OUTPUT")
                                             (error 'capture "Missing capture output"))))
    (make-directory* output-dir)))
(define (capture-registry! actual)
  (capture-enabled!)
  (when registry (error 'capture "Multiple initialization registries are not supported in one capture"))
  (registry-files actual)
  (set! registry actual)
  (void))
(define (snapshot-bytes x)
  (cond [(string? x) (string->bytes/utf-8 x)] [(bytes? x) x]
        [else (error 'capture "Snapshot is neither a string nor WXME bytes")]))

(define (capture-request! actual child-limit)
  (capture-enabled!)
  (unless (and registry (vector? actual) (= 6 (vector-length actual))
               (place-channel? (vector-ref actual 2)) (place-channel? (vector-ref actual 4)))
    (error 'capture "Missing actual frozen registry or malformed six-field request"))
  (call-with-semaphore
   state-lock
   (lambda ()
     (set! request-number (add1 request-number))
     (define snapshot (vector-ref actual 0))
     (define sha (digest (snapshot-bytes snapshot)))
     (define expected (or (getenv "OPENRACKET_CAPTURE_EXPECTED_SHA256")
                          (error 'capture "Expected edited-snapshot digest is required")))
     (cond
       [(or selected-terminal (not (equal? sha expected))) #f]
       [else
        (when (>= (length selected-attempts) 8)
          (error 'capture "More than eight matching native requests; capture is inconclusive"))
        (unless (equal? child-limit 268435456)
          (error 'capture "Child limit differs from the authorized 256 MiB requirement"))
        (define worker (collection-file-path "expanding-place.rkt" "drracket" "private"))
        (define caller (collection-file-path "module-language.rkt" "drracket" "private"))
        (define context (runtime-context))
        (define preference-path (hash-ref context 'preferences-path))
        (define preference-bytes (and (file-exists? preference-path) (file->bytes preference-path)))
        (unless (equal? (and preference-bytes (digest preference-bytes))
                        (hash-ref context 'preferences-sha256))
          (error 'capture "Preferences changed while capturing their exact state"))
        (set! selected-id request-number)
        (set! selected-attempts (cons request-number selected-attempts))
        (set! observed-statuses '())
        (set! observed-monitors 0)
        (set! observed-monitor-evidence (make-monitor-evidence registry))
        (set! selected-record
              (hasheq 'schema-version 1 'request-id request-number
                      'snapshot snapshot 'source (vector-ref actual 1)
                      'settings (vector-ref actual 3) 'open-files (vector-ref actual 5)
                      'snapshot-sha256 sha 'snapshot-kind (if (string? snapshot) 'string 'wxme)
                      'snapshot-bytes (bytes-length (snapshot-bytes snapshot))
                      'snapshot-characters (and (string? snapshot) (string-length snapshot))
                      'registry registry 'registry-files (registry-files registry)
                      'registry-sha256 (digest (datum-bytes registry))
                      'context context 'preferences-bytes preference-bytes 'child-limit child-limit
                      'worker-path worker 'worker-sha256 (file-hash worker)
                      'caller-path caller 'caller-sha256 (file-hash caller)
                      'support-path support-self 'support-sha256 (file-hash support-self)))
        (validate-capture! selected-record #:runtime? #f)
        (write-datum-atomic (build-path output-dir (format "capture-attempt-~a.rktd" request-number)) selected-record)
        (write-datum-atomic (build-path output-dir "capture.rktd") selected-record)
        (write-json-atomic
         (build-path output-dir "capture.launch.json")
         (hasheq 'environment (environment-snapshot)
                 'cwd (path->string (current-directory))
                 'snapshot_sha256 sha 'registry_sha256 (hash-ref selected-record 'registry-sha256)))
        (persist-capture-summary!)
        selected-id]))))

(define (safe-description x)
  (define s (~s x)) (substring s 0 (min 8192 (string-length s))))
(define (summarize-result result)
  (unless (and (vector? result) (positive? (vector-length result)) (symbol? (vector-ref result 0)))
    (error 'replay "Malformed result protocol"))
  (define tag (vector-ref result 0))
  (cond
    [(eq? tag 'monitor-message)
     (hasheq 'tag "monitor-message" 'handler_key (safe-description (vector-ref result 1)))]
    [(eq? tag 'handler-results)
     (unless (= 4 (vector-length result)) (error 'replay "Malformed handler-results"))
     (define compiled (vector-ref result 3))
     (hasheq 'tag "handler-results"
             'handler_keys (for/list ([row (in-list (vector-ref result 1))]) (safe-description (car row)))
             'loaded_paths_count (length (vector-ref result 2))
             'compiled_bytes (if compiled (bytes-length (vector-ref compiled 2)) #f)
             'compiled_sha256 (and compiled (digest (vector-ref compiled 2))))]
    [(eq? tag 'abnormal-termination)
     (hasheq 'tag "abnormal-termination" 'message (vector-ref result 1)
             'explicit_out_of_memory (and (regexp-match? #rx"out of memory" (vector-ref result 1)) #t))]
    [else
     (hasheq 'tag (symbol->string tag)
             'exception_details (safe-description (vector-ref result 1))
             'exception_details_truncated (> (string-length (~s (vector-ref result 1))) 8192))]))
(define (captured-terminal? result)
  (and (vector? result) (positive? (vector-length result))
       (not (eq? (vector-ref result 0) 'monitor-message))))
(define (persist-capture-summary!)
  (when selected-record
    (write-json-atomic
     (build-path output-dir "capture-summary.json")
     (hasheq 'schema_version 1 'request_id selected-id
             'matching_request_ids (reverse selected-attempts)
             'status (if selected-terminal "terminal_observed" "awaiting_terminal")
             'snapshot_sha256 (hash-ref selected-record 'snapshot-sha256)
             'snapshot_kind (~a (hash-ref selected-record 'snapshot-kind))
             'snapshot_bytes (hash-ref selected-record 'snapshot-bytes)
             'actual_child_limit_bytes (hash-ref selected-record 'child-limit)
             'snapshot_characters (hash-ref selected-record 'snapshot-characters)
             'source (safe-description (hash-ref selected-record 'source))
             'settings (safe-description (hash-ref selected-record 'settings))
             'registry_sha256 (hash-ref selected-record 'registry-sha256)
             'registry (map safe-description registry)
             'statuses (map symbol->string (reverse observed-statuses))
             'monitor_messages observed-monitors
             'monitor_evidence (monitor-evidence-json observed-monitor-evidence) 'terminal (or selected-terminal 'null)))))
(define (capture-status! id status)
  (call-with-semaphore state-lock
    (lambda ()
      (when (equal? id selected-id)
        (set! observed-statuses (cons status observed-statuses))
        (persist-capture-summary!)))))
(define (capture-result! id result)
  (call-with-semaphore state-lock
    (lambda ()
      (when (equal? id selected-id)
        (if (captured-terminal? result)
            (set! selected-terminal (summarize-result result))
            (begin
              (set! observed-monitors (add1 observed-monitors))
              (observe-monitor! observed-monitor-evidence result)))
        ;; Avoid a disk write for every monitor batch.
        (when selected-terminal (persist-capture-summary!))))))
(define (capture-complete?) (and selected-terminal #t))

(define (validate-capture! record #:runtime? [runtime? #t])
  (unless (and (hash? record) (equal? (hash-ref record 'schema-version #f) 1))
    (error 'replay "Unsupported capture schema"))
  (unless (equal? (digest (snapshot-bytes (hash-ref record 'snapshot)))
                  (hash-ref record 'snapshot-sha256))
    (error 'replay "Snapshot digest mismatch"))
  (unless (equal? (digest (datum-bytes (hash-ref record 'registry))) (hash-ref record 'registry-sha256))
    (error 'replay "Registry digest mismatch"))
  (unless (equal? (hash-ref record 'child-limit) 268435456)
    (error 'replay "Capture did not preserve the authorized 256 MiB child limit"))
  (define settings (hash-ref record 'settings))
  (unless (and (equal? (prefab-struct-key settings) 'prefab-module-settings)
               (= (vector-length (struct->vector settings)) 7)
               (eq? (vector-ref (struct->vector settings) 5) 'none))
    (error 'replay "Capture is not the actual stock online-expansion prefab with annotations none"))
  (when runtime?
    (define actual-context (runtime-context))
    (unless (equal? (hash-ref record 'context) actual-context)
      (error 'replay "Runtime context differs from capture in fields: ~s"
             (for/list ([(key value) (in-hash (hash-ref record 'context))]
                        #:unless (equal? value (hash-ref actual-context key #f))) key)))
    (for ([key '(worker caller support)])
      (unless (equal? (file-hash (hash-ref record (string->symbol (format "~a-path" key))))
                      (hash-ref record (string->symbol (format "~a-sha256" key))))
        (error 'replay "Diagnostic source changed: ~a" key)))
    (unless (equal? (registry-files (hash-ref record 'registry)) (hash-ref record 'registry-files))
      (error 'replay "A captured handler's source or resolution changed")))
  record)

(define (restore-disposable-preferences! record output)
  ;; Native capture can flush preferences as its process exits. Restore only the
  ;; explicitly marked disposable profile; preserve the post-exit file in output.
  (define context (hash-ref record 'context))
  (define pref (hash-ref context 'preferences-path))
  (define before (file-hash pref))
  (define wanted (hash-ref context 'preferences-sha256))
  (cond
    [(equal? before wanted) (hasheq 'restored #f 'sha256 (or wanted 'null))]
    [else
     (define bytes (hash-ref record 'preferences-bytes))
     (unless (equal? (and bytes (digest bytes)) wanted)
       (error 'replay "Captured preference contents do not match the captured hash"))
     (define home-string (getenv "PLTUSERHOME"))
     (unless (and home-string
                  (equal? home-string (hash-ref (hash-ref context 'environment) 'PLTUSERHOME)))
       (error 'replay "Preference restore requires the original disposable profile"))
     (define home (simplify-path (path->complete-path home-string) #t))
     (define real-pref (simplify-path pref #t))
     (define relative (find-relative-path home real-pref))
     (unless (and (relative-path? relative) (not (member 'up (explode-path relative)))
                  (not (link-exists? pref))
                  (equal? (file->string (build-path home "openracket-diagnostic-profile"))
                          "openracket-expansion-diagnostic-profile\n"))
       (error 'replay "Refusing to restore preferences outside a marked disposable profile"))
     (when (file-exists? pref)
       (copy-file pref (build-path output "preferences-after-capture.rktd") #f))
     (cond [bytes (make-directory* (path-only pref))
                  (call-with-output-file pref #:exists 'truncate/replace
                    (lambda (out) (write-bytes bytes out)))]
           [(file-exists? pref) (delete-file pref)])
     (unless (equal? (file-hash pref) wanted) (error 'replay "Preference restoration did not verify"))
     (hasheq 'restored #t 'path (path->string pref)
             'before_sha256 (or before 'null) 'restored_sha256 (or wanted 'null)
             'scope "Only the marked disposable diagnostic profile; exact captured bytes or original absence")]))

(define (make-gc-observer logger)
  (define receiver (make-log-receiver logger 'debug 'GC))
  (define rows (make-vector 4096 #f))
  (define used 0)
  (define dropped 0)
  (define stop (make-semaphore 0))
  (define collector
    (thread
     (lambda ()
       (let loop ()
         (define row (sync (handle-evt receiver values)
                           (handle-evt (semaphore-peek-evt stop) (lambda (_) #f))))
         (when row
           (if (< used (vector-length rows))
               (begin
                 (vector-set! rows used
                              (vector (current-inexact-monotonic-milliseconds)
                                      (safe-description (vector-ref row 2))
                                      (> (string-length (~s (vector-ref row 2))) 8192)))
                 (set! used (add1 used)))
               (set! dropped (add1 dropped)))
           (loop))))))
  (define (snapshot)
    (hasheq 'monotonic_ms (current-inexact-monotonic-milliseconds)
            'gc_ms (current-gc-milliseconds) 'records_dropped dropped
            'records (for/list ([i (in-range used)]) (vector-ref rows i))))
  (values snapshot (lambda ([timeout 2]) (semaphore-post stop) (sync/timeout timeout (thread-dead-evt collector)))))

(define (worker-ready! p logger child-limit)
  (unless (and (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
               (not (equal? (getenv "OPENRACKET_EXPANSION_CAPTURE") "1")))
    (error 'replay "Readiness is only permitted in the standalone diagnostic process"))
  (unless (equal? child-limit 268435456) (error 'replay "Authorized 256 MiB child limit missing"))
  (define memory-accounting? (custodian-memory-accounting-available?))
  (unless memory-accounting? (error 'replay "Memory accounting unavailable; authorized cap cannot be enforced"))
  (define-values (snapshot stop) (make-gc-observer logger))
  (define phase-control
    (and (equal? (getenv "OPENRACKET_EXPANSION_PHASE_PROBE") "1")
         ((dynamic-require phase-probe-self 'start-probe!))))
  (define (combined-snapshot)
    (define gc (snapshot))
    (if phase-control (hash-set gc 'phase_probe (phase-control 'snapshot)) gc))
  (define (stop-all)
    (cond
      [(not phase-control) (stop)]
      [else
       (define deadline (+ (current-inexact-monotonic-milliseconds) 2000))
       (define (remaining) (max 0 (/ (- deadline (current-inexact-monotonic-milliseconds)) 1000.0)))
       (define gc-ok? (with-handlers ([exn? (lambda (_) #f)]) (stop (remaining))))
       (define phase-ok? (with-handlers ([exn? (lambda (_) #f)]) (phase-control 'stop #f (remaining))))
       (and gc-ok? phase-ok?)]))
  (define-values (remote local) (place-channel))
  (thread
   (lambda ()
     (let loop ()
       (define command (place-channel-get local))
       (case command
         [(snapshot) (place-channel-put local (combined-snapshot)) (loop)]
         [(stop) (place-channel-put local (if (stop-all) 'stopped
                                            (if phase-control 'observer-stop-failed 'gc-observer-stop-failed)))]
         [else
          (match command
            [(vector (and action (or 'phase-begin 'phase-end)) (? exact-positive-integer? trial))
             (unless phase-control (error 'replay "Phase control requires the opt-in probe"))
             (place-channel-put local (phase-control (if (eq? action 'phase-begin) 'begin 'end) trial))
             (loop)]
            [_ (error 'replay "Unsupported diagnostic control message")])]))))
  (place-channel-put p (vector 'openracket-expansion-replay-ready remote child-limit memory-accounting?))
  (unless (eq? (place-channel-get p) 'openracket-expansion-replay-continue)
    (error 'replay "Missing initialization acknowledgement")))
