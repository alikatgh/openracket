#lang racket/base
;; Verify the GUI's existing dependency, never create an instance for evidence.
;; module->namespace: https://docs.racket-lang.org/reference/Namespaces.html
;; module->imports / dynamic-require (missing-export thunk only):
;; https://docs.racket-lang.org/reference/Module_Names_and_Loading.html
(require racket/file racket/path syntax/modresolve
         (only-in "gui-observer.rkt" digest))
(provide gui-activation-evidence)
(define activation-export 'openracket-interval-map-fast-set-enabled?)
(define flag-name "OPENRACKET_INTERVAL_MAP_FAST_SET")
(define (sha256? value)
  (and (string? value) (regexp-match? #px"^[0-9a-f]{64}$" value)))
(define (bounded-source source)
  (unless (and (path? source) (complete-path? source)
               (not (link-exists? source)) (file-exists? source)
               (<= (file-size source) (* 1024 1024)))
    (error 'activation "Resolved interval-map source is missing, linked or unbounded"))
  (define name (path->string source))
  (when (> (string-length name) 2048)
    (error 'activation "Resolved interval-map source path exceeds bound"))
  (define data (call-with-input-file source (lambda (in) (read-bytes (add1 (* 1024 1024)) in))))
  (when (or (eof-object? data) (> (bytes-length data) (* 1024 1024)))
    (error 'activation "Resolved interval-map source changed beyond bound"))
  (values name (digest data)))

(define (existing-import-evidence gui-module dependency arm expected-sha)
  (unless (and (member arm '("stock" "candidate")) (sha256? expected-sha))
    (error 'activation "Arm or independent expected source SHA256 is invalid"))
  ;; This must succeed BEFORE any dependency export lookup. An absent GUI module,
  ;; namespace/inspector error, load error or wrong phase propagates unchanged.
  (define gui-namespace (module->namespace gui-module))
  (unless (= (namespace-base-phase gui-namespace) 0)
    (error 'activation "GUI namespace is not at phase zero"))
  (parameterize ([current-namespace gui-namespace])
    ;; resolve-module-path does not load/instantiate. Check the GUI module's
    ;; actual phase-zero import indexes, not an unrelated worker/place registry.
    (define selected-source (resolve-module-path dependency #f))
    (define imports
      (for*/list ([entry (in-list (module->imports gui-module))]
                  #:when (equal? (car entry) 0)
                  [index (in-list (cdr entry))]
                  #:when (equal? (resolved-module-path-name
                                  (module-path-index-resolve index #f)) selected-source))
        (module-path-index-resolve index #f)))
    (unless (= (length imports) 1)
      (error 'activation "GUI must have exactly one matching phase-zero interval-map import"))
    (define actual-module (car imports))
    (define actual-namespace (module->namespace actual-module))
    (unless (= (namespace-base-phase actual-namespace) 0)
      (error 'activation "Actual interval-map module is not instantiated at phase zero"))
    (define missing (gensym 'missing-export))
    (define exported
      (dynamic-require actual-module activation-export (lambda () missing)
                       (lambda () (error 'activation "Activation export is syntax, not a boolean value"))))
    ;; There is deliberately no exception handler that maps errors to 'missing'.
    (define export-status (cond [(eq? exported missing) "missing"]
                                [(boolean? exported) "boolean"] [else "non-boolean"]))
    (define-values (source-name source-sha)
      (bounded-source (resolved-module-path-name actual-module)))
    (define flag (getenv flag-name))
    (define phase-flag (getenv "OPENRACKET_GUI_PHASE_POINTS"))
    (define verified
      (and (equal? expected-sha source-sha) (not phase-flag)
           (if (equal? arm "candidate")
               (and (equal? flag "1") (eq? exported #t))
               (and (not flag) (eq? exported missing))) #t))
    (hasheq 'schema_version 1 'kind "gui_interval_map_activation" 'arm arm
            'gui_module "drracket/private/syncheck/gui"
            'gui_module_already_instantiated #t 'gui_namespace_base_phase 0
            'gui_phase0_import_verified #t 'interval_map_module "data/interval-map"
            'interval_map_already_instantiated #t
            'source source-name 'source_sha256 source-sha 'expected_source_sha256 expected-sha
            'flag_name flag-name 'flag_value (or flag 'null)
            'activation_export (symbol->string activation-export)
            'export_status export-status 'fast_set_enabled (if (boolean? exported) exported 'null)
            'phase_points_enabled (and phase-flag #t) 'verified verified)))

(define (gui-activation-evidence arm expected-sha)
  (existing-import-evidence 'drracket/private/syncheck/gui 'data/interval-map arm expected-sha))

;; Synthetic fixture modules are permitted only via an explicit test submodule;
;; the production entry point has no dependency/module/namespace override.
(module+ test-support (provide existing-import-evidence))
