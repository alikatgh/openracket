#lang racket/base
;; Headless check of the actual coordinator wrapper, using a separate handler
;; thread. This is an orchestration test, never evidence of native GUI behavior.
(require rackunit racket/async-channel "native-tool-coordinator.rkt")

(module+ test
  (define requests (make-async-channel))
  (define handler
    (thread
     (lambda ()
       ;; Deliberately non-raising ambient RackUnit handler, as on a GUI handler.
       (parameterize ([current-check-handler (lambda (_) (void))])
         (let loop ()
           (define message (async-channel-get requests))
           (unless (eq? message 'stop)
             (define thunk (car message))
             (define reply (cdr message))
             (async-channel-put
              reply
              (with-handlers ([(lambda (_) #t) (lambda (e) (cons 'error e))])
                (cons 'value (thunk))))
             (loop)))))))
  (define callback-active? #f)
  (define (on-handler thunk)
    (define reply (make-async-channel))
    (async-channel-put requests
                       (cons (lambda ()
                               (dynamic-wind
                                 (lambda () (set! callback-active? #t))
                                 thunk
                                 (lambda () (set! callback-active? #f))))
                             reply))
    (define result (sync/timeout 2 reply))
    (unless result (error 'test "Handler timed out"))
    (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))
  (define last-timeout #f)
  (define (fake-wait description predicate seconds)
    (set! last-timeout seconds)
    (check-false callback-active? "Action callback returned before polling")
    (on-handler predicate))
  (define-values (gui await)
    (make-checked-coordinator on-handler fake-wait handler))
  (dynamic-wind
    void
    (lambda ()
      (check-eq? (gui current-thread) handler)
      (check-exn exn:fail? (lambda () (gui (lambda () (check-equal? 1 2)))))
      (check-exn exn:fail?
                 (lambda () (await "failing check" (lambda () (check-true #f)))))
      (check-exn #rx"predicate failure"
                 (lambda () (await "broken predicate"
                                   (lambda () (error "predicate failure")))))
      (check-eq? (gui (lambda () 'action-returned)) 'action-returned)
      (check-eq? (await "after action" (lambda () 'ready) 20) 'ready)
      (check-equal? last-timeout 20)
      (define-values (wrong-gui wrong-await)
        (make-checked-coordinator (lambda (f) (f)) fake-wait handler))
      (check-exn #rx"actual GUI handler" (lambda () (wrong-gui void))))
    (lambda () (async-channel-put requests 'stop) (thread-wait handler))))
