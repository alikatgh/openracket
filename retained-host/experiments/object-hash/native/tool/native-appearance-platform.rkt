#lang racket/base
(require racket/gui/dynamic racket/runtime-path "native-appearance.rkt")
(provide make-platform-native-appearance-adapter)

(define-runtime-path cocoa-backend "native-appearance-cocoa.rkt")
(define-runtime-path gtk-backend "native-appearance-gtk.rkt")

;; Never starts a GUI, never creates an application/eventspace, never changes a
;; desktop preference. Call only after the existing GUI has started, in its
;; handler thread. A false return means native appearance stays untouched.
(define (make-platform-native-appearance-adapter
         #:enabled? [enabled? #f]
         #:allow-gtk-candidate? [allow-gtk? #f]
         #:on-unavailable [unavailable void])
  (define (no reason) (unavailable reason) #f)
  (with-handlers ([exn:fail? (lambda (e) (no (exn-message e)))])
    (cond
      [(not enabled?) (no 'disabled)]
      [(not (gui-available?)) (no 'gui-not-started)]
      [else
       (define current-eventspace (gui-dynamic-require 'current-eventspace))
       (define handler-thread (gui-dynamic-require 'eventspace-handler-thread))
       (define shutdown? (gui-dynamic-require 'eventspace-shutdown?))
       (define eventspace (current-eventspace))
       (define (on-gui-thread?)
         (and (not (shutdown? eventspace))
              (eq? (current-thread) (handler-thread eventspace))))
       (cond
         [(not (on-gui-thread?)) (no 'wrong-thread)]
         [else
          (case ((gui-dynamic-require 'graphical-system-type))
            [(cocoa)
             ((dynamic-require cocoa-backend 'make-cocoa-appearance-adapter)
              on-gui-thread?)]
            [(gtk3)
             (if allow-gtk?
                 ((dynamic-require gtk-backend 'make-gtk-appearance-adapter)
                  on-gui-thread?)
                 (no 'gtk-stock-color-cache-unvalidated))]
            [else (no 'unsupported-native-backend)])])])))
