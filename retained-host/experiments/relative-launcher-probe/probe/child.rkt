#lang racket/base
;; Invoked by the actual GUI process through its effective exec-file.
(require "paths.rkt" "dyld.rkt" json ffi/unsafe)
(define getpid (get-ffi-obj "getpid" (ffi-lib #f) (_fun -> _int)))
(write-json (hash 'schema 1 'status "observed" 'pid (getpid)
                  'version (version) 'gc (symbol->string (system-type 'gc))
                  'paths (collect-paths) 'loaded_images (loaded-images)))
(newline)
