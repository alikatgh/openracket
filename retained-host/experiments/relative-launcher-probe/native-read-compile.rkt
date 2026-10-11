#lang racket/base
;; Separate future macOS gate. Reading/compiling does not invoke module bodies.
;; Use ONLY with a clean environment, explicit -A/-U/-R, and source/runtime
;; before/after witnesses. Native compilation has not been performed here.
(require compiler/cm racket/file)
(define files (vector->list (current-command-line-arguments)))
(unless (pair? files) (error 'native-gate "expected explicit source files"))
(for ([file (in-list files)])
  (call-with-input-file* file
    (lambda (in)
      (parameterize ([read-accept-reader #t])
        (unless (syntax? (read-syntax file in)) (error 'native-gate "no module"))
        (unless (eof-object? (read in)) (error 'native-gate "trailing input")))))
  (managed-compile-zo file))
(displayln "native-reader-and-compile: passed")
