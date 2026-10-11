#lang racket/base
;; Standalone native regression: run with `racket`, not as a successful-check
;; count. Intentional failed checks are the test input. No window is created.
(require racket/gui/base rackunit "rackunit-failure-propagation.rkt")

(define (require! value message)
  (unless value (error 'rackunit-failure-propagation-test "~a" message)))

(define caller (current-thread))
(define custodian (make-custodian))
(define result-channel (make-channel))
(define ambient-failures 0)
(define (nonraising-ambient-handler _)
  (set! ambient-failures (add1 ambient-failures))
  (void))
(define space
  (parameterize ([current-custodian custodian]
                 [current-check-handler nonraising-ambient-handler])
    (make-eventspace)))

(parameterize ([current-eventspace space])
  (queue-callback
   (lambda ()
     (with-handlers ([exn? (lambda (e) (channel-put result-channel e))])
       (require! (and (eq? (current-thread) (eventspace-handler-thread space))
                      (not (eq? (current-thread) caller)))
                 "regression must execute on the separate GUI handler")
       ;; The separate eventspace inherits a deliberately nonraising ambient
       ;; policy. Establish that behavior without comparing procedure identity.
       (check-true #f "intentional nonraising ambient control")
       (require! (= ambient-failures 1) "ambient policy must handle and return")
       (define rejected-nonraising?
         (with-handlers
             ([exn:fail?
               (lambda (e)
                 (and (not (exn:test:check? e))
                      (regexp-match? #rx"RackUnit failed check returned normally instead of raising"
                                     (exn-message e))))])
           (assert-rackunit-failure-propagation!)
           #f))
       (require! rejected-nonraising? "exact production witness must reject nonraising policy")
       (require! (= ambient-failures 2) "negative control must exercise actual failed check")
       (define reached-after-failure? #f)
       (define observed-check-failure?
         (with-handlers ([exn:test:check? (lambda (_) #t)])
           ;; Same actual-handler parameterization as the docs postflight.
           (parameterize ([current-check-handler raise])
             (assert-rackunit-failure-propagation!)
             (check-true #f "intentional protected continuation failure")
             (set! reached-after-failure? #t))
           #f))
       (require! observed-check-failure? "protected failed check must escape as exn:test:check")
       (require! (not reached-after-failure?) "code after protected failed check must be unreachable")
       (require! (= ambient-failures 2) "protected checks must not reach ambient handler")
       (check-true #f "intentional restored ambient control")
       (require! (= ambient-failures 3) "nonraising ambient policy must be restored")
       (channel-put result-channel 'passed)))
   #f))

(define result (sync/timeout 10 result-channel))
(custodian-shutdown-all custodian)
(require! result "separate handler regression timed out after 10 seconds")
(when (exn? result) (raise result))
(require! (eq? result 'passed) "unexpected regression result")
(displayln "OPENRACKET_RACKUNIT_PROPAGATION_OK separate-handler nonraising-ambient rejected-return escaped-failure")
(flush-output)
;; The standalone native caller owns process termination after its eventspace
;; has been shut down and every behavioral assertion has completed.
(exit 0)
