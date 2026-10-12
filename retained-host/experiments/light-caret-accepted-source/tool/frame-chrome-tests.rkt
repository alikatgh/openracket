#lang racket/base
(require racket/class racket/draw racket/list rackunit "frame-chrome.rkt")

(define dark-bg (make-object color% 23 28 38))
(define dark-text (make-object color% 236 240 247))
(define light-bg (make-object color% 247 248 250))
(define light-text (make-object color% 37 48 71))
(define dark (make-chrome-palette dark-bg dark-text))
(define light (make-chrome-palette light-bg light-text))
(define (rgb c) (list (send c red) (send c green) (send c blue)))
(define (luminance c)
  (define (linear v)
    (define s (/ v 255.0))
    (if (<= s .04045) (/ s 12.92) (expt (/ (+ s .055) 1.055) 2.4)))
  (apply + (map * '(.2126 .7152 .0722) (map linear (rgb c)))))
(define (contrast a b)
  (/ (+ .05 (max (luminance a) (luminance b)))
     (+ .05 (min (luminance a) (luminance b)))))

(define W 160)
(define H 96)
(define HX 12)
(define VY 10)
(define (make-surface [background dark-bg])
  (define bitmap (make-bitmap W H))
  (define dc (new bitmap-dc% [bitmap bitmap]))
  (send dc set-background background)
  (send dc clear)
  (values bitmap dc))
(define (pixels bitmap)
  (define out (make-bytes (* 4 W H)))
  (send bitmap get-argb-pixels 0 0 W H out)
  out)
(define (pixel bytes x y)
  (subbytes bytes (* 4 (+ x (* y W))) (* 4 (+ 1 x (* y W)))))

(test-case "palette aligns with light/dark accent colors"
  (check-equal? (rgb (chrome-palette-focus dark)) '(134 174 255))
  (check-equal? (rgb (chrome-palette-focus light)) '(36 94 219))
  (check-true (>= (contrast dark-bg (chrome-palette-focus dark)) 3))
  (check-true (>= (contrast light-bg (chrome-palette-focus light)) 3)))

(test-case "focus remains discernible even on custom low-contrast schemes"
  (for* ([r '(0 32 64 96 128 160 192 224 255)]
         [g '(0 64 128 192 255)]
         [b '(0 64 128 192 255)])
    (define bg (make-object color% r g b))
    (define palette (make-chrome-palette bg bg))
    (check-true (>= (contrast bg (chrome-palette-focus palette)) 3)
                (format "background ~a" (rgb bg)))))

(test-case "pane edges adapt to actual custom scheme colors"
  (define custom (make-chrome-palette (make-object color% 100 120 140)
                                      (make-object color% 200 220 240)))
  (check-equal? (rgb (chrome-palette-edge custom)) '(118 138 158)))

(test-case "production painter never changes editor interior pixels"
  (for* ([palette (in-list (list dark light))] [focused? '(#f #t)])
    (define-values (bitmap dc) (make-surface))
    ;; Contrasting content stands in only as a pixel invariant, not a fake editor.
    (send dc set-pen "magenta" 0 'transparent)
    (send dc set-brush "magenta" 'solid)
    (send dc draw-rectangle HX VY (- W (* 2 HX)) (- H (* 2 VY)))
    (define before (pixels bitmap))
    (paint-editor-chrome dc W H HX VY focused? palette)
    (define after (pixels bitmap))
    (for* ([x (in-range HX (- W HX))] [y (in-range VY (- H VY))])
      (check-equal? (pixel before x y) (pixel after x y)))
    (check-not-equal? before after)))

(test-case "focus rail occupies only the left reserved inset"
  (define-values (bitmap dc) (make-surface))
  (paint-editor-chrome dc W H HX VY #f dark)
  (define unfocused (pixels bitmap))
  (paint-editor-chrome dc W H HX VY #t dark)
  (define focused (pixels bitmap))
  (define changed
    (for*/list ([x (in-range W)] [y (in-range H)]
                #:unless (bytes=? (pixel unfocused x y) (pixel focused x y)))
      (list x y)))
  (check-equal? (length changed) (* 2 (- H (* 2 VY))))
  (for ([xy (in-list changed)])
    (check-true (<= 2 (car xy) 3))
    (check-true (<= VY (cadr xy) (- H VY 1)))))

(test-case "small viewports and reduced margins keep exactly stock pixels"
  (for ([geometry '((12 10 12 10) (160 96 4 10) (160 96 12 1)
                    (0 0 12 10) (24 20 12 10))])
    (define-values (bitmap dc) (make-surface))
    (define before (pixels bitmap))
    (apply paint-editor-chrome dc (append geometry (list #t dark)))
    (check-equal? (pixels bitmap) before)))

(define (dc-state dc)
  (list (send dc get-pen) (send dc get-brush) (send dc get-smoothing)
        (send dc get-alpha) (send dc get-font) (send dc get-text-foreground)
        (send dc get-transformation) (send dc get-clipping-region)))
(define (customize-dc! dc)
  (send dc set-pen "orange" 3 'long-dash)
  (send dc set-brush "red" 'cross-hatch)
  (send dc set-alpha .37)
  (send dc set-smoothing 'smoothed)
  (send dc set-font (make-font #:size 17 #:family 'modern))
  (send dc set-text-foreground "green")
  (send dc set-origin 3 4)
  (define region (new region% [dc dc]))
  (send region set-rectangle 2 2 100 80)
  (send dc set-clipping-region region))

(test-case "painter preserves DC state, transform and existing clipping"
  (define-values (bitmap dc) (make-surface))
  (customize-dc! dc)
  (define before (dc-state dc))
  (paint-editor-chrome dc W H HX VY #t dark)
  (check-equal? (dc-state dc) before))

(test-case "painter restores state even when a supplied color is invalid"
  (define-values (bitmap dc) (make-surface))
  (customize-dc! dc)
  (define before (dc-state dc))
  (check-exn exn:fail?
             (lambda ()
               (paint-editor-chrome dc W H HX VY #t
                                    (chrome-palette (chrome-palette-edge dark) #f))))
  (check-equal? (dc-state dc) before))

(define stock-editor (gensym 'retained-stock-editor))
(define fake-canvas%
  (class object%
    (super-new)
    (define-values (bitmap dc) (make-surface))
    (define focus? #f)
    (define enabled? #t)
    (define calls '())
    (define/public (get-calls) calls)
    (define/public (get-pixels) (pixels bitmap))
    (define/public (get-dc) dc)
    (define/public (get-client-size) (values W H))
    (define/public (horizontal-inset) HX)
    (define/public (vertical-inset) VY)
    (define/public (has-focus?) focus?)
    (define/public (is-enabled?) enabled?)
    (define/public (enable value) (set! enabled? value))
    (define/public (get-editor) stock-editor)
    (define/public (refresh) (set! calls (append calls '(refresh))))
    (define/public (on-paint)
      (set! calls (append calls '(stock-paint)))
      (send dc set-background dark-bg)
      (send dc clear)
      'stock-paint-result)
    (define/public (on-focus value)
      (set! calls (append calls (list (list 'stock-focus value))))
      (set! focus? value)
      'stock-focus-result)
    (define/public (on-superwindow-activate value)
      (set! calls (append calls (list (list 'stock-activate value))))
      'stock-activate-result)
    (define/public (on-char evt) (list 'stock-char evt))
    (define/public (on-event evt) (list 'stock-event evt))))

(test-case "canvas retains editor identity and forwards paint/focus once in order"
  (define canvas (new ((make-editor-chrome-mixin (lambda () #t) (lambda () dark))
                      fake-canvas%)))
  (check-true (is-a? canvas fake-canvas%))
  (check-eq? (send canvas get-editor) stock-editor)
  (check-eq? (send canvas on-focus #t) 'stock-focus-result)
  (check-eq? (send canvas on-paint) 'stock-paint-result)
  (check-equal? (send canvas get-calls) '((stock-focus #t) refresh stock-paint))
  (check-equal? (send canvas on-char 'input) '(stock-char input))
  (check-equal? (send canvas on-event 'click) '(stock-event click))
  (check-equal? (sort (interface->method-names (object-interface canvas)) symbol<?)
                (sort (interface->method-names (class->interface fake-canvas%)) symbol<?)))

(test-case "disabled appearance adds no palette lookup, painting or refresh"
  (define canvas (new ((make-editor-chrome-mixin
                       (lambda () #f)
                       (lambda () (error 'unexpected "palette lookup")))
                      fake-canvas%)))
  (define before (send canvas get-pixels))
  (send canvas on-focus #t)
  (send canvas on-superwindow-activate #f)
  (send canvas on-paint)
  (check-equal? (send canvas get-pixels) before)
  (check-equal? (send canvas get-calls)
                '((stock-focus #t) (stock-activate #f) stock-paint)))

(test-case "focus and window activation changes remove and restore the rail"
  (define canvas (new ((make-editor-chrome-mixin (lambda () #t) (lambda () dark))
                      fake-canvas%)))
  (send canvas on-paint)
  (define unfocused (send canvas get-pixels))
  (send canvas on-focus #t)
  (send canvas on-paint)
  (define focused (send canvas get-pixels))
  (check-not-equal? focused unfocused)
  (check-eq? (send canvas on-superwindow-activate #f) 'stock-activate-result)
  (send canvas on-paint)
  (check-equal? (send canvas get-pixels) unfocused)
  (send canvas on-superwindow-activate #t)
  (send canvas on-paint)
  (check-equal? (send canvas get-pixels) focused)
  (send canvas on-focus #f)
  (send canvas on-paint)
  (check-equal? (send canvas get-pixels) unfocused))

(test-case "disabled native canvas does not display an active focus rail"
  (define canvas (new ((make-editor-chrome-mixin (lambda () #t) (lambda () dark))
                      fake-canvas%)))
  (send canvas on-paint)
  (define unfocused (send canvas get-pixels))
  (send canvas on-focus #t)
  (send canvas enable #f)
  (send canvas on-paint)
  (check-equal? (send canvas get-pixels) unfocused))

(test-case "appearance can be disabled on a live canvas without editor replacement"
  (define enabled? #t)
  (define canvas
    (new ((make-editor-chrome-mixin (lambda () enabled?) (lambda () dark)) fake-canvas%)))
  (send canvas on-paint)
  (define styled (send canvas get-pixels))
  (set! enabled? #f)
  (send canvas on-paint)
  (check-not-equal? (send canvas get-pixels) styled)
  (check-eq? (send canvas get-editor) stock-editor))

(define fake-panel%
  (class object%
    (init-field children parent)
    (super-new)
    (define b 0)
    (define s 0)
    (define/public (border [value #f]) (if value (set! b value) b))
    (define/public (spacing [value #f]) (if value (set! s value) s))
    (define/public (get-parent) parent)
    (define/public (get-children) children)
    (define/public (is-shown?) #f)))

(test-case "status geometry preserves native row, child order, parent and visibility"
  (define children (list (gensym 'language) (gensym 'memory) (gensym 'lock)))
  (define parent (gensym 'stock-parent))
  (define status (new fake-panel% [children children] [parent parent]))
  (define frame%
    (class object%
      (super-new)
      (define/public (get-info-panel) status)
      (define/public (execute-callback) 'stock-run)))
  (define frame (new ((make-status-chrome-mixin (lambda () #t)) frame%)))
  (check-true (is-a? frame frame%))
  (check-eq? (send frame get-info-panel) status)
  (check-eq? (send status get-parent) parent)
  (check-eq? (send status get-children) children)
  (check-false (send status is-shown?))
  (check-equal? (send status border) 6)
  (check-equal? (send status spacing) 10)
  (check-eq? (send frame execute-callback) 'stock-run))

(test-case "disabled status mixin leaves all stock geometry intact"
  (define status (new fake-panel% [children '()] [parent #f]))
  (define frame%
    (class object%
      (super-new)
      (define/public (get-info-panel) status)))
  (new ((make-status-chrome-mixin (lambda () #f)) frame%))
  (check-equal? (send status border) 0)
  (check-equal? (send status spacing) 0))
