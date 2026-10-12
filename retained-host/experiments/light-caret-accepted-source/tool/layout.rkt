#lang racket/base

;; GUI-free mixin definitions: the superclass is always the real host class.
;; No event handler, editor, snip, keymap, toolbar control, or callback is replaced.
(require racket/class)
(provide make-canvas-spacing-mixin make-frame-spacing-mixin preferred-editor-face
         host-theme-enabled?)

;; The standalone tool must never restyle a real profile merely by being found.
(define (host-theme-enabled? explicit-proof-opt-in ui-mode)
  (and (equal? explicit-proof-opt-in "1") (not (equal? ui-mode "stock"))))

(define (preferred-editor-face available fallback)
  (or (for/or ([face (in-list '("JetBrains Mono" "SF Mono" "Cascadia Code"
                               "Menlo" "DejaVu Sans Mono"))])
        (and (member face available) face))
      fallback))

(define (make-canvas-spacing-mixin enabled?)
  (lambda (super%)
    (class super%
      (inherit horizontal-inset vertical-inset)
      (super-new)
      (when (enabled?)
        (horizontal-inset 12)
        (vertical-inset 10)))))

(define (make-frame-spacing-mixin initialize! enabled?)
  (lambda (super%)
    (class super%
      (inherit get-button-panel)
      ;; DrRacket has discovered info.rkt color schemes by the time its first
      ;; real frame is instantiated, but not when tool phase2 runs.
      (initialize!)
      (super-new)
      (when (enabled?)
        (define buttons (get-button-panel))
        (send buttons spacing 6)
        ;; Keep the stock parent and child order, including third-party tools.
        (define stock-top-panel (send buttons get-parent))
        (send stock-top-panel spacing 6)
        (send stock-top-panel border 8)))))
