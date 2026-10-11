#lang racket/base
;; Inspect the already-instantiated GUI module at phase zero. No alternate
;; dependency, namespace, instance, load-error fallback, or source rewriting.
(require racket/file racket/path syntax/modresolve
         (only-in "gui-observer.rkt" digest))
(provide gui-activation-evidence)
(define activation-export 'openracket-binding-table-index-enabled?)
(define flag-name "OPENRACKET_BINDING_TABLE_INDEX")
(define (sha256? value)
  (and (string? value) (regexp-match? #px"^[0-9a-f]{64}$" value)))
(define (bounded-source source)
  (unless (and (path? source) (complete-path? source)
               (not (link-exists? source)) (file-exists? source)
               (<= (file-size source) (* 1024 1024)))
    (error 'activation "Resolved GUI source is missing, linked or unbounded"))
  (define name (path->string source))
  (when (> (string-length name) 2048)
    (error 'activation "Resolved GUI source path exceeds bound"))
  (define data (call-with-input-file source (lambda (in) (read-bytes (add1 (* 1024 1024)) in))))
  (when (or (eof-object? data) (> (bytes-length data) (* 1024 1024)))
    (error 'activation "Resolved GUI source changed beyond bound"))
  (values name (digest data)))

(define (existing-module-evidence gui-module arm expected-sha)
  (unless (and (member arm '("stock" "candidate")) (sha256? expected-sha))
    (error 'activation "Arm or independent expected source SHA256 is invalid"))
  ;; Must succeed BEFORE dynamic-require. This is not an import or a fresh
  ;; namespace used to manufacture an apparently activated dependency instance.
  (define actual-module (make-resolved-module-path (resolve-module-path gui-module #f)))
  (define gui-namespace (module->namespace actual-module))
  (unless (= (namespace-base-phase gui-namespace) 0)
    (error 'activation "GUI namespace is not at phase zero"))
  (parameterize ([current-namespace gui-namespace])
    (define missing (gensym 'missing-export))
    (define exported
      (dynamic-require actual-module activation-export (lambda () missing)
                       (lambda () (error 'activation "Activation export is syntax, not a boolean value"))))
    ;; Only the missing-export thunk classifies stock. Every load, namespace,
    ;; source, or inspector exception propagates unchanged.
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
    (hasheq 'schema_version 1 'kind "gui_binding_table_activation" 'arm arm
            'gui_module "drracket/private/syncheck/gui"
            'gui_module_already_instantiated #t 'gui_namespace_base_phase 0
            'same_gui_module_instance #t
            'source source-name 'source_sha256 source-sha 'expected_source_sha256 expected-sha
            'flag_name flag-name 'flag_value (or flag 'null)
            'activation_export (symbol->string activation-export)
            'export_status export-status 'binding_index_enabled (if (boolean? exported) exported 'null)
            'phase_points_enabled (and phase-flag #t) 'verified verified)))

(define (gui-activation-evidence arm expected-sha)
  (existing-module-evidence 'drracket/private/syncheck/gui arm expected-sha))
(module+ test-support (provide existing-module-evidence))
