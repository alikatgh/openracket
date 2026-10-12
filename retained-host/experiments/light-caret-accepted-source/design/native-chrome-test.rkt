#lang racket/base
;; Native integration gate. Run ONLY on an authorized, functioning GUI display.
;; This file has not been run in the local headless workspace.
(require racket/class racket/gui/base framework rackunit
         "../tool/frame-chrome.rkt"
         "../tool/layout.rkt")

(define (palette)
  (make-chrome-palette
   (color-prefs:lookup-in-color-scheme 'framework:basic-canvas-background)
   (color-prefs:lookup-in-color-scheme 'framework:default-text-color)))
(define enabled? #t)
(define frame
  (new ((make-status-chrome-mixin (lambda () enabled?)) frame:info%)
       [label "OpenRacket retained native chrome test"] [width 640] [height 420]))
(define panel (new vertical-panel% [parent (send frame get-area-container)]))
(define editor (new text%))
(send editor insert "#lang racket\n(define answer 42)\nanswer\n")
(send editor set-position 14 30)
(define canvas%
  ((make-editor-chrome-mixin (lambda () enabled?) palette)
   ((make-canvas-spacing-mixin (lambda () enabled?)) canvas:color%)))
(define canvas (new canvas% [parent panel] [editor editor]))

(test-case "actual native canvas and editor identities are preserved"
  (check-true (is-a? canvas editor-canvas%))
  (check-true (is-a? canvas canvas:color%))
  (check-eq? (send canvas get-editor) editor)
  (check-equal? (send canvas horizontal-inset) 12)
  (check-equal? (send canvas vertical-inset) 10))

(test-case "actual native painting/focus preserves text and selection"
  (define before (send editor get-text))
  (define start (send editor get-start-position))
  (define end (send editor get-end-position))
  (send canvas on-focus #t)
  (send canvas on-paint)
  (send canvas on-superwindow-activate #f)
  (send canvas on-paint)
  (send canvas on-superwindow-activate #t)
  (send canvas on-focus #f)
  (send canvas on-paint)
  (check-equal? (send editor get-text) before)
  (check-equal? (send editor get-start-position) start)
  (check-equal? (send editor get-end-position) end))

(test-case "stock native key input still reaches the original editor"
  (send editor set-position (send editor last-position))
  (send canvas on-char (new key-event% [key-code #\x]))
  (check-equal? (send editor get-text (- (send editor last-position) 1)) "x"))

(test-case "real Framework info row remains populated and independently hideable"
  (define status (send frame get-info-panel))
  (define children (send status get-children))
  (check-true (pair? children))
  (check-equal? (send status border) 6)
  (check-equal? (send status spacing) 10)
  (send frame hide-info)
  (check-true (send frame is-info-hidden?))
  (send frame show-info)
  (check-false (send frame is-info-hidden?))
  (check-equal? (send status get-children) children))

(test-case "live painter opt-out leaves original editor editable"
  (set! enabled? #f)
  (send canvas on-paint)
  (send canvas on-focus #t)
  (check-eq? (send canvas get-editor) editor)
  (send editor set-position (send editor last-position))
  (send canvas on-char (new key-event% [key-code #\y]))
  (check-equal? (send editor get-text (- (send editor last-position) 1)) "y"))

(send frame show #f)
