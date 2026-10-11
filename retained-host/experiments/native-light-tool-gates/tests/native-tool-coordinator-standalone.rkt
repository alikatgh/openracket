#lang racket/base
;; Direct driver: raco test counts even the two intentionally caught failures
;; on the separate handler thread. Keep that original regression unchanged.
(require rackunit racket/runtime-path
         ;; Racket 9.3 wraps actual/expected check-info values in pretty-info.
         (only-in rackunit/private/check-info pretty-info? pretty-info-value))
(define-runtime-path regression "native-tool-coordinator-test.rkt")
(define arguments (current-command-line-arguments))
(unless (or (equal? arguments #())
            (equal? arguments #("--inject-outer-failure")))
  (error 'native-tool-coordinator-standalone "unsupported arguments"))
(parameterize ([current-check-handler raise])
  (dynamic-require `(submod ,regression test) #f)
  ;; The supervisor must observe nonzero/no success marker for this negative
  ;; control. It verifies that unexpected outer failures are not swallowed.
  (when (equal? arguments #("--inject-outer-failure"))
    (displayln "OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE")
    (flush-output)
    ;; Only the injected check is caught. The real regression above is outside
    ;; this handler, and the original exception is always re-raised below.
    (with-handlers
        ([exn:test:check?
          (lambda (failure)
            ;; Diagnostic errors must not replace the original check failure.
            ;; This catch covers only inspection/output, never any real check.
            (with-handlers ([(lambda (_) #t) void])
              (define infos (exn:test:check-stack failure))
              (define (unique-info-value key)
                (define matches
                  (for/list ([info (in-list infos)]
                             #:when (eq? (check-info-name info) key))
                    (check-info-value info)))
                (and (= (length matches) 1) (car matches)))
              (define name (unique-info-value 'name))
              (define actual (unique-info-value 'actual))
              (define expected (unique-info-value 'expected))
              ;; Do not certify arbitrary exceptions, missing/duplicate fields,
              ;; changed wrappers, or any values other than this exact failure.
              (when (and (eq? name 'check-equal?)
                         (pretty-info? actual)
                         (pretty-info? expected)
                         (eq? (pretty-info-value actual) 'actual)
                         (eq? (pretty-info-value expected) 'deliberately-wrong))
                (printf "OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE exception=exn:test:check check=~s actual=~s expected=~s\n"
                        name (pretty-info-value actual) (pretty-info-value expected))
                (flush-output)))
            (raise failure))])
      (check-equal? 'actual 'deliberately-wrong))))
(displayln "OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete")
(exit 0)
