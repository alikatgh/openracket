(lambda (probe-test-fault)
(lambda (category length)
  (with-handlers ([probe-diagnostic-failure? probe-fault!])
    (raise probe-test-fault)
    ;; Only length is observed; no vector is passed to this procedure or stored.
    (case category
  [(0) (set! probe-definitions-impersonator-vectors (add1 probe-definitions-impersonator-vectors))
       (set! probe-definitions-impersonator-slots (+ probe-definitions-impersonator-slots length))
       (set! probe-definitions-impersonator-max-slots (max probe-definitions-impersonator-max-slots length))]
  [(1) (set! probe-definitions-skipped-vectors (add1 probe-definitions-skipped-vectors))
       (set! probe-definitions-skipped-slots (+ probe-definitions-skipped-slots length))
       (set! probe-definitions-skipped-max-slots (max probe-definitions-skipped-max-slots length))]
  [(2) (set! probe-definitions-not-skipped-vectors (add1 probe-definitions-not-skipped-vectors))
       (set! probe-definitions-not-skipped-slots (+ probe-definitions-not-skipped-slots length))
       (set! probe-definitions-not-skipped-max-slots (max probe-definitions-not-skipped-max-slots length))]
  [(3) (set! probe-definitions-inspection-failed-vectors (add1 probe-definitions-inspection-failed-vectors))
       (set! probe-definitions-inspection-failed-slots (+ probe-definitions-inspection-failed-slots length))
       (set! probe-definitions-inspection-failed-max-slots (max probe-definitions-inspection-failed-max-slots length))]
  [(4) (set! probe-interactions-impersonator-vectors (add1 probe-interactions-impersonator-vectors))
       (set! probe-interactions-impersonator-slots (+ probe-interactions-impersonator-slots length))
       (set! probe-interactions-impersonator-max-slots (max probe-interactions-impersonator-max-slots length))]
  [(5) (set! probe-interactions-skipped-vectors (add1 probe-interactions-skipped-vectors))
       (set! probe-interactions-skipped-slots (+ probe-interactions-skipped-slots length))
       (set! probe-interactions-skipped-max-slots (max probe-interactions-skipped-max-slots length))]
  [(6) (set! probe-interactions-not-skipped-vectors (add1 probe-interactions-not-skipped-vectors))
       (set! probe-interactions-not-skipped-slots (+ probe-interactions-not-skipped-slots length))
       (set! probe-interactions-not-skipped-max-slots (max probe-interactions-not-skipped-max-slots length))]
  [(7) (set! probe-interactions-inspection-failed-vectors (add1 probe-interactions-inspection-failed-vectors))
       (set! probe-interactions-inspection-failed-slots (+ probe-interactions-inspection-failed-slots length))
       (set! probe-interactions-inspection-failed-max-slots (max probe-interactions-inspection-failed-max-slots length))])
    (void))))
