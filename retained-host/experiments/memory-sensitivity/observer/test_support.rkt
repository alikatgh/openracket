#lang racket/base
;; Run on an already available native runtime: racket test_support.rkt.
;; Synthetic protocol-helper tests are deliberately distinct from native GUI evidence.
(require rackunit rackunit/text-ui racket/file racket/runtime-path racket/list json)
(define-runtime-path support "support.rkt")
(define (fresh thunk)
  (parameterize ([current-namespace (make-base-namespace)]
                 [current-environment-variables (environment-variables-copy (current-environment-variables))])
    (putenv "OPENRACKET_COMPACT_OBSERVER" "1")
    (thunk (lambda (name) (dynamic-require support name)))))
(define final "#lang racket/base\n(define final-value 81)\n")
(define source (build-path (current-directory) "fixture.rkt"))
(define (request text [path source] [settings 'settings]) (vector-immutable text path #f settings #f '()))
(define success (vector 'handler-results '() '() #f))
(define oom (vector 'abnormal-termination "Expansion thread terminated unexpectedly (out of memory)" '() '()))
(define (register api) ((api 'observer-register-final!) final #:generation "final-81" #:source source))

(define protocol-tests
 (test-suite "Compact protocol metadata"
 (test-case "Exact source + exact final contents, terminal receipt is not callback delivery"
  (fresh
   (lambda (api)
     (define sha (register api))
     (check-equal? (string-length sha) 64)
     (define partial ((api 'observer-request!) (request "#lang racket/base\n")))
     (define wrong-file ((api 'observer-request!) (request final (build-path (current-directory) "other.rkt"))))
     (define id ((api 'observer-request!) (request final)))
     (check-false ((api 'observer-final-outcome)))
     ((api 'observer-status!) id 'finished-expansion)
     ((api 'observer-terminal!) id success)
     (check-false ((api 'observer-final-outcome)))
     ((api 'observer-callback-enter!) id #t)
     (check-false ((api 'observer-final-outcome)))
     ((api 'observer-callback-delivered!) id)
     (define outcome ((api 'observer-final-outcome)))
     (check-equal? (hash-ref outcome 'request_id) id)
     (check-equal? (hash-ref outcome 'snapshot_sha256) sha)
     (check-equal? (hash-ref (hash-ref outcome 'terminal) 'tag) "handler-results")
     (check-true (hash-ref outcome 'callback_current))
     (check-equal? (hash-ref outcome 'actual_prefab) "settings")
     (check-false (hash-ref outcome 'actual_prefab_truncated))
     (define all ((api 'observer-summary)))
     (check-equal? (map (lambda (r) (hash-ref r 'final_match)) (hash-ref all 'records)) '(#f #f #t))
     (check-true (hash-ref all 'complete_observation))
     (check-not-exn (lambda () (jsexpr->string all)))
     (check-false (regexp-match? #rx"final-value" (jsexpr->string all)))
     ;; A newer matching request makes an older completed outcome unavailable.
     (define newer ((api 'observer-request!) (request final)))
     (check-false ((api 'observer-final-outcome)))
     ((api 'observer-terminal!) newer oom)
     ((api 'observer-callback-enter!) newer #f)
     ((api 'observer-callback-delivered!) newer)
     (check-false ((api 'observer-final-outcome)))
     (define newer-result (last ((api 'observer-final-terminals))))
     (check-true (hash-ref (hash-ref newer-result 'terminal) 'explicit_out_of_memory))
     (check-false (hash-ref newer-result 'callback_current))
     (check-equal? (length ((api 'observer-final-terminals))) 2))))

(test-case "Monitor error does not disappear behind handler-results; traces are not retained"
  (fresh
   (lambda (api)
     (register api)
     (define id ((api 'observer-request!) (request final)))
     ((api 'observer-response!) id (vector 'monitor-message 'handler '(private-trace payload)))
     ((api 'observer-response!) id (vector 'monitor-message 'handler '()))
     ((api 'observer-response!) id (vector 'monitor-message 'handler (make-string 600 #\e)))
     ((api 'observer-response!) id (vector 'monitor-message 'handler '#(unusual)))
     ((api 'observer-response!) id success)
     ((api 'observer-callback-enter!) id #t)
     ((api 'observer-callback-delivered!) id)
     (define outcome ((api 'observer-final-outcome)))
     (check-equal? (hash-ref outcome 'monitor_messages) 4)
     (check-equal? (hash-ref outcome 'monitor_pair_messages) 1)
     (check-equal? (hash-ref outcome 'monitor_empty_messages) 1)
     (check-equal? (hash-ref outcome 'monitor_string_errors) 1)
     (check-equal? (hash-ref outcome 'monitor_other_messages) 1)
     (check-true (hash-ref (car (hash-ref outcome 'monitor_errors)) 'truncated))
     (check-equal? (string-length (hash-ref (car (hash-ref outcome 'monitor_errors)) 'message)) 512)
     (check-false (regexp-match? #rx"private-trace" (jsexpr->string ((api 'observer-summary))))))))

(test-case "Same-length wrong contents and WXME never match plain-text final"
  (fresh
   (lambda (api)
     (register api)
     ((api 'observer-request!) (request (make-string (string-length final) #\x)))
     ((api 'observer-request!) (request (string->bytes/utf-8 final)))
     (check-equal? (map (lambda (r) (hash-ref r 'final_match))
                        (hash-ref ((api 'observer-summary)) 'records)) '(#f #f)))))

(test-case "Actual request settings have a bounded explicit truncation flag"
  (fresh
   (lambda (api)
     (register api)
     ((api 'observer-request!) (request final source (make-prefab-struct 'prefab-module-settings (make-string 5000 #\s))))
     (define r (car (hash-ref ((api 'observer-summary)) 'records)))
     (check-equal? (string-length (hash-ref r 'actual_prefab)) 1024)
     (check-true (hash-ref r 'actual_prefab_truncated)))))

(test-case "Non-OOM abnormal, exception tags, and duplicate terminal failure are retained"
  (fresh
   (lambda (api)
     (register api)
     (define id ((api 'observer-request!) (request final)))
     ((api 'observer-terminal!) id (vector 'abnormal-termination "Expansion thread terminated unexpectedly" '() '()))
     (define terminal (hash-ref (car ((api 'observer-final-terminals))) 'terminal))
     (check-false (hash-ref terminal 'explicit_out_of_memory))
     (define exn-id ((api 'observer-request!) (request final)))
     ((api 'observer-terminal!) exn-id (vector 'exn:variable '("PRIVATE FULL SOURCE PAYLOAD") '()))
     (define summary ((api 'observer-summary)))
     (check-false (regexp-match? #rx"PRIVATE FULL SOURCE" (jsexpr->string summary)))
     (check-equal? (hash-ref (hash-ref (last (hash-ref summary 'records)) 'terminal) 'tag) "exn:variable")
     ((api 'observer-terminal!) exn-id success)
     (check-false (hash-ref ((api 'observer-summary)) 'complete_observation)))))

(test-case "Capped records fail closed and retain all prior capped outcomes"
  (fresh
   (lambda (api)
     (register api)
     (for ([i (in-range 513)])
       (define id ((api 'observer-request!) (request final)))
       (when id ((api 'observer-terminal!) id success)))
     (define summary ((api 'observer-summary)))
     (check-equal? (hash-ref summary 'request_count) 513)
     (check-equal? (length (hash-ref summary 'records)) 512)
     (check-equal? (hash-ref summary 'dropped_requests) 1)
     (check-false (hash-ref summary 'complete_observation))
     (check-false ((api 'observer-final-outcome))))))

(test-case "Registration is single-shot, required, and default-off"
  (fresh
   (lambda (api)
     (check-false ((api 'observer-request!) (request final)))
     (check-equal? (hash-ref ((api 'observer-summary)) 'observer_error_count) 1)))
  (fresh
   (lambda (api)
     (register api)
     (check-exn exn:fail? (lambda () (register api)))))
  (fresh
   (lambda (api)
     (putenv "OPENRACKET_COMPACT_OBSERVER" "0")
     (check-exn exn:fail? (lambda () (register api))))))))

;; Mock xref modules isolate the observer's activation proof logic. They do not
;; stand in for the native GUI/real handler-registry test required for acceptance.
(define (check-worker variant)
   (define dir (make-temporary-file "compact-observer-test-~a" 'directory))
   (dynamic-wind
     void
     (lambda ()
       (define private (build-path dir "drracket" "private" "syncheck"))
       (make-directory* private)
       (call-with-output-file (build-path private "xref.rkt")
         (lambda (out)
           (display "#lang racket/base\n" out)
           (unless (eq? variant 'stock)
             (fprintf out "(provide openracket-xref-reply-cell-enabled?)\n(define openracket-xref-reply-cell-enabled? ~s)\n"
                      (eq? variant 'enabled)))))
       (fresh
        (lambda (api)
          (parameterize ([current-library-collection-paths (cons dir (current-library-collection-paths))])
            (putenv "OPENRACKET_COMPACT_OBSERVER_OUTPUT" (path->string dir))
            (unless (eq? variant 'uninstantiated) (dynamic-require 'drracket/private/syncheck/xref #f))
            (cond
              [(eq? variant 'uninstantiated)
               (check-false ((api 'observer-worker-init!) '(((drracket/private/syncheck/xref go) #f)
                                                           ((drracket/private/syncheck/xref monitor) #t)) 134217728))
               (check-false (file-exists? (build-path dir "worker-init.json")))]
              [else
               (define rec ((api 'observer-worker-init!) '(((drracket/private/syncheck/xref go) #f)
                                                          ((drracket/private/syncheck/xref monitor) #t)) 134217728))
               (check-true (hash-ref rec 'xref_already_instantiated))
               (check-true (hash-ref rec 'memory_accounting_available))
               (check-equal? (hash-ref rec 'memory_accounting_available)
                             (custodian-memory-accounting-available?))
               (check-equal? (hash-ref rec 'child_memory_limit) 134217728)
               (check-equal? (hash-ref rec 'xref_export_status) (if (eq? variant 'stock) "missing" "boolean"))
               (check-equal? (hash-ref rec 'xref_reply_cell_enabled)
                             (case variant [(stock) 'null] [(enabled) #t] [else #f]))
               (check-equal? (string-length (hash-ref rec 'xref_sha256)) 64)
               (check-equal? (map (lambda (row) (hash-ref row 'export)) (hash-ref rec 'actual_handler_registry))
                             '("go" "monitor"))
               (check-equal? (map (lambda (row) (hash-ref row 'monitor)) (hash-ref rec 'actual_handler_registry))
                             '(#f #t))
               (check-equal? (map (lambda (row) (hash-ref row 'module)) (hash-ref rec 'actual_handler_registry))
                             (make-list 2 (path->string (build-path private "xref.rkt"))))
               (check-equal? (call-with-input-file (build-path dir "worker-init.json") read-json) rec)
               (check-true (file-exists? (build-path dir "worker-init-overhead.json")))])))))
     (lambda () (delete-directory/files dir))))

;; A real hook is stopped on either side of its shared CAS commit. This does
;; not depend on dynamic-wind, break cleanup, or semaphore cleanup under kill.
(define (check-killed-hook hook-kind phase mode)
  (fresh
   (lambda (api)
     (register api)
     (define id (and (not (eq? hook-kind 'request)) ((api 'observer-request!) (request final))))
     (define test-hook (dynamic-require `(submod ,support test-support) 'observer-test-commit-hook))
     (define reached (make-semaphore 0))
     (define hold (make-semaphore 0))
     (define cust (make-custodian))
     (define worker
       (parameterize ([current-custodian cust]
                      [test-hook (lambda (where)
                                   (when (eq? where phase)
                                     (semaphore-post reached)
                                     (semaphore-wait hold)))])
         (thread (lambda ()
                   (case hook-kind
                     [(request) ((api 'observer-request!) (request final))]
                     [(status) ((api 'observer-status!) id 'finished-expansion)]
                     [(response) ((api 'observer-response!) id success)])))))
     (unless (sync/timeout 2 reached)
       (custodian-shutdown-all cust)
       (error 'kill-regression "Hook did not reach the selected CAS checkpoint"))
     (case mode
       [(kill) (kill-thread worker)]
       [(custodian) (custodian-shutdown-all cust)])
     (unless (sync/timeout 2 (thread-dead-evt worker))
       (custodian-shutdown-all cust)
       (error 'kill-regression "Hook thread did not terminate"))
     (define reply (make-channel))
     (define query
       (thread (lambda ()
                 (channel-put reply (vector ((api 'observer-summary)) ((api 'observer-final-outcome)))))))
     (define answer (sync/timeout 2 reply))
     (unless answer
       (kill-thread query)
       (custodian-shutdown-all cust)
       (error 'kill-regression "GUI-style observer read blocked after killed hook"))
     (check-true (hash-ref (vector-ref answer 0) 'complete_observation))
     (check-false (vector-ref answer 1))
     ;; Later original hooks can commit and finish normally after the kill.
     (define later ((api 'observer-request!) (request final)))
     ((api 'observer-response!) later success)
     ((api 'observer-callback-enter!) later #t)
     ((api 'observer-callback-delivered!) later)
     (check-equal? (hash-ref ((api 'observer-final-outcome)) 'request_id) later)
     (custodian-shutdown-all cust))))

(define all-tests
  (test-suite "Compact native observer helpers (synthetic protocol; no GUI claims)"
    protocol-tests
    (test-case "Worker already-instantiated stock missing export" (check-worker 'stock))
    (test-case "Worker already-instantiated export disabled" (check-worker 'disabled))
    (test-case "Worker already-instantiated export enabled" (check-worker 'enabled))
    (test-case "Worker never fabricates instantiation evidence" (check-worker 'uninstantiated))
    (test-case "Killed hooks never block later GUI reads or hooks"
      (for* ([hook-kind '(request status response)] [phase '(before after)] [mode '(kill custodian)])
        (check-killed-hook hook-kind phase mode)))))
(exit (if (zero? (run-tests all-tests)) 0 1))
