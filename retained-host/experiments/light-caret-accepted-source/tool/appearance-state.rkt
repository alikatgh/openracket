#lang racket/base

;; Preference bookkeeping only. No GUI imports, evaluator, or editor state.
(provide appearance-pref-keys snapshot-value? restore-appearance! initial-color-mode)

(define (initial-color-mode explicit-theme current-mode)
  (cond [(equal? explicit-theme "light") #f]
        [(equal? explicit-theme "dark") #t]
        [else current-mode]))

(define appearance-pref-keys
  '(framework:color-scheme-light
    framework:color-scheme-dark
    framework:white-on-black-mode?
    framework:standard-style-list:font-name
    framework:standard-style-list:font-size
    framework:standard-style-list:smoothing))

(define (font-size-value? value)
  (and (vector? value) (= (vector-length value) 2)
       (hash? (vector-ref value 0)) (byte? (vector-ref value 1))
       (for/and ([(monitors size) (in-hash (vector-ref value 0))])
         (and (byte? size) (pair? monitors) (list? monitors)
              (for/and ([dimensions (in-list monitors)])
                (and (list? dimensions) (= (length dimensions) 2)
                     (andmap exact-nonnegative-integer? dimensions)))))))

(define (snapshot-value? value)
  (or (not value)
      (and (list? value)
           (= (length value) (length appearance-pref-keys))
           (for/and ([entry (in-list value)] [key (in-list appearance-pref-keys)])
             (and (pair? entry) (eq? (car entry) key)
                  (case key
                    [(framework:color-scheme-light framework:color-scheme-dark)
                     (symbol? (cdr entry))]
                    [(framework:white-on-black-mode?)
                     (or (boolean? (cdr entry)) (eq? (cdr entry) 'platform))]
                    [(framework:standard-style-list:font-name) (string? (cdr entry))]
                    [(framework:standard-style-list:font-size) (font-size-value? (cdr entry))]
                    [(framework:standard-style-list:smoothing)
                     (and (memq (cdr entry) '(unsmoothed partly-smoothed smoothed default)) #t)]))))))

(define (restore-appearance! snapshot put-pref! effective-scheme-name set-scheme!)
  (unless (snapshot-value? snapshot)
    (raise-argument-error 'restore-appearance! "snapshot-value?" snapshot))
  (when snapshot
    (define errors '())
    (define (attempt thunk)
      (with-handlers ([exn:fail? (lambda (e) (set! errors (cons e errors)) #f)])
        (thunk)))
    ;; A third-party preference callback may fail after its value was written.
    ;; Keep restoring the remaining settings, then report the first failure.
    (for ([entry (in-list snapshot)])
      (attempt (lambda () (put-pref! (car entry) (cdr entry)))))
    ;; The Framework getter resolves missing saved names to the correct light /
    ;; dark fallback. Passing the absent saved name directly to the setter would
    ;; always choose Classic and overwrite the saved light preference.
    (for ([dark? (in-list '(#f #t))])
      (attempt (lambda () (set-scheme! (effective-scheme-name dark?)))))
    ;; Refreshing effective schemes writes preference names. Preserve the exact
    ;; original names afterward, including schemes temporarily not installed.
    (for ([key (in-list '(framework:color-scheme-light framework:color-scheme-dark))])
      (attempt (lambda () (put-pref! key (cdr (assq key snapshot))))))
    (unless (null? errors) (raise (car (reverse errors))))))
