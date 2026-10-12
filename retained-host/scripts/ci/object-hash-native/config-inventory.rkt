#lang racket/base
;; Run only with -c -I racket/base after the arm's exact -X/-G/-A/-U/-R prefix.
(require racket/file racket/list racket/path setup/dirs setup/link "common.rkt")
(install-read-only-guard!)
(assert-layout! #:source-only? #t)
(define P (profile-root))
(define actual-class-source
  (physical (collection-file-path "class-internal.rkt" "racket" "private")))
(unless (equal? actual-class-source
                (physical (build-path C "collects" "racket" "private" "class-internal.rkt")))
  (fail "Effective collection links redirect the core class source"))
(define paths null)
(define (record! label role p)
  (when p
    (unless (path-string? p) (fail "Non-path in ~a: ~e" label p))
    (define raw (path->complete-path p))
    (define full (physical raw))
    (set! paths (cons (hasheq 'label label 'role role 'raw_path (path->string raw)
                            'path (path->string full)
                            'exists (or (file-exists? full) (directory-exists? full))
                            'file (file-exists? full) 'directory (directory-exists? full)) paths))))
(define (record-value! label role v)
  (cond [(not v) (void)]
        [(list? v) (for ([p (in-list v)]) (record! label role p))]
        [else (record! label role v)]))
;; Only public setup/dirs APIs. No private config parameter is imported.
(define directory-apis
  '((source find-collects-dir get-main-collects-search-dirs find-user-collects-dir
            get-collects-search-dirs find-pkgs-dir get-pkgs-search-dirs find-user-pkgs-dir)
    (config find-config-dir)
    (link find-links-file get-links-search-files find-user-links-file)
    (metadata get-info-domain-root)
    (library find-lib-dir find-user-lib-dir get-lib-search-dirs get-cross-lib-search-dirs
             find-dll-dir find-cross-dll-dir get-cross-lib-extra-search-dirs
             find-share-dir find-user-share-dir get-share-search-dirs get-share-extra-search-dirs
             find-include-dir find-user-include-dir get-include-search-dirs)
    (write find-console-bin-dir find-user-console-bin-dir
           find-gui-bin-dir find-user-gui-bin-dir
           get-console-bin-search-dirs get-gui-bin-search-dirs
           get-console-bin-extra-search-dirs get-gui-bin-extra-search-dirs
           find-config-tethered-console-bin-dir find-config-tethered-gui-bin-dir
           find-config-tethered-apps-dir find-addon-tethered-console-bin-dir
           find-addon-tethered-gui-bin-dir find-addon-tethered-apps-dir
           find-apps-dir find-user-apps-dir find-doc-dir find-user-doc-dir
           get-doc-search-dirs get-doc-extra-search-dirs find-man-dir find-user-man-dir
           get-man-search-dirs get-man-extra-search-dirs)))
