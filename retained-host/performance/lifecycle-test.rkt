#lang racket/base
;; Headless lifecycle regression: stop monitors from a different custodian without
;; trying to kill a thread the caller does not solely manage.
(require rackunit racket/runtime-path racket/file)
(define-runtime-path source "retained-host.rkt")
(check-false (regexp-match? #rx"kill-thread" (file->string source)))
(for ([kind '(startup heartbeat)])
  (define stop? #f)
  (define worker
    (thread (lambda () (let loop () (unless stop? (sleep .005) (loop))))))
  (define child (make-custodian))
  (parameterize ([current-custodian child])
    (set! stop? #t)
    (check-not-false (sync/timeout 1 (thread-dead-evt worker))))
  (check-true (thread-dead? worker)))
