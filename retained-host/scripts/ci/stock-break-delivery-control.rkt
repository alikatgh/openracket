#lang racket/base
;; Separate stock-runtime diagnostic, never loaded into DrRacket. No appearance
;; overlay, evaluator mutation, desktop preference or direct DrRacket break.
;; Each mode must run in its own process using the exact unmodified 9.3 runtime.
(require racket/list racket/string json)

(define args (vector->list (current-command-line-arguments)))
(unless (and (= (length args) 1)
             (member (car args) '("plain-racket" "gui-worker-nested"
                                  "gui-eventspace-nested" "gui-eventspace-returning")))
  (error 'stock-break-control
         "Expected one mode: plain-racket, gui-worker-nested, gui-eventspace-nested, gui-eventspace-returning"))
(define mode (car args))
;; Capture/clear before importing GUI, matching the corrected launch harness.
(current-command-line-arguments #())
(define gui? (not (equal? mode "plain-racket")))
(define eventspace? (string-prefix? mode "gui-eventspace-"))
(define nested? (member mode '("gui-worker-nested" "gui-eventspace-nested")))
(define gui-yield (and gui? (dynamic-require 'racket/gui/base 'yield)))
(define queue (and gui? (dynamic-require 'racket/gui/base 'queue-callback)))
(define current-es (and gui? (dynamic-require 'racket/gui/base 'current-eventspace)))
(define make-es (and gui? (dynamic-require 'racket/gui/base 'make-eventspace)))
(define es-thread (and gui? (dynamic-require 'racket/gui/base 'eventspace-handler-thread)))
(define ready (make-semaphore))
(define done (make-semaphore))
(define target #f)
(define user-custodian #f)
(define phase 'not-started)
(define body-breaks-enabled 'not-observed)
(define body-is-eventspace-handler #f)
(define caught #f)
(define error-message #f)
(define break-sent-at #f)
(define completion-ms #f)

(define (wait-event evt) (if gui? (gui-yield evt) (sync evt)))
(define (on-gui thunk)
  (define finished (make-semaphore))
  (define result #f)
  (queue (lambda ()
           (with-handlers ([(lambda (_) #t) (lambda (e) (set! result (cons 'error e)))])
             (set! result (cons 'value (thunk))))
           (semaphore-post finished)) #f)
  (wait-event (semaphore-peek-evt finished))
  (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))
(define (wait-bounded evt seconds)
  ;; Same 20ms yielded polling pattern as the real host's preservation workflow.
  (define deadline (+ (current-inexact-monotonic-milliseconds) (* 1000 seconds)))
  (let loop ()
    (cond [(sync/timeout 0 evt) #t]
          [(>= (current-inexact-monotonic-milliseconds) deadline) #f]
          [else (wait-event (alarm-evt (+ (current-inexact-milliseconds) 20))) (loop)])))
(define (context)
  (and target
       (not (thread-dead? target))
       (with-handlers ([exn? (lambda (e) (exn-message e))])
         (define entries (continuation-mark-set->context (continuation-marks target)))
         (define text (format "~s" (take entries (min 12 (length entries)))))
         (substring text 0 (min 1800 (string-length text))))))
(define (emit stage)
  (display "OPENRACKET_STOCK_BREAK_CONTROL ")
  (write-json
   (hash 'mode mode 'stage stage 'racket_version (version)
         'os (symbol->string (system-type 'os)) 'vm (symbol->string (system-type 'vm))
         'phase (symbol->string phase)
         'body_breaks_enabled (if (boolean? body-breaks-enabled) body-breaks-enabled 'null)
         'body_is_eventspace_handler body-is-eventspace-handler
         'observer_is_eventspace_handler
         (and gui? (eq? (current-thread) (es-thread (current-es))))
         'target_live (and target (not (thread-dead? target)))
         'target_running (and target (thread-running? target))
         'caught_break (eq? caught 'break) 'error (or error-message 'null)
         'completion_ms (or completion-ms 'null) 'context (or (context) 'null)))
  (newline) (flush-output))
(define (start!)
  ;; These public APIs reproduce DrRacket rep.rkt's eventspace/break setup.
  (define parent (make-custodian))
  (set! user-custodian parent)
  (define custodian (parameterize ([current-custodian parent]) (make-custodian)))
  (define break-parameterization (parameterize-break #t (current-break-parameterization)))
  (define (body)
    (with-handlers ([exn:break? (lambda (e) (set! caught 'break) (set! phase 'interrupted))]
                    [(lambda (_) #t)
                     (lambda (e)
                       (set! caught 'other)
                       (set! error-message (if (exn? e) (exn-message e) (format "~s" e)))
                       (set! phase 'failed))])
      (call-with-break-parameterization
       break-parameterization
       (lambda ()
         (set! body-breaks-enabled (break-enabled))
         (set! body-is-eventspace-handler
               (and gui? (eq? (current-thread) (es-thread (current-es)))))
         (set! phase 'sleep-entered)
         (semaphore-post ready)
         (sleep 120)
         (set! phase 'unexpected-normal-return))))
    (when break-sent-at
      (set! completion-ms (- (current-inexact-monotonic-milliseconds) break-sent-at)))
    (semaphore-post done))
  (cond
    [eventspace?
     (define es (parameterize ([current-custodian custodian])
                  (make-es #:suspend-to-kill? #t)))
     (set! target (es-thread es))
     (parameterize ([current-es es]) (queue body #f))]
    [else
     (set! target (parameterize ([current-custodian custodian]) (thread body)))]))
(define (interrupt!)
  (emit "before-break")
  (set! break-sent-at (current-inexact-monotonic-milliseconds))
  (break-thread target)
  (emit "after-break"))
(define (check-ready!)
  (unless (wait-bounded (semaphore-peek-evt ready) 5)
    (error 'stock-break-control "Body did not reach its sleep within 5 seconds"))
  (unless (eq? body-breaks-enabled #t)
    (error 'stock-break-control "Control body unexpectedly has breaks disabled")))
(define (check-completion!)
  (unless (wait-bounded (semaphore-peek-evt done) 20)
    (emit "interrupt-timeout")
    (error 'stock-break-control "Sleeping target did not catch the break within 20 seconds"))
  (emit "completed")
  (unless (and (eq? caught 'break) (eq? phase 'interrupted))
    (error 'stock-break-control "Target did not complete by the intended break path")))

(define status 0)
(with-handlers ([(lambda (_) #t)
                 (lambda (e)
                   (set! status 1)
                   (set! error-message (if (exn? e) (exn-message e) (format "~s" e)))
                   (emit "failed"))])
  (cond
    [nested?
     ;; Mirrors the current host workflow: a GUI callback yields while awaiting
     ;; the target and its break completion, without returning to its dispatcher.
     (on-gui (lambda () (start!) (check-ready!) (interrupt!) (check-completion!)))]
    [gui?
     ;; Control for the nested-dispatch hypothesis: the interrupt callback returns
     ;; before completion is awaited on the process's original Racket thread.
     (on-gui start!) (check-ready!) (on-gui interrupt!) (check-completion!)]
    [else (start!) (check-ready!) (interrupt!) (check-completion!)]))
(when user-custodian (custodian-shutdown-all user-custodian))
(exit status)
