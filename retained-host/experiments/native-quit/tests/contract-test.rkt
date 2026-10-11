#lang racket/base
;; Actual pure Racket contracts. NOT RUN locally; later official9.3 native gate.
(require rackunit racket/file racket/list racket/path "../driver/contract.rkt")
(define root (make-temporary-file "quit-contract-~a" 'directory))
(define original "#lang racket/base\n(define answer 42)\n")
(define edited (string-append original ";; intended edit λ 日本語\n"))
(define (str p) (path->string p))
(for ([p '("profile" "evidence" "app/Contents/MacOS" "runtime")]) (make-directory* (build-path root p)))
(define fixture (build-path root "Quit λ's.rkt"))
(display-to-file original fixture)
(display-to-file "unit-only" (build-path root "app/Contents/MacOS/native"))
(define c0
  (hash 'schema 1 'run_id "quit-contract-run-000001" 'mode "stock" 'case "save"
        'root_dir (str root) 'output_dir (str (build-path root "evidence"))
        'profile_path (str (build-path root "profile")) 'app_path (str (build-path root "app"))
        'native_executable_path (str (build-path root "app/Contents/MacOS/native"))
        'runtime_root (str (build-path root "runtime")) 'bundle_id "org.example.contract"
        'fixture_path (str fixture) 'original_text original 'edited_text edited
        'memory_mib 128 'process_timeout_seconds 150 'step_tokens (hash)))
(define c (hash-set c0 'step_tokens
                    (for/hash ([stage (in-list (step-names c0))] [i (in-naturals)])
                      (values (string->symbol stage) (format "unique-stage-token-~a" i)))))
(dynamic-wind
 void
 (lambda ()
   (test-case "strict valid config and exact stage order"
     (check-equal? (validate-config c) c)
     (check-equal? (step-names c) '("ready" "dirty" "quit-confirm-1" "unsaved-1" "cancelled" "quit-confirm-2" "unsaved-2" "terminal-response")))
   (test-case "missing or additional config keys refused"
     (for ([key (in-list (hash-keys c))])
       (check-exn exn:fail? (lambda () (validate-config (hash-remove c key)))))
     (check-exn exn:fail? (lambda () (validate-config (hash-set c 'extra #t)))))
   (test-case "known modes cases memory schema and frozen deadline"
     (for ([pair (in-list (list (cons 'schema #t) (cons 'schema 1.0) (cons 'mode "modern-light")
                                (cons 'case "save-as") (cons 'memory_mib 256)
                                (cons 'process_timeout_seconds 151)))])
       (check-exn exn:fail? (lambda () (validate-config (hash-set c (car pair) (cdr pair)))))))
   (test-case "append-only plain-text edit contract"
     (for ([text (list original "#lang racket/base\nreplacement\n"
                      (string-append original "code\n") (string-append original ";; " (make-string 4097 #\x) "\n"))])
       (check-exn exn:fail? (lambda () (validate-config (hash-set c 'edited_text text))))))
   (test-case "safe existing canonical paths and managed symlink refusal"
     (check-true (contained? fixture root))
     (check-false (contained? root root))
     (define alias (build-path root "alias.rkt"))
     (make-file-or-directory-link fixture alias)
     (check-equal? (canonical fixture) (canonical alias))
     (check-exn exn:fail? (lambda () (validate-config (hash-set c 'fixture_path (str alias))))))
   (test-case "mismatched initial bytes refused without repair"
     (display-to-file "wrong" fixture #:exists 'truncate)
     (check-exn exn:fail? (lambda () (validate-config c)))
     (check-equal? (file->string fixture) "wrong")
     (display-to-file original fixture #:exists 'truncate))
   (test-case "ACK requires exact positive capture and fresh stage envelope"
     (define good (hash-set (envelope c "ready") 'capture_ok #t))
     (check-true (ack-valid? good c "ready"))
     (for ([bad (list (hash-set good 'capture_ok #f) (hash-set good 'capture_ok "true")
                      (hash-set good 'token "different-token-0001") (hash-set good 'stage "dirty")
                      (hash-set good 'extra #f) (hash-set good 'schema 1.0))])
       (check-false (ack-valid? bad c "ready"))))
   (test-case "bounded JSON rejects oversized and trailing values"
     (define p (build-path root "control.json"))
     (for ([text (list "{} {}" "{" (make-string 65537 #\space))])
       (display-to-file text p #:exists 'truncate)
       (check-exn exn:fail? (lambda () (read-json-file p))))))
 (lambda () (delete-directory/files root)))
