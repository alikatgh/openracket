#lang racket/base
;; Actual retained definitions-editor docs map, read only after the unchanged
;; genuine Check Syntax workflow. This does not replay or synthesize annotations.
(require data/interval-map json racket/class racket/file racket/gui/base
         racket/list racket/path racket/port racket/runtime-path rackunit
         syntax/modresolve "rackunit-failure-propagation.rkt" "docs-entry-diagnostic.rkt")
(provide run-interval-docs-postflight!)

(define-runtime-path host-path "independent-native-host.rkt")
(define-runtime-path workflow-path "independent-native-workflows.rkt")
(define original-map-pin "1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de")
(define candidate-map-pin "1f1636316c3ba3f307fcb33f44d68c00ee9804b775fac7d78916db01d87fec4d")
(define host-pin "ad0ba1ec80fb8dbcec86f54e1a0088d6a938c62c052d6bcaf7cb12e251134fb8")
(define workflow-pin "b175a92754e8f0e8a0f524ae5947f5eae8da605b0f3274bbc098e20ce1de53bf")
(define pins
  (hash 'blueboxes-gui "c81a8df93f0012b0ab564009bb4a9ad34d9ce1cde3795e180bfbe33a1008e721"
        'gui "5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e"
        'xref "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7"
        'traversals "bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00"
        'online-comp "1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5"))
(define fixture "#lang racket/base\n(define (bump x) (+ x 1))\n(bump 41)\n")
(define plus-tag '(def ((quote #%kernel) +)))
(define plus-anchor "(def._((quote._~23~25kernel)._+))")
(define capture-written? #f)

(define (require! v message)
  (unless v (error 'interval-docs-postflight "~a" message)))
(define (bytes->hex bs)
  (apply string-append
         (for/list ([b (in-bytes bs)])
           (define s (number->string b 16))
           (if (= (string-length s) 1) (string-append "0" s) s))))
(define (digest path)
  (call-with-input-file path (lambda (in) (bytes->hex (sha256-bytes (port->bytes in))))))
(define (bytes-prefix? prefix value)
  (and (<= (bytes-length prefix) (bytes-length value))
       (bytes=? prefix (subbytes value 0 (bytes-length prefix)))))

(define (run-interval-docs-postflight! frame)
  ;; Failed RackUnit checks propagate through the frozen host's existing fatal
  ;; exception route, including its unmodified screenshot/failure diagnostics.
  (parameterize ([current-check-handler raise])
    (capture! frame)))

(define (capture! frame)
  (require! (not capture-written?) "duplicate postflight invocation")
  (assert-rackunit-failure-propagation!)
  (check-eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
  (check-equal? (version) "9.3")
  (check-equal? (getenv "OPENRACKET_UI") "stock")
  (check-equal? (getenv "OPENRACKET_NATIVE_CASE") "check-syntax")
  (check-not-equal? (getenv "OPENRACKET_NATIVE_APPEARANCE_CHECK") "1")
  (define mode (getenv "OPENRACKET_INTERVAL_EXPECT_MODE"))
  (require! (member mode '("stock" "candidate-on")) "expected stock or candidate-on mode")
  (define enabled? (equal? mode "candidate-on"))
  (define flag (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET"))
  (check-equal? flag (and enabled? "1"))
  (define output (getenv "OPENRACKET_INTERVAL_DOCS_OUTPUT"))
  (require! (and output (not (equal? output ""))) "JSON output path is required")
  (require! (not (file-exists? output)) "refusing an existing JSON output (duplicate/stale capture)")
  (define root-env (getenv "OPENRACKET_INTERVAL_RUNTIME_ROOT"))
  (require! (and root-env (complete-path? root-env)) "explicit absolute runtime root is required")
  (define root (simplify-path root-env #t))
  (check-equal? (path->string root) root-env "runtime root must already be canonical")
  (require! (and (directory-exists? root) (not (equal? root-env "/")))
            "runtime root must be a specific clone directory")
  (check-equal? (path->bytes root) (string->bytes/utf-8 root-env)
                "root text/byte evidence must be lossless")
  (check-equal? (path-convention-type root) 'unix "only reviewed Unix native runtimes are supported")
  (define root-prefix (path->bytes (path->directory-path root)))
  (define (encode-path path)
    (require! (and (path? path) (complete-path? path)
                   (eq? (path-convention-type path) 'unix)) "unsupported/nonabsolute stored path")
    (require! (file-exists? path) "captured path must name an existing clone file")
    (define raw (path->bytes path))
    (require! (bytes=? raw (path->bytes (simplify-path path #f)))
              "noncanonical path bytes cannot be normalized losslessly")
    (require! (and (bytes-prefix? root-prefix raw)
                   (bytes-prefix? root-prefix (path->bytes (simplify-path path #t))))
              "path is outside the explicitly verified clone root")
    (define suffix (subbytes raw (bytes-length root-prefix)))
    (require! (positive? (bytes-length suffix)) "path must name a clone descendant")
    (list "path" "unix" (list "root" "runtime" (bytes->list suffix))))
  (define executable (simplify-path (find-executable-path (find-system-path 'exec-file)) #t))
  (define executable-evidence (encode-path executable))
  (define module-paths (make-hasheq))
  (define all-pins (hash-set pins 'interval-map (if enabled? candidate-map-pin original-map-pin)))
  (define sources
    (for/hash ([(name expected) (in-hash all-pins)])
      (define mod (if (eq? name 'interval-map) 'data/interval-map
                      (string->symbol (format "drracket/private/syncheck/~a" name))))
      (define path (resolve-module-path mod #f))
      (require! (path? path) "a pinned module did not resolve to a source file")
      (define encoded-path (encode-path path))
      (check-equal? (digest path) expected (format "actual ~a source pin" name))
      (hash-set! module-paths name path)
      (values name (hash 'path encoded-path 'sha256 expected))))
  (check-equal? (digest host-path) host-pin "exact two-insertion frozen-host derivative")
  (check-equal? (digest workflow-path) workflow-pin "unchanged real Check Syntax with fatal checks")
  ;; data/interval-map is already required by this module and the real GUI. The
  ;; fallback is used only for its absent stock export, never for activation errors.
  (define activation
    (dynamic-require 'data/interval-map 'openracket-interval-map-fast-set-enabled?
                     (lambda () 'unexported)))
  (check-equal? activation (if enabled? #t 'unexported))
  ;; module->namespace DOES NOT instantiate the module. If the genuine GUI did
  ;; not instantiate this exact resolved/pinned file, stop instead of loading it.
  (define blueboxes-ns (module->namespace (hash-ref module-paths 'blueboxes-gui)))
  (define gui-ns (module->namespace (hash-ref module-paths 'gui)))
  (require! (and (namespace? blueboxes-ns) (namespace? gui-ns)) "actual GUI module instances unavailable")
  ;; Compile one explicit expression in the existing module namespace so send
  ;; uses the ORIGINAL define-local-member-name transformer. A plain-symbol send
  ;; from this module, or get/start-docs-im (which may allocate), is invalid here.
  (define get-existing-docs-map
    (parameterize ([current-namespace blueboxes-ns])
      (eval '(lambda (editor) (send editor get-docs-im)))))
  (require! (procedure-arity-includes? get-existing-docs-map 1) "private read-only accessor missing")
  (define defs (send frame get-definitions-text))
  (define canvas (send frame get-definitions-canvas))
  (define tab (send frame get-current-tab))
  (define filename (send defs get-filename))
  (define text-before (send defs get-text))
  (define selection-before (list (send defs get-start-position) (send defs get-end-position)))
  (define modified-before (send defs is-modified?))
  (check-eq? (send canvas get-editor) defs)
  (check-equal? text-before fixture)
  (check-equal? (send defs last-position) 54)
  (check-equal? selection-before '(1 6))
  (check-equal? (substring text-before 36 37) "+")
  (check-false (send frame syncheck:error-report-visible?))
  (check-true (send (send frame syncheck:get-button) is-enabled?))
  (require! (positive? (hash-count (send defs syncheck:get-bindings-table))) "real binding graph must be nonempty")
  (define docs (get-existing-docs-map defs))
  (check-true (interval-map? docs) "actual existing definitions docs map")
  ;; Type-preserving, duplicate-preserving bounded datum encoder. Unsupported
  ;; values, cycles/deep data and non-clone paths fail rather than print lossily.
  (define remaining 10000)
  (define (encode value [depth 0])
    (set! remaining (sub1 remaining))
    (require! (and (positive? remaining) (< depth 64)) "datum encoding bound exceeded")
    (define (recur v) (encode v (add1 depth)))
    (cond
      [(path? value) (encode-path value)]
      [(boolean? value) (list "boolean" value)]
      [(exact-integer? value) (list "integer" (number->string value))]
      [(string? value) (list "string" value)]
      [(symbol? value)
       (require! (symbol-interned? value) "uninterned symbol cannot be encoded losslessly")
       (list "symbol" (symbol->string value))]
      [(bytes? value) (list "bytes" (bytes->list value))]
      [(list? value) (cons "list" (map recur value))]
      [(pair? value) (list "pair" (recur (car value)) (recur (cdr value)))]
      [(vector? value) (cons "vector" (map recur (vector->list value)))]
      [else (error 'interval-docs-postflight "unsupported datum type in actual docs map")]))
  (define (snapshot)
    (let loop ([iter (interval-map-iterate-first docs)] [previous-end -1] [count 0] [result '()])
      (cond
        [(not iter) (reverse result)]
        [else
         (define bounds (interval-map-iterate-key docs iter))
         (define stored (interval-map-iterate-value docs iter))
         (define entry
           (with-handlers
               ([exn? (lambda (e)
                        (with-handlers ([exn? void])
                          (write-docs-entry-diagnostic! count previous-end bounds stored))
                        (raise e))])
             (require! (< count 256) "actual docs interval bound exceeded")
             (require! (and (pair? bounds) (exact-integer? (car bounds)) (exact-integer? (cdr bounds))
                            (<= 0 (car bounds)) (< (car bounds) (cdr bounds))
                            (<= previous-end (car bounds)) (<= (cdr bounds) 55)) "invalid ordered interval geometry")
             (require! (and (list? stored) (= (length stored) 5)
                            (exact-integer? (car stored)) (exact-integer? (cadr stored))
                            (<= 0 (car stored) (car bounds))
                            (<= (cdr bounds) (cadr stored) 55)
                            (<= (car stored) (sub1 (cadr stored)))
                            (path? (list-ref stored 3))) "unsupported full stored docs-range geometry/value")
             (hash 'start (car bounds) 'end (cdr bounds) 'stored (encode stored))))
         (loop (interval-map-iterate-next docs iter) (cdr bounds) (add1 count)
               (cons entry result))])))
  (define intervals (snapshot))
  (require! (pair? intervals) "real docs map must be nonempty")
  (define plus (interval-map-ref docs 36 (lambda () (error 'interval-docs-postflight "actual + documentation missing"))))
  (define-values (plus-start plus-end plus-by-bounds) (interval-map-ref/bounds docs 36))
  (check-equal? (list plus-start plus-end) '(36 38))
  (check-eq? plus-by-bounds plus "ref/bounds returns the identical stored + value")
  (define at-37 (interval-map-ref docs 37 #f))
  (define at-38 (interval-map-ref docs 38 #f))
  (check-eq? at-37 plus "end+1 includes the character after +")
  (check-not-equal? at-38 plus "half-open stored interval excludes end+1")
  (check-equal? (take plus 3) (list 36 38 plus-tag))
  (check-equal? (list-ref plus 4) plus-anchor)
  (define plus-path (list-ref plus 3))
  (require! (path? plus-path) "actual + doc path must be a path value")
  (define plus-path-encoded (encode-path plus-path))
  (require! (regexp-match? #rx#"/reference/generic-numbers[.]html$" (path->bytes plus-path))
            "actual + documentation must target reference/generic-numbers.html")
  (define plus-indexes
    (for/list ([entry (in-list intervals)] [index (in-naturals)]
               #:when (and (= (hash-ref entry 'start) 36) (= (hash-ref entry 'end) 38))) index))
  (check-equal? (length plus-indexes) 1 "one exact [36,38) actual interval")
  (define plus-index (car plus-indexes))
  (check-equal? (hash-ref (list-ref intervals plus-index) 'stored) (encode plus))
  (check-equal? (snapshot) intervals "read-only capture cannot change any stored interval")
  (check-eq? (get-existing-docs-map defs) docs)
  (check-eq? (send frame get-definitions-text) defs)
  (check-eq? (send frame get-definitions-canvas) canvas)
  (check-eq? (send frame get-current-tab) tab)
  (check-eq? (send canvas get-editor) defs)
  (check-equal? (send defs get-filename) filename)
  (check-equal? (send defs get-text) text-before)
  (check-equal? (list (send defs get-start-position) (send defs get-end-position)) selection-before)
  (check-equal? (send defs is-modified?) modified-before)
  (check-eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
  (for ([(name path) (in-hash module-paths)])
    (check-equal? (digest path) (hash-ref all-pins name) "source must remain unchanged during capture"))
  (define report
    (hash 'schema "openracket-actual-gui-docs-map/v1" 'completed #t
          'runtime (hash 'mode mode 'version (version) 'flag (or flag 'null)
                         'activation (if (eq? activation 'unexported) "unexported" activation)
                         'root root-env 'root_bytes (bytes->list (path->bytes root))
                         'executable executable-evidence 'sources sources)
          'host (hash 'sha256 host-pin 'workflow_sha256 workflow-pin
                      'case "check-syntax" 'ui "stock" 'fatal_check_handler #t
                      'handler_thread_verified #t 'getter "existing-module-namespace/lexical-get-docs-im"
                      'source_pins_unchanged #t)
          'editor (hash 'source text-before 'characters 54 'selection selection-before
                        'source_unchanged #t 'filename_unchanged #t 'modified_state_unchanged #t
                        'definitions_identity_unchanged #t 'canvas_identity_unchanged #t
                        'canvas_editor_identity_unchanged #t 'tab_identity_unchanged #t
                        'docs_map_identity_unchanged #t 'intervals_unchanged #t)
          'interval_count (length intervals) 'intervals intervals
          'plus (hash 'position 36 'source_end 37 'stored_end 38 'interval_index plus-index
                      'definition_tag (encode plus-tag) 'path plus-path-encoded 'url_anchor (encode plus-anchor)
                      'query_bounds (list plus-start plus-end) 'at_37 (encode at-37) 'at_38 (encode at-38))))
  (call-with-output-file output #:exists 'error
    (lambda (out) (write-json report out) (newline out)))
  (set! capture-written? #t)
  (printf "OPENRACKET_INTERVAL_DOCS_MAP ~a\n"
          (jsexpr->string (hash 'completed #t 'mode mode 'interval_count (length intervals))))
  (flush-output)
  (void))
