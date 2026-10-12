#lang racket/base
;; Native-unrun. The .dep format below is pinned to the reviewed 9.3 writer.
(require racket/file racket/list racket/path json compiler/compilation-path
         setup/collects syntax/modresolve (only-in file/sha1 sha1) "common.rkt")
(provide make-receipter receipt-one! receipt-resolved! receipt-result module-base
         assert-products-current! receipt-generation receipt-known?)
(struct receipter (modules external primitives active runtime-paths expansion-namespace generation) #:transparent)
(define (make-receipter)
  (receipter (make-hash) (make-hash) (make-hash) (make-hash) (make-hash)
             (make-base-empty-namespace) (box 0)))
(define (receipt-generation r) (unbox (receipter-generation r)))
(define (receipt-known? r p)
  (hash-has-key? (receipter-modules r) (path->string (physical p))))
(define (module-base m)
  (cond [(and (pair? m) (eq? (car m) 'submod)) (cadr m)]
        [(and (pair? m) (or (path? (car m)) (symbol? (car m)))) (car m)]
        [else m]))
(define (source-path p)
  (cond [(file-exists? p) p]
        [(and (regexp-match? #rx"[.]rkt$" (path->string p))
              (file-exists? (path-replace-extension p #".ss")))
         (path-replace-extension p #".ss")]
        [else (fail "Required module source is missing: ~a" p)]))
(define (products-for nominal actual)
  (define possibilities
    (remove-duplicates
     (for/list ([p (in-list (list nominal actual))])
       (get-compilation-bytecode-file p #:modes (list (string->path "compiled"))
                                     #:roots (list K))) equal?))
  (define usable
    (filter (lambda (zo) (and (file-exists? zo)
                              (file-exists? (path-replace-extension zo #".dep")))) possibilities))
  (unless (= (length usable) 1)
    (fail "Missing or ambiguous .zo/.dep pair for ~a: ~e" nominal usable))
  (define zo (inside-file! (car usable) (list K)))
  (values zo (inside-file! (path-replace-extension zo #".dep") (list K))))
(define (assert-products-current! source zo)
  (when (> (file-or-directory-modify-seconds source)
           (file-or-directory-modify-seconds zo))
    (fail "Source is newer than rebuilt bytecode; source fallback is forbidden: ~a" source)))
(define (decode-dependency d)
  (define indirect? (and (pair? d) (eq? (car d) 'indirect)))
  (define first (if indirect? (cdr d) d))
  (define external? (and (pair? first) (eq? (car first) 'ext)))
  (define encoded (if external? (cdr first) first))
  (define p
    (cond [(bytes? encoded) (bytes->path encoded)]
          [(and (list? encoded) (>= (length encoded) 3)
                (eq? (car encoded) 'collects) (andmap bytes? (cdr encoded)))
           (collects-relative->path encoded)]
          [else (fail "Unknown .dep dependency encoding: ~e" d)]))
  (unless (and (path? p) (complete-path? p))
    (fail "Dependency did not resolve to a complete path: ~e" d))
  (values p external? indirect?))
(define (receipt-resolved! r resolved reason)
  (define root (module-base resolved))
  (cond [(path? root) (receipt-one! r root reason)]
        [(symbol? root)
         (define name (make-resolved-module-path root))
         (unless (module-predefined? name)
           (fail "A non-file static dependency is not a predefined VM module: ~s" root))
         (hash-set! (receipter-primitives r) root
                    (hasheq 'name (symbol->string root) 'classification "predefined-vm-module"
                            'module_predefined #t))]
        [else (fail "Unrecognized resolved module identity: ~e" resolved)]))
;; This is the public-API expansion-time visitation pattern used by the pinned
;; official compiler/embed. It declares compiled code and visits compile-time
;; portions; it does not instantiate the inspected module at runtime.
(define (runtime-module-paths! r code source)
  (unless (module-compiled-cross-phase-persistent? code)
    (define name (module-compiled-name code))
    (define module-path (if (pair? name) `(submod ,source ,@(cdr name)) source))
    (define specs
      (parameterize ([current-namespace (receipter-expansion-namespace r)]
                     [current-security-guard (make-read-only-guard)]
                     [use-compiled-file-paths (list (string->path "compiled"))]
                     [current-compiled-file-roots (list K)])
        (unless (module-declared? module-path #f)
          ;; Top-level code contains its submodules; it is declared first by the
          ;; caller, so the eval branch is used only for a top-level module.
          (parameterize ([current-module-declare-name
                          (module-path-index-resolve (module-path-index-join module-path #f))])
            (eval code)))
        (define expanded
          (expand `(,#'module runtime-path-receipt racket/kernel
                              (#%require (only ,module-path) racket/runtime-path)
                              (runtime-paths ,module-path))))
        (syntax-case expanded (quote)
          [(_ name language (#%mb requires (quote (spec ...))))
           (syntax->datum #'(spec ...))]
          [_ (fail "Unexpected public runtime-paths expansion for ~a" module-path)])))
    (define records
      (for/list ([spec (in-list specs)])
        (cond
          [(and (list? spec) (= (length spec) 3) (eq? (car spec) 'module))
           ;; The third element is the registration variable-reference. Do not
           ;; retain it or serialize it. The module path alone resolves relative
           ;; to the visited module exactly as in compiler/embed.
           (define target (cadr spec))
           (unless (module-path? target) (fail "Malformed registered runtime module path"))
           (define resolved (resolve-module-path target module-path))
           (receipt-resolved! r resolved "registered-runtime-module-path")
           (hasheq 'kind "module" 'module (datum-json target) 'resolved (datum-json resolved))]
          [else
           ;; Ordinary runtime file/resource paths are data, even with a .rkt
           ;; suffix. No extension-based promotion to a module is permitted.
           (hasheq 'kind "data" 'spec (datum-json spec))])))
    (hash-set! (receipter-runtime-paths r) (format "~s" module-path)
               (hasheq 'module (datum-json module-path) 'paths records))))
(define (compiled-imports! r code source)
  (unless (compiled-module-expression? code) (fail "Not a compiled module: ~a" source))
  (for* ([phase+imports (in-list (module-compiled-imports code))]
         [mpi (in-list (cdr phase+imports))])
    (receipt-resolved! r (resolve-module-path-index mpi source) "compiled-import"))
  (runtime-module-paths! r code source)
  (for ([sub (in-list (append (module-compiled-submodules code #t)
                              (module-compiled-submodules code #f)))])
    (compiled-imports! r sub source)))
(define (receipt-one! r input reason)
  (define nominal (physical input))
  (define source (inside-file! (source-path nominal) source-roots))
  (define key (path->string nominal))
  (unless (or (hash-has-key? (receipter-modules r) key)
              (hash-has-key? (receipter-active r) key))
    (hash-set! (receipter-active r) key #t)
    (define-values (zo dep) (products-for nominal source))
    (assert-products-current! source zo)
    (define raw (read-datum dep))
    (unless (and (list? raw) (>= (length raw) 3) (equal? (car raw) (version))
                 (pair? (caddr raw)) (string? (car (caddr raw))))
      (fail "Unknown or stale .dep header for ~a" source))
    (unless (equal? (cadr raw) (current-compile-target-machine))
      (fail "Dependency target machine is not this process's native compilation target: ~a" source))
    (define source-sha1 (call-with-input-file source sha1))
    (unless (equal? source-sha1 (car (caddr raw)))
      (fail ".dep source hash does not match actual source: ~a" source))
    (define edges
      (for/list ([d (in-list (cdddr raw))])
        (define-values (p external? indirect?) (decode-dependency d))
        (define actual (inside-file! (if external? p (source-path p)) source-roots))
        (if external?
            (hash-set! (receipter-external r) (path->string actual) (file-record actual))
            (receipt-one! r p "recorded-dependency"))
        (hasheq 'path (path->string actual) 'external external? 'indirect indirect?)))
    ;; Reading a .zo does not instantiate or compile it. This records VM imports
    ;; absent from .dep and checks static imports of all compiled submodules.
    (define code
      (parameterize ([read-accept-compiled #t])
        (call-with-input-file zo read)))
    (compiled-imports! r code source)
    (hash-set! (receipter-modules r) key
               (hasheq 'nominal_path key 'source (file-record source)
                       'bytecode (file-record zo) 'dependency (file-record dep)
                       'dep_source_sha1 source-sha1 'target_machine (datum-json (cadr raw))
                       'reason reason 'dependencies edges))
    (hash-remove! (receipter-active r) key)
    (set-box! (receipter-generation r) (add1 (receipt-generation r)))))
(define (sorted-values h)
  (for/list ([k (in-list (sort (hash-keys h) string<? #:key (lambda (v) (format "~a" v))))])
    (hash-ref h k)))
(define (receipt-result r)
  (hasheq 'modules (sorted-values (receipter-modules r))
          'external_files (sorted-values (receipter-external r))
          'primitives (sorted-values (receipter-primitives r))
          'runtime_paths (sorted-values (receipter-runtime-paths r))))
