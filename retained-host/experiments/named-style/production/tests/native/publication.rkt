#lang racket/base
;; TEST-ONLY hook inserted into the complete candidate source immediately before
;; its single snapshot publication. The shipped overlay contains no hook.
(require racket/class racket/cmdline json)
(define module-path (command-line #:args (source) (string->path source)))
(unless (equal? (version) "9.3") (error 'version "expected native Racket 9.3"))
(define list% (dynamic-require module-path 'style-list%))
(define state (dynamic-require module-path 'openracket-named-style-index-state))
(define before-publication (dynamic-require module-path 'openracket-test-before-publication))
(unless (dynamic-require module-path 'openracket-named-style-index-enabled?)
  (error 'activation "publication tests require exact flag 1"))
(define checks 0)
(define (same a b why)
  (set! checks (add1 checks))
  (unless (equal? a b) (error 'publication "~a: ~s != ~s" why a b)))
(define (yes a why) (same (and a #t) #t why))
(define (identical a b why) (yes (eq? a b) why))

;; Synchronous reentry publishes a new-generation index while the interrupted
;; old-generation lookup still owns its captured snapshot and complete index.
(let ()
  (define sl (new list%))
  (define inserted #f)
  (define entered? #f)
  (define observed
    (parameterize ([before-publication
                    (lambda (snapshot index)
                      (yes (immutable? index) "build map is immutable before publication")
                      (yes (list? snapshot) "snapshot is an immutable Racket list")
                      (unless entered?
                        (set! entered? #t)
                        (set! inserted (send sl new-named-style "newer" (send sl basic-style)))
                        (identical (send sl find-named-style "newer") inserted "reentrant newer build")))])
      (send sl find-named-style "newer")))
  (same observed #f "outer lookup answers from its old captured list")
  (same (hash-ref (state sl) 'cache-valid) #f "old completed map cannot claim the current snapshot")
  (identical (send sl find-named-style "newer") inserted "next lookup rebuilds after stale publication")
  (same (hash-ref (state sl) 'cache-valid) #t "new cache valid after rebuild"))

;; Escaping/raising during a build cannot publish partial cache state. This hook
;; executes after construction, so visits are counted but publication is not.
(for ([kind '(raise escape)])
  (define sl (new list%))
  (define result
    (with-handlers ([exn:fail? (lambda (e) 'raised)])
      (let/ec exit
        (parameterize ([before-publication
                        (lambda (snapshot index)
                          (if (eq? kind 'raise)
                              (error 'build "intentional pre-publication failure")
                              (exit 'escaped)))])
          (send sl find-named-style "Basic")))))
  (same result (if (eq? kind 'raise) 'raised 'escaped) "intended interruption occurred")
  (define interrupted (state sl))
  (same (hash-ref interrupted 'cache-valid) #f "no valid partial cache after interruption")
  (same (hash-ref interrupted 'named-entries) 0 "no partial table is retained")
  (same (hash-ref interrupted 'rebuilds) 0 "interrupted build has no completed publication")
  (same (hash-ref interrupted 'members-traversed) 1 "aborted visits remain visible")
  (identical (send sl find-named-style "Basic") (send sl basic-style) "retry succeeds normally"))

;; A resumed continuation carries the old immutable snapshot, not a new label.
(let ()
  (define sl (new list%))
  (define saved #f)
  (define first? #t)
  (define tag (make-continuation-prompt-tag 'publication))
  (define (run thunk)
    (call-with-continuation-prompt thunk tag (lambda (v) v)))
  (define initial
    (run
     (lambda ()
       (parameterize ([before-publication
                       (lambda (snapshot index)
                         (when first?
                           (set! first? #f)
                           (call-with-composable-continuation
                            (lambda (k)
                              (set! saved k)
                              (abort-current-continuation tag 'suspended)) tag)))])
         (send sl find-named-style "resumed")))))
  (same initial 'suspended "old build suspended before publication")
  (define inserted (send sl new-named-style "resumed" (send sl basic-style)))
  (identical (send sl find-named-style "resumed") inserted "new build completes before old continuation resumes")
  (same (run (lambda () (saved (void)))) #f "resumed lookup still uses its original snapshot")
  (same (hash-ref (state sl) 'cache-valid) #f "resumed old publication remains labeled old")
  (identical (send sl find-named-style "resumed") inserted "next call rejects resumed stale cache"))

;; Deterministic two-thread publication order, with owned workers and bounded
;; synchronization. The hook introduces coordination only in this test module.
(let ()
  (define owner (make-custodian))
  (define sl (new list%))
  (define built (make-semaphore 0))
  (define resume (make-semaphore 0))
  (define returned (make-channel))
  (define worker #f)
  (dynamic-wind
    void
    (lambda ()
      (set! worker
            (parameterize ([current-custodian owner])
              (thread
               (lambda ()
                 (with-handlers ([exn? (lambda (e) (channel-put returned (list 'raised (exn-message e))))])
                   (define result
                     (parameterize ([before-publication
                                     (lambda (snapshot index)
                                       (semaphore-post built)
                                       (semaphore-wait resume))])
                       (send sl find-named-style "concurrent")))
                   (channel-put returned (list 'returned result)))))))
      (yes (sync/timeout 5 built) "worker reached full pre-publication build")
      (define inserted (send sl new-named-style "concurrent" (send sl basic-style)))
      (identical (send sl find-named-style "concurrent") inserted "main thread publishes new snapshot first")
      (semaphore-post resume)
      (same (sync/timeout 5 returned) '(returned #f) "worker publishes and answers its old snapshot")
      (same (hash-ref (state sl) 'cache-valid) #f "concurrent stale publication never labeled current")
      (identical (send sl find-named-style "concurrent") inserted "next lookup revalidates by identity"))
    (lambda ()
      (custodian-shutdown-all owner)
      (when worker (yes (sync/timeout 5 (thread-dead-evt worker)) "owned worker reaped")))))

(write-json (hasheq 'schema "openracket-named-style-publication-v1" 'passed #t 'checks checks))
(newline)
