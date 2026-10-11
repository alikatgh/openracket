#lang racket/base
(require ffi/unsafe)
(provide loaded-images)
(define (loaded-images)
  ;; Darwin dyld read-only APIs. The bounded process is not changing libraries
  ;; concurrently when sampled; this is a snapshot, not a system-wide audit.
  (define lib (ffi-lib #f))
  (define count (get-ffi-obj "_dyld_image_count" lib (_fun -> _uint32)))
  (define name (get-ffi-obj "_dyld_get_image_name" lib (_fun _uint32 -> _string/utf-8)))
  (define n (count))
  (unless (<= n 8192) (error 'probe "unexpected loaded-image count"))
  (for/list ([i (in-range n)]) (name i)))
