#lang racket

;; Small programs. Clear ideas.
;; Run this buffer, then try (greet "world") below.

(define (greet name)
  (string-append "Hello, " name "."))

(define (square x)
  (* x x))

(map square '(1 2 3 4 5))
(greet "Racket")

;; Exact arithmetic stays exact.
(+ 1/3 1/6)
