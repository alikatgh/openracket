#lang racket/base
;; Resolution and byte-integrity checks only: no GUI module is instantiated.
(require json racket/file racket/list racket/path racket/runtime-path
         setup/dirs file/sha1)
(define-runtime-path root "..")
(define profile (simplify-path (build-path root "profile")))
(define modules '(racket/gui/base drracket/drracket mrlib/switchable-button
                 drracket/tool macro-debugger/stepper stepper/stepper-tool
                 openracket-appearance/tool))
(define (module-path m)
  (resolved-module-path-name ((current-module-name-resolver) m #f #f #f)))
(define (attempt thunk)
  (with-handlers ([exn:fail? (lambda (e) (hash 'available #f 'error (exn-message e)))])
    (thunk)))
(define (resolve m)
  (hash-set
   (attempt (lambda ()
              (define p (module-path m))
              (hash 'available (and (path? p) (file-exists? p))
                    'path (if (path? p) (path->string p) (format "~s" p)))))
   'module (symbol->string m)))
(define manifest (call-with-input-file (build-path root "reports/patch-manifest.json") read-json))
(define (confined? path)
  (define relative (find-relative-path profile (simplify-path path)))
  (and (relative-path? relative) (not (member 'up (explode-path relative)))))
(define (check-source module expected-hash)
  (hash-set
   (attempt
    (lambda ()
      (define path (module-path module))
      (define digest (bytes->hex-string (sha256-bytes (file->bytes path))))
      (hash 'available (and (confined? path) (equal? digest expected-hash))
            'path (path->string path) 'inside_profile (confined? path)
            'sha256 digest 'expected_sha256 expected-hash)))
   'module (symbol->string module)))
(define module-checks (map resolve modules))
(define source-checks
  (list (check-source 'mrlib/switchable-button (hash-ref manifest 'patched_sha256))
        (check-source 'mrlib/private/openracket-paint (hash-ref manifest 'painter_sha256))
        (check-source 'framework/private/text-misc
                      "00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d")))
(define passed?
  (and (equal? (version) "9.3")
       (for/and ([check (in-list (append module-checks source-checks))])
         (hash-ref check 'available))))
(write-json (hash 'status (if passed? "passed" "failed")
                  'racket_version (version)
                  'platform (symbol->string (system-type 'os))
                  'display (or (getenv "DISPLAY") 'null)
                  'wayland_display (or (getenv "WAYLAND_DISPLAY") 'null)
                  'compiled_roots (for/list ([p (current-compiled-file-roots)])
                                    (if (path? p) (path->string p) (symbol->string p)))
                  'module_checks module-checks 'source_checks source-checks
                  'native_window_started #f))
(newline)
(exit (if passed? 0 1))
