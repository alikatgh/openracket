#lang racket/base
;; Executes the actual bridge definition with Framework's before-commit callback
;; ordering. No GUI import, no replacement production bridge, no physical display.
(require rackunit racket/list racket/match racket/runtime-path)
(define-runtime-path source "../tool/tool.rkt")
(define forms
  (match (parameterize ([read-accept-reader #t]) (call-with-input-file source read))
    [`(module ,_ ,_ (#%module-begin ,forms ...)) forms]))
(define (definition-name form)
  (match form [`(define (,name ,_ ...) ,_ ...) name]
    [`(define ,(? symbol? name) ,_ ...) name] [_ #f]))

(define (bridge [initial-dark? #f] #:present? [present? #t])
  (define dark? initial-dark?)
  (define painter 'auto)
  (define role-labels #f)
  (define queued '())
  (define refresh-count 0)
  (define color-callbacks '())
  (define mode-callbacks '())
  (define (queue thunk . priority) (set! queued (append queued (list thunk))))
  (define ns (make-base-namespace))
  (parameterize ([current-namespace ns])
    (namespace-require 'racket/class)
    (eval '(define-syntax-rule (string-constant key) (symbol->string 'key)))
    (for ([name '(optional-painter-export color-prefs:white-on-black-color-scheme?
                                         color-prefs:register-color-scheme-entry-change-callback
                                         preferences:add-callback queue-callback get-top-level-windows refresh-retained-toolbars!)]
          [proc (list
                 (lambda (name)
                   (and present? (case name
                                   [(set-modern-host-theme!) (lambda (value) (set! painter value))]
                                   [(set-modern-role-labels!) (lambda (value) (set! role-labels value))]
                                   [else #f])))
                 (lambda () dark?)
                 (lambda (key callback . unused) (set! color-callbacks (cons callback color-callbacks)))
                 (lambda (key callback . unused) (set! mode-callbacks (cons callback mode-callbacks)))
                 queue
                 (lambda () '())
                 (lambda () (set! refresh-count (add1 refresh-count))))])
      (namespace-set-variable-value! name proc #t))
    (for ([form (in-list forms)]
          #:when (memq (definition-name form) '(synchronize-painter! install-painter-bridge!)))
      (eval form))
    ((eval 'install-painter-bridge!)))
  (define (transition! next #:background? [background? #t])
    ;; Official Framework checks callbacks BEFORE writing its new preference.
    (for ([callback (in-list mode-callbacks)]) (callback 'framework:white-on-black-mode? next))
    (when background?
      (for ([callback (in-list color-callbacks)]) (callback 'new-background)))
    (set! dark? next))
  (define (drain!)
    (let loop ()
      (unless (null? queued)
        (define thunk (car queued))
        (set! queued (cdr queued))
        (thunk)
        (loop))))
  (values (lambda () painter) transition! drain! (lambda () (length queued))
          (lambda () role-labels)
          (lambda () (parameterize ([current-namespace ns]) ((eval 'synchronize-painter!))))
          (lambda () refresh-count)))

(test-case "initial bridge follows current committed light mode"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (check-eq? (p) 'light)
  (check-true (hash? (roles))))
(test-case "initial bridge follows current committed dark mode"
  (define-values (p change drain queued roles sync refreshes) (bridge #t))
  (check-eq? (p) 'dark))
(test-case "before-commit light to dark callback uses committed mode next event"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (change #t)
  (check-equal? (queued) 1)
  (drain)
  (check-eq? (p) 'dark))
(test-case "dark to light to dark stays synchronized across repeated preference toggles"
  (define-values (p change drain queued roles sync refreshes) (bridge #t))
  (change #f) (drain) (check-eq? (p) 'light)
  (change #t) (drain) (check-eq? (p) 'dark))
(test-case "two mode changes before dispatch coalesce and read the newest mode"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (change #t) (change #f)
  (check-equal? (queued) 1)
  (drain)
  (check-eq? (p) 'light))
(test-case "custom equal-background schemes still synchronize through mode callback"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (change #t #:background? #f)
  (drain)
  (check-eq? (p) 'dark))
(test-case "post-transaction synchronization reads committed state immediately"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (change #t)
  (sync)
  (check-eq? (p) 'dark)
  (drain)
  (check-eq? (p) 'dark))
(test-case "missing optional painter registers no callbacks or mutation"
  (define-values (p change drain queued roles sync refreshes) (bridge #:present? #f))
  (change #t) (drain) (sync)
  (check-eq? (p) 'auto)
  (check-false (roles))
  (check-equal? (queued) 0))

(test-case "committed mode synchronization requests a retained toolbar repaint"
  (define-values (p change drain queued roles sync refreshes) (bridge))
  (define before (refreshes))
  (change #t) (drain)
  (check-true (> (refreshes) before)))
