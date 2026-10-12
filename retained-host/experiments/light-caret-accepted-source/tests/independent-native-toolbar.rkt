#lang racket/base
;; Run only on a permitted native GUI. This imports the actual installed widget.
;; These behavioral tests are shared unchanged by pristine, patched-stock and modern runs.
(require racket/class racket/list racket/gui/base rackunit rackunit/text-ui
         mrlib/switchable-button)

(define (with-button proc)
  (define frame (new frame% [label "Retained toolbar contract test"] [width 500] [height 140]))
  (define parent (new horizontal-panel% [parent frame]))
  (define primary (make-bitmap 36 24 #t))
  (define alternate (make-bitmap 17 15 #t))
  (define calls '())
  (define button
    (new switchable-button% [parent parent] [label "Run"]
         [bitmap primary] [alternate-bitmap alternate]
         [callback (lambda (self) (set! calls (append calls (list self))))]))
  (define (event type)
    (send button on-event (new mouse-event% [event-type type] [x 8] [y 8])))
  (dynamic-wind void
                (lambda () (proc frame button event (lambda () calls)))
                (lambda () (send frame show #f))))

(define cases
  (test-suite
   "Independent real retained toolbar contracts"
   (test-case "repeat activation retains exact widget identity"
     (with-button
      (lambda (frame b event calls)
        (for ([i (in-range 12)]) (event 'enter) (event 'left-down) (event 'left-up))
        (check-equal? (calls) (make-list 12 b)))))
   (test-case "leaving cancels, reentering restores stock mouse behavior"
     (with-button
      (lambda (frame b event calls)
        (event 'enter) (event 'left-down) (event 'leave) (event 'left-up)
        (check-equal? (calls) '())
        (event 'enter) (event 'left-down) (event 'left-up)
        (check-equal? (calls) (list b)))))
   (test-case "disable while pressed prevents dispatch and reenabling works"
     (with-button
      (lambda (frame b event calls)
        (event 'enter) (event 'left-down) (send b enable #f) (event 'left-up)
        (check-false (send b is-enabled?))
        (check-equal? (calls) '())
        (send b enable #t)
        (event 'enter) (event 'left-down) (event 'left-up)
        (check-true (send b is-enabled?))
        (check-equal? (calls) (list b)))))
   (test-case "programmatic command preserves stock unconditional semantics"
     (with-button
      (lambda (frame b event calls)
        (send b enable #f)
        (send b command)
        (check-equal? (calls) (list b)))))
   (test-case "parent hide clears hover activation state"
     (with-button
      (lambda (frame b event calls)
        (event 'enter) (event 'left-down)
        (send b on-superwindow-show #f)
        (event 'left-up)
        (check-equal? (calls) '())
        (send b on-superwindow-show #t)
        (event 'enter) (event 'left-down) (event 'left-up)
        (check-equal? (calls) (list b)))))
   (test-case "parent deactivate clears hover activation state"
     (with-button
      (lambda (frame b event calls)
        (event 'enter) (event 'left-down)
        (send b on-superwindow-activate #f)
        (event 'left-up)
        (check-equal? (calls) '())
        (event 'enter) (event 'left-down) (event 'left-up)
        (check-equal? (calls) (list b)))))
   (test-case "localized mutable labels and alternate bitmap geometry survive toggles"
     (with-button
      (lambda (frame b event calls)
        (for ([label '("Exécuter" "执行" "Выполнить" "Ausführen" "Kill")])
          (send b set-label label)
          (check-equal? (send b get-label) label)
          (check-equal? (send b get-button-label) label)
          (check-true (> (send b get-large-width) (send b get-small-width)))
          (send b set-label-visible #f)
          (check-false (send b get-label-visible))
          (check-equal? (- (send b get-small-width) (send b get-without-label-small-width)) 19)
          (check-equal? (send b min-width) (send b get-without-label-small-width))
          (send b on-paint)
          (send b set-label-visible #t)
          (check-true (send b get-label-visible))
          (check-equal? (send b min-width) (send b get-small-width))
          (send b on-paint))
        (check-equal? (calls) '()))))
   (test-case "actual canvas keeps caller DC state around modern paint"
     (with-button
      (lambda (frame b event calls)
        (send frame show #t)
        (event 'enter) (event 'left-down)
        (define dc (send b get-dc))
        (define before
          (list (send dc get-alpha) (send dc get-smoothing) (send dc get-pen)
                (send dc get-brush) (send dc get-text-foreground)))
        (send b on-paint)
        (check-equal?
         (list (send dc get-alpha) (send dc get-smoothing) (send dc get-pen)
               (send dc get-brush) (send dc get-text-foreground)) before)
        ;; Stock deliberately sets normal-control-font without restoring it.
        ;; The shared invariant excludes that documented stock difference.
        (event 'leave) (event 'left-up)
        (check-equal? (calls) '()))))))

(define (run!)
  (define failures (run-tests cases))
  (printf "OPENRACKET_NATIVE_TOOLBAR_RESULT mode=~a failures=~a\n"
          (or (getenv "OPENRACKET_UI") "modern") failures)
  (flush-output)
  (unless (zero? failures) (error 'native-toolbar "~a native test failures" failures)))
(module+ test (run!))
(module+ main (run!))
