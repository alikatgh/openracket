#lang racket/base

;; Native integration gate, not a model of Check Syntax. This calls the stock
;; exported online-comp monitor/go pair and consumes the real handler trace.
;; Run in a fresh process for each of stock, default-off, and enabled.
(require json
         racket/async-channel
         racket/cmdline
         racket/file
         racket/list
         racket/path
         racket/place
         racket/port
         racket/runtime-path
         syntax/modresolve)

(define-runtime-path manifest-path "../manifest.json")
(define mode #f)
(define output-path #f)
(define runtime-root #f)
(define fixture-timeout 30)
(define suite-timeout 180)
(command-line
 #:program "native-trace.rkt"
 #:once-each
 [("--mode") value "stock, off, or on" (set! mode value)]
 [("--output") value "JSON capture destination" (set! output-path value)]
 [("--runtime-root") value "Root of this disposable Racket installation"
  (set! runtime-root (simplify-path (path->complete-path value) #t))]
 [("--timeout") value "Seconds allowed per fixture"
  (define n (string->number value))
  (unless (and (real? n) (positive? n) (<= n 120))
    (error 'native-trace "--timeout must be in (0, 120]; whole suite remains bounded at 180 seconds"))
  (set! fixture-timeout n)])
(unless (and (member mode '("stock" "off" "on")) output-path runtime-root)
  (error 'native-trace "--mode stock|off|on, --runtime-root and --output are required"))
(unless (equal? (version) "9.3")
  (error 'native-trace "this source-pinned gate requires Racket 9.3"))
(define expected-flag (and (equal? mode "on") "1"))
(unless (equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") expected-flag)
  (error 'native-trace "stock/off require an unset flag; on requires exactly 1"))

(define (bytes->hex bs)
  (apply string-append
         (for/list ([b (in-bytes bs)])
           (define s (number->string b 16))
           (if (= (string-length s) 1) (string-append "0" s) s))))
(define (file-digest p)
  (call-with-input-file p (lambda (in) (bytes->hex (sha256-bytes (port->bytes in))))))
(define manifest (call-with-input-file manifest-path read-json))
(define (bytes-prefix? prefix value)
  (and (<= (bytes-length prefix) (bytes-length value))
       (bytes=? prefix (subbytes value 0 (bytes-length prefix)))))
(define (root-suffix path root)
  (define raw (path->bytes path))
  (define root-bytes (path->bytes root))
  (define prefix (path->bytes (path->directory-path root)))
  (cond
    [(bytes=? raw root-bytes) #""]
    [(and (bytes-prefix? prefix raw)
          ;; Verify containment without discarding any original path bytes.
          (bytes-prefix? prefix (path->bytes (simplify-path path #f))))
     (subbytes raw (bytes-length prefix))]
    [else #f]))
(define executable
  (simplify-path (find-executable-path (find-system-path 'exec-file)) #t))
(unless (and (directory-exists? runtime-root) (root-suffix executable runtime-root))
  (error 'native-trace "--runtime-root must contain the actual resolved Racket executable"))
(define source-pins
  (hasheq 'interval-map (if (equal? mode "stock")
                   (hash-ref manifest 'original_sha256)
                   (hash-ref manifest 'patched_sha256))
          'xref "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7"
          'traversals "bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00"
          'online-comp "1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5"))
(define source-evidence
  (for/hasheq ([name '(interval-map xref traversals online-comp)])
    (define mod (if (eq? name 'interval-map)
                    'data/interval-map
                    (string->symbol (format "drracket/private/syncheck/~a" name))))
    (define path (resolve-module-path mod #f))
    (unless (path? path)
      (error 'native-trace "module did not resolve to a file: ~s" mod))
    (unless (root-suffix (simplify-path path #t) runtime-root)
      (error 'native-trace "~a resolves outside the verified disposable runtime root" name))
    (define digest (file-digest path))
    (unless (equal? digest (hash-ref source-pins name))
      (error 'native-trace "source pin mismatch for ~a: ~a" name digest))
    (values name (hasheq 'path (path->string path) 'sha256 digest))))

;; No filesystem contents are inferred or synthesized for the handler. Each
;; string is read with source locations and genuinely expanded in a fresh base
;; namespace, with the source file on disk for normal module-path resolution.
(struct fixture (name source repeated-key minimum no-docs-key) #:transparent)
(define fixtures
  (list
   (fixture
    "repeated-base"
    (string-append
     "#lang racket/base\n"
     "(define existing 7)\n"
     "(define first (add1 existing))\n"
     "(define second (add1 first))\n"
     "(list (add1 second) (add1 existing) first second)\n")
    'add1 4 #f)
   (fixture
    "unicode"
    (string-append
     "#lang racket/base\n"
     ";; Unicode before identifiers tests character positions: λ 雪 🦊\n"
     "(define existing 10)\n"
     "(define δ (λ (雪) (add1 雪)))\n"
     "(list (δ existing) (add1 existing) \"λ雪🦊\")\n")
    'add1 2 #f)
   (fixture
    "phase-one"
    (string-append
     "#lang racket/base\n"
     "(require (for-syntax racket/base))\n"
     "(begin-for-syntax\n"
     "  (define existing (add1 (add1 0)))\n"
     "  (void existing))\n"
     "(define-syntax (answer stx) (datum->syntax stx 42))\n"
     "(answer)\n")
    'add1 2 #f)
   (fixture
    "import-aliases"
    (string-append
     "#lang racket/base\n"
     "(require (rename-in racket/base [add1 bump])\n"
     "         (prefix-in base: racket/base))\n"
     "(define existing 1)\n"
     "(list (bump existing) (bump 2)\n"
     "      (base:add1 existing) (base:add1 4))\n")
    'bump 2 #f)
   (fixture
    "undocumented-binding"
    (string-append
     "#lang racket/base\n"
     "(module local racket/base\n"
     "  (provide undocumented-value)\n"
     "  (define undocumented-value 7))\n"
     "(require (submod \".\" local))\n"
     "(define existing undocumented-value)\n"
     "(list (add1 existing) (add1 undocumented-value))\n")
    'add1 2 'undocumented-value)))

;; Bound all fixture work, including expansion, monitor/go rendezvous and rename
;; requests. The custodian also owns the stock monitor's answerer threads.
(define (call/bounded seconds thunk)
  (define cust (make-custodian))
  (define result (make-async-channel))
  (dynamic-wind
   void
   (lambda ()
     (parameterize ([current-custodian cust])
       (thread
        (lambda ()
          (with-handlers ([exn? (lambda (e) (async-channel-put result (cons #f e)))])
            (async-channel-put result (cons #t (thunk)))))))
     (define answer (sync/timeout seconds result))
     (unless answer (error 'native-trace "native operation exceeded ~a seconds" seconds))
     (if (car answer) (cdr answer) (raise (cdr answer))))
   (lambda () (custodian-shutdown-all cust))))

(define rename-queries '("openracket-fresh-name" "existing" "add1" "λ" "δ"))
(define (capture-fixture spec monitor go source-root)
  (define source-path (build-path source-root (string-append (fixture-name spec) ".rkt")))
  (display-to-file (fixture-source spec) source-path #:exists 'error)
  (parameterize ([current-namespace (make-base-namespace)]
                 [current-directory source-root]
                 [current-load-relative-directory source-root])
    (define input (open-input-string (fixture-source spec)))
    (port-count-lines! input)
    (define expanded
      (parameterize ([read-accept-reader #t])
        (expand (read-syntax source-path input))))
    (close-input-port input)
    (unless (equal? (syntax-source expanded) source-path)
      (error 'native-trace "expanded source does not match monitor source"))
    (define payloads '())
    (define orig-cust (current-custodian))
    ;; monitor registers its real receiver synchronously before starting its
    ;; thread. go's final channel rendezvous acknowledges that send-back ran.
    (define monitor-thread
      (monitor (lambda (payload) (set! payloads (cons payload payloads)))
               source-path source-path orig-cust))
    (unless (thread? monitor-thread) (error 'native-trace "monitor did not return a thread"))
    (unless (void? (go expanded source-path source-path orig-cust))
      (error 'native-trace "go did not complete with void"))
    (unless (and (= (length payloads) 1)
                 (list? (car payloads))
                 (andmap vector? (car payloads)))
      (error 'native-trace "handler error or unexpected send-back payload: ~s" payloads))
    (define trace (car payloads))
    (when (null? trace) (error 'native-trace "handler returned an empty trace"))
    (define docs
      (filter (lambda (v) (eq? (vector-ref v 0) 'syncheck:add-docs-menu)) trace))
    (when (null? docs) (error 'native-trace "documentation annotations missing; install native docs"))
    (for ([doc (in-list docs)])
      (unless (and (= (vector-length doc) 8)
                   (exact-nonnegative-integer? (vector-ref doc 1))
                   (exact-nonnegative-integer? (vector-ref doc 2))
                   (<= (vector-ref doc 1) (vector-ref doc 2) (string-length (fixture-source spec)))
                   (symbol? (vector-ref doc 3))
                   (string? (vector-ref doc 4))
                   (positive? (string-length (vector-ref doc 4)))
                   (path? (vector-ref doc 5))
                   (vector-ref doc 6))
        (error 'native-trace "malformed documentation annotation: ~s" doc)))
    (define repeated-docs
      (filter (lambda (v) (eq? (vector-ref v 3) (fixture-repeated-key spec))) docs))
    (for ([doc (in-list repeated-docs)])
      (unless (equal? (substring (fixture-source spec) (vector-ref doc 1) (vector-ref doc 2))
                      (symbol->string (fixture-repeated-key spec)))
        (error 'native-trace "repeated binding's character positions do not match source")))
    (unless (>= (length (remove-duplicates (map (lambda (v) (vector-ref v 1)) repeated-docs)))
                (fixture-minimum spec))
      (error 'native-trace "documented repeated references missing in ~a" (fixture-name spec)))
    (when (and (fixture-no-docs-key spec)
               (ormap (lambda (v) (eq? (vector-ref v 3) (fixture-no-docs-key spec))) docs))
      (error 'native-trace "unexpected docs for local undocumented binding"))
    (when (equal? (fixture-name spec) "import-aliases")
      (unless (>= (length (filter (lambda (v) (eq? (vector-ref v 3) 'base:add1)) docs)) 2)
        (error 'native-trace "prefixed documented references missing")))

    (define channel-ids (make-hasheq))
    (define (channel-id p)
      (hash-ref! channel-ids p (lambda () (hash-count channel-ids))))
    ;; Normalize roots structurally, only for path values. Preserve convention
    ;; and the exact remaining path bytes. Strings, symbols, labels, definition
    ;; tags, anchors, positions, request IDs, numbers and entry order stay exact.
    (define (encode-path path)
      (define fixture-suffix (root-suffix path source-root))
      (define runtime-suffix (root-suffix path runtime-root))
      (list "path" (symbol->string (path-convention-type path))
            (cond
              [fixture-suffix (list "root" "fixture" (bytes->list fixture-suffix))]
              [runtime-suffix (list "root" "runtime" (bytes->list runtime-suffix))]
              [else (list "literal" (bytes->list (path->bytes path)))])))
    (define (encode value)
      (cond
        [(boolean? value) value]
        [(string? value) value]
        [(symbol? value) (list "symbol" (symbol->string value))]
        [(number? value) (list "number" (number->string value))]
        [(path? value) (encode-path value)]
        [(bytes? value) (list "bytes" (bytes->list value))]
        [(char? value) (list "character" (char->integer value))]
        [(null? value) (list "list")]
        [(list? value) (cons "list" (map encode value))]
        [(pair? value) (list "pair" (encode (car value)) (encode (cdr value)))]
        [(vector? value) (cons "vector" (map encode (vector->list value)))]
        [(place-channel? value)
         (unless (hash-has-key? channel-ids value)
           (error 'native-trace "unrecognized place-channel outside a rename field"))
         (list "rename-channel" (channel-id value))]
        [else (error 'native-trace "unsupported trace value; refusing lossy encoding: ~s" value)]))
    (define rename-answers
      (append*
       (for/list ([entry (in-list trace)] [entry-index (in-naturals)])
         (define method (vector-ref entry 0))
         (cond
           [(memq method '(syncheck:add-arrow/name-dup/pxpy syncheck:add-id-set))
            (define expected-size (if (eq? method 'syncheck:add-id-set) 4 14))
            (unless (= (vector-length entry) expected-size)
              (error 'native-trace "rename trace signature changed: ~s" entry))
            (define channel (vector-ref entry (- expected-size 2)))
            (define request-id (vector-ref entry (- expected-size 1)))
            (unless (and (place-channel? channel) (exact-nonnegative-integer? request-id))
              (error 'native-trace "invalid genuine rename endpoint"))
            (define identity (channel-id channel))
            (for/list ([query (in-list rename-queries)])
              (place-channel-put channel (list request-id query))
              ;; Wrap the event so a legitimate #f answer is not a timeout.
              (define reply (sync/timeout 5 (handle-evt channel (lambda (v) (list v)))))
              (unless (and reply (boolean? (car reply)))
                (error 'native-trace "rename answer missing or non-boolean"))
              (hasheq 'entry_index entry-index 'channel identity 'request_id request-id
                      'query query 'answer (car reply)))]
           [else '()]))))
    (when (null? rename-answers) (error 'native-trace "no real rename requests were exercised"))
    (hasheq 'name (fixture-name spec)
            'source (fixture-source spec)
            'trace (map encode trace)
            'rename_answers rename-answers
            'documentation_count (length docs)
            'repeated_key (symbol->string (fixture-repeated-key spec))
            'repeated_minimum (fixture-minimum spec)
            'no_docs_key (and (fixture-no-docs-key spec) (symbol->string (fixture-no-docs-key spec))))))

(define suite-cust (make-custodian))
(define source-root
  (simplify-path (make-temporary-file "openracket-native-trace-~a" 'directory) #t))
(dynamic-wind
 void
 (lambda ()
   (parameterize ([current-custodian suite-cust]
                  ;; The module's define-logger captures this parent on load.
                  ;; All monitor receivers use the same isolated logger.
                  [current-logger (make-logger 'openracket-native-trace #f)])
     (define capture
       (call/bounded
        suite-timeout
        (lambda ()
          (define activation
            (dynamic-require 'data/interval-map
                             'openracket-interval-map-fast-set-enabled?
                             (lambda () "unexported")))
          (define expected-activation
            (cond [(equal? mode "stock") "unexported"] [(equal? mode "on") #t] [else #f]))
          (unless (equal? activation expected-activation)
            (error 'native-trace "runtime activation mismatch: expected ~s, got ~s"
                   expected-activation activation))
          (define monitor (dynamic-require 'drracket/private/syncheck/online-comp 'monitor))
          (define go (dynamic-require 'drracket/private/syncheck/online-comp 'go))
          (unless (and (procedure-arity-includes? monitor 4) (procedure-arity-includes? go 4))
            (error 'native-trace "stock monitor/go API arity changed"))
          (define results
            (for/list ([spec (in-list fixtures)])
              (call/bounded fixture-timeout
                            (lambda () (capture-fixture spec monitor go source-root)))))
          (define answers (append-map (lambda (r) (hash-ref r 'rename_answers)) results))
          (unless (and (ormap (lambda (r) (hash-ref r 'answer)) answers)
                       (ormap (lambda (r) (not (hash-ref r 'answer))) answers))
            (error 'native-trace "rename protocol must exercise both true and false answers"))
          (hasheq 'schema "openracket-actual-online-comp-trace/v1"
                  'completed #t
                  'runtime (hasheq 'mode mode 'version (version)
                                   'activation activation 'flag (or expected-flag 'null)
                                   'root (path->string runtime-root)
                                   'executable (path->string executable)
                                   'fixture_timeout_seconds fixture-timeout
                                   'suite_timeout_seconds suite-timeout
                                   'sources source-evidence)
                  'fixtures results))))
     (call-with-output-file output-path #:exists 'error
       (lambda (out) (write-json capture out) (newline out)))
     (printf "Captured actual online-comp trace (~a): ~a\n" mode output-path)))
 (lambda ()
   (custodian-shutdown-all suite-cust)
   (delete-directory/files source-root)))
