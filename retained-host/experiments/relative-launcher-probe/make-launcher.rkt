#lang racket/base
;; Source-only hypothesis. This file has NOT passed a Racket reader or compiler.
;; Official generator intrinsically applies its own ad-hoc signature. There is
;; no manual signing, signature removal, or security-policy operation here.
(require compiler/embed racket/path)
(unless (and (equal? (version) "9.3")
             (eq? (system-type 'os) 'macosx)
             (eq? (system-type 'gc) 'cs))
  (error 'relative-probe "requires the selected full native macOS Racket 9.3 CS"))
(define args (current-command-line-arguments))
(unless (= (vector-length args) 1)
  (error 'relative-probe "expected one fresh .app destination"))
(define dest (string->path (vector-ref args 0)))
(unless (and (complete-path? dest) (regexp-match? #rx"[.]app$" (path->string dest)))
  (error 'relative-probe "destination must be an absolute .app path"))
(when (or (file-exists? dest) (directory-exists? dest) (link-exists? dest))
  (error 'relative-probe "refusing occupied output; the generator replaces it"))
(define-values (parent leaf directory?) (split-path dest))
(unless (and (path? parent) (directory-exists? parent))
  (error 'relative-probe "destination parent must already exist"))
;; Generate the native skeleton BEFORE placing any payload in it. Explicit
;; paths avoid embed.rkt deriving references to the generator installation.
;; An empty built-in collection list intentionally tests the uncertain -X
;; restoration behavior. boot.rkt records it and refuses disabled link paths.
(create-embedding-executable
 dest #:gracket? #t #:launcher? #t #:variant 'cs
 #:modules null #:literal-files null #:cmdline null #:collects-path null
 #:aux '((relative? . #t)
         (forget-exe? . #t)
         (framework-root . "@executable_path/../Resources/runtime/lib/")
         (config-dir . "../Resources/runtime/etc")))
