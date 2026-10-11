#lang racket/base
;; Separate stock-only discriminator. Same original Stop fixture and assertions,
;; but each real GUI action returns before the coordinator polls completion.
(require racket/class racket/file racket/gui/base racket/list racket/string
         json string-constants rackunit)
(provide run-returning-stop-check!)

(define stop-fixture
  (string-append "#lang racket/base\n"
                 "(printf \"BREAKS_ENABLED=~s\\n\" (break-enabled))\n"
                 "(displayln \"WAITING_TO_BREAK\")\n(flush-output)\n"
                 "(sleep 120)\n(displayln \"UNREACHABLE\")\n"))

(define (run-returning-stop-check! frame on-gui wait-for)
  (parameterize ([current-check-handler raise])
    (define directory (make-temporary-file "openracket-stop-returning-~a" 'directory))
    (define file (build-path directory "fixture.rkt"))
    (call-with-output-file file #:exists 'truncate (lambda (out) (display stop-fixture out)))
    (define widgets
      (on-gui (lambda ()
                (list (send frame get-definitions-text) (send frame get-interactions-text)
                      (send frame get-execute-button) (send frame get-break-button)
                      (send frame get-current-tab)))))
    (define defs (list-ref widgets 0))
    (define ints (list-ref widgets 1))
    (define run (list-ref widgets 2))
    (define stop (list-ref widgets 3))
    (define tab (list-ref widgets 4))
    (define pinned-target #f)
    (define pinned-custodian #f)
    (define (widget-identities)
      (and (eq? defs (send frame get-definitions-text))
           (eq? ints (send frame get-interactions-text))
           (eq? run (send frame get-execute-button))
           (eq? stop (send frame get-break-button))
           (eq? tab (send frame get-current-tab))))
    (define (state! stage [include-context? #f])
      (define-values (target custodian) (send tab get-breakables))
      (define (bounded text [limit 1800]) (substring text 0 (min limit (string-length text))))
      (display "OPENRACKET_RETURNING_STOP_STATE ")
      (write-json
       (hash 'stage stage 'same_tab (eq? tab (send frame get-current-tab))
             'same_stop_widget (eq? stop (send frame get-break-button))
             'all_widget_identities (widget-identities)
             'target_is_evaluator (eq? target (send ints get-user-thread))
             'evaluator_is_pinned (eq? pinned-target (send ints get-user-thread))
             'target_is_pinned (eq? target pinned-target)
             'custodian_is_pinned (eq? custodian pinned-custodian)
             'pinned_target_live (and pinned-target (not (thread-dead? pinned-target)))
             'target_live (and target (not (thread-dead? target)))
             'running (send tab is-running?) 'in_evaluation (send ints get-in-evaluation?)
             'run_enabled (send run is-enabled?) 'stop_label (send stop get-label)
             'interactions_excerpt (bounded (send ints get-text))
             'pinned_context
             (if (and include-context? pinned-target (not (thread-dead? pinned-target)))
                 (with-handlers ([exn? (lambda (e) (exn-message e))])
                   (define entries
                     (continuation-mark-set->context (continuation-marks pinned-target)))
                   (bounded (format "~s" (take entries (min 12 (length entries))))))
                 'null)))
      (newline) (flush-output))
    (on-gui (lambda ()
              (send frame change-to-file file)
              (check-true (widget-identities))
              (check-equal? (send defs get-text) stop-fixture)))
    (wait-for "returning Stop: Run enabled" (lambda () (send run is-enabled?)) 20)
    ;; This callback has fully returned before the first readiness poll.
    (on-gui (lambda () (send run command)))
    (wait-for
     "returning Stop: marker and live evaluator"
     (lambda ()
       (define-values (target custodian) (send tab get-breakables))
       (and (string-contains? (send ints get-text) "WAITING_TO_BREAK")
            (send tab is-running?) (thread? target) (not (thread-dead? target))
            (custodian? custodian)))
     20)
    (on-gui
     (lambda ()
       (define-values (target custodian) (send tab get-breakables))
       (set! pinned-target target) (set! pinned-custodian custodian)
       (check-true (widget-identities))
       (check-eq? target (send ints get-user-thread))
       (check-true (send stop is-enabled?))
       (check-equal? (send stop get-label) (string-constant break-button-label))
       (state! "before-stop")
       (send stop command)
       (check-equal? (send stop get-label) (string-constant break-button-kill-label))
       (state! "after-stop-before-callback-return")))
    ;; No GUI action callback remains active here. The coordinator's polling
    ;; callbacks only inspect state and return, exactly like normal host Run checks.
    (with-handlers ([exn? (lambda (e)
                           (on-gui (lambda () (state! "interrupt-timeout" #t)))
                           (raise e))])
      (wait-for "returning Stop: interrupted evaluation completes and Run is available"
                (lambda () (and (not (send tab is-running?)) (send run is-enabled?)))
                20))
    (on-gui
     (lambda ()
       (state! "completed")
       (check-true (widget-identities))
       ;; Evaluator reuse is logged, not an extra acceptance condition. The
       ;; discriminator retains the original Stop completion contract.
       (check-false (string-contains? (send ints get-text) "UNREACHABLE"))))
    (hash 'status "passed" 'case "stop-returning" 'same_original_fixture #t
          'strict_completion_seconds 20 'real_stop_callback #t)))
