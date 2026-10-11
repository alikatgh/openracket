#lang racket/base
;; Native rackunit tests; no display server, GUI library, installation, or I/O.
(require rackunit racket/async-channel json "heartbeat.rkt")

(define (tick) (current-inexact-monotonic-milliseconds))
(define (deadline [ms 2000.0]) (+ (tick) ms))
(define (box-change! b f)
  (let loop ()
    (define old (unbox b))
    (unless (box-cas! b old (f old)) (loop))))
(struct dispatcher (queue yield pop depth maximum priorities accepted) #:transparent)
(define (make-dispatcher [after-queue void])
  (define callbacks (make-async-channel))
  (define depth (box 0))
  (define maximum (box 0))
  (define priorities (box '()))
  (define accepted (make-semaphore 0))
  (define (queue callback high-priority?)
    (box-change! depth add1)
    (box-change! maximum (lambda (n) (max n (unbox depth))))
    (box-change! priorities (lambda (xs) (cons high-priority? xs)))
    (async-channel-put callbacks callback)
    (semaphore-post accepted)
    (after-queue))
  (define (dispatch callback)
    (box-change! depth sub1)
    (callback))
  (define (pop)
    (define callback (sync/timeout 2.0 callbacks))
    (check-not-false callback "expected a queued heartbeat")
    (and callback (begin (dispatch callback) #t)))
  (define (gui-yield evt)
    (let loop ()
      (define selected
        (sync (handle-evt evt (lambda (v) (cons 'done v)))
              (handle-evt callbacks (lambda (callback) (cons 'callback callback)))))
      (if (eq? (car selected) 'done)
          (cdr selected)
          (begin (dispatch (cdr selected)) (loop)))))
  (dispatcher queue gui-yield pop depth maximum priorities accepted))
(define (await-queued d)
  (check-not-false (sync/timeout 2.0 (dispatcher-accepted d))))
(define (summary h) (heartbeat-summary h))
(define (field h key) (hash-ref (summary h) key))
(define (rows h) (field h 'records))
(define (stop/join h d)
  (heartbeat-stop! h)
  (check-true (heartbeat-join! h (dispatcher-yield d) (deadline))))
(define (with-heartbeat d thunk #:period-ms [period 2.0] #:max-records [bound 4096])
  (define h (start-heartbeat! (dispatcher-queue d) #:period-ms period #:max-records bound))
  (dynamic-wind void (lambda () (thunk h))
                (lambda ()
                  (heartbeat-stop! h)
                  (heartbeat-join! h (dispatcher-yield d) (deadline)))))

(test-case "exact production defaults and no false success without coverage"
  (define d (make-dispatcher))
  (define h (start-heartbeat! (dispatcher-queue d)))
  (check-equal? (field h 'period_ms) 50.0)
  (check-equal? (field h 'max_records) 4096)
  (heartbeat-stop! h)
  (check-true (heartbeat-join! h (dispatcher-yield d) (deadline)))
  (when (zero? (field h 'handled_count)) (check-false (heartbeat-ok? h))))

(test-case "only one low-priority callback outstanding despite a GUI stall"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (await-queued d)
     (sleep 0.04) ; no fake GUI dispatch for many heartbeat periods
     (check-equal? (unbox (dispatcher-depth d)) 1)
     (check-equal? (field h 'submitted_count) 1)
     (check-equal? (field h 'outstanding_callbacks) 1)
     (stop/join h d)
     (check-equal? (unbox (dispatcher-maximum d)) 1)
     (check-equal? (unbox (dispatcher-priorities d)) '(#f))
     (check-equal? (field h 'outstanding_callbacks) 0)
     (check-true (field h 'producer_exited))
     (check-true (heartbeat-ok? h))
     (check-true (hash-ref (car (rows h)) 'after_stop)))))

(test-case "bounded retained records and explicit overflow"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (for ([i (in-range 7)]) ((dispatcher-pop d)))
     (stop/join h d)
     (check-equal? (length (rows h)) 3)
     (check-equal? (field h 'record_count) 3)
     (check-equal? (field h 'dropped_records) (- (field h 'handled_count) 3))
     (check-true (>= (field h 'dropped_records) 4))
     (check-equal? (map (lambda (row) (hash-ref row 'sequence)) (rows h)) '(1 2 3))
     (check-false (heartbeat-ok? h)))
   #:max-records 3))

(test-case "cancellation wakes a sleeping producer without a further tick"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (heartbeat-stop! h)
     (define first-stop (field h 'stopped_monotonic_ms))
     (heartbeat-stop! h)
     (check-equal? (field h 'stopped_monotonic_ms) first-stop)
     (check-true (heartbeat-join! h (dispatcher-yield d) (deadline 300.0)))
     (check-equal? (field h 'submitted_count) 0)
     (check-equal? (unbox (dispatcher-depth d)) 0))
   #:period-ms 60000.0))

(test-case "join uses GUI yield to drain callback after producer stops"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (await-queued d)
     (heartbeat-stop! h)
     (define yielded 0)
     (check-true
      (heartbeat-join! h
                       (lambda (evt)
                         (set! yielded (add1 yielded))
                         ((dispatcher-yield d) evt))
                       (deadline)))
     (check-true (positive? yielded))
     (check-equal? (field h 'handled_count) 1)
     (check-equal? (unbox (dispatcher-depth d)) 0))))

(test-case "expired original deadline does not grant cleanup grace or kill"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (await-queued d)
     (heartbeat-stop! h)
     (define yielded #f)
     (check-false (heartbeat-join! h (lambda (_) (set! yielded #t)) (- (tick) 1.0)))
     (check-false yielded)
     (check-true (field h 'join_timed_out))
     (check-equal? (field h 'outstanding_callbacks) 1)
     ;; Eventual draining is safe, but does not erase the original failure.
     (check-true (heartbeat-join! h (dispatcher-yield d) (deadline)))
     (check-false (heartbeat-ok? h)))))

(test-case "bounded join times out when dispatcher cannot drain"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     (await-queued d)
     (heartbeat-stop! h)
     (define until (deadline 25.0))
     (check-false (heartbeat-join! h sync until))
     (check-true (>= (tick) until))
     (check-true (field h 'join_timed_out))
     (check-equal? (field h 'outstanding_callbacks) 1))))

(test-case "producer lateness keeps scheduled deadline across producer suspension"
  (define release (make-semaphore 0))
  (define first? #t)
  (define d
    (make-dispatcher
     (lambda ()
       (when first?
         (set! first? #f)
         ;; Test-only fake queue pauses the producer after accepting its first
         ;; callback; real callbacks can still run in the fake GUI thread.
         (semaphore-wait release)))))
  (with-heartbeat
   d
   (lambda (h)
     (dynamic-wind
       void
       (lambda ()
         ((dispatcher-pop d))
         (define first (car (rows h)))
         (sleep 0.06)
         (define resumed-at (tick))
         (semaphore-post release)
         ((dispatcher-pop d))
         (stop/join h d)
         (define second (cadr (rows h)))
         (define intended (+ (hash-ref first 'handler_monotonic_ms) 2.0))
         (check-= (hash-ref second 'scheduled_monotonic_ms) intended 0.0001)
         (check-true (>= (hash-ref second 'submitted_monotonic_ms) resumed-at))
         (check-true (>= (hash-ref second 'producer_lateness_ms) (- resumed-at intended)))
         (check-true (>= (hash-ref second 'handler_gap_ms) 50.0)))
       (lambda () (semaphore-post release))))))

(test-case "dispatch latency and handler gaps expose long GUI gaps"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     ((dispatcher-pop d))
     (await-queued d) ; consume the first submission's acknowledgment
     (await-queued d) ; second callback is waiting in the GUI queue
     (define stall-start (tick))
     (sleep 0.06)
     (heartbeat-stop! h)
     (define frozen-tail (field h 'stop_handler_gap_ms))
     (check-true (>= (field h 'stop_handler_gap_ms) 50.0))
     (check-true (heartbeat-join! h (dispatcher-yield d) (deadline)))
     (check-equal? (field h 'stop_handler_gap_ms) frozen-tail)
     (define first (car (rows h)))
     (define second (cadr (rows h)))
     (check-true (<= (hash-ref second 'submitted_monotonic_ms) stall-start))
     (check-true (>= (hash-ref second 'dispatch_latency_ms) 50.0))
     (check-true (>= (hash-ref second 'handler_gap_ms) 50.0))
     (check-equal? (hash-ref first 'handler_gap_ms) 'null)
     (for ([row (in-list (rows h))])
       (check-= (+ (hash-ref row 'producer_lateness_ms)
                   (hash-ref row 'dispatch_latency_ms))
                (- (hash-ref row 'handler_monotonic_ms)
                   (hash-ref row 'scheduled_monotonic_ms)) 0.0001)))))

(test-case "queue failures are scalar evidence and cannot strand cancellation"
  (define attempted (make-semaphore 0))
  (define h
    (start-heartbeat! (lambda (_callback _priority)
                        (semaphore-post attempted)
                        (error 'fake "queue unavailable"))
                      #:period-ms 1.0))
  (check-not-false (sync/timeout 2.0 attempted))
  (check-true (heartbeat-join! h sync (deadline)))
  (check-true (positive? (field h 'error_count)))
  (check-not-false (member "queue-callback-failed" (field h 'errors)))
  (check-equal? (field h 'outstanding_callbacks) 0)
  (check-false (heartbeat-ok? h)))

(test-case "summary is an immutable scalar JSON tree and stable snapshot"
  (define d (make-dispatcher))
  (with-heartbeat
   d
   (lambda (h)
     ((dispatcher-pop d))
     (define before (summary h))
     (define count (hash-ref before 'handled_count))
     ((dispatcher-pop d))
     (stop/join h d)
     (check-equal? (hash-ref before 'handled_count) count)
     (define (scalar-tree? value)
       (cond
         [(hash? value)
          (and (immutable? value)
               (for/and ([(key v) (in-hash value)]) (and (symbol? key) (scalar-tree? v))))]
         [(list? value) (andmap scalar-tree? value)]
         [(string? value) (immutable? value)]
         [else (or (boolean? value) (real? value) (eq? value 'null))]))
     (check-true (scalar-tree? (summary h)))
     (check-true (string? (jsexpr->string (summary h)))))))

(test-case "invalid test configuration cannot silently remove bounds"
  (define d (make-dispatcher))
  (for ([n (in-list '(0 -1 4097 1.5))])
    (check-exn exn:fail:contract? (lambda () (start-heartbeat! (dispatcher-queue d) #:max-records n))))
  (for ([period (in-list (list 0 -1 +inf.0 +nan.0))])
    (check-exn exn:fail:contract? (lambda () (start-heartbeat! (dispatcher-queue d) #:period-ms period)))))
