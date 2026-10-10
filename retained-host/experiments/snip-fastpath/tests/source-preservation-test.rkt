#lang racket/base
(require rackunit racket/match racket/list racket/runtime-path racket/file racket/string)
(define-runtime-path stock "../vendor/text-misc-v9.3.rkt")
(define-runtime-path candidate "../overlay/drracket/private/openracket-all-string-snips.rkt")
(define-runtime-path stock-unit "../vendor/unit-v9.3.rkt")
(define-runtime-path candidate-unit "../overlay/drracket/private/unit.rkt")
(define-runtime-path forbidden-overlay "../overlay/framework/private/text-misc.rkt")
(define (module-datum path)
  (match (parameterize ([read-accept-reader #t]) (call-with-input-file path read))
    [`(module ,name ,language ,body) `(module upstream ,language ,body)]))
(define (find-definition tree name)
  (cond [(and (list? tree) (>= (length tree) 3)
              (eq? (car tree) 'define) (eq? (cadr tree) name)) tree]
        [(pair? tree) (or (find-definition (car tree) name)
                          (find-definition (cdr tree) name))]
        [else #f]))
(define additions
  '(openracket-fast-path-enabled? openracket-mutations-pending openracket-fast-path-safe?
    openracket-before-mutation openracket-after-mutation on-insert after-delete
    find-next-non-string-snip))
(define removed '())
(define unwrapped '())
(define eligibility-guards-removed 0)
(define eligibility-guard
  '(when (and openracket-fast-path-enabled?
              (or (has-contract? s)
                  (not (eq? (object-interface s) (class->interface string-snip%)))))
     (set! openracket-fast-path-safe? #f)))
(define (restore-stock-scan tree)
  (cond [(pair? tree)
         (if (equal? (car tree) eligibility-guard)
             (begin (set! eligibility-guards-removed (add1 eligibility-guards-removed))
                    (restore-stock-scan (cdr tree)))
             (cons (restore-stock-scan (car tree)) (restore-stock-scan (cdr tree))))]
        [else tree]))
(define (decl-name f)
  (match f
    [`(define ,(? symbol? name) ,_ ...) name]
    [`(,(or 'define/private 'define/augment 'define/override) (,name ,_ ...) ,_ ...) name]
    [_ #f]))
(define (restore-decl f)
  (match f
    [`(define/augment (after-insert start len)
        (openracket-after-mutation 'insert start len (lambda () ,body ...)))
     (set! unwrapped (cons 'after-insert unwrapped))
     (restore-stock-scan `(define/augment (after-insert start len) ,@body))]
    [`(define/augment (on-delete start end)
        (openracket-before-mutation 'delete start end (lambda () ,body ...)))
     (set! unwrapped (cons 'on-delete unwrapped))
     `(define/augment (on-delete start end) ,@body)]
    [_ f]))
(define (restore-definition tree)
  (match tree
    [`(define all-string-snips-mixin (mixin ,inputs ,outputs ,decls ...))
     `(define all-string-snips-mixin
        (mixin ,inputs ,outputs
          ,@(for/list ([f (in-list decls)]
                       #:unless (and (memq (decl-name f) additions)
                                     (begin (set! removed (cons (decl-name f) removed)) #t)))
              (restore-decl f))))]))
(test-case "private clone preserves every original stock cache form and callback order"
  (check-equal? (restore-definition (find-definition (module-datum candidate) 'all-string-snips-mixin))
                (find-definition (module-datum stock) 'all-string-snips-mixin))
  (check-equal? (sort removed symbol<?) (sort additions symbol<?))
  (check-equal? (sort unwrapped symbol<?) '(after-insert on-delete))
  (check-equal? eligibility-guards-removed 1))
(test-case "the known DrRacket composition changes only one require and one call"
  (define original (file->string stock-unit))
  (define patched (file->string candidate-unit))
  (check-equal? (length (regexp-match* #rx"openracket:all-string-snips-mixin" patched)) 1)
  (check-equal? (length (regexp-match* #rx"openracket-all-string-snips[.]rkt" patched)) 1)
  (check-equal?
   (string-replace
    (string-replace patched "         \"openracket-all-string-snips.rkt\"\n" "")
    "(openracket:all-string-snips-mixin\n" "(text:all-string-snips-mixin\n")
   original))
(test-case "generic Framework module is not an overlay and its public interface is reused"
  (check-false (file-exists? forbidden-overlay))
  (check-equal? (find-definition (module-datum candidate) 'all-string-snips<%>)
                '(define all-string-snips<%> text:all-string-snips<%>))
  (check-equal? (find-definition (module-datum candidate) 'openracket:all-string-snips-mixin)
                '(define openracket:all-string-snips-mixin
                   (if openracket-fast-path-selected?
                       all-string-snips-mixin text:all-string-snips-mixin))))
