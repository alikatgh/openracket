#lang racket/base
;; Native-free contracts. These do not compile or execute the GUI observer.
(require rackunit racket/file racket/list racket/match racket/path racket/runtime-path "../contract.rkt")
(define config
  (hash 'schema 1 'run_id "unique-run-0001" 'mode "coldfile"
        'output_dir "/ci/output" 'app_path "/ci/Preview λ's.app"
        'native_executable_path "/ci/Preview λ's.app/Contents/MacOS/OpenRacket-native"
        'bundle_id "org.openracket.preview.test" 'profile_path "/ci/source/profile"
        'memory_mib "256" 'files '("/ci/one λ.rkt" "/ci/two's.rkt")
        'step_tokens (hash 'coldfile "cold-token-001" 'warmfile "warm-token-001" 'duplicate "dupe-token-001")))
(define (control step kind)
  (hash 'schema 1 'run_id (hash-ref config 'run_id) 'step step
        'token (hash-ref (hash-ref config 'step_tokens) (string->symbol step))
        (if (eq? kind 'ack) 'capture_ok 'open_exit) (if (eq? kind 'ack) #t 0)))
(test-case "valid coldfile contract and exact expected file sets"
  (check-equal? (validate-config config) config)
  (check-equal? (step-names config) '("coldfile" "warmfile" "duplicate"))
  (check-equal? (expected-files config "coldfile") '("/ci/one λ.rkt"))
  (check-equal? (expected-files config "warmfile") (hash-ref config 'files))
  (check-equal? (expected-files config "duplicate") (hash-ref config 'files)))
(test-case "coldempty contract has one future file and no initial document path"
  (define c (hash-set* config 'mode "coldempty" 'files '("/ci/warm λ.rkt")
                      'step_tokens (hash 'coldempty "cold-token-001" 'warmfile "warm-token-001" 'duplicate "dupe-token-001")))
  (check-equal? (validate-config c) c)
  (check-equal? (expected-files c "coldempty") '())
  (check-equal? (expected-files c "warmfile") '("/ci/warm λ.rkt")))
(test-case "missing and unknown config fields fail closed"
  (for ([key (in-list (hash-keys config))])
    (check-exn exn:fail? (lambda () (validate-config (hash-remove config key)))))
  (check-exn exn:fail? (lambda () (validate-config (hash-set config 'unknown #t)))))
(test-case "malformed scalar, mode, traversal, path, tokens and file cardinality fail"
  (for ([bad (in-list (list (hash-set config 'schema 2) (hash-set config 'schema 1.0)
                            (hash-set config 'schema #t) (hash-set config 'schema "1") (hash-set config 'mode "open")
                            (hash-set config 'run_id "../escape") (hash-set config 'run_id "short")
                            (hash-set config 'output_dir "relative") (hash-set config 'app_path "/ci/bad\npath")
                            (hash-set config 'files '("/ci/a" "/ci/a"))
                            (hash-set config 'files '("/ci/a"))
                            (hash-set config 'step_tokens (hash 'coldfile "same-token" 'warmfile "same-token" 'duplicate "same-token"))))])
    (check-exn exn:fail? (lambda () (validate-config bad)))))
(test-case "strict memory values preserve bytes and unlimited false"
  (check-equal? (parse-expected-memory-limit "256") 268435456)
  (check-equal? (parse-expected-memory-limit "0008") 8388608)
  (check-false (parse-expected-memory-limit "unlimited"))
  (for ([v '(#f "" "7" "-128" "+128" "128.0" "128e0" "128/1" " 128" "128 " "１２８" "UNLIMITED" "#f")])
    (check-exn exn:fail? (lambda () (parse-expected-memory-limit v)))))
(test-case "each ACK requires exact run/step/token and actual true capture flag"
  (for ([step (in-list (step-names config))])
    (define good (control step 'ack))
    (check-true (control-valid? good config step 'ack))
    (for ([bad (in-list (list (hash-remove good 'token) (hash-set good 'schema 1.0)
                              (hash-set good 'schema #t) (hash-set good 'schema "1") (hash-set good 'token "other-token")
                              (hash-set good 'run_id "other-run-0001") (hash-set good 'step "other")
                              (hash-set good 'capture_ok "true") (hash-set good 'capture_ok #f)))])
      (check-false (control-valid? bad config step 'ack)))))
(test-case "sent receipt requires zero external open exit; no truthy coercion"
  (define good (control "warmfile" 'sent))
  (check-true (control-valid? good config "warmfile" 'sent))
  (for ([bad '(#f #t "0" 1 -1 0.0)])
    (check-false (control-valid? (hash-set good 'open_exit bad) config "warmfile" 'sent)))
  (check-false (control-valid? (control "coldfile" 'sent) config "warmfile" 'sent))
  (check-false (control-valid? good config "warmfile" 'ack)))
(test-case "safe unique path and exact JSON false and Unicode behavior"
  (check-equal? (path->string (control-path config "warmfile" "ready")) "/ci/output/unique-run-0001.warmfile.ready.json")
  (check-equal? (json-safe (hash 'false #f 'null 'null 'path (string->path "/ci/λ")))
                (hash 'false #f 'null 'null 'path "/ci/λ")))
(test-case "JSON reader rejects trailing values, malformed, and oversized controls"
  (define path (make-temporary-file "observer-contract~a.json"))
  (dynamic-wind void
    (lambda ()
      (for ([text '("{} {}" "{" "true false")])
        (display-to-file text path #:exists 'truncate)
        (check-exn exn:fail? (lambda () (read-json-file path))))
      (display-to-file (make-string 65537 #\space) path #:exists 'truncate)
      (check-exn #rx"Oversized" (lambda () (read-json-file path))))
    (lambda () (delete-file path))))

(test-case "existing native aliases and trailing directory syntax compare canonically"
  (define root (make-temporary-file "observer-alias~a" 'directory))
  (dynamic-wind void
    (lambda ()
      (define target (build-path root "actual λ directory"))
      (define alias (build-path root "alias"))
      (make-directory target)
      (make-file-or-directory-link target alias)
      (display-to-file "#lang racket/base\n" (build-path target "fixture.rkt"))
      (check-equal? (canonical target) (canonical alias))
      (check-equal? (canonical target) (canonical (path->directory-path target)))
      (check-equal? (canonical (build-path alias "fixture.rkt"))
                    (canonical (build-path target "fixture.rkt")))
      (check-exn exn:fail? (lambda () (canonical (build-path root "missing"))))
      (when (and (eq? (system-type 'os) 'macosx)
                 (directory-exists? "/var") (directory-exists? "/private/var"))
        (check-equal? (canonical "/var") (canonical "/private/var"))))
    (lambda () (delete-directory/files root))))
