#lang racket/base
;; Failure-only diagnostics. Never used to encode a successful docs snapshot.
(require json racket/list racket/path)
(provide docs-entry-diagnostic write-docs-entry-diagnostic!)

(define max-items 256)
(define max-depth 24)
(define max-data-bytes 4096)
(define max-json-bytes 32768)
(define marker "OPENRACKET_INTERVAL_DOCS_ENTRY_FAILURE ")

(define (docs-entry-diagnostic index previous-end bounds stored)
  (define items-left max-items)
  (define bytes-left max-data-bytes)
  (define complete? #t)
  (define (incomplete!) (set! complete? #f))
  (define (clip-bytes raw)
    (define size (bytes-length raw))
    (define kept (min size bytes-left))
    (set! bytes-left (- bytes-left kept))
    (unless (= size kept) (incomplete!))
    (list (bytes->list (subbytes raw 0 kept)) size (= size kept)))
  (define (clip-string text)
    ;; Do not first encode an arbitrarily large string. At most one raw-byte
    ;; budget's worth of characters is converted; truncation is always explicit.
    (define length (string-length text))
    (define kept (min length bytes-left))
    (unless (= kept length) (incomplete!))
    (define part (clip-bytes (string->bytes/utf-8 (substring text 0 kept))))
    (list (car part) length (and (= kept length) (caddr part))))
  (define (unsupported value)
    (incomplete!)
    (list "unsupported"
          (cond [(number? value) "number"] [(hash? value) "hash"]
                [(box? value) "box"] [(procedure? value) "procedure"]
                [(struct? value) "structure"] [else "other"])))
  (define (encode value depth)
    (cond
      [(zero? items-left)
       (incomplete!) (list "truncated" "items")]
      [else
       (set! items-left (sub1 items-left))
       (define (recur v) (encode v (add1 depth)))
       (cond
         [(>= depth max-depth) (incomplete!) (list "truncated" "depth")]
         [(boolean? value) (list "boolean" value)]
         [(null? value) (list "null")]
         [(exact-integer? value)
          (if (<= (integer-length value) 256)
              (list "integer" (number->string value))
              (begin (incomplete!) (list "truncated-integer" (integer-length value) (negative? value))))]
         [(char? value) (list "character" (char->integer value))]
         [(string? value) (cons "string" (clip-string value))]
         [(symbol? value) (append (list "symbol" (symbol-interned? value))
                                  (clip-string (symbol->string value)))]
         [(bytes? value) (cons "bytes" (clip-bytes value))]
         [(path? value) (append (list "path" (symbol->string (path-convention-type value)))
                                (clip-bytes (path->bytes value)))]
         [(pair? value) (list "pair" (recur (car value)) (recur (cdr value)))]
         [(vector? value)
          (define size (vector-length value))
          (define entries
            (for/list ([index (in-range size)] #:break (zero? items-left))
              (recur (vector-ref value index))))
          (define kept (length entries))
          (unless (= kept size) (incomplete!))
          (list "vector" size entries (= kept size))]
         [else (unsupported value)])]))
  ;; The complete flag is read only after both actual values were encoded.
  (define encoded-bounds (encode bounds 0))
  (define encoded-stored (encode stored 0))
  (hash 'schema "openracket-docs-entry-failure/v1" 'failure #t
        'index index 'previous_end previous-end 'complete complete?
        'limits (hash 'items max-items 'depth max-depth 'data_bytes max-data-bytes 'json_bytes max-json-bytes)
        'bounds encoded-bounds 'stored encoded-stored))

(define (write-docs-entry-diagnostic! index previous-end bounds stored [out (current-error-port)])
  (define report (docs-entry-diagnostic index previous-end bounds stored))
  (define text (jsexpr->string report))
  (define encoded (string->bytes/utf-8 text))
  (define bounded
    (if (<= (bytes-length encoded) max-json-bytes)
        text
        ;; A bounded failure marker is not a replacement/success datum. The
        ;; original guard exception is still raised by the caller.
        (jsexpr->string
         (hash 'schema "openracket-docs-entry-failure/v1" 'failure #t 'complete #f
               'diagnostic_error "serialized diagnostic exceeds hard byte limit"
               'max_json_bytes max-json-bytes))))
  (display marker out) (display bounded out) (newline out) (flush-output out))
