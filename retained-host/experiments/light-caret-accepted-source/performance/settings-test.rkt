#lang racket/base
(require rackunit racket/class racket/file "settings.rkt")
(define language%
  (class object%
    (define/public (get-language-position) '("The Racket Language"))
    (define/public (marshall-settings settings) settings)
    (super-new)))
(define editor%
  (class object%
    (define/public (get-next-settings) 'configuration)
    (super-new)))
(define (lookup module name)
  (case name
    [(drracket:language-configuration:language-settings-language) (lambda (_) (new language%))]
    [(drracket:language-configuration:language-settings-settings) (lambda (_) '#(#t constructor repeating-decimal #f #t lang-default))]
    [(drracket:language:simple-settings->vector) values]
    [else (error 'fake "unexpected API: ~s" name)]))
(define fixture (make-temporary-file "metadata-fixture-~a.rkt"))
(dynamic-wind
 void
 (lambda ()
   (call-with-output-file fixture #:exists 'truncate
     (lambda (port) (display "#lang racket/base\n; no execution\n(error 'must-not-run)\n" port)))
   (define result (capture-language-settings (new editor%) fixture #:lookup lookup))
   (check-equal? (hash-ref result 'status) "complete")
   (check-equal? (hash-ref result 'annotations) "lang-default")
   (check-equal? (hash-ref result 'effective_annotations) "debug")
   (check-equal? (hash-ref result 'language_position) "(\"The Racket Language\")")
   (define partial
     (capture-language-settings
      (new editor%) fixture
      #:lookup (lambda (module name)
                 (if (eq? name 'drracket:language:simple-settings->vector)
                     (lambda (_) (error 'intentional "vector unavailable"))
                     (lookup module name)))))
   (check-equal? (hash-ref partial 'status) "partial")
   (check-equal? (hash-ref partial 'language_default_instrumentation) "debug")
   (check-true (hash-has-key? partial 'serialized_settings))
   (check-true (hash-has-key? (hash-ref partial 'errors) 'simple_settings_vector))
   (check-false (hash-has-key? partial 'effective_annotations)))
 (lambda () (delete-file fixture)))
