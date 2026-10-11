#lang racket/base
;; GUI-free native test of the exact failure-only diagnostic encoder.
(require json racket/list racket/match racket/port "docs-entry-diagnostic.rkt")
(define (require! condition message)
  (unless condition (error 'docs-entry-diagnostic-test "~a" message)))
(define bounds (cons 35 36))
(define stored (list 35 36 '(form ((quote #%kernel) #%datum))
                     (string->path "/runtime/doc/reference/quote.html")
                     "(form._((quote._~23~25kernel)._~23~25datum))"))
(define diagnostic (docs-entry-diagnostic 2 25 bounds stored))
(define (decode value)
  (match value
    [(list "null") '()]
    [(list "integer" number) (string->number number)]
    [(list "boolean" value) value]
    [(list "pair" a d) (cons (decode a) (decode d))]
    [(list "string" bytes size #t)
     (define text (bytes->string/utf-8 (list->bytes bytes)))
     (require! (= (string-length text) size) "complete string length") text]
    [(list "symbol" #t bytes size #t)
     (define text (bytes->string/utf-8 (list->bytes bytes)))
     (require! (= (string-length text) size) "complete symbol length") (string->symbol text)]
    [(list "path" convention bytes size #t)
     (require! (= (length bytes) size) "complete raw path byte length")
     (bytes->path (list->bytes bytes) (string->symbol convention))]
    [_ (error 'docs-entry-diagnostic-test "unexpected or incomplete diagnostic datum")]))
(require! (hash-ref diagnostic 'failure) "diagnostic is always a failure record")
(require! (hash-ref diagnostic 'complete) "small actual-style entry must be captured completely")
(require! (equal? (decode (hash-ref diagnostic 'bounds)) bounds) "exact typed bounds round trip")
(require! (equal? (decode (hash-ref diagnostic 'stored)) stored) "exact complete stored value round trip")
(for ([value (in-list (list (make-string 20000 #\λ)
                            (make-vector 10000 stored)
                            (for/fold ([value #f]) ([index (in-range 100)]) (cons value '()))
                            (make-hash)))])
  (define report (docs-entry-diagnostic 0 -1 bounds value))
  (require! (not (hash-ref report 'complete)) "truncation and unsupported types must be explicit")
  (define out (open-output-string))
  (write-docs-entry-diagnostic! 0 -1 bounds value out)
  (define output (get-output-string out))
  (define prefix "OPENRACKET_INTERVAL_DOCS_ENTRY_FAILURE ")
  (require! (<= (bytes-length (string->bytes/utf-8 output)) (+ 32768 (string-length prefix) 1))
            "diagnostic has a hard serialized byte bound")
  (define parsed (call-with-input-string (substring output (string-length prefix)) read-json))
  (require! (and (hash-ref parsed 'failure) (not (hash-ref parsed 'complete)))
            "bounded log remains explicit failed/incomplete JSON"))
(displayln "OPENRACKET_DOCS_ENTRY_DIAGNOSTIC_OK exact-roundtrip bounded-failure-only")
