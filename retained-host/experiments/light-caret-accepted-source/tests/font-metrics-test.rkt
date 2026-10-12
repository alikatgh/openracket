#lang racket/base
;; The actual stock font must drive retained button metrics and paint together.
(require rackunit racket/class racket/draw racket/file racket/list racket/runtime-path
         "../src/paint.rkt")
(define-runtime-path patched "../overlay/mrlib/switchable-button.rkt")

(for* ([pixels? '(#t #f)] [size '(10 15 20 30)])
  (test-case (format "preserve platform font identity: ~a ~a" size pixels?)
    (define supplied
      (make-font #:size size #:family 'system #:weight 'bold
                 #:size-in-pixels? pixels? #:smoothing 'unsmoothed))
    (check-eq? (modern-control-font supplied) supplied)
    (check-= (send (modern-control-font supplied) get-size) size 0)
    (check-equal? (send (modern-control-font supplied) get-size-in-pixels) pixels?)
    (check-equal? (send (modern-control-font supplied) get-weight) 'bold)
    (check-equal? (send (modern-control-font supplied) get-smoothing) 'unsmoothed)))

(for* ([pixels? '(#t #f)] [size '(10 15 20 30)])
  (test-case (format "scaled font paints within its measured bounds: ~a ~a" size pixels?)
    (define supplied (make-font #:size size #:family 'system #:size-in-pixels? pixels?))
    (define label "Tool: café lambda")
    (define measure-dc (new bitmap-dc%))
    (define-values (tw th descent extra)
      (send measure-dc get-text-extent label (modern-control-font supplied)))
    (define width (inexact->exact (ceiling (+ tw 6 20 24))))
    (define height (inexact->exact (ceiling (+ (max th 24) 20))))
    (define bitmap (make-bitmap width height))
    (define dc (new bitmap-dc% [bitmap bitmap]))
    (define original-font (send dc get-font))
    (parameterize ([current-modern-theme 'light])
      (paint-modern-button dc width height label (make-preview-icon 20)
                           (make-preview-icon 20) #t #f #f #f 32
                           (modern-control-font supplied))
      (check-eq? (send dc get-font) original-font)
      (define foreground (theme-color 'text))
      (define bytes (make-bytes (* 4 width height)))
      (send bitmap get-argb-pixels 0 0 width height bytes)
      (define locations
        (for*/list ([y (in-range height)] [x (in-range width)]
                    #:when
                    (let ([at (* 4 (+ x (* y width)))])
                      (and (> (bytes-ref bytes at) 127)
                           (<= (abs (- (bytes-ref bytes (+ at 1)) (send foreground red))) 80)
                           (<= (abs (- (bytes-ref bytes (+ at 2)) (send foreground green))) 80)
                           (<= (abs (- (bytes-ref bytes (+ at 3)) (send foreground blue))) 80))))
          (cons x y)))
      (check-true (> (length locations) 5))
      (check-true (andmap (lambda (p) (and (< 0 (car p) (sub1 width))
                                         (< 0 (cdr p) (sub1 height)))) locations)))
    (send dc set-bitmap #f)))

(test-case "actual source supplies identical font expression to both metrics and painter"
  (define source (file->string patched))
  (check-equal? (length (regexp-match* #rx"[(]modern-control-font normal-control-font[)]" source)) 3)
  (check-true
   (regexp-match? #rx"[(]get-small-width[)]\n +[(]modern-control-font normal-control-font[)]" source)))

(define (with-blended value thunk)
  (define original (get-modern-chrome-blended?))
  (dynamic-wind (lambda () (set-modern-chrome-blended! value)) thunk
                (lambda () (set-modern-chrome-blended! original))))
(define (background-pixel blended? hover? disabled?)
  (define bitmap (make-bitmap 200 50))
  (define dc (new bitmap-dc% [bitmap bitmap]))
  (send dc set-background "yellow") (send dc clear)
  (with-blended
   blended?
   (lambda ()
     (parameterize ([current-modern-theme 'dark])
       (paint-modern-button dc 200 50 "External" (make-preview-icon 20)
                            (make-preview-icon 20) #t disabled? hover? #f 32))))
  (define pixel (make-bytes 4))
  (send bitmap get-argb-pixels 10 10 1 1 pixel)
  (send dc set-bitmap #f)
  pixel)
(test-case "verified native chrome keeps idle parent background"
  (check-equal? (background-pixel #t #f #f) (bytes 255 255 255 0)))
(test-case "unsupported native appearance keeps contrast-safe capsule"
  (check-not-equal? (background-pixel #f #f #f) (bytes 255 255 255 0)))
(test-case "blended hover still provides visible feedback"
  (check-not-equal? (background-pixel #t #t #f) (bytes 255 255 255 0)))
(test-case "disabled blended control ignores hover background"
  (check-equal? (background-pixel #t #t #t) (bytes 255 255 255 0)))
(test-case "blending state is explicitly boolean"
  (check-exn exn:fail:contract? (lambda () (set-modern-chrome-blended! 'maybe))))
