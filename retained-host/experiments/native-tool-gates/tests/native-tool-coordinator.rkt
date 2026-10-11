#lang racket/base
;; GUI-independent orchestration seam. This does not supply a GUI or a tool.
(require rackunit)
(provide make-checked-coordinator)

(define (make-checked-coordinator on-gui wait-for handler-thread)
  (define (checked thunk)
    (lambda ()
      (unless (eq? (current-thread) handler-thread)
        (error 'native-tool-gate "Callback did not run on the actual GUI handler"))
      ;; Parameters belong to threads: parameterizing only the coordinator does
      ;; not make RackUnit failures fatal on the existing GUI handler thread.
      (parameterize ([current-check-handler raise])
        (thunk))))
  (values
   (lambda (thunk) (on-gui (checked thunk)))
   (lambda (description predicate [seconds 20])
     ;; Never convert an exception to #f. A broken readiness predicate fails now.
     (wait-for description (checked predicate) seconds))))
