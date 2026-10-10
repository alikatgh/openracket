#lang racket/base
;; Presentation-only renderer. No event handling, evaluation, or tool callbacks.
(require racket/class racket/draw racket/list)
(provide modern-ui? modern-control-font paint-modern-button
         modern-role-labels current-modern-theme theme-color
         set-modern-host-theme! get-modern-host-theme set-modern-role-labels!
         make-preview-icon call-with-dc-state)

(define (modern-ui?) (not (equal? (getenv "OPENRACKET_UI") "stock")))
(define current-modern-theme
  (make-parameter (if (equal? (getenv "OPENRACKET_THEME") "light") 'light 'dark)))
;; The DrRacket tool populates these from stock localized string constants.
;; English defaults are only used by the isolated paint proof.
(define initial-role-labels
  (hash "Check Syntax" 'check "Debug" 'debug
                        "Macro Stepper" 'macro "Run" 'run "Stop" 'stop "Kill" 'stop))
(define configured-role-labels (box initial-role-labels))
(define modern-role-labels (make-parameter #f))
(define (set-modern-role-labels! labels) (set-box! configured-role-labels labels))
(define host-theme (box 'auto))
(define (set-modern-host-theme! theme)
  (unless (memq theme '(auto dark light)) (raise-argument-error 'set-modern-host-theme! "(or/c 'auto 'dark 'light)" theme))
  (set-box! host-theme theme))
(define (get-modern-host-theme) (unbox host-theme))
(define palettes
  (hash 'light (hash 'background "#F7F8FA" 'surface "#FFFFFF" 'hover "#E9EDF4"
                     'pressed "#DCE4EF" 'text "#253047" 'muted "#62718A"
                     'border "#D8DFE9" 'blue "#245EDB" 'green "#167C58"
                     'purple "#7955D5" 'red "#C7404D")
        'dark (hash 'background "#171C26" 'surface "#202735" 'hover "#2B3548"
                    'pressed "#35415A" 'text "#ECF0F7" 'muted "#9BA9BE"
                    'border "#3C4860" 'blue "#86AEFF" 'green "#78D7B1"
                    'purple "#BEA4FF" 'red "#FF9098")))
(define (theme-color key)
  (define h (hash-ref (hash-ref palettes (current-modern-theme)) key))
  (make-object color% (string->number (substring h 1 3) 16)
               (string->number (substring h 3 5) 16)
               (string->number (substring h 5 7) 16)))
(define modern-font
  (make-font #:size 13 #:family 'system
             #:face (case (system-type 'os)
                      [(macosx) "SF Pro Text"] [(windows) "Segoe UI"]
                      [else "DejaVu Sans"])
             #:size-in-pixels? #t #:smoothing 'smoothed))
(define (modern-control-font stock-font)
  (if (modern-ui?) modern-font stock-font))

;; Restore every mutable DC setting this module touches, including on failure.
(define (call-with-dc-state dc thunk)
  (define pen (send dc get-pen))
  (define brush (send dc get-brush))
  (define font (send dc get-font))
  (define fg (send dc get-text-foreground))
  (define alpha (send dc get-alpha))
  (define smooth (send dc get-smoothing))
  (dynamic-wind void thunk
                (lambda ()
                  (send dc set-pen pen) (send dc set-brush brush)
                  (send dc set-font font) (send dc set-text-foreground fg)
                  (send dc set-alpha alpha) (send dc set-smoothing smooth))))

(define (line dc color x1 y1 x2 y2 [width 1.65])
  (send dc set-pen color width 'solid)
  (send dc draw-line x1 y1 x2 y2))
(define (triangle dc color x y s)
  (send dc set-pen color 0 'transparent)
  (send dc set-brush color 'solid)
  (define p (new dc-path%))
  (send p move-to x y) (send p line-to (+ x s) (+ y (/ s 2)))
  (send p line-to x (+ y s)) (send p close)
  (send dc draw-path p))
(define (icon-color role)
  (theme-color (case role [(run debug) 'green] [(stop) 'red]
                            [(macro) 'purple] [else 'blue])))
(define (draw-modern-icon dc role x y w h)
  (define color (icon-color role))
  (define base-w (if (memq role '(check debug macro)) 35 19))
  (define scale (min 1 (/ w base-w) (/ h 19)))
  (define left (+ x (/ (- w (* base-w scale)) 2)))
  (define top (+ y (/ (- h (* 19 scale)) 2)))
  (define (X a) (+ left (* a scale)))
  (define (Y a) (+ top (* a scale)))
  (define (L a b c d) (line dc color (X a) (Y b) (X c) (Y d) (max 1 (* 1.65 scale))))
  (send dc set-pen color (max 1 (* 1.65 scale)) 'solid)
  (send dc set-brush color 'transparent)
  (case role
    [(run) (triangle dc color (X 3) (Y 2) (* 15 scale))]
    [(stop) (send dc set-brush color 'solid)
            (send dc set-pen color 0 'transparent)
            (send dc draw-rounded-rectangle (X 2) (Y 2) (* 15 scale) (* 15 scale) (* 3 scale))]
    [(check)
     (send dc draw-ellipse (X 1) (Y 1) (* 11 scale) (* 11 scale))
     (L 11 11 16 16)
     (L 20 9 24 13) (L 24 13 31 4)]
    [(debug)
     (send dc draw-rounded-rectangle (X 4) (Y 5) (* 9 scale) (* 12 scale) (* 4 scale))
     (send dc draw-ellipse (X 6) (Y 1) (* 5 scale) (* 5 scale))
     (for ([dy '(7 11 15)]) (L 1 dy 4 dy) (L 13 dy 16 dy))
     (L 8 7 8 15) (triangle dc color (X 22) (Y 4) (* 11 scale))]
    [(macro)
     (L 5 2 3 17) (L 12 2 10 17) (L 1 7 16 7) (L 0 12 15 12)
     (triangle dc color (X 21) (Y 4) (* 11 scale)) (L 34 4 34 15)]))

;; All parameters come directly from the retained upstream switchable-button%.
;; The stock host decides has-label?, small-width, in?, down?, and disabled?.
;; Unknown/localized/custom bitmap buttons retain their stock artwork.
(define (paint-modern-button dc cw ch label bitmap alternate-bitmap
                             has-label? disabled? in? down? small-width)
  (call-with-dc-state
   dc
   (lambda ()
     (send dc set-smoothing 'smoothed)
     (send dc set-font modern-font)
     (define bg (theme-color (cond [(and in? (not disabled?) down?) 'pressed]
                                   [(and in? (not disabled?)) 'hover]
                                   [else 'background])))
     (send dc set-brush bg 'solid) (send dc set-pen bg 0 'transparent)
     (send dc draw-rounded-rectangle 1 2 (max 0 (- cw 2)) (max 0 (- ch 4)) 6)
     (send dc set-alpha (* (send dc get-alpha) (if disabled? .42 1)))
     (send dc set-text-foreground (theme-color 'text))
     (define show-text? (and has-label? (string? label) (> cw small-width)))
     (define bm (if has-label? bitmap alternate-bitmap))
     (define bw (send bm get-width)) (define bh (send bm get-height))
     (define-values (tw th d a)
       (if show-text? (send dc get-text-extent label) (values 0 0 0 0)))
     (define total (+ tw (if show-text? 6 0) bw))
     (define x (/ (- cw total) 2))
     (when show-text? (send dc draw-text label x (/ (- ch th) 2)))
     (define bx (+ x tw (if show-text? 6 0)))
     (define by (/ (- ch bh) 2))
     (define role (and (string? label) (hash-ref (or (modern-role-labels) (unbox configured-role-labels)) label #f)))
     (cond
       [role (draw-modern-icon dc role bx by bw bh)]
       [else (send dc draw-bitmap bm bx by 'solid (make-object color% 0 0 0) (send bm get-loaded-mask))]))))

;; Fixtures only; actual host passes real stock icon bitmaps.
(define (make-preview-icon w [h 24])
  (make-bitmap w h #t))
