#lang racket/base
;; Native-only correctness caller. PREPARED, NOT EXECUTED LOCALLY.
;; Contract: racket independent-native-autosave-host.rkt stock|candidate-off|candidate-on
;; Supply a fresh PLTUSERHOME and a separate actual full Racket 9.3 runtime per arm.
;; Candidate-on alone sets OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1. Other
;; experiment variables must be absent. Use an external process timeout >= 200s.
;; Startup follows the previously proven actual drracket/drracket GUI pattern.
(require racket/class racket/file racket/gui/base racket/list racket/path
         racket/runtime-path racket/string file/sha1 json)
(define-runtime-path save-fixture "independent-native-save-recovery.rkt")
(define-runtime-path failure-fixture "review-native-save-failure.rkt")
(define args (vector->list (current-command-line-arguments)))
;; Read command arguments once, and clear them permanently BEFORE stock queues
;; its first frame. A brief parameterization would leak MODE into file startup.
(current-command-line-arguments #())
(define mode (and (= (length args) 1) (string->symbol (car args))))
(define before '())
(define created-frame #f)
(define checks 0)
(define source-evidence '())
(define completed? #f)
(define (emit marker value)
  (printf "~a ~a\n" marker (jsexpr->string value)) (flush-output))
(define (assert! value description)
  (unless value (error 'native-autosave-host "~a" description))
  (set! checks (add1 checks)))
(define (bounded value [limit 800])
  (define s (if (string? value) value (format "~s" value)))
  (substring s 0 (min limit (string-length s))))
(define (on-gui thunk [seconds 15])
  (define done (make-semaphore 0))
  (define result #f)
  (queue-callback
   (lambda ()
     (with-handlers ([(lambda (_) #t) (lambda (e) (set! result (cons 'error e)))])
       (set! result (cons 'value (thunk))))
     (semaphore-post done))
   #f)
  (yield (choice-evt (semaphore-peek-evt done)
                     (alarm-evt (+ (current-inexact-milliseconds) (* 1000 seconds)))))
  (unless (semaphore-try-wait? done)
    (error 'native-autosave-host "GUI callback timed out after ~a seconds" seconds))
  (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))
(define (wait-for description predicate [seconds 45])
  (define deadline (+ (current-inexact-monotonic-milliseconds) (* 1000 seconds)))
  (let loop ()
    (define result (on-gui predicate 5))
    (cond [result result]
          [(>= (current-inexact-monotonic-milliseconds) deadline)
           (error 'native-autosave-host "Timed out: ~a" description)]
          [else (yield (alarm-evt (+ (current-inexact-milliseconds) 25))) (loop)])))
(define (source! filename collections expected)
  (define path (apply collection-file-path filename collections))
  (define actual (call-with-input-file path (lambda (p) (bytes->hex-string (sha256-bytes p)))))
  (define row (hash 'module (string-join (append collections (list filename)) "/")
                    'resolved_path (path->string path) 'sha256 actual 'expected_sha256 expected))
  (set! source-evidence (append source-evidence (list row)))
  (emit "OPENRACKET_AUTOSAVE_SOURCE" row)
  (assert! (equal? actual expected) (format "Wrong source version for ~a" path)))
(define (diagnostics exception)
  (define (attempt thunk) (with-handlers ([(lambda (_) #t) (lambda (e) (bounded e))]) (thunk)))
  (define (labels node depth)
    (append
     (if (object-method-arity-includes? node 'get-label 0)
         (list (bounded (send node get-label) 300)) '())
     (if (and (positive? depth) (object-method-arity-includes? node 'get-children 0))
         (let ([children (send node get-children)])
           (append-map (lambda (child) (labels child (sub1 depth)))
                       (take children (min 12 (length children))))) '())))
  (define report
    (attempt
     (lambda ()
       (on-gui
        (lambda ()
          (for/list ([w (in-list (take (get-top-level-windows)
                                      (min 10 (length (get-top-level-windows)))))] )
            (define text-labels (labels w 3))
            (define-values (width height) (send w get-size))
            (define base
              (hash 'title (bounded (send w get-label)) 'shown (send w is-shown?)
                    'dialog (is-a? w dialog%) 'width width 'height height
                    'labels (take text-labels (min 40 (length text-labels)))))
            (if (object-method-arity-includes? w 'get-definitions-text 0)
                (let ([e (send w get-definitions-text)])
                  (hash-set* base
                             'editor_filename (bounded (send e get-filename))
                             'editor_characters (send e last-position)
                             'editor_format (bounded (send e get-file-format))
                             'editor_modified (send e is-modified?)
                             'editor_excerpt (bounded (send e get-text) 1200)))
                base))) 8))))
  (emit "OPENRACKET_AUTOSAVE_FAILURE"
        (hash 'status "failed" 'mode (bounded mode) 'checks checks
              'error (if (exn? exception) (exn-message exception) (bounded exception))
              'sources source-evidence 'actual_windows report)))
;; A final non-GUI watchdog ensures even a wedged modal/native operation cannot
;; keep the process alive forever. The external runner still owns its timeout.
(define watchdog
  (thread
   (lambda ()
     (sleep 180)
     (unless completed?
       (emit "OPENRACKET_AUTOSAVE_WATCHDOG"
             (hash 'status "failed" 'reason "180-second process watchdog" 'mode (bounded mode)))
       (exit 2)))))
(with-handlers ([(lambda (_) #t)
                 (lambda (e)
                   (with-handlers ([(lambda (_) #t) (lambda (d)
                                                      (eprintf "AUTOSAVE_DIAGNOSTICS_FAILED ~a\n" (bounded d)))])
                     (diagnostics e))
                   (set! completed? #t)
                   (exit 1))])
  (assert! (memq mode '(stock candidate-off candidate-on)) "One mode argument is required")
  (assert! (equal? (version) "9.3") "Exact official Racket 9.3 runtime required")
  (define profile-env (getenv "PLTUSERHOME"))
  (assert! (and profile-env (complete-path? (string->path profile-env))) "Absolute fresh PLTUSERHOME required")
  (define profile (simplify-path (string->path profile-env)))
  (make-directory* profile)
  (define prefs-file (find-system-path 'pref-file))
  (define relative-prefs (find-relative-path profile (simplify-path prefs-file)))
  (assert! (and (relative-path? relative-prefs) (not (member 'up (explode-path relative-prefs))))
           "Actual preference file must be confined to the fresh profile")
  (assert! (not (file-exists? prefs-file)) "Fresh profile must not already contain a preferences file")
  (call-with-output-file (build-path profile "independent-native-autosave.claim") #:exists 'error
    (lambda (out) (fprintf out "~s\n" mode)))
  (for ([key '("OPENRACKET_ALL_STRING_FAST_PATH" "OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"
               "OPENRACKET_HOST_THEME" "OPENRACKET_THEME" "OPENRACKET_UI")])
    (assert! (not (getenv key)) (format "Unrelated experiment environment must be absent: ~a" key)))
  (define flag (getenv "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD"))
  (assert! (equal? flag (if (eq? mode 'candidate-on) "1" #f)) "Mode and save-scan environment disagree")
  (emit "OPENRACKET_AUTOSAVE_ENVIRONMENT"
        (hash 'mode (symbol->string mode) 'runtime (version) 'os (symbol->string (system-type))
              'profile (path->string profile) 'preferences_file (path->string prefs-file)
              'save_guard_environment (or flag 'null) 'other_experiments "absent"))
  (source! "text-misc.rkt" '("framework" "private")
           (if (eq? mode 'stock)
               "7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638"
               "00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d"))
  (source! "editor-misc.rkt" '("framework" "private")
           "3becc626874477283cdd1b9f45631f11baed586aa37a3c95d67a4a0a2b677885")
  (source! "editor.rkt" '("mred" "private")
           "1eef92a431da2c2cf40d193237d4ab9879adae9518c71b39ba5af0dc6b32f75a")
  (source! "autosave.rkt" '("framework" "private")
           "db156fe925d2372bcfadac91abe8be5568b68bea52c1cacd73264bdf548c9f9f")
  (source! "path-utils.rkt" '("framework" "private")
           "86d73bed097739a1098ae7957c831bbdfbeee3eb2c7f82c43901b5cc50325c93")
  (source! "color.rkt" '("framework" "private")
           "da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578")
  (source! "unit.rkt" '("drracket" "private")
           "535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5")
  (source! "switchable-button.rkt" '("mrlib")
           "532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de")
  (set! before (on-gui get-top-level-windows))
  (on-gui
   (lambda ()
     (current-command-line-arguments #())
     (displayln "OPENRACKET_AUTOSAVE_STAGE loading-stock-entrypoint") (flush-output)
     (dynamic-require 'drracket/drracket #f)) 75)
  (define frame
    (wait-for "shown genuine DrRacket frame"
              (lambda ()
                (for/or ([w (in-list (get-top-level-windows))] #:unless (memq w before))
                  (and (object-method-arity-includes? w 'get-definitions-text 0)
                       (send w is-shown?) w)))))
  (set! created-frame frame)
  (define result-dirs
    (on-gui
     (lambda ()
       (define get-frame% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-unit-frame))
       (define get-defs% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-definitions-text))
       (define defs (send frame get-definitions-text))
       (assert! (is-a? frame (get-frame%)) "Actual registered DrRacket frame class required")
       (assert! (is-a? defs (get-defs%)) "Actual registered DrRacket definitions editor required")
       (assert! (eq? defs (send (send frame get-definitions-canvas) get-editor)) "Real canvas/editor identity")
       (define selected?
         (dynamic-require 'framework/private/text-misc 'openracket-experimental-save-scan-guard?
                          (lambda () 'absent)))
       (assert! (equal? selected? (case mode [(stock) 'absent] [(candidate-off) #f] [else #t]))
                "Actual loaded activation export must match mode")
       (define pref-get (dynamic-require 'framework 'preferences:get))
       (define verify? (pref-get 'framework:verify-change-format))
       (emit "OPENRACKET_AUTOSAVE_ACTIVATION"
             (hash 'mode (symbol->string mode) 'loaded_guard (if (eq? selected? 'absent) "absent" selected?)
                   'verify_change_format_default verify? 'preference_mutated #f))
       (assert! (eq? verify? #f) "Pinned fresh-stock verify-change-format default must remain #f")
       (assert! (not (send defs get-filename)) "Never clear a named editor")
       (assert! (send defs still-untouched?) "Never clear an edited buffer")
       (define starter (or (pref-get 'drracket:module-language:auto-text)
                           (pref-get 'drracket:most-recent-lang-line)))
       (define actual-text (send defs get-text))
       (assert! (or (equal? actual-text "") (and (string? starter) (equal? actual-text starter)))
                "Only the exact stock preferred starter template may be cleared")
       (emit "OPENRACKET_AUTOSAVE_STARTER"
             (hash 'characters (send defs last-position) 'exact_text actual-text 'known_preferred_template starter))
       (unless (zero? (send defs last-position))
         (send defs erase)
         (send defs set-modified #f))
       ;; Check the live loaded mixin in addition to source hashes and the flag.
       ;; This is outside timing, and does not alter the real definitions editor.
       (define scan-calls 0)
       (define counted%
         (class text%
           (super-new)
           (define/override (find-first-snip)
             (set! scan-calls (add1 scan-calls)) (super find-first-snip))))
       (define clever (dynamic-require 'framework 'text:clever-file-format-mixin))
       (define probe (new (clever counted%)))
       (send probe insert "live activation canary")
       (send probe set-file-format 'text)
       (set! scan-calls 0)
       (assert! (send probe can-save-file? "unused-native-canary" 'copy) "Native copy can-save remains allowed")
       (send probe on-save-file "unused-native-canary" 'copy)
       (assert! (= scan-calls (if (eq? mode 'candidate-on) 0 2)) "Live non-same callback count must match mode")
       (define copy-calls scan-calls)
       (set! scan-calls 0)
       (assert! (send probe can-save-file? "unused-native-canary" 'same) "Native same can-save remains allowed")
       (send probe on-save-file "unused-native-canary" 'same)
       (assert! (= scan-calls 2) "Live same-format callbacks remain stock")
       (emit "OPENRACKET_AUTOSAVE_LIVE_CANARY" (hash 'copy_first_calls copy-calls 'same_first_calls scan-calls))
       (displayln "OPENRACKET_AUTOSAVE_STAGE stock-default-save-artifact-fixture") (flush-output)
       (define save-dir ((dynamic-require save-fixture 'run-independent-native-save-check!) frame mode))
       (displayln "OPENRACKET_AUTOSAVE_STAGE native-write-failure-retry-fixture") (flush-output)
       (define failure-dir ((dynamic-require failure-fixture 'run-review-native-save-failure-check!)))
       (list save-dir failure-dir)) 45))
  (for ([dir (in-list result-dirs)])
    (assert! (directory-exists? dir) "Fixture evidence directory must exist"))
  (emit "OPENRACKET_AUTOSAVE_CORRECTNESS"
        (hash 'status "passed" 'scope "native stock-default save/copy/WXME/autosave artifact reload"
              'mode (symbol->string mode) 'checks checks 'directories (map path->string result-dirs)
              'native_write_failure_retry_cases 4
              'sources source-evidence 'verification_enabled_dialogs "unrun"
              'crash_restart_recovery_dialog "unrun" 'measured_benefit #f))
  (on-gui (lambda () (send frame show #f)) 5)
  (set! completed? #t)
  (exit 0))
