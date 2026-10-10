#lang racket/base
;; Separate-process, trusted-code Racket engine for the native editor.
;; Protocol and compatibility notes: runtime/PROTOCOL.md.
(require json racket/async-channel racket/list racket/match racket/path racket/port
         syntax/modread)

(define protocol-out (current-output-port))
(define protocol-in (current-input-port))
(define root-custodian (current-custodian))
(define max-request-bytes (* 8 1024 1024))
(define max-source-chars (* 2 1024 1024))
(define max-output-bytes (* 256 1024))
(define max-output-events 256)
(define max-chunk-bytes 4096)
(define max-input-bytes (* 64 1024))
;; User output can never wait for the protocol writer. The queue, event count,
;; chunk size, and cumulative bytes all have independent fixed upper bounds.
(define events (make-async-channel 512))
(define writer
  (thread
   (lambda ()
     (with-handlers ([exn:fail? (lambda (_) (exit 1))])
       (let loop ()
         (define msg (async-channel-get events))
         (cond [(eq? msg 'shutdown) (flush-output protocol-out)]
               [else (write-json msg protocol-out) (newline protocol-out)
                     (flush-output protocol-out) (loop)]))))))
(define (emit h) (async-channel-put events h))
(define (done id status) (emit (hasheq 'event "done" 'id id 'status status)))
(define (clip s [n 16384])
  (if (> (string-length s) n) (string-append (substring s 0 n) "… [truncated]") s))
(define (source-text s)
  (cond [(path? s) (path->string s)] [(string? s) s] [(symbol? s) (symbol->string s)]
        [else #f]))
(define (location->json loc)
  (hasheq 'source (or (source-text (srcloc-source loc)) 'null)
          'line (or (srcloc-line loc) 'null)
          'column (or (srcloc-column loc) 'null)
          'position (or (srcloc-position loc) 'null)
          'span (or (srcloc-span loc) 'null)))
(define (syntax->location s)
  (srcloc (syntax-source s) (syntax-line s) (syntax-column s)
          (syntax-position s) (syntax-span s)))
(struct exn:fail:missing-language exn:fail ())
(define (error-kind e)
  (cond [(exn:fail:missing-language? e) "missing-language"] [(exn:break? e) "interrupted"] [(exn:fail:read:eof? e) "incomplete"]
        [(exn:fail:read? e) "read"] [(exn:fail:syntax? e) "syntax"]
        [else "runtime"]))
(define (report-error id e [fallback #f])
  (define raw
    (append
     (cond [(exn:fail:read? e) (exn:fail:read-srclocs e)]
           [(exn:fail:syntax? e) (map syntax->location (exn:fail:syntax-exprs e))]
           [(and (exn? e) (exn:srclocs? e)) ((exn:srclocs-accessor e) e)]
           [else null])
     (if (exn? e)
         (filter values (map cdr (continuation-mark-set->context (exn-continuation-marks e))))
         null)))
  (define useful
    (filter (lambda (loc)
              (define src (source-text (srcloc-source loc)))
              (and src (not (regexp-match? #rx"[/\\\\]runtime[/\\\\]bridge[.]rkt$" src)))) raw))
  (define locs (remove-duplicates (if (null? useful) (if fallback (list fallback) null) useful)))
  (emit (hasheq 'event "error" 'id id 'kind (error-kind e)
                'message (clip (if (exn? e) (exn-message e) (format "Uncaught value: ~s" e)))
                'locations (map location->json (take locs (min 16 (length locs)))))))
(define (protocol-error id message [kind "protocol"])
  (emit (hasheq 'event "error" 'id id 'kind kind 'message message 'locations null))
  (done id "error"))

;; A budget is shared by stdout/stderr/value for one operation. Bytes are
;; decoded incrementally so a UTF-8 scalar split across writes stays intact.
(struct budget (id bytes count truncated?) #:mutable)
(define (truncate! b stream)
  (unless (budget-truncated? b)
    (set-budget-truncated?! b #t)
    (emit (hasheq 'event "truncated" 'id (budget-id b) 'stream stream
                  'limit max-output-bytes 'event_limit max-output-events
                  'message "Output limit reached; further output from this operation is discarded."))))
(define (emit-output b stream bytes)
  (unless (or (zero? (bytes-length bytes)) (budget-truncated? b))
    (define remaining (- max-output-bytes (budget-bytes b)))
    (cond
      [(or (<= remaining 0) (>= (budget-count b) max-output-events)) (truncate! b stream)]
      [else
       (define n (min remaining (bytes-length bytes)))
       (define h (hasheq 'event stream 'id (budget-id b)
                         'text (bytes->string/utf-8 bytes #\uFFFD 0 n)))
       (if (sync/timeout 0 (async-channel-put-evt events h))
           (begin (set-budget-bytes! b (+ n (budget-bytes b)))
                  (set-budget-count! b (add1 (budget-count b)))
                  (when (< n (bytes-length bytes)) (truncate! b stream)))
           (truncate! b stream))])))
;; Return a prefix ending on a UTF-8 boundary, keeping <=3 trailing bytes.
(define (utf8-prefix-size bs n)
  (let loop ([i (sub1 n)] [continuations 0])
    (cond [(< i 0) n]
          [else
           (define v (bytes-ref bs i))
           (cond [(and (>= v #x80) (< v #xC0))
                  (if (< continuations 3) (loop (sub1 i) (add1 continuations)) n)]
                 [else
                  (define needed (cond [(< v #x80) 1] [(< v #xE0) 2]
                                       [(< v #xF0) 3] [(< v #xF5) 4] [else 1]))
                  (if (> needed (add1 continuations)) i n)])])))
(define (make-capture-port b stream)
  (define buffer (make-bytes (+ max-chunk-bytes 4)))
  (define used 0)
  (define lock (make-semaphore 1))
  (define (flush-locked! final?)
    (define n (if final? used (utf8-prefix-size buffer used)))
    (when (> n 0)
      (emit-output b stream (subbytes buffer 0 n))
      (bytes-copy! buffer 0 buffer n used)
      (set! used (- used n))))
  (define (flush! [final? #f])
    (call-with-semaphore lock (lambda () (flush-locked! final?))))
  (define p
    (make-output-port
     (string->symbol stream) always-evt
     (lambda (bs start end non-block? breakable?)
       (call-with-semaphore
        lock
        (lambda ()
          (cond [(= start end) (flush-locked! #f)]
                [(budget-truncated? b) (set! used 0)]
                [else
                 (let loop ([i start])
                   (when (< i end)
                     (define n (min (- end i) (- max-chunk-bytes used)))
                     (bytes-copy! buffer used bs i (+ i n))
                     (set! used (+ used n))
                     (when (or (= used max-chunk-bytes)
                               (and (> used 0) (= (bytes-ref buffer (sub1 used)) 10)))
                       (flush-locked! #f))
                     (unless (budget-truncated? b) (loop (+ i n)))))])))
       (- end start))
     (lambda () (flush! #t))))
  (values p flush!))

(define session-custodian (make-custodian root-custodian))
(define session-namespace #f)
(define session-directory (current-directory))
(define session-source #f)
(define initial-parameterization (current-parameterization))
(define session-parameters #f)
(define current-value-port (make-parameter #f))
(define default-language-printer (current-print))
;; Stable adapter has no operation-specific port closure to retain/reuse.
(define (bridge-printer v)
  (parameterize ([current-output-port (or (current-value-port) (current-output-port))])
    (default-language-printer v)))
(define (capture-session-parameters!)
  ;; Publish one complete snapshot, never a half-updated parameter/cell pair.
  (define snapshot (vector (current-parameterization) (current-preserved-thread-cell-values)))
  (set! session-directory (current-directory))
  (set! session-parameters snapshot))
(define active #f)
(struct task (id op thread custodian input output-flushers budget result interrupted? input-requested?) #:mutable)
(define (new-namespace!)
  (custodian-shutdown-all session-custodian)
  (set! session-custodian (make-custodian root-custodian))
  (set! session-namespace #f)
  (set! session-source #f)
  (set! session-parameters #f))
(define (ensure-namespace!)
  (unless session-namespace (set! session-namespace (make-base-namespace))))

(define (make-user-input t)
  (define-values (pin pout) (make-pipe max-input-bytes))
  (define (request!)
    (unless (task-input-requested? t)
      (set-task-input-requested?! t #t)
      (emit (hasheq 'event "input-request" 'id (task-id t)))))
  (define p
    (make-input-port
     'interactions-input
     (lambda (bs)
       (define n (read-bytes-avail!* bs pin))
       (cond [(and (number? n) (zero? n))
              (request!) (wrap-evt pin (lambda (_) 0))]
             [else (set-task-input-requested?! t #f) n]))
     #f (lambda () (close-input-port pin))))
  (values p pout))

(define (read-port source name)
  (define p (open-input-string source name))
  (port-count-lines! p)
  p)
(define (read-interaction p)
  ;; Plain-text Racket reader, not a parenthesis heuristic. Readtable behavior
  ;; follows the active language's current-read-interaction parameter.
  ((current-read-interaction) 'interactions p))
(define (check-source id source)
  (define p (read-port source 'interactions))
  (with-handlers ([exn:fail:read:eof?
                   (lambda (_) (emit (hasheq 'event "check" 'id id 'status "incomplete")))]
                  [exn:fail:read?
                   (lambda (e) (emit (hasheq 'event "check" 'id id 'status "error"))
                     (report-error id e)
                     (set-box! (task-result active) "error"))])
    (let loop ()
      (unless (eof-object? (read-interaction p)) (loop)))
    (emit (hasheq 'event "check" 'id id 'status "complete"))))
(define (print-values thunk port)
  (call-with-values thunk
    (lambda vals
      (for ([v (in-list vals)] #:unless (void? v))
        ;; current-print is the actual language printer. It preserves exact
        ;; rationals, quotations, multiple values, and custom print handlers.
        (parameterize ([current-output-port port]) ((current-print) v))))))
(define (run-module req value-port)
  (define source (hash-ref req 'source))
  (define requested-dir (hash-ref req 'cwd (path->string session-directory)))
  (define cwd (path->complete-path requested-dir))
  (unless (directory-exists? cwd) (error 'run "Working directory does not exist: ~a" cwd))
  (define raw-path (hash-ref req 'path 'null))
  (define path (if (string? raw-path) (path->complete-path raw-path cwd)
                   (build-path cwd "untitled.rkt")))
  (define p (read-port source path))
  (set! session-directory cwd)
  (set! session-source path)
  (parameterize ([current-directory cwd]
                 [current-load-relative-directory (or (path-only path) cwd)]
                 [current-namespace session-namespace]
                 [compile-enforce-module-constants #f]
                 [compile-context-preservation-enabled #t])
    (define stx
      (with-module-reading-parameterization (lambda () (read-syntax path p))))
    (unless (and (syntax? stx)
                 (let ([d (syntax->datum stx)])
                   (and (pair? d) (eq? (car d) 'module))))
      (raise (exn:fail:missing-language "Missing #lang. Add #lang racket as the first line (or choose another installed language explicitly)."
                       (current-continuation-marks))))
    (unless (eof-object? (read-syntax path p))
      (error 'run "Expected one module; unexpected content after the module."))
    (parameterize ([current-module-declare-name (make-resolved-module-path path)]
                   [current-module-declare-source path])
      (eval stx))
    (dynamic-require path #f)
    (when (module-declared? `(submod ,path main))
      (dynamic-require `(submod ,path main) #f))
    (set! session-namespace (module->namespace path))
    (current-namespace session-namespace)
    (capture-session-parameters!)))
(define (evaluate-interactions source value-port)
  (define p (read-port source 'interactions))
  (let loop ()
    (define stx (read-interaction p))
    (unless (eof-object? stx)
      (with-handlers ([(lambda (e) (not (exn:break? e)))
                      (lambda (e)
                        (report-error (task-id active) e (syntax->location stx))
                        (set-box! (task-result active) "error"))])
        (print-values (lambda () (eval-syntax (namespace-syntax-introduce stx))) value-port))
      ;; As in a REPL, a failed form does not erase earlier definitions; stop
      ;; this submitted group instead of accidentally running later forms.
      (when (equal? (unbox (task-result active)) "ok") (loop)))))

(define (start-task req)
  (define id (hash-ref req 'id 'null))
  (define op (hash-ref req 'op))
  (cond
    [active (protocol-error id "An operation is already running. Break it or wait for completion." "busy")]
    [(or (not (string? (hash-ref req 'source #f)))
         (> (string-length (hash-ref req 'source "")) max-source-chars))
     (protocol-error id "source must be a string of at most 2,097,152 characters.")]
    [else
     (when (equal? op "run") (new-namespace!))
     (define b (budget id 0 0 #f))
     (define t (task id op #f session-custodian #f null b (box "ok") #f #f))
     (set! active t)
     (define-values (stdout flush-stdout) (make-capture-port b "stdout"))
     (define-values (stderr flush-stderr) (make-capture-port b "stderr"))
     (define-values (value-out flush-value) (make-capture-port b "value"))
     (set-task-output-flushers! t (list flush-stdout flush-stderr flush-value))
     (define-values (user-in user-out)
       (parameterize ([current-custodian session-custodian]) (make-user-input t)))
     (set-task-input! t user-out)
     (emit (hasheq 'event "started" 'id id 'op op))
     (define gate (make-semaphore 0))
     (define finished (box #f))
     (define worker
       (parameterize ([current-custodian session-custodian])
         (thread
          (lambda ()
            (semaphore-wait gate)
            ;; Parameterizations bind thread cells; both must be restored to
            ;; preserve direct parameter mutations when switching workers.
            ;; Never install user cells into the control or writer thread.
            (when session-parameters
              (current-preserved-thread-cell-values (vector-ref session-parameters 1)))
            (call-with-parameterization
             (if session-parameters (vector-ref session-parameters 0) initial-parameterization)
             (lambda ()
               (parameterize ([current-output-port stdout]
                              [current-error-port stderr]
                              [current-input-port user-in]
                              [current-value-port value-out]
                              [current-custodian (task-custodian t)]
                              [exit-handler (lambda (code) (error 'exit "Program requested exit (~a); the editor stays open." code))])
                 (unless session-parameters
                   (current-directory session-directory)
                   (current-load-relative-directory session-directory)
                   (compile-context-preservation-enabled #t)
                   (compile-enforce-module-constants #f)
                   (current-subprocess-custodian-mode 'kill)
                   (current-print bridge-printer))
                 (with-handlers ([(lambda (_) #t)
                                  (lambda (e)
                                    (cond [(exn:break? e) (set-box! (task-result t) "interrupted")]
                                          [else (set-box! (task-result t) "error")])
                                    (report-error id e)
                                    (when (equal? op "eval") (capture-session-parameters!)))])
                   (ensure-namespace!)
                   (current-namespace session-namespace)
                   (cond [(equal? op "run") (run-module req value-out)]
                         [(equal? op "check") (check-source id (hash-ref req 'source))]
                         [else
                          (evaluate-interactions (hash-ref req 'source) value-out)
                          (capture-session-parameters!)])))))
            (set-box! finished #t)))))
     (set-task-thread! t worker)
     (semaphore-post gate)
     ;; Monitor lives outside the user's custodian, and therefore can report a
     ;; terminal result even when the whole user custodian has been shut down.
     (thread
      (lambda ()
        (let wait-loop ()
          (unless (sync/timeout 0.03 (thread-dead-evt worker))
            (for ([flush! (in-list (task-output-flushers t))]) (flush!))
            (wait-loop)))
        (when (and (not (unbox finished)) (not (task-interrupted? t)))
          (custodian-shutdown-all (task-custodian t))
          (set! session-custodian (make-custodian root-custodian))
          (set-box! (task-result t) "error")
          (report-error id (exn:fail "Evaluation thread stopped before completing. Its resources were canceled; Run again if its state is uncertain." (current-continuation-marks))))
        (when (task-interrupted? t)
          (custodian-shutdown-all (task-custodian t))
          (set! session-custodian (make-custodian root-custodian))
          (set-box! (task-result t) "interrupted"))
        (for ([flush! (in-list (task-output-flushers t))]) (flush! #t))
        (unless (port-closed? user-out) (close-output-port user-out))
        (when (eq? active t) (set! active #f))
        (done id (unbox (task-result t)))))]))

(define (break-task id)
  (define t active)
  (when t
    (set-task-interrupted?! t #t)
    (break-thread (task-thread t))
    ;; Cooperative break first, then forcibly cancel Racket-managed threads,
    ;; sockets, ports, and subprocesses. The Rust supervisor is the final
    ;; hard-kill fallback for a blocked VM/FFI call or process termination.
    (thread
     (lambda ()
       (unless (sync/timeout 0.25 (thread-dead-evt (task-thread t)))
         (custodian-shutdown-all (task-custodian t))))))
  (done id "ok"))
(define (supply-input req)
  (define id (hash-ref req 'id 'null))
  (define text (hash-ref req 'text ""))
  (cond
    [(not active) (protocol-error id "No running program is waiting for input.")]
    [(not (string? text)) (protocol-error id "input text must be a string.")]
    [else
     (define bs (string->bytes/utf-8 text))
     (define port (task-input active))
     (cond [(> (bytes-length bs) max-input-bytes)
            (protocol-error id "Input chunk exceeds 65,536 UTF-8 bytes.")]
           [(port-closed? port) (protocol-error id "Program input is already closed.")]
           [else
            (define n (write-bytes-avail* bs port))
            (cond [(not (= n (bytes-length bs)))
                   (protocol-error id (format "Input buffer full; accepted ~a of ~a bytes." n (bytes-length bs)))]
                  [else
                   (set-task-input-requested?! active #f)
                   (when (hash-ref req 'eof #f) (close-output-port port))
                   (done id "ok")])])]))
(define (dispatch req)
  (define id (if (hash? req) (hash-ref req 'id 'null) 'null))
  (with-handlers ([exn? (lambda (e) (protocol-error id (clip (exn-message e))))])
    (unless (hash? req) (error 'protocol "Request must be a JSON object."))
    (match (hash-ref req 'op #f)
      [(or "run" "eval" "check") (start-task req)]
      ["break" (break-task id)]
      ["input" (supply-input req)]
      ["reset" (if active (protocol-error id "Break the running operation before resetting." "busy")
                   (begin (new-namespace!) (done id "ok")))]
      ["shutdown"
       (custodian-shutdown-all session-custodian)
       (done id "ok") (async-channel-put events 'shutdown) (thread-wait writer) (exit 0)]
      [_ (protocol-error id "Unknown operation. Expected run, eval, check, break, input, reset, or shutdown.")])))

;; Bound even malformed input lines; never allocate an unbounded read-line.
(define (bounded-read-line)
  (define out (open-output-bytes))
  (let loop ([n 0] [oversized? #f])
    (define b (read-byte protocol-in))
    (cond [(eof-object? b) (if (zero? n) eof (if oversized? 'oversized (get-output-bytes out)))]
          [(= b 10) (if oversized? 'oversized (get-output-bytes out))]
          [else
           (unless (or oversized? (>= n max-request-bytes)) (write-byte b out))
           (loop (add1 n) (or oversized? (>= n max-request-bytes)))])))
(emit (hasheq 'event "ready" 'protocol 1 'racket_version (version)
              'max_source_chars max-source-chars 'max_output_bytes max-output-bytes))
(let loop ()
  (define line (bounded-read-line))
  (cond [(eof-object? line) (custodian-shutdown-all session-custodian)
                          (async-channel-put events 'shutdown) (thread-wait writer)]
        [(eq? line 'oversized) (protocol-error 'null "Protocol line exceeds 8 MiB.") (loop)]
        [else
         (with-handlers ([exn? (lambda (e) (protocol-error 'null (string-append "Invalid JSON: " (clip (exn-message e)))))])
           (dispatch (read-json (open-input-bytes line))))
         (loop)]))
