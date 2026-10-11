#lang racket/base
;; Native headless scalar lifecycle tests. These are not GUI/performance evidence.
(require rackunit racket/list racket/runtime-path)
(define-runtime-path helper "application-probe.rkt")
(define observed? (equal? (getenv "OPENRACKET_GUI_APPLICATION_POINTS") "1"))
(define tags '(syncheck:add-arrow/name-dup/pxpy syncheck:add-tail-arrow
  syncheck:add-mouse-over-status syncheck:add-text-type syncheck:add-background-color
  syncheck:add-jump-to-definition/phase-level+space syncheck:add-require-open-menu
  syncheck:add-docs-menu syncheck:add-definition-target/phase-level+space
  syncheck:unused-binder syncheck:add-id-set syncheck:add-prefixed-require-reference
  syncheck:add-unused-require))
(define (fresh run)
  (parameterize ([current-namespace (make-base-namespace)])
    (run (dynamic-require helper 'application-hook)
         (dynamic-require helper 'application-summary))))
(define (row summary [n 0]) (list-ref (hash-ref (summary) 'records) n))
(define (entries hook r values)
  (for ([tag (in-list values)])
    (when observed? (hook 'entry-before r tag))
    ;; Represents the exact unwrapped stock invocation between the scalar hooks.
    (void)
    (when observed? (hook 'entry-after r))))
(define (finals hook r)
  (when observed?
    (for ([i (in-range 4)]) (hook 'final-before r i) (hook 'final-after r i))))

(fresh
 (lambda (hook summary)
   (define r (hook 'begin #(7 1)))
   (hook 'batch-start r)
   ;; Two appended chunks drain in the same stock slice without inventing a batch.
   (entries hook r (take tags 4))
   (entries hook r (drop tags 4))
   (hook 'batch-yield r)
   (sleep .003)
   (hook 'batch-resume r)
   (entries hook r tags)
   (hook 'batch-yield r)
   (hook 'callback-return r) ; Current callback returned after requeueing.
   (sleep .003)
   (hook 'batch-resume r)
   (finals hook r)
   (hook 'finish r #t)
   (hook 'callback-return r) ; Completed queued callback, not a stale event.
   (define v (row summary))
   (check-true (hash-ref v 'completed))
   (check-equal? (hash-ref v 'errors) 0)
   (check-equal? (hash-ref (summary) 'observer_failures) 0)
   (check-equal? (hash-ref (summary) 'probe_enabled) observed?)
   (check-equal? (hash-ref (hash-ref v 'batch_active) 'count) 3)
   (check-equal? (hash-ref (hash-ref v 'requeue_wait) 'count) 2)
   (check-equal? (hash-ref v 'yield_count) (hash-ref v 'resume_count))
   (check-false (hash-ref v 'active_batch))
   (check-false (hash-ref v 'queued_wait))
   (cond
     [observed?
      (check-equal? (hash-ref v 'entries_started) 26)
      (check-equal? (hash-ref v 'entries_completed) 26)
      (check-equal? (map (lambda (a) (hash-ref a 'count)) (hash-ref v 'tag_buckets)) (make-list 13 2))
      (check-equal? (map (lambda (a) (hash-ref a 'count)) (hash-ref v 'final_updates)) '(1 1 1 1))
      (define active (hash-ref (hash-ref v 'batch_active) 'wall_ms))
      (define wait (hash-ref (hash-ref v 'requeue_wait) 'wall_ms))
      (check-true (>= wait 5))
      (check-= (+ active wait) (- (hash-ref v 'last_batch_end_ms) (hash-ref v 'first_batch_start_ms)) .0001)
      (check-true (<= (for/sum ([a (in-list (append (hash-ref v 'tag_buckets) (hash-ref v 'final_updates)))])
                        (hash-ref a 'wall_ms)) active))]
     [else
      (check-equal? (hash-ref v 'tag_buckets) '())
      (check-equal? (hash-ref v 'final_updates) '())
      (check-equal? (hash-ref v 'entries_started) 0)
      (check-equal? (hash-ref (hash-ref v 'batch_active) 'wall_ms) 'null)])))

;; Actual queued callback skipped its stock liveness test: never a normal finish.
(fresh (lambda (h s)
  (define r (h 'begin #(1 1)))
  (h 'batch-start r) (h 'batch-yield r) (h 'batch-resume r)
  (h 'callback-return r)
  (check-true (hash-ref (row s) 'cancelled))
  (check-false (hash-ref (row s) 'completed))))
;; Cancel in the ordinary nonempty-trace branch.
(fresh (lambda (h s)
  (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'cancel r)
  (check-true (hash-ref (row s) 'cancelled))))
;; Queued continuation invalidated by a newer generation keeps old evidence invalid.
(fresh (lambda (h s)
  (define a (h 'begin #(1 1))) (h 'batch-start a) (h 'batch-yield a)
  (define b (h 'begin #(1 2))) (h 'batch-start b)
  (h 'batch-resume a)
  (check-true (positive? (hash-ref (row s) 'stale_events)))
  (check-true (hash-ref (row s) 'queued_wait))
  (h 'finish b #t)))
;; Common token-currentness must be carried into finish.
(fresh (lambda (h s)
  (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'finish r #f)
  (check-false (hash-ref (row s) 'completed))
  (check-equal? (hash-ref (row s) 'stale_events) 1)))
;; Overflow stays fixed at eight retained records.
(fresh (lambda (h s)
  (for ([i (in-range 12)]) (h 'begin (vector i 1)))
  (check-equal? (length (hash-ref (s) 'records)) 8)
  (check-equal? (hash-ref (s) 'dropped_records) 4)))
(when observed?
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r)
    (h 'entry-before r 'syncheck:unknown) (h 'entry-after r)
    (check-equal? (hash-ref (row s) 'unknown_tags) 1)))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r)
    (h 'entry-before r (car tags)) (h 'entry-before r (cadr tags))
    (h 'entry-after r) (h 'entry-after r)
    (check-equal? (hash-ref (row s) 'reentrant_entries) 1)))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'entry-after r)
    (check-equal? (hash-ref (row s) 'unmatched_events) 1)))
  ;; Before/after instrumentation does not catch or replace the consumer exception.
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r)
    (define original (exn:fail "stock consumer failed" (current-continuation-marks)))
    (check-eq? (with-handlers ([exn:fail? values])
                 (h 'entry-before r (car tags)) (raise original) (h 'entry-after r)) original)
    (check-equal? (hash-ref (row s) 'open_entry_depth) 1)
    (check-true (hash-ref (row s) 'active_batch))))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r)
    (check-equal? (let/ec escape (h 'entry-before r (car tags)) (escape 'original-escape) (h 'entry-after r)) 'original-escape)
    (check-equal? (hash-ref (row s) 'open_entry_depth) 1)))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'final-before r 0)
    (check-true (hash-ref (row s) 'open_final))
    (h 'finish r #t)
    (check-true (positive? (hash-ref (row s) 'unmatched_events)))))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'final-after r 0)
    (check-true (positive? (hash-ref (row s) 'unmatched_events))))))

(when observed?
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'batch-start r) (h 'final-before r 0)
    (h 'entry-before r (car tags)) (h 'entry-after r)
    (check-true (positive? (hash-ref (row s) 'reentrant_entries)))))
  (fresh (lambda (h s)
    (define r (h 'begin #(1 1))) (h 'final-before r 0)
    (check-true (positive? (hash-ref (row s) 'unmatched_events))))))