(for* ([entry (in-list directory-apis)] [api (in-list (cdr entry))])
  (record-value! (symbol->string api) (symbol->string (car entry))
                 ((dynamic-require 'setup/dirs api))))
(for ([s (in-list '(home-dir pref-dir pref-file init-dir init-file addon-dir temp-dir))])
  (record! (format "system:~a" s) "write" (find-system-path s)))
(for ([v (in-list '("HOME" "PLTUSERHOME" "PLTADDONDIR" "TMPDIR"
                   "XDG_CONFIG_HOME" "XDG_CACHE_HOME" "XDG_DATA_HOME"))])
  (define p (getenv v))
  (unless p (fail "Required profile environment is unset: ~a" v))
  (record! (string-append "environment:" v) "write" p))
(record! "compiled-root" "write" K)
(define raw-configs null)
(define unclassified null)
(define path-config-keys
  '(collects-search-dirs lib-dir lib-search-dirs dll-dir share-dir share-search-dirs
    links-file links-search-files pkgs-dir pkgs-search-dirs bin-dir gui-bin-dir
    bin-search-dirs gui-bin-search-dirs apps-dir man-dir man-search-dirs doc-dir
    doc-search-dirs include-dir include-search-dirs info-domain-root
    config-tethered-console-bin-dir config-tethered-gui-bin-dir config-tethered-apps-dir
    addon-tethered-console-bin-dir addon-tethered-gui-bin-dir addon-tethered-apps-dir))
(define scalar-config-keys
  '(installation-name absolute-installation? cgc-suffix 3m-suffix cs-suffix
    doc-search-url doc-open-url build-stamp base-documentation-packages
    distribution-documentation-packages main-language-family default-scope
    download-cache-max-files download-cache-max-bytes trash-max-packages trash-max-seconds))
(define (config-paths! key value base)
  (cond [(not value) (void)]
        [(list? value) (for ([v (in-list value)]) (config-paths! key v base))]
        [(or (path-string? value) (bytes? value))
         (record! (format "config:~a" key) "config"
                  (path->complete-path (if (bytes? value) (bytes->path value) value) base))]
        [else (fail "Unsupported path config ~a: ~e" key value)]))
(for ([cfg (in-list (list (build-path (find-config-dir) "config.rktd")
                          (build-path (find-system-path 'addon-dir) "etc" "config.rktd")))])
  (record! "configuration-file" "config" cfg)
  (define exists? (file-exists? cfg))
  (define table (if exists? (read-datum cfg) (hash)))
  (unless (hash? table) (fail "Configuration is not a hash table: ~a" cfg))
  (for ([(key value) (in-hash table)])
    (cond [(memq key path-config-keys)
           (config-paths! key value
                          (if (regexp-match? #rx"^addon-tethered-" (symbol->string key))
                              (path-only cfg) (find-collects-dir)))]
          [(eq? key 'compiled-file-roots)
           (unless (list? value) (fail "Bad compiled-file-roots config"))
           (for ([root (in-list value)] #:unless (eq? root 'same))
             (define p (cond [(bytes? root) (bytes->path root)]
                             [(path-string? root) root]
                             [else (fail "Unsupported configured compiled root: ~e" root)]))
             (unless (complete-path? p)
               (fail "Relative configured compiled roots need separate reviewed expansion: ~a" p))
             (record! "config:compiled-file-roots" "write" p))]
          [(eq? key 'catalogs)
           (unless (list? value) (fail "Bad catalogs config"))
           (for ([v (in-list value)] #:when v)
             (unless (string? v) (fail "Bad catalog value"))
             (unless (regexp-match? #rx"^[a-zA-Z]+://" v)
               (config-paths! key v (path-only cfg))))]
          [(memq key scalar-config-keys) (void)]
          [else (set! unclassified (cons (hasheq 'key (datum-json key)
                                               'value (datum-json value)
                                               'file (path->string cfg)) unclassified))]))
  (set! raw-configs (cons (hasheq 'path (path->string cfg) 'exists exists?
                                 'datum (datum-json table)) raw-configs)))
(define collection-links
  (for/list ([v (in-list (current-library-collection-links))])
    (cond [(not v) (hasheq 'kind "splice")]
          [(path-string? v) (record! "effective-collection-link-file" "link" v)
                           (hasheq 'kind "file" 'path (path->string (path->complete-path v)))]
          [(hash? v)
           (hasheq 'kind "table" 'entries
                   (for/list ([(name ps) (in-hash v)])
                     (unless (and (or (not name) (symbol? name)) (list? ps))
                       (fail "Unknown effective collection-link table form"))
                     (for ([p (in-list ps)]) (record! "effective-link-table-source" "source" p))
                     (hasheq 'name (and name (symbol->string name))
                             'paths (map (lambda (p) (path->string (path->complete-path p))) ps))))]
          [else (fail "Unknown effective collection-link form: ~e" v)])))
(define link-files
  (remove-duplicates
   (filter values (append (filter path-string? (current-library-collection-links))
                          (get-links-search-files)
                          (list (find-links-file) (find-user-links-file)))) equal?))
(define link-records
  (for/list ([p (in-list link-files)])
    (record! "links-file" "link" p)
    (define ordinary (links #:file p #:with-path? #t))
    (define roots (links #:file p #:root? #t))
    (define raw (if (file-exists? p) (read-datum p) null))
    ;; Retain even version-inactive link targets. Their documented data encoding
    ;; is read directly; the public links API supplies the effective forms above.
    (define all-entries
      (for/list ([entry (in-list raw)])
        (define encoded (cadr entry))
        (define decoded
          (cond [(path-string? encoded) encoded]
                [(bytes? encoded) (bytes->path encoded)]
                [(list? encoded)
                 (apply build-path
                        (for/list ([part (in-list encoded)])
                          (cond [(bytes? part) (bytes->path-element part)]
                                [(memq part '(same up)) part]
                                [else (fail "Unknown encoded link component: ~e" part)])))]
                [else (fail "Unknown encoded link path: ~e" encoded)]))
        (define target (path->complete-path decoded (path-only (path->complete-path p))))
        (record! "all-configured-link-targets" "source" target)
        (hasheq 'kind (if (string? (car entry)) "ordinary" (symbol->string (car entry)))
                'name (if (string? (car entry)) (car entry) #f)
                'path (path->string target)
                'active (or (= 2 (length entry)) (and (regexp-match? (caddr entry) (version)) #t)))))
    (for ([pair (in-list ordinary)]) (record! "ordinary-link-source" "source" (cdr pair)))
    (for ([root (in-list roots)]) (record! "root-or-static-root-link-source" "source" root))
    (hasheq 'path (path->string p) 'exists (file-exists? p)
            'ordinary (for/list ([pair (in-list ordinary)])
                        (hasheq 'name (car pair) 'path (path->string (cdr pair))))
            'roots (map path->string roots)
            'all_entries all-entries 'raw (datum-json raw))))
;; setup/getinfo's documented cache search with info-domain rerooting.
(define (info-reroot p) (if (get-info-domain-root) (reroot-path p (get-info-domain-root)) p))
(for ([root (in-list (remove-duplicates (append (current-library-collection-paths)
                                               (get-main-collects-search-dirs))))])
  (record! "collection-info-domain-cache" "metadata"
           (info-reroot (build-path root "info-domain" "compiled" "cache.rktd"))))
(for ([root (in-list (filter values (list (find-share-dir) (find-user-share-dir))))])
  (record! "share-info-cache" "metadata" (info-reroot (build-path root "info-cache.rktd"))))
(for ([root (in-list (remove-duplicates (append (get-pkgs-search-dirs)
                                               (list (find-pkgs-dir) (find-user-pkgs-dir)))))])
  (when root
    (record! "package-database" "metadata" (build-path root "pkgs.rktd"))
    (record! "package-configuration" "config" (build-path root "config.rktd"))))
(emit (hasheq 'schema "object-hash-config/v1" 'native_run #t
              'runtime_root (path->string C) 'probe_root (path->string Q)
              'helper_root (path->string H) 'compiled_root (path->string K)
              'profile_root (path->string P)
              'resolved_class_source (file-record actual-class-source)
              'collections (map path->string (current-library-collection-paths))
              'compiled_roots (map path->string (current-compiled-file-roots))
              'compiled_subdirs (map path->string (use-compiled-file-paths))
              'collection_links collection-links 'paths (reverse paths)
              'links link-records 'config_files (reverse raw-configs)
              'unclassified_config (reverse unclassified)
              'accepted (null? unclassified)))
(unless (null? unclassified) (fail "Unclassified configuration keys require review"))
