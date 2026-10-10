#lang racket/base
;; Execute configuration and the actual patched stopping predicate without GUI.
(require racket/list racket/match racket/runtime-path rackunit)
(define-runtime-path source "../overlay/framework/private/color.rkt")
(define root
  (parameterize ([read-accept-reader #t]) (call-with-input-file source read)))
(define (find-form predicate tree)
  (cond [(predicate tree) tree]
        [(pair? tree) (or (find-form predicate (car tree))
                          (find-form predicate (cdr tree)))]
        [else #f]))
(define config
  (find-form (lambda (x) (match x [`(define openracket-experimental-color-budget-ms ,_) #t] [_ #f])) root))
(define worker
  (find-form (lambda (x) (match x [`(define/private (continue-re-tokenize . ,_) . ,_) #t] [_ #f])) root))
(define predicate
  (match worker [`(define/private ,_ (cond [,predicate #f] . ,_)) predicate]))
(define ns (make-base-namespace))
(define (budget value)
  (parameterize ([current-namespace ns])
    (eval `(let ([getenv (lambda (_) ',value)]) ,(caddr config)))))
(define (stop? allowed? control elapsed slice)
  (parameterize ([current-namespace ns])
    (eval `(let ([ok-to-stop? ,allowed?] [start-time 100.0]
                 [tokenizing-give-up-early (lambda () ',control)]
                 [current-inexact-milliseconds (lambda () ,(+ 100.0 elapsed))]
                 [openracket-experimental-color-budget-ms ,slice])
             ,predicate))))
(test-case "explicit experiment with stock default and invalid values rejected"
  (for ([value '(#f "20" "12" "8" "4")] [expected '(20.0 20.0 12.0 8.0 4.0)])
    (check-equal? (budget value) expected))
  (for ([value '("0" "-1" "NaN" "8.5" "" "40")])
    (check-exn exn:fail? (lambda () (budget value)))))
(test-case "deferred stop tests the selected threshold exactly"
  (for ([slice '(4.0 8.0 12.0 20.0)])
    (check-false (stop? #t 'defer (- slice .001) slice))
    (check-true (stop? #t 'defer slice slice))
    (check-true (stop? #t 'defer (+ slice .001) slice))))
(test-case "don't-stop path remains dominant even after arbitrarily long lexer calls"
  (for* ([control '(#t #f defer)] [slice '(4.0 8.0 12.0 20.0)])
    (check-false (stop? #f control 1000000.0 slice))))
(test-case "tool overrides retain their stock meaning"
  (for ([slice '(4.0 8.0 12.0 20.0)])
    (check-true (stop? #t #t 0.0 slice))
    (check-false (stop? #t #f 1000000.0 slice))))
