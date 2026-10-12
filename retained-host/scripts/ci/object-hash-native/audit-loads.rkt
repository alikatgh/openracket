#lang racket/base
;; Preload with -t before each frozen target. No command arguments consumed and
;; no OPENRACKET_ variable added. This observes one place and inheriting threads.
;; Recursive reflection/expansion belongs solely to standalone prebuild receipts.
(require racket/file racket/list racket/path json setup/dirs "common.rkt")
(define original-resolver (current-module-name-resolver))
(define original-compiled-loader (current-load/use-compiled))
(define original-loader (current-load))
(define original-exit-handler (exit-handler))
(define initial-collections (current-library-collection-paths))
(define initial-links (datum-json (current-library-collection-links)))
(define (effective-executable)
  (physical (or (find-executable-path (find-system-path 'exec-file))
                (find-system-path 'exec-file))))
(define initial-executable (effective-executable))
(define declared-here (make-hash))
(define verified-roots (make-hash))
(define gate-lock (make-semaphore 1))
;; All audit writers share this distinct lock. A graph check can hold gate-lock
;; while primitive/declaration/rejection records run on other inheriting threads.
(define output-lock (make-semaphore 1))
(define (record! event payload)
  (call-with-semaphore
   output-lock
   (lambda ()
     (display "OBJECT_HASH_LOAD_AUDIT ")
     (emit (hasheq 'schema "object-hash-load-audit/v1" 'event event 'data payload)))))
(define (fatal e)
  (record! "rejected" (hasheq 'message (exn-message e)))
  ;; Auditing failure must not become a plugin warning that the host swallows.
  (original-exit-handler 96)
  (error 'object-hash-audit "Exit handler returned after audit rejection"))
(define (module-base m)
  (cond [(and (pair? m) (eq? (car m) 'submod)) (cadr m)]
        [(and (pair? m) (or (path? (car m)) (symbol? (car m)))) (car m)]
        [else m]))
(define (sha256-string? s)
  (and (string? s) (= (string-length s) 64)
       (regexp-match? #rx"^[0-9a-f]+$" s)))
;; Native predicate assertions run inside the existing guard initialization.
;; Their inclusion is not a claim that they have run in this source-only review.
(define (check-sha256-predicate!)
  (define cases
    (list (list "positive-64-hex" (string-append "0123456789abcdef" "0123456789abcdef"
                                               "0123456789abcdef" "0123456789abcdef") #t)
          (list "literal-braces" "a{64}" #f)
          (list "short" (make-string 63 #\a) #f)
          (list "long" (make-string 65 #\a) #f)
          (list "nonhex" (string-append (make-string 63 #\a) "g") #f)
          (list "uppercase" (make-string 64 #\A) #f)
          (list "nonstring" #f #f)))
  (for ([sample (in-list cases)])
    (unless (eq? (sha256-string? (cadr sample)) (caddr sample))
      (fail "SHA-256 predicate self-check failed: ~a" (car sample)))))
(define (configuration!)
  ;; Validate inherited loader parameters on every callback. Environment is
  ;; verified once before installation: setup/getinfo legitimately parameterizes
  ;; a pruned environment while visiting complex info metadata.
  (unless (and (equal? (current-compiled-file-roots) (list K))
               (equal? (use-compiled-file-paths) (list (string->path "compiled")))
               (not (use-user-specific-search-paths))
               (equal? (physical (find-collects-dir)) (physical (build-path C "collects")))
               (equal? (physical (find-config-dir)) (physical (build-path C "etc")))
               (directory-exists? (find-collects-dir))
               (directory-exists? (find-config-dir))
               (equal? (effective-executable) initial-executable)
               (file-exists? initial-executable)
               (inside? initial-executable C)
               (equal? initial-collections (current-library-collection-paths))
               (equal? initial-links (datum-json (current-library-collection-links))))
    (fail "Loader/search parameters changed during the audited process")))
(define prebuild-path (build-path W "prebuild-receipts.json"))
(define expected-receipt-sha256 (getenv "OBJECT_HASH_PREBUILD_RECEIPT_SHA256"))
(define (canonical-file-field row key roots)
  (define field (hash-ref row key))
  (unless (hash? field) (fail "Malformed prebuild ~a record" key))
  (define text (hash-ref field 'path))
  (unless (and (string? text) (complete-path? text)
               (equal? text (path->string (physical text)))
               (for/or ([root (in-list roots)]) (inside? text root)))
    (fail "Prebuild ~a path is noncanonical or outside the approved roots" key))
  (unless (and (sha256-string? (hash-ref field 'sha256))
               (exact-nonnegative-integer? (hash-ref field 'size)))
    (fail "Malformed prebuild ~a hash/size" key))
  field)
(define-values (known-modules known-bytecode prebuild-module-count)
  (with-handlers ([exn:fail? fatal])
    (check-sha256-predicate!)
    (assert-layout!)
    (void (profile-root))
    (unless (and (sha256-string? expected-receipt-sha256)
                 (file-exists? prebuild-path) (not (link-exists? prebuild-path)))
      (fail "A regular prebuild receipt and explicit expected SHA-256 are required"))
    (define raw (file->bytes prebuild-path))
    (unless (equal? (hex (sha256-bytes raw)) expected-receipt-sha256)
      (fail "Prebuild receipt raw SHA-256 mismatch"))
    (define in (open-input-bytes raw))
    (define receipt (read-json in))
    (unless (eof-object? (read-json in)) (fail "Trailing data in prebuild receipt"))
    (unless (and (hash? receipt)
                 (equal? (hash-ref receipt 'schema) "object-hash-rebuild-receipts/v1")
                 (equal? (hash-ref receipt 'mode) "full")
                 (equal? (hash-ref receipt 'runtime_root) (path->string C))
                 (equal? (hash-ref receipt 'probe_root) (path->string Q))
                 (equal? (hash-ref receipt 'helper_root) (path->string H))
                 (equal? (hash-ref receipt 'compiled_root) (path->string K))
                 (eq? (hash-ref receipt 'registered_and_static_closure_complete) #t))
      (fail "Prebuild receipt schema, mode, roots or known-closure gate differs"))
    (unless (for/and ([flag (in-list '(live_registry_observed online_handler_registry_complete
                                     child_place_dynamic_audit_complete arbitrary_dynamic_graph_proven))])
              (eq? (hash-ref receipt flag) #f))
      (fail "Prebuild receipt coverage flags are missing or differ from the accepted scope"))
    (define rows (hash-ref receipt 'modules))
    (unless (and (list? rows) (pair? rows)) (fail "Prebuild module inventory is empty or malformed"))
    (define by-source (make-hash))
    (define by-bytecode (make-hash))
    (define nominal-seen (make-hash))
    (define (add-consistent! table path row)
      (define old (hash-ref table path #f))
      (when (and old
                 (not (for/and ([key (in-list '(source bytecode dependency))])
                        (equal? (hash-ref old key) (hash-ref row key)))))
        (fail "Ambiguous prebuild module/product mapping: ~a" path))
      (hash-set! table path row))
    (for ([row (in-list rows)])
      (unless (hash? row) (fail "Malformed prebuild module record"))
      (define nominal (hash-ref row 'nominal_path))
      (unless (and (string? nominal) (complete-path? nominal)
                   (equal? nominal (path->string (physical nominal)))
                   (for/or ([root (in-list source-roots)]) (inside? nominal root))
                   (not (hash-has-key? nominal-seen nominal)))
        (fail "Missing, duplicate or outside-root prebuild nominal module"))
      (hash-set! nominal-seen nominal #t)
      (define source (canonical-file-field row 'source source-roots))
      (define bytecode (canonical-file-field row 'bytecode (list K)))
      (define dependency (canonical-file-field row 'dependency (list K)))
      (unless (and (regexp-match? #rx"[.]zo$" (hash-ref bytecode 'path))
                   (equal? (path->string (path-replace-extension (hash-ref bytecode 'path) #".dep"))
                           (hash-ref dependency 'path)))
        (fail "Prebuild bytecode/dependency pair is malformed"))
      (add-consistent! by-source nominal row)
      (add-consistent! by-source (hash-ref source 'path) row)
      (add-consistent! by-bytecode (hash-ref bytecode 'path) row))
    ;; The per-process maps are immutable. Python owns the pre/post execution
    ;; file witnesses; these checks are not a hostile-concurrency security guard.
    (values (make-immutable-hash (hash->list by-source))
            (make-immutable-hash (hash->list by-bytecode))
            (length rows))))
(define (verify-file! field)
  (define path (hash-ref field 'path))
  (unless (and (file-exists? path)
               (= (file-size path) (hash-ref field 'size))
               (equal? (digest path) (hash-ref field 'sha256)))
    (fail "Actual source/bytecode/dependency differs from prebuild receipt: ~a" path)))
(define (check-file! p)
  (with-handlers ([exn:fail? fatal])
    (configuration!)
    (define key (path->string (physical p)))
    (define row (hash-ref known-modules key #f))
    (unless row (fail "Unknown runtime module outside the accepted prebuild closure: ~a" p))
    (call-with-semaphore
     gate-lock
     (lambda ()
       ;; A known, already verified root does not copy or traverse the graph.
       (define identity (hash-ref (hash-ref row 'source) 'path))
       (unless (hash-has-key? verified-roots identity)
         (for ([field (in-list '(source bytecode dependency))])
           (verify-file! (hash-ref row field)))
         (when (> (file-or-directory-modify-seconds (hash-ref (hash-ref row 'source) 'path))
                  (file-or-directory-modify-seconds (hash-ref (hash-ref row 'bytecode) 'path)))
           (fail "Source newer than accepted bytecode; source fallback is forbidden"))
         (hash-set! verified-roots identity #t)
         ;; The full closure is retained losslessly once in the hashed receipt.
         ;; Actual-load events carry only verified file facts and that reference.
         (record! "modules"
                  (hasheq 'nominal_path (hash-ref row 'nominal_path)
                          'source (hash-ref row 'source)
                          'bytecode (hash-ref row 'bytecode)
                          'dependency (hash-ref row 'dependency)
                          'prebuild_receipt_sha256 expected-receipt-sha256)))))))
(define (check-symbol! name)
  (define base (module-base name))
  (cond [(module-predefined? (make-resolved-module-path base))
         (record! "primitive" (hasheq 'name (symbol->string base)
                                      'classification "predefined-vm-module"))]
        [(hash-has-key? declared-here name)
         (record! "evaluated-module" (hasheq 'name (datum-json name)
                                             'classification "declaration-observed-in-this-process"))]
        [else (fail "Unclassified symbolic module load: ~e" name)]))
;; Validate the guard itself against the accepted receipt before installing it.
(check-file! (build-path H "audit-loads.rkt"))
(current-module-name-resolver
 (case-lambda
   [(name from-namespace)
    (unless from-namespace (hash-set! declared-here (resolved-module-path-name name) #t))
    (original-resolver name from-namespace)]
   [(module relative syntax load?)
    (define resolved (original-resolver module relative syntax #f))
    (when load?
      (with-handlers ([exn:fail? fatal])
        (configuration!)
        (define name (resolved-module-path-name resolved))
        (define base (module-base name))
        (cond [(path? base)
               (cond [(hash-has-key? known-modules (path->string (physical base))) (check-file! base)]
                     [(hash-has-key? declared-here name)
                      ;; Evaluated user programs may carry file-shaped module
                      ;; names without requesting any file-backed module load.
                      (record! "evaluated-module"
                               (hasheq 'name (datum-json name) 'file_backed_load #f
                                       'classification "declaration-observed-in-this-process"))]
                     [else (fail "Unknown runtime module outside the accepted prebuild closure: ~a" base)])]
              [(symbol? base) (check-symbol! name)]
              [else (fail "Unknown resolved module kind")])))
    (original-resolver module relative syntax load?)]))
(current-load/use-compiled
 (lambda (path expected)
   (check-file! path)
   (original-compiled-loader path expected)))
(current-load
 (lambda (path expected)
   (when expected
     (with-handlers ([exn:fail? fatal])
       (configuration!)
       (define selected (path->string (physical path)))
       (define row (hash-ref known-bytecode selected #f))
       (unless row
         (fail "A required runtime module selected unknown bytecode or source fallback: ~a" path))
       (check-file! (hash-ref row 'nominal_path))
       ;; Recheck every selected bytecode load, including roots already seen.
       (unless (equal? (digest selected) (hash-ref (hash-ref row 'bytecode) 'sha256))
         (fail "Selected bytecode changed after its prebuild receipt: ~a" selected))))
   (original-loader path expected)))
(record! "installed"
         (hasheq 'compiled_root (path->string K)
                 'source_roots (map path->string source-roots)
                 'prebuild_receipt (path->string prebuild-path)
                 'prebuild_receipt_sha256 expected-receipt-sha256
                 'prebuild_module_count prebuild-module-count
                 'scope "initial-place-and-inheriting-threads"
                 'live_registry_observed #f
                 'online_handler_registry_complete #f
                 'arbitrary_dynamic_graph_proven #f
                 'child_place_dynamic_audit_complete #f
                 'arguments_unchanged (vector->list (current-command-line-arguments))))
