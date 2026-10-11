#lang racket/base
;; The initial diagnostic uses base + the core racket/path import only. JSON,
;; setup/dirs and GUI dependencies are loaded only after the link-path assertion.
(require racket/path)
(define argv (current-command-line-arguments))
(unless (= (vector-length argv) 2) (error 'probe "expected bundle and profile"))
(define bundle (normalize-path (vector-ref argv 0)))
(define profile (normalize-path (vector-ref argv 1)))
(call-with-output-file* (build-path profile "startup-minimal.rktd") #:exists 'error
  (lambda (out)
    (write (hash 'schema 1 'use_collection_link_paths (use-collection-link-paths)
                 'use_user_specific_search_paths (use-user-specific-search-paths)
                 'exec-file (find-system-path 'exec-file)
                 'collects-dir (find-system-path 'collects-dir)
                 'config-dir (find-system-path 'config-dir)) out)
    (newline out)))
(unless (and (use-collection-link-paths) (not (use-user-specific-search-paths)))
  (error 'probe "-X did not restore collection links, or -U did not isolate searches"))
(define paths-source (build-path bundle "Contents" "Resources" "probe" "paths.rkt"))
(define collect-paths (dynamic-require paths-source 'collect-paths))
(define write-result (dynamic-require paths-source 'write-result))
(define startup (collect-paths))
(write-result profile "startup.json"
              (hash 'schema 1 'status "startup-observed" 'paths startup))
((dynamic-require (build-path bundle "Contents" "Resources" "probe" "gui.rkt")
                  'run-probe) bundle profile startup)
