#lang racket/base
;; Genuine GUI diagnostic host. Hook state is scalar-only and never performs
;; reporting I/O. This host owns the sole bounded final/exception snapshot write.
(require racket/class racket/file racket/path racket/format json
         (only-in "gui-observer.rkt" digest observer-summary)
         "activation.rkt" "heartbeat.rkt")

(define config (string->jsexpr (or (getenv "OPENRACKET_CAPTURE_CONFIG")
                                  (error 'capture-host "Missing native capture configuration"))))
(define fixture (path->complete-path (hash-ref config 'fixture)))
(define output (path->complete-path (hash-ref config 'output)))
(define arm (hash-ref config 'arm))
(define expected-sha (getenv "OPENRACKET_GUI_EXPECTED_SHA256"))
(define expected-characters 1048577)
(define started (current-inexact-monotonic-milliseconds))
(define report (make-hasheq))
(define queue-callback #f)
(define gui-yield #f)
(define windows #f)
(define last-observation #f)
(define worker-init-cache #f)
(define worker-phase-cache #f)
(define activation #f)
(define heartbeat #f)
(define workload-deadline #f)

(define (persist!)
  (call-with-output-file (build-path output "capture-host.json") #:exists 'truncate/replace
    (lambda (out) (write-json report out) (newline out))))
(define (persist-observation! summary)
  ;; Called only after all final endpoints or after an exception, never while
  ;; polling and never by a GUI/pending-thread observation hook.
  (define data (string->bytes/utf-8 (jsexpr->string summary)))
  (when (> (add1 (bytes-length data)) (* 1024 1024))
    (error 'capture-host "Scalar GUI observation exceeds fixed output bound"))
  (define temporary (build-path output ".gui-observation.json.tmp"))
  (call-with-output-file temporary #:exists 'truncate/replace
    (lambda (out) (write-bytes data out) (newline out)))
  (rename-file-or-directory temporary (build-path output "gui-observation.json") #t))
(define (persist-telemetry! filename value maximum-bytes)
  ;; Host-only endpoint/failure persistence. No heartbeat/GUI hook writes files.
  (define data (string->bytes/utf-8 (jsexpr->string value)))
  (when (> (add1 (bytes-length data)) maximum-bytes)
    (error 'capture-host "Telemetry exceeds fixed output bound: ~a" filename))
  (call-with-output-file (build-path output filename) #:exists 'truncate/replace
    (lambda (out) (write-bytes data out) (newline out))))
(define (persist-extra-evidence!)
  (when activation (persist-telemetry! "activation.json" activation (* 16 1024)))
  (when heartbeat (persist-telemetry! "heartbeat.json" (heartbeat-summary heartbeat) (* 2 1024 1024))))
(define (stop-heartbeat-on-failure!)
  (when heartbeat
    (heartbeat-stop! heartbeat)
    ;; Cleanup only: never grants a later workload/evidence grace period.
    (heartbeat-join! heartbeat gui-yield
                     (min (or workload-deadline +inf.0)
                          (+ (current-inexact-monotonic-milliseconds) 1000)))))
(define (pause seconds)
  ;; All evidence-file polling remains on the existing GUI event loop.
  (gui-yield (alarm-evt (+ (current-inexact-milliseconds) (* 1000 seconds)))))
(define (finite-nonnegative? value)
  (and (real? value) (>= value 0) (< value +inf.0)))
(define (positive-count? value)
  (and (exact-integer? value) (> value 0)))
(define (zero-count? value)
  (and (exact-integer? value) (= value 0)))
(define (json-scalar? value)
  (or (boolean? value) (string? value) (eq? value 'null)
      (and (real? value) (< -inf.0 value +inf.0))))
(define (metric? value)
  (and (hash? value)
       (finite-nonnegative? (hash-ref value 'monotonic_ms #f))
       (for/and ([v (in-hash-values value)]) (json-scalar? v))))
(define (bounded-object filename maximum-bytes)
  (define path (build-path output filename))
  (cond
    [(link-exists? path) (error 'capture-host "Evidence may not be a symlink: ~a" filename)]
    [(not (file-exists? path)) #f]
    [else
     (when (> (file-size path) maximum-bytes)
       (error 'capture-host "Evidence exceeds fixed bound: ~a" filename))
     (define data (call-with-input-file path
                    (lambda (in) (read-bytes (add1 maximum-bytes) in))))
     (when (or (eof-object? data) (> (bytes-length data) maximum-bytes))
       (error 'capture-host "Evidence is empty or exceeds fixed bound: ~a" filename))
     (define value (string->jsexpr (bytes->string/utf-8 data)))
     (unless (hash? value) (error 'capture-host "Evidence is not an object: ~a" filename))
     value]))

(define required-points
  '(terminal-received terminal-callback-enter terminal-callback-return application-complete
    monitor-received monitor-callback-enter application-enter))
(define terminal-timeline '(terminal-received terminal-callback-enter terminal-callback-return))
(define application-timeline '(monitor-received monitor-callback-enter application-enter application-complete))
(define (timeline-ordered? points names)
  (apply <= (for/list ([name (in-list names)])
              (hash-ref (hash-ref points name) 'monotonic_ms))))
(define (complete-observation)
  ;; Read scalar state directly without serialization or filesystem I/O. There is
  ;; deliberately no bridge/fallback if native module-instance identity differs.
  (define summary (observer-summary))
  (set! last-observation summary)
  (and summary
       (let ()
         (unless (and (zero-count? (hash-ref summary 'error_count #f))
                      (zero-count? (hash-ref summary 'dropped_records #f)))
           (error 'capture-host "GUI observation has errors, dropped records or missing counters"))
         (define records (hash-ref summary 'records #f))
         (define ids (hash-ref summary 'matching_request_ids #f))
         (unless (and (list? records) (<= (length records) 8)
                      (andmap hash? records) (list? ids))
           (error 'capture-host "Malformed or unbounded GUI request records"))
         (define matching
           (for/list ([record (in-list records)]
                      #:when (and (equal? (hash-ref record 'snapshot_sha256 #f) expected-sha)
                                  (equal? (hash-ref record 'snapshot_characters #f) expected-characters)))
             record))
         (when (or (> (length ids) 1) (> (length matching) 1))
           (error 'capture-host "Ambiguous edited snapshot: more than one matching request"))
         (and (= (length ids) 1) (= (length matching) 1)
              (let* ([record (car matching)]
                     [id (hash-ref record 'request_id #f)]
                     [terminal (hash-ref record 'terminal #f)]
                     [monitor (hash-ref record 'monitor_evidence #f)]
                     [points (hash-ref record 'gui_points #f)]
                     [registry (hash-ref summary 'actual_registry #f)])
                (unless (and (positive-count? id) (equal? ids (list id))
                             (= 1 (for/sum ([r (in-list records)])
                                    (if (equal? (hash-ref r 'request_id #f) id) 1 0))))
                  (error 'capture-host "Selected request ID is missing, duplicated or inconsistent"))
                (and (hash? terminal) (equal? (hash-ref terminal 'tag #f) "handler-results")
                     (list? registry) (pair? registry)
                     (hash? monitor)
                     (positive-count? (hash-ref monitor 'trace_entries #f))
                     (positive-count? (hash-ref monitor 'rename_capability_rows #f))
                     (zero-count? (hash-ref monitor 'error_messages #f))
                     (zero-count? (hash-ref monitor 'invalid_payloads #f))
                     (eq? (hash-ref record 'terminal_callback_current #f) #t)
                     (eq? (hash-ref record 'application_current #f) #t)
                     (eq? (hash-ref record 'application_cancelled 'missing) #f)
                     (zero-count? (hash-ref record 'stale_application_events #f))
                     (zero-count? (hash-ref record 'point_duplicates #f))
                     (hash? points)
                     (for/and ([name (in-list required-points)])
                       (metric? (hash-ref points name #f)))
                     ;; Stock monitor application can finish before compilation's
                     ;; terminal arrives. These timelines are independent.
                     (timeline-ordered? points terminal-timeline)
                     (timeline-ordered? points application-timeline)
                     record))))))

(define (actual-worker-ready?)
  (define worker (or worker-init-cache (bounded-object "worker-init.json" (* 16 1024))))
  (and worker
       (begin
         (unless worker-init-cache
           (unless (and (equal? (hash-ref worker 'child_limit_bytes #f) 268435456)
                        (eq? (hash-ref worker 'memory_accounting_available #f) #t))
             (error 'capture-host "Actual worker did not verify 256 MiB limit and memory accounting"))
           (set! worker-init-cache worker)
           (hash-set! report 'actual_worker_child_limit_bytes (hash-ref worker 'child_limit_bytes))
           (hash-set! report 'actual_worker_memory_accounting_available #t))
         #t)))
(define (worker-report-ready?)
  ;; No readiness/control rendezvous is introduced. This is a post-send data-only
  ;; file in BOTH arms, with producer points disabled in both timing arms. Once read,
  ;; scalar evidence is cached so a GUI poll never repeatedly reparses it.
  (or worker-phase-cache
      (let ([value (bounded-object "worker-phase-1.json" (* 64 1024))])
        (and value
             (begin
               (unless (eq? (hash-ref value 'phase_points_enabled 'missing) #f)
                 (error 'capture-host "Producer phase points must be disabled in both timing arms"))
               (set! worker-phase-cache value)
               #t)))))
(define (on-gui thunk)
  (define done (make-semaphore 0))
  (define result #f)
  (queue-callback
   (lambda ()
     (with-handlers ([exn? (lambda (e) (set! result e))]) (thunk))
     (semaphore-post done)) #f)
  (gui-yield (semaphore-peek-evt done))
  (when result (raise result)))

(hash-set! report 'measurement_kind "genuine_gui_interval_map_timing; closed-loop queue/handler observations, not physical input-to-photon or actual typing")
(hash-set! report 'status "starting")
(hash-set! report 'arm arm)
(hash-set! report 'phase_points_enabled #f)
(hash-set! report 'fixture (path->string fixture))
(hash-set! report 'os (~a (system-type 'os)))
(hash-set! report 'racket_version (version))
(persist!)
(with-handlers ([exn? (lambda (e)
                       (hash-set! report 'status "failed")
                       (hash-set! report 'error (exn-message e))
                       (with-handlers ([exn? (lambda (cleanup-error)
                                              (hash-set! report 'heartbeat_cleanup_error
                                                         (exn-message cleanup-error)))])
                         (stop-heartbeat-on-failure!))
                       (with-handlers ([exn? (lambda (write-error)
                                              (hash-set! report 'observation_write_error
                                                         (exn-message write-error)))])
                         (persist-observation! (observer-summary))
                         (persist-extra-evidence!))
                       (persist!) (eprintf "CAPTURE FAILED: ~a\n" (exn-message e)) (exit 1))])
  (unless (and (member arm '("stock" "candidate"))
               (equal? (getenv "OPENRACKET_GUI_OBSERVER") "1")
               (equal? (getenv "OPENRACKET_GUI_EXPECTED_SOURCE") (path->string fixture))
               (equal? (getenv "OPENRACKET_GUI_OBSERVER_OUTPUT") (path->string output))
               (equal? (getenv "OPENRACKET_GUI_EXPECTED_CHARACTERS") "1048577")
               (equal? expected-sha "f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735")
               (= (hash-ref config 'edit_position) 524139)
               (not (getenv "OPENRACKET_GUI_PHASE_POINTS"))
               (if (equal? arm "candidate")
                   (equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1")
                   (not (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET")))
               (not (getenv "OPENRACKET_EXPANSION_REPLAY"))
               (not (getenv "OPENRACKET_EXPANSION_CAPTURE")))
    (error 'capture-host "Genuine GUI capture configuration does not match the selected arm"))
  (current-command-line-arguments #())
  (set! queue-callback (dynamic-require 'racket/gui/base 'queue-callback))
  (set! gui-yield (dynamic-require 'racket/gui/base 'yield))
  (set! windows (dynamic-require 'racket/gui/base 'get-top-level-windows))
  (define key-event% (dynamic-require 'racket/gui/base 'key-event%))
  (on-gui
   (lambda ()
     (dynamic-require 'drracket/drracket #f)
     (define frame
       (let loop ()
         (define found
           (for/or ([w (in-list (windows))])
             (and (object-method-arity-includes? w 'get-definitions-text 0)
                  (send w is-shown?) w)))
         (cond [found found]
               [(> (- (current-inexact-monotonic-milliseconds) started) 90000)
                (error 'capture-host "No real DrRacket frame within 90 seconds")]
               [else (pause .02) (loop)])))
     (unless (eq? (current-thread)
                  ((dynamic-require 'racket/gui/base 'eventspace-handler-thread)
                   ((dynamic-require 'racket/gui/base 'current-eventspace))))
       (error 'capture-host "Activation and heartbeat must run on the actual GUI handler thread"))
     (set! activation
           (hash-set (gui-activation-evidence
                      arm (hash-ref config 'expected_interval_map_source_sha256))
                     'gui_handler_thread #t))
     (unless (hash-ref activation 'verified)
       (error 'capture-host "Actual GUI interval-map source, flag or export does not match arm"))
     (hash-set! report 'activation_verified #t)
     (define editor (send frame get-definitions-text))
     (define canvas (send frame get-definitions-canvas))
     (define prefs-get (dynamic-require 'framework 'preferences:get))
     (define child-limit (prefs-get 'drracket:child-only-memory-limit))
     (define online? (prefs-get 'drracket:online-compilation-default-on))
     (define coloring? (prefs-get 'framework:coloring-active))
     (hash-set! report 'preserved_preferences
                (hasheq 'child_limit_bytes child-limit 'online_compilation online? 'coloring coloring?))
     (unless (and (equal? child-limit 268435456) online? coloring?)
       (error 'capture-host "Native defaults differ: require authorized 256 MiB child limit, online expansion and coloring"))
     (send frame resize 1200 820)
     (send canvas focus)
     (set! heartbeat (start-heartbeat! queue-callback))
     (hash-set! report 'workload_started_monotonic_ms (current-inexact-monotonic-milliseconds))
     (send frame change-to-file fixture)
     (unless (= (send editor last-position) 1048576)
       (error 'capture-host "Fixture length differs from base mixed-1MiB"))
     (define pos (hash-ref config 'edit_position))
     (send editor set-position pos)
     (send editor scroll-to-position pos)
     (send editor on-char (new key-event% [key-code #\x]))
     (unless (and (= (send editor last-position) expected-characters)
                  (string=? (send editor get-text pos (add1 pos)) "x"))
       (error 'capture-host "Native key event did not produce the exact first edit"))
     (hash-set! report 'edit_dispatched_monotonic_ms (current-inexact-monotonic-milliseconds))
     (hash-set! report 'edited_snapshot_sha256 (digest (string->bytes/utf-8 (send editor get-text))))
     (unless (equal? (hash-ref report 'edited_snapshot_sha256) expected-sha)
       (error 'capture-host "Native edited snapshot digest mismatch"))
     ;; Read actual selected Run settings without changing them. The common
     ;; observer separately records the actual online worker settings/registry.
     (define next-settings (send editor get-next-settings))
     (define get-lang (dynamic-require 'drracket/tool-lib 'drracket:language-configuration:language-settings-language))
     (define get-settings (dynamic-require 'drracket/tool-lib 'drracket:language-configuration:language-settings-settings))
     (hash-set! report 'pending_run_configuration_scope "get-next-settings: pending next Run, not worker instrumentation")
     (hash-set! report 'pending_run_serialized_settings
                (~s (send (get-lang next-settings) marshall-settings (get-settings next-settings))))
     ;; This is the one original absolute post-edit deadline. Receipt, callback,
     ;; application, lexer and worker report all consume this same budget.
     (define deadline (+ (current-inexact-monotonic-milliseconds) 90000))
     (set! workload-deadline deadline)
     (hash-set! report 'post_edit_deadline_monotonic_ms deadline)
     (define first-lexer-valid #f)
     (define completed-record
       (let loop ()
         (when (>= (current-inexact-monotonic-milliseconds) deadline)
           (error 'capture-host "GUI terminal/application/lexer/worker evidence incomplete within original 90-second deadline"))
         (define lexer-valid? (send editor is-lexer-valid?))
         (when (and lexer-valid? (not first-lexer-valid))
           (unless (and (= (send editor last-position) expected-characters)
                        (equal? (digest (string->bytes/utf-8 (send editor get-text))) expected-sha))
             (error 'capture-host "Source changed before first final-lexer-valid observation"))
           (set! first-lexer-valid (current-inexact-monotonic-milliseconds))
           (hash-set! report 'first_final_lexer_valid_observed_monotonic_ms first-lexer-valid))
         (define record (complete-observation))
         (define worker-ready? (actual-worker-ready?))
         (define report-ready? (worker-report-ready?))
         (cond [(and record worker-ready? report-ready? lexer-valid?) record]
               [else (pause .02) (loop)])))
     (define points (hash-ref completed-record 'gui_points))
     (for ([point (in-list required-points)]
           [field (in-list '(terminal_received_monotonic_ms
                            terminal_callback_enter_monotonic_ms
                            terminal_callback_return_monotonic_ms
                            application_complete_monotonic_ms
                            monitor_received_monotonic_ms
                            monitor_callback_enter_monotonic_ms
                            application_enter_monotonic_ms))])
       (hash-set! report field (hash-ref (hash-ref points point) 'monotonic_ms)))
     (hash-set! report 'matching_request_id (hash-ref completed-record 'request_id))
     (hash-set! report 'final_snapshot_characters (send editor last-position))
     (hash-set! report 'final_snapshot_sha256 (digest (string->bytes/utf-8 (send editor get-text))))
     (hash-set! report 'source_unchanged
                (and (= (hash-ref report 'final_snapshot_characters) expected-characters)
                     (equal? (hash-ref report 'final_snapshot_sha256) expected-sha)))
     (hash-set! report 'lexer_valid_at_completion (send editor is-lexer-valid?))
     (unless (and (hash-ref report 'source_unchanged) (hash-ref report 'lexer_valid_at_completion)
                  (< (current-inexact-monotonic-milliseconds) deadline))
       (error 'capture-host "Final unchanged-source/lexer/deadline gate failed"))
     (hash-set! report 'workload_completed_monotonic_ms (current-inexact-monotonic-milliseconds))
     (heartbeat-stop! heartbeat)
     (unless (and (heartbeat-join! heartbeat gui-yield deadline) (heartbeat-ok? heartbeat))
       (error 'capture-host "GUI heartbeat did not stop/join cleanly within original deadline"))
     (hash-set! report 'heartbeat_verified #t)
     ;; Join can dispatch queued GUI work. Revalidate after the LAST yield so
     ;; final source, lexer and annotation-currentness evidence cannot be stale.
     (define final-record (complete-observation))
     (unless (and final-record
                  (equal? (hash-ref final-record 'request_id)
                          (hash-ref completed-record 'request_id)))
       (error 'capture-host "Selected annotation application changed during heartbeat cleanup"))
     (hash-set! report 'final_snapshot_characters (send editor last-position))
     (hash-set! report 'final_snapshot_sha256 (digest (string->bytes/utf-8 (send editor get-text))))
     (hash-set! report 'source_unchanged
                (and (= (hash-ref report 'final_snapshot_characters) expected-characters)
                     (equal? (hash-ref report 'final_snapshot_sha256) expected-sha)))
     (hash-set! report 'lexer_valid_at_completion (send editor is-lexer-valid?))
     (unless (and (hash-ref report 'source_unchanged) (hash-ref report 'lexer_valid_at_completion)
                  (< (current-inexact-monotonic-milliseconds) deadline))
       (error 'capture-host "Post-join final source/lexer/deadline gate failed"))
     (hash-set! report 'post_join_final_verification_monotonic_ms (current-inexact-monotonic-milliseconds))
     (persist-observation! last-observation)
     (persist-extra-evidence!)
     (unless (< (current-inexact-monotonic-milliseconds) deadline)
       (error 'capture-host "Final scalar observation write exceeded original 90-second deadline"))
     (hash-set! report 'status "gui_application_complete")
     (hash-set! report 'elapsed_ms (- (current-inexact-monotonic-milliseconds) started))
     (persist!)))
  ;; Exit without save dialogs or further editor changes. The unchanged external
  ;; process-group cleanup owns all remaining process cleanup.
  (exit 0))
