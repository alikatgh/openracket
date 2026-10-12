#lang racket/base
;; One bounded, read-only reproduction of the old launch-argument mistake.
;; Logs actual native windows. Never clicks or dismisses a dialog.
(require racket/class racket/list racket/format json)
(define args (current-command-line-arguments))
(unless (= (vector-length args) 5)
  (error 'diagnose-startup "expected legacy FIXTURE OUTPUT MODE EDIT-POS SIZE arguments"))
(define output (vector-ref args 1))
;; The original benchmark output existed before GUI startup; replicate that fact.
(call-with-output-file output #:exists 'truncate/replace
  (lambda (port) (display "{}\n" port)))
(define queue-callback (dynamic-require 'racket/gui/base 'queue-callback))
(define gui-yield (dynamic-require 'racket/gui/base 'yield))
(define get-top-level-windows (dynamic-require 'racket/gui/base 'get-top-level-windows))
(define dialog% (dynamic-require 'racket/gui/base 'dialog%))
(define start (current-inexact-monotonic-milliseconds))
(define (safe thunk) (with-handlers ([exn:fail? (lambda (e) (exn-message e))]) (thunk)))
(define (short-text text)
  (if (string? text) (substring text 0 (min 2048 (string-length text))) (~s text)))
(define (describe widget [depth 0])
  (hasheq
   'class (~a (object-name widget))
   'label (if (object-method-arity-includes? widget 'get-label 0)
              (safe (lambda () (short-text (send widget get-label)))) "")
   'editor_text
   (if (object-method-arity-includes? widget 'get-editor 0)
       (safe (lambda ()
               (define editor (send widget get-editor))
               (if (and editor (object-method-arity-includes? editor 'get-text 0))
                   (short-text (send editor get-text)) ""))) "")
   'children
   (if (and (< depth 8) (object-method-arity-includes? widget 'get-children 0))
       (safe (lambda () (for/list ([child (in-list (send widget get-children))])
                         (describe child (add1 depth))))) null)))
(define (inspect!)
  (define shown (filter (lambda (w) (send w is-shown?)) (get-top-level-windows)))
  (define found? (ormap (lambda (w) (is-a? w dialog%)) shown))
  (define elapsed (- (current-inexact-monotonic-milliseconds) start))
  (when (or found? (> elapsed 10000))
    (define report (hasheq 'measurement_kind "startup_diagnostic_only"
                           'observed_dialog found?
                           'elapsed_ms elapsed
                           'current_argv (vector->list (current-command-line-arguments))
                           'shown_windows (map describe shown)))
    (call-with-output-file output #:exists 'truncate/replace
      (lambda (port) (write-json report port) (newline port)))
    (displayln "OPENRACKET_STARTUP_DIAGNOSTIC_JSON_BEGIN")
    (write-json report) (newline)
    (displayln "OPENRACKET_STARTUP_DIAGNOSTIC_JSON_END")
    (flush-output)
    (exit 0)))
(thread (lambda () (let loop () (sleep .5) (queue-callback inspect! #t) (loop))))
(queue-callback
 (lambda ()
   ;; Intentionally preserve the old temporary parameterization only in this
   ;; diagnostic, so the stock callback's actual live argv/dialog can be observed.
   (parameterize ([current-command-line-arguments #()])
     (dynamic-require 'drracket/drracket #f))) #f)
(gui-yield (make-semaphore))
