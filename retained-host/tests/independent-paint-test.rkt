#lang racket/base
(require rackunit racket/class racket/draw "../src/paint.rkt")

(define (solid-bitmap width height color)
  (define bitmap (make-bitmap width height #t))
  (define dc (new bitmap-dc% [bitmap bitmap]))
  (send dc set-background color)
  (send dc clear)
  (send dc set-bitmap #f)
  bitmap)
(define primary (solid-bitmap 20 20 "red"))
(define alternate (solid-bitmap 10 10 "green"))
(define (render label has-label? #:roles [roles (hash)] #:disabled? [disabled? #f])
  (define bitmap (make-bitmap 120 50))
  (define dc (new bitmap-dc% [bitmap bitmap]))
  (parameterize ([current-modern-theme 'light] [modern-role-labels roles])
    (paint-modern-button dc 120 50 label primary alternate has-label? disabled? #f #f 200))
  (send dc set-bitmap #f)
  bitmap)
(define (pixel bitmap x y)
  (define out (make-bytes 4))
  (send bitmap get-argb-pixels x y 1 1 out)
  (bytes->list out))

(test-case "unrecognized visible-label role retains primary bitmap, even when text is collapsed"
  (check-equal? (pixel (render "Third-party action" #t) 60 25) '(255 255 0 0)))
(test-case "label-hidden role retains the alternate bitmap"
  (check-equal? (pixel (render "Third-party action" #f) 60 25) '(255 0 255 0)))
(test-case "unmapped localized role retains exact supplied icon"
  (check-equal? (pixel (render "実行" #t) 60 25) '(255 255 0 0)))
(test-case "false label retains alternate bitmap"
  (check-equal? (pixel (render #f #f) 60 25) '(255 0 255 0)))
(test-case "disabled fallback is visibly dimmed without replacing artwork"
  (define enabled (pixel (render "Third-party action" #t) 60 25))
  (define disabled (pixel (render "Third-party action" #t #:disabled? #t) 60 25))
  (check-not-equal? enabled disabled)
  (check-true (> (cadr disabled) (caddr disabled))))
(test-case "explicit localization map replaces only the requested exact string"
  (define roles (hash "実行" 'run))
  (check-not-equal? (pixel (render "実行" #t #:roles roles) 60 25) '(255 255 0 0))
  (check-equal? (pixel (render "実行 extra" #t #:roles roles) 60 25) '(255 255 0 0)))

(test-case "renderer preserves complete transform, clip, background and drawing settings"
  (define dc (new bitmap-dc% [bitmap (make-bitmap 300 160)]))
  (send dc set-origin 3 7)
  (send dc set-scale 1.5 1.5)
  (send dc set-rotation .05)
  (send dc set-clipping-rect 3 3 100 100)
  (send dc set-text-mode 'solid)
  (send dc set-text-background "pink")
  (send dc set-background "orange")
  (send dc set-alpha .67)
  (send dc set-smoothing 'aligned)
  (define (state)
    (list (send dc get-transformation) (send dc get-clipping-region)
          (send dc get-text-mode) (send dc get-text-background) (send dc get-background)
          (send dc get-alpha) (send dc get-smoothing) (send dc get-pen)
          (send dc get-brush) (send dc get-font) (send dc get-text-foreground)))
  (define before (state))
  (paint-modern-button dc 120 50 "Run" primary alternate #t #f #t #t 38)
  (check-equal? (state) before)
  ;; An exception in the actual paint path must still restore every touched field.
  (check-exn exn:fail?
             (lambda () (paint-modern-button dc 120 50 "Run" #f #f #t #t #t #t 38)))
  (check-equal? (state) before))

(test-case "long Unicode metrics and drawing use exactly the same selected font"
  (define stock-font (make-font #:size 22 #:family 'system))
  (define dc (new bitmap-dc% [bitmap (make-bitmap 1000 100)]))
  (define chosen (modern-control-font stock-font))
  (define label "Exécuter 日本語 Ελληνικά Выполнить العربية")
  (define-values (width height descent extra) (send dc get-text-extent label chosen))
  (check-true (> width 0))
  (check-true (> height 0))
  (check-not-exn
   (lambda ()
     (paint-modern-button dc (+ width 64) (+ height 24) label primary alternate #t #f #f #f 38))))
