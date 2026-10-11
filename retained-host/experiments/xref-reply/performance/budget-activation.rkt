#lang racket/base
;; Read the actual already-loaded color module's immutable experimental budget.
(provide verify-budget-activation)
(define (verify-budget-activation expected #:lookup [lookup dynamic-require]
                                  #:environment [environment getenv])
  (define flag (environment "OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"))
  (cond
    [(equal? expected "none")
     (hasheq 'status "not-requested" 'environment_flag (or flag "unset"))]
    [else
     (define selected
       (lookup 'framework/private/color 'openracket-experimental-color-budget-ms
               (lambda () 'absent)))
     (define pass?
       (cond [(equal? expected "stock") (and (not flag) (eq? selected 'absent))]
             [(member expected '("4" "8" "12" "20"))
              (and (equal? flag expected) (number? selected)
                   (= selected (string->number expected)))]
             [else (error 'budget-activation "unknown expectation: ~s" expected)]))
     (unless pass?
       (error 'budget-activation "expected ~s; environment ~s; loaded color budget ~s"
              expected flag selected))
     (hasheq 'status "verified" 'expected expected
             'environment_flag (or flag "unset")
             'export_present (not (eq? selected 'absent))
             'loaded_budget_ms (if (eq? selected 'absent) 'null selected))]))
