#lang racket/base
;; Run with exactly one argument: core or full. No module is instantiated for
;; tool discovery: public setup/getinfo reads the rebuilt registration metadata.
(require racket/file racket/list racket/path json syntax/modresolve setup/getinfo
         "common.rkt" "receipt-lib.rkt")
(install-read-only-guard!)
(assert-layout! #:source-only? (null? (use-compiled-file-paths)))
(define args (current-command-line-arguments))
(unless (and (= (vector-length args) 1) (member (vector-ref args 0) '("core" "full")))
  (fail "Expected core or full receipt mode"))
(define full? (equal? (vector-ref args 0) "full"))
(define r (make-receipter))
(define roots null)
(define registrations null)
(define metadata null)
(define (add-module! mod reason [relative #f])
  (define resolved (resolve-module-path mod relative))
  (receipt-resolved! r resolved reason)
  (set! roots (cons (hasheq 'module (datum-json mod) 'resolved (datum-json resolved)
                           'reason reason) roots)))
(add-module! 'racket/private/class-internal "class-first")
(when full?
  (define pin-file (inside-file! (build-path Q "RUNTIME-PINS.json") (list Q)))
  (define pins (call-with-input-file pin-file read-json))
  (define flag (getenv "OPENRACKET_OBJECT_HASH_PROBE"))
  (unless (or (not flag) (equal? flag "0")) (fail "Build receipts require stock unset or diagnostic 0"))
  (for ([(mod expected) (in-hash pins)])
    (define source (inside-file! (resolve-module-path mod #f) (list C)))
    (define expected-hash
      (if (and (eq? mod 'racket/private/class-internal) (not flag))
          "1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f"
          expected))
    (unless (equal? (digest source) expected-hash) (fail "Runtime pin mismatch: ~a" mod))
    (add-module! mod "runtime-pin"))
  (for ([mod (in-list '(racket/class racket/gui/base framework drracket/drracket
                        drracket/private/tools drracket/private/language-configuration
                        drracket/private/module-language drracket/private/module-language-tools
                        drracket/private/expanding-place))])
    (add-module! mod "required-runtime-root"))
  (for ([root (in-list (list (build-path Q "native") (build-path Q "vendor" "host")))]
        [count (in-list '(13 10))])
    (define files
      (sort (for/list ([p (in-directory root)]
                       #:when (and (file-exists? p) (regexp-match? #rx"[.]rkt$" (path->string p)))) p)
            string<? #:key path->string))
    (unless (= count (length files)) (fail "Frozen native/stock-host module count changed: ~a" root))
    (for ([p (in-list files)]) (add-module! p "frozen-probe-module")))
  (for ([p (in-list (sort (directory-list H #:build? #t) string<? #:key path->string))]
        #:when (regexp-match? #rx"[.]rkt$" (path->string p)))
    (add-module! p "ci-helper-module"))
  ;; These dynamic worker seams are independently pinned, not inferred from .dep.
  (define api-evidence (call-with-input-file (build-path H "API-PROVENANCE.json") read-json))
  (for ([pair (in-list '((drracket/private/module-language . "drracket-core-lib/drracket/private/module-language.rkt")
                         (drracket/private/module-language-tools . "drracket-core-lib/drracket/private/module-language-tools.rkt")
                         (drracket/private/expanding-place . "drracket-core-lib/drracket/private/expanding-place.rkt")))])
    (define evidence
      (findf (lambda (row) (equal? (hash-ref row 'path) (cdr pair)))
             (hash-ref api-evidence 'evidence)))
    (unless evidence (fail "Missing worker API provenance: ~a" (car pair)))
    (unless (equal? (digest (resolve-module-path (car pair) #f)) (hash-ref evidence 'sha256))
      (fail "Pinned dynamic worker seam differs: ~a" (car pair))))
  ;; Exact tool field family used by the official v9.3 tool loader.
  (define tool-fields '(drracket-tools drracket-tool-icons drracket-tool-names drracket-tool-urls
                        tools tool-icons tool-names tool-urls))
  (define language-fields '(drscheme-language-positions get-drscheme-language-positions
                            drscheme-language-modules drscheme-language-readers
                            textbook-pls get-textbook-pls))
  (define omission-fields '(compile-omit-paths compile-omit-files compile-include-files
                            assume-virtual-sources))
  (define records (find-relevant-directory-records
                   (append tool-fields language-fields omission-fields) 'preferred))
  (define (registration! dir field spec module)
    (define relative (build-path dir "info.rkt"))
    (add-module! module (format "registration:~a" field) relative)
    (set! registrations
          (cons (hasheq 'directory (path->string dir) 'field (symbol->string field)
                         'spec (datum-json spec) 'module (datum-json module)
                         'resolved (datum-json (resolve-module-path module relative))) registrations)))
  (for ([record (in-list records)])
    (define dir (physical (directory-record-path record)))
    (unless (inside? dir C) (fail "Tool/info registration outside clone: ~a" dir))
    (define info-file (cond [(file-exists? (build-path dir "info.rkt")) (build-path dir "info.rkt")]
                            [(file-exists? (build-path dir "info.ss")) (build-path dir "info.ss")]
                            [else (fail "Rebuilt metadata has no info source: ~a" dir)]))
    (define info (get-info/full dir))
    (unless info (fail "Missing registered info source: ~a" dir))
    (set! metadata
          (cons (hasheq 'source (file-record (inside-file! info-file (list C)))
                         'record_spec (datum-json (directory-record-spec record))
                         'fields (map symbol->string (directory-record-syms record))
                         'omissions (for/hasheq ([field (in-list omission-fields)])
                                      (values field (datum-json (info field (lambda () #f)))))) metadata))
    (for ([field (in-list '(tools drracket-tools))])
      (define specs (info field (lambda () null)))
      (unless (list? specs) (fail "Malformed tool list in ~a" dir))
      (for ([spec (in-list specs)])
        (define pieces
          (cond [(string? spec) (list spec)]
                [(and (list? spec) (pair? spec) (andmap string? spec))
                 (append (cdr spec) (list (car spec)))]
                [else (fail "Malformed tool specification: ~e" spec)]))
        (registration! dir field spec (apply build-path dir pieces))))
    (define modules (info 'drscheme-language-modules (lambda () null)))
    (unless (list? modules) (fail "Malformed language module registrations"))
    (for ([spec (in-list modules)])
      (define mod (cond [(string? spec) (build-path dir spec)]
                        [(and (list? spec) (pair? spec) (andmap string? spec)) (cons 'lib spec)]
                        [else (fail "Malformed language module: ~e" spec)]))
      (registration! dir 'drscheme-language-modules spec mod))
    (define readers (info 'drscheme-language-readers (lambda () null)))
    (unless (list? readers) (fail "Malformed language readers"))
    (for ([spec (in-list readers)] #:when spec)
      (unless (module-path? spec) (fail "Malformed language reader module: ~e" spec))
      (registration! dir 'drscheme-language-readers spec
                     (if (string? spec) (build-path dir spec) spec)))
    (for ([field (in-list '(get-drscheme-language-positions get-textbook-pls))])
      (define spec (info field (lambda () #f)))
      (when spec
        (unless (and (list? spec) (= 2 (length spec)) (module-path? (car spec)) (symbol? (cadr spec)))
          (fail "Malformed indirect language metadata: ~e" spec))
        ;; Inventory the provider without executing its export in this reader.
        (registration! dir field spec (car spec))))))
(define result (receipt-result r))
(emit (hasheq 'schema "object-hash-rebuild-receipts/v1" 'mode (if full? "full" "core")
              'runtime_root (path->string C) 'probe_root (path->string Q)
              'helper_root (path->string H) 'compiled_root (path->string K)
              'required_roots (reverse roots) 'registrations (reverse registrations)
              'metadata (reverse metadata) 'modules (hash-ref result 'modules)
              'external_files (hash-ref result 'external_files)
              'primitives (hash-ref result 'primitives)
              'runtime_paths (hash-ref result 'runtime_paths)
              'worker_roots (if full?
                                (list (hasheq 'module "drracket/private/expanding-place"
                                              'export "start"
                                              'source (path->string
                                                       (resolve-module-path 'drracket/private/expanding-place #f))))
                                null)
              'ordered_online_handler_registry null
              'live_registry_observed #f
              'online_handler_registry_complete #f
              'ordered_online_handler_registry_complete #f
              'registered_and_static_closure_complete #t
              'arbitrary_dynamic_graph_proven #f
              'runtime_audit_scope "initial-place-and-inheriting-threads"
              'child_place_dynamic_audit_complete #f))
