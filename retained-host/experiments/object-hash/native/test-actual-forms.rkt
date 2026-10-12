#lang racket/base
;; NATIVE UNRUN. A separate fresh process is required for every scenario.
;; Actual installed core forms + mechanical original reference; synthetic objects
;; here are semantics fixtures, never evidence that genuine editors match.
(require racket/class racket/runtime-path rackunit json)
(define-runtime-path reference-path "original-reference.rktd")
(define-runtime-path pins-path "../SOURCE-PINS.json")
(define-runtime-path observer-fault-path "observer-fault-form.rktd")
(define core 'racket/private/class-internal)
(dynamic-require core #f)
(define ns (module->namespace core))
(define (private name) (parameterize ([current-namespace ns]) (eval name)))
(define (load-form path) (parameterize ([current-namespace ns]) (eval (call-with-input-file path read))))
(define actual (private 'object-hash-code))
(define reference (load-form reference-path))
(define enabled? (dynamic-require core 'openracket-object-hash-probe-enabled?))
(define arm! (dynamic-require core 'openracket-object-hash-probe-arm!))
(define stop! (dynamic-require core 'openracket-object-hash-probe-stop!))
(define state (dynamic-require core 'openracket-object-hash-probe-state))
(define scenario (string->symbol (vector-ref (current-command-line-arguments) 0)))
(define owner (make-inspector))
(define (object-with inspector)
  (new (class object% (inspect inspector) (field [x 19]) (super-new))))
(define definitions (object-with owner))
(define interactions (object-with owner))
(define custom-calls 0)
(define custom%
  (class* object% (equal<%>)
    (define/public (equal-to? other recur) #t)
    (define/public (equal-hash-code-of recur) (set! custom-calls (add1 custom-calls)) 17)
    (define/public (equal-secondary-hash-code-of recur) (set! custom-calls (add1 custom-calls)) 29)
    (super-new)))
(define (compare! obj inspector)
  (for ([hash-proc (in-list (list equal-hash-code equal-secondary-hash-code))])
    (define left '()) (define right '())
    (define a (parameterize ([current-inspector inspector])
                (reference obj (lambda (v) (set! left (cons v left)) (hash-proc v)))))
    (define b (parameterize ([current-inspector inspector])
                (actual obj (lambda (v) (set! right (cons v right)) (hash-proc v)))))
    (check-equal? b a)
    (check-equal? right left)))
(define (get-count key) (hash-ref (state) key))
;; Official v9.3 namespaces.scrbl distinguishes top-level variable setters from
;; mutation of existing module bindings. Compile this setter in the core's body
;; namespace, so it cannot create an unrelated top-level shadow.
(define fault-counter-reference
  (private '(#%variable-reference probe-definitions-not-skipped-vectors)))
(define core-reference
  (private '(#%variable-reference openracket-object-hash-probe-state)))
(define fault-counter-setter
  (private '(lambda (value) (set! probe-definitions-not-skipped-vectors value))))
(define (set-fault-counter! value)
  (fault-counter-setter value)
  (check-eq? (private 'probe-definitions-not-skipped-vectors) value)
  (check-eq? (hash-ref (state) 'definitions_not_skipped_vectors) value))

(parameterize ([current-check-handler raise])
  (check-equal? (version) "9.3")
  (check-not-false (variable-reference->resolved-module-path fault-counter-reference))
  (check-equal? (variable-reference->resolved-module-path fault-counter-reference)
                (variable-reference->resolved-module-path core-reference))
  (check-false (variable-reference-constant? fault-counter-reference))
  (check-equal? (dynamic-require core 'openracket-object-hash-probe-build-id)
                (hash-ref (call-with-input-file pins-path read-json) 'build_id))
  (cond
    [(eq? scenario 'off)
     (check-false enabled?)
     (check-exn exn:fail? (lambda () (arm! definitions interactions (current-thread))))
     (compare! definitions owner)
     (check-equal? (get-count 'attempts) 0)]
    [else
     (check-true enabled?)
     ;; Build targets before arm, so class setup cannot consume the window.
     (case scenario
       [(transparent recursive-results observer-fault observer-break)
        (set! definitions (object-with #f))]
       [(custom-dispatch) (set! definitions (new custom%))]
       [(mixed-inheritance)
        (define base% (class object% (inspect owner) (field [x 3]) (super-new)))
        (define leaf% (class base% (inspect #f) (field [y 5]) (super-new)))
        (set! definitions (new leaf%))]
       [(impersonator conversion-fault)
        (define-values (type skipped?) (struct-info definitions))
        (check-false skipped?)
        (define-values (name init auto accessor mutator immutable super skipped-parent?)
          (struct-type-info type))
        (check-true (positive? (+ init auto)))
        (define access (make-struct-field-accessor accessor 0))
        (define marker (exn:fail "original wrapped field fault" (current-continuation-marks)))
        (set! definitions
              (chaperone-struct definitions access
                (lambda (self value)
                  (if (eq? scenario 'conversion-fault) (raise marker) value))))]
       [else (void)])
     (arm! definitions interactions (current-thread))
     (check-exn exn:fail? (lambda () (arm! definitions interactions (current-thread))))
     (case scenario
       [(opaque same-inspector)
        (compare! definitions owner)
        (check-true (positive? (get-count 'definitions_skipped_fallbacks)))]
       [(transparent)
        (compare! definitions (make-inspector))
        (check-true (positive? (get-count 'definitions_not_skipped_returns)))]
       [(mixed-inheritance)
        (compare! definitions owner)
        (check-true (positive? (get-count 'definitions_not_skipped_fallbacks)))]
       [(impersonator)
        (check-true (impersonator? definitions))
        (compare! definitions (current-inspector))
        (check-true (positive? (get-count 'definitions_impersonator_matches)))
        (check-equal? (get-count 'definitions_skipped_matches) 0)]
       [(conversion-fault)
        (define e1 #f) (define e2 #f)
        (with-handlers ([(lambda (v) #t) (lambda (v) (set! e1 v))]) (reference definitions values))
        (with-handlers ([(lambda (v) #t) (lambda (v) (set! e2 v))]) (actual definitions values))
        (check-not-false e1) (check-eq? e2 e1)
        (check-equal? (get-count 'definitions_impersonator_matches) 1)
        (check-equal? (get-count 'definitions_impersonator_vectors) 0)]
       [(recursive-results)
        (define marker (gensym 'same-raised-value))
        (for ([f (in-list (list reference actual))])
          (check-equal? (call-with-values (lambda () (f definitions (lambda (v) (values 3 5)))) list) '(3 5))
          (check-equal? (call-with-values (lambda () (f definitions (lambda (v) (values)))) list) '())
          (check-exn (lambda (v) (eq? v marker))
                     (lambda () (f definitions (lambda (v) (raise marker))))))]
       [(observer-fault)
        ;; Scalar mutation is confined to this disposable test process. The actual
        ;; observer catches its arithmetic fault, then the original body succeeds.
        (set-fault-counter! 'fault)
        (check-equal? (actual definitions (lambda (v) 23)) (reference definitions (lambda (v) 23)))
        (check-equal? (get-count 'diagnostic_faults) 1)
        (check-false (hash-ref (state) 'active))
        (set-fault-counter! 0)]
       [(observer-break)
        ;; Exact source-derived observer form has one explicit injected raise
        ;; inside its scalar-update handler. Installed predicate/handler bindings
        ;; must propagate cancellation instead of swallowing it as a fault.
        (define marker (exn:break "observer cancellation" (current-continuation-marks) (let/ec k k)))
        (define make-fault-observer (load-form observer-fault-path))
        (check-false ((private 'probe-diagnostic-failure?) marker))
        (check-exn (lambda (v) (eq? marker v)) (lambda () ((make-fault-observer marker) 0 1)))
        (check-equal? (get-count 'diagnostic_faults) 0)]
       [(caps-attempt)
        (define unmatched (object-with owner))
        (for ([i (in-range 20005)]) (actual unmatched (lambda (v) 0)))
        (check-equal? (get-count 'attempts) 20000)
        (check-equal? (get-count 'matches) 0)
        (check-equal? (hash-ref (state) 'eligibility) "unresolved-no-matching-calls")]
       [(caps-match)
        (for ([i (in-range 140)]) (actual definitions (lambda (v) 0)))
        (check-equal? (get-count 'matches) 128)
        (check-equal? (get-count 'definitions_not_skipped_vectors) 128)]
       [(thread-scope)
        (thread-wait (thread (lambda () (actual definitions (lambda (v) 0)))))
        (check-equal? (get-count 'attempts) 0)]
       [(weak-registry)
        (define d (make-weak-box definitions)) (define i (make-weak-box interactions))
        (set! definitions #f) (set! interactions #f)
        (collect-garbage) (collect-garbage) (collect-garbage)
        (check-false (weak-box-value d)) (check-false (weak-box-value i))]
       [(custom-dispatch)
        (check-equal? (equal-hash-code definitions) 17)
        (check-equal? (equal-secondary-hash-code definitions) 29)
        (check-equal? custom-calls 2)
        (check-equal? (get-count 'attempts) 0)]
       [(public-dispatch)
        (parameterize ([current-inspector owner])
          (check-equal? (equal-hash-code definitions) (eq-hash-code definitions))
          (check-equal? (equal-secondary-hash-code definitions) (eq-hash-code definitions)))
        (check-true (>= (get-count 'definitions_skipped_matches) 2))]
       [else (error 'object-hash-test "Unknown scenario ~a" scenario)])])
  (stop!)
  (display "OPENRACKET_OBJECT_HASH_NATIVE_SEMANTICS ")
  (write-json (hasheq 'scenario (symbol->string scenario) 'status "passed" 'state (state)))
  (newline))
