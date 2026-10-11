#lang racket/base
;; TEST DOUBLE ONLY. This is never a stock expansion worker or performance sample.
(require racket/place "support.rkt")
(provide start)
(define (start p)
  (place-channel-get p) ; fake test consumes the real compile-lock endpoint
  (place-channel-get p) ; no stock registry is asserted by this protocol double
  (when (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
    (cond
      [(member (getenv "OPENRACKET_REPLAY_MOCK_MODE") '("cleanup-wrong" "cleanup-missing"))
       (define-values (local remote) (place-channel))
       (thread
        (lambda ()
          (let controls ()
            (case (place-channel-get local)
              [(snapshot)
               (place-channel-put local (hasheq 'monotonic_ms (current-inexact-monotonic-milliseconds)
                                                'gc_ms (current-gc-milliseconds) 'records '() 'records_dropped 0))
               (controls)]
              [(stop)
               (if (equal? (getenv "OPENRACKET_REPLAY_MOCK_MODE") "cleanup-wrong")
                   (place-channel-put local 'wrong-acknowledgement) (sleep 10))]))))
       (place-channel-put p (vector 'openracket-expansion-replay-ready remote 268435456 (custodian-memory-accounting-available?)))
       (unless (eq? (place-channel-get p) 'openracket-expansion-replay-continue) (error 'mock "bad continue"))]
      [else (worker-ready! p (current-logger) 268435456)]))
  (let loop ([count 0])
    (define request (place-channel-get p))
    (cond
      [(eq? request 'abort) (loop count)]
      [else
       (define next-count (add1 count))
       (define mode (or (getenv "OPENRACKET_REPLAY_MOCK_MODE") "success"))
       (when (and (= next-count 2) (equal? mode "second-no-response")) (sleep 10))
       (when (and (= next-count 2) (equal? mode "second-death-no-response")) (exit 3))
       (define response (vector-ref request 2))
       (define status (vector-ref request 4))
       (place-channel-put status 'finished-expansion)
       (define-values (local remote) (place-channel))
       (thread (lambda () (let rpc () (place-channel-put local (place-channel-get local)) (rpc))))
       (place-channel-put response (vector 'monitor-message '(test go) (vector remote 1)))
       (case (string->symbol (or (getenv "OPENRACKET_REPLAY_MOCK_MODE") "success"))
         [(timeout) (sleep 10)]
         [(death) (exit 3)]
         [(abnormal) (sleep .03)
                     (place-channel-put response
                       (vector 'abnormal-termination "Expansion thread terminated unexpectedly (out of memory)" '() '()))]
         [else (sleep .03) (place-channel-put response (vector 'handler-results '() '() #f))])
       (loop next-count)])))
