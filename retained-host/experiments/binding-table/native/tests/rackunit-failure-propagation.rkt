#lang racket/base
;; Test-only behavioral witness. Procedure identity is not a valid assertion
;; for current-check-handler, whose public parameter may wrap its values.
(require rackunit)
(provide assert-rackunit-failure-propagation!)

(define (assert-rackunit-failure-propagation!)
  ;; Use the active check policy without replacing it. Only an actual RackUnit
  ;; check exception establishes propagation; a normal return fails this guard.
  (define raised-check?
    (with-handlers ([exn:test:check? (lambda (_) #t)])
      (check-true #f "intentional RackUnit failure-propagation witness")
      #f))
  (unless raised-check?
    (error 'assert-rackunit-failure-propagation!
           "RackUnit failed check returned normally instead of raising")))
