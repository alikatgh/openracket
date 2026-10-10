#lang racket/base
;; Native follow-on acceptance checks. Source reviewed; native execution pending.
;; Invoke run-follow-on-check! on the genuine DrRacket GUI handler thread after
;; normal startup, in a fresh disposable profile/process for EACH selected case.
(require racket/class racket/file racket/gui/base racket/list racket/string racket/set json
         string-constants rackunit)
(provide run-follow-on-check!)

(define (await! description predicate [seconds 20])
  (define deadline (+ (current-inexact-monotonic-milliseconds) (* 1000 seconds)))
  (let loop ()
    (define value (predicate))
    (cond [value value]
          [(>= (current-inexact-monotonic-milliseconds) deadline)
           (error 'follow-on "Timed out: ~a. Preserve a failure screenshot; do not dismiss dialogs." description)]
          [else (yield (alarm-evt (+ (current-inexact-milliseconds) 20))) (loop)])))

(define (snips editor)
  (let loop ([snip (send editor find-first-snip)] [acc '()])
    (if snip (loop (send snip next) (cons snip acc)) (reverse acc))))
(define (bitmap-bytes bitmap)
  (define data (make-bytes (* 4 (send bitmap get-width) (send bitmap get-height))))
  (send bitmap get-argb-pixels 0 0 (send bitmap get-width) (send bitmap get-height) data)
  data)

(define (run-follow-on-check! frame which)
  (parameterize ([current-check-handler raise])
    (perform-follow-on-check! frame which)))

(define (perform-follow-on-check! frame which)
  (unless (eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
    (error 'follow-on "Run this test on the real frame eventspace handler thread"))
  (define directory (make-temporary-file "openracket-followon-~a" 'directory))
  (define defs (send frame get-definitions-text))
  (define ints (send frame get-interactions-text))
  (define run (send frame get-execute-button))
  (define stop (send frame get-break-button))
  (define tab (send frame get-current-tab))
  (define (load! contents)
    (define file (build-path directory "fixture.rkt"))
    (call-with-output-file file #:exists 'truncate (lambda (out) (display contents out)))
    (send frame change-to-file file)
    (check-equal? (send defs get-text) contents "public file-open must load exact fixture")
    file)
  (define (start!)
    (await! "Run enabled" (lambda () (send run is-enabled?)))
    (send run command))
  (define (output-has? text) (string-contains? (send ints get-text) text))
  ;; No preference, instrumentation, language limits or tool discovery are changed.
  (case which
    [(stop)
     (load! "#lang racket/base\n(displayln \"WAITING_TO_BREAK\")\n(flush-output)\n(sleep 120)\n(displayln \"UNREACHABLE\")\n")
     (start!)
     ;; Stock Run can remain enabled to restart a running program. Evaluation
     ;; liveness is the tab's independently maintained state, not widget enablement.
     (define (stop-state stage)
       (define-values (thread custodian) (send tab get-breakables))
       (display "OPENRACKET_STOP_STATE ")
       (write-json (hash 'stage stage 'running (send tab is-running?)
                         'run_enabled (send run is-enabled?)
                         'stop_enabled (send stop is-enabled?)
                         'break_thread_live (and (thread? thread) (not (thread-dead? thread)))
                         'break_custodian_present (custodian? custodian)
                         'stop_label (send stop get-label)))
       (newline) (flush-output))
     (await! "running blocking program with live break target"
             (lambda ()
               (define-values (thread custodian) (send tab get-breakables))
               (and (output-has? "WAITING_TO_BREAK") (send tab is-running?)
                    (thread? thread) (not (thread-dead? thread)) (custodian? custodian))))
     (stop-state "before-stop")
     (check-true (send stop is-enabled?))
     (check-equal? (send stop get-label) (string-constant break-button-label))
     (send stop command)
     ;; Stock's private local-member does-break-kill? is not externally callable.
     ;; Its real callback synchronously exposes that transition through this label.
     (check-equal? (send stop get-label) (string-constant break-button-kill-label))
     (stop-state "after-stop-before-event-loop")
     (await! "interrupted evaluation completes and Run is available"
             (lambda () (and (not (send tab is-running?)) (send run is-enabled?))))
     (stop-state "after-interrupt-cleanup")
     (check-false (output-has? "UNREACHABLE"))
     (check-eq? (send frame get-definitions-text) defs)]
    [(input-eof)
     (load! (string-append "#lang racket/base\n(displayln \"INPUT_WAIT\")\n(flush-output)\n"
                          "(define line (read-line))\n(printf \"READ=~a\\n\" line)\n(flush-output)\n"
                          "(printf \"EOF=~a\\n\" (eof-object? (read-line)))\n"))
     (start!)
     (define (current-input-box)
       (for/or ([snip (in-list (snips ints))])
         (and (is-a? snip editor-snip%)
              (is-a? (send snip get-editor) (send ints get-box-input-text%))
              (not (send (send snip get-editor) is-locked?))
              (send snip get-editor))))
     (define input (await! "native read-line input editor" current-input-box))
     (send input insert "café λ")
     (send input on-char (new key-event% [key-code #\return]))
     (await! "Unicode text reaches actual stdin" (lambda () (output-has? "READ=café λ")))
     (await! "second read-line input editor" current-input-box)
     ;; This is the same public port bridge used by the retained EOF snip.
     ;; It verifies EOF semantics, not physical pointer hit-testing on that snip.
     (send ints send-eof-to-box-in-port)
     (await! "EOF completes real program" (lambda () (and (output-has? "EOF=#t")
                                                         (not (send tab is-running?))
                                                         (send run is-enabled?))))
     (check-eq? (send frame get-interactions-text) ints)]
    [(wxme)
     (load! "#lang racket/base\n;; Rich document preservation fixture\n")
     (define bitmap (make-bitmap 12 9 #t))
     (define bitmap-dc (new bitmap-dc% [bitmap bitmap]))
     (send bitmap-dc set-background "red") (send bitmap-dc clear) (send bitmap-dc set-bitmap #f)
     (define image (make-object image-snip% bitmap))
     (define nested (new text%)) (send nested insert "nested café λ")
     (send defs insert image (send defs last-position))
     (send defs insert (new editor-snip% [editor nested]) (send defs last-position))
     (define rich-file (build-path directory "rich.wxme"))
     (check-true (send defs save-file rich-file 'standard))
     (send frame change-to-file rich-file)
     (define restored-images (filter (lambda (s) (is-a? s image-snip%)) (snips defs)))
     (define restored-editors (filter (lambda (s) (is-a? s editor-snip%)) (snips defs)))
     (check-equal? (length restored-images) 1)
     (check-equal? (length restored-editors) 1)
     (check-equal? (bitmap-bytes (send (car restored-images) get-bitmap)) (bitmap-bytes bitmap))
     (check-equal? (send (send (car restored-editors) get-editor) get-text) "nested café λ")
     (define canvas (send frame get-definitions-canvas))
     (define identities (snips defs))
     (send defs set-position 2 8)
     (send canvas on-focus #t) (send canvas on-paint)
     (send canvas on-superwindow-activate #f) (send canvas on-paint)
     (send canvas on-superwindow-activate #t) (send canvas on-paint)
     (check-equal? (snips defs) identities)
     (check-equal? (list (send defs get-start-position) (send defs get-end-position)) '(2 8))
     (check-eq? (send canvas get-editor) defs)]
    [(check-syntax)
     (define contents "#lang racket/base\n(define (bump x) (+ x 1))\n(bump 41)\n")
     (load! contents)
     ;; Let the actual Run callback perform stock #lang selection first.
     (start!)
     (await! "module Run returns 42 before Check Syntax"
             (lambda () (and (send run is-enabled?) (not (send tab is-running?))
                            (regexp-match? #rx"(^|\n)42(\n|$)" (send ints get-text)))))
     (define button (send frame syncheck:get-button))
     (await! "Check Syntax enabled" (lambda () (send button is-enabled?)))
     (send button command)
     (await! "real lexical binding arrows" (lambda ()
                                             (and (send button is-enabled?)
                                                  (positive? (hash-count (send defs syncheck:get-bindings-table))))))
     (check-false (send frame syncheck:error-report-visible?))
     (check-equal? (send defs get-text) contents)
     (define arrows (hash-copy (send defs syncheck:get-bindings-table)))
     ;; Object identity is process-local; emit exact numeric endpoints for pairing.
     (define (lexicographic<? a b)
       (cond [(null? a) (pair? b)] [(null? b) #f]
             [(= (car a) (car b)) (lexicographic<? (cdr a) (cdr b))]
             [else (< (car a) (car b))]))
     (define endpoints
       (sort
        (remove-duplicates
         (for*/list ([(start ends) (in-hash arrows)]
                     [end (in-set ends)]
                     #:when (and (eq? (car start) defs) (eq? (car end) defs)))
           (append (cdr start) (cdr end)))) lexicographic<?))
     (define undirected
       (for/list ([edge (in-list endpoints)])
         (define left (take edge 2)) (define right (drop edge 2))
         (if (lexicographic<? left right) edge (append right left))))
     (check-not-false (member '(27 31 45 49) undirected) "bump definition/use link exists")
     (check-not-false (member '(32 33 38 39) undirected) "x parameter/use link exists")
     (display "OPENRACKET_BINDING_GRAPH ") (write-json endpoints) (newline) (flush-output)
     (send defs set-position 1 6)
     (define canvas (send frame get-definitions-canvas))
     (send canvas on-focus #t) (send canvas on-paint)
     (send canvas on-superwindow-activate #f) (send canvas on-paint)
     (check-equal? (send defs syncheck:get-bindings-table) arrows)
     (check-equal? (list (send defs get-start-position) (send defs get-end-position)) '(1 6))]
    [else (error 'follow-on "Unknown case ~a" which)])
  ;; Keep files for failure diagnostics; owning disposable process deletes its
  ;; temporary workspace only after screenshots/logs. Never save outside it.
  (printf "OPENRACKET_FOLLOWON_CASE ~a completed\n" which)
  (flush-output)
  (hash 'case (symbol->string which) 'status "passed"
        'temporary_directory (path->string directory)))
