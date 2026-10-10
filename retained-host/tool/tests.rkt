#lang racket/base
(require rackunit racket/class racket/list racket/runtime-path setup/getinfo
         "appearance-state.rkt"
         "layout.rkt")

(define-runtime-path here ".")
(define-runtime-path tool-source "tool.rkt")
(define info (get-info/full here))
(define schemes (info 'framework:color-schemes))

(define (color? c)
  (and (vector? c) (memv (vector-length c) '(3 4))
       (for/and ([v (in-vector c)] [i (in-naturals)])
         (if (< i 3) (byte? v) (and (real? v) (<= 0 v 1))))))
(define (luminance c)
  (define (linear x)
    (define s (/ x 255.0))
    (if (<= s 0.04045) (/ s 12.92) (expt (/ (+ s 0.055) 1.055) 2.4)))
  (+ (* 0.2126 (linear (vector-ref c 0)))
     (* 0.7152 (linear (vector-ref c 1)))
     (* 0.0722 (linear (vector-ref c 2)))))
(define (contrast a b)
  (define x (luminance a)) (define y (luminance b))
  (/ (+ (max x y) .05) (+ (min x y) .05)))

(test-case "profile mutation requires an explicit proof opt-in"
  (check-false (host-theme-enabled? #f #f))
  (check-false (host-theme-enabled? "true" #f))
  (check-false (host-theme-enabled? "0" "modern"))
  (check-false (host-theme-enabled? "1" "stock"))
  (check-true (host-theme-enabled? "1" #f))
  (check-true (host-theme-enabled? "1" "modern")))

(test-case "standard DrRacket tool registration and paired schemes"
  (check-equal? (info 'drracket-tools) '(("tool.rkt")))
  (check-equal? (map (lambda (s) (hash-ref s 'name)) schemes)
                '("OpenRacket Light" "OpenRacket Dark"))
  (check-equal? (map (lambda (s) (hash-ref s 'white-on-black-base?)) schemes) '(#f #t))
  (check-equal? (map car (hash-ref (car schemes) 'colors))
                (map car (hash-ref (cadr schemes) 'colors)))
  (for ([scheme (in-list schemes)])
    (define colors (hash-ref scheme 'colors))
    (check-equal? (length colors) (length (remove-duplicates (map car colors))))
    (for ([entry (in-list colors)])
      (check-true (symbol? (car entry)))
      (check-not-false (color? (cadr entry))))))

(test-case "normal editor and syntax text have at least 4.5:1 contrast"
  (for ([scheme (in-list schemes)])
    (define colors (hash-ref scheme 'colors))
    (define bg (cadr (assq 'framework:basic-canvas-background colors)))
    (for ([entry (in-list colors)]
          #:when (or (eq? (car entry) 'framework:default-text-color)
                     (eq? (car entry) 'framework:line-numbers)
                     (regexp-match? #rx"syntax-color:scheme:|read-eval-print-loop:|at-top-of-interactions"
                                    (symbol->string (car entry)))))
      (check-true (>= (contrast bg (cadr entry)) 4.5)
                  (format "~a: ~a has contrast ~a"
                          (hash-ref scheme 'name) (car entry) (contrast bg (cadr entry)))))))

(test-case "font selection uses an installed face and preserves a fallback"
  (check-equal? (preferred-editor-face '("Menlo" "JetBrains Mono") "Monospace")
                "JetBrains Mono")
  (check-equal? (preferred-editor-face '("DejaVu Sans Mono") "Monospace")
                "DejaVu Sans Mono")
  (check-equal? (preferred-editor-face '("Proportional") "Monospace") "Monospace"))

(define retained-editor (gensym 'stock-editor))
(define calls '())
(define fake-canvas%
  (class object%
    (super-new)
    (define h 5) (define v 5)
    (define/public (horizontal-inset [x #f]) (if x (set! h x) h))
    (define/public (vertical-inset [x #f]) (if x (set! v x) v))
    (define/public (get-editor) retained-editor)
    (define/public (on-event event) (set! calls (cons event calls)))))

(test-case "canvas mixin changes only insets and inherits editor/events"
  (define c (new ((make-canvas-spacing-mixin (lambda () #t)) fake-canvas%)))
  (check-true (is-a? c fake-canvas%))
  (check-eq? (send c get-editor) retained-editor)
  (check-equal? (send c horizontal-inset) 12)
  (check-equal? (send c vertical-inset) 10)
  (send c on-event 'stock-event)
  (check-equal? calls '(stock-event))
  (check-equal? (sort (interface->method-names (object-interface c)) symbol<?)
                (sort (interface->method-names (class->interface fake-canvas%)) symbol<?)))

(test-case "disabled mixin preserves stock canvas geometry"
  (define c (new ((make-canvas-spacing-mixin (lambda () #f)) fake-canvas%)))
  (check-equal? (send c horizontal-inset) 5)
  (check-equal? (send c vertical-inset) 5))

(define fake-panel%
  (class object%
    (init-field [parent #f])
    (super-new)
    (define s 0) (define b 0)
    (define/public (get-parent) parent)
    (define/public (spacing [x #f]) (if x (set! s x) s))
    (define/public (border [x #f]) (if x (set! b x) b))))

(test-case "frame retains toolbar parent, child identity, and stock methods"
  (define top (new fake-panel%))
  (define buttons (new fake-panel% [parent top]))
  (define order '())
  (define fake-frame%
    (class object%
      (super-new)
      (set! order (append order '(stock-frame)))
      (define/public (get-button-panel) buttons)
      (define/public (execute-callback) 'stock-execute)))
  (define initialize! (lambda () (set! order (append order '(initialize)))))
  (define f (new ((make-frame-spacing-mixin initialize! (lambda () #t)) fake-frame%)))
  (check-equal? order '(initialize stock-frame))
  (check-true (is-a? f fake-frame%))
  (check-eq? (send f get-button-panel) buttons)
  (check-eq? (send buttons get-parent) top)
  (check-equal? (send buttons spacing) 6)
  (check-equal? (send top spacing) 6)
  (check-equal? (send top border) 8)
  (check-eq? (send f execute-callback) 'stock-execute))

(test-case "disabled frame mixin leaves stock toolbar spacing alone"
  (define top (new fake-panel%))
  (define buttons (new fake-panel% [parent top]))
  (define fake-frame%
    (class object%
      (super-new)
      (define/public (get-button-panel) buttons)))
  (define f (new ((make-frame-spacing-mixin void (lambda () #f)) fake-frame%)))
  (check-eq? (send f get-button-panel) buttons)
  (check-equal? (send buttons spacing) 0)
  (check-equal? (send top spacing) 0)
  (check-equal? (send top border) 0))

(test-case "GUI module syntax reads without invoking an unavailable display"
  (parameterize ([read-accept-reader #t])
    (check-not-false (call-with-input-file tool-source read-syntax))))

(define snapshot
  (map cons appearance-pref-keys
       (list 'temporarily-absent-light 'temporarily-absent-dark 'platform
             "Existing Mono" (vector (hash '((1920 1080)) 16) 14) 'default)))

(test-case "initial appearance retains stock mode unless explicitly selected"
  (for ([mode '(#f #t platform)])
    (check-eq? (initial-color-mode #f mode) mode)
    (check-eq? (initial-color-mode "unknown" mode) mode)
    (check-false (initial-color-mode "light" mode))
    (check-true (initial-color-mode "dark" mode))))

(test-case "saved appearance validates every original preference type"
  (check-true (snapshot-value? #f))
  (check-true (snapshot-value? snapshot))
  (check-false (snapshot-value? (reverse snapshot)))
  (for ([index (in-range (length appearance-pref-keys))]
        [bad (in-list '("not-a-symbol" 7 automatic 99 13 antialiased))])
    (check-false
     (snapshot-value?
      (list-set snapshot index (cons (list-ref appearance-pref-keys index) bad))))))

(test-case "rollback keeps absent scheme identifiers and refreshes correct fallbacks"
  (define prefs (make-hasheq))
  (define refreshed '())
  (define (effective dark?)
    (check-eq? (hash-ref prefs (if dark? 'framework:color-scheme-dark 'framework:color-scheme-light))
               (if dark? 'temporarily-absent-dark 'temporarily-absent-light))
    (if dark? 'white-on-black 'classic))
  (define (set-scheme! name)
    (set! refreshed (append refreshed (list name)))
    (hash-set! prefs (if (eq? name 'white-on-black)
                        'framework:color-scheme-dark 'framework:color-scheme-light) name))
  (restore-appearance! snapshot (lambda (key value) (hash-set! prefs key value)) effective set-scheme!)
  (check-equal? refreshed '(classic white-on-black))
  (check-equal? (for/list ([key (in-list appearance-pref-keys)]) (cons key (hash-ref prefs key))) snapshot))

(test-case "rollback attempts remaining preferences after a callback fails"
  (define prefs (make-hasheq))
  (define (put-pref! key value)
    (hash-set! prefs key value)
    (when (eq? key 'framework:white-on-black-mode?) (error 'fixture "callback failed")))
  (check-exn #rx"callback failed"
             (lambda ()
               (restore-appearance! snapshot put-pref!
                                    (lambda (dark?) (if dark? 'white-on-black 'classic))
                                    (lambda (name) (error 'fixture "style callback failed")))))
  (check-equal? (for/list ([key (in-list appearance-pref-keys)]) (cons key (hash-ref prefs key))) snapshot))
