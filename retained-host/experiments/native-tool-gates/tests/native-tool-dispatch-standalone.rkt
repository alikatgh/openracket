#lang racket/base
;; Headless orchestration regression, never evidence of native GUI behavior.
;; The original thread is the handler, as when racket/gui/base is first loaded.
(require rackunit racket/async-channel
         (only-in rackunit/private/check-info pretty-info? pretty-info-value)
         "native-tool-coordinator.rkt" "native-tool-dispatch.rkt")

(define arguments (current-command-line-arguments))
(unless (or (equal? arguments #())
            (equal? arguments #("--inject-wrong-result")))
  (error 'native-tool-dispatch-test "Unsupported arguments"))
(define handler (current-thread))
(define requests (make-async-channel))
(define context (make-parameter 'outside))
(define callback-active? #f)
(define handler-failure #f)
(define coordinator #f)
(define last-timeout #f)

(define (on-handler thunk)
  (define reply (make-async-channel))
  (async-channel-put requests (cons thunk reply))
  (define response (sync reply))
  (if (eq? (car response) 'error) (raise (cdr response)) (cdr response)))
(define (pump-until-dead finished)
  (check-eq? (current-thread) handler)
  (let loop ()
    (sync
     (handle-evt finished void)
     (handle-evt
      requests
      (lambda (request)
        (define response
          (with-handlers ([(lambda (_) #t)
                           (lambda (failure)
                             (set! handler-failure failure)
                             (cons 'error failure))])
            (cons 'value
                  (dynamic-wind
                    (lambda () (set! callback-active? #t))
                    (lambda ()
                      ;; The checked GUI wrapper must override this on handler.
                      (parameterize ([current-check-handler (lambda (_) (void))])
                        ((car request))))
                    (lambda () (set! callback-active? #f))))))
        (async-channel-put (cdr request) response)
        (loop))))))
(define (fake-wait description predicate seconds)
  (set! last-timeout seconds)
  (check-false callback-active? "Action callback returned before polling")
  (on-handler predicate))
(define-values (gui await)
  (make-checked-coordinator on-handler fake-wait handler))
(define (coordinate thunk [wait pump-until-dead])
  (call-in-tool-coordinator
   (lambda ()
     (set! coordinator (current-thread))
     (check-not-eq? coordinator handler)
     (thunk))
   wait))

(parameterize ([current-check-handler raise]
               [context 'host-eventspace-context])
  (check-eq?
   (coordinate
    (lambda ()
      (check-eq? (context) 'host-eventspace-context)
      (check-eq? (gui current-thread) handler)
      (check-eq? (gui context) 'host-eventspace-context)
      (check-eq? (gui (lambda () 'action-returned)) 'action-returned)
      (check-eq? (await "after action" (lambda () 'ready) 20) 'ready)
      (check-equal? last-timeout 20)
      'actual))
   'actual)
  (check-true (thread-dead? coordinator))
  (check-eq? (current-thread) handler)
  (check-eq? (context) 'host-eventspace-context)

  ;; Produce a real failed RackUnit check on the original handler. The exact
  ;; exception must traverse on-handler, the worker, and the new join boundary.
  (check-exn
   (lambda (failure)
     (and (exn:test:check? failure) (eq? failure handler-failure)))
   (lambda () (coordinate (lambda () (gui (lambda () (check-equal? 1 2)))))))
  (check-true (thread-dead? coordinator))
  (check-false callback-active?)
  (check-eq? (coordinate (lambda () (gui (lambda () 'recovered)))) 'recovered)
  (check-true (thread-dead? coordinator))

  (define raised-token (gensym 'raised-value))
  (define received-token
    (with-handlers ([(lambda (_) #t) (lambda (failure) failure)])
      (coordinate (lambda () (raise raised-token)))
      'returned-without-raising))
  ;; The strict assertion is outside the catch; normal return cannot satisfy it.
  (check-eq? received-token raised-token)
  (check-true (thread-dead? coordinator))

  ;; An interrupted or prematurely returning wait must kill and join its worker.
  (for ([mode '(interrupted premature)])
    (define started (make-semaphore 0))
    (check-exn
     (if (eq? mode 'interrupted) #rx"wait interrupted" #rx"before coordinator termination")
     (lambda ()
       (coordinate
        (lambda () (semaphore-post started) (sync never-evt))
        (lambda (_)
          (sync started)
          (when (eq? mode 'interrupted) (error 'test "wait interrupted"))))))
    (check-true (thread-dead? coordinator)))
  (check-exn #rx"terminated without a result"
             (lambda () (coordinate (lambda () (kill-thread (current-thread))))))
  (check-true (thread-dead? coordinator))

  (when (equal? arguments #("--inject-wrong-result"))
    (define actual (coordinate (lambda () (gui (lambda () 'actual)))))
    (check-true (thread-dead? coordinator))
    (displayln "OPENRACKET_NATIVE_TOOL_DISPATCH_INJECTING_FAILURE")
    (flush-output)
    (with-handlers
        ([exn:test:check?
          (lambda (failure)
            ;; Diagnostic-only inspection cannot replace the original failure.
            (with-handlers ([(lambda (_) #t) void])
              (define infos (exn:test:check-stack failure))
              (define (unique key)
                (define matches
                  (for/list ([info (in-list infos)]
                             #:when (eq? (check-info-name info) key))
                    (check-info-value info)))
                (and (= (length matches) 1) (car matches)))
              (define name (unique 'name))
              (define got (unique 'actual))
              (define expected (unique 'expected))
              (when (and (eq? name 'check-equal?)
                         (pretty-info? got) (pretty-info? expected)
                         (eq? (pretty-info-value got) 'actual)
                         (eq? (pretty-info-value expected) 'deliberately-wrong))
                (printf "OPENRACKET_NATIVE_TOOL_DISPATCH_FAILURE exception=exn:test:check check=~s actual=~s expected=~s\n"
                        name (pretty-info-value got) (pretty-info-value expected))
                (flush-output)))
            (raise failure))])
      (check-equal? actual 'deliberately-wrong)))
  (displayln "OPENRACKET_NATIVE_TOOL_DISPATCH_OK distinct-thread strict-failures cleanup-complete")
  (flush-output))
(exit 0)
