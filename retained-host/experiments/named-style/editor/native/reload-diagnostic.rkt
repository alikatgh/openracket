#lang racket/base
;; Failure-only evidence for the original load-file call. No alternate reader.
(require json racket/class racket/exn racket/file racket/gui/base
         racket/list "snapshot.rkt"
         (rename-in "failure-observation.rkt"
                    [run-failure-observation-controls! run-forwarding-controls!]))
(provide make-reload-observer call/observe-reload-failure
         run-failure-observation-controls!)

(define byte-limit (* 256 1024))
(define (bounded-message e)
  (define s (if (exn? e) (exn-message e) (format "~s" e)))
  (substring s 0 (min 2048 (string-length s))))
(define (observation thunk)
  (with-handlers ([(lambda (_) #t)
                   (lambda (e) (hasheq 'status "unavailable" 'error (bounded-message e)))])
    (define value (thunk))
    ;; Validate before publishing into the main report; malformed diagnostic
    ;; state must not make bootstrap's otherwise-valid failure JSON unwritable.
    (write-json value (open-output-string))
    (hasheq 'status "observed" 'value value)))
(define (digest bs)
  (apply string-append
         (for/list ([b (in-bytes (sha256-bytes bs))])
           (define s (number->string b 16))
           (if (= (string-length s) 1) (string-append "0" s) s))))
(define (stream-view stream failed?)
  ;; ok? only reads status. For modern WXME, tell also records pos-map state;
  ;; call it only after an original false return/raise, when stock load-file
  ;; will abort without another read. This is a logical item index, not bytes.
  (define okay (send stream ok?))
  (unless (boolean? okay)
    (error 'reload-diagnostic "invalid bounded stream observation"))
  (if failed?
      (let ([position (send stream tell)])
        (unless (and (exact-nonnegative-integer? position) (<= position byte-limit))
          (error 'reload-diagnostic "invalid bounded stream position"))
        (hasheq 'logical_item_position position 'ok okay))
      (hasheq 'ok okay)))
(define (reader-event stream phase arguments result)
  (observation
   (lambda ()
     (hasheq 'phase phase 'argument_count (add1 (length arguments))
             'arguments_after_stream arguments
             'stream
             (observation
              (lambda ()
                (stream-view stream
                             (or (equal? phase "raised")
                                 (and (equal? phase "returned")
                                      (equal? result '(#f)))))))
             'result (if (equal? phase "raised")
                         (hasheq 'error (bounded-message result))
                         result)))))
(define (run-failure-observation-controls!)
  (run-forwarding-controls!)
  (define (check value why) (unless value (error 'reload-diagnostic-controls "~a" why)))
  (define ok-calls 0)
  (define tell-calls 0)
  (define fail-tell? #f)
  (define stream
    (new (class object%
           (super-new)
           (define/public (ok?) (set! ok-calls (add1 ok-calls)) #f)
           (define/public (tell)
             (set! tell-calls (add1 tell-calls))
             (if fail-tell? (error 'fake-stream "injected tell failure") 17)))))
  (check (and (equal? (stream-view stream #f) (hasheq 'ok #f))
              (= ok-calls 1) (= tell-calls 0))
         "nonfailed observation calls ok? and never tell")
  (check (and (equal? (stream-view stream #t) (hasheq 'ok #f 'logical_item_position 17))
              (= ok-calls 2) (= tell-calls 1))
         "failed observation calls tell once and keeps logical item position")
  (set! fail-tell? #t)
  (define events '())
  (define reader
    (new (make-observed-reader-class
          (class object% (super-new) (define/public (read-from-file . args) #f))
          (lambda (stream phase args result)
            (set! events (append events (list (reader-event stream phase args result))))))))
  (check (eq? (send reader read-from-file stream #t) #f)
         "tell error preserves original false reader result")
  (check (and (= tell-calls 2) (= (length events) 2)
              (equal? (hash-ref (hash-ref (cadr events) 'value) 'result) '(#f))
              (equal? (hash-ref (hash-ref (hash-ref (cadr events) 'value) 'stream) 'status)
                      "unavailable"))
         "tell error is isolated while original returned value remains recorded")
  (void))
(define (make-reload-observer)
  (define events '())
  (define observed%
    (make-observed-reader-class
     text%
     (lambda (stream phase arguments result)
       (when (< (length events) 8)
         (define event (reader-event stream phase arguments result))
         (set! events (append events (list event)))))))
  (values (new observed%) (lambda () events)))
(define (registry-view rich)
  (define registry (get-the-snip-class-list))
  (define registry-count (send registry number))
  (unless (and (exact-nonnegative-integer? registry-count) (<= registry-count 1024))
    (error 'reload-diagnostic "snip registry count bound exceeded"))
  (for/list ([entry
              (in-list
               (append
                (for/list ([s (in-list (snips rich))]) (list "outer" rich s))
                (append-map
                 (lambda (s)
                   (if (is-a? s editor-snip%)
                       (let ([nested (send s get-editor)])
                         (for/list ([ns (in-list (snips nested))]) (list "nested" nested ns)))
                       '()))
                 (snips rich))))])
    (define owner (cadr entry))
    (define snip (caddr entry))
    (define cls (send snip get-snipclass))
    (define index (send registry find-position cls))
    (define name (send cls get-classname))
    (define version (send cls get-version))
    (unless (and (string? name) (<= (string-length name) 1024)
                 (exact-nonnegative-integer? version) (<= version 100000)
                 (exact-integer? index) (<= -1 index) (< index registry-count))
      (error 'reload-diagnostic "invalid bounded snip registry observation"))
    (hasheq 'document (car entry) 'position (send owner get-snip-position snip)
            'class name 'version version
            'registry_index index
            'registered_same_object
            (and (exact-nonnegative-integer? index) (eq? (send registry nth index) cls)))))
(define (call/observe-reload-failure load! path rich restored reader-events record!)
  ;; Read existing identity mappings only. In particular, `find` could autoload
  ;; and register a missing class, which would change the operation observed.
  (define registry-before (observation (lambda () (registry-view rich))))
  (call/preserve-failure
   load!
   (lambda (original)
     (define report
       (hasheq
        'original_error (bounded-message original)
        'wxme
        (observation
         (lambda ()
           (define size (file-size path))
           (unless (< 0 size byte-limit) (error 'reload-diagnostic "WXME file bound exceeded"))
           ;; Bound the read itself as well as the prior file-size observation.
           (define bytes (call-with-input-file path
                           (lambda (in) (read-bytes (add1 byte-limit) in))))
           (unless (and (bytes? bytes) (= size (bytes-length bytes))
                        (< (bytes-length bytes) byte-limit))
             (error 'reload-diagnostic "WXME size changed"))
           ;; Ordered byte arrays use the existing lossless chunked JSON
           ;; transport even at the file cap; a giant string would not.
           (hasheq 'bytes size 'sha256 (digest bytes) 'encoding "byte-array"
                   'data (bytes->list bytes))))
        'registry_before registry-before
        'registry_after (observation (lambda () (registry-view rich)))
        'reader (observation reader-events)
        'partial_restored (observation (lambda () (editor-view restored)))))
     (write-json report (open-output-string))
     (record! 'reload_failure report))))
