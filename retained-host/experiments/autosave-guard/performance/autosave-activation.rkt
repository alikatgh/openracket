#lang racket/base
(provide verify-autosave-activation)
(define (verify-autosave-activation expected #:lookup [lookup dynamic-require]
                                    #:environment [environment getenv])
  (define flag (environment "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD"))
  (cond
    [(equal? expected "none") (hasheq 'status "not-requested" 'environment_flag (or flag "unset"))]
    [else
     (define selected
       (lookup 'framework/private/text-misc 'openracket-experimental-save-scan-guard?
               (lambda () 'absent)))
     (define pass?
       (cond [(equal? expected "stock") (and (not flag) (eq? selected 'absent))]
             [(equal? expected "candidate") (and (equal? flag "1") (eq? selected #t))]
             [else (error 'autosave-activation "unknown expectation ~s" expected)]))
     (unless pass?
       (error 'autosave-activation "expected ~s; environment ~s; loaded export ~s"
              expected flag selected))
     (hasheq 'status "verified" 'expected expected 'environment_flag (or flag "unset")
             'export_present (not (eq? selected 'absent)) 'selected (eq? selected #t))]))
