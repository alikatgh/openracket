#lang racket/base
;; Test-only activation witness, then the unchanged real-host Check Syntax gate.
(require racket/file racket/runtime-path file/sha1 json)
(define-runtime-path manifest-path "../../experiments/interval-map/manifest.json")
(define-runtime-path host-path "../../experiments/interval-map/tests/independent-native-host.rkt")
(define mode (getenv "OPENRACKET_INTERVAL_EXPECT_MODE"))
(unless (member mode '("stock" "candidate-on"))
  (error 'interval-host "Expected explicit stock or candidate-on arm"))
(unless (and (equal? (getenv "OPENRACKET_UI") "stock")
             (equal? (getenv "OPENRACKET_NATIVE_CASE") "check-syntax")
             (zero? (vector-length (current-command-line-arguments))))
  (error 'interval-host "Use the unchanged stock-appearance Check Syntax harness without argv"))
(define manifest (call-with-input-file manifest-path read-json))
(define path (collection-file-path "interval-map.rkt" "data"))
(define sha (call-with-input-file path (lambda (in) (bytes->hex-string (sha256-bytes in)))))
(define expected (hash-ref manifest (if (equal? mode "stock") 'original_sha256 'patched_sha256)))
(unless (equal? sha expected) (error 'interval-host "Installed source hash differs from exact selected arm"))
(define selected
  (dynamic-require 'data/interval-map 'openracket-interval-map-fast-set-enabled?
                   (lambda () 'absent)))
(unless (if (equal? mode "stock")
            (and (not (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET")) (eq? selected 'absent))
            (and (equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1") (eq? selected #t)))
  (error 'interval-host "Wrong actual host-process interval-map selection"))
(printf "OPENRACKET_INTERVAL_HOST_ACTIVATION ~a\n"
        (jsexpr->string (hasheq 'mode mode 'status "verified" 'path (path->string path)
                               'sha256 sha 'enabled (eq? selected #t))))
(flush-output)
(dynamic-require host-path #f)
