#lang racket/base
;; Validate the native harness's actual fixture without executing GUI imports.
(require racket/match racket/runtime-path rackunit)
(define-runtime-path source "native-lexer-equivalence.rkt")
(define data (parameterize ([read-accept-reader #t]) (call-with-input-file source read)))
(match-define `(module ,_ ,_ (#%module-begin ,forms ...)) data)
(define form
  (for/first ([form forms] #:when (match form [`(define fixture-text ,_) #t] [_ #f])) form))
(define text (eval (caddr form) (make-base-namespace)))
(check-true (> (bytes-length (string->bytes/utf-8 text)) (string-length text)))
(check-not-false (regexp-match? #rx"λ 世界 🌿" text))
(check-not-exn
 (lambda ()
   (parameterize ([read-accept-reader #t] [current-namespace (make-base-namespace)])
     (compile (read-syntax 'fixture (open-input-string text))))))
