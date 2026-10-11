#lang racket/base
;; Read-only metadata via public APIs. No private DrRacket member names.
(require racket/class racket/format racket/path)
(provide capture-language-settings)

(define (capture-language-settings editor fixture #:lookup [lookup dynamic-require])
  (define result (make-hasheq))
  (define errors (make-hasheq))
  (hash-set! result 'configuration_scope "pending next Run configuration from get-next-settings")
  (define missing (gensym 'missing))
  (define (capture key thunk #:format [format-value values])
    (with-handlers ([exn:fail?
                     (lambda (e)
                       (hash-set! errors key (exn-message e))
                       missing)])
      (define value (thunk))
      (hash-set! result key (format-value value))
      value))
  (define config
    (with-handlers ([exn:fail?
                     (lambda (e) (hash-set! errors 'selected_settings (exn-message e)) missing)])
      (send editor get-next-settings)))
  (define (lookup-setting name)
    (when (eq? config missing) (error 'settings-capture "selected settings unavailable"))
    ((lookup 'drracket/tool-lib name) config))
  (define language
    (with-handlers ([exn:fail?
                     (lambda (e) (hash-set! errors 'language_object (exn-message e)) missing)])
      (lookup-setting 'drracket:language-configuration:language-settings-language)))
  (define settings
    (with-handlers ([exn:fail?
                     (lambda (e) (hash-set! errors 'settings_object (exn-message e)) missing)])
      (lookup-setting 'drracket:language-configuration:language-settings-settings)))
  (unless (eq? language missing)
    (capture 'language_position (lambda () (send language get-language-position)) #:format ~s)
    (unless (eq? settings missing)
      (capture 'serialized_settings (lambda () (send language marshall-settings settings)) #:format ~s)))
  ;; In 9.3 the public annotations accessor's contract omits 'lang-default.
  ;; The documented six-element vector preserves that valid sixth field.
  (define simple-vector
    (capture 'simple_settings_vector
             (lambda ()
               (when (eq? settings missing) (error 'settings-capture "settings unavailable"))
               (define vector-value
                 ((lookup 'drracket/tool-lib 'drracket:language:simple-settings->vector) settings))
               (unless (and (vector? vector-value) (= 6 (vector-length vector-value)))
                 (error 'settings-capture "unexpected simple-settings vector"))
               vector-value)
             #:format ~s))
  (define annotations
    (if (eq? simple-vector missing) missing
        (capture 'annotations (lambda () (vector-ref simple-vector 5)) #:format ~s)))
  ;; This queries the fixture reader, not the editor's private get-irl method.
  ;; Our immutable benchmark fixtures use #lang racket/base. The benchmark edits
  ;; comments only, so the reader declaration remains identical to the source.
  (define default-instrumentation
    (capture 'language_default_instrumentation
             (lambda ()
               (define full-path (path->complete-path fixture))
               (parameterize ([current-directory (path-only full-path)]
                              [current-load-relative-directory (path-only full-path)])
                 (define info (call-with-input-file full-path read-language))
                 (unless (procedure? info) (error 'settings-capture "fixture has no #lang reader info"))
                 (define value (info 'drracket:default-instrumentation 'debug))
                 (unless (memq value '(none debug debug/profile test-coverage))
                   (error 'settings-capture "unsupported reader instrumentation response: ~s" value))
                 value))
             #:format ~s))
  (hash-set! result 'default_instrumentation_source
             "public read-language on immutable fixture; key drracket:default-instrumentation, fallback debug")
  (unless (or (eq? annotations missing)
              (and (eq? annotations 'lang-default) (eq? default-instrumentation missing)))
    (hash-set! result 'effective_annotations
               (~s (if (eq? annotations 'lang-default) default-instrumentation annotations))))
  (hash-set! result 'effective_annotations_evidence
             "selected language settings plus fixture reader default; no evaluator-state measurement")
  (hash-set! result 'errors errors)
  (hash-set! result 'status (if (zero? (hash-count errors)) "complete" "partial"))
  result)
