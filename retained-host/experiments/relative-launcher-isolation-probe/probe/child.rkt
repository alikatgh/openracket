#lang racket/base
;; Invoked by the actual GUI process through its effective exec-file.
(require "paths.rkt" "dyld.rkt" json ffi/unsafe)
(define getpid (get-ffi-obj "getpid" (ffi-lib #f) (_fun -> _int)))
(define paths (collect-paths))
(define-values (images snapshot) (loaded-image-snapshot))
(write-json (hash 'schema 1 'status "observed" 'pid (getpid)
                  'version (version) 'gc (symbol->string (system-type 'gc))
                  'paths paths 'loaded_images images 'loaded_image_snapshot snapshot))
(newline)
