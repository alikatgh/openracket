#lang racket/base
;; Run only in an authorized native graphical session. No tool/preference bypasses.
(require racket/class racket/list racket/file racket/format racket/runtime-path json)

(define-runtime-path diagnostics-path "diagnostics.rkt")
(define-runtime-path settings-path "settings.rkt")
(define-runtime-path activation-path "activation.rkt")
(define-runtime-path budget-activation-path "budget-activation.rkt")
(define started (current-inexact-monotonic-milliseconds))
(define (now) (current-inexact-monotonic-milliseconds))
(unless (zero? (vector-length (current-command-line-arguments)))
  (error 'retained-host "benchmark config must use OPENRACKET_BENCH_CONFIG, never GUI launch arguments"))
(define config
  (string->jsexpr (or (getenv "OPENRACKET_BENCH_CONFIG")
                     (error 'retained-host "missing OPENRACKET_BENCH_CONFIG"))))
(define fixture (path->complete-path (hash-ref config 'fixture)))
(define output (path->complete-path (hash-ref config 'output)))
(define mode (hash-ref config 'mode))
(define edit-pos (hash-ref config 'edit_position))
(define expected-size (hash-ref config 'characters))
(define profile-enabled? (hash-ref config 'profile #f))
(define metadata-only? (hash-ref config 'metadata_only #f))
(define finish-profile #f)
(define get-observer-summary #f)
(define get-observer-final-outcome #f)
(define expected-final-source #f)
(define diagnostic-root-logger (current-logger))
(define last-heartbeat-time (now))
;; Stock reads launch arguments later in its initial-frame callback. No benchmark
;; config is passed as process arguments, and this is set before GUI creation.
(current-command-line-arguments #())
(define report (make-hasheq))
(hash-set! report 'schema_version 1)
(hash-set! report 'mode mode)
(hash-set! report 'fixture (path->string fixture))
(hash-set! report 'racket_version (version))
(hash-set! report 'os (~a (system-type 'os)))
(hash-set! report 'vm (~a (system-type 'vm)))
(hash-set! report 'status "running")
(hash-set! report 'measurement_kind "matched_gui_with_common_compact_observer")
(define (persist!)
  (call-with-output-file output #:exists 'truncate/replace
    (lambda (port) (write-json report port) (newline port))))
(define (record! key value) (hash-set! report key value) (persist!))
(define phase "startup")
(define heartbeat-samples null)
(define heartbeat-running? #t)
(define heartbeat-thread #f)
(define queue-callback #f)
(define gui-yield #f)
(define get-top-level-windows #f)
(define key-event% #f)
(define startup-finished? #f)
(define startup-watcher #f)
(define (describe-startup-widget widget [depth 0])
  (define (safe thunk)
    (with-handlers ([exn:fail? (lambda (e) (exn-message e))]) (thunk)))
  (define (short text)
    (if (string? text) (substring text 0 (min 2048 (string-length text))) (~s text)))
  (hasheq
   'class (~a (object-name widget))
   'label (if (object-method-arity-includes? widget 'get-label 0)
              (safe (lambda () (short (send widget get-label)))) "")
   'editor_text
   (if (object-method-arity-includes? widget 'get-editor 0)
       (safe (lambda ()
               (define ed (send widget get-editor))
               (if (and ed (object-method-arity-includes? ed 'get-text 0))
                   (short (send ed get-text)) ""))) "")
   'children
   (if (and (< depth 8) (object-method-arity-includes? widget 'get-children 0))
       (safe (lambda () (for/list ([child (in-list (send widget get-children))])
                         (describe-startup-widget child (add1 depth))))) null)))
(define (on-gui thunk)
  (define done (make-semaphore))
  (define result #f)
  (queue-callback
   (lambda ()
     (with-handlers ([exn? (lambda (e) (set! result (cons 'error e)))])
       (set! result (cons 'value (thunk))))
     (semaphore-post done)) #f)
  (gui-yield (semaphore-peek-evt done))
  (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))
(define (pause seconds)
  (gui-yield (alarm-evt (+ (current-inexact-milliseconds) (* seconds 1000.0)))))
;; This is a queue fence, not an assertion that pixels have been presented.
(define (fence!)
  (define done (make-semaphore))
  (queue-callback (lambda () (semaphore-post done)) #f)
  (gui-yield (semaphore-peek-evt done)))
(define (timed-command thunk)
  (define start (now))
  (thunk)
  (define returned (now))
  (fence!)
  (hasheq 'command_ms (- returned start)
          'command_plus_low_priority_fence_ms (- (now) start)))
(define (await-lexer! editor [limit-ms 45000])
  (define start (now))
  (let loop ([valid-count 0])
    (define valid? (send editor is-lexer-valid?))
    (cond
      [(and valid? (>= valid-count 2))
       (hasheq 'complete #t 'elapsed_ms (- (now) start))]
      [(>= (- (now) start) limit-ms)
       (hasheq 'complete #f 'elapsed_ms (- (now) start))]
      [else (pause .020) (loop (if valid? (add1 valid-count) 0))])))
(define (memory-snapshot)
  (hasheq 'racket_managed_bytes (current-memory-use)
          'racket_cumulative_allocated_bytes (current-memory-use 'cumulative)
          'racket_peak_allocated_bytes (current-memory-use 'peak)
          'process_cpu_ms (current-process-milliseconds)
          'gc_ms (current-gc-milliseconds)))

(with-handlers ([exn:fail?
                 (lambda (e)
                   (set! heartbeat-running? #f)
                   (set! startup-finished? #t)
                   (hash-set! report 'status "failed")
                   (hash-set! report 'error (exn-message e))
                   (hash-set! report 'heartbeat_samples (reverse heartbeat-samples))
                   (when get-observer-summary
                     (with-handlers ([exn:fail? (lambda (_) (void))])
                       (hash-set! report 'online_expansion_observer (get-observer-summary))))
                   (when get-observer-final-outcome
                     (with-handlers ([exn:fail? (lambda (_) (void))])
                       (hash-set! report 'online_expansion_outcome
                                  (or (get-observer-final-outcome) 'null))))
                   (persist!)
                   (eprintf "PERFORMANCE FAILED: ~a\n" (exn-message e))
                   (exit 1))])
  (record! 'memory_before_gui (memory-snapshot))
  (define observer-support
    (string->path (or (getenv "OPENRACKET_COMPACT_OBSERVER_SUPPORT")
                     (error 'observer "Missing reviewed compact observer helper"))))
  (set! get-observer-summary (dynamic-require observer-support 'observer-summary))
  (set! get-observer-final-outcome (dynamic-require observer-support 'observer-final-outcome))
  (define registration-start (now))
  (set! expected-final-source
        (string->immutable-string
         (let ([original (file->string fixture)])
           (string-append (substring original 0 edit-pos) "x" (make-string 80 #\a)
                          (substring original edit-pos)))))
  ((dynamic-require observer-support 'observer-register-final!)
   expected-final-source #:generation 1 #:source fixture)
  (record! 'observer_registration_ms (- (now) registration-start))
  (record! 'observer_support_sha256 (hash-ref config 'observer_support_sha256))
  (record! 'initial_gui_argv (vector->list (current-command-line-arguments)))
  ;; Dynamic imports put GUI and DrRacket initialization inside startup timing.
  (set! queue-callback (dynamic-require 'racket/gui/base 'queue-callback))
  (set! gui-yield (dynamic-require 'racket/gui/base 'yield))
  (set! get-top-level-windows (dynamic-require 'racket/gui/base 'get-top-level-windows))
  (set! key-event% (dynamic-require 'racket/gui/base 'key-event%))
  (define dialog% (dynamic-require 'racket/gui/base 'dialog%))
  ;; A modal dialog still dispatches queued callbacks. Observe it without clicking,
  ;; dismissing, changing preferences, or treating a timeout as a latency sample.
  (set! startup-watcher
        (thread
         (lambda ()
           (let loop ()
             (sleep .5)
             (unless startup-finished?
               (queue-callback
                (lambda ()
                  (unless (or startup-finished? (hash-has-key? report 'startup_dialog_diagnostic))
                    (define dialogs
                      (filter (lambda (w) (and (is-a? w dialog%) (send w is-shown?)))
                              (get-top-level-windows)))
                    (when (pair? dialogs)
                      (record! 'startup_dialog_diagnostic
                               (hasheq 'current_argv (vector->list (current-command-line-arguments))
                                       'shown_dialogs (map describe-startup-widget dialogs)))))) #t)
               (loop))))))
  (on-gui
   (lambda ()
  ;; Every GUI operation below runs on the actual eventspace handler thread.
  ;; Do not pass benchmark arguments to DrRacket's own command-line parser.
  (dynamic-require 'drracket/drracket #f)
  (define frame
    (let loop ()
      (define found
        (for/or ([w (in-list (get-top-level-windows))])
          (and (object-method-arity-includes? w 'get-definitions-text 0)
               (send w is-shown?) w)))
      (cond [found found]
            [(> (- (now) started) 90000) (error 'startup "no shown DrRacket frame after90s")]
            [else (pause .020) (loop)])))
  (set! startup-finished? #t)
  (record! 'fresh_process_gui_startup_ms (- (now) started))
  ;; DrRacket manages its own custodian context. Cooperative shutdown plus the
  ;; read-only death event requires no authority over the monitor's custodian.
  (gui-yield (thread-dead-evt startup-watcher))
  (record! 'gui_argv_after_startup (vector->list (current-command-line-arguments)))
  (define prefs-get (dynamic-require 'framework 'preferences:get))
  (define settings-keys
    '(drracket:child-only-memory-limit
      framework:coloring-active drracket:online-compilation-default-on
      drracket:inline-overview-shown?
      framework:spell-check-on? framework:spell-check-strings? framework:spell-check-text?))
  (record! 'preserved_settings
           (for/hasheq ([key (in-list settings-keys)])
             (values key
                     (with-handlers ([exn:fail? (lambda (e) "UNAVAILABLE")])
                       (~s (prefs-get key))))))
  (record! 'ui_environment
           (for/hasheq ([key '("OPENRACKET_UI" "OPENRACKET_HOST_THEME" "OPENRACKET_THEME"
                            "OPENRACKET_ALL_STRING_FAST_PATH"
                            "OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS")])
             (values (string->symbol key) (or (getenv key) "unset"))))
  (define editor (send frame get-definitions-text))
  (define canvas (send frame get-definitions-canvas))
  ;; Matched to the verified1024x768 Mac runner desktop. Historical offscreen
  ;; windows are not a direct comparison for this newly paired workload.
  (send frame resize 1000 700)
  (send canvas focus)
  (fence!) (pause .100)
  ;; Exactly one pending heartbeat prevents an unbounded backlog. Queue delay
  ;; and inter-callback gap are both retained to expose coordinated omission.
  (set! last-heartbeat-time (now))
  (set! heartbeat-thread
        (thread
         (lambda ()
           (let loop ([previous (now)])
             (when heartbeat-running?
               (sleep .016)
               (define submitted (now))
               (define submitted-phase phase)
               (define done (make-semaphore))
               (queue-callback
                (lambda ()
                  (define observed (now))
                  (set! last-heartbeat-time observed)
                  (set! heartbeat-samples
                        (cons (hasheq 'phase submitted-phase
                                      'dispatch_ms (- observed submitted)
                                      'callback_gap_ms (- observed previous)
                                      'at_ms (- observed started)) heartbeat-samples))
                  (semaphore-post done)) #t)
               (semaphore-wait done)
               (loop (now)))))))
  (when profile-enabled?
    (set! finish-profile
          ((dynamic-require diagnostics-path 'start-diagnostics)
           (current-thread) (lambda () phase) (lambda () last-heartbeat-time)
           #:logger diagnostic-root-logger)))
  (record! 'scan_activation
           ((dynamic-require activation-path 'verify-scan-activation)
            (hash-ref config 'scan_activation "none")))
  (record! 'budget_activation
           ((dynamic-require budget-activation-path 'verify-budget-activation)
            (hash-ref config 'budget_activation "none")))
  (record! 'memory_before_open (memory-snapshot))
  (set! phase "first_open")
  (define initial-open-start (now))
  (record! 'first_open (timed-command (lambda () (send frame change-to-file fixture))))
  (unless (= (send editor last-position) expected-size)
    (error 'first-open "loaded character count differs: ~a vs ~a"
           (send editor last-position) expected-size))
  (record! 'loaded_characters (send editor last-position))
  (record! 'loaded_filename (~a (send editor get-filename)))
  (record! 'loaded_prefix (send editor get-text 0 (min 128 expected-size)))
  (define (capture-settings!)
    (set! phase "metadata_capture")
    (record! 'selected_language_settings
             ((dynamic-require settings-path 'capture-language-settings) editor fixture)))
  (when metadata-only?
    (capture-settings!)
    (set! heartbeat-running? #f)
    (gui-yield (thread-dead-evt heartbeat-thread))
    (record! 'heartbeat_samples (reverse heartbeat-samples))
    (record! 'status
             (if (equal? (hash-ref (hash-ref report 'selected_language_settings) 'status) "complete")
                 "complete" "failed"))
    (send editor set-modified #f)
    (send frame show #f)
    (exit (if (equal? (hash-ref report 'status) "complete") 0 1)))
  ;; Jump occurs before waiting for coloring to finish, at the first file open.
  (set! phase "first_jump")
  (define near-end (max 0 (- expected-size 2048)))
  (record! 'first_jump
           (timed-command
            (lambda () (send editor set-position near-end)
                       (send editor scroll-to-position near-end))))
  (record! 'lexer_valid_after_first_jump (send editor is-lexer-valid?))
  (set! phase "first_edit")
  (record! 'first_edit
           (timed-command (lambda ()
                            (send editor set-position edit-pos)
                            (send editor scroll-to-position edit-pos)
                            (send editor on-char (new key-event% [key-code #\x])))))
  (unless (= (send editor last-position) (add1 expected-size))
    (error 'first-edit "synthetic editor key event did not insert exactly one character"))
  ;; Separate experiment: type while initial coloring may still be pending.
  ;; This is deliberately not comparable to the settled-input scan workload.
  (record! 'memory_before_contention (memory-snapshot))
  (set! phase "initial_coloring_typing")
  (define contention-start (now))
  (define next-contention-deadline (+ contention-start 16.0))
  (define contention-reversed null)
  (define contention-error #f)
  ;; One outstanding request avoids an unbounded synthetic input backlog.
  ;; The producer sleeps off the GUI thread and timestamps actual enqueueing.
  (define contention-producer
    (thread
     (lambda ()
       (for ([i (in-range 80)] #:break contention-error)
         (define scheduled next-contention-deadline)
         (sleep (max 0 (/ (- scheduled (now)) 1000.0)))
         (define done (make-semaphore))
         (define submitted (now))
         (queue-callback
          (lambda ()
            (with-handlers ([(lambda (_) #t) (lambda (e) (set! contention-error (cons 'raised e)))])
              (define dispatched (now))
              (define valid-before? (send editor is-lexer-valid?))
              (define editor-completed #f)
              (define sample
                (timed-command (lambda ()
                                 (send editor on-char (new key-event% [key-code #\a]))
                                 (set! editor-completed (now)))))
              (define fenced (now))
              (define valid-after? (send editor is-lexer-valid?))
              (define dispatch-ms (- dispatched submitted))
              (set! contention-reversed
                    (cons (for/fold ([result sample])
                                    ([key '(ordinal lexer_valid_before lexer_valid_after
                                                    queue_to_handler_ms
                                                    queue_to_editor_completion_ms
                                                    queue_to_fence_ms
                                                    producer_scheduling_delay_ms
                                                    scheduled_to_editor_completion_ms
                                                    scheduled_to_fence_ms)]
                                     [value (list i valid-before? valid-after? dispatch-ms
                                                  (- editor-completed submitted)
                                                  (- fenced submitted)
                                                  (max 0 (- submitted scheduled))
                                                  (- editor-completed scheduled)
                                                  (- fenced scheduled))])
                            (hash-set result key value))
                          contention-reversed))
              (set! next-contention-deadline (+ fenced 16.0)))
            (semaphore-post done)) #t)
         (semaphore-wait done)))))
  (gui-yield (thread-dead-evt contention-producer))
  (when contention-error
    (if (exn? (cdr contention-error))
        (raise (cdr contention-error))
        (error 'initial-coloring-typing "callback raised a non-exception: ~e" (cdr contention-error))))
  (define contention-samples (reverse contention-reversed))
  (unless (= (length contention-samples) 80)
    (error 'initial-coloring-typing "producer did not complete exactly 80 requests"))
  (define contention-elapsed (- (now) contention-start))
  (record! 'initial_coloring_key_samples contention-samples)
  (record! 'initial_coloring_typing_phase_ms contention-elapsed)
  (record! 'keys_starting_with_lexer_invalid
           (for/sum ([sample (in-list contention-samples)])
             (if (hash-ref sample 'lexer_valid_before) 0 1)))
  (record! 'memory_after_contention (memory-snapshot))
  (unless (= (send editor last-position) (+ expected-size 81))
    (error 'initial-coloring-typing "synthetic editor key count mismatch"))
  (unless (string=? (send editor get-text edit-pos (+ edit-pos 81))
                   (string-append "x" (make-string 80 #\a)))
    (error 'initial-coloring-typing "synthetic input content mismatch"))
  (set! phase "post_typing_lexer_settle")
  (define post-typing-settle (await-lexer! editor))
  (define completed-workload-ms (- (now) initial-open-start))
  (record! 'post_typing_lexer_settle post-typing-settle)
  (record! 'open_to_completed_workload_ms completed-workload-ms)
  (unless (hash-ref post-typing-settle 'complete)
    (error 'post-typing-lexer-settle "lexer did not become valid within 45 seconds"))
  (record! 'memory_after_post_typing_settle (memory-snapshot))
  ;; Keep the old lexer endpoint separate from actual final tool observation.
  ;; This15s wait remains inside the unchanged60s outer trial bound.
  (set! phase "online_terminal_observation")
  (define terminal-wait-start (now))
  (define online-outcome
    (let loop ()
      (define outcome (get-observer-final-outcome))
      (cond [outcome outcome]
            [(>= (- (now) terminal-wait-start) 15000) #f]
            [else (pause .020) (loop)])))
  (define terminal-observed (now))
  (record! 'online_terminal_wait
           (hasheq 'complete (and online-outcome #t)
                   'elapsed_ms (- terminal-observed terminal-wait-start)))
  (record! 'online_expansion_outcome (or online-outcome 'null))
  (record! 'open_to_terminal_callback_observed_ms (- terminal-observed initial-open-start))
  (when online-outcome
    (record! 'open_to_terminal_callback_ms
             (- (hash-ref online-outcome 'callback_delivered_ms) initial-open-start)))
  (record! 'memory_after_terminal_observation (memory-snapshot))
  (record! 'online_expansion_observer (get-observer-summary))
  (unless online-outcome
    (error 'online-terminal "No final-source terminal callback within separate15s observation bound"))
  (set! phase "idle")
  (pause .500)
  (set! heartbeat-running? #f)
  (gui-yield (thread-dead-evt heartbeat-thread))
  (record! 'heartbeat_samples (reverse heartbeat-samples))
  (record! 'memory_after_workload (memory-snapshot))
  (when finish-profile (record! 'diagnostics (finish-profile)))
  ;; Metadata imports are outside every latency/profile phase.
  (capture-settings!)
  ;; Full source comparison is deliberately outside every timed/GC workload.
  (unless (string=? (send editor get-text) expected-final-source)
    (error 'contention-source "Full resulting source differs from the intended edits"))
  (record! 'exact_resulting_source_verified #t)
  ;; Explicit collection only after all latency work; do not hide allocation/GC.
  (collect-garbage) (collect-garbage)
  (record! 'memory_after_explicit_gc (memory-snapshot))
  (record! 'measured_workload_ms (- (now) started))
  (record! 'status "complete")
  ;; Never save edits; all frames and profiles belong to this disposable process.
  (send editor set-modified #f)
  (send frame show #f)
  (printf "PERFORMANCE COMPLETE ~a ~a\n" mode expected-size)
  (flush-output)
  (exit 0))))
