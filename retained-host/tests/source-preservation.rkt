#lang racket/base
(require rackunit racket/list racket/match racket/port racket/runtime-path)
(define-runtime-path root "..")
(define (load-datum p)
  (parameterize ([read-accept-reader #t])
    (call-with-input-file (build-path root p) read)))
(define before (load-datum "vendor/switchable-button-v9.3.rkt"))
(define after (load-datum "overlay/mrlib/switchable-button.rkt"))
(define (class-body module)
  (match module [`(module ,_ ,_ (#%module-begin ,forms ...))
                (match (findf (lambda (f) (and (pair? f) (equal? (take f (min 2 (length f)))
                                                                '(define switchable-button%)))) forms)
                  [`(define switchable-button% (class canvas% ,body ...)) body])]))
(define (method-name x)
  (match x [`(,(or 'define/private 'define/public 'define/override) (,name ,_ ...) ,_ ...) name] [_ #f]))
(define old-body (class-body before))
(define new-body (class-body after))
(define (methods body)
  (for/hash ([x body] #:when (method-name x)) (values (method-name x) x)))
(define old-methods (methods old-body))
(define new-methods (methods new-body))
(define allowed '(on-paint update-sizes get-large-width))
(for ([(name source) old-methods] #:unless (memq name allowed))
  (test-case (format "retained stock method: ~a" name)
    (check-equal? source (hash-ref new-methods name))))
(test-case "all stock on-paint instructions retained as fallback"
  (define old (hash-ref old-methods 'on-paint))
  (define kept (hash-ref new-methods 'paint-stock-button))
  (check-equal? (cddr old) (cddr kept)))
(test-case "same public class, no replacement class or callback wrapper"
  (check-equal? (filter (lambda (f) (not (method-name f))) old-body)
                (filter (lambda (f) (not (method-name f))) new-body)))
(define (normalize-measurement v)
  (cond [(equal? v '(modern-control-font normal-control-font)) 'normal-control-font]
        [(pair? v) (map normalize-measurement v)] [else v]))
(for ([name '(update-sizes get-large-width)])
  (test-case (format "only font measurement changed: ~a" name)
    (check-equal? (hash-ref old-methods name)
                  (normalize-measurement (hash-ref new-methods name)))))
(test-case "no extra public behavior methods"
  (check-equal? (sort (hash-keys new-methods) symbol<?)
                (sort (cons 'paint-stock-button (hash-keys old-methods)) symbol<?)))
(printf "Verified ~a original methods; only ~a are permitted presentation changes.\n"
        (hash-count old-methods) allowed)
(test-case "entire module differs only at the declared presentation seams"
  (define (normalize v)
    (cond
      [(equal? v (hash-ref new-methods 'on-paint)) (hash-ref old-methods 'on-paint)]
      [(equal? v '(modern-control-font normal-control-font)) 'normal-control-font]
      [(equal? v '(define gap (if (modern-ui?) 6 4))) '(define gap 4)]
      [(equal? v '(define margin (if (modern-ui?) 4 2))) '(define margin 2)]
      [(equal? v '(define w-circle-space (if (modern-ui?) 10 6))) '(define w-circle-space 6)]
      [(equal? v '(define h-circle-space (if (modern-ui?) 8 6))) '(define h-circle-space 6)]
      [(pair? v)
       (map normalize
            (filter (lambda (x)
                      (and (not (equal? x "private/openracket-paint.rkt"))
                           (not (equal? (method-name x) 'paint-stock-button)))) v))]
      [else v]))
  ;; Filename-derived module name is not relevant to the body.
  (check-equal? (cddr before) (cddr (normalize after))))
