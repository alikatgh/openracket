#lang racket/base
(require ffi/unsafe)
(provide loaded-image-snapshot)
(define (loaded-image-snapshot)
  ;; Public Darwin APIs only. A read-only bounded snapshot, not a system audit.
  ;; dyld enumeration is not thread-safe: fail if count/index/name/header changes.
  ;; This probe does not intentionally load/unload libraries during this call.
  (define lib (ffi-lib #f))
  (define count (get-ffi-obj "_dyld_image_count" lib (_fun -> _uint32)))
  (define name (get-ffi-obj "_dyld_get_image_name" lib (_fun _uint32 -> _string/utf-8)))
  (define header (get-ffi-obj "_dyld_get_image_header" lib (_fun _uint32 -> _pointer)))
  ;; C99 bool is one byte, unlike ffi/unsafe's C-int _bool.
  (define cached? (get-ffi-obj "_dyld_shared_cache_contains_path" lib
                             (_fun _string/utf-8 -> _stdbool)))
  (define n (count))
  (unless (<= 1 n 8192) (error 'probe "unexpected loaded-image count"))
  (define captured
    (for/list ([i (in-range n)])
      (define raw (name i))
      (define mh (header i))
      (unless (and raw mh) (error 'probe "missing dyld name/header"))
      (list raw mh)))
  (define (check-stable!)
    (unless (and (= n (count))
                 (for/and ([item (in-list captured)] [i (in-naturals)])
                   (and (equal? (car item) (name i))
                        (ptr-equal? (cadr item) (header i))))
                 (= n (count)))
      (error 'probe "dyld snapshot changed")))
  (check-stable!)
  (define records
    (for/list ([item (in-list captured)] [i (in-naturals)])
      (define raw (car item))
      (define mh (cadr item))
      ;; Header layout and MH_DYLIB_IN_CACHE are public mach-o/loader.h.
      ;; Read only the fixed header. Never dereference a path or a load command.
      (hash 'index i 'raw raw
            'header_address (number->string (cast mh _pointer _uintptr) 16)
            'magic (ptr-ref mh _uint32 0)
            'cpu_type (ptr-ref mh _uint32 1)
            'file_type (ptr-ref mh _uint32 3)
            'flags (ptr-ref mh _uint32 6)
            'shared_cache_contains_path (cached? raw))))
  (check-stable!)
  (values (map car captured)
          (hash 'schema 1 'method "public-dyld-name-header-cache-v1"
                'count n 'stable #t 'records records)))
