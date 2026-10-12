#lang racket/base
;; Explicit native-only smoke test; importing/compiling this file starts no GUI.
;; Run only in an approved graphical test environment with an external timeout:
;;   racket tool/native-appearance-native-tests.rkt
;; GTK also requires OPENRACKET_NATIVE_GTK_CANDIDATE=1. Its inheritance-source
;; limitation remains even if every value/palette assertion below passes.
(require racket/class racket/gui/dynamic rackunit
         "native-appearance.rkt" "native-appearance-platform.rkt")
(provide run-native-appearance-checks)

(define (run-native-appearance-checks)
  (unless (gui-available?) (error 'native-appearance-test "Existing GUI required"))
  (define queue-callback (gui-dynamic-require 'queue-callback))
  (define yield (gui-dynamic-require 'yield))
  (define (on-gui thunk)
    (define done (make-semaphore 0))
    (define result #f)
    (queue-callback
     (lambda ()
       (with-handlers ([exn? (lambda (e) (set! result (cons #f e)))])
         (parameterize ([current-check-handler raise])
           (set! result (cons #t (thunk)))))
       (semaphore-post done)) #f)
    (yield done)
    (if (car result) (cdr result) (raise (cdr result))))
  (define unavailable #f)
  (define adapter
    (on-gui
     (lambda ()
       (make-platform-native-appearance-adapter
        #:enabled? #t
        #:allow-gtk-candidate? (equal? (getenv "OPENRACKET_NATIVE_GTK_CANDIDATE") "1")
        #:on-unavailable (lambda (reason) (set! unavailable reason))))))
  (unless adapter
    (error 'native-appearance-test "Native capability unavailable: ~a" unavailable))
  (define c (make-native-appearance-controller adapter #:enabled? #t))
  (define original (on-gui (lambda () (native-appearance-inspect c))))
  ;; Official 9.3 exposes this predicate through mrlib/panel-wob, not gui/base.
  ;; Keep the require inside the runner so import/compilation remains GUI-free.
  (define dark? (dynamic-require 'mrlib/panel-wob 'white-on-black-panel-scheme?))
  (define get-fg (gui-dynamic-require 'get-label-foreground-color))
  (define get-bg (gui-dynamic-require 'get-label-background-color))
  (define get-selection-fg (gui-dynamic-require 'get-highlight-text-color))
  (define get-selection-bg (gui-dynamic-require 'get-highlight-background-color))
  (define (rgb color)
    (and color (list (send color red) (send color green) (send color blue))))
  (define (luminance color)
    (define (linear n)
      (define v (/ n 255.0))
      (if (<= v .04045) (/ v 12.92) (expt (/ (+ v .055) 1.055) 2.4)))
    (apply + (map * '(0.2126 0.7152 0.0722) (map linear (rgb color)))))
  (define (contrast a b)
    (define x (+ .05 (luminance a)))
    (define y (+ .05 (luminance b)))
    (/ (max x y) (min x y)))
  (define callback-count 0)
  (define frame #f)
  (define panel #f)
  (define children #f)
  (define states '())
  (dynamic-wind
   void
   (lambda ()
     (on-gui
      (lambda ()
        (define frame% (gui-dynamic-require 'frame%))
        (define vertical-panel% (gui-dynamic-require 'vertical-panel%))
        (define message% (gui-dynamic-require 'message%))
        (define button% (gui-dynamic-require 'button%))
        (define text-field% (gui-dynamic-require 'text-field%))
        (define check-box% (gui-dynamic-require 'check-box%))
        (set! frame (new frame% [label "Native appearance verification"] [width 520] [height 260]))
        (set! panel (new vertical-panel% [parent frame]))
        (new message% [parent panel] [label "Retained native controls: λ, café, 日本語"])
        (new text-field% [parent panel] [label "Text"] [init-value "Native editable selection"])
        (new check-box% [parent panel] [label "Original native checkbox"])
        (new button% [parent panel] [label "Original native button"]
             [callback (lambda args (set! callback-count (add1 callback-count)))])
        (new button% [parent panel] [label "Disabled native button"] [enabled #f])
        (set! children (send panel get-children))
        (send frame show #t)))
     (for ([mode '(dark light dark light)])
       (on-gui
        (lambda ()
          (check-eq? (native-appearance-result-status (native-appearance-set! c mode)) 'applied)
          (check-eq? (native-appearance-result-status (native-appearance-set! c mode)) 'unchanged
                     "Repeated native notification is verified without another mutation")))
       ;; Let real platform notifications and stock cache/refresh callbacks run.
       (on-gui void)
       (on-gui
        (lambda ()
          (check-equal? (dark?) (eq? mode 'dark) "Stock platform mode tracks native appearance")
          (check-true (>= (contrast (get-fg) (get-bg)) 4.5) "Stock label colors remain readable")
          (check-equal? (send frame get-label) "Native appearance verification")
          (check-equal? (send panel get-children) children "Native child identities/order preserved")
          (check-equal? callback-count 0 "Appearance changes cannot invoke control callbacks")
          (define state
            (hash 'requested mode 'native (native-appearance-inspect c)
                  'label-foreground (rgb (get-fg)) 'label-background (rgb (get-bg))
                  'selection-foreground (rgb (get-selection-fg))
                  'selection-background (rgb (get-selection-bg))))
          (set! states (cons state states))
          (printf "NATIVE_APPEARANCE_STATE ~s\n" state))))
     (on-gui
      (lambda ()
        (check-eq? (native-appearance-result-status (native-appearance-follow-original! c)) 'following)
        (check-equal? (native-appearance-inspect c) original "Platform follows original native inheritance")
        (check-false (native-appearance-active? c))
        (check-eq? (native-appearance-result-status (native-appearance-follow-original! c)) 'following)
        (check-eq? (native-appearance-result-status (native-appearance-set! c 'dark)) 'applied)
        (check-eq? (native-appearance-result-status (native-appearance-restore! c)) 'restored)
        (check-equal? (native-appearance-inspect c) original "Exact prior native values restored")
        (check-false (native-appearance-active? c))
        (check-eq? (native-appearance-result-status (native-appearance-restore! c)) 'unchanged)))
     (on-gui void)
     (displayln "NATIVE_APPEARANCE_LIFECYCLE_OK")
     (reverse states))
   (lambda ()
     (on-gui
      (lambda ()
        ;; Cleanup still restores after an assertion failure; report any native
        ;; restore failure rather than silently leaving the test app overridden.
        (define restored (native-appearance-restore! c))
        (unless (memq (native-appearance-result-status restored) '(restored unchanged))
          (eprintf "NATIVE_APPEARANCE_RESTORE_FAILED ~s\n" restored))
        (when frame (send frame show #f)))))))

(module+ main
  (dynamic-require 'racket/gui/base #f)
  (run-native-appearance-checks)
  (exit 0))
