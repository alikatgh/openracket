#lang racket/base
;; Common, low-priority GUI responsiveness evidence. This module does not load
;; racket/gui, perform I/O, retain workload objects, or install a timer%.
;; Pass queue-callback and yield from the workload's actual GUI eventspace.
(provide start-heartbeat! heartbeat-stop! heartbeat-join!
         heartbeat-summary heartbeat-ok?)

(define default-period-ms 50.0)
(define maximum-records 4096)
(define maximum-errors 8)
(define (tick) (current-inexact-monotonic-milliseconds))
(define (finite-real? v) (and (real? v) (< -inf.0 v +inf.0)))
(struct heartbeat (state stop acknowledged producer))

;; Native box-cas! may return #f spuriously without changing the box. The
;; private parameter only lets native tests reproduce that permitted result.
;; It is not part of the production API or configurable from the environment.
(define current-once-cas! (make-parameter box-cas!))
(module+ test-support (provide current-once-cas!))
(define (claim-once! once)
  (define cas! (current-once-cas!))
  (let loop ()
    (cond
      [(unbox once) #f]
      [(cas! once #f #t) #t]
      [else (loop)])))

;; The producer and GUI callback share only bounded scalar evidence and these
;; synchronization objects. CAS avoids ever waiting for a mutex in the GUI.
(define (change! h transition)
  (let loop ()
    (define old (unbox (heartbeat-state h)))
    (define-values (new result) (transition old))
    (if (box-cas! (heartbeat-state h) old new) result (loop))))
(define (put h key value)
  (change! h (lambda (old) (values (hash-set old key value) (void)))))
(define (stopped? h)
  (not (eq? (hash-ref (unbox (heartbeat-state h)) 'stopped_monotonic_ms) 'null)))
(define (error! h code)
  ;; Fixed immutable strings, not exception objects, stacks, or arbitrary data.
  (change! h
           (lambda (old)
             (define errors (hash-ref old 'errors))
             (values
              (hash-set
               (hash-set old 'error_count (add1 (hash-ref old 'error_count)))
               'errors (if (< (length errors) maximum-errors) (cons code errors) errors))
              (void)))))

(define (heartbeat-stop! h)
  (define first-stop?
    (change!
     h
     (lambda (old)
       (cond
         [(not (eq? (hash-ref old 'stopped_monotonic_ms) 'null)) (values old #f)]
         [else
          (define previous (hash-ref old 'last_handler_monotonic_ms))
          (define stopped-at (tick))
          (values
           (hash-set
            (hash-set old 'stopped_monotonic_ms stopped-at)
            'stop_handler_gap_ms
            (- stopped-at
               (if (eq? previous 'null)
                   (hash-ref old 'started_monotonic_ms) previous)))
           #t)]))))
  (when first-stop? (semaphore-post (heartbeat-stop h)))
  (void))

(define (callback! h sequence scheduled submitted once acknowledged)
  (cond
    [(not (claim-once! once))
     (error! h "duplicate-callback")
     (heartbeat-stop! h)]
    [else
     ;; Acknowledgment is in the post-thunk even if observation itself fails.
     ;; No semaphore wait, GUI yield, reporting, or file I/O occurs here.
     (dynamic-wind
       void
       (lambda ()
         (with-handlers ([exn? (lambda (_)
                                (error! h "callback-failed")
                                (heartbeat-stop! h))])
           (define handled-at (tick))
           (change!
            h
            (lambda (old)
              (define previous (hash-ref old 'last_handler_monotonic_ms))
              (define stopped-at (hash-ref old 'stopped_monotonic_ms))
              (define room? (< (hash-ref old 'record_count) (hash-ref old 'max_records)))
              (define row
                (vector-immutable
                 sequence scheduled submitted handled-at
                 (- submitted scheduled) (- handled-at submitted)
                 (if (eq? previous 'null) 'null (- handled-at previous))
                 (and (not (eq? stopped-at 'null)) (>= handled-at stopped-at))))
              (define next
                (hash-set
                 (hash-set old 'handled_count (add1 (hash-ref old 'handled_count)))
                 'last_handler_monotonic_ms handled-at))
              (values
               (if room?
                   (hash-set
                    (hash-set next 'records (cons row (hash-ref old 'records)))
                    'record_count (add1 (hash-ref old 'record_count)))
                   (hash-set next 'dropped_records (add1 (hash-ref old 'dropped_records))))
               (void))))))
       (lambda ()
         (put h 'outstanding_callbacks 0)
         (semaphore-post acknowledged)))]))

(define (produce! h queue-callback)
  (define stop-event (semaphore-peek-evt (heartbeat-stop h)))
  (define initial (unbox (heartbeat-state h)))
  (define period (hash-ref initial 'period_ms))
  (with-handlers ([exn? (lambda (_)
                         (error! h "producer-failed")
                         (heartbeat-stop! h))])
    (let loop ([scheduled (+ (hash-ref initial 'started_monotonic_ms) period)])
      ;; Preserve the intended deadline through a producer/GC suspension. Every
      ;; alarm here and in join uses the monotonic clock (second argument #t).
      (sync (choice-evt stop-event (alarm-evt scheduled #t)))
      (unless (stopped? h)
        (define sequence
          (change!
           h
           (lambda (old)
             ;; Linearize reservation with stop: no reservation after stop.
             (cond
               [(not (eq? (hash-ref old 'stopped_monotonic_ms) 'null)) (values old #f)]
               [else
                (define n (add1 (hash-ref old 'submitted_count)))
                (values (hash-set (hash-set old 'submitted_count n)
                                  'outstanding_callbacks 1) n)]))))
        (when sequence
          (define once (box #f))
          (define acknowledged (make-semaphore 0))
          (set-box! (heartbeat-acknowledged h) acknowledged)
          (define submitted (tick))
          (with-handlers
              ([exn? (lambda (_)
                       (error! h "queue-callback-failed")
                       (heartbeat-stop! h)
                       ;; A failed submission cannot leave join waiting for a
                       ;; callback that was never accepted. If a broken queue
                       ;; later invokes it, once makes that an explicit error.
                       (when (claim-once! once)
                         (put h 'outstanding_callbacks 0)
                         (semaphore-post acknowledged)))])
            (queue-callback
             (lambda () (callback! h sequence scheduled submitted once acknowledged)) #f))
          ;; One callback at most. Stop releases the producer immediately; the
          ;; GUI will drain any accepted callback while heartbeat-join! yields.
          (sync (choice-evt stop-event (semaphore-peek-evt acknowledged)))
          (unless (stopped? h)
            ;; CLOSED LOOP, not a catch-up timer: next planned wake is one
            ;; period after this handler's timestamp, never a new 'now'. A
            ;; delayed producer therefore cannot reset away its own lateness.
            (loop (+ (hash-ref (unbox (heartbeat-state h))
                              'last_handler_monotonic_ms) period))))))))

(define (start-heartbeat! queue-callback
                          #:period-ms [period-ms default-period-ms]
                          #:max-records [max-records maximum-records])
  ;; Keywords permit short, bounded native tests. Production uses defaults.
  (unless (and (procedure? queue-callback) (procedure-arity-includes? queue-callback 2))
    (raise-argument-error 'start-heartbeat! "procedure accepting 2 arguments" queue-callback))
  (unless (and (finite-real? period-ms) (positive? period-ms))
    (raise-argument-error 'start-heartbeat! "positive finite real period" period-ms))
  (unless (and (exact-positive-integer? max-records) (<= max-records maximum-records))
    (raise-argument-error 'start-heartbeat! "integer in [1, 4096]" max-records))
  (define h
    (heartbeat
     (box (hasheq
           'schema_version 1 'kind "gui-heartbeat" 'clock "monotonic"
           'period_ms period-ms 'max_records max-records
           'started_monotonic_ms (tick) 'stopped_monotonic_ms 'null
           'last_handler_monotonic_ms 'null 'stop_handler_gap_ms 'null
           'outstanding_callbacks 0 'submitted_count 0 'handled_count 0
           'record_count 0 'dropped_records 0 'error_count 0 'errors '()
           'join_timed_out #f 'joined #f 'records '()))
     (make-semaphore 0) (box (make-semaphore 1)) (box #f)))
  (set-box! (heartbeat-producer h) (thread (lambda () (produce! h queue-callback))))
  h)

(define (producer-exited? h)
  (define producer (unbox (heartbeat-producer h)))
  (and producer (thread-dead? producer) #t))
(define (drained? h)
  (and (producer-exited? h)
       (zero? (hash-ref (unbox (heartbeat-state h)) 'outstanding_callbacks))
       (sync/timeout 0 (semaphore-peek-evt (unbox (heartbeat-acknowledged h))))
       #t))

(define (heartbeat-join! h gui-yield absolute-monotonic-deadline)
  ;; The caller must stop after its endpoint, then pass its ORIGINAL deadline.
  ;; Join defensively requests stop too; it never grants additional workload
  ;; time. An expired deadline returns immediately without killing a thread.
  (unless (and (procedure? gui-yield) (procedure-arity-includes? gui-yield 1))
    (raise-argument-error 'heartbeat-join! "procedure accepting one event" gui-yield))
  (unless (finite-real? absolute-monotonic-deadline)
    (raise-argument-error 'heartbeat-join! "finite monotonic deadline" absolute-monotonic-deadline))
  (heartbeat-stop! h)
  (define deadline-event (alarm-evt absolute-monotonic-deadline #t))
  (with-handlers ([exn? (lambda (_)
                         (error! h "join-yield-failed")
                         #f)])
    (let loop ()
      (cond
        [(drained? h) (put h 'joined #t) #t]
        [(>= (tick) absolute-monotonic-deadline)
         (put h 'join_timed_out #t) #f]
        [else
         ;; Do not repeatedly select an already-dead producer while a queued
         ;; callback still needs GUI dispatch. Its acknowledgment is distinct.
         (define completion-event
           (if (producer-exited? h)
               (semaphore-peek-evt (unbox (heartbeat-acknowledged h)))
               (thread-dead-evt (unbox (heartbeat-producer h)))))
         (gui-yield (choice-evt completion-event deadline-event))
         (loop)]))))

(define row-keys
  '(sequence scheduled_monotonic_ms submitted_monotonic_ms handler_monotonic_ms
             producer_lateness_ms dispatch_latency_ms handler_gap_ms after_stop))
(define (heartbeat-summary h)
  ;; Conversion and list reversal happen only on request, never in the producer
  ;; or GUI callback. The returned JSON tree contains immutable hashes/lists and
  ;; scalar values; no thread, semaphore, procedure, or mutable row escapes.
  (define old (unbox (heartbeat-state h)))
  (hash-set
   (hash-set
    (hash-set old 'producer_exited (producer-exited? h))
    'errors (reverse (hash-ref old 'errors)))
   'records
   (for/list ([row (in-list (reverse (hash-ref old 'records)))])
     (for/hasheq ([key (in-list row-keys)] [value (in-vector row)])
       (values key value)))))

(define (heartbeat-ok? h)
  (define state (unbox (heartbeat-state h)))
  (and (drained? h) (hash-ref state 'joined)
       (not (hash-ref state 'join_timed_out))
       (zero? (hash-ref state 'error_count))
       (zero? (hash-ref state 'dropped_records))
       (positive? (hash-ref state 'handled_count))
       (= (hash-ref state 'submitted_count) (hash-ref state 'handled_count))))
