#lang racket/base
;; Headless transaction tests execute the actual tool.rkt function datums against
;; an in-memory preference store. This is not a native Framework integration test.
(require rackunit racket/list racket/match racket/runtime-path)
(define-runtime-path source "../tool/tool.rkt")
(define-runtime-path helper "../tool/appearance-state.rkt")
(define-runtime-path layout "../tool/layout.rkt")
(define appearance-keys
  '(framework:color-scheme-light framework:color-scheme-dark framework:white-on-black-mode?
    framework:standard-style-list:font-name framework:standard-style-list:font-size
    framework:standard-style-list:smoothing))
(define initial
  (hash 'framework:color-scheme-light 'classic
        'framework:color-scheme-dark 'white-on-black
        'framework:white-on-black-mode? 'platform
        'framework:standard-style-list:font-name "Original Mono"
        'framework:standard-style-list:font-size (vector (hash '((1920 1080)) 21) 19)
        'framework:standard-style-list:smoothing 'default
        'openracket:appearance-enabled? #f
        'openracket:appearance-state 'fresh
        'openracket:appearance-snapshot #f))
(define forms
  (match (parameterize ([read-accept-reader #t]) (call-with-input-file source read))
    [`(module ,_ ,_ (#%module-begin ,forms ...)) forms]))
(define needed
  '(enabled-pref state-pref snapshot-pref synchronize-painter! native-controller native-committed?
                 startup-native-considered? native-state-write? native-state-generation set-appearance-state!
                 begin-native-state-transaction! set-painter-blended! current-native-mode modern-session? layout-enabled?
                 capture-appearance restore-snapshot! apply-appearance! initialize-once!))
(define (definition-name form)
  (match form [`(define (,name ,_ ...) ,_ ...) name]
    [`(define ,(? symbol? name) ,_ ...) name] [_ #f]))

(define (sandbox #:fail-key [fail-key #f] #:fail-before? [fail-before? #f]
                 #:schemes? [schemes? #t])
  (define prefs (hash-copy initial))
  (define fired? #f)
  (define known (if schemes? '(classic white-on-black |OpenRacket Light| |OpenRacket Dark|)
                    '(classic white-on-black)))
  (define (put! key value)
    (define fail? (and fail-key (eq? key fail-key) (not fired?)))
    (when (and fail? fail-before?) (set! fired? #t) (error 'fixture "pre-write failure"))
    (hash-set! prefs key value)
    (when fail? (set! fired? #t) (error 'fixture "post-write callback failure")))
  (define (get-scheme #:wob? dark?)
    (define v (hash-ref prefs (if dark? 'framework:color-scheme-dark 'framework:color-scheme-light)))
    (if (memq v known) v (if dark? 'white-on-black 'classic)))
  ;; Official 9.3 setter: an unknown name resolves to the first light scheme.
  (define (set-scheme! name)
    (define actual (if (memq name known) name 'classic))
    (put! (if (memq actual '(white-on-black |OpenRacket Dark|))
              'framework:color-scheme-dark 'framework:color-scheme-light) actual))
  (define ns (make-base-namespace))
  (parameterize ([current-namespace ns])
    (namespace-require `(file ,(path->string helper)))
    (namespace-require `(file ,(path->string layout)))
    (for ([name '(preferences:get preferences:set color-prefs:set-current-color-scheme
                                 color-prefs:get-current-color-scheme-name get-face-list)]
          [proc (list (lambda (key) (hash-ref prefs key)) put! set-scheme! get-scheme
                      (lambda (_) '("DejaVu Sans Mono")))])
      (namespace-set-variable-value! name proc #t))
    (for ([name '(native-appearance-eligible? activate-native-appearance!
                  deactivate-native-appearance! suspend-native-appearance!
                  synchronize-native-appearance!)])
      (namespace-set-variable-value! name (make-keyword-procedure (lambda (keys values . args) #f)) #t))
    (namespace-set-variable-value! 'color-prefs:white-on-black-color-scheme?
                                   (lambda () (eq? (hash-ref prefs 'framework:white-on-black-mode?) #t)) #t)
    (eval '(define-logger openracket-appearance))
    (for ([form (in-list forms)] #:when (memq (definition-name form) needed)) (eval form)))
  (values prefs (lambda (name . args) (parameterize ([current-namespace ns]) (apply (eval name) args)))))

(test-case "successful apply captures exact six original settings"
  (define-values (prefs invoke) (sandbox))
  (check-true (invoke 'apply-appearance!))
  (check-equal? (hash-ref prefs 'openracket:appearance-state) 'applied)
  (check-equal? (hash-ref prefs 'openracket:appearance-snapshot)
                (map (lambda (key) (cons key (hash-ref initial key))) appearance-keys)))

(test-case "reapply does not replace the original rollback snapshot"
  (define-values (prefs invoke) (sandbox))
  (check-true (invoke 'apply-appearance!))
  (define snapshot (hash-ref prefs 'openracket:appearance-snapshot))
  (hash-set! prefs 'framework:standard-style-list:font-name "User Changed Font")
  (check-true (invoke 'apply-appearance!))
  (check-equal? (hash-ref prefs 'openracket:appearance-snapshot) snapshot))

(test-case "missing info-based schemes fail safely and preserve every setting"
  (define-values (prefs invoke) (sandbox #:schemes? #f))
  (check-false (invoke 'apply-appearance!))
  (check-equal? prefs (hash-copy initial)))

(for* ([key (in-list (append appearance-keys
                             '(openracket:appearance-snapshot openracket:appearance-enabled?
                               openracket:appearance-state)))]
       [before? '(#f #t)])
  (test-case (format "rollback at ~a ~a its write" key (if before? 'before 'after))
    (define-values (prefs invoke) (sandbox #:fail-key key #:fail-before? before?))
    (check-false (invoke 'apply-appearance!))
    (check-equal? prefs (hash-copy initial))))

(test-case "saved absent custom scheme ids survive restore with effective fallback refresh"
  (define-values (prefs invoke) (sandbox))
  (define saved
    (map (lambda (key)
           (cons key (case key
                       [(framework:color-scheme-light) 'temporarily-missing-light]
                       [(framework:color-scheme-dark) 'temporarily-missing-dark]
                       [else (hash-ref initial key)]))) appearance-keys))
  (invoke 'restore-snapshot! saved)
  (for ([entry (in-list saved)])
    (check-equal? (hash-ref prefs (car entry)) (cdr entry))))
