#lang racket/base
;; Three independent native stock-tool acceptance gates. Native execution pending.
;; Call from the coordinator, NOT from on-gui. One case per fresh process/profile.
(require racket/class racket/file racket/gui/base racket/list racket/path
         racket/string json rackunit string-constants mrlib/switchable-button
         "native-tool-coordinator.rkt")
(provide run-native-tool-check!)

(define debugger-fixture
  "#lang racket/base\n(define (bump x) (+ x 1))\n(define answer (bump 41))\n(displayln \"OPENRACKET_DEBUG_COMPLETE\")\n(displayln answer)\n")
(define macro-fixture
  "#lang racket/base\n(define-syntax-rule (openracket-twice x) (+ x x))\n(displayln \"OPENRACKET_MACRO_COMPLETE\")\n(+ (openracket-twice 10) (openracket-twice 11))\n")
(define teaching-failing
  "#lang htdp/bsl\n(define (bump x) (+ x 1))\n(bump 41)\n(check-expect (bump 1) 2)\n(check-expect (bump 2) 4)\n")
(define teaching-corrected
  (string-replace teaching-failing "(check-expect (bump 2) 4)"
                  "(check-expect (bump 2) 3)"))

(define (emit stage value)
  (printf "OPENRACKET_STOCK_TOOL_STATE ~a\n"
          (jsexpr->string (hash 'stage stage 'evidence value)))
  (flush-output))
