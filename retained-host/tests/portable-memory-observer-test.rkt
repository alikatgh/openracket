#lang racket/base
;; Execute the memory observer's actual parsed functions with an explicit fake
;; preference reader. These GUI-free contracts are not native-launch evidence.
(require json racket/list racket/match racket/runtime-path rackunit)
(define-runtime-path source "portable-observer/tool.rkt")
(define tree (parameterize ([read-accept-reader #t]) (call-with-input-file source read)))
(define (find-form x pred)
  (cond [(pred x) x]
        [(pair? x) (or (find-form (car x) pred) (find-form (cdr x) pred))]
        [else #f]))
(define (definition name)
  (or (find-form tree (lambda (x) (match x [`(define (,n ,_ ...) ,_ ...) (eq? n name)] [_ #f])))
      (error 'memory-observer-test "Missing actual observer definition: ~a" name)))
(define (in ns x) (parameterize ([current-namespace ns]) (eval x)))
(define (observer-namespace actual)
  (define ns (make-base-namespace))
  (in ns `(define actual ',actual))
  (in ns '(define reads '()))
  (in ns '(define assertions 0))
  (in ns '(define (preferences:get key)
            (set! reads (cons key reads))
            (unless (eq? key 'drracket:child-only-memory-limit)
              (error 'mock-preferences "Unregistered preference: ~s" key))
            actual))
  (in ns '(define (assert! value message)
            (unless value (error 'memory-assertion "~a" message))
            (set! assertions (add1 assertions))))
  (for ([name '(parse-expected-memory-limit memory-limit-evidence assert-memory-limit! json-safe)])
    (in ns (definition name)))
  ns)

(test-case "strict decimal MiB expectations preserve exact bytes"
  (define ns (observer-namespace #f))
  (for ([value '("8" "128" "256" "512" "2048" "0008" "9007199254740993")]
        [mib '(8 128 256 512 2048 8 9007199254740993)])
    (define parsed (in ns `(parse-expected-memory-limit ,value)))
    (check-equal? parsed (* mib 1024 1024))
    (check-true (exact-integer? parsed)))
  (check-equal? (in ns 'reads) '()))

(test-case "unlimited is false but missing and malformed expectations fail closed"
  (define ns (observer-namespace #f))
  (check-false (in ns '(parse-expected-memory-limit "unlimited")))
  (for ([value '(#f "" "0" "7" "-128" "+128" "128.0" "128e0" "128/1"
                "#e128" "#x80" " 128" "128 " "128\n" "\t128" "１２８"
                "UNLIMITED" " unlimited" "unlimited\n" "#f" "false" "default")])
    (check-exn #rx"OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB"
               (lambda () (in ns `(parse-expected-memory-limit ,value)))))
  (check-equal? (in ns 'reads) '()))

(test-case "each inspection reads the original registered preference exactly once"
  (for ([value (list #f (* 8 1024 1024) (* 128 1024 1024)
                     (* 256 1024 1024) (* 384 1024 1024))])
    (define ns (observer-namespace value))
    (define report (in ns `(memory-limit-evidence ,value)))
    (check-equal? (in ns 'reads) '(drracket:child-only-memory-limit))
    (check-equal? (hash-ref report 'preference_key) "drracket:child-only-memory-limit")
    (check-equal? (hash-ref report 'expected_bytes) value)
    (check-equal? (hash-ref report 'effective_bytes) value)
    (check-false (hash-ref report 'worker_cap_measured))
    (in ns `(assert-memory-limit! ',report assert!))
    (check-equal? (in ns 'assertions) 2)
    (check-equal? (in ns 'reads) '(drracket:child-only-memory-limit))))

(test-case "wrong registered values and unlimited mismatches cannot pass readiness"
  (for ([actual (list (* 128 1024 1024) (* 256 1024 1024) #f)]
        [expected (list (* 256 1024 1024) #f (* 128 1024 1024))])
    (define ns (observer-namespace actual))
    (in ns `(define evidence (memory-limit-evidence ,expected)))
    (check-exn #rx"expected .*observed"
               (lambda () (in ns '(assert-memory-limit! evidence assert!))))
    (check-equal? (in ns '(hash-ref evidence 'effective_bytes)) actual)))

(test-case "preference value types are never coerced or silently repaired"
  (for ([actual (list 0 (* 7 1024 1024) 268435456.0 "268435456" #t 'unlimited)])
    (define ns (observer-namespace actual))
    (in ns '(define evidence (memory-limit-evidence (* 256 1024 1024))))
    (check-exn #rx"must be #f or exact bytes"
               (lambda () (in ns '(assert-memory-limit! evidence assert!))))
    (check-equal? (in ns '(hash-ref evidence 'effective_bytes)) actual)))

(test-case "missing registration fails without registering a fallback preference"
  (define ns (observer-namespace #f))
  (in ns '(set! preferences:get
                (lambda (key) (error 'mock-preferences "Unregistered preference: ~s" key))))
  (check-exn #rx"Unregistered preference: drracket:child-only-memory-limit"
             (lambda () (in ns '(memory-limit-evidence (* 256 1024 1024))))))

(test-case "memory evidence survives JSON roundtrip with exact integers and false"
  (for ([actual (list #f (* 128 1024 1024) (* 256 1024 1024))])
    (define ns (observer-namespace actual))
    (define report (in ns `(json-safe (memory-limit-evidence ,actual))))
    (define roundtrip (string->jsexpr (jsexpr->string report)))
    (check-equal? roundtrip report)
    (check-equal? (hash-ref roundtrip 'effective_bytes) actual)
    (check-equal? (hash-ref roundtrip 'expected_bytes) actual)
    (check-false (hash-ref roundtrip 'worker_cap_measured))))

(test-case "expectation is configured before the timer and independently of launcher input"
  (define startup (definition 'start-observer!))
  (define expected-form
    '(set! expected-memory-limit
           (parse-expected-memory-limit (getenv "OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB"))))
  (check-not-false (find-form startup (lambda (x) (equal? x expected-form))))
  (define configuration
    (find-form startup
               (lambda (x)
                 (and (pair? x) (eq? (car x) 'with-handlers)
                      (member expected-form (cddr x))))))
  (check-not-false configuration)
  (define timer-form '(set! timer (new timer% [notify-callback tick] [interval 100])))
  (define forms (cddr configuration))
  (check-true (< (index-of forms expected-form) (index-of forms timer-form)))
  (check-false (find-form (definition 'memory-limit-evidence) (lambda (x) (eq? x 'getenv))))
  (check-false (find-form (definition 'memory-limit-evidence) (lambda (x) (eq? x 'preferences:set))))
  (check-false (find-form (definition 'memory-limit-evidence) (lambda (x) (eq? x 'preferences:set-default)))))
