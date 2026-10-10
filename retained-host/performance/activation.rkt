#lang racket/base
;; Read-only assertion of the independently installed scan candidate.
(provide verify-scan-activation)
(define helper 'drracket/private/openracket-all-string-snips)
(define (verify-scan-activation expectation #:lookup [lookup dynamic-require]
                                #:environment [environment getenv])
  (define flag (environment "OPENRACKET_ALL_STRING_FAST_PATH"))
  (cond
    [(equal? expectation "none") (hasheq 'status "not-requested" 'environment_flag (or flag "unset"))]
    [else
     (define selected
       (with-handlers ([exn:fail:filesystem:missing-module?
                        (lambda (e)
                          ;; A missing dependency inside an installed helper is
                          ;; not evidence that the requested helper is absent.
                          (if (equal? (exn:fail:filesystem:missing-module-path e) helper)
                              'absent (raise e)))])
         (lookup helper 'openracket-fast-path-selected?)))
     (define pass?
       (cond [(equal? expectation "stock") (and (not flag) (eq? selected 'absent))]
             [(equal? expectation "candidate") (and (equal? flag "1") (eq? selected #t))]
             [else (error 'scan-activation "unexpected verification mode: ~s" expectation)]))
     (unless pass?
       (error 'scan-activation "expected ~a; environment flag ~s; helper selection ~s"
              expectation flag selected))
     (hasheq 'status "verified" 'expected expectation
             'environment_flag (or flag "unset")
             'module_present (not (eq? selected 'absent))
             'selected (eq? selected #t))]))
