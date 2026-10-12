#lang racket/base
;; Native-unrun setup -- --boot continuation. Keep this independent of helpers.
(require compiler/cm)
(provide go)
;; Resolve every component using base path APIs; no path helper module is loaded
;; into the bootstrap namespace merely to validate identity.
(define (physical p [links 0])
  (when (>= links 64) (error 'core-first "Too many symbolic links"))
  (define full (simplify-path (path->complete-path p)))
  (define-values (base name directory?) (split-path full))
  (define parent (and (path? base) (physical base links)))
  (define next (if parent (build-path parent name) full))
  (if (link-exists? next)
      (physical (path->complete-path (resolve-path next) (or parent (current-directory)))
                (add1 links))
      next))
(define (hex bs)
  (apply string-append
         (for/list ([byte (in-bytes bs)])
           (define str (number->string byte 16))
           (if (= (string-length str) 1) (string-append "0" str) str))))
(define (go original-compiled-paths)
  (unless (and (equal? original-compiled-paths (list (string->path "compiled")))
               (equal? (getenv "PLT_ZO_PATH") "compiled"))
    (error 'core-first "Unexpected compiled-subdirectory configuration"))
  (define self (resolved-module-path-name
                (variable-reference->resolved-module-path (#%variable-reference))))
  (define-values (helper-root helper-name helper-directory?) (split-path self))
  (define workspace (physical (build-path helper-root 'up)))
  (define expected-root (physical (build-path workspace "compiled")))
  (unless (and (= (length (current-compiled-file-roots)) 1)
               (complete-path? (car (current-compiled-file-roots)))
               (equal? (physical (car (current-compiled-file-roots))) expected-root)
               (equal? (getenv "PLTCOMPILEDROOTS") (path->string expected-root)))
    (error 'core-first "The preapproved sole absolute W/compiled root is required"))
  (define expected-source
    (physical (build-path workspace "runtime" "collects" "racket" "private" "class-internal.rkt")))
  (define source (physical (collection-file-path "class-internal.rkt" "racket" "private")))
  (unless (equal? source expected-source)
    (error 'core-first "Resolved class source is not the exact approved clone source"))
  (define flag (getenv "OPENRACKET_OBJECT_HASH_PROBE"))
  (define expected-sha256
    (cond [(not flag) "1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f"]
          [(equal? flag "0") "808a728997c4f085a98fe5c30793c821d9a1097373431addd411370ba2d161d6"]
          [else (error 'core-first "Expected stock unset or diagnostic 0 during compilation")]))
  (unless (equal? (hex (call-with-input-file source sha256-bytes)) expected-sha256)
    (error 'core-first "Resolved class source SHA-256 differs from the approved arm"))
  (printf "CORE_SOURCE ~s ~a\n" source expected-sha256)
  (parameterize ([current-namespace (make-base-empty-namespace)]
                 [trust-existing-zos #f]
                 [managed-recompile-only #f]
                 [managed-recompile-cache-dir #f]
                 [manager-skip-file-handler (lambda (p) #f)]
                 [manager-compile-notify-handler
                  (lambda (p) (printf "CORE_COMPILE_START ~s\n" p))])
    (managed-compile-zo source))
  ;; Completion is accepted only with independent source/.zo/.dep receipts.
  (printf "CORE_COMPILE_RETURNED ~s\n" source)
  (flush-output))
