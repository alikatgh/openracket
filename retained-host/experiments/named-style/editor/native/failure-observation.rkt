#lang racket/base
;; Test-local observers never substitute for a real reader result or failure.
(require json racket/class racket/list)
(provide call/preserve-failure make-observed-reader-class
         run-failure-observation-controls!)

(define (best-effort thunk)
  (with-handlers ([(lambda (_) #t) (lambda (_) (void))]) (thunk)))

(define (call/preserve-failure thunk observe-failure!)
  (with-handlers ([(lambda (_) #t)
                   (lambda (original)
                     (best-effort (lambda () (observe-failure! original)))
                     (raise original))])
    (thunk)))

(define (make-observed-reader-class base% observe!)
  (class base%
    (super-new)
    (define/private (observe-call stream arguments thunk)
      (best-effort (lambda () (observe! stream "before" arguments '())))
      (call/preserve-failure
       (lambda ()
         (call-with-values
          thunk
          (lambda results
            (best-effort (lambda () (observe! stream "returned" arguments results)))
            (apply values results))))
       (lambda (original) (observe! stream "raised" arguments original))))
    ;; Preserve each actual public reader overload and its original arity.
    ;; In particular, the real load-file path calls (stream overwrite?).
    (define/override read-from-file
      (case-lambda
        [(stream)
         (observe-call stream '() (lambda () (super read-from-file stream)))]
        [(stream argument)
         (observe-call stream (list argument)
                       (lambda () (super read-from-file stream argument)))]
        [(stream start overwrite?)
         (observe-call stream (list start overwrite?)
                       (lambda () (super read-from-file stream start overwrite?)))]))))

(define (run-failure-observation-controls!)
  ;; These are real, deterministic Racket tests when the native gate runs.
  ;; Portable source/delimiter checks do not claim to execute these controls.
  (define (check value why) (unless value (error 'reload-diagnostic-controls "~a" why)))
  (define original (gensym 'original-reader-failure))
  (define diagnostic-failure (gensym 'diagnostic-failure))
  (define called? #f)
  (check (equal? (call-with-values
                 (lambda () (call/preserve-failure
                             (lambda () (values #f 17 "unchanged"))
                             (lambda (_) (set! called? #t)))) list)
                '(#f 17 "unchanged"))
         "success values preserved")
  (check (not called?) "failure observer is absent on success")
  (define closed-output (open-output-string))
  (close-output-port closed-output)
  (define failing-observers
    (list (lambda (_) (raise diagnostic-failure))
          (lambda (_) (error 'diagnostic "injected observation failure"))
          (lambda (_) (write-json (hasheq 'malformed (lambda () (void)))
                                  (open-output-string)))
          (lambda (_) (display "injected write" closed-output))))
  (for* ([failure (in-list (list original (exn:fail "original reader exception"
                                                  (current-continuation-marks))))]
         [observer (in-list failing-observers)])
    (define caught
      (with-handlers ([(lambda (_) #t) values])
        (call/preserve-failure (lambda () (raise failure)) observer)))
    (check (eq? caught failure) "same original failure survives diagnostic/write failure"))
  (define false-base%
    (class object% (super-new) (define/public (read-from-file . args) #f)))
  (for ([observer (in-list failing-observers)])
    (define false-reader
      (new (make-observed-reader-class false-base%
                                      (lambda args (observer #f)))))
    (check (eq? (send false-reader read-from-file 'stream #t) #f)
           "false reader result survives malformed/write-failing observations"))
  (define invocation-count 0)
  (define returned-values (list #f original "unchanged"))
  (define base%
    (class object%
      (super-new)
      (define/public (read-from-file . args)
        (set! invocation-count (add1 invocation-count))
        (if (eq? (car args) original)
            (raise original)
            (apply values (cons args returned-values))))))
  (define observed%
    (make-observed-reader-class base% (lambda args (raise diagnostic-failure))))
  (define reader (new observed%))
  (define stream (gensym 'same-stream))
  (for ([args (in-list (list (list stream) (list stream #f) (list stream 3 #t)))])
    (define before invocation-count)
    (define result (call-with-values (lambda () (send/apply reader read-from-file args)) list))
    (check (= invocation-count (add1 before)) "super reader called exactly once")
    (check (and (equal? (car result) args) (eq? (caar result) stream)
                (equal? (cdr result) returned-values)) "actual arguments and values preserved"))
  (define before invocation-count)
  (define caught
    (with-handlers ([(lambda (_) #t) values]) (send reader read-from-file original #t)))
  (check (and (eq? caught original) (= invocation-count (add1 before)))
         "reader failure identity survives failing before/raised observers")
  (void))
