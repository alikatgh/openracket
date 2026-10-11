#lang racket/base
;; Native-only actual-source test. Do not count source checks as execution.
(require racket/class racket/contract racket/list racket/set racket/string
         racket/cmdline
         (prefix-in s: "generated/stock.rkt")
         (prefix-in c: "generated/candidate.rkt")
         (prefix-in f: "generated/candidate-fault.rkt")
         (prefix-in g: "generated/stock-fault.rkt"))
(define expected (command-line #:args (mode) mode))
(unless (member expected '("off" "on")) (error 'args "mode must be off/on"))
(unless (equal? (version) "9.3") (error 'version "Racket 9.3 is required"))
(define enabled? (equal? expected "on"))
(define checks 0)
(define (stage! label)
  (printf "BINDINGS_EAGER_STAGE ~a mode=~a\n" label expected)
  (flush-output))
(define (same a b [why "values"])
  (set! checks (add1 checks))
  (unless (equal? a b) (error 'binding-differential "~a: ~s differs from ~s" why a b)))
(define (require! a why) (same (and a #t) #t why))
(same c:openracket-binding-table-eager-enabled? enabled? "read-only activation")
(same s:openracket-binding-table-eager-enabled? #f "stock arm")
(define stock% (s:make-test-class object%))
(define candidate% (c:make-test-class object%))
(define (pair [candidate-class candidate%])
  (values (new stock%) (new candidate-class)))
(define (state c key) (hash-ref (send c test:state) key))
(define (sig e)
  (list (cond [(exn:fail:contract? e) 'contract] [(exn:fail? e) 'failure] [else 'exception])
        (car (string-split (exn-message e) "\n"))))
(define (try f)
  (with-handlers ([exn? (lambda (e) (list 'raised (sig e)))])
    (list 'returned (call-with-values f list))))
;; A throwing custom hash can abandon stock CS's mutable-hash semaphore.
;; Observe only in a separately owned worker: never block the main test thread
;; on that table. A timeout is expected lock-boundary evidence, not a speed gate.
;; Returned values and all raised values remain distinct, typed test outcomes.
(define (observe-poisoned-count table label)
  (define owner (make-custodian))
  (define entered (make-semaphore 0))
  (define result (make-channel))
  (define worker #f)
  (stage! (format "~a count-probe-begin" label))
  (define observed
    (dynamic-wind
      void
      (lambda ()
        (set! worker
              (parameterize ([current-custodian owner])
                (thread
                 (lambda ()
                   (semaphore-post entered)
                   (with-handlers ([(lambda (value) #t)
                                    (lambda (value)
                                      (channel-put result
                                                   (list 'raised
                                                         (if (exn? value) (sig value)
                                                             (list 'non-exception value)))))])
                     (channel-put result (list 'returned (hash-count table))))))))
        (require! (sync/timeout 5 entered) "poisoned-table observer entered")
        (define answer (sync/timeout 1 result))
        (unless answer
          (require! (not (thread-dead? worker)) "poisoned-table observer is live at the bound"))
        answer)
      (lambda ()
        (custodian-shutdown-all owner)
        (when worker
          (require! (sync/timeout 5 (thread-dead-evt worker))
                    "poisoned-table observer stopped and reaped")))))
  (printf "CUSTOM_HASH_LOCK_BOUNDARY arm=~a outcome=~s mode=~a\n"
          label (or observed 'blocked-within-window) expected)
  (flush-output)
  (same observed #f "stock hash count blocked within one-second observation window")
  observed)
(define (add s c a b d e f g)
  (define sr (try (lambda () (send s test:add a b d e f g))))
  (define cr (try (lambda () (send c test:add a b d e f g))))
  (same cr sr "add return or error")
  sr)
(define (own s c a b d e) (add s c c a b c d e))
(define (ordered table)
  (for/list ([(k v) (in-hash table)]) (cons k (set->list v))))
(define (compare-current s c [why "unexposed real public table"])
  (define st (send s test:peek))
  (define ct (send c test:peek))
  (same ct st why)
  (same (ordered ct) (ordered st) "unexposed public enumeration order"))
(define (compare s c [why "public table"])
  (define st (send s syncheck:get-bindings-table))
  (define ct (send c syncheck:get-bindings-table))
  (same ct st why)
  (same (ordered ct) (ordered st) "exact same-process hash/set enumeration order")
  (require! (and (hash-equal? ct) (not (immutable? ct))) "mutable equal? public hash")
  (for ([v (in-hash-values ct)])
    (require! (and (set? v) (not (set-mutable? v)) (not (set-weak? v))
                   (set-equal? v)) "ordinary immutable equal? sets")))

;; All numerical edge cases in the actual owner domain; do not expose early.
(stage! 'numerical-edges)
(let-values ([(s c) (pair)])
  (define initial (send c test:peek))
  (for ([p (in-list (list '(0 0 2 2) '(0 1 2 3) '(0 1 2 3)
                          '(0 0 0 0) '(-8 -3 -2 1) '(7 2 1 -8)
                          '(0 1 3 4) (list (expt 2 100) (expt 2 101) 3 4)))])
    (apply own s c p))
  (same (state c 'accepted) (if enabled? 6 0) "nonself unique accepted")
  (same (state c 'duplicates) (if enabled? 1 0) "duplicate rejected")
  (same (state c 'pending) 0 "no deferred entries")
  (same (state c 'eager_writes) (if enabled? 6 0) "immediate public writes")
  (same (state c 'public_keys) 5 "constant-time real public table key count")
  (same (state c 'indexed_edges) (if enabled? 6 0) "numeric duplicate index")
  (same (state c 'cached_starts) (if enabled? 5 0) "current immutable priors cache")
  (same (state c 'in_flight) #f "successful call leaves no active insertion")
  (compare-current s c)
  (send s test:tooltip) (send c test:tooltip)
  (same (send c syncheck:get-bindings-table #t)
        (send s syncheck:get-bindings-table #t) "tooltip getter exact branch")
  (same (state c 'active) enabled? "tooltip getter does not expose bindings")
  (same (send c test:state) (send c test:state) "witness is read-only")
  (require! (immutable? (send c test:state)) "witness is immutable")
  (compare s c)
  (require! (eq? initial (send c syncheck:get-bindings-table)) "initial hash identity kept")
  (same (state c 'active) #f "permanent fallback after exposure")
  (same (state c 'pending) 0 "no pending work after exposure")
  (same (state c 'materializations) 0 "getter never materializes")
  (same (state c 'eager_writes) (if enabled? 6 0) "getter does not write bindings")
  (same (state c 'indexed_edges) 0 "getter discards duplicate cache")
  (same (state c 'cached_starts) 0 "getter discards priors cache")
  (same (state c 'exposed) enabled? "enabled exposure is witnessed")
  (same (state c 'fallback_reason) (if enabled? 'public-exposure #f) "exposure reason")
  (own s c 0 1 90 92)
  (same (state c 'accepted) (if enabled? 6 0) "no later index reactivation")
  (compare s c))

;; 1,200 deterministic operations and duplicates; inspect the real table before exposure.
(stage! 'deterministic-trace)
(let-values ([(s c) (pair)])
  (define gen (make-pseudo-random-generator))
  (parameterize ([current-pseudo-random-generator gen]) (random-seed 381298))
  (define (draw n) (parameterize ([current-pseudo-random-generator gen]) (random n)))
  (for ([i (in-range 1200)])
    (define p (for/list ([j (in-range 4)]) (- (draw 100) 20)))
    (apply own s c p)
    (when (zero? (modulo i 7)) (apply own s c p))
    (when (zero? (modulo i 31)) (compare-current s c)))
  (when enabled? (require! (> (state c 'accepted) 1100) "genuine fast-path hits"))
  (compare s c "complete deterministic trace"))

;; Escaped table and immutable prior-set snapshots stay live and exact.
(stage! 'escaped-table)
(let-values ([(s c) (pair)])
  (own s c 0 1 2 3)
  (compare s c)
  (define st (send s syncheck:get-bindings-table))
  (define ct (send c syncheck:get-bindings-table))
  (define k (list c 0 1))
  (define old-s (hash-ref st k))
  (define old-c (hash-ref ct k))
  (own s c 0 1 4 5)
  (same old-c old-s "retained set snapshot")
  (same (set-count old-c) 1 "old set remains immutable snapshot")
  (same (set-count (hash-ref ct k)) 2 "escaped hash gets later insertions")
  (hash-remove! st k) (hash-remove! ct k)
  (own s c 0 1 2 3)
  (compare s c "external deletion affects future duplicate answer")
  (hash-set! st k (set (list c 10 11)))
  (hash-set! ct k (set (list c 10 11)))
  (same (own s c 0 1 10 11) '(returned (#f)) "external insertion is duplicate")
  (own s c 0 1 12 13)
  (compare s c "external immutable set accepted")
  (hash-set! st k 42) (hash-set! ct k 42)
  (require! (eq? (car (own s c 0 1 14 15)) 'raised) "invalid external value raises")
  (same (hash-ref ct k) 42 "invalid value remains unchanged")
  (hash-set! st k (mutable-set (list c 2 3)))
  (hash-set! ct k (mutable-set (list c 2 3)))
  (same (own s c 0 1 2 3) '(returned (#f)) "mutable external duplicate matches stock")
  (require! (eq? (car (own s c 0 1 14 15)) 'raised) "mutable external new entry raises")
  (hash-clear! st) (hash-clear! ct)
  (own s c 7 8 9 10)
  (compare s c "external clear")
  (define old (hash-copy ct))
  (send s syncheck:init-arrows) (send c syncheck:init-arrows)
  (same (state c 'generation) 1 "reset generation")
  (same (state c 'active) enabled? "reset re-enables only default-off experiment")
  (own s c 20 21 22 23)
  (same ct old "reset leaves old escaped table unchanged")
  (compare s c "fresh table after reset")
  (require! (not (eq? ct (send c syncheck:get-bindings-table))) "reset creates new table"))

;; Reset before exposure keeps the fully current old hash unchanged, then
;; starts a new generation. Numeric = self suppression
;; still precedes the exact-integer domain gate (including exact/inexact pairs).
(stage! 'reset-before-exposure)
(let-values ([(s c) (pair)])
  (own s c 1 2 3 4)
  (define initial (send c test:peek))
  (same (add s c c 5 6 c 5.0 6.0) '(returned (#f)) "numeric self check before guard")
  (same (state c 'active) enabled? "numeric self check does not force fallback")
  (send s syncheck:init-arrows) (send c syncheck:init-arrows)
  (same (state c 'pending) 0 "unexposed reset has no pending work")
  (same (state c 'accepted) 0 "unexposed reset clears accepts")
  (same (state c 'materializations) 0 "unexposed reset performs no materialization")
  (same (hash-count initial) 1 "old fully populated hash unchanged by reset")
  (own s c 8 9 10 11)
  (compare s c "fresh generation excludes old generation edges"))

;; Foreign self-links must not force fallback; other foreign objects must.
(stage! 'foreign-input)
(let-values ([(s c) (pair)])
  (define other (new object%))
  (own s c 0 1 2 3)
  (same (add s c other 4 5 other 4 5) '(returned (#f)) "foreign self suppressed first")
  (same (state c 'active) enabled? "foreign self leaves index untouched")
  (add s c c 4 5 other 6 7)
  (same (state c 'active) #f "foreign endpoint permanently disables caches")
  (same (state c 'unsupported_fallbacks) (if enabled? 1 0) "one unsupported fallback")
  (same (state c 'fallback_reason) (if enabled? 'unsupported-input #f) "unsupported reason")
  (own s c 8 9 10 11)
  (compare s c))

;; Chaperoned owner, equal-but-distinct transparent objects and non-integer
;; coordinates go through the original branch with the real table already current.
(for ([kind (in-list '(wrapped transparent inexact rational))])
  (stage! (format "unsupported ~a" kind))
  (let-values ([(s c) (pair)])
    (own s c 0 1 2 3)
    (case kind
      [(wrapped)
       (define wrapped (contract (object/c [test:peek (->m any/c)]) c 'provider 'client))
       (require! (object=? wrapped c) "contract wrapper represents the owner")
       (same (add s c c 0 1 wrapped 0 1) '(returned (#f)) "wrapped self check")
       (add s c wrapped 5 6 c 7 8)]
      [(transparent)
       (define t% (class object% (inspect #f) (super-new) (field [v 10])))
       (define x (new t%)) (define y (new t%))
       (require! (equal? x y) "equal-but-not-identical objects")
       (add s c x 1 2 c 3 4)
       (same (add s c y 1 2 c 3 4) '(returned (#f)) "stock equal? duplicate")]
      [(inexact) (add s c c 0.0 1.0 c 2.0 3.0)]
      [(rational) (add s c c 1/2 3/2 c 5/2 7/2)])
    (same (state c 'active) #f "unsupported domain permanently stock")
    (compare s c)))

;; Stateful foreign equality: constant hashes, actual retained callback state,
;; and a changed equality answer for an as-yet-uninserted distinct object.
;; The candidate must already be on its stock path before the toggle matters.
(stage! 'stateful-foreign-equality)
(let-values ([(s c) (pair)])
  (define equivalent? #f)
  (define equality-calls 0)
  (define foreign%
    (class* object% (equal<%>)
      (super-new)
      (define/public (equal-to? other recur)
        (set! equality-calls (add1 equality-calls))
        equivalent?)
      (define/public (equal-hash-code-of recur) 31)
      (define/public (equal-secondary-hash-code-of recur) 31)))
  (define x (new foreign%))
  (define y (new foreign%))
  (own s c 0 1 2 3)
  (same (add s c x 10 11 c 12 13) '(returned (#t)) "first foreign binding")
  (same (state c 'active) #f "stateful equality begins after permanent fallback")
  (same (state c 'pending) 0 "stateful equality begins with no pending work")
  (same (state c 'fallback_reason) (if enabled? 'unsupported-input #f)
        "foreign source selected stock before equality toggle")
  (same (equal? x y) #f "retained equality state initially distinguishes objects")
  (define original-hashes (list (equal-hash-code x) (equal-hash-code y)))
  (set! equivalent? #t)
  (same (equal? x y) #t "retained equality state changes the answer")
  (define before-stock equality-calls)
  (define stock-answer (send s test:add y 10 11 c 12 13))
  (define after-stock equality-calls)
  (define candidate-answer (send c test:add y 10 11 c 12 13))
  (same candidate-answer stock-answer "stateful foreign duplicate decisions")
  (same candidate-answer #f "equivalent new foreign object is a duplicate")
  (require! (> after-stock before-stock) "stock used retained equality callback")
  (require! (> equality-calls after-stock) "candidate used retained equality callback")
  ;; y was not inserted while equivalent. Restore distinction before inserting
  ;; it; no stored hash value changes and no equivalent stored keys are merged.
  (set! equivalent? #f)
  (same (add s c y 10 11 c 12 13) '(returned (#t))
        "distinct foreign object is accepted after equality toggles back")
  (same (list (equal-hash-code x) (equal-hash-code y)) original-hashes
        "stateful equality keeps hashes constant")
  (compare s c "stateful foreign equality final graph"))

;; Preserve the first object=?/= error before changing any cache state.
(stage! 'self-check-errors)
(for ([args (in-list (list (list #f 0 1 #f 2 3) (list 'bad 0 1 'bad 0 1)))])
  (let-values ([(s c) (pair)])
    (own s c 0 1 2 3)
    (require! (eq? (car (apply add s c args)) 'raised) "object=? input error")
    (same (state c 'active) enabled? "invalid object leaves valid caches intact before stock error")
    (compare s c)))
(let-values ([(s c) (pair)])
  (own s c 0 1 2 3)
  (require! (eq? (car (add s c c 'bad 1 c 2 3)) 'raised) "numeric self-check error")
  (same (state c 'active) enabled? "numeric error precedes any cache change")
  (compare s c))

;; The enabled scope deliberately excludes owner-defined equality/hash callbacks.
;; Exercise BOTH standard equal<%> and direct interface* prop:equal+hash, since
;; testing only equal<%> is not a sound guard against custom behavior.
(for ([direct? (in-list '(#f #t))])
  (stage! (format "custom-callback direct=~a" direct?))
  (define callbacks 0)
  (define (count-hash obj recur) (set! callbacks (add1 callbacks)) 7)
  (define base%
    (if direct?
        (let ([i<%> (interface* () ([prop:equal+hash
                                    (list (lambda (a b recur) #f) count-hash count-hash)]))])
          (class* object% (i<%>) (super-new)))
        (class* object% (equal<%>)
          (super-new)
          (define/public (equal-to? other recur) #f)
          (define/public (equal-hash-code-of recur) (count-hash this recur))
          (define/public (equal-secondary-hash-code-of recur) (count-hash this recur)))))
  (let-values ([(s c) (pair (c:make-test-class base%))])
    (send s test:add c 0 1 c 2 3)
    (send c test:add c 0 1 c 2 3)
    (set! callbacks 0)
    (send s test:add c 0 1 c 4 5)
    (define stock-count callbacks)
    (set! callbacks 0)
    (send c test:add c 0 1 c 4 5)
    (define candidate-count callbacks)
    (require! (> stock-count 0) "stock invokes owner hash callbacks")
    (if enabled?
        (require! (and (> candidate-count 0) (< candidate-count stock-count))
                  "documented eager owner callback reduction, never deferred writes")
        (same candidate-count stock-count "off preserves callback count"))
    (compare s c "pure custom callback still yields equal final data")
    (printf "CUSTOM_CALLBACK_BOUNDARY direct=~a stock=~a candidate=~a mode=~a\n"
            direct? stock-count candidate-count expected)))

;; Foreign and owning throwing hashes still fail during insertion. Custom owner
;; callback counts/order remain excluded, but no owner error is deferred to a getter.
(define throwing%
  (class* object% (equal<%>)
    (super-new)
    (define/public (equal-to? other recur) #f)
    (define/public (equal-hash-code-of recur) (error 'custom-owner-hash "deliberate"))
    (define/public (equal-secondary-hash-code-of recur) (error 'custom-owner-hash "deliberate"))))
(let-values ([(s c) (pair)])
  (define other (new throwing%))
  (stage! 'throwing-foreign-endpoint)
  (own s c 0 1 2 3)
  (require! (eq? (car (add s c c 5 6 other 7 8)) 'raised) "foreign custom hash error")
  (compare s c "published prefix preserved before foreign error"))
(let-values ([(s c) (pair (c:make-test-class throwing%))])
  (stage! 'throwing-owner)
  (define initial-stock (send s test:peek))
  (define initial-candidate (send c test:peek))
  (define stock-result (try (lambda () (send s test:add c 0 1 c 2 3))))
  (define candidate-result (try (lambda () (send c test:add c 0 1 c 2 3))))
  (require! (eq? (car stock-result) 'raised) "stock owner hash raises at insertion")
  (same candidate-result stock-result "owner-hash error still occurs during insertion")
  (stage! 'throwing-owner-error-parity)
  ;; The original getter only returns the hash; identity needs no hash lock.
  (require! (eq? initial-stock (send s syncheck:get-bindings-table))
            "stock getter returns the same table after callback escape")
  (observe-poisoned-count initial-stock 'stock)
  (cond
    [enabled?
     ;; Enabled raises in immutable set-add before taking the public hash lock.
     ;; Keep every original eager cleanup and immediate-error assertion.
     (same (state c 'active) #f "failed eager insertion permanently discards caches")
     (same (state c 'failure_fallbacks) 1 "failed eager insertion recorded")
     (same (state c 'eager_writes) 0 "no publication before throwing set-add")
     (same (hash-count (send c syncheck:get-bindings-table)) 0 "getter has no deferred error")]
    [else
     (require! (eq? initial-candidate (send c syncheck:get-bindings-table))
               "off getter returns the same table after callback escape")
     (same (observe-poisoned-count initial-candidate 'candidate-off) #f
           "off preserves stock callback lock outcome")])
  ;; Only after recording both outcomes, replace poisoned test tables. Never
  ;; query their counts, contents or witness again on the main test thread.
  (stage! 'throwing-owner-reset-after-observation)
  (send s syncheck:init-arrows) (send c syncheck:init-arrows)
  (require! (not (eq? initial-stock (send s test:peek))) "stock reset replaces poisoned table")
  (require! (not (eq? initial-candidate (send c test:peek))) "candidate reset replaces old table")
  (same (state c 'generation) 1 "reset after callback escape creates a fresh generation")
  (same (state c 'active) enabled? "fresh generation has its ordinary activation")
  (same (state c 'failure_fallbacks) 0 "reset clears previous failure diagnostics")
  (same (state c 'eager_writes) 0 "reset starts with no writes")
  (same (state c 'public_keys) 0 "fresh public hash is inspectable")
  (define other (new object%))
  (same (add s c other 0 1 other 2 3) '(returned (#t))
        "reset restores ordinary stock writes after callback escape")
  (compare s c "fresh tables agree after callback escape"))


;; Deterministic fault modules differ only by explicitly declared test hooks.
;; Production has no hook field/API. Inject before publication, after the real
;; write, and between the two auxiliary commits; every failure discards caches
;; and leaves any successful real write authoritative, without rollback.
(when enabled?
  (for* ([stage (in-list '(before-public after-public after-first-cache))]
         [kind (in-list '(exception arbitrary break escape))])
    (stage! (format "fault stage=~a kind=~a" stage kind))
    (define s (new stock%))
    (define c (new (f:make-test-class object%)))
    (define published? (not (eq? stage 'before-public)))
    (define marker (gensym 'original-raised-value))
    (define payload
      (case kind
        [(exception) (exn:fail "controlled-cache-failure" (current-continuation-marks))]
        [(break) (call-with-escape-continuation
                  (lambda (k) (exn:break "controlled-cache-break" (current-continuation-marks) k)))]
        [else marker]))
    (define (arm thunk)
      (case stage
        [(before-public) (send c test:arm-set-add! thunk)]
        [(after-public) (send c test:arm-public! thunk)]
        [(after-first-cache) (send c test:arm-cache! thunk)]))
    (when published? (same (send s test:add c 0 1 c 2 3) #t "reference successful real write"))
    (define caught
      (if (eq? kind 'escape)
          (let/ec leave
            (arm (lambda () (arm void) (leave payload)))
            (send c test:add c 0 1 c 2 3))
          (with-handlers ([(lambda (value) #t) (lambda (value) value)])
            (arm (lambda () (arm void) (raise payload)))
            (send c test:add c 0 1 c 2 3))))
    (require! (eq? caught payload) "original exception/arbitrary value/break/escape is unchanged")
    (same (state c 'active) #f "partial auxiliary state is discarded atomically")
    (same (state c 'in_flight) #f "unwind clears matching in-flight token")
    (same (state c 'indexed_edges) 0 "failed insertion exposes no auxiliary edges")
    (same (state c 'cached_starts) 0 "failed insertion exposes no auxiliary priors")
    (same (state c 'failure_fallbacks) 1 "one fail-closed interruption")
    (same (state c 'fallback_reason) 'interrupted "failure reason retained")
    (same (state c 'eager_writes) (if published? 1 0) "real write count survives auxiliary failure")
    (same (state c 'accepted) 0 "failed insertion does not claim successful return")
    (compare-current s c "failure preserves the authoritative real table")
    (same (own s c 0 1 2 3) (if published? '(returned (#f)) '(returned (#t)))
          "retry consults authoritative public table")
    (own s c 0 1 4 5)
    (same (set-count (hash-ref (send c test:peek) (list c 0 1))) 2
          "later insertion never loses published edge after cache failure")
    (compare s c)))

;; A real requested thread break, not only a raised exn:break value, must
;; unwind each publication/cache seam without leaving an active marker/cache.
(when enabled?
  (for ([stage (in-list '(before-public after-public after-first-cache))])
    (stage! (format "requested-break stage=~a" stage))
    (define s (new stock%))
    (define c (new (f:make-test-class object%)))
    (define published? (not (eq? stage 'before-public)))
    (define (arm thunk)
      (case stage
        [(before-public) (send c test:arm-set-add! thunk)]
        [(after-public) (send c test:arm-public! thunk)]
        [(after-first-cache) (send c test:arm-cache! thunk)]))
    (when published? (send s test:add c 0 1 c 2 3))
    (define caught
      (with-handlers ([exn:break? (lambda (e) e)])
        (parameterize-break #t
          (arm (lambda ()
                 (arm void)
                 (break-thread (current-thread))
                 (sync/timeout 1 never-evt)
                 (error 'requested-break "break was not delivered inside the original write")))
          (send c test:add c 0 1 c 2 3))))
    (require! (exn:break? caught) "requested break escapes as its original break exception")
    (same (state c 'active) #f "requested break disables partial cache state")
    (same (state c 'in_flight) #f "requested break leaves no stranded in-flight marker")
    (same (state c 'failure_fallbacks) 1 "requested break cleanup ran once")
    (compare-current s c "requested break preserves the actual publication boundary")
    (same (own s c 0 1 2 3) (if published? '(returned (#f)) '(returned (#t)))
          "retry after requested break uses authoritative table")
    (own s c 0 1 4 5)
    (compare s c)))

;; Metadata cleanup disables breaks only around private state changes. The
;; original real write executes with the caller's break setting unchanged.
(stage! 'caller-break-state)
(when enabled?
  (define c (new (f:make-test-class object%)))
  (define seen #f)
  (send c test:arm-set-add! (lambda () (set! seen (break-enabled))))
  (parameterize-break #t
    (same (send c test:add c 0 1 c 2 3) #t "break-enabled original write")
    (same (break-enabled) #t "caller break state remains enabled"))
  (same seen #t "original write retains caller break state")
  (same (state c 'in_flight) #f "successful normal unwind clears marker"))

;; Exposure during either an original set-add or an auxiliary commit must not
;; revive the dropped caches. The returned real hash remains the same live hash.
(stage! 'in-flight-exposure)
(when enabled?
  (for ([stage (in-list '(before-public after-public after-first-cache))])
    (stage! (format "exposure stage=~a" stage))
    (define c (new (f:make-test-class object%)))
    (define escaped #f)
    (define before (send c test:peek))
    (define (expose!) (set! escaped (send c syncheck:get-bindings-table)))
    (case stage
      [(before-public) (send c test:arm-set-add! expose!)]
      [(after-public) (send c test:arm-public! expose!)]
      [(after-first-cache) (send c test:arm-cache! expose!)])
    (same (send c test:add c 0 1 c 2 3) #t "in-flight exposure insertion completes")
    (require! (eq? escaped before) "exposure returns original live public hash")
    (same (set-count (hash-ref escaped (list c 0 1))) 1 "escaped hash receives real write")
    (same (state c 'active) #f "in-flight exposure never re-enables caches")
    (same (state c 'indexed_edges) 0 "in-flight exposure discards numeric index")
    (same (state c 'cached_starts) 0 "in-flight exposure discards priors cache")
    (same (state c 'eager_writes) 1 "one immediate write despite in-flight exposure")
    (same (state c 'accepted) 1 "one completed eager insertion")
    (same (state c 'fallback_reason) 'public-exposure "first exposure reason persists")
    (same (state c 'in_flight) #f "exposure call unwinds its in-flight marker")
    (send c test:arm-set-add! void)
    (same (send c test:add c 0 1 c 4 5) #t "later stock update after in-flight exposure")
    (same (set-count (hash-ref escaped (list c 0 1))) 2 "escaped hash stays live")))

;; Reset inside the third hash-set! argument must preserve stock's captured old
;; target table. No old insertion may write new-generation cache state/counters.
(stage! 'in-flight-reset)
(when enabled?
  (define s (new (g:make-test-class object%)))
  (define c (new (f:make-test-class object%)))
  (define old-s (send s test:peek))
  (define old-c (send c test:peek))
  (send s test:arm-set-add! (lambda () (send s test:arm-set-add! void) (send s syncheck:init-arrows)))
  (send c test:arm-set-add! (lambda () (send c test:arm-set-add! void) (send c syncheck:init-arrows)))
  (same (send s test:add c 0 1 c 2 3) #t "stock reset inside set-add result")
  (same (send c test:add c 0 1 c 2 3) #t "eager reset inside set-add result")
  (same old-c old-s "original hash-set! argument order preserves old target")
  (same (hash-count old-c) 1 "completed old insertion reaches old table")
  (compare-current s c "new generation remains empty after old write")
  (same (state c 'generation) 1 "reset increments generation")
  (same (state c 'active) #t "old call does not disable fresh generation")
  (same (state c 'indexed_edges) 0 "old call does not seed fresh index")
  (same (state c 'cached_starts) 0 "old call does not seed fresh priors")
  (same (state c 'accepted) 0 "old call does not count as new generation accept")
  (same (state c 'eager_writes) 0 "old call does not count as new generation write")
  (own s c 0 1 4 5)
  (compare-current s c "fresh insertion after in-flight reset")
  (compare s c))

;; Actual captured stock/candidate continuations inside the third hash-set!
;; argument resume after an intervening write, public exposure, or reset.
;; Resumption repeats the original public write (including its stock overwrite
;; behavior) but must never restore a stale private index or cached prior set.
(when enabled?
  (for ([transition (in-list '(write exposure reset))])
    (stage! (format "resumed-continuation transition=~a" transition))
    (define s (new (g:make-test-class object%)))
    (define c (new (f:make-test-class object%)))
    (define tag-s (make-continuation-prompt-tag 'stock-insertion))
    (define tag-c (make-continuation-prompt-tag 'eager-insertion))
    (define saved-s #f)
    (define saved-c #f)
    (send s test:arm-set-add!
          (lambda ()
            (send s test:arm-set-add! void)
            (call-with-current-continuation (lambda (k) (set! saved-s k) (void)) tag-s)))
    (send c test:arm-set-add!
          (lambda ()
            (send c test:arm-set-add! void)
            (call-with-current-continuation (lambda (k) (set! saved-c k) (void)) tag-c)))
    (same (call-with-continuation-prompt (lambda () (send s test:add c 0 1 c 2 3)) tag-s)
          #t "stock continuation capture insertion")
    (same (call-with-continuation-prompt (lambda () (send c test:add c 0 1 c 2 3)) tag-c)
          #t "candidate continuation capture insertion")
    (define old-s (send s test:peek))
    (define old-c (send c test:peek))
    (case transition
      [(exposure) (compare s c "exposure before resumed insertion")]
      [(reset) (send s syncheck:init-arrows) (send c syncheck:init-arrows)])
    (own s c 0 1 4 5)
    (compare-current s c "intervening write before continuation resume")
    (same (call-with-continuation-prompt (lambda () (saved-s (void))) tag-s)
          #t "original resumed stock write returns")
    (same (call-with-continuation-prompt (lambda () (saved-c (void))) tag-c)
          #t "original resumed candidate write returns")
    (compare-current s c "resumed public write exactly matches stock")
    (same old-c old-s "old target identity/content after resumed continuation")
    (same (state c 'in_flight) #f "resumed continuation leaves no in-flight marker")
    (if (eq? transition 'reset)
        (begin
          (same (state c 'active) #t "old resumed continuation leaves new cache active")
          (same (state c 'indexed_edges) 1 "new generation index remains intact")
          (same (state c 'accepted) 1 "old resumed continuation cannot increment new accepts")
          (same (state c 'eager_writes) 1 "old resumed continuation cannot increment new writes"))
        (begin
          (same (state c 'active) #f "resuming old priors permanently discards old caches")
          (same (state c 'indexed_edges) 0 "resumption does not revive stale index")
          (same (state c 'cached_starts) 0 "resumption does not revive stale priors")))
    (own s c 0 1 6 7)
    (same (set-count (hash-ref (send c test:peek) (list c 0 1))) 2
          "next insertion reads authoritative table after resumption")
    (compare s c)))

(printf "BINDINGS_EAGER_DIFFERENTIAL passed mode=~a checks=~a\n" expected checks)
(flush-output)
