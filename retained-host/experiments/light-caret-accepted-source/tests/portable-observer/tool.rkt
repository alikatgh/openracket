#lang racket/base
;; CI-only observer. It never invokes setup, a DrRacket entrypoint, an editor
;; mutation, a control callback, a preference setter or a native appearance setter.
(require racket/class racket/file racket/list racket/path racket/string racket/unit
         racket/gui/base drracket/tool framework string-constants
         mrlib/switchable-button mrlib/panel-wob file/sha1 json)
(provide tool@)

(define (bounded value [limit 1000])
  (define s (if (string? value) value (format "~s" value)))
  (substring s 0 (min limit (string-length s))))
(define (json-safe value)
  (cond [(eq? value 'null) 'null]
        [(symbol? value) (symbol->string value)]
        [(path? value) (path->string value)]
        [(hash? value) (for/hash ([(k v) (in-hash value)]) (values k (json-safe v)))]
        [(list? value) (map json-safe value)]
        [else value]))
(define (emit marker value)
  (printf "~a ~a\n" marker (jsexpr->string (json-safe value))) (flush-output))
;; This expectation is supplied independently by CI, never inferred from the
;; preview configuration or written to preferences. #f is DrRacket's unlimited
;; value; keep it distinct from missing/invalid observer configuration.
(define (parse-expected-memory-limit value)
  (cond
    [(equal? value "unlimited") #f]
    [(and (string? value) (regexp-match-exact? #px"[0-9]+" value)
          (let ([mib (string->number value 10)])
            (and (exact-integer? mib) (>= mib 8))))
     (* (string->number value 10) 1024 1024)]
    [else
     (error 'portable-observer
            "OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB must be a decimal integer >= 8 or exactly unlimited; received ~s"
            value)]))
(define (memory-limit-evidence expected)
  ;; Registered by stock eval-helpers-and-pref-init.rkt. Do not register a
  ;; fallback: an absent registration must fail instead of hiding a wrong key.
  (define actual (preferences:get 'drracket:child-only-memory-limit))
  (hash 'preference_key "drracket:child-only-memory-limit"
        'expected_bytes expected 'effective_bytes actual
        'observation "registered preference in launcher-created frame process"
        'worker_cap_measured #f))
(define (assert-memory-limit! evidence assert!)
  (define actual (hash-ref evidence 'effective_bytes))
  (define expected (hash-ref evidence 'expected_bytes))
  (assert! (or (eq? actual #f)
               (and (exact-integer? actual) (>= actual (* 8 1024 1024))))
           (format "Registered child-only memory preference must be #f or exact bytes >= 8 MiB; observed ~s"
                   actual))
  (assert! (equal? actual expected)
           (format "Registered child-only memory preference: expected ~s bytes/#f, observed ~s"
                   expected actual)))
(define (geometry frame)
  (define-values (width height) (send frame get-size))
  (hash 'x (send frame get-x) 'y (send frame get-y) 'width width 'height height))
(define (descendants node)
  (cons node
        (if (is-a? node area-container<%>)
            (append-map descendants (send node get-children)) '())))
(define (window-evidence)
  (for/list ([w (in-list (take (get-top-level-windows)
                              (min 8 (length (get-top-level-windows)))))])
    (define base
      (hash 'title (bounded (send w get-label) 300) 'shown (send w is-shown?)
            'dialog (is-a? w dialog%) 'geometry (geometry w)
            'labels (for/list ([node (in-list (take (descendants w) (min 40 (length (descendants w)))))]
                               #:when (object-method-arity-includes? node 'get-label 0))
                      (bounded (send node get-label) 250))))
    (if (object-method-arity-includes? w 'get-definitions-text 0)
        (let ([e (send w get-definitions-text)])
          (hash-set* base 'editor_filename (bounded (send e get-filename))
                     'editor_characters (send e last-position)
                     'editor_excerpt (bounded (send e get-text))))
        base)))

(define tool@
  (unit
    (import drracket:tool^)
    (export drracket:tool-exports^)
    (define (phase1) (void))
    (define (phase2)
      ;; Accidental registration without the CI opt-in remains inert.
      (when (getenv "OPENRACKET_PORTABLE_FIXTURE") (start-observer!)))

    (define (start-observer!)
      (define ready-path #f)
      (define done-path #f)
      (define fixture #f)
      (define fixture-text #f)
      (define timer #f)
      (define phase 'waiting)
      (define result-code 1)
      (define completed? #f)
      (define deadline (+ (current-inexact-monotonic-milliseconds) 60000))
      (define capture-deadline #f)
      (define last-problem "No shown launcher-created fixture frame yet")
      (define last-state (hash))
      (define stable-frame #f)
      (define stable-count 0)
      (define source-evidence #f)
      (define checks 0)
      (define expected-ui (getenv "OPENRACKET_PORTABLE_EXPECT_UI"))
      (define expected-guard (getenv "OPENRACKET_PORTABLE_EXPECT_SAVE_GUARD"))
      (define expected-memory-limit 'unconfigured)
      (define modern? (equal? expected-ui "modern"))
      (define (assert! condition text)
        (unless condition (error 'portable-observer "~a" text))
        (set! checks (add1 checks)))
      (define (required-path key #:exists? [exists? #f])
        (define value (getenv key))
        (assert! (and value (complete-path? (string->path value)))
                 (format "~a must name an absolute CI path" key))
        (define p (simplify-path (string->path value)))
        (when exists? (assert! (file-exists? p) (format "~a must exist" key)))
        p)
      (define (source filename collections expected)
        (define path (apply collection-file-path filename collections))
        (define actual (call-with-input-file path
                         (lambda (in) (bytes->hex-string (sha256-bytes in)))))
        (assert! (equal? actual expected) (format "Unexpected source: ~a" path))
        (hash 'module (string-join (append collections (list filename)) "/")
              'path path 'sha256 actual))
      (define (finish! code)
        (set! completed? #t)
        (when timer (send timer stop))
        (exit code))
      (define (publish! report code)
        (set! result-code code)
        (set! phase 'capture)
        (set! capture-deadline (+ (current-inexact-monotonic-milliseconds) 20000))
        (emit (if (zero? code) "OPENRACKET_NATIVE_RESULT" "OPENRACKET_NATIVE_FAILURE_DIAGNOSTIC") report)
        (when ready-path
          (call-with-output-file ready-path #:exists 'error
            (lambda (out) (write-json (json-safe report) out) (newline out))))
        (displayln (if (zero? code) "OPENRACKET_NATIVE_READY" "OPENRACKET_NATIVE_FAILURE_READY"))
        (flush-output))
      (define (fail! problem)
        (define windows
          (with-handlers ([exn? (lambda (e) (list (hash 'diagnostic_error (exn-message e))))])
            (window-evidence)))
        (publish! (hash 'status "failed" 'failure_diagnostic #t 'error (bounded problem)
                        'checks checks 'last_state last-state 'windows windows
                        'geometry (if (and (pair? windows) (hash-has-key? (car windows) 'geometry))
                                      (hash-ref (car windows) 'geometry) (hash))) 1))
      (define (inspect-frame frame)
        (set! checks 0)
        (define defs (send frame get-definitions-text))
        (define ints (send frame get-interactions-text))
        (define dc (send frame get-definitions-canvas))
        (define ic (send frame get-interactions-canvas))
        (assert! (is-a? frame (drracket:get/extend:get-unit-frame)) "Registered stock frame class")
        (assert! (is-a? defs (drracket:get/extend:get-definitions-text)) "Registered definitions class")
        (assert! (is-a? ints (drracket:get/extend:get-interactions-text)) "Registered interactions class")
        (assert! (is-a? dc (drracket:get/extend:get-definitions-canvas)) "Registered definitions canvas class")
        (assert! (is-a? ic (drracket:get/extend:get-interactions-canvas)) "Registered interactions canvas class")
        (assert! (eq? defs (send dc get-editor)) "Definitions canvas/editor identity")
        (assert! (eq? ints (send ic get-editor)) "Interactions canvas/editor identity")
        (assert! (and (send defs get-filename)
                      (equal? (simplify-path (send defs get-filename)) fixture))
                 "Launcher argv opened the exact fixture")
        (assert! (equal? (send defs get-text) fixture-text) "Launcher preserved exact Unicode source")
        (assert! (not (send defs is-modified?)) "Observer did not edit the opened fixture")
        (define memory-limit (memory-limit-evidence expected-memory-limit))
        ;; Preserve the actual value in failure diagnostics before asserting it.
        (set! last-state (hash 'memory_limit memory-limit))
        (assert-memory-limit! memory-limit assert!)
        (assert! (pair? (send (send frame get-menu-bar) get-items)) "Original menu bar remains populated")
        (assert! (pair? (send frame get-tabs)) "Original tab remains present")
        (define toolbar (send frame get-button-panel))
        (define buttons (filter (lambda (w) (is-a? w switchable-button%)) (descendants toolbar)))
        (define labels (map (lambda (w) (send w get-label)) buttons))
        (define expected
          (list (string-constant check-syntax) (string-constant debug-tool-button-name)
                (string-constant macro-stepper) (string-constant execute-button-label)
                (string-constant break-button-label)))
        (define observed (filter (lambda (label) (member label expected)) labels))
        (define horizontal?
          (if (object-method-arity-includes? toolbar 'get-orientation 0)
              (send toolbar get-orientation)
              (is-a? toolbar horizontal-pane%)))
        (assert! (equal? observed (if horizontal? expected (reverse expected)))
                 "Localized Check Syntax/Debug/Macro Stepper/Run/Stop order remains stock")
        (define run (send frame get-execute-button))
        (define stop (send frame get-break-button))
        (assert! (and (is-a? run switchable-button%) (memq run buttons)) "Run retains native toolbar identity")
        (assert! (and (is-a? stop switchable-button%) (memq stop buttons)) "Stop retains native toolbar identity")
        (assert! (equal? (send run get-label) (string-constant execute-button-label)) "Localized Run label")
        (assert! (equal? (send stop get-label) (string-constant break-button-label)) "Localized Stop label")
        (define painter-theme ((dynamic-require 'mrlib/private/openracket-paint 'get-modern-host-theme)))
        (define blended? ((dynamic-require 'mrlib/private/openracket-paint 'get-modern-chrome-blended?)))
        (define unavailable #f)
        (define make-adapter (dynamic-require 'openracket-appearance/native-appearance-platform
                                             'make-platform-native-appearance-adapter))
        (define inspect (dynamic-require 'openracket-appearance/native-appearance
                                        'native-appearance-adapter-inspect))
        ;; Constructing this adapter only verifies capability; call its read-only
        ;; inspector directly. Never capture, set, restore or own appearance here.
        (define adapter (make-adapter #:enabled? #t
                                     #:on-unavailable (lambda (why) (set! unavailable why))))
        (assert! adapter (format "Native appearance inspector available: ~s" unavailable))
        (define native ((inspect adapter)))
        (assert! (eq? (hash-ref native 'backend #f) 'cocoa) "This acceptance gate is Cocoa-specific")
        (set! last-state
              (hash 'painter painter-theme 'native_blending blended? 'native native
                    'memory_limit memory-limit
                    'light_scheme (color-prefs:get-current-color-scheme-name #:wob? #f)
                    'dark_scheme (color-prefs:get-current-color-scheme-name #:wob? #t)
                    'mode (preferences:get 'framework:white-on-black-mode?)
                    'toolbar_labels labels))
        (define painter-modern? ((dynamic-require 'mrlib/private/openracket-paint 'modern-ui?)))
        (assert! (eq? painter-modern? modern?) "Actual painter mode matches the chosen launcher")
        (cond
          [modern?
           (assert! (eq? (preferences:get 'openracket:appearance-state) 'applied) "Appearance transaction applied")
           (assert! (eq? (preferences:get 'framework:white-on-black-mode?) #t) "Explicit dark editor preference")
           (assert! (and (eq? (color-prefs:get-current-color-scheme-name #:wob? #f) '|OpenRacket Light|)
                         (eq? (color-prefs:get-current-color-scheme-name #:wob? #t) '|OpenRacket Dark|))
                    "Both OpenRacket palettes selected")
           (assert! (eq? painter-theme 'dark) "Retained painter synchronized to dark")
           (assert! blended? "Verified native chrome blending active")
           (assert! (white-on-black-panel-scheme?) "Stock native panel appearance is dark")
           (assert! (equal? (hash-ref native 'explicit-name #f) "NSAppearanceNameDarkAqua")
                    "Actual app-local DarkAqua override")
           (assert! (equal? (hash-ref native 'effective-name #f) "NSAppearanceNameDarkAqua")
                    "Actual effective DarkAqua appearance")]
          [else
           (assert! (and (not (eq? (color-prefs:get-current-color-scheme-name #:wob? #f) '|OpenRacket Light|))
                         (not (eq? (color-prefs:get-current-color-scheme-name #:wob? #t) '|OpenRacket Dark|)))
                    "Separate stock profile retains original schemes")
           (assert! (not blended?) "Stock launcher leaves native blending disabled")
           (assert! (not (hash-ref native 'explicit-name #f)) "Stock launcher leaves app-native appearance inherited")])
        (define save-guard
          (dynamic-require 'framework/private/text-misc 'openracket-experimental-save-scan-guard?
                           (lambda () 'missing)))
        (assert! (eq? save-guard (equal? expected-guard "1")) "Actual loaded save guard matches the explicit expectation")
        (assert! (not (for/or ([w (in-list (get-top-level-windows))])
                       (and (is-a? w dialog%) (send w is-shown?))))
                 "No modal startup dialog is hidden by readiness")
        (hash 'status "passed" 'observer "CI-only real launcher" 'checks checks
              'genuine_host #t 'entrypoint_replaced #f 'fixture_opened_by_observer #f
              'content_or_preferences_changed #f 'fixture fixture 'fixture_characters (string-length fixture-text)
              'toolbar_labels labels 'toolbar_horizontal horizontal? 'ui expected-ui 'theme (if modern? "dark" "stock")
              'native native 'painter painter-theme 'native_blending blended? 'save_guard save-guard
              'memory_limit memory-limit
              'sources source-evidence 'geometry (geometry frame) 'complete_stock_parity #f))
      (define (tick)
        (with-handlers ([exn? (lambda (e)
                               (if (eq? phase 'waiting)
                                   (begin (set! stable-count 0) (set! last-problem (exn-message e)))
                                   (begin (eprintf "PORTABLE_OBSERVER_FATAL ~a\n" (exn-message e))
                                          (finish! 1))))])
          (case phase
            [(waiting)
             (cond
               [(>= (current-inexact-monotonic-milliseconds) deadline) (fail! last-problem)]
               [else
                (define frame
                  (for/or ([w (in-list (get-top-level-windows))])
                    (and (object-method-arity-includes? w 'get-definitions-text 0)
                         (send w is-shown?) w)))
                (cond
                  [frame
                   (define report (inspect-frame frame))
                   (set! last-state report)
                   (set! stable-count (if (eq? stable-frame frame) (add1 stable-count) 1))
                   (set! stable-frame frame)
                   (when (>= stable-count 3) (publish! report 0))]
                  [else (set! stable-count 0) (set! stable-frame #f)])])]
            [(capture)
             (cond [(and done-path (file-exists? done-path)) (finish! result-code)]
                   [(>= (current-inexact-monotonic-milliseconds) capture-deadline)
                    (emit "OPENRACKET_PORTABLE_CAPTURE_TIMEOUT" (hash 'result_code result-code))
                    (finish! (if (zero? result-code) 2 result-code))])])))
      (with-handlers ([exn? (lambda (e)
                             (eprintf "PORTABLE_OBSERVER_CONFIGURATION_FAILURE ~a\n" (exn-message e))
                             (finish! 1))])
        (set! fixture (required-path "OPENRACKET_PORTABLE_FIXTURE" #:exists? #t))
        (set! ready-path (required-path "OPENRACKET_NATIVE_READY_FILE"))
        (set! done-path (required-path "OPENRACKET_NATIVE_CAPTURE_DONE"))
        (assert! (not (file-exists? ready-path)) "Readiness path must be fresh")
        (assert! (not (file-exists? done-path)) "Capture completion path must be fresh")
        (assert! (member expected-ui '("modern" "stock")) "Explicit expected UI is modern or stock")
        (assert! (member expected-guard '("1" "0")) "Explicit expected guard is 1 or 0")
        (set! expected-memory-limit
              (parse-expected-memory-limit (getenv "OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB")))
        (assert! (equal? (getenv "OPENRACKET_UI") expected-ui) "Actual launcher UI environment")
        (if modern?
            (begin
              (assert! (equal? (getenv "OPENRACKET_THEME") "dark") "Explicit dark launch requested")
              (assert! (equal? (getenv "OPENRACKET_NATIVE_APPEARANCE") "1") "Native appearance enabled"))
            (assert! (not (getenv "OPENRACKET_NATIVE_APPEARANCE")) "Stock launcher clears native appearance override"))
        (assert! (equal? (version) "9.3") "Pinned Racket 9.3 runtime")
        (set! fixture-text (file->string fixture))
        (assert! (<= (string-length fixture-text) 20000) "Use a small synthetic CI fixture")
        (set! source-evidence
              (list (source "color.rkt" '("framework" "private")
                            "da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578")
                    (source "unit.rkt" '("drracket" "private")
                            "535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5")
                    (source "eval-helpers-and-pref-init.rkt" '("drracket" "private")
                            "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62")
                    (source "text-misc.rkt" '("framework" "private")
                            "00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d")))
        (assert! (not (file-exists? (build-path (path-only (collection-file-path "unit.rkt" "drracket" "private"))
                                              "openracket-all-string-snips.rkt")))
                 "No scan experiment helper is installed")
        (emit "OPENRACKET_PORTABLE_OBSERVER_STARTED" (hash 'fixture fixture 'sources source-evidence))
        (set! timer (new timer% [notify-callback tick] [interval 100]))
        ;; Cooperative completion flag only; never kill a cross-custodian thread.
        (thread (lambda () (sleep 90)
                  (unless completed?
                    (emit "OPENRACKET_PORTABLE_WATCHDOG" (hash 'status "failed" 'last_problem last-problem))
                    (exit 2))))))))
