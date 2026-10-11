#lang racket/base
;; Direct supervised headless entrypoint; no GUI, no native-pass claim.
(require rackunit racket/list json "native-light-state-contract.rkt"
         "native-tool-failure-diagnostics.rkt"
         (only-in rackunit/private/check-info pretty-info? pretty-info-value))
(define arguments (current-command-line-arguments))
(unless (or (equal? arguments #()) (equal? arguments #("--inject-wrong-painter")))
  (error 'native-light-state "Unsupported arguments"))
(define (ordinary-hashes value)
  (cond [(hash? value) (for/hash ([(key item) (in-hash value)])
                        (values key (ordinary-hashes item)))]
        [(list? value) (map ordinary-hashes value)]
        [else value]))
(parameterize ([current-check-handler raise])
  (check-equal? (validate-light-state! expected-light-state) expected-light-state)
  (define ordinary (ordinary-hashes expected-light-state))
  (check-true (hash-equal? ordinary))
  (check-true (hash-equal? (hash-ref ordinary 'native)))
  (check-true (hash-eq? expected-light-state))
  (check-not-exn (lambda () (validate-light-state! ordinary)))
  (define json-roundtrip (read-json (open-input-string (jsexpr->string ordinary))))
  (check-true (hash-eq? (hash-ref json-roundtrip 'native)))
  (check-not-exn (lambda () (validate-light-state! json-roundtrip)))
  (for ([key (in-list (hash-keys expected-light-state))])
    (check-exn exn:test:check?
               (lambda () (validate-light-state! (hash-remove expected-light-state key))))
    (check-exn exn:test:check?
               (lambda () (validate-light-state! (hash-set expected-light-state key "wrong")))))
  (for ([key (in-list (hash-keys (hash-ref expected-light-state 'painter_palette)))])
    (check-exn exn:test:check?
               (lambda ()
                 (validate-light-state!
                  (hash-set expected-light-state 'painter_palette
                            (hash-set (hash-ref expected-light-state 'painter_palette) key '(0 0 0)))))))
  (for ([key '(backend explicit-name effective-name increase-contrast?)])
    (check-exn exn:test:check?
               (lambda ()
                 (validate-light-state!
                  (hash-set expected-light-state 'native
                            (hash-remove (hash-ref expected-light-state 'native) key)))))
    (check-exn exn:test:check?
               (lambda ()
                 (validate-light-state!
                  (hash-set expected-light-state 'native
                            (hash-set (hash-ref expected-light-state 'native) key "wrong"))))))
  (for ([bad (list #f '() (hash-set expected-light-state 'extra #t)
                   (hash-set expected-light-state 'mode_preference 'platform)
                   (hash-set expected-light-state 'mode_preference 0)
                   (hash-set expected-light-state 'painter_modern 1)
                   (hash-set expected-light-state 'palette_background '(247.0 248 250))
                   (hash-set expected-light-state 'palette_background '(23 28 38))
                   (hash-set expected-light-state 'palette_foreground '(236 240 247)))])
    (check-exn exn:test:check? (lambda () (validate-light-state! bad))))
  (when (equal? arguments #("--inject-wrong-painter"))
    (displayln "OPENRACKET_NATIVE_LIGHT_STATE_INJECTING_FAILURE")
    (flush-output)
    (with-handlers
        ([exn:test:check?
          (lambda (failure)
            ;; Diagnostic formatting or flush failure cannot replace the exact
            ;; original check. The outer gate rejects a missing typed marker.
            (report-failure!
             failure
             (lambda (original)
              (define infos (exn:test:check-stack original))
              (define (unique name)
                (define matches (filter (lambda (info) (eq? (check-info-name info) name)) infos))
                (and (= (length matches) 1) (check-info-value (car matches))))
              (define actual (unique 'actual))
              (define expected (unique 'expected))
              (when (and (eq? (unique 'name) 'check-equal?)
                         (pretty-info? actual) (pretty-info? expected)
                         (equal? (pretty-info-value actual) "dark")
                         (equal? (pretty-info-value expected) "light"))
                (displayln "OPENRACKET_NATIVE_LIGHT_STATE_FAILURE exception=exn:test:check check=check-equal? actual=dark expected=light")
                (flush-output))))
            (raise failure))])
      (validate-light-state! (hash-set expected-light-state 'painter "dark")))))
(displayln "OPENRACKET_NATIVE_LIGHT_STATE_OK exact-palette-painter-cocoa-refusals")
(exit 0)
