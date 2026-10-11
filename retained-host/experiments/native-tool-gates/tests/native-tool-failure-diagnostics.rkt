#lang racket/base
;; Diagnostic data only. Never handles, replaces, or certifies a failed check.
(require racket/list rackunit
         (only-in rackunit/private/check-info pretty-info? pretty-info-value))
(provide failure->diagnostic report-failure!)

;; Output/capture is best effort. A reporter can even raise a non-exception;
;; neither case may replace the original failure owned by its caller.
(define (report-failure! failure reporter)
  (with-handlers ([(lambda (_) #t) (lambda (_) (void))])
    (reporter failure)
    (void)))

(define (bounded-write value)
  (define text (format "~s" value))
  (substring text 0 (min 2000 (string-length text))))

(define (failure->diagnostic failure)
  (hash 'exception_type (cond [(exn:test:check? failure) "exn:test:check"]
                             [(exn:fail? failure) "exn:fail"]
                             [(exn? failure) "exn"]
                             [else "raised-value"])
        ;; RackUnit's exn-message can be empty; the typed stack is authoritative.
        'check_info
        (if (exn:test:check? failure)
            (for/list ([info (in-list (take (exn:test:check-stack failure)
                                           (min 64 (length (exn:test:check-stack failure)))))])
              (define raw (check-info-value info))
              (hash 'name (format "~a" (check-info-name info))
                    'pretty_info (pretty-info? raw)
                    'value (bounded-write (if (pretty-info? raw)
                                             (pretty-info-value raw) raw))))
            '())))
