#lang racket/base
;; Pure evidence validator shared by the real light host and headless refusals.
(require rackunit racket/list racket/runtime-path json)
(provide expected-light-state validate-light-state!)
(define-runtime-path expected-path "native-light-state-expected.json")
(define expected-light-state (call-with-input-file expected-path read-json))
(define (canonical value)
  ;; JSON readers use hasheq; callers may have ordinary symbol-key hashes.
  ;; Normalize only hash comparison kind, recursively, never field values/types.
  (cond [(hash? value) (for/hasheq ([(key item) (in-hash value)])
                        (values key (canonical item)))]
        [(list? value) (map canonical value)]
        [else value]))
(define (validate-light-state! observed)
  ;; A missing #f-valued key must fail; never use a #f fallback as evidence.
  (parameterize ([current-check-handler raise])
    (check-true (hash? observed) "Light-state observation must be a hash")
    (check-true (andmap symbol? (hash-keys observed)) "Symbol-key light state required")
    (check-equal? (sort (hash-keys observed) symbol<?)
                  (sort (hash-keys expected-light-state) symbol<?)
                  "Complete exact light-state evidence keys")
    (for ([key (in-list (sort (hash-keys expected-light-state) symbol<?))])
      (check-equal? (canonical (hash-ref observed key)) (canonical (hash-ref expected-light-state key))
                    (format "Actual light state: ~a" key))))
  observed)
