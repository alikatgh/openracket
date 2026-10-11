#lang racket/base
;; Separate CI-only observer; never an application entrypoint or file opener.
(require racket/class racket/file racket/list racket/path racket/string racket/unit
         racket/runtime-path racket/gui/base drracket/tool framework string-constants
         mrlib/switchable-button mrlib/panel-wob file/sha1 json "contract.rkt")
(provide tool@)
(define-runtime-path config-path "observer-config.json")
(define-runtime-path cocoa-reader-path "cocoa-identity.rkt")
(define (bounded value [limit 1000])
  (define s (if (string? value) value (format "~s" value)))
  (substring s 0 (min limit (string-length s))))
(define (emit marker value)
  (printf "~a ~a\n" marker (jsexpr->string (json-safe value))) (flush-output))
(define (digest-bytes bs) (bytes->hex-string (sha256-bytes bs)))
(define (write-new-json! path value)
  ;; Readers never see a partial READY. An existing destination is never replaced.
  (define tmp (path-add-extension path #".tmp"))
  (call-with-output-file tmp #:exists 'error
    (lambda (out) (write-json (json-safe value) out) (newline out)))
  (rename-file-or-directory tmp path #f))
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
                     'editor_excerpt (send e get-text 0 (min 1000 (send e last-position)))))
        base)))


(define tool@
  (unit
    (import drracket:tool^)
    (export drracket:tool-exports^)
    (define (phase1) (void))
    (define (phase2)
      ;; Real Launch Services does not promise shell environment inheritance.
      ;; No configuration file means no observer activity or native FFI import.
      (when (file-exists? config-path) (start-observer!)))
    (define (start-observer!)
      (define config #f)
      (define steps #f)
      (define step-index 0)
      (define phase 'waiting)
      (define timer #f)
      (define completed? #f)
      (define result-code 1)
      (define deadline (+ (current-inexact-monotonic-milliseconds) 60000))
      (define capture-deadline #f)
      (define dispatched-at #f)
      (define dispatch-evidence #f)
      (define last-problem "No shown genuine DrRacket window yet")
      (define last-state (hash))
      (define checks 0)
      (define source-evidence #f)
      (define control-ready? #f)
      (define expected-memory-limit 'unconfigured)
      (define expected-ui "modern")
      (define expected-guard "1")
      (define modern? #t)
      (define fixture-texts (make-hash))
      (define fixture-hashes (make-hash))
      (define identity-reader #f)
      (define first-pid #f)
      (define stable-snapshot #f)
      (define stable-count 0)
      (define prior-snapshot #f)
      (define object-ids (make-hasheq))
      (define next-object-id 0)
      (define reports '())
      (define (step) (list-ref steps step-index))
      (define (id object)
        (hash-ref! object-ids object
                   (lambda () (set! next-object-id (add1 next-object-id)) next-object-id)))
      (define (assert! condition text)
        (unless condition (error 'mac-app-observer "~a" text))
        (set! checks (add1 checks)))
      (define (source filename collections expected)
        (define path (apply collection-file-path filename collections))
        (define actual (digest-bytes (file->bytes path)))
        (assert! (equal? actual expected) (format "Unexpected source: ~a" path))
        (hash 'module (string-join (append collections (list filename)) "/")
              'path path 'sha256 actual))
      (define (finish! code)
        (set! completed? #t)
        (when timer (send timer stop))
        (exit code))
      (define (envelope)
        (hash 'schema 1 'run_id (hash-ref config 'run_id) 'step (step)
              'token (hash-ref (hash-ref config 'step_tokens) (string->symbol (step)))))
      (define (publish! report code)
        (set! result-code code)
        (set! phase 'capture)
        (set! capture-deadline (+ (current-inexact-monotonic-milliseconds) 20000))
        (define with-envelope
          (for/fold ([h report]) ([(k v) (in-hash (envelope))]) (hash-set h k v)))
        (set! last-state with-envelope)
        (write-new-json! (control-path config (step) "ready") with-envelope)
        (emit (if (zero? code) "OPENRACKET_MAC_APP_READY" "OPENRACKET_MAC_APP_FAILURE_READY") with-envelope))
      (define (fail! problem)
        (define windows
          (with-handlers ([exn? (lambda (e) (list (hash 'diagnostic_error (bounded (exn-message e)))))])
            (window-evidence)))
        (publish! (hash 'status "failed" 'error (bounded problem) 'checks checks
                        'last_state last-state 'windows windows
                        'geometry (if (pair? windows) (hash-ref (car windows) 'geometry (hash)) (hash))) 1))
      (define (inspect-frame frame)
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
        (assert! (eq? defs (send (send frame get-current-tab) get-defs)) "Active tab owns definitions editor")
        (assert! (eq? ints (send (send frame get-current-tab) get-ints)) "Active tab owns interactions editor")
        (define memory-limit (memory-limit-evidence expected-memory-limit))
        ;; Preserve the actual value in failure diagnostics before asserting it.
        (set! last-state (hash 'memory_limit memory-limit))
        (assert-memory-limit! memory-limit assert!)
        (assert! (pair? (send (send frame get-menu-bar) get-items)) "Original menu bar remains populated")
        (assert! (pair? (send frame get-tabs)) "Original tab remains present")
        (define toolbar (send frame get-button-panel))
        (define buttons (filter (lambda (w) (is-a? w switchable-button%)) (descendants toolbar)))
        (define labels (map (lambda (w) (send w get-label)) buttons))
        (define full-expected
          (list (string-constant check-syntax) (string-constant debug-tool-button-name)
                (string-constant macro-stepper) (string-constant execute-button-label)
                (string-constant break-button-label)))
        ;; Read the active document's real stock language, not its toolbar shape.
        ;; Detached capability-disabled widgets are absent from get-children.
        (define language
          (drracket:language-configuration:language-settings-language
           (send defs get-next-settings)))
        (define language-position (send language get-language-position))
        (define no-language?
          (equal? language-position
                  (list (string-constant initial-language-category)
                        (string-constant no-language-chosen))))
        (define module-language? (is-a? language drracket:module-language:module-language<%>))
        (define unnamed-empty? (and (not (send defs get-filename)) (zero? (send defs last-position))))
        (define capability-keys
          '(drscheme:check-syntax-button gui-debugger:debug-button macro-stepper:enabled))
        (define registered (map drracket:language:capability-registered? capability-keys))
        (define capabilities
          (map (lambda (key present?)
                 (if present? (send language capability-value key) 'unregistered))
               capability-keys registered))
        (define toolbar-language
          (hash 'position language-position 'no_language_chosen no-language?
                'module_language module-language? 'unnamed_empty unnamed-empty?
                'capability_keys capability-keys 'capabilities_registered registered
                'capability_values capabilities))
        ;; Preserve diagnostic evidence even if the state/order assertion fails.
        (set! last-state (hash 'memory_limit memory-limit 'toolbar_labels labels
                              'toolbar_language toolbar-language))
        (define expected
          (expected-toolbar-labels (hash-ref config 'mode) (step) unnamed-empty?
                                   no-language? module-language? registered capabilities full-expected))
        ;; Filter against all five names, so unexpected visible language tools
        ;; cannot disappear from the no-language comparison.
        (define observed (filter (lambda (label) (member label full-expected)) labels))
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
                    'toolbar_labels labels 'toolbar_language toolbar-language))
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
        (hash 'status "passed" 'observer "CI-only native app retained host" 'checks checks
              'genuine_host #t 'entrypoint_replaced #f 'fixture_opened_by_observer #f
              'content_or_preferences_changed #f
              'toolbar_labels labels 'toolbar_language toolbar-language
              'full_toolbar_verified (and module-language?
                                          (equal? observed (if horizontal? full-expected (reverse full-expected))))
              'toolbar_horizontal horizontal? 'ui expected-ui 'theme (if modern? "dark" "stock")
              'native native 'painter painter-theme 'native_blending blended? 'save_guard save-guard
              'memory_limit memory-limit
              'sources source-evidence 'geometry (geometry frame) 'complete_stock_parity #f))
      (define (inspect-identity)
        (define identity (identity-reader))
        (set! last-state (hash 'identity identity))
        (define pid (hash-ref identity 'pid))
        (assert! (and (exact-positive-integer? pid) (= pid (hash-ref identity 'running_pid)))
                 "libc and Cocoa report the same real PID")
        (unless first-pid (set! first-pid pid))
        (assert! (= pid first-pid) "Every stage runs in the same native process")
        (assert! (hash-ref identity 'same_running_application) "NSRunningApplication isEqual: remains true")
        (for ([key '(running_bundle_identifier main_bundle_identifier)])
          (assert! (equal? (hash-ref identity key) (hash-ref config 'bundle_id))
                   (format "Actual Cocoa ~a matches expected app" key)))
        (for ([key '(running_bundle_path main_bundle_path)])
          (assert! (and (hash-ref identity key) (equal? (canonical (hash-ref identity key))
                                                       (canonical (hash-ref config 'app_path))))
                   (format "Actual Cocoa ~a is destination-built app" key)))
        (assert! (and (hash-ref identity 'process_image_path)
                      (equal? (canonical (hash-ref identity 'process_image_path))
                              (canonical (hash-ref config 'native_executable_path))))
                 "dyld current process image is the generated native executable")
        ;; Cocoa's executable metadata can describe the declared shell entry.
        ;; Preserve both raw values and accept only the two actual bundle entries.
        (define allowed-executables
          (list (canonical (hash-ref config 'native_executable_path))
                (canonical (build-path (hash-ref config 'app_path) "Contents" "MacOS" "OpenRacket-launch"))))
        (for ([key '(running_executable_path main_bundle_executable_path)])
          (assert! (and (hash-ref identity key)
                        (member (canonical (hash-ref identity key)) allowed-executables))
                   (format "Cocoa ~a identifies an actual native or declared bundle entry" key)))
        (hash-set identity 'same_pid #t))
      (define (inspect-all)
        (set! checks 0)
        (define identity (inspect-identity))
        (define windows (get-top-level-windows))
        (define frames (filter (lambda (w) (is-a? w (drracket:get/extend:get-unit-frame))) windows))
        (assert! (and (pair? frames) (<= (length frames) 8)) "One to eight genuine frames")
        (assert! (andmap (lambda (f) (send f is-shown?)) frames) "All observed application frames are shown")
        (define frame-reports
          (for/list ([frame (in-list frames)]) (hash-set (inspect-frame frame) 'frame_id (id frame))))
        (define tabs
          (for*/list ([frame (in-list frames)] [tab (in-list (send frame get-tabs))])
            (assert! (eq? frame (send tab get-frame)) "Original tab retains its real frame")
            (define defs (send tab get-defs))
            (define ints (send tab get-ints))
            (assert! (is-a? defs (drracket:get/extend:get-definitions-text)) "All tabs retain registered definitions class")
            (assert! (is-a? ints (drracket:get/extend:get-interactions-text)) "All tabs retain registered interactions class")
            (assert! (not (send defs is-modified?)) "Every observed definitions buffer is unmodified")
            (define name (send defs get-filename))
            (define filename (and name (canonical name)))
            (assert! (<= (send defs last-position) 20000) "Bounded synthetic editor fixture")
            (define text (send defs get-text))
            (hash 'frame_id (id frame) 'tab_id (id tab) 'definitions_id (id defs) 'interactions_id (id ints)
                  'filename filename 'characters (string-length text) 'text text
                  'editor_utf8_sha256 (digest-bytes (string->bytes/utf-8 text))
                  'modified #f 'current (eq? tab (send frame get-current-tab)))))
        (assert! (<= (length tabs) 8) "At most eight observed tabs")
        (define expected (map canonical (expected-files config (step))))
        (define named (filter (lambda (t) (hash-ref t 'filename)) tabs))
        (assert! (equal? (sort (map (lambda (t) (hash-ref t 'filename)) named) string<?)
                         (sort expected string<?))
                 "Stock-opened file set contains each expected file exactly once and no extras")
        (define active-fixture-toolbar
          (and (not (equal? (step) "coldempty"))
               (current-fixture-toolbar-witness tabs frame-reports expected)))
        (unless (equal? (step) "coldempty")
          (assert! active-fixture-toolbar
                   "A current expected fixture has a verified module-language five-tool toolbar"))
        (for ([t (in-list tabs)])
          (define filename (hash-ref t 'filename))
          (if filename
              (begin
                (assert! (equal? (hash-ref t 'text) (hash-ref fixture-texts filename))
                         "Actual editor preserves exact expected Unicode content")
                (assert! (<= (file-size filename) 80000) "Fixture stays within the bounded byte size")
                (assert! (equal? (digest-bytes (file->bytes filename)) (hash-ref fixture-hashes filename))
                         "Disposable fixture bytes remain unchanged"))
              (assert! (equal? (hash-ref t 'text) "") "Unnamed startup editor remains empty")))
        (define blank-count (- (length tabs) (length named)))
        (if (equal? (hash-ref config 'mode) "coldfile")
            (assert! (= blank-count 0) "Cold-file sequence has no phantom blank document")
            (if (equal? (step) "coldempty")
                (assert! (and (= blank-count 1) (= (length frames) 1)) "Exactly one initial empty stock document")
                (assert! (<= blank-count 1) "No additional unnamed documents after warm event")))
        ;; IDs come from eq?-keyed live object identity, never path-based guesses.
        (define snapshot
          (sort (map (lambda (t) (list (hash-ref t 'frame_id) (hash-ref t 'tab_id)
                                      (hash-ref t 'definitions_id) (hash-ref t 'interactions_id)
                                      (hash-ref t 'filename))) tabs)
                < #:key cadr))
        (when prior-snapshot
          (for ([before (in-list prior-snapshot)] #:when (list-ref before 4))
            (assert! (member before snapshot) "Previously opened file retains frame/tab/editor identities")))
        (when (equal? (step) "duplicate")
          (assert! (equal? snapshot prior-snapshot) "Observed duplicate dispatch creates no new frame/tab/editor"))
        (define report
          (hash 'status "passed" 'observer "CI-only genuine native app" 'checks checks
                'entrypoint_replaced #f 'fixture_opened_by_observer #f 'handler_replaced #f
                'content_or_preferences_changed #f 'pid first-pid 'same_pid #t 'identity identity
                'frames frame-reports 'tabs tabs 'frame_count (length frames) 'tab_count (length tabs)
                'blank_count blank-count 'expected_files expected
                'active_fixture_toolbar_witness (or active-fixture-toolbar 'null)
                'sources source-evidence
                'profile (hash 'user_home (or (getenv "PLTUSERHOME") 'null)
                               'addon_dir (or (getenv "PLTADDONDIR") 'null)
                               'compiled_roots (current-compiled-file-roots))
                'geometry (geometry (car frames))
                'duplicate (if (equal? (step) "duplicate")
                               (hash 'observed_no_duplicate #t 'handler_receipt_proven #f
                                     'before prior-snapshot 'after snapshot 'settle_ms 2000)
                               #f)
                'external_dispatch dispatch-evidence 'complete_app_acceptance #f))
        (values report snapshot))
      (define (read-control kind)
        (define path (control-path config (step) (symbol->string kind)))
        (and (file-exists? path)
             (let ([data (read-json-file path)])
               (unless (control-valid? data config (step) kind)
                 (error 'mac-app-control "Mismatched or malformed ~a control for ~a" kind (step)))
               data)))
      (define (next-stage!)
        (set! reports (append reports (list last-state)))
        (set! prior-snapshot stable-snapshot)
        (cond
          [(= step-index 2)
           (write-new-json! (build-path (hash-ref config 'output_dir)
                                        (format "~a.complete.json" (hash-ref config 'run_id)))
                            (hash 'schema 1 'run_id (hash-ref config 'run_id) 'status "passed"
                                  'all_screenshots_acknowledged #t 'same_pid #t 'pid first-pid
                                  'steps (step-names config) 'complete_app_acceptance #f))
           (emit "OPENRACKET_MAC_APP_COMPLETE" (hash 'run_id (hash-ref config 'run_id) 'pid first-pid))
           (finish! 0)]
          [else
           (set! step-index (add1 step-index))
           (set! phase 'waiting)
           (set! dispatched-at #f) (set! dispatch-evidence #f)
           (set! stable-count 0) (set! stable-snapshot #f)
           (set! deadline (+ (current-inexact-monotonic-milliseconds) 60000))
           (set! last-problem "Awaiting external Launch Services dispatch receipt")]))
      (define (observe-turn!)
        (with-handlers ([exn:fail? (lambda (e) (set! stable-count 0)
                                  (set! last-problem (exn-message e)))])
          (define-values (report snapshot) (inspect-all))
          (set! last-state report)
          (set! stable-count (if (equal? stable-snapshot snapshot) (add1 stable-count) 1))
          (set! stable-snapshot snapshot)
          (when (and (>= stable-count 3)
                     (or (not (equal? (step) "duplicate"))
                         (>= (- (current-inexact-monotonic-milliseconds) dispatched-at) 2000)))
            (publish! report 0))))
      (define (tick)
        (with-handlers ([exn:fail?
                         (lambda (e)
                           (if (eq? phase 'waiting) (fail! (exn-message e))
                               (begin (emit "OPENRACKET_MAC_APP_FATAL" (hash 'error (bounded (exn-message e))))
                                      (finish! 1))))])
          (case phase
            [(waiting)
             (cond
               [(>= (current-inexact-monotonic-milliseconds) deadline) (fail! last-problem)]
               [else
                (when (and (> step-index 0) (not dispatched-at))
                  (define sent (read-control 'sent))
                  (when sent
                    (set! dispatch-evidence sent)
                    (set! dispatched-at (current-inexact-monotonic-milliseconds))))
                (when (or (= step-index 0) dispatched-at) (observe-turn!))])]
            [(capture)
             (define ack (read-control 'ack))
             (cond [ack (if (zero? result-code) (next-stage!) (finish! result-code))]
                   [(>= (current-inexact-monotonic-milliseconds) capture-deadline)
                    (emit "OPENRACKET_MAC_APP_CAPTURE_TIMEOUT" (envelope))
                    (finish! (if (zero? result-code) 2 result-code))])])))
      (with-handlers ([exn:fail? (lambda (e)
                                 (emit "OPENRACKET_MAC_APP_CONFIGURATION_FAILURE"
                                       (hash 'error (bounded (exn-message e))))
                                 (if control-ready?
                                     (begin (fail! (exn-message e))
                                            (set! timer (new timer% [notify-callback tick] [interval 100])))
                                     (finish! 1)))])
        (set! config (validate-config (read-json-file config-path)))
        (set! steps (step-names config))
        (for ([key '(output_dir app_path profile_path)])
          (assert! (directory-exists? (hash-ref config key)) (format "Existing ~a directory" key)))
        (assert! (file-exists? (hash-ref config 'native_executable_path)) "Native executable exists")
        (assert! (null? (directory-list (hash-ref config 'output_dir))) "Fresh empty evidence directory")
        (set! control-ready? #t)
        (set! expected-memory-limit (parse-expected-memory-limit (hash-ref config 'memory_mib)))
        (assert! (equal? (version) "9.3") "Pinned Racket 9.3 runtime")
        (assert! (equal? (getenv "OPENRACKET_UI") "modern") "Actual launcher modern UI")
        (assert! (equal? (getenv "OPENRACKET_THEME") "dark") "App built for explicit dark theme")
        (assert! (equal? (getenv "OPENRACKET_NATIVE_APPEARANCE") "1") "Native appearance enabled by launcher")
        (assert! (and (getenv "PLTUSERHOME")
                      (equal? (canonical (getenv "PLTUSERHOME")) (canonical (hash-ref config 'profile_path))))
                 "Actual process uses selected isolated profile")
        (assert! (and (getenv "PLTADDONDIR")
                      (equal? (canonical (getenv "PLTADDONDIR"))
                              (canonical (build-path (hash-ref config 'profile_path) ".local" "share" "racket"))))
                 "Actual process uses selected isolated addon")
        (assert! (and (pair? (current-compiled-file-roots))
                      (path? (car (current-compiled-file-roots)))
                      (equal? (canonical (car (current-compiled-file-roots)))
                              (canonical (build-path (hash-ref config 'profile_path) "compiled-cache"))))
                 "Actual compiled roots are private-first")
        (for ([name (in-list (hash-ref config 'files))])
          (define path (canonical name))
          (assert! (<= (file-size path) 80000) "Small disposable UTF-8 fixture")
          (define bytes (file->bytes path))
          (define text (bytes->string/utf-8 bytes #f))
          (assert! (<= (string-length text) 20000) "Small disposable Unicode fixture")
          (assert! (not (hash-has-key? fixture-texts path)) "Canonical fixture paths are distinct")
          (hash-set! fixture-texts path text)
          (hash-set! fixture-hashes path (digest-bytes bytes)))
        (set! source-evidence
              (list (source "color.rkt" '("framework" "private")
                            "da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578")
                    (source "unit.rkt" '("drracket" "private")
                            "535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5")
                    (source "eval-helpers-and-pref-init.rkt" '("drracket" "private")
                            "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62")
                    (source "text-misc.rkt" '("framework" "private")
                            "00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d")
                    (source "autosave.rkt" '("framework" "private")
                            "db156fe925d2372bcfadac91abe8be5568b68bea52c1cacd73264bdf548c9f9f")))
        (assert! (not (file-exists? (build-path (path-only (collection-file-path "unit.rkt" "drracket" "private"))
                                              "openracket-all-string-snips.rkt")))
                 "No scan experiment installed")
        (define eventspace (current-eventspace))
        (set! identity-reader
              ((dynamic-require cocoa-reader-path 'make-cocoa-identity-reader)
               (lambda () (and (not (eventspace-shutdown? eventspace))
                               (eq? (current-thread) (eventspace-handler-thread eventspace))))))
        (emit "OPENRACKET_MAC_APP_OBSERVER_STARTED"
              (hash 'run_id (hash-ref config 'run_id) 'steps steps 'sources source-evidence))
        (set! timer (new timer% [notify-callback tick] [interval 100]))
        ;; 3 * (60s observation + 20s ACK) plus 30s headroom. A stuck GUI
        ;; callback still requires the independent external CI timeout.
        (thread (lambda () (sleep 270)
                  (unless completed?
                    (emit "OPENRACKET_MAC_APP_WATCHDOG" (hash 'status "failed" 'last_problem last-problem))
                    (exit 2))))))))
