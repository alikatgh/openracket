#lang racket/base
;; Test-only read-only observation. Never set, capture or restore appearance.
(require racket/class racket/gui/base json mrlib/panel-wob
         "native-light-state-contract.rkt")
(provide observe-light-state!)
(define (json-safe value)
  (cond [(symbol? value) (symbol->string value)]
        [(hash? value) (for/hasheq ([(key item) (in-hash value)])
                         (values key (json-safe item)))]
        [(list? value) (map json-safe value)]
        [else value]))
(define (rgb color)
  (list (send color red) (send color green) (send color blue)))
(define (observe-light-state! stage)
  (unless (eq? (current-thread) (eventspace-handler-thread (current-eventspace)))
    (error 'native-light-state "Existing GUI handler thread required"))
  (define pref-get (dynamic-require 'framework 'preferences:get))
  (define scheme-name (dynamic-require 'framework 'color-prefs:get-current-color-scheme-name))
  (define color-lookup (dynamic-require 'framework 'color-prefs:lookup-in-color-scheme))
  (define (paint name) (dynamic-require 'mrlib/private/openracket-paint name))
  (define painter ((paint 'get-modern-host-theme)))
  (define painter-parameter (paint 'current-modern-theme))
  (define painter-color (paint 'theme-color))
  (define make-adapter (dynamic-require 'openracket-appearance/native-appearance-platform
                                      'make-platform-native-appearance-adapter))
  (define inspect (dynamic-require 'openracket-appearance/native-appearance
                                 'native-appearance-adapter-inspect))
  ;; The factory checks capability but does not own or set an appearance. Its
  ;; inspector is the only adapter operation invoked, matching the accepted
  ;; portable-observer path. Missing/unsupported Cocoa is a hard failure.
  (define adapter (make-adapter #:enabled? #t))
  (unless adapter (error 'native-light-state "Positive Cocoa inspector capability required"))
  (define observed
    (json-safe
     (hash 'appearance_state (pref-get 'openracket:appearance-state)
           'mode_preference (pref-get 'framework:white-on-black-mode?)
           'light_scheme (scheme-name #:wob? #f) 'dark_scheme (scheme-name #:wob? #t)
           'palette_background (rgb (color-lookup 'framework:basic-canvas-background))
           'palette_foreground (rgb (color-lookup 'framework:default-text-color))
           'painter_modern ((paint 'modern-ui?)) 'painter painter
           'painter_blended ((paint 'get-modern-chrome-blended?))
           ;; Read the same palette under the ACTUAL retained painter mode, as
           ;; switchable-button% does. Do not substitute the requested 'light.
           'painter_palette
           (parameterize ([painter-parameter painter])
             (for/hash ([key '(background surface hover pressed text muted border blue green purple red)])
               (values key (rgb (painter-color key)))))
           'panel_dark (white-on-black-panel-scheme?)
           'native ((inspect adapter)))))
  ;; Preserve the actual snapshot even if a strict assertion subsequently fails.
  (printf "OPENRACKET_NATIVE_LIGHT_STATE ~a\n"
          (jsexpr->string (hash 'stage stage 'observed observed)))
  (flush-output)
  (validate-light-state! observed))
