#lang racket/base

;; Run twice in separate Racket processes, using the installed, genuine Racket
;; runtime and the same data/skip-list dependency for both module paths:
;;   env -u OPENRACKET_INTERVAL_MAP_FAST_SET racket ... STOCK CANDIDATE off
;;   OPENRACKET_INTERVAL_MAP_FAST_SET=1 racket ... STOCK CANDIDATE on
;; This is a semantic test, not a GUI or performance benchmark.
(require racket/cmdline
         racket/contract
         racket/list
         racket/path
         racket/string)

;; Fail the process immediately. Standalone RackUnit checks can otherwise be
;; reported without providing the process exit status expected by a CI gate.
(define (check-equal? actual expected [message "values differ"])
  (unless (equal? actual expected)
    (error 'interval-map-differential "~a\n  expected: ~s\n  received: ~s"
           message expected actual)))
(define (check-true value [message "expected #t"])
  (check-equal? value #t message))

(define-values (stock-file candidate-file expected-mode)
  (command-line #:args (stock-file candidate-file expected-mode)
                (values stock-file candidate-file expected-mode)))
(unless (member expected-mode '("off" "on"))
  (error 'arguments "expected mode must be off or on"))
(unless (equal? (version) "9.3")
  (error 'interval-map-differential "The source-pinned differential gate requires Racket 9.3"))
(printf "Racket version=~a stock=~a candidate=~a expected-mode=~a\n"
        (version) stock-file candidate-file expected-mode)

(define names
  '(make-interval-map interval-map-ref interval-map-ref/bounds
    interval-map-set! interval-map-cons*! interval-map-update*!
    interval-map-remove! interval-map-expand! interval-map-contract!
    interval-map-iterate-first interval-map-iterate-next
    interval-map-iterate-key interval-map-iterate-value
    interval-map-iterate-least interval-map-iterate-greatest
    interval-map-iterate-least/start>? interval-map-iterate-least/start>=?
    interval-map-iterate-greatest/start<? interval-map-iterate-greatest/start<=?
    interval-map-iterate-least/end>? interval-map-iterate-least/end>=?
    interval-map-iterate-greatest/end<? interval-map-iterate-greatest/end<=?))
(define (load-api path)
  (define p (path->complete-path path))
  (for/hash ([name (in-list names)])
    (values name (dynamic-require p name))))
(define S (load-api stock-file))
(define C (load-api candidate-file))
(check-equal?
 (dynamic-require (path->complete-path stock-file)
                  'openracket-interval-map-fast-set-enabled?
                  (lambda () 'absent))
 'absent
 "the comparison arm must be the original stock module")
(check-equal?
 (dynamic-require (path->complete-path candidate-file)
                  'openracket-interval-map-fast-set-enabled?)
 (equal? expected-mode "on")
 "candidate must explicitly witness the requested default-off/on mode")

(define (api a name) (hash-ref a name))
(define absent (gensym 'absent))
(define checks 0)
(define operations 0)
(define label "initialization")
(define (same a b what)
  (set! checks (add1 checks))
  (check-equal? a b (format "~a: ~a" label what)))

;; Module blame names and physical source paths naturally differ. Preserve the
;; exception family, method, and expected/given contract details, rather than
;; treating those incidental locations as part of the API's behavior.
(define (exception-signature e)
  (define lines (string-split (exn-message e) "\n"))
  (list (cond [(exn:fail:contract:arity? e) 'contract-arity]
              [(exn:fail:contract? e) 'contract]
              [(exn:fail? e) 'failure]
              [else 'exception])
        (if (null? lines) "" (car lines))
        (filter (lambda (s) (regexp-match? #px"^\\s*(expected|given):" s))
                lines)))
(define (attempt f)
  (with-handlers ([exn? (lambda (e) (list 'raised (exception-signature e)))])
    (list 'returned (call-with-values f list))))

(define (make-maps #:key-contract [kc any/c] #:value-contract [vc any/c]
                   [contents null])
  (values ((api S 'make-interval-map) #:key-contract kc #:value-contract vc contents)
          ((api C 'make-interval-map) #:key-contract kc #:value-contract vc contents)))

(define (snapshot a im)
  (let loop ([it ((api a 'interval-map-iterate-first) im)] [acc null])
    (cond [it
           (loop ((api a 'interval-map-iterate-next) im it)
                 (cons (list ((api a 'interval-map-iterate-key) im it)
                             ((api a 'interval-map-iterate-value) im it))
                       acc))]
          [else (reverse acc)])))

(define (iterator-entry a im it)
  (and it
       (list ((api a 'interval-map-iterate-key) im it)
             ((api a 'interval-map-iterate-value) im it))))

(define (compare-maps sm cm #:queries? [queries? #t])
  (define ss (snapshot S sm))
  (define cs (snapshot C cm))
  (same ss cs "complete iteration bounds, order, and values")
  (when queries?
    ;; Every integer point in the represented hull, with an external margin.
    (define lo (if (null? ss) -50 (min -50 (- (caar (car ss)) 2))))
    (define hi (if (null? ss) 50 (max 50 (+ (cdar (last ss)) 2))))
    (for ([p (in-range lo (add1 hi))])
      (same (attempt (lambda () ((api S 'interval-map-ref) sm p absent)))
            (attempt (lambda () ((api C 'interval-map-ref) cm p absent)))
            (format "point lookup ~a" p))
      (same (attempt (lambda () ((api S 'interval-map-ref/bounds) sm p absent)))
            (attempt (lambda () ((api C 'interval-map-ref/bounds) cm p absent)))
            (format "point bounds lookup ~a" p)))))

(define (step sm cm description f #:queries? [queries? #t])
  (set! label description)
  (set! operations (add1 operations))
  (same (attempt (lambda () (f S sm)))
        (attempt (lambda () (f C cm)))
        "return values or method/contract failure")
  (compare-maps sm cm #:queries? queries?))

;; Empty, adjacent, overlapping, containing, contained, repeated, and negative
;; ranges. Values remain lists so later cons/update operations are meaningful.
(let-values ([(sm cm) (make-maps)])
  (compare-maps sm cm)
  (for ([spec (in-list '((-8 -3 a) (0 5 b) (5 10 c) (2 8 d)
                         (-12 15 e) (-4 4 f) (-4 4 g) (4 5 h)
                         (-100 -90 i) (90 100 j)))])
    (step sm cm (format "deterministic set ~s" spec)
          (lambda (a im)
            ((api a 'interval-map-set!) im (car spec) (cadr spec) (list (caddr spec)))))))

;; Mixed operations in a deterministic PRNG stream; operation generation is
;; independent of the skip list's own randomized insertion heights.
(define gen (make-pseudo-random-generator))
(parameterize ([current-pseudo-random-generator gen]) (random-seed 381156))
(define (draw n) (parameterize ([current-pseudo-random-generator gen]) (random n)))
(let-values ([(sm cm) (make-maps)])
  (for ([i (in-range 1200)])
    (define start (- (draw 101) 50))
    (define end (+ start 1 (draw 16)))
    (define kind (list-ref '(set set cons update remove expand contract) (draw 7)))
    (step sm cm (format "random ~a: ~a [~a,~a)" i kind start end)
          (lambda (a im)
            (case kind
              [(set) ((api a 'interval-map-set!) im start end (list i))]
              [(cons) ((api a 'interval-map-cons*!) im start end i null)]
              [(update) ((api a 'interval-map-update*!) im start end
                         (lambda (old) (append old (list (- i)))) null)]
              [(remove) ((api a 'interval-map-remove!) im start end)]
              [(expand) ((api a 'interval-map-expand!) im start end)]
              [(contract) ((api a 'interval-map-contract!) im start end)])))))

;; Invalid/empty intervals, non-integer coordinates, missing ranges, infinities.
(let-values ([(sm cm) (make-maps '(((0 . 10) . (original))))])
  (for* ([name (in-list '(interval-map-set! interval-map-cons*! interval-map-update*!
                         interval-map-remove! interval-map-expand! interval-map-contract!))]
         [bounds (in-list '((3 3) (7 2) (1/2 4) (0 2.0) (-inf.0 2) (0 +inf.0)))])
    (step sm cm (format "bounds failure ~a ~s" name bounds)
          (lambda (a im)
            (apply (api a name) im (car bounds) (cadr bounds)
                   (case name
                     [(interval-map-set!) (list '(replacement))]
                     [(interval-map-cons*!) (list 'head null)]
                     [(interval-map-update*!) (list (lambda (x) x) null)]
                     [else null])))))
  (step sm cm "remove whole map with infinities"
        (lambda (a im) ((api a 'interval-map-remove!) im -inf.0 +inf.0)))
  (step sm cm "missing default raises"
        (lambda (a im) ((api a 'interval-map-update*!) im 0 4 (lambda (x) x))))
  (step sm cm "missing point without default raises"
        (lambda (a im) ((api a 'interval-map-ref) im 42))))

;; Exact value identity must survive replacements; the optimizer cannot copy,
;; rebuild, freeze, or coalesce the values stored by callers.
(let-values ([(sm cm) (make-maps)])
  (define payload (box (vector 'mutable 1)))
  (for ([bounds (in-list '((0 10) (2 8) (-2 12) (3 7)))])
    (step sm cm (format "mutable value identity ~s" bounds)
          (lambda (a im)
            ((api a 'interval-map-set!) im (car bounds) (cadr bounds) payload)))
    (for ([p (in-range (car bounds) (cadr bounds))])
      (check-true (eq? ((api S 'interval-map-ref) sm p) payload))
      (check-true (eq? ((api C 'interval-map-ref) cm p) payload))))
  (set-box! payload (vector 'changed 2))
  (compare-maps sm cm))

;; Range overwrite identity and adjacent equal values must NOT be coalesced.
(let-values ([(sm cm) (make-maps)])
  (define value (list 'same-object))
  (for ([bounds (in-list '((0 4) (4 8) (2 6)))])
    (step sm cm (format "preserve boundaries ~s" bounds)
          (lambda (a im) ((api a 'interval-map-set!) im (car bounds) (cadr bounds) value))))
  (same (map car (snapshot C cm)) '((0 . 2) (2 . 6) (6 . 8))
        "overlap preserves stock boundary partition"))

;; Contracts: valid and invalid keys/values, and a failing updater that leaves
;; earlier interval updates visible. Public contracts must still execute.
(let-values ([(sm cm) (make-maps #:key-contract (integer-in -20 20)
                                #:value-contract (listof integer?))])
  (for ([spec (in-list '((0 3 (1)) (5 8 (2)) (-21 -19 (3))
                         (19 21 (4)) (1 2 (invalid)) (2 6 (5 6))))])
    (step sm cm (format "constrained set ~s" spec)
          (lambda (a im) ((api a 'interval-map-set!) im
                         (car spec) (cadr spec) (caddr spec)))))
  (step sm cm "constrained updater result fails after partial success"
        (lambda (a im)
          (define n 0)
          ((api a 'interval-map-update*!) im 0 8
           (lambda (old)
             (set! n (add1 n))
             (if (= n 2) '(invalid) (cons 99 old)))
           null))))

;; Side-effecting flat contracts are legal: the optimized setter must neither
;; bypass nor multiply their observations, even on a rejected replacement.
(let ()
  (define sl null)
  (define cl null)
  (define (make-observed a)
    (define (record kind x)
      (if (eq? a S) (set! sl (cons (list kind x) sl))
          (set! cl (cons (list kind x) cl))))
    ((api a 'make-interval-map)
     #:key-contract
     (flat-named-contract 'observed-key
                          (lambda (x) (record 'key x) (<= -10 x 10)))
     #:value-contract
     (flat-named-contract 'observed-value
                          (lambda (x) (record 'value x) (and (list? x) (andmap integer? x))))))
  (define sm (make-observed S))
  (define cm (make-observed C))
  (for ([spec (in-list '((0 4 (1)) (1 3 (2)) (-11 4 (3)) (0 2 (bad))))])
    (set! sl null)
    (set! cl null)
    (step sm cm (format "observable contracts ~s" spec)
          (lambda (a im) ((api a 'interval-map-set!) im
                         (car spec) (cadr spec) (caddr spec))))
    (same sl cl "key/value contract invocation order and multiplicity")))

;; Callback invocation order, default-thunk single evaluation, exceptions and
;; partial-state visibility on the UNCHANGED arbitrary updater/cons paths.
(for ([scenario (in-list '(side-effects updater-raises default-raises))])
  (let-values ([(sm cm) (make-maps '(((0 . 2) . (a)) ((4 . 6) . (b))
                                   ((8 . 10) . (c))))])
    (define sl null)
    (define cl null)
    (define (record! a x)
      (if (eq? a S) (set! sl (cons x sl)) (set! cl (cons x cl))))
    (step sm cm (format "callbacks ~a" scenario)
          (lambda (a im)
            (define calls 0)
            ((api a 'interval-map-update*!) im 0 12
             (lambda (old)
               (set! calls (add1 calls))
               (record! a (list 'update calls old))
               (when (and (eq? scenario 'updater-raises) (= calls 3))
                 (error 'test-updater "intentional failure"))
               (cons calls old))
             (lambda ()
               (record! a 'default)
               (when (eq? scenario 'default-raises)
                 (error 'test-default "intentional failure"))
               null))))
    (same sl cl "callback/default order and multiplicity")))

;; A reentrant updater changes its own map. Do not assert desirable behavior;
;; assert exactly the stock behavior, including any stock exception/partial map.
(for ([action (in-list '(set remove expand contract))])
  (let-values ([(sm cm) (make-maps '(((0 . 2) . (a)) ((4 . 6) . (b))))])
    (step sm cm (format "reentrant updater ~a" action)
          (lambda (a im)
            (define once? #f)
            ((api a 'interval-map-update*!) im 0 6
             (lambda (old)
               (unless once?
                 (set! once? #t)
                 (case action
                   [(set) ((api a 'interval-map-set!) im 0 2 '(replacement))]
                   [(remove) ((api a 'interval-map-remove!) im 0 2)]
                   [(expand) ((api a 'interval-map-expand!) im 0 1)]
                   [(contract) ((api a 'interval-map-contract!) im 2 3)]))
               (cons 'visited old))
             null)))))

;; Keep actual pre-existing iterator objects through splits, deletions,
;; insertion, expansion and contraction. Deleted iterators may reject key/value
;; queries while next repairs to a surviving successor; compare all three.
(let-values ([(sm cm) (make-maps '(((0 . 10) . (a)) ((20 . 30) . (b))
                                 ((40 . 50) . (c))))])
  (define (collect a im)
    (let loop ([it ((api a 'interval-map-iterate-first) im)])
      (if it (cons it (loop ((api a 'interval-map-iterate-next) im it))) null)))
  (define sits (collect S sm))
  (define cits (collect C cm))
  (for ([spec (in-list '((set 3 7) (set 20 30) (set 35 45)
                         (expand 1 4) (contract 7 12) (set -5 60)))])
    (step sm cm (format "retained iterators ~s" spec)
          (lambda (a im)
            (case (car spec)
              [(set) ((api a 'interval-map-set!) im (cadr spec) (caddr spec) '(new))]
              [(expand) ((api a 'interval-map-expand!) im (cadr spec) (caddr spec))]
              [(contract) ((api a 'interval-map-contract!) im (cadr spec) (caddr spec))])))
    (for ([si (in-list sits)] [ci (in-list cits)] [index (in-naturals)])
      (for ([name (in-list '(interval-map-iterate-key interval-map-iterate-value))])
        (same (attempt (lambda () ((api S name) sm si)))
              (attempt (lambda () ((api C name) cm ci)))
              (format "retained iterator ~a ~a" index name)))
      (same (attempt (lambda () (iterator-entry S sm ((api S 'interval-map-iterate-next) sm si))))
            (attempt (lambda () (iterator-entry C cm ((api C 'interval-map-iterate-next) cm ci))))
            (format "retained iterator ~a next/repair" index)))))

;; Ordered endpoint searches are another observable representation boundary.
(let-values ([(sm cm) (make-maps '(((-8 . -3) . (a)) ((0 . 3) . (b))
                                 ((3 . 7) . (c)) ((10 . 12) . (d))))])
  (for* ([name (in-list '(interval-map-iterate-least/start>?
                         interval-map-iterate-least/start>=?
                         interval-map-iterate-greatest/start<?
                         interval-map-iterate-greatest/start<=?
                         interval-map-iterate-least/end>?
                         interval-map-iterate-least/end>=?
                         interval-map-iterate-greatest/end<?
                         interval-map-iterate-greatest/end<=?))]
         [point (in-range -10 15)])
    (set! label (format "ordered query ~a ~a" name point))
    (same (attempt (lambda () (iterator-entry S sm ((api S name) sm point))))
          (attempt (lambda () (iterator-entry C cm ((api C name) cm point))))
          "ordered search result")))

(printf "PASS interval-map differential mode=~a operations=~a assertions=~a seed=381156\n"
        expected-mode operations checks)
