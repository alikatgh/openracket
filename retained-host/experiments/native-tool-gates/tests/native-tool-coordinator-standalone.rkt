#lang racket/base
;; Direct driver: raco test counts even the two intentionally caught failures
;; on the separate handler thread. Keep that original regression unchanged.
(require rackunit racket/runtime-path)
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
    (check-equal? 'actual 'deliberately-wrong)))
(displayln "OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete")
(exit 0)
