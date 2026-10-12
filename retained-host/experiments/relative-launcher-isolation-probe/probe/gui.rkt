#lang racket/base
(require "paths.rkt" "cocoa-identity.rkt" "dyld.rkt"
         racket/gui/base racket/file racket/path racket/port racket/system
         json)
(provide run-probe)
(define (run-probe bundle profile startup)
  (define (observe)
     (with-handlers ([exn:fail?
                      (lambda (e)
                        (write-result profile "result.json"
                                      (hash 'schema 1 'status "error"
                                            'error (exn-message e)))
                        (exit 1))])
       (define gui-thread?
         (lambda () (eq? (current-thread)
                        (eventspace-handler-thread (current-eventspace)))))
       (define identity ((make-cocoa-identity-reader gui-thread?)))
       ;; Resolve package files without loading DrRacket or its tools.
       (define modules
         (for/hash ([entry '((racket_base "base.rkt" "racket")
                            (setup_dirs "dirs.rkt" "setup")
                            (pkg_lib "lib.rkt" "pkg")
                            (gui_base "base.rkt" "racket" "gui")
                            (drracket_main "main.rkt" "drracket"))])
           (values (car entry) (file-record (apply collection-file-path (cdr entry))))))
       ;; The supervisor monitors these files while the child runs. Avoid
       ;; unbounded in-memory output strings before the final JSON is written.
       (define child-out (build-path profile "child.stdout"))
       (define child-err (build-path profile "child.stderr"))
       (define runtime (build-path bundle "Contents" "Resources" "runtime"))
       (define child-code
         (call-with-output-file* child-out #:exists 'error
           (lambda (out)
             (call-with-output-file* child-err #:exists 'error
               (lambda (err)
                 (parameterize ([current-input-port (open-input-string "")]
                                [current-output-port out] [current-error-port err])
                   (system*/exit-code
                    (find-system-path 'exec-file)
                    "-E" (path->string (find-system-path 'exec-file))
                    "-X" (path->string (build-path runtime "collects"))
                    "-G" (path->string (build-path runtime "etc"))
                    "-A" (path->string (build-path profile "addons")) "-U"
                    "-R" (path->string (build-path profile "compiled"))
                    "-t" (path->string (build-path bundle "Contents" "Resources" "probe" "child.rkt")))))))))
       (unless (<= (+ (file-size child-out) (file-size child-err)) 1048576)
         (error 'probe "child output exceeded 1 MiB"))
       (unless (zero? child-code) (error 'probe "child failed; see child.stderr"))
       (define child-input (open-input-string (file->string child-out)))
       (define child (read-json child-input))
       (unless (regexp-match? #px"^\\s*$" (port->string child-input))
         (error 'probe "unexpected child stdout after JSON"))
       (define paths (collect-paths))
       (define-values (images snapshot) (loaded-image-snapshot))
       (write-result
        profile "result.json"
        (hash 'schema 1 'status "observed" 'version (version)
              'os (symbol->string (system-type 'os))
              'gc (symbol->string (system-type 'gc))
              'startup startup 'paths paths 'modules modules
              'identity identity 'loaded_images images 'loaded_image_snapshot snapshot
              'child child 'child_stderr (file->string child-err)))
       (exit 0)))
  (if (eq? (current-thread) (eventspace-handler-thread (current-eventspace)))
      (observe)
      (begin
        (queue-callback observe #f)
        ;; No frame is created just to keep this test alive. Do not block the
        ;; handler thread; the callback exits this bounded process when done.
        (sync never-evt))))
