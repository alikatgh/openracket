#lang racket/base
;; Requires a legitimate native GUI display. This test has NOT run here.
;; It exercises the real retained switchable-button% class, not a model/fake widget.
(require racket/class racket/gui/base rackunit mrlib/switchable-button)
(define f (new frame% [label "OpenRacket native toolbar regression"]))
(define p (new horizontal-panel% [parent f]))
(define bm (make-bitmap 24 24 #t))
(define calls '())
(define b
  (new switchable-button% [parent p] [label "Run"] [bitmap bm]
       [callback (lambda (button) (set! calls (cons button calls)))]))
(define (event type) (send b on-event (new mouse-event% [event-type type] [x 8] [y 8])))
(test-case "mouse activation calls original callback with same host object"
  (event 'enter) (event 'left-down) (event 'left-up)
  (check-equal? calls (list b)))
(test-case "disabled mouse activation remains suppressed"
  (send b enable #f) (event 'enter) (event 'left-down) (event 'left-up)
  (check-equal? calls (list b)))
(test-case "command retains stock unconditional callback semantics"
  (send b command) (check-equal? calls (list b b)))
(test-case "reenable and leaving cancel activation"
  (send b enable #t) (event 'enter) (event 'left-down) (event 'leave) (event 'left-up)
  (check-equal? calls (list b b)))
(test-case "labels retain stock setters and compact size protocol"
  (send b set-label "Kill")
  (check-equal? (send b get-label) "Kill")
  (check-equal? (send b get-button-label) "Kill")
  (send b set-label-visible #f) (check-false (send b get-label-visible))
  (send b set-label-visible #t) (check-true (send b get-label-visible))
  (check-true (> (send b get-large-width) (send b get-small-width)))
  (check-true (positive? (send b get-without-label-small-width))))
(test-case "real canvas painting succeeds"
  (send b on-paint))
(send f show #f)
