#lang racket/base
;; Test-harness thread bridge only. It does not create or supply an eventspace.
(provide call-in-tool-coordinator)

(define (call-in-tool-coordinator thunk wait-for-thread)
  (define result #f)
  (define coordinator #f)
  (dynamic-wind
    void
    (lambda ()
      ;; Inherit the caller's parameters, including its actual host eventspace.
      (set! coordinator
            (thread
             (lambda ()
               (set! result
                     (with-handlers ([(lambda (_) #t)
                                      (lambda (failure) (cons 'error failure))])
                       (cons 'value (thunk)))))))
      ;; Native callers supply GUI yield; sync/thread-wait here would deadlock
      ;; the initial GUI handler while the coordinator requests its callbacks.
      (wait-for-thread (thread-dead-evt coordinator))
      (unless (thread-dead? coordinator)
        (error 'native-tool-dispatch "Wait returned before coordinator termination"))
      (unless result
        (error 'native-tool-dispatch "Coordinator terminated without a result"))
      (if (eq? (car result) 'error)
          (raise (cdr result))
          (cdr result)))
    (lambda ()
      ;; Always join the one worker we own, including when waiting raises.
      (when coordinator
        (unless (thread-dead? coordinator) (kill-thread coordinator))
        (thread-wait coordinator)))))
