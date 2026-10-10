#lang racket/base
;; Run only in an authorized native graphical session. No tool/preference bypasses.
(require racket/class racket/list racket/file racket/format json)

(define started (current-inexact-monotonic-milliseconds))
(define (now) (current-inexact-monotonic-milliseconds))
(define args (current-command-line-arguments))
(unless (= (vector-length args) 5)
  (error 'retained-host "usage: retained-host.rkt FIXTURE OUTPUT MODE EDIT-POS SIZE"))
(define fixture (path->complete-path (vector-ref args 0)))
(define output (path->complete-path (vector-ref args 1)))
(define mode (vector-ref args 2))
(define edit-pos (string->number (vector-ref args 3)))
(define expected-size (string->number (vector-ref args 4)))
(define report (make-hasheq))
(hash-set! report 'schema_version 1)
(hash-set! report 'mode mode)
(hash-set! report 'fixture (path->string fixture))
(hash-set! report 'racket_version (version))
(hash-set! report 'os (~a (system-type 'os)))
(hash-set! report 'vm (~a (system-type 'vm)))
(hash-set! report 'status "running")
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
          'process_cpu_ms (current-process-milliseconds)
          'gc_ms (current-gc-milliseconds)))

(with-handlers ([exn:fail?
                 (lambda (e)
                   (set! heartbeat-running? #f)
                   (when heartbeat-thread (kill-thread heartbeat-thread))
                   (hash-set! report 'status "failed")
                   (hash-set! report 'error (exn-message e))
                   (hash-set! report 'heartbeat_samples (reverse heartbeat-samples))
                   (persist!)
                   (eprintf "PERFORMANCE FAILED: ~a\n" (exn-message e))
                   (exit 1))])
  (record! 'memory_before_gui (memory-snapshot))
  ;; Dynamic imports put GUI and DrRacket initialization inside startup timing.
  (set! queue-callback (dynamic-require 'racket/gui/base 'queue-callback))
  (set! gui-yield (dynamic-require 'racket/gui/base 'yield))
  (set! get-top-level-windows (dynamic-require 'racket/gui/base 'get-top-level-windows))
  (set! key-event% (dynamic-require 'racket/gui/base 'key-event%))
  (on-gui
   (lambda ()
  ;; Every GUI operation below runs on the actual eventspace handler thread.
  ;; Do not pass benchmark arguments to DrRacket's own command-line parser.
  (parameterize ([current-command-line-arguments #()])
    (dynamic-require 'drracket/drracket #f))
  (define frame
    (let loop ()
      (define found
        (for/or ([w (in-list (get-top-level-windows))])
          (and (object-method-arity-includes? w 'get-definitions-text 0)
               (send w is-shown?) w)))
      (cond [found found]
            [(> (- (now) started) 90000) (error 'startup "no shown DrRacket frame after90s")]
            [else (pause .020) (loop)])))
  (record! 'fresh_process_gui_startup_ms (- (now) started))
  (define prefs-get (dynamic-require 'framework 'preferences:get))
  (define settings-keys
    '(drracket:default-instrumentation drracket:child-only-memory-limit
      framework:coloring-active drracket:online-compilation-default-on
      drracket:inline-overview-shown?
      framework:spell-check-on? framework:spell-check-strings? framework:spell-check-text?))
  (record! 'preserved_settings
           (for/hasheq ([key (in-list settings-keys)])
             (values key
                     (with-handlers ([exn:fail? (lambda (e) "UNAVAILABLE")])
                       (~s (prefs-get key))))))
  (record! 'ui_environment
           (for/hasheq ([key '("OPENRACKET_UI" "OPENRACKET_HOST_THEME" "OPENRACKET_THEME")])
             (values (string->symbol key) (or (getenv key) "unset"))))
  (define editor (send frame get-definitions-text))
  (define canvas (send frame get-definitions-canvas))
  (send frame resize 1200 820)
  (send canvas focus)
  (fence!) (pause .100)
  ;; Exactly one pending heartbeat prevents an unbounded backlog. Queue delay
  ;; and inter-callback gap are both retained to expose coordinated omission.
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
                  (set! heartbeat-samples
                        (cons (hasheq 'phase submitted-phase
                                      'dispatch_ms (- observed submitted)
                                      'callback_gap_ms (- observed previous)
                                      'at_ms (- observed started)) heartbeat-samples))
                  (semaphore-post done)) #t)
               (semaphore-wait done)
               (loop (now)))))))
  (record! 'memory_before_open (memory-snapshot))
  (set! phase "first_open")
  (record! 'first_open (timed-command (lambda () (send frame change-to-file fixture))))
  (unless (= (send editor last-position) expected-size)
    (error 'first-open "loaded character count differs: ~a vs ~a"
           (send editor last-position) expected-size))
  (record! 'loaded_characters (send editor last-position))
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
  (set! phase "initial_lexer_settle")
  (define initial-settle (await-lexer! editor))
  (record! 'initial_lexer_settle initial-settle)
  (unless (hash-ref initial-settle 'complete)
    (error 'initial-lexer-settle "lexer did not become valid within45s; warm timings invalid"))
  (record! 'memory_after_initial_settle (memory-snapshot))
  (set! phase "warm_typing")
  (define warm-samples
    (for/list ([i (in-range 80)])
      (define sample
        (timed-command (lambda () (send editor on-char (new key-event% [key-code #\a])))))
      (pause .016)
      sample))
  (record! 'warm_editor_key_samples warm-samples)
  (unless (= (send editor last-position) (+ expected-size 81))
    (error 'warm-typing "synthetic editor key count mismatch"))
  (unless (string=? (send editor get-text edit-pos (+ edit-pos 81))
                   (string-append "x" (make-string 80 #\a)))
    (error 'warm-typing "synthetic input content mismatch"))
  (set! phase "warm_jump")
  (record! 'warm_jump_samples
           (for/list ([i (in-range 12)])
             (define pos (if (even? i) near-end 0))
             (define sample
               (timed-command (lambda () (send editor set-position pos)
                                          (send editor scroll-to-position pos))))
             (pause .016)
             sample))
  (set! phase "final_lexer_settle")
  (record! 'final_lexer_settle (await-lexer! editor))
  (set! phase "idle")
  (pause .500)
  (set! heartbeat-running? #f)
  (kill-thread heartbeat-thread)
  (record! 'heartbeat_samples (reverse heartbeat-samples))
  (record! 'memory_after_workload (memory-snapshot))
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
