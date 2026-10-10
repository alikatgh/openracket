#lang racket/base
;; Headless tests of caller orchestration helpers, parsed from the actual caller.
;; These do not load/expand native GUI modules or validate native bindings.
(require racket/list racket/match racket/runtime-path rackunit rackunit/text-ui)
(define-runtime-path caller "portable-native-save-host.rkt")
(define root (parameterize ([read-accept-reader #t]) (call-with-input-file caller read)))
(define (find-form tree pred)
  (cond [(pred tree) tree]
        [(pair? tree) (or (find-form (car tree) pred) (find-form (cdr tree) pred))]
        [else #f]))
(define (function name)
  (find-form root (lambda (f) (match f [`(define (,n ,_ ...) ,_ ...) (eq? n name)] [_ #f]))))
(define ns (make-base-namespace))
(define dispatches (box 0))
(define (dispatch thunk priority)
  (set-box! dispatches (add1 (unbox dispatches)))
  (thread thunk)
  (void))
(define on-gui
  (parameterize ([current-namespace ns])
    (namespace-set-variable-value! 'queue-callback dispatch #t)
    (namespace-set-variable-value! 'yield sync #t)
    (eval (function 'on-gui))
    (eval 'on-gui)))
(define wait-for
  (parameterize ([current-namespace ns])
    (eval (function 'wait-for))
    (eval 'wait-for)))
(define tests
  (test-suite
   "Independent native caller headless orchestration contracts"
   (test-case "GUI dispatch returns values and propagates actual exceptions"
     (check-equal? (on-gui (lambda () '(real result)) 1) '(real result))
     (check-exn #rx"specific injected failure" (lambda ()
                                             (on-gui (lambda () (error 'thunk "specific injected failure")) 1)))
     (check-exn (lambda (e) (equal? e 'custom-raised-value))
                (lambda () (on-gui (lambda () (raise 'custom-raised-value)) 1))))
   (test-case "GUI dispatch is bounded even if its callback is not responsive"
     (define forever (make-semaphore))
     (define cust (make-custodian))
     (dynamic-wind
       void
       (lambda ()
         (parameterize ([current-custodian cust])
           (check-exn #rx"GUI callback timed out"
                      (lambda () (on-gui (lambda () (sync forever)) .01)))))
       (lambda () (custodian-shutdown-all cust))))
   (test-case "stock frame polling has a success and terminal timeout path"
     (define attempts 0)
     (check-equal? (wait-for "test frame" (lambda ()
                                          (set! attempts (add1 attempts))
                                          (and (= attempts 3) 'actual-frame)) 1)
                   'actual-frame)
     (check-exn #rx"Timed out: absent frame"
                (lambda () (wait-for "absent frame" (lambda () #f) .01))))
   (test-case "stock startup clears arguments and no preference-setting code exists"
     (match root
       [`(module ,_ ,_ (#%module-begin ,forms ...))
        (define arg-pos (index-of forms '(current-command-line-arguments #())))
        (check-not-false arg-pos)
        (define launch
          (find-form root (lambda (f) (match f [`(lambda () (current-command-line-arguments #()) ,_ ...
                                                         (dynamic-require 'drracket/drracket #f)) #t] [_ #f]))))
        (check-not-false launch)])
     (check-false (find-form root (lambda (f) (eq? f 'preferences:set)))))))
(module+ main (exit (if (zero? (run-tests tests)) 0 1)))
(module+ test
  (define failures (run-tests tests))
  (unless (zero? failures) (error 'native-caller-contract "~a failures" failures)))
