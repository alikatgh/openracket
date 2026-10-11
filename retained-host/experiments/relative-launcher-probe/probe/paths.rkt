#lang racket/base
;; Core-only path witness. No package install, setup, compilation, or mutations.
(require json racket/file racket/list racket/path setup/dirs
         (only-in file/sha1 bytes->hex-string))
(provide path-record file-record collect-paths write-result)
(define (path-record p)
  (cond
    [(not p) #f]
    [(path-string? p)
     (define raw (if (path? p) (path->string p) p))
     (define full (path->complete-path p))
     (define exists? (or (file-exists? full) (directory-exists? full)))
     ;; A missing search root is reported, never turned into a verified path.
     (hash 'raw raw 'absolute (path->string full) 'exists exists?
           'resolved (and exists? (path->string (normalize-path full))))]
    [else (hash 'non_path (format "~s" p))]))
(define (file-record p)
  (hash 'path (path-record p)
        'sha256 (and (file-exists? p)
                     (call-with-input-file* p
                       (lambda (in) (bytes->hex-string (sha256-bytes in)))))))
(define (collect-paths)
  (define (rec f) (path-record (f)))
  (define (recs f) (map path-record (f)))
  (hash
   'system (for/hash ([key '(exec-file run-file collects-dir config-dir addon-dir
                                      home-dir pref-dir temp-dir)])
             (values key (path-record (find-system-path key))))
   'use_collection_link_paths (use-collection-link-paths)
   'use_user_specific_search_paths (use-user-specific-search-paths)
   'collection_paths (map path-record (current-library-collection-paths))
   'compiled_roots (map path-record (current-compiled-file-roots))
   'setup (hash 'collects (rec find-collects-dir) 'config (rec find-config-dir)
                'lib (rec find-lib-dir) 'dll (rec find-dll-dir)
                'share (rec find-share-dir) 'doc (rec find-doc-dir)
                'pkgs (rec find-pkgs-dir) 'links (rec find-links-file)
                'console_bin (rec find-console-bin-dir) 'gui_bin (rec find-gui-bin-dir)
                'lib_search (recs get-lib-search-dirs)
                'pkgs_search (recs get-pkgs-search-dirs)
                'links_search (recs get-links-search-files)
                'doc_search (recs get-doc-search-dirs))
   'config_file (file-record (build-path (find-config-dir) "config.rktd"))
   'links_file (file-record (find-links-file))
   'package_database (file-record (build-path (find-pkgs-dir) "pkgs.rktd"))))
(define (write-result profile name data)
  (call-with-output-file* (build-path profile name)
    #:exists 'error (lambda (out) (write-json data out) (newline out))))
