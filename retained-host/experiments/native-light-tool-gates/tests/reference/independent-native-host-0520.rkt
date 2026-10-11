#lang racket/base
;; Genuine stock DrRacket launch/retained-host integration. Native GUI required.
;; No substitute editor, evaluator, disabled tool, changed memory limit or mocked GUI.
;; The CI runner supplies a fresh preference profile and external timeout.
(require racket/class racket/file racket/gui/base racket/list racket/string racket/runtime-path
         json mrlib/switchable-button)

(define checks 0)
(define-runtime-path follow-on-module "independent-native-workflows.rkt")
(define-runtime-path native-appearance-module "independent-native-appearance-workflows.rkt")
(define-runtime-path returning-stop-module "independent-native-stop-returning.rkt")
(define native-appearance-check? (equal? (getenv "OPENRACKET_NATIVE_APPEARANCE_CHECK") "1"))
(define native-appearance-result #f)
(define follow-on-case (getenv "OPENRACKET_NATIVE_CASE"))
(define follow-on-result #f)
(define created-frames '())
(define fixture
  (make-temporary-file "openracket-native-fixture-~a.rkt"))
(define fixture-text
  (string-append
   "#lang racket/base\n"
   ";; Native retained-host verification: λ, café, 日本語\n"
   "(define (square x) (* x x))\n"
   "(displayln \"OPENRACKET_NATIVE_EVAL_OK\")\n"
   "(+ (square 6) 6)\n"))
(call-with-output-file fixture #:exists 'truncate
  (lambda (out) (display fixture-text out)))

(define (assert! value description)
  (unless value (error 'independent-native-host "~a" description))
  (set! checks (add1 checks))
  (printf "NATIVE_CHECK ~a\n" description)
  (flush-output))

;; Execute widget operations on the actual GUI eventspace handler thread.
(define (on-gui thunk)
  (define done (make-semaphore 0))
  (define result #f)
  (queue-callback
   (lambda ()
     (with-handlers ([exn? (lambda (e) (set! result (cons 'error e)))])
       (set! result (cons 'value (thunk))))
     (semaphore-post done))
   #f)
  (yield done)
  (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))

(define (wait-for description predicate [seconds 60])
  (define deadline (+ (current-inexact-monotonic-milliseconds) (* 1000 seconds)))
  (let loop ()
    (define result (on-gui predicate))
    (cond [result result]
          [(>= (current-inexact-monotonic-milliseconds) deadline)
           (error 'independent-native-host "Timed out: ~a" description)]
          [else (yield (alarm-evt (+ (current-inexact-milliseconds) 25))) (loop)])))

(define before (on-gui get-top-level-windows))

(define (bounded-text value [limit 600])
  (define text (if (string? value) value (format "~a" value)))
  (substring text 0 (min limit (string-length text))))
(define (window-geometry window)
  (define-values (width height) (send window get-size))
  (hash 'x (send window get-x) 'y (send window get-y) 'width width 'height height))
(define (publish-ready! report marker)
  (when (getenv "OPENRACKET_READY_FILE")
    (call-with-output-file (getenv "OPENRACKET_READY_FILE") #:exists 'truncate
      (lambda (out) (write-json report out) (newline out))))
  (displayln marker)
  (flush-output))
(define (wait-for-capture!)
  (define capture-done (getenv "OPENRACKET_CAPTURE_DONE"))
  (define deadline (+ (current-inexact-monotonic-milliseconds) (if capture-done 20000 1000)))
  (let loop ()
    (unless (or (and capture-done (file-exists? capture-done))
                (>= (current-inexact-monotonic-milliseconds) deadline))
      (yield (alarm-evt (+ (current-inexact-milliseconds) 50)))
      (loop))))
(define (assert-theme-state! expected-dark? stage)
  (define pref-get (dynamic-require 'framework 'preferences:get))
  (define scheme-name (dynamic-require 'framework 'color-prefs:get-current-color-scheme-name))
  (define color-lookup (dynamic-require 'framework 'color-prefs:lookup-in-color-scheme))
  (define painter-theme (dynamic-require 'mrlib/private/openracket-paint 'get-modern-host-theme))
  (define background (color-lookup 'framework:basic-canvas-background))
  (printf "OPENRACKET_NATIVE_THEME_STATE ~a\n"
          (jsexpr->string
           (hash 'stage stage 'requested_dark expected-dark?
                 'mode_preference (format "~s" (pref-get 'framework:white-on-black-mode?))
                 'light_scheme (symbol->string (scheme-name #:wob? #f))
                 'dark_scheme (symbol->string (scheme-name #:wob? #t))
                 'painter (symbol->string (painter-theme))
                 'background (list (send background red) (send background green) (send background blue)))))
  (flush-output)
  (assert! (eq? (pref-get 'framework:white-on-black-mode?) expected-dark?)
           (string-append stage ": requested light/dark mode actually activated"))
  (assert! (eq? (painter-theme) (if expected-dark? 'dark 'light))
           (string-append stage ": retained toolbar painter synchronized with editor mode")))

(define (failure-diagnostics! exception)
  ;; Bounded synthetic-test window evidence. Never dismiss or answer a dialog.
  (with-handlers ([exn? (lambda (e)
                         (eprintf "OPENRACKET_DIAGNOSTIC_FAILURE ~a\n" (exn-message e)))])
    (define report
      (on-gui
       (lambda ()
         (define windows
           (filter (lambda (window) (not (memq window before))) (get-top-level-windows)))
         (define (labels node depth)
           (append
            (if (object-method-arity-includes? node 'get-label 0)
                (list (bounded-text (send node get-label) 300)) '())
            (if (and (positive? depth) (object-method-arity-includes? node 'get-children 0))
                (append-map (lambda (child) (labels child (sub1 depth)))
                            (take (send node get-children) (min 15 (length (send node get-children)))))
                '())))
         (define (describe window)
           (define basic
             (hash 'title (bounded-text (send window get-label))
                   'shown (send window is-shown?) 'geometry (window-geometry window)
                   'labels (take (labels window 3) (min 30 (length (labels window 3))))))
           (if (object-method-arity-includes? window 'get-definitions-text 0)
               (let ([editor (send window get-definitions-text)])
                 (hash-set* basic 'editor_filename (bounded-text (send editor get-filename))
                            'editor_characters (send editor last-position)
                            'editor_excerpt (bounded-text (send editor get-text) 1000)))
               basic))
         (define descriptions (map describe (take windows (min 8 (length windows)))))
         (hash 'status "failed" 'failure_diagnostic #t 'checks checks
               'error (bounded-text (exn-message exception) 1000)
               'windows descriptions
               'geometry (if (pair? descriptions) (hash-ref (car descriptions) 'geometry) (hash))))))
    (printf "OPENRACKET_NATIVE_FAILURE_DIAGNOSTIC ~a\n" (jsexpr->string report))
    (publish-ready! report "OPENRACKET_NATIVE_FAILURE_READY")
    (wait-for-capture!)))

(define (cleanup!)
  ;; Only frames created by this launch are hidden; never touch a preexisting frame.
  (with-handlers ([exn? (lambda (_) (void))])
    (on-gui
     (lambda ()
       (for ([frame (in-list created-frames)]) (send frame show #f)))))
  (when (file-exists? fixture) (delete-file fixture)))

(with-handlers
    ([exn?
      (lambda (e)
        (eprintf "OPENRACKET_NATIVE_FAILURE ~a\n" (exn-message e))
        (failure-diagnostics! e)
        (cleanup!)
        (exit 1))])
  ;; Read-only capture before DrRacket's appearance tool can set an app override.
  (define native-appearance-baseline
    (and native-appearance-check?
         (on-gui
          (lambda ()
            (call-with-values
             (dynamic-require native-appearance-module 'capture-native-appearance-baseline)
             list)))))
  (on-gui
   (lambda ()
     ;; The first-window callback reads argv later. Do not briefly parameterize
     ;; it during module load, then let benchmark/test arguments leak back in.
     (current-command-line-arguments #())
     (displayln "OPENRACKET_NATIVE_STAGE loading-stock-entrypoint")
     (flush-output)
     (dynamic-require 'drracket/drracket #f)))

  ;; Stock 9.3 queues its first ordinary frame as a low-priority callback.
  (define frame
    (wait-for
     "shown genuine DrRacket frame"
     (lambda ()
       (for/or ([window (in-list (get-top-level-windows))]
                #:unless (memq window before))
         (and (object-method-arity-includes? window 'get-definitions-text 0)
              (send window is-shown?)
              window)))))
  (set! created-frames (list frame))
  (on-gui
   (lambda ()
     (define initial-editor (send frame get-definitions-text))
     (printf "OPENRACKET_NATIVE_INITIAL_EDITOR filename=~s characters=~a excerpt=~s\n"
             (send initial-editor get-filename) (send initial-editor last-position)
             (bounded-text (send initial-editor get-text)))
     ;; Use the normal, documented retained frame file-open route after startup.
     (send frame change-to-file fixture)
     (define opened-editor (send frame get-definitions-text))
     (printf "OPENRACKET_NATIVE_OPENED_EDITOR filename=~s characters=~a excerpt=~s\n"
             (send opened-editor get-filename) (send opened-editor last-position)
             (bounded-text (send opened-editor get-text)))
     (flush-output)
     (assert! (and (send opened-editor get-filename)
                   (equal? (simplify-path (send opened-editor get-filename))
                           (simplify-path fixture)))
              "documented file-open route selects the exact fixture")))
  (define definitions (on-gui (lambda () (send frame get-definitions-text))))
  (define interactions (on-gui (lambda () (send frame get-interactions-text))))
  (define run-button (on-gui (lambda () (send frame get-execute-button))))

  (on-gui
   (lambda ()
     (define get-frame% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-unit-frame))
     (define get-defs% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-definitions-text))
     (define get-ints% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-interactions-text))
     (define get-defs-canvas% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-definitions-canvas))
     (define get-ints-canvas% (dynamic-require 'drracket/tool-lib 'drracket:get/extend:get-interactions-canvas))
     (define defs-canvas (send frame get-definitions-canvas))
     (define ints-canvas (send frame get-interactions-canvas))
     (assert! (is-a? frame (get-frame%)) "actual registered DrRacket frame class")
     (assert! (is-a? definitions (get-defs%)) "actual registered definitions editor class")
     (assert! (is-a? interactions (get-ints%)) "actual registered interactions editor class")
     (assert! (is-a? defs-canvas (get-defs-canvas%)) "actual registered definitions canvas class")
     (assert! (is-a? ints-canvas (get-ints-canvas%)) "actual registered interactions canvas class")
     (assert! (eq? definitions (send defs-canvas get-editor)) "definitions canvas retains its editor identity")
     (assert! (eq? interactions (send ints-canvas get-editor)) "interactions canvas retains its editor identity")
     (assert! (equal? (send definitions get-text) fixture-text) "real file-open route preserves Unicode source")
     (assert! (positive? (length (send (send frame get-menu-bar) get-items))) "native menu bar remains populated")
     (assert! (pair? (send frame get-tabs)) "native tabs remain present")
     (assert! (is-a? run-button switchable-button%) "Run uses the retained native switchable-button class")
     (assert! (is-a? (send frame get-break-button) switchable-button%) "Stop uses the retained native switchable-button class")
     (assert! (member run-button (send (send frame get-button-panel) get-children)) "Run remains in the stock toolbar panel")
     (define pref-get (dynamic-require 'framework 'preferences:get))
     (define scheme-name (dynamic-require 'framework 'color-prefs:get-current-color-scheme-name))
     (define expected-modern?
       (and (equal? (getenv "OPENRACKET_HOST_THEME") "1")
            (not (equal? (getenv "OPENRACKET_UI") "stock"))))
     (cond
       [expected-modern?
        (assert! (eq? (pref-get 'openracket:appearance-state) 'applied)
                 "opted-in appearance transaction completed")
        (assert! (and (eq? (scheme-name #:wob? #f) '|OpenRacket Light|)
                      (eq? (scheme-name #:wob? #t) '|OpenRacket Dark|))
                 "both OpenRacket schemes registered and selected")
        (define expected-dark? (not (equal? (getenv "OPENRACKET_THEME") "light")))
        (assert-theme-state! expected-dark? "initial appearance")
        (assert! (and (= (send defs-canvas horizontal-inset) 12)
                      (= (send defs-canvas vertical-inset) 10)
                      (= (send ints-canvas horizontal-inset) 12)
                      (= (send ints-canvas vertical-inset) 10))
                 "retained editor canvas spacing activated")]
       [else
        (assert! (and (not (eq? (scheme-name #:wob? #f) '|OpenRacket Light|))
                      (not (eq? (scheme-name #:wob? #t) '|OpenRacket Dark|)))
                 "fresh stock profile did not select OpenRacket schemes")])
     ;; Real editor editing and its inherited undo/redo stack, with no buffer swap.
     (define end (send definitions last-position))
     (define marker ";; temporary undo/redo probe\n")
     (send definitions insert marker end end)
     (assert! (string-suffix? (send definitions get-text) marker) "stock definitions insert works")
     (send definitions undo)
     (assert! (equal? (send definitions get-text) fixture-text) "stock definitions undo restores source")
     (send definitions redo)
     (assert! (string-suffix? (send definitions get-text) marker) "stock definitions redo restores edit")
     (send definitions undo)
     (send definitions set-modified #f)))

  (when (and (equal? (getenv "OPENRACKET_HOST_THEME") "1")
             (not (equal? (getenv "OPENRACKET_UI") "stock")))
    (define initial-dark? (not (equal? (getenv "OPENRACKET_THEME") "light")))
    ;; Use stock preference callbacks; never force a toolbar repaint from the test.
    ;; A second low-priority callback is a fence for the bridge's queued sync.
    (for ([dark? (in-list (list (not initial-dark?) initial-dark?))]
          [stage '("switched appearance" "restored appearance")])
      (on-gui (lambda ()
                ((dynamic-require 'framework 'preferences:set)
                 'framework:white-on-black-mode? dark?)))
      (on-gui (lambda () (assert-theme-state! dark? stage)))))

  ;; Two real Run callbacks exercise stock evaluator lifecycle and repeated Run.
  ;; This deliberately does not claim debugger, macro-stepper, teaching-language,
  ;; modal preferences, snip, IME or accessibility parity.
  (for ([iteration (in-range 2)])
    (wait-for "Run button enabled" (lambda () (send run-button is-enabled?)))
    (on-gui (lambda () (send run-button command)))
    (wait-for
     "stock evaluator output and completion"
     (lambda ()
       (and (send run-button is-enabled?)
            (not (send (send frame get-current-tab) is-running?))
            (string-contains? (send interactions get-text) "OPENRACKET_NATIVE_EVAL_OK")
            (regexp-match? #rx"(^|\n)42(\n|$)" (send interactions get-text)))))
    (assert! #t (format "real Run ~a produces marker and value 42" (add1 iteration))))

  (when native-appearance-check?
    (when follow-on-case
      (error 'independent-native-host "Appearance lifecycle requires its own fresh process"))
    (set! native-appearance-result
          (on-gui
           (lambda ()
             ((dynamic-require native-appearance-module 'run-native-appearance-workflows!)
              frame (car native-appearance-baseline) (cadr native-appearance-baseline)
              (lambda (created)
                (unless (memq created created-frames)
                  (set! created-frames (cons created created-frames)))))))))

  (when follow-on-case
    (unless (member follow-on-case '("stop" "input-eof" "wxme" "check-syntax" "stop-returning"))
      (error 'independent-native-host "Unsupported follow-on case ~s" follow-on-case))
    (printf "OPENRACKET_NATIVE_STAGE follow-on=~a\n" follow-on-case)
    (flush-output)
    (set! follow-on-result
          (if (equal? follow-on-case "stop-returning")
              ((dynamic-require returning-stop-module 'run-returning-stop-check!)
               frame on-gui wait-for)
              (on-gui
               (lambda ()
                 ((dynamic-require follow-on-module 'run-follow-on-check!)
                  frame (string->symbol follow-on-case)))))))

  ;; A low-priority event turn allows actual paint work to follow the last update.
  (on-gui (lambda ()
            ;; Capture dimensions only: fit the actual runner display (the macOS
            ;; runner can be 1024x768) without clipping native toolbar controls.
            (define-values (display-width display-height) (get-display-size))
            (send frame resize (max 1 (min 1100 (- display-width 24)))
                  (max 1 (min 760 (- display-height 100))))
            (send frame show #t)
            (send (send frame get-definitions-canvas) focus)))
  (yield (alarm-evt (+ (current-inexact-milliseconds) 500)))
  (define geometry
    (on-gui
     (lambda ()
       (window-geometry frame))))
  (define report
    (hash 'status "passed" 'checks checks 'racket (version)
          'ui (or (getenv "OPENRACKET_UI") "modern")
          'theme (or (getenv "OPENRACKET_THEME") "unspecified")
          'genuine_host #t 'repeated_real_run #t 'geometry geometry
          'native_appearance_lifecycle (or native-appearance-result 'null)
          'follow_on_case (or follow-on-case 'null) 'follow_on_result (or follow-on-result 'null)
          'complete_stock_parity #f 'physical_input_to_photon_measured #f))
  (printf "OPENRACKET_NATIVE_RESULT ~a\n" (jsexpr->string report))
  (publish-ready! report "OPENRACKET_NATIVE_READY")
  ;; Screenshot coordination only, bounded even if no capture agent responds.
  (wait-for-capture!)
  (cleanup!)
  (exit 0))