(define (descendants node)
  ;; A control with a shown flag under a hidden ancestor is not visible.
  (if (and (is-a? node window<%>) (not (send node is-shown?)))
      '()
      (cons node (if (is-a? node area-container<%>)
                     (append-map descendants (send node get-children)) '()))))
(define (unique-control root class% matches?)
  (define found
    (filter (lambda (node) (and (is-a? node class%) (send node is-shown?) (matches? node)))
            (descendants root)))
  (check-equal? (length found) 1 "Exactly one live, shown stock control must match")
  (car found))
(define (normal-label=? value text [side #f])
  ;; Stock 9.3 button% retains its bitmap/text/side label tuple verbatim.
  (if side
      (and (list? value) (= (length value) 3)
           (equal? (cadr value) text) (eq? (caddr value) side))
      (equal? value text)))
(define (source-id source)
  (cond [(path? source) (path->string (simplify-path source))]
        [(string? source) source]
        [else (format "~s" source)]))
(define (location->json location)
  (hash 'source (source-id (srcloc-source location))
        'line (or (srcloc-line location) 'null)
        'column (or (srcloc-column location) 'null)
        'position (or (srcloc-position location) 'null)
        'span (or (srcloc-span location) 'null)))

(define (run-native-tool-check! frame which on-gui wait-for register-frame!)
  (unless (equal? (version) "9.3")
    (error 'native-tool-gate "These source-pinned gates require official Racket 9.3"))
  (when (eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
    (error 'native-tool-gate "Coordinator must be outside the GUI handler"))
  (define-values (gui await)
    (make-checked-coordinator on-gui wait-for
                              (eventspace-handler-thread (send frame get-eventspace))))
  (define directory (make-temporary-file "openracket-stock-tool-~a" 'directory))
  (define file (build-path directory "fixture.rkt"))
  (define initial
    (gui (lambda ()
           (list (send frame get-definitions-text) (send frame get-interactions-text)
                 (send frame get-current-tab) (send frame get-definitions-canvas)
                 (send frame get-interactions-canvas) (send frame get-execute-button)))))
  (define defs (list-ref initial 0))
  (define ints (list-ref initial 1))
  (define tab (list-ref initial 2))
  (define canvas (list-ref initial 3))
  (define ints-canvas (list-ref initial 4))
  (define run (list-ref initial 5))
  (define (identities!)
    (check-eq? defs (send frame get-definitions-text))
    (check-eq? ints (send frame get-interactions-text))
    (check-eq? tab (send frame get-current-tab))
    (check-eq? canvas (send frame get-definitions-canvas))
    (check-eq? ints-canvas (send frame get-interactions-canvas))
    (check-eq? run (send frame get-execute-button))
    (check-eq? defs (send canvas get-editor))
    (check-eq? ints (send ints-canvas get-editor)))
  (define (load! contents)
    (call-with-output-file file #:exists 'truncate
      (lambda (out) (display contents out)))
    (gui (lambda ()
           (send frame change-to-file file)
           (identities!)
           (check-equal? (send defs get-text) contents)
           (check-equal? (simplify-path (send defs get-filename)) (simplify-path file)))))
  (define (start!)
    (await "Run enabled" (lambda () (send run is-enabled?)))
    (gui (lambda () (send run command))))
  (define (done? marker)
    (and (not (send tab is-running?)) (send run is-enabled?)
         (string-contains? (send ints get-text) marker)
         (regexp-match? #rx"(^|\n)42(\n|$)" (send ints get-text))))
  (define (focus-preserves! expected-source)
    ;; Pin source/editor/selection before any focus or repaint operation.
    (define selection
      (gui (lambda ()
             (identities!)
             (check-equal? (send defs get-text) expected-source)
             (send defs set-position 1 6)
             (define pinned (list (send defs get-start-position) (send defs get-end-position)))
             (send frame show #t)
             (send canvas focus)
             pinned)))
    (await "retained definitions canvas receives native focus" (lambda () (send canvas has-focus?)))
    (gui (lambda ()
           (send canvas on-paint)
           (identities!)
           (check-equal? (send defs get-text) expected-source)
           (check-equal? (list (send defs get-start-position) (send defs get-end-position)) selection)
           (check-true (send canvas has-focus?)))))

  (define result
    (case which
      [(debugger)
       (load! debugger-fixture)
       ;; Establish the real module language and opt-out toolbar via ordinary Run.
       (start!)
       (await "pre-debug Run completes" (lambda () (done? "OPENRACKET_DEBUG_COMPLETE")))
       (define debug
         (gui (lambda ()
                ;; get-debug-button is a HIDDEN legacy control for #lang programs.
                (unique-control (send frame get-button-panel) switchable-button%
                                (lambda (button)
                                  (equal? (send button get-label)
                                          (string-constant debug-tool-button-name)))))))
       (define step (gui (lambda () (send frame get-step-button))))
       (define resume (gui (lambda () (send frame get-resume-button))))
       (define (suspended?)
         (and (send tab debug?) (send tab is-running?) (send tab get-break-status)
              (pair? (send tab get-stack-frames))
              (exact-positive-integer? (send tab get-pc))
              (send step is-enabled?) (send resume is-enabled?)))
       (define (debug-state)
         (hash 'pc (send tab get-pc)
               'break_status (format "~s" (send tab get-break-status))
               'frame_endpoints (send tab get-current-frame-endpoints)))
       (define (assert-source!)
         (identities!)
         (check-equal? (send defs get-text) debugger-fixture)
         (check-eq? (send tab defs-containing-pc) defs)
         (check-eq? (send tab defs-containing-current-frame) defs)
         (define endpoints (send tab get-current-frame-endpoints))
         (check-equal? (length endpoints) 2)
         (check-true (and (exact-positive-integer? (car endpoints))
                         (<= (car endpoints) (cadr endpoints) (send defs last-position)))))
       (await "shown Debug control enabled" (lambda () (send debug is-enabled?)))
       (gui (lambda () (send debug command)))
       (await "Debugger suspended at real fixture source" suspended?)
       (define first-state
         (gui (lambda () (assert-source!) (debug-state))))
       (emit "debugger-suspended" first-state)
       (focus-preserves! debugger-fixture)
       (gui (lambda ()
              (check-equal? (debug-state) first-state)
              (check-true (send step is-enabled?))
              (send step command)))
       ;; The Step callback returns before any completion polling.
       (await "Debugger Step changes PC/status/endpoints tuple"
              (lambda () (and (suspended?) (not (equal? (debug-state) first-state)))))
       (define next-state
         (gui (lambda () (assert-source!) (debug-state))))
       (emit "debugger-stepped" next-state)
       (gui (lambda ()
              (check-true (send resume is-enabled?))
              (send resume command)))
       (await "Debugger Go completes actual evaluation and output"
              (lambda () (done? "OPENRACKET_DEBUG_COMPLETE")))
       (gui (lambda ()
              (identities!)
              (check-false (send tab get-break-status))
              (check-false (send tab get-stack-frames))
              (check-false (send step is-enabled?))
              (check-false (send resume is-enabled?))))
       ;; Recovery must also work through stock Run after debug evaluation.
       (start!)
       (await "ordinary Run recovers after Debugger" (lambda () (done? "OPENRACKET_DEBUG_COMPLETE")))
       (gui (lambda () (identities!) (check-false (send tab debug?))))
       (hash 'first_stop first-state 'after_step next-state
             'step_changed_observable_state #t 'real_resume_completed #t
             'ordinary_run_recovered #t)]

      [(macro-stepper)
       (load! macro-fixture)
       (start!)
       (await "pre-stepper Run completes" (lambda () (done? "OPENRACKET_MACRO_COMPLETE")))
       (define old-windows (gui get-top-level-windows))
       (define launch
         (gui (lambda ()
                (unique-control (send frame get-button-panel) switchable-button%
                                (lambda (button)
                                  (equal? (send button get-label) (string-constant macro-stepper)))))))
       (await "Macro Stepper control enabled" (lambda () (send launch is-enabled?)))
       (gui (lambda () (send launch command)))
       (define tool-frame
         (await "new stock Macro Stepper frame"
                (lambda ()
                  (define found
                    (for/list ([window (in-list (get-top-level-windows))]
                               #:when (and (not (memq window old-windows))
                                           (send window is-shown?)
                                           (object-method-arity-includes? window 'get-widget 0)
                                           (object-method-arity-includes? window 'add-obsoleted-warning 0)))
                      window))
                  (when (> (length found) 1)
                    (error 'native-tool-gate "Multiple Macro Stepper frames appeared"))
                  (and (pair? found) (car found)))))
       (gui (lambda () (register-frame! tool-frame)))
       (define widget (gui (lambda () (send tool-frame get-widget))))
       (define (nav text side)
         (unique-control tool-frame button%
                         (lambda (button) (normal-label=? (send button get-label) text side))))
       (define controls
         (gui (lambda ()
                (check-true (is-a? widget (dynamic-require 'macro-debugger/view/stepper 'macro-stepper-widget%)))
                (list (nav "Start" 'left) (nav "Step" 'left)
                      (nav "Step" 'right) (nav "End" 'right)))))
       (define start-button (list-ref controls 0))
       (define previous-button (list-ref controls 1))
       (define next-button (list-ref controls 2))
       (define end-button (list-ref controls 3))
       (define (index) (send widget get-current-step-index))
       (define (browser-text) (send (send (send widget get-view) get-text) get-text 0 'eof #t))
       ;; A valid cursor is set only after a real term's reductions are ready.
       ;; The required visible macro and enabled navigation exclude empty/error
       ;; windows and a no-op navigation call before asynchronous add-deriv lands.
       (await "completed derivation and enabled real navigation"
              (lambda ()
                (and (not (send tab is-running?)) (send run is-enabled?)
                     (exact-nonnegative-integer? (index))
                     (string-contains? (browser-text) "openracket-twice")
                     (send next-button is-enabled?))))
       (define start-index (gui index))
       (define start-text (gui browser-text))
       (gui (lambda ()
              (check-equal? start-index 0)
              (check-false (send start-button is-enabled?))
              (check-false (send previous-button is-enabled?))
              (identities!)
              (check-equal? (send defs get-text) macro-fixture)))
       (define (click! button)
         (gui (lambda ()
                (check-true (send button is-enabled?))
                (send button command (new control-event% [event-type 'button])))))
       (click! next-button)
       (await "Macro Stepper Next advances a real derivation index"
              (lambda () (and (exact-nonnegative-integer? (index)) (> (index) start-index))))
       (define next-index (gui index))
       (click! end-button)
       (await "Macro Stepper End reaches completed expansion"
              (lambda () (and (exact-nonnegative-integer? (index)) (> (index) next-index)
                             (not (send next-button is-enabled?))
                             (not (send end-button is-enabled?))
                             (send previous-button is-enabled?))))
       (define end-index (gui index))
       (define end-text (gui browser-text))
       (gui (lambda () (check-not-equal? start-text end-text)))
       (click! previous-button)
       (await "Macro Stepper Previous goes back one step"
              (lambda () (equal? (index) (sub1 end-index))))
       (click! start-button)
       (await "Macro Stepper Start restores the original derivation"
              (lambda () (and (equal? (index) start-index)
                             (equal? (browser-text) start-text)
                             (not (send previous-button is-enabled?)))))
       (emit "macro-stepper-navigated"
             (hash 'start_index start-index 'next_index next-index 'end_index end-index
                   'initial_text start-text 'expanded_text end-text))
       (gui (lambda ()
              (identities!)
              (check-equal? (send defs get-text) macro-fixture)
              ;; frame:basic%.close preserves can-close?/on-close/show semantics.
              ;; Hiding a window alone is not a successful close.
              (send tool-frame close)))
       (await "Macro Stepper normal close hides only its own frame"
              (lambda () (and (not (send tool-frame is-shown?)) (send frame is-shown?))))
       (focus-preserves! macro-fixture)
       (start!)
       (await "ordinary Run recovers after Macro Stepper close"
              (lambda () (done? "OPENRACKET_MACRO_COMPLETE")))
       (gui identities!)
       (hash 'start_index start-index 'next_index next-index 'end_index end-index
             'derivation_changed #t 'previous_and_start_verified #t
             'normal_close #t 'ordinary_run_recovered #t)]

      [(teaching-tests)
       (load! teaching-failing)
       (start!)
       (await "htdp/bsl completes and exposes actual failure report"
              (lambda () (and (done? "42") (send tab get-test-editor)
                             (positive? (send (send tab get-test-editor) last-position)))))
       ;; Read the already-instantiated test engine in the actual user evaluator.
       ;; Do not fabricate a model, change its results, or require test-engine in
       ;; the harness namespace and mistake that empty instance for user state.
       (define (snapshot-tests!)
         (define response (box #f))
         (gui (lambda ()
                (define user-namespace (send ints get-user-namespace))
                (check-true (namespace? user-namespace))
                (check-false (send tab is-running?))
                (send ints run-in-evaluation-thread
                      (lambda ()
                        (with-handlers ([(lambda (_) #t)
                                         (lambda (e) (set-box! response (cons 'error e)))])
                          (parameterize ([current-namespace user-namespace])
                            ;; Fails if this engine was not instantiated by BSL.
                            (module->namespace 'test-engine/test-engine)
                            (define (api name) (dynamic-require 'test-engine/test-engine name))
                            (define current ((api 'current-test-object)))
                            (define failures ((api 'test-object-failed-checks) current))
                            (set-box!
                             response
                             (cons 'value
                                   (hash 'tests (length ((api 'test-object-tests) current))
                                         'passed (length ((api 'test-object-successful-tests) current))
                                         'failures (length failures)
                                         'details
                                         (for/list ([failure (in-list failures)])
                                           (define reason ((api 'failed-check-reason) failure))
                                           (define unequal? ((api 'unequal?) reason))
                                           (hash 'location (location->json ((api 'fail-reason-srcloc) reason))
                                                 'unequal unequal?
                                                 'actual (and unequal? ((api 'unequal-actual) reason))
                                                 'expected (and unequal? ((api 'unequal-expected) reason)))))))))))))
         (await "read-only evaluator test-result snapshot"
                (lambda ()
                  (define value (unbox response))
                  (and value (if (eq? (car value) 'error) (raise (cdr value)) (cdr value))))))
       (define failing-state (snapshot-tests!))
       (define report (gui (lambda () (send tab get-test-editor))))
       (define failure-form "(check-expect (bump 2) 4)")
       (define failure-start (car (car (regexp-match-positions (regexp-quote failure-form) teaching-failing))))
       (define expected-location
         (hash 'source (path->string (simplify-path file)) 'line 5 'column 0
               'position (add1 failure-start) 'span (string-length failure-form)))
       (gui (lambda ()
              (check-equal? (hash-ref failing-state 'tests) 2)
              (check-equal? (hash-ref failing-state 'passed) 1)
              (check-equal? (hash-ref failing-state 'failures) 1)
              (check-equal? (hash-ref failing-state 'details)
                            (list (hash 'location expected-location 'unequal #t 'actual 3 'expected 4)))
              (define flat-report (send report get-text 0 'eof #t))
              (check-true (string-contains? flat-report
                                           (format (string-constant test-engine-m-of-n-tests-failed) 1 2)))
              (define location-label
                (format (string-constant test-engine-in-at-line-column) "fixture.rkt" "5" "0"))
              (check-true (string-contains? flat-report location-label))
              ;; Test the stock report's installed source-link callback itself.
              ;; Use editor positions from unflattened text so nested value snips
              ;; cannot shift clickback offsets.
              (define link (regexp-match-positions (regexp-quote location-label) (send report get-text)))
              (check-not-false link)
              (send report call-clickback (caar link) (cdar link))
              (define ranges (send ints get-error-ranges))
              (check-true (and (list? ranges) (= (length ranges) 1)))
              (check-eq? (srcloc-source (car ranges)) defs
                         "The actual report clickback resolves to the retained editor")
              (check-equal? (hash-remove (location->json (car ranges)) 'source)
                            (hash-remove expected-location 'source))
              (identities!)))
       (emit "teaching-failure" failing-state)
       (focus-preserves! teaching-failing)
       (gui (lambda ()
              ;; Real editor correction, leaving the source and editor identities
              ;; intact. The next run must consume this unsaved edited buffer.
              (define expected-position (+ failure-start (sub1 (string-length failure-form)) -1))
              (check-equal? (send defs get-text expected-position (add1 expected-position)) "4")
              (send defs insert "3" expected-position (add1 expected-position))
              (check-equal? (send defs get-text) teaching-corrected)
              (check-true (send defs is-modified?))
              (identities!)))
       (start!)
       (await "corrected htdp/bsl Run completes and clears the old report"
              (lambda ()
                (and (done? (string-constant test-engine-both-tests-passed))
                     (eq? report (send tab get-test-editor))
                     (zero? (send report last-position)))))
       (define corrected-state (snapshot-tests!))
       (gui (lambda ()
              (check-equal? (hash-ref corrected-state 'tests) 2)
              (check-equal? (hash-ref corrected-state 'passed) 2)
              (check-equal? (hash-ref corrected-state 'failures) 0)
              (check-equal? (hash-ref corrected-state 'details) '())
              (check-equal? (send defs get-text) teaching-corrected)
              (check-equal? (send report get-text 0 'eof #t) "")
              (identities!)))
       (focus-preserves! teaching-corrected)
       (emit "teaching-corrected" corrected-state)
       (hash 'before failing-state 'after corrected-state
             'source_link_verified #t 'retained_report_cleared #t
             'corrected_unsaved_buffer_rerun #t 'retained_focus_and_editors #t)]
      [else (error 'native-tool-gate "Unknown case ~s" which)]))
  (emit "completed" (hash 'case (symbol->string which) 'status "passed" 'result result))
  (hash 'case (symbol->string which) 'status "passed" 'evidence result
        'temporary_directory (path->string directory)))
