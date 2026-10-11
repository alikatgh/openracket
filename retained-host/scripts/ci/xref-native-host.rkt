#lang racket/base
;; Test-only activation witness, then the unchanged real-host Check Syntax gate.
(require racket/file racket/runtime-path file/sha1 json)
(define-runtime-path manifest-path "../../experiments/xref-reply/manifest.json")
(define-runtime-path host-path "../../tests/independent-native-host.rkt")
(define mode (getenv "OPENRACKET_XREF_EXPECT_MODE"))
(unless (member mode '("stock" "candidate-on"))
  (error 'xref-host "Expected explicit stock or candidate-on arm"))
(unless (and (equal? (getenv "OPENRACKET_UI") "stock")
             (equal? (getenv "OPENRACKET_NATIVE_CASE") "check-syntax")
             (zero? (vector-length (current-command-line-arguments))))
  (error 'xref-host "Use the unchanged stock-appearance Check Syntax harness without argv"))
(define manifest (call-with-input-file manifest-path read-json))
(define path (collection-file-path "xref.rkt" "drracket" "private" "syncheck"))
(define sha (call-with-input-file path (lambda (in) (bytes->hex-string (sha256-bytes in)))))
(define expected (hash-ref manifest (if (equal? mode "stock") 'original_sha256 'patched_sha256)))
(unless (equal? sha expected) (error 'xref-host "Installed source hash differs from exact selected arm"))
(define selected
  (dynamic-require 'drracket/private/syncheck/xref 'openracket-xref-reply-cell-enabled?
                   (lambda () 'absent)))
(unless (if (equal? mode "stock")
            (and (not (getenv "OPENRACKET_XREF_REPLY_CELL")) (eq? selected 'absent))
            (and (equal? (getenv "OPENRACKET_XREF_REPLY_CELL") "1") (eq? selected #t)))
  (error 'xref-host "Wrong actual host-process xref selection"))
(printf "OPENRACKET_XREF_HOST_ACTIVATION ~a\n"
        (jsexpr->string (hasheq 'mode mode 'status "verified" 'path (path->string path)
                               'sha256 sha 'enabled (eq? selected #t))))
(flush-output)
(dynamic-require host-path #f)
