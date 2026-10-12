#lang racket/base

;; Appearance only. These mixins extend the real stock canvases/frame; they do
;; not replace editors, child widgets, selection, events, or command callbacks.
;; racket/draw permits the exact production margin painter to be tested without
;; loading racket/gui/base or opening a display.
(require racket/class racket/draw)
(provide (struct-out chrome-palette)
         make-chrome-palette
         paint-editor-chrome
         make-editor-chrome-mixin
         make-status-chrome-mixin)

(struct chrome-palette (edge focus) #:transparent)

(define (luminance color)
  (define (linear component)
    (define value (/ component 255.0))
    (if (<= value .04045)
        (/ value 12.92)
        (expt (/ (+ value .055) 1.055) 2.4)))
  (+ (* .2126 (linear (send color red)))
     (* .7152 (linear (send color green)))
     (* .0722 (linear (send color blue)))))

(define (contrast first second)
  (define a (luminance first))
  (define b (luminance second))
  (/ (+ (max a b) .05) (+ (min a b) .05)))

;; Derive quiet pane edges from the user's actual canvas/text scheme, including
;; custom schemes. The focus cue meets at least 3:1 contrast against that canvas.
;; It supplements (and never replaces) the stock caret and platform selection.
(define (make-chrome-palette background foreground)
  (define (blend get)
    (inexact->exact (round (+ (* .82 (get background))
                             (* .18 (get foreground))))))
  (define edge (make-object color%
                (blend (lambda (c) (send c red)))
                (blend (lambda (c) (send c green)))
                (blend (lambda (c) (send c blue)))))
  (define blue
    (if (< (luminance background) .30)
        (make-object color% 134 174 255)
        (make-object color% 36 94 219)))
  (define focus
    (cond
      [(>= (contrast blue background) 3) blue]
      [(>= (contrast foreground background) 3) foreground]
      [(> (luminance background) .179) (make-object color% 0 0 0)]
      [else (make-object color% 255 255 255)]))
  (chrome-palette edge focus))

(define (call-with-paint-state dc thunk)
  (define pen (send dc get-pen))
  (define brush (send dc get-brush))
  (define smoothing (send dc get-smoothing))
  (define alpha (send dc get-alpha))
  (dynamic-wind
    void thunk
    (lambda ()
      (send dc set-pen pen)
      (send dc set-brush brush)
      (send dc set-smoothing smoothing)
      (send dc set-alpha alpha))))

;; Paint only in the canvas margin, after the stock editor painter has run.
;; A one-DIP perimeter and two-DIP left focus rail never touch editor content.
;; Scrollbars are excluded because dimensions come from get-client-size.
;; Tiny canvases or reduced margins deliberately get no additional chrome.
(define (paint-editor-chrome dc width height horizontal-inset vertical-inset
                             focused? palette)
  (when (and (>= horizontal-inset 5) (>= vertical-inset 2)
             (> width (* 2 horizontal-inset))
             (> height (* 2 vertical-inset)))
    (call-with-paint-state
     dc
     (lambda ()
       (send dc set-smoothing 'unsmoothed)
       (send dc set-alpha 1)
       (send dc set-pen "black" 0 'transparent)
       (send dc set-brush (chrome-palette-edge palette) 'solid)
       (send dc draw-rectangle 0 0 width 1)
       (send dc draw-rectangle 0 (- height 1) width 1)
       (send dc draw-rectangle 0 1 1 (- height 2))
       (send dc draw-rectangle (- width 1) 1 1 (- height 2))
       (when focused?
         (send dc set-brush (chrome-palette-focus palette) 'solid)
         (send dc draw-rectangle 2 vertical-inset 2
               (- height (* 2 vertical-inset))))))))

;; enabled? and palette-thunk are supplied by the host's existing appearance
;; preference and Framework color-scheme lookup. They are not global settings.
(define (make-editor-chrome-mixin enabled? palette-thunk)
  (lambda (super%)
    (class super%
      (inherit get-dc get-client-size horizontal-inset vertical-inset
               has-focus? is-enabled? refresh)
      (define chrome-ready? #f)
      (define active-window? #t)

      (define/override (on-paint)
        (begin0
          (super on-paint)
          (when (and chrome-ready? (enabled?))
            (define-values (width height) (get-client-size))
            (paint-editor-chrome
             (get-dc) width height (horizontal-inset) (vertical-inset)
             (and active-window? (has-focus?) (is-enabled?))
             (palette-thunk)))))

      (define/override (on-focus on?)
        (begin0
          (super on-focus on?)
          (when (and chrome-ready? (enabled?)) (refresh))))

      (define/override (on-superwindow-activate active?)
        (begin0
          (super on-superwindow-activate active?)
          (set! active-window? (and active? #t))
          (when (and chrome-ready? (enabled?)) (refresh))))

      (super-new)
      (set! chrome-ready? #t))))

;; The stock status row owns its labels, error state, language picker, memory
;; display, lock icon and visibility. Only its public border/spacing are changed.
(define (make-status-chrome-mixin enabled?)
  (lambda (super%)
    (class super%
      (inherit get-info-panel)
      (super-new)
      (when (enabled?)
        (define status (get-info-panel))
        (send status border 6)
        (send status spacing 10)))))
