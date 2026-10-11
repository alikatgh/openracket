#lang racket/base

;; Independent, headless tests for the *actual* stock and generated definitions.
;; No reimplementation of the lookup loop or get-index-entry-info is tested.
;; Run from any directory:
;;   racket tests/independent-reply-test.rkt
;; Optional positional arguments: STOCK-XREF.RKT CANDIDATE-XREF.RKT
;; No Racket executable is available in the authoring environment. Native run
;; 38104720998 exercised the initial version; the deterministic break-checkpoint
;; repair below still requires a native rerun.

(require rackunit
         rackunit/text-ui
         racket/async-channel
         racket/file
         racket/list
         racket/match
         racket/path
         racket/port
         racket/runtime-path)

(define-runtime-path default-stock "../vendor/xref.rkt")
(define-runtime-path default-candidate "../overlay/xref.rkt")
(define arguments (current-command-line-arguments))
(unless (or (= (vector-length arguments) 0) (= (vector-length arguments) 2))
  (error 'independent-reply-test "expected zero arguments or STOCK CANDIDATE"))
(define stock-path
  (if (zero? (vector-length arguments)) default-stock (vector-ref arguments 0)))
(define candidate-path
  (if (zero? (vector-length arguments)) default-candidate (vector-ref arguments 1)))
(define flag-name #"OPENRACKET_XREF_REPLY_CELL")
(define timeout 5.0)
(define quiet-window 0.05)

(struct variant (name path flag reply-cell?) #:transparent)
(define variants
  (list (variant 'stock stock-path #f #f)
        (variant 'off candidate-path #f #f)
        (variant 'on candidate-path #"1" #t)))
(struct gate (entered release) #:transparent)
(define (make-gate) (gate (make-semaphore 0) (make-semaphore 0)))
;; Strongly retaining a complete request here would invalidate collection tests.
(struct accepted (key directory response-weak ready-weak) #:transparent)
(struct fixture (variant custodian namespace get flush service requests lookups
                         completions workers descriptions error-output)
  #:transparent)
(struct caller (thread custodian done dispatched) #:transparent)

(define (await event [message "event did not become ready"])
  (define result (sync/timeout timeout event))
  (unless result (error 'independent-reply-test "~a" message))
  result)

(define (eventually predicate [message "condition did not become true"])
  (define deadline (+ (current-inexact-milliseconds) (* 1000 timeout)))
  (let loop ()
    (unless (predicate)
      (when (>= (current-inexact-milliseconds) deadline)
        (error 'independent-reply-test "~a" message))
      (sleep 0.005)
      (loop))))

(define (module-forms path)
  (define datum
    (call-with-input-file path
      (lambda (input)
        (parameterize ([read-accept-reader #t])
          (read input)))))
  (match datum
    [`(module ,_ racket/base (#%module-begin ,forms ...)) forms]
    [_ (error 'independent-reply-test "unexpected module structure in ~a" path)]))

(define (install! ns name value)
  ;; Establish fresh top-level bindings; do not mutate racket/base exports.
  (namespace-set-variable-value! name value #t ns))

(define (make-fixture v #:gates [gates (hash)] #:xref? [xref? #t])
  (define cust (make-custodian))
  (define ns (make-base-namespace))
  (define env (environment-variables-copy (current-environment-variables)))
  (environment-variables-set! env flag-name (variant-flag v))
  (define requests (box '()))
  (define lookups (box '()))
  (define completions (box '()))
  (define workers (box '()))
  (define descriptions (make-hash))
  (define error-output (open-output-string))
  ;; Only the production service invokes this channel-get binding. Record
  ;; acceptance before lookup, without retaining the response transport.
  (define (tracked-channel-get channel)
    (define request (channel-get channel))
    (match request
      [(list key directory response ready)
       (set-box! requests
                 (cons (accepted key directory (make-weak-box response)
                                 (make-weak-box ready))
                       (unbox requests)))]
      [#f (set-box! requests (cons #f (unbox requests)))])
    request)
  (define (tracked-thread thunk)
    ;; Do not let a short response helper finish before it has been recorded.
    ;; This gate belongs only to instrumentation, not to the source under test.
    (define registered (make-semaphore 0))
    (define worker (thread (lambda () (semaphore-wait registered) (thunk))))
    (set-box! workers (cons worker (unbox workers)))
    (semaphore-post registered)
    worker)
  (define (definition-tag _xref key _phase)
    (set-box! lookups (cons (list key (current-directory)) (unbox lookups)))
    (define held (hash-ref gates key #f))
    (when held
      (semaphore-post (gate-entered held))
      (semaphore-wait (gate-release held)))
    (when (eq? key 'explode)
      (error 'injected-lookup "expected lookup exception"))
    (set-box! completions (cons key (unbox completions)))
    (if (eq? key 'multiple-values)
        (values key key)
        (and (not (eq? key 'missing-tag)) key)))
  (define (tag-path _xref key)
    (values (and (not (eq? key 'missing-path))
                 (build-path (current-directory) "injected-doc.html"))
            (format "anchor:~s" key)))
  (define (index-entry _xref key)
    (and (not (eq? key 'missing-entry))
         (hash-ref! descriptions key (lambda () (box (list 'description key))))))
  (with-handlers ([exn? (lambda (exception)
                         (custodian-shutdown-all cust)
                         (raise exception))])
    (parameterize ([current-namespace ns]
                   [current-custodian cust]
                   [current-environment-variables env]
                   [current-error-port error-output])
      (namespace-require 'racket/match)
      (install! ns 'load-collections-xref (lambda () xref?))
      (install! ns 'xref-binding->definition-tag definition-tag)
      (install! ns 'xref-tag->path+anchor tag-path)
      (install! ns 'xref-tag->index-entry index-entry)
      (install! ns 'entry-desc values)
      (install! ns 'thread tracked-thread)
      (install! ns 'channel-get tracked-channel-get)
      (for ([form (in-list (module-forms (variant-path v)))])
        (match form
          ;; The only substituted dependencies are the documented lookup seam.
          [`(require setup/xref scribble/xref racket/match) (void)]
          [`(require ,_ ...) (error 'independent-reply-test
                                    "unreviewed require in source: ~s" form)]
          [`(provide ,_ ...) (void)]
          [_ (eval form)])))
    (define (get name)
      (parameterize ([current-namespace ns]) (eval name)))
    (unless (eq? (variant-name v) 'stock)
      (check-equal? (get 'openracket-xref-reply-cell-enabled?)
                    (variant-reply-cell? v)))
    (fixture v cust ns (get 'get-index-entry-info) (get 'flush-index-entry-cache)
             (get 'thd) requests lookups completions workers descriptions
             error-output)))

(define (call-with-fixture v proc #:gates [gates (hash)] #:xref? [xref? #t])
  (define f (make-fixture v #:gates gates #:xref? xref?))
  (dynamic-wind void
                (lambda () (proc f))
                (lambda () (custodian-shutdown-all (fixture-custodian f)))))

(define (start-caller f key #:directory [directory (current-directory)]
                      #:breaks? [breaks? #t] #:returned [returned #f]
                      #:break-checkpoint? [break-checkpoint? #f])
  (define cust (make-custodian (fixture-custodian f)))
  (define done (make-async-channel))
  (define dispatched (make-semaphore 0))
  (define worker
    (parameterize ([current-custodian cust])
      (thread
       (lambda ()
         (with-handlers ([exn:break? (lambda (_) (async-channel-put done '(break)))]
                         [exn? (lambda (exn)
                                 (async-channel-put done (list 'exception exn)))])
           (semaphore-post dispatched)
           (define result
             (parameterize ([current-directory directory])
               (parameterize-break breaks?
                 (define result ((fixture-get f) key))
                 (when returned (async-channel-put returned (list 'value result)))
                 result)))
           ;; Leaving parameterize-break restores the previous state; it does
           ;; not establish an explicit break-delivery synchronization point.
           ;; A requested checkpoint must receive the pending break, or the
           ;; caller stays blocked and the fixture's bounded await fails.
           (when break-checkpoint? (sync/enable-break never-evt))
           (async-channel-put done (list 'value result)))))))
  (caller worker cust done dispatched))

(define (result-of c)
  (match (await (caller-done c) "caller failed to finish")
    [(list 'value result) result]
    [(list 'exception exn) (raise exn)]
    [other (error 'independent-reply-test "unexpected caller outcome: ~s" other)]))

(define (request f key #:directory [directory (current-directory)])
  (result-of (start-caller f key #:directory directory)))

(define (lookup-keys f)
  (map car (reverse (unbox (fixture-lookups f)))))
(define (request-keys f)
  (for/list ([request (in-list (reverse (unbox (fixture-requests f))))]
             #:when request)
    (accepted-key request)))
(define (lookup-count f key)
  (count (lambda (actual) (equal? actual key)) (lookup-keys f)))
(define (response-workers f)
  (filter (lambda (worker) (not (eq? worker (fixture-service f))))
          (unbox (fixture-workers f))))
(define (live-response-workers f)
  (filter (lambda (worker) (not (thread-dead? worker))) (response-workers f)))
(define (no-response-leak! f)
  (eventually (lambda () (null? (live-response-workers f)))
              "response helper thread remained alive"))
(define (check-reply-count! f count)
  (check-equal? (length (response-workers f))
                (if (variant-reply-cell? (fixture-variant f)) 0 count)))
(define (last-accepted f key)
  (findf (lambda (request) (and request (equal? key (accepted-key request))))
         (unbox (fixture-requests f))))

(define differential-snapshots (make-hash))

(define (tests-for v)
  (test-suite
   (symbol->string (variant-name v))

   (test-case "misses, cached false, result identity, and equal? cache keys"
     (call-with-fixture
      v
      (lambda (f)
        (for ([key '(missing-tag missing-path missing-entry)])
          (check-false (request f key))
          (check-false (request f key))
          (check-equal? (lookup-count f key) 1))
        (define key1 (list 'binding 'same))
        (define key2 (list 'binding 'same))
        (check-false (eq? key1 key2))
        (define first (request f key1))
        (define second (request f key2))
        (check-eq? first second)
        (check-eq? (car first) (hash-ref (fixture-descriptions f) key1))
        (check-equal? (lookup-count f key1) 1)
        (check-equal? (caddr first) key1)
        (check-equal? (cadddr first) "anchor:(binding same)")
        (no-response-leak! f)
        (check-reply-count! f 8)
        (hash-set! differential-snapshots (variant-name v)
                   (list (lookup-keys f) (map unbox (list (car first)))
                         (caddr first) (cadddr first))))))

   (test-case "absent collection xref returns false without invoking lookup"
     (call-with-fixture
      v #:xref? #f
      (lambda (f)
        (check-false (request f 'ordinary))
        (check-false (request f 'ordinary))
        (check-equal? (lookup-keys f) '())
        (no-response-leak! f)
        (check-reply-count! f 2))))

   (test-case "false result becomes ready only after its lookup has finished"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'missing-tag held)
      (lambda (f)
        (define c (start-caller f 'missing-tag))
        (await (gate-entered held))
        (check-false (sync/timeout quiet-window (caller-done c)))
        (semaphore-post (gate-release held))
        (check-false (result-of c))
        (check-false (request f 'missing-tag))
        (check-equal? (lookup-count f 'missing-tag) 1)
        (no-response-leak! f)
        (check-reply-count! f 2))))

   (test-case "caller current-directory applies on a miss; cache key is unchanged"
     (define root (make-temporary-file "xref-reply~a" 'directory))
     (dynamic-wind
       void
       (lambda ()
         (define directory-a (build-path root "a"))
         (define directory-b (build-path root "b"))
         (make-directory directory-a)
         (make-directory directory-b)
         (call-with-fixture
          v
          (lambda (f)
            (define first (request f 'shared #:directory directory-a))
            (define hit (request f 'shared #:directory directory-b))
            (define second (request f 'other #:directory directory-b))
            (check-eq? first hit)
            (check-equal? (cadr first) (build-path directory-a "injected-doc.html"))
            (check-equal? (cadr second) (build-path directory-b "injected-doc.html"))
            (check-equal? (lookup-keys f) '(shared other))
            (no-response-leak! f))))
       (lambda () (delete-directory/files root))))

   (test-case "stock flush only constructs an unsynchronized event"
     (call-with-fixture
      v
      (lambda (f)
        (define before (request f 'cached))
        (check-true (void? ((fixture-flush f))))
        (no-response-leak! f)
        (check-eq? before (request f 'cached))
        (check-equal? (lookup-count f 'cached) 1)
        (check-false (member #f (unbox (fixture-requests f))))
        (no-response-leak! f)
        ;; One extra thread is the stock flush thread, even in the on variant.
        (check-equal? (length (response-workers f))
                      (if (variant-reply-cell? v) 1 3)))))

   (test-case "concurrent callers preserve serial acceptance and shared identity"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'first held)
      (lambda (f)
        (define first (start-caller f 'first))
        (await (gate-entered held))
        (define keys (append (build-list 24 (lambda (i) (string->symbol (format "key~a" i))))
                             (make-list 12 'shared)))
        (define callers (map (lambda (key) (start-caller f key)) keys))
        (for ([c (in-list callers)]) (await (caller-dispatched c)))
        (semaphore-post (gate-release held))
        (check-equal? (caddr (result-of first)) 'first)
        (define results (map result-of callers))
        (for ([key (in-list keys)] [result (in-list results)])
          (check-equal? (caddr result) key))
        (define shared-results (drop results 24))
        (for ([result (in-list (cdr shared-results))])
          (check-eq? (car shared-results) result))
        (check-equal? (lookup-count f 'shared) 1)
        ;; First occurrence in accepted order must be exactly lookup order.
        (check-equal? (lookup-keys f) (remove-duplicates (request-keys f)))
        (check-equal? (reverse (unbox (fixture-completions f))) (lookup-keys f))
        (no-response-leak! f)
        (check-reply-count! f 37))))

   (test-case "kill and caller-custodian shutdown during accepted lookup"
     (for ([cancel '(kill custodian)])
       (define held (make-gate))
       (call-with-fixture
        v #:gates (hash 'abandoned held)
        (lambda (f)
          (define c (start-caller f 'abandoned))
          (await (gate-entered held))
          (case cancel
            [(kill) (kill-thread (caller-thread c))]
            [(custodian) (custodian-shutdown-all (caller-custodian c))])
          (await (thread-dead-evt (caller-thread c)))
          (semaphore-post (gate-release held))
          (check-equal? (caddr (request f 'after-cancellation)) 'after-cancellation)
          ;; An already accepted lookup completes and populates the stock cache.
          (define cached (request f 'abandoned))
          (check-equal? (caddr cached) 'abandoned)
          (check-equal? (lookup-count f 'abandoned) 1)
          (check-false (thread-dead? (fixture-service f)))
          (no-response-leak! f)
          (check-reply-count! f 3)))))

   (test-case "kill and custodian shutdown after response is ready but unconsumed"
     (for ([cancel '(kill custodian)])
       (define held (make-gate))
       (call-with-fixture
        v #:gates (hash 'unconsumed held)
        (lambda (f)
          (define c (start-caller f 'unconsumed))
          (await (gate-entered held))
          (thread-suspend (caller-thread c))
          (semaphore-post (gate-release held))
          ;; Finishing a subsequent lookup proves the serial service already
          ;; published the first result while its caller was still suspended.
          (check-equal? (caddr (request f 'sentinel)) 'sentinel)
          (check-false (sync/timeout 0 (caller-done c)))
          ;; A suspended caller's channel event might already be selected.
          ;; Do not require the stock helper to stay alive until resume/kill.
          (check-reply-count! f 2)
          (case cancel
            [(kill) (kill-thread (caller-thread c))]
            [(custodian) (custodian-shutdown-all (caller-custodian c))])
          (await (thread-dead-evt (caller-thread c)))
          (check-equal? (caddr (request f 'still-usable)) 'still-usable)
          (no-response-leak! f)
          (check-reply-count! f 3)))))

   (test-case "suspend then resume receives the original reply without a lost wakeup"
     (for ([key '(retained-reply missing-tag)])
       (define held (make-gate))
       (call-with-fixture
        v #:gates (hash key held)
        (lambda (f)
          (define c (start-caller f key))
          (await (gate-entered held))
          (thread-suspend (caller-thread c))
          (semaphore-post (gate-release held))
          (request f 'sentinel)
          (check-false (sync/timeout 0 (caller-done c)))
          (thread-resume (caller-thread c))
          (define result (result-of c))
          (if (eq? key 'missing-tag)
              (check-false result)
              (check-equal? (caddr result) key))
          (check-eq? result (request f key))
          (check-equal? (lookup-count f key) 1)
          (check-false (thread-dead? (fixture-service f)))
          (no-response-leak! f)
          (check-reply-count! f 3)))))

   (test-case "cancel before acceptance does not add lookup or cache work"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'first held)
      (lambda (f)
        (define first (start-caller f 'first))
        (await (gate-entered held))
        (define second (start-caller f 'not-accepted))
        (await (caller-dispatched second))
        (kill-thread (caller-thread second))
        (await (thread-dead-evt (caller-thread second)))
        (semaphore-post (gate-release held))
        (result-of first)
        (request f 'sentinel)
        (check-false (member 'not-accepted (request-keys f)))
        (check-false (member 'not-accepted (lookup-keys f)))
        (no-response-leak! f))))

   (test-case "enabled breaks cancel a caller blocked during lookup"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'break-during-lookup held)
      (lambda (f)
        (define c (start-caller f 'break-during-lookup))
        (await (gate-entered held))
        (break-thread (caller-thread c))
        (check-equal? (await (caller-done c)) '(break))
        (semaphore-post (gate-release held))
        (request f 'after-break)
        (check-equal? (lookup-count f 'break-during-lookup) 1)
        (no-response-leak! f))))

   (test-case "enabled breaks after ready response preserve service usability"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'ready-before-break held)
      (lambda (f)
        (define c (start-caller f 'ready-before-break))
        (await (gate-entered held))
        (thread-suspend (caller-thread c))
        (semaphore-post (gate-release held))
        (request f 'sentinel)
        (break-thread (caller-thread c))
        (thread-resume (caller-thread c))
        (check-equal? (await (caller-done c)) '(break))
        (request f 'after-ready-break)
        (no-response-leak! f))))

   (test-case "disabled lookup returns before pending break at explicit enabled wait"
     (define held (make-gate))
     (define returned (make-async-channel))
     (call-with-fixture
      v #:gates (hash 'deferred-break held)
      (lambda (f)
        (define c (start-caller f 'deferred-break
                                #:breaks? #f #:returned returned
                                #:break-checkpoint? #t))
        (await (gate-entered held))
        (break-thread (caller-thread c))
        (check-false (sync/timeout quiet-window (caller-done c)))
        (semaphore-post (gate-release held))
        (define original-result (cadr (await returned)))
        (check-equal? (caddr original-result) 'deferred-break)
        (check-equal? (await (caller-done c)) '(break))
        (check-eq? original-result (request f 'deferred-break))
        (check-equal? (lookup-count f 'deferred-break) 1)
        (request f 'after-deferred-break)
        (no-response-leak! f))))

   (test-case "lookup exception kills service; in-flight call stays blocked"
     (call-with-fixture
      v
      (lambda (f)
        (define c (start-caller f 'explode))
        (await (thread-dead-evt (fixture-service f)))
        (check-false (sync/timeout quiet-window (caller-done c)))
        (check-false (thread-dead? (caller-thread c)))
        (check-false (request f 'after-death))
        (check-true (void? ((fixture-flush f))))
        (check-equal? (lookup-keys f) '(explode))
        (check-true (regexp-match? #rx"expected lookup exception"
                                   (get-output-string (fixture-error-output f))))
        (kill-thread (caller-thread c))
        (await (thread-dead-evt (caller-thread c)))
        (no-response-leak! f))))

   (test-case "externally killed service keeps the same bounded dead-service outcome"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'service-dies held)
      (lambda (f)
        (define c (start-caller f 'service-dies))
        (await (gate-entered held))
        (kill-thread (fixture-service f))
        (await (thread-dead-evt (fixture-service f)))
        (check-false (sync/timeout quiet-window (caller-done c)))
        (check-false (request f 'after-service-kill))
        (kill-thread (caller-thread c))
        (await (thread-dead-evt (caller-thread c)))
        (no-response-leak! f))))

   (test-case "multiple-value backend result retains the stock arity-error outcome"
     (call-with-fixture
      v
      (lambda (f)
        (define c (start-caller f 'multiple-values))
        (await (thread-dead-evt (fixture-service f)))
        (check-false (sync/timeout quiet-window (caller-done c)))
        (check-false (thread-dead? (caller-thread c)))
        (check-false (request f 'after-arity-error))
        (check-equal? (lookup-keys f) '(multiple-values))
        (check-true (regexp-match? #rx"arity mismatch"
                                   (get-output-string (fixture-error-output f))))
        (kill-thread (caller-thread c))
        (await (thread-dead-evt (caller-thread c)))
        (no-response-leak! f))))

   (test-case "abandoned transport is collectible after service advances"
     (define held (make-gate))
     (call-with-fixture
      v #:gates (hash 'collectible held)
      (lambda (f)
        (define weak-transports
          (let ()
            (define c (start-caller f 'collectible))
            (await (gate-entered held))
            (define record (last-accepted f 'collectible))
            (kill-thread (caller-thread c))
            (await (thread-dead-evt (caller-thread c)))
            (semaphore-post (gate-release held))
            (request f 'advance-one)
            (request f 'advance-two)
            (no-response-leak! f)
            (list (accepted-response-weak record) (accepted-ready-weak record))))
        (eventually
         (lambda ()
           (collect-garbage)
           (andmap (lambda (weak) (not (weak-box-value weak))) weak-transports))
         "canceled request retained its response transport")
        (check-equal? (lookup-count f 'collectible) 1)
        (check-equal? (caddr (request f 'collectible)) 'collectible))))))

(define suite
  (test-suite
   "independent production xref reply transport"
   (test-case "stock snapshot has the reviewed source forms"
     (check-not-false
      (member '(define (flush-index-entry-cache)
                 (unless (thread-dead? thd)
                   (thread (lambda () (channel-put-evt req-chan #f)))
                   (void)))
              ;; The upstream source uses the Unicode spelling of lambda.
              (let normalize ([value (module-forms stock-path)])
                (cond [(eq? value 'λ) 'lambda]
                      [(pair? value) (cons (normalize (car value))
                                          (normalize (cdr value)))]
                      [else value])))))
   (tests-for (list-ref variants 0))
   (tests-for (list-ref variants 1))
   (tests-for (list-ref variants 2))
   (test-case "stable observations match stock in both candidate modes"
     (define stock (hash-ref differential-snapshots 'stock))
     (check-equal? (hash-ref differential-snapshots 'off) stock)
     (check-equal? (hash-ref differential-snapshots 'on) stock))
   (test-case "only the exact value 1 opts in"
     (for ([flag (list #f #"" #"0" #"true" #"1")])
       (define on? (equal? flag #"1"))
       (call-with-fixture
        (variant 'flag-check candidate-path flag on?)
        (lambda (f)
          (request f 'probe)
          (no-response-leak! f)
          (check-reply-count! f 1)))))))

(module+ main
  (define failures (run-tests suite))
  (unless (zero? failures) (exit 1)))
(module+ test
  (define failures (run-tests suite))
  (unless (zero? failures)
    (error 'independent-reply-test "~a test(s) failed" failures)))
