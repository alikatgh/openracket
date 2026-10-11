#lang racket/base
;; Build-time only. Invoke with the explicitly selected official Racket runtime.
;; No GUI launch, package installation, or source embedding is requested here.
(require launcher/launcher)
(unless (and (equal? (version) "9.3") (eq? (system-type) 'macosx))
  (error 'openracket-app "requires official full Racket 9.3 on macOS"))
(define argv (current-command-line-arguments))
(unless (= (vector-length argv) 1)
  (error 'openracket-app "expected a fresh destination .app path"))
(define destination (vector-ref argv 0))
(when (or (file-exists? destination)
          (directory-exists? destination)
          (link-exists? destination))
  (error 'openracket-app "refusing an existing destination"))
;; Non-script variant: on macOS this creates the official native application
;; launcher, retaining absolute references to this installation. Flags arrive
;; from the unchanged preview launcher via the narrowly scoped dispatcher.
(parameterize ([current-launcher-variant (system-type 'gc)])
  (make-gracket-launcher null destination '((relative? . #f))
                        #:tether-mode #f))
