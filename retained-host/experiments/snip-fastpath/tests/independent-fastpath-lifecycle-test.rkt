#lang racket/base
;; Execute the actual generated mixin against a deliberately small, GUI-free
;; mutation model. This verifies guard logic, not native text% behavior.
(require rackunit racket/class racket/list racket/match racket/runtime-path)
(define-runtime-path candidate "../overlay/drracket/private/openracket-all-string-snips.rkt")
(define-runtime-path stock "../vendor/text-misc-v9.3.rkt")
(define-runtime-path forbidden-framework-overlay "../overlay/framework/private/text-misc.rkt")
(define-namespace-anchor here)
(define public-all-string-interface (interface () all-string-snips?))

(define snip%
  (class object%
    (super-new)
    (field [following #f])
    (define/public (next) following)
    (define/public (link! s) (set! following s))
    (define/public (get-count) 1)))
(define string-snip% (class snip% (super-new)))

(define text%
  (class object%
    (super-new)
    (field [contents '()] [delegations 0] [first-calls 0] [first-fails? #f]
           [observer (lambda args (void))])
    (define/public (observe! f) (set! observer f))
    (define/public (observe kind start len) (observer this kind start len))
    (define/public (get-delegations) delegations)
    (define/public (get-first-calls) first-calls)
    (define/public (fail-first! flag) (set! first-fails? flag))
    (define/public (all-snips) contents)
    (define/private (replace! values)
      (set! contents values)
      (for ([s (in-list contents)] [n (in-list (if (null? contents) '() (append (cdr contents) '(#f))))])
        (send s link! n)))
    ;; Model an allowed custom snip merge performed by a style change, which
    ;; changes the native linked list without insert/delete notifications.
    (define/public (silent-replace! values) (replace! values))
    (define/public (find-first-snip)
      (set! first-calls (add1 first-calls))
      (when first-fails? (error 'find-first-snip "unexpected extra virtual call"))
      (and (pair? contents) (car contents)))
    (define/public (find-snip pos direction [where #f])
      (when where (set-box! where pos))
      (and (< pos (length contents)) (list-ref contents pos)))
    (define/public (find-next-non-string-snip value)
      (set! delegations (add1 delegations))
      (unless (or (not value) (is-a? value snip%))
        (raise-argument-error 'find-next-non-string-snip "(or/c #f snip%)" value))
      (define tail (if value (let ([found (memq value contents)]) (and found (cdr found))) contents))
      (and tail (for/or ([s (in-list tail)]) (and (not (is-a? s string-snip%)) s))))
    (define/pubment (on-insert start len) (inner (void) on-insert start len))
    (define/pubment (after-insert start len) (inner (void) after-insert start len))
    (define/pubment (on-delete start len) (inner (void) on-delete start len))
    (define/pubment (after-delete start len) (inner (void) after-delete start len))
    (define/public (insert! s [pos (length contents)])
      (send this on-insert pos 1)
      (replace! (append (take contents pos) (list s) (drop contents pos)))
      (send this observe 'between-insert pos 1)
      (send this after-insert pos 1))
    (define/public (delete! pos)
      (send this on-delete pos 1)
      (replace! (append (take contents pos) (drop contents (add1 pos))))
      (send this observe 'between-delete pos 1)
      (send this after-delete pos 1))))

(define (module-forms file)
  (match (parameterize ([read-accept-reader #t]) (call-with-input-file file read))
    [`(module ,_ ,_ (#%module-begin ,forms ...)) forms]))
(define forms (module-forms candidate))
(define stock-forms
  (for/first ([f (in-list (module-forms stock))]
              #:when (and (pair? f) (eq? (car f) 'define-unit)))
    (cddr f)))
(define stock-mixin-form
  (for/first ([f (in-list stock-forms)]
              #:when (match f [`(define all-string-snips-mixin ,_) #t] [_ #f])) f))
(define (fixture [enabled? #t] #:details? [details? #f])
  (define ns (make-base-namespace))
  (namespace-attach-module (namespace-anchor->namespace here) 'racket/class ns)
  (define mixed
    (parameterize ([current-namespace ns])
      (namespace-require 'racket/class)
      (for ([entry (in-list (list (cons 'text% text%) (cons 'snip% snip%)
                                 (cons 'string-snip% string-snip%)
                                 (cons 'text:all-string-snips<%> public-all-string-interface)
                                 (cons 'getenv (lambda (_) (if enabled? "1" #f)))))])
        (namespace-set-variable-value! (car entry) (cdr entry) #t))
      (eval '(define all-string-snips<%> text:all-string-snips<%>))
      (eval stock-mixin-form)
      (define stock-mixin (eval 'all-string-snips-mixin))
      (namespace-set-variable-value! 'text:all-string-snips-mixin stock-mixin #t)
      (for ([f (in-list forms)]
            #:when (match f [`(define ,name ,_ ...)
                            (memq name '(all-string-snips<%> all-string-snips-mixin
                                         openracket-fast-path-selected? openracket:all-string-snips-mixin))]
                     [_ #f]))
        (eval f))
      (define selected (eval 'openracket:all-string-snips-mixin))
      (cons (selected text%)
            (hash 'selected selected 'stock stock-mixin
                  'public-interface (eval 'all-string-snips<%>)))))
  (define instance
    (new (class (car mixed)
         (super-new)
         (define/augment (on-insert start len) (send this observe 'on-insert start len))
         (define/augment (after-insert start len) (send this observe 'after-insert start len))
         (define/augment (on-delete start len) (send this observe 'on-delete start len))
         (define/augment (after-delete start len) (send this observe 'after-delete start len)))))
  (if details? (values instance (cdr mixed)) instance))

(test-case "private selection keeps exact public interface and exact default stock mixin"
  (define-values (off off-details) (fixture #f #:details? #t))
  (define-values (on on-details) (fixture #t #:details? #t))
  (check-eq? (hash-ref off-details 'selected) (hash-ref off-details 'stock))
  (check-not-eq? (hash-ref on-details 'selected) (hash-ref on-details 'stock))
  (for ([t (in-list (list off on))] [details (in-list (list off-details on-details))])
    (check-eq? (hash-ref details 'public-interface) public-all-string-interface)
    (check-true (is-a? t public-all-string-interface)))
  (check-false (file-exists? forbidden-framework-overlay)))

(test-case "generic original Framework mixin still preserves custom superclass query"
  (define-values (on details) (fixture #t #:details? #t))
  (define custom%
    (class text%
      (super-new)
      (define/override (find-next-non-string-snip value) 'superclass-observed)))
  (define generic (new ((hash-ref details 'stock) custom%)))
  (check-eq? (send generic find-next-non-string-snip #f) 'superclass-observed)
  (check-true (is-a? generic public-all-string-interface)))

(test-case "stable text fast path preserves reflective arity and invalid argument errors"
  (define t (fixture))
  (define s (new string-snip%)) (send t insert! s)
  (for ([value (in-list (list #f s (new snip%) (new string-snip%)))])
    (check-false (send t find-next-non-string-snip value)))
  (check-equal? (send t get-delegations) 0)
  (for ([n '(0 1 2)])
    (check-equal? (object-method-arity-includes? t 'find-next-non-string-snip n) (= n 1)))
  (check-exn exn:fail:contract:arity? (lambda () (send t find-next-non-string-snip)))
  (check-exn exn:fail:contract:arity? (lambda () (send t find-next-non-string-snip #f #f)))
  (for ([value '(42 "snip" #(snip))])
    (check-exn exn:fail:contract? (lambda () (send t find-next-non-string-snip value))))
  (check-equal? (send t get-delegations) 3))

(test-case "default-off delegates even a known all-string buffer"
  (define t (fixture #f)) (send t insert! (new string-snip%))
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 1))

(test-case "query after native-model mutation and before stock cache update sees rich snip"
  (define t (fixture)) (define rich (new snip%))
  (define observations '())
  (send t observe! (lambda (self kind start len)
                    (when (memq kind '(between-insert after-insert))
                      (set! observations (cons (send self find-next-non-string-snip #f) observations)))))
  (send t insert! rich)
  (check-equal? observations (list rich rich))
  (check-eq? (send t find-next-non-string-snip #f) rich))

(test-case "inner after-insert exception leaves fast path permanently closed"
  (define t (fixture)) (define rich (new snip%))
  (send t observe! (lambda (self kind start len)
                    (when (eq? kind 'after-insert) (error 'plugin "after mutation"))))
  (check-exn exn:fail? (lambda () (send t insert! rich)))
  (send t observe! void)
  (check-eq? (send t find-next-non-string-snip #f) rich)
  ;; Stock cache is still #t after this exception; the new method must not trust it.
  (check-true (send t all-string-snips?))
  (check-eq? (send t find-next-non-string-snip #f) rich))

(test-case "non-exception escape after mutation also permanently fails closed"
  (define t (fixture)) (define rich (new snip%))
  (let/ec escape
    (send t observe! (lambda (self kind start len) (when (eq? kind 'after-insert) (escape 'escaped))))
    (send t insert! rich))
  (send t observe! void)
  (check-eq? (send t find-next-non-string-snip #f) rich))

(test-case "unknown cache does not introduce a new find-first-snip callback"
  (define t (fixture)) (define rich (new snip%))
  (send t insert! rich) (send t delete! 0)
  (send t fail-first! #t)
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-first-calls) 0)
  (check-equal? (send t get-delegations) 1))

(test-case "unmatched on-hook and mismatched completion cannot enable optimization"
  (define t (fixture))
  (send t on-insert 0 1)
  (send t after-delete 0 1)
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 1))

(test-case "direct or repeated after-hooks are fail-closed"
  (define t (fixture))
  (send t after-delete 0 1)
  (send t after-delete 0 1)
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 1))

(test-case "nested mutation keeps outer guard until original cache update finishes"
  (define t (fixture)) (define rich (new snip%)) (define entered? #f)
  (send t observe! (lambda (self kind start len)
                    (when (and (eq? kind 'after-insert) (not entered?))
                      (set! entered? #t)
                      (send self insert! rich)
                      (check-eq? (send self find-next-non-string-snip #f) rich))))
  (send t insert! (new string-snip%))
  (check-eq? (send t find-next-non-string-snip #f) rich))

(test-case "completion from inside an unfinished on-hook cannot certify stability"
  (define t (fixture))
  (send t observe! (lambda (self kind start len)
                    (when (eq? kind 'on-insert) (send self after-insert start len))))
  (send t insert! (new string-snip%))
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 1))

(test-case "continuation reentry cannot recertify a completed mutation"
  (define t (fixture))
  (define tag (make-continuation-prompt-tag 'independent-mutation))
  (define resume #f)
  (send t observe! (lambda (self kind start len)
                    (when (eq? kind 'after-insert)
                      (call-with-composable-continuation
                       (lambda (k) (set! resume k)) tag))))
  (call-with-continuation-prompt (lambda () (send t insert! (new string-snip%))) tag)
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 0)
  (call-with-continuation-prompt (lambda () (resume (void))) tag)
  (check-false (send t find-next-non-string-snip #f))
  (check-equal? (send t get-delegations) 1))

(test-case "string-snip subclasses preserve results through conservative delegation"
  (define derived-string% (class string-snip% (super-new)))
  (define t (fixture))
  (send t insert! (new derived-string%))
  (check-false (send t find-next-non-string-snip #f))
  (check-true (send t all-string-snips?))
  (check-equal? (send t get-delegations) 1))

(test-case "custom string merge cannot hide a rich snip behind stale true cache"
  (define derived-string% (class string-snip% (super-new)))
  (define t (fixture)) (define rich (new snip%))
  (send t insert! (new derived-string%))
  (send t silent-replace! (list rich))
  (check-true (send t all-string-snips?) "The original cache can remain stale after a custom merge")
  (check-eq? (send t find-next-non-string-snip #f) rich)
  (check-equal? (send t get-delegations) 1))

(test-case "rich or unknown mutation history cannot later recertify an unexamined subclass"
  (define derived-string% (class string-snip% (super-new)))
  (define t (fixture)) (define rich (new snip%))
  (send t insert! rich)
  (check-false (send t all-string-snips?))
  (send t delete! 0)
  ;; At insertion the stock cache is unknown, so its existing scan is skipped.
  (send t insert! (new derived-string%))
  (check-true (send t all-string-snips?))
  (send t silent-replace! (list rich))
  (check-eq? (send t find-next-non-string-snip #f) rich))
