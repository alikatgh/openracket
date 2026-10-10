#lang racket/base
;; Derived only from the exact Racket 9.3 Framework all-string-snips mixin.
;; See vendor licenses and reports/fastpath-manifest.json for provenance.
;; This private helper is used ONLY at the pinned stock DrRacket composition.
;; The public Framework mixin/module remains byte-for-byte original.
(require racket/class racket/gui/base
         (only-in framework text:all-string-snips<%> text:all-string-snips-mixin))
(provide openracket:all-string-snips-mixin openracket-fast-path-selected?)
;; Reuse the real public interface object; never create a replacement interface.
(define all-string-snips<%> text:all-string-snips<%>)
  (define all-string-snips-mixin
    (mixin ((class->interface text%)) (all-string-snips<%>)
      (inherit find-first-snip find-snip)

      ;; OpenRacket experiment: stable stock all-string knowledge can avoid
      ;; repeated scans when the colorer opens another editor-backed input port.
      ;; No new scan, lexer setting, style update, or evaluator behavior is added.
      (define openracket-fast-path-enabled?
        (equal? (getenv "OPENRACKET_ALL_STRING_FAST_PATH") "1"))
      (define openracket-mutations-pending null)
      (define openracket-fast-path-safe? #t)

      (define/private (openracket-before-mutation kind start len thunk)
        (cond
          [(not openracket-fast-path-enabled?) (thunk)]
          [else
           (define entered? #f)
           (define completed? #f)
           (define token (vector kind start len #f))
           (dynamic-wind
             (lambda ()
               ;; Rich/unknown history is outside this shortcut's plain-stock
               ;; eligibility. Never re-enable after an unexamined insertion.
               (unless (eq? all-string-snips-state #t)
                 (set! openracket-fast-path-safe? #f))
               ;; Reentering any captured callback continuation fails closed.
               (when entered? (set! openracket-fast-path-safe? #f))
               (set! entered? #t)
               (set! openracket-mutations-pending
                     (cons token openracket-mutations-pending)))
             (lambda ()
               (begin0 (thunk)
                 (set! completed? #t)
                 (vector-set! token 3 #t)))
             (lambda ()
               (unless completed?
                 ;; This covers raised values and all other nonlocal escapes.
                 ;; Never infer that the existing stock cache was updated.
                 (set! openracket-fast-path-safe? #f)
                 (set! openracket-mutations-pending null))))]))

      (define/private (openracket-after-mutation kind start len thunk)
        (cond
          [(not openracket-fast-path-enabled?) (thunk)]
          [else
           (define entered? #f)
           (define completed? #f)
           (define token (and (pair? openracket-mutations-pending)
                              (car openracket-mutations-pending)))
           (define matching?
             (and token (eq? kind (vector-ref token 0))
                  (equal? start (vector-ref token 1))
                  (equal? len (vector-ref token 2)) (vector-ref token 3)))
           (dynamic-wind
             (lambda ()
               (unless (and (not entered?) matching?)
                 (set! openracket-fast-path-safe? #f))
               (set! entered? #t))
             (lambda () (begin0 (thunk) (set! completed? #t)))
             (lambda ()
               (unless completed? (set! openracket-fast-path-safe? #f))
               ;; An unmatched callback cannot consume some other pending edit.
               (if (and matching? (pair? openracket-mutations-pending)
                        (eq? token (car openracket-mutations-pending)))
                   (set! openracket-mutations-pending (cdr openracket-mutations-pending))
                   (set! openracket-fast-path-safe? #f))))]))

      (define/augment (on-insert start len)
        (openracket-before-mutation 'insert start len
          (lambda () (inner (void) on-insert start len))))

      (define/augment (after-delete start len)
        (openracket-after-mutation 'delete start len
          (lambda () (inner (void) after-delete start len))))

      (define/override (find-next-non-string-snip snip)
        (if (and openracket-fast-path-enabled?
                 openracket-fast-path-safe?
                 (null? openracket-mutations-pending)
                 (eq? all-string-snips-state #t)
                 ;; Keep the exact arity and stock detached-snip contract.
                 ;; Only an exact native string snip has the known field-only
                 ;; get-admin method. Subclasses/custom/invalid arguments always
                 ;; delegate, without invoking an additional virtual callback.
                 ;; A detached native snip delegates too: stock object=? raises
                 ;; for its #f admin, even when this editor is empty.
                 (or (not snip)
                     (and (is-a? snip string-snip%)
                          (eq? (object-interface snip) (class->interface string-snip%))
                          (send snip get-admin))))
            #f
            (super find-next-non-string-snip snip)))
    
      (define/private (all-string-snips?/slow)
        (let loop ([s (find-first-snip)])
          (cond
            [(not s) #t]
            [(is-a? s string-snip%) (loop (send s next))]
            [else #f])))

      (define/augment (after-insert start len)
        (openracket-after-mutation 'insert start len
          (lambda ()
            (inner (void) after-insert start len)
            (define end (+ start len))
            (when (equal? all-string-snips-state #t)
              (define init-i (box 0))
              (define init-s (find-snip start 'after-or-none init-i))
              (let loop ([s init-s]
                         [i (unbox init-i)])
                (cond
                  [(not s) (void)]
                  [(not (< i end)) (void)]
                  [(is-a? s string-snip%)
                   (when (and openracket-fast-path-enabled?
                              (not (eq? (object-interface s) (class->interface string-snip%))))
                     (set! openracket-fast-path-safe? #f))
                   (define size (send s get-count))
                   (loop (send s next) (+ i size))]
                  [else
                   (set! all-string-snips-state #f)])))
          )))

      (define/augment (on-delete start end)
        (openracket-before-mutation 'delete start end
          (lambda ()
            (inner (void) on-delete start end)
            (when (equal? all-string-snips-state #f)
              (let loop ([s (find-snip start 'after-or-none)]
                         [i start])
                (cond
                  [(not s) (void)]
                  [(not (< i end)) (void)]
                  [(is-a? s string-snip%)
                   (define size (send s get-count))
                   (loop (send s next) (+ i size))]
                  [else (set! all-string-snips-state 'dont-know)])))
          )))

      ;; (or/c #t #f 'dont-know)
      (define all-string-snips-state #t)
      (define/public (all-string-snips?)
        (cond
          [(boolean? all-string-snips-state)
           all-string-snips-state]
          [else
           (define all-string-snips? (all-string-snips?/slow))
           (set! all-string-snips-state all-string-snips?)
           all-string-snips?]))
    
      (super-new)))

;; Default-off selection uses the exact stock mixin, not a behavior-simulating
;; wrapper. Native CI must explicitly prove the selected activation flag.
(define openracket-fast-path-selected?
  (equal? (getenv "OPENRACKET_ALL_STRING_FAST_PATH") "1"))
(define openracket:all-string-snips-mixin
  (if openracket-fast-path-selected? all-string-snips-mixin text:all-string-snips-mixin))
