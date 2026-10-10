#lang racket/base
(require rackunit "activation.rkt")
(define helper 'drracket/private/openracket-all-string-snips)
(define (missing module symbol)
  (raise (exn:fail:filesystem:missing-module "missing" (current-continuation-marks) helper)))
(check-equal? (verify-scan-activation "stock" #:lookup missing #:environment (lambda (_) #f))
              (hasheq 'status "verified" 'expected "stock" 'environment_flag "unset"
                      'module_present #f 'selected #f))
(check-true (hash-ref (verify-scan-activation "candidate" #:lookup (lambda _ #t)
                                            #:environment (lambda (_) "1")) 'selected))
(check-exn exn:fail? (lambda () (verify-scan-activation "candidate" #:lookup missing
                                                      #:environment (lambda (_) "1"))))
(check-exn exn:fail? (lambda () (verify-scan-activation "stock" #:lookup (lambda _ #f)
                                                      #:environment (lambda (_) #f))))
(check-exn exn:fail? (lambda () (verify-scan-activation "candidate" #:lookup (lambda _ #t)
                                                      #:environment (lambda (_) #f))))
(check-exn exn:fail:filesystem:missing-module?
           (lambda () (verify-scan-activation "stock" #:environment (lambda (_) #f)
                       #:lookup (lambda _ (raise (exn:fail:filesystem:missing-module
                                                  "dependency missing" (current-continuation-marks)
                                                  'other/dependency))))))
