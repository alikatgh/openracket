#lang racket/base
;; Inspect existing GUI-imported style module only. Never instantiate, warm a
;; style cache, attach namespaces, or classify a loader exception as stock.
(require racket/class racket/file racket/path syntax/modresolve
         (only-in "gui-observer.rkt" digest))
(provide gui-activation-evidence unexpected-experiment-flags existing-style-state-reader)
(define activation-export 'openracket-named-style-index-enabled?)
(define state-export 'openracket-named-style-index-state)
(define flag-name "OPENRACKET_NAMED_STYLE_INDEX")
(define allowed-openracket-flags
  '("OPENRACKET_GUI_OBSERVER" "OPENRACKET_GUI_OBSERVER_SUPPORT"
    "OPENRACKET_GUI_PHASE_SUPPORT" "OPENRACKET_GUI_OBSERVER_OUTPUT"
    "OPENRACKET_GUI_EXPECTED_SHA256" "OPENRACKET_GUI_EXPECTED_SOURCE"
    "OPENRACKET_GUI_EXPECTED_CHARACTERS" "OPENRACKET_CAPTURE_CONFIG"
    "OPENRACKET_NAMED_STYLE_INDEX"))
(define (unexpected-experiment-flags)
  (sort
   (for/list ([key (in-list (environment-variables-names (current-environment-variables)))]
              #:when (regexp-match? #rx#"^OPENRACKET_" key)
              #:unless (member (bytes->string/utf-8 key) allowed-openracket-flags))
     (bytes->string/utf-8 key)) string<?))
(define (sha256? value)
  (and (string? value) (regexp-match? #px"^[0-9a-f]{64}$" value)))
(define (existing-module module)
  (define actual (make-resolved-module-path (resolve-module-path module #f)))
  (define namespace (module->namespace actual))
  (unless (= (namespace-base-phase namespace) 0)
    (error 'activation "Existing module namespace is not at phase zero"))
  actual)
(define (bounded-source actual expected-source root)
  (define source (resolved-module-path-name actual))
  (unless (and (path? source) (complete-path? source)
               (not (link-exists? source)) (file-exists? source)
               (<= (file-size source) (* 1024 1024))
               (equal? (simplify-path source) (simplify-path expected-source))
               (let ([relative (find-relative-path (simplify-path root) (simplify-path source))])
                 (and (relative-path? relative) (not (memq 'up (explode-path relative))))))
    (error 'activation "Resolved module source is missing, linked, foreign or unbounded"))
  (define name (path->string source))
  (when (> (string-length name) 2048)
    (error 'activation "Resolved module source path exceeds bound"))
  (define data (call-with-input-file source (lambda (in) (read-bytes (add1 (* 1024 1024)) in))))
  (when (or (eof-object? data) (> (bytes-length data) (* 1024 1024)))
    (error 'activation "Resolved source changed beyond bound"))
  (values name (digest data)))
(define (existing-module-evidence gui-module style-module actual-style-list arm expected-sha expected-source root)
  (unless (and (member arm '("stock" "candidate")) (sha256? expected-sha))
    (error 'activation "Arm or independent expected style source SHA256 is invalid"))
  ;; Both must already exist BEFORE any dynamic-require below.
  (define actual-gui (existing-module gui-module))
  (define actual-style (existing-module style-module))
  (define gui-style-class (dynamic-require actual-gui 'style-list%))
  (define style-class (dynamic-require actual-style 'style-list%))
  (unless (and (is-a? actual-style-list style-class) (is-a? actual-style-list gui-style-class))
    (error 'activation "Actual definitions style list is not the same GUI-imported style class"))
  (define missing (gensym 'missing-export))
  (define exported
    (dynamic-require actual-style activation-export (lambda () missing)
                     (lambda () (error 'activation "Activation export is syntax, not a boolean value"))))
  (define reader
    (dynamic-require actual-style state-export (lambda () missing)
                     (lambda () (error 'activation "State export is syntax, not a procedure"))))
  (define export-status (cond [(eq? exported missing) "missing"]
                              [(boolean? exported) "boolean"] [else "non-boolean"]))
  (define reader-status (cond [(eq? reader missing) "missing"]
                              [(and (procedure? reader) (procedure-arity-includes? reader 1)) "procedure"]
                              [else "invalid"]))
  (define-values (source-name source-sha) (bounded-source actual-style expected-source root))
  (define flag (getenv flag-name))
  (define phase-flag (getenv "OPENRACKET_GUI_PHASE_POINTS"))
  (define unexpected-flags (unexpected-experiment-flags))
  (define verified
    (and (equal? expected-sha source-sha) (not phase-flag) (null? unexpected-flags)
         (if (equal? arm "candidate")
             (and (equal? flag "1") (eq? exported #t) (equal? reader-status "procedure"))
             (and (not flag) (eq? exported missing) (eq? reader missing))) #t))
  (hasheq 'schema_version 1 'kind "gui_named_style_index_activation" 'arm arm
          'gui_module "racket/gui/base" 'style_module "racket/snip/private/style"
          'gui_module_already_instantiated #t 'style_module_already_instantiated #t
          'gui_namespace_base_phase 0 'style_namespace_base_phase 0
          'same_gui_imported_style_instance #t 'actual_editor_style_list #t
          'source source-name 'source_sha256 source-sha 'expected_source_sha256 expected-sha
          'runtime_root (path->string root) 'flag_name flag-name 'flag_value (or flag 'null)
          'activation_export (symbol->string activation-export) 'state_export (symbol->string state-export)
          'state_export_status reader-status 'export_status export-status
          'named_style_index_enabled (if (boolean? exported) exported 'null)
          'unexpected_experiment_flags unexpected-flags 'phase_points_enabled (and phase-flag #t)
          'verified verified))
(define (gui-activation-evidence actual-style-list arm expected-sha expected-source root
                                 expected-gui-sha expected-gui-source)
  (define actual-syncheck (existing-module 'drracket/private/syncheck/gui))
  (define-values (gui-source gui-sha)
    (bounded-source actual-syncheck expected-gui-source root))
  (unless (and (sha256? expected-gui-sha) (equal? gui-sha expected-gui-sha))
    (error 'activation "Actual existing annotation GUI module differs from common observed source"))
  (hash-set* (existing-module-evidence 'racket/gui/base 'racket/snip/private/style actual-style-list
                                        arm expected-sha expected-source root)
             'syncheck_module_already_instantiated #t
             'syncheck_source gui-source 'syncheck_source_sha256 gui-sha))
(define (existing-style-state-reader arm)
  (define actual (existing-module 'racket/snip/private/style))
  (define missing (gensym 'missing-export))
  (define reader (dynamic-require actual state-export (lambda () missing)))
  (cond [(equal? arm "stock")
         (unless (eq? reader missing) (error 'activation "Unexpected stock style-state export")) #f]
        [(and (equal? arm "candidate") (procedure? reader) (procedure-arity-includes? reader 1)) reader]
        [else (error 'activation "Missing or invalid candidate style-state reader")]))
(module+ test-support (provide existing-module-evidence))
