#lang racket/base
;; Native-only evidence from the real definitions editor after actual Check Syntax.
(require json racket/class racket/file racket/gui/base racket/list racket/path
         racket/port racket/runtime-path racket/set rackunit string-constants
         syntax/modresolve "rackunit-failure-propagation.rkt"
         "native-tool-failure-diagnostics.rkt")
(provide run-binding-postflight!)
(define-runtime-path host-path "independent-native-host.rkt")
(define-runtime-path workflow-path "independent-native-workflows.rkt")
(define-runtime-path pins-path "binding-native-pins.json")
(define fixture "#lang racket/base\n(define (bump x) (+ x 1))\n(bump 41)\n")
(define fixed-pins
  (hash 'blueboxes-gui "c81a8df93f0012b0ab564009bb4a9ad34d9ce1cde3795e180bfbe33a1008e721"
        'xref "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7"
        'traversals "bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00"
        'online-comp "1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5"))
(define written? #f)
(define (require! value message)
  (unless value (error 'binding-postflight "~a" message)))
(define (hex bytes)
  (apply string-append
         (for/list ([b (in-bytes bytes)])
           (define s (number->string b 16))
           (if (= (string-length s) 1) (string-append "0" s) s))))
(define (digest path)
  (call-with-input-file path (lambda (in) (hex (sha256-bytes (port->bytes in))))))
(define (lex<? a b)
  (cond [(null? a) (pair? b)] [(null? b) #f]
        [(= (car a) (car b)) (lex<? (cdr a) (cdr b))]
        [else (< (car a) (car b))]))
(define witness-fields '(enabled active in_flight generation accepted duplicates eager_writes stock_calls
                                pending materializations public_keys indexed_edges cached_starts exposed
                                unsupported_fallbacks failure_fallbacks fallback_reason))
(define (run-binding-postflight! frame)
  (parameterize ([current-check-handler raise])
    (with-handlers
        ([(lambda (_) #t)
          (lambda (failure)
            ;; Best-effort typed evidence may not replace or suppress failure.
            (report-failure!
             failure
             (lambda (reported)
               (printf "OPENRACKET_BINDING_POSTFLIGHT_FAILURE ~a\n"
                       (jsexpr->string (failure->diagnostic reported)))
               (flush-output)))
            (raise failure))])
      (capture! frame))))
(define (capture! frame)
  (require! (not written?) "duplicate/stale postflight")
  (assert-rackunit-failure-propagation!)
  (check-eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
  (check-equal? (version) "9.3")
  (check-equal? (getenv "OPENRACKET_UI") "stock")
  (check-equal? (getenv "OPENRACKET_NATIVE_CASE") "check-syntax")
  (define pins (call-with-input-file pins-path read-json))
  (check-equal? (digest host-path) (hash-ref pins 'host))
  (check-equal? (digest workflow-path) (hash-ref pins 'workflow))
  (define mode (getenv "OPENRACKET_BINDINGS_EXPECT_MODE"))
  (require! (member mode '("stock" "candidate-off" "candidate-on")) "explicit valid mode required")
  (define candidate? (not (equal? mode "stock")))
  (define enabled? (equal? mode "candidate-on"))
  (define flag (getenv "OPENRACKET_BINDING_TABLE_EAGER"))
  (check-equal? flag (and candidate? (if enabled? "1" "0")))
  (define output (getenv "OPENRACKET_BINDINGS_OUTPUT"))
  (require! (and output (complete-path? output) (not (file-exists? output))) "fresh absolute output required")
  (define root-env (getenv "OPENRACKET_BINDINGS_RUNTIME_ROOT"))
  (require! (and root-env (complete-path? root-env)) "explicit absolute runtime root required")
  (define root (simplify-path root-env #t))
  (check-equal? (path->string root) root-env "runtime root must already be canonical")
  (require! (and (directory-exists? root) (not (equal? root-env "/"))) "specific runtime root required")
  (define prefix (path->bytes (path->directory-path root)))
  (define (relative-source path)
    (define canonical (simplify-path path #t))
    (define raw (path->bytes canonical))
    (require! (and (file-exists? canonical) (> (bytes-length raw) (bytes-length prefix))
                   (bytes=? prefix (subbytes raw 0 (bytes-length prefix)))) "resolved source outside runtime")
    (bytes->string/utf-8 (subbytes raw (bytes-length prefix))))
  (define expected-pins
    (hash-set fixed-pins 'gui (hash-ref pins (if candidate? 'candidate_gui 'stock_gui))))
  (define source-paths (make-hasheq))
  (define sources
    (for/hash ([(name expected) (in-hash expected-pins)])
      (define path (resolve-module-path (string->symbol (format "drracket/private/syncheck/~a" name)) #f))
      (require! (path? path) "module must resolve to a source file")
      (define relative (relative-source path))
      (check-equal? (digest path) expected)
      (hash-set! source-paths name path)
      (values name (hash 'relative relative 'sha256 expected))))
  (define activation
    (dynamic-require 'drracket/private/syncheck/gui 'openracket-binding-table-eager-enabled?
                     (lambda () 'unexported)))
  (check-equal? activation (if candidate? enabled? 'unexported))
  (define defs (send frame get-definitions-text))
  (define canvas (send frame get-definitions-canvas))
  (define tab (send frame get-current-tab))
  (define text-before (send defs get-text))
  (define filename-before (send defs get-filename))
  (define modified-before (send defs is-modified?))
  (define selection-before (list (send defs get-start-position) (send defs get-end-position)))
  (check-equal? text-before fixture)
  (check-equal? (send defs last-position) 54)
  (check-equal? selection-before '(1 6))
  (check-eq? (send canvas get-editor) defs)
  (check-equal? (object-method-arity-includes? defs 'openracket:get-binding-table-eager-state 0) candidate?)
  (define (witness)
    (cond
      [candidate?
       (define state (send defs openracket:get-binding-table-eager-state))
       ;; Best-effort scalar evidence must not replace an original schema
       ;; failure if a malformed witness cannot be encoded.
       (report-failure!
        state
        (lambda (observed)
          (printf "OPENRACKET_BINDING_POSTFLIGHT_STATE ~a\n"
                  (jsexpr->string
                   (hash 'mode mode 'flag flag
                         'state (hash-set observed 'fallback_reason
                                          (if (hash-ref observed 'fallback_reason)
                                              (symbol->string (hash-ref observed 'fallback_reason))
                                              'null)))))
          (flush-output)))
       (require! (and (hash? state) (immutable? state)
                      (= (hash-count state) (length witness-fields))
                      (andmap (lambda (key) (hash-has-key? state key)) witness-fields))
                 "exact immutable scalar witness required")
       (for ([key '(generation accepted duplicates eager_writes stock_calls pending materializations public_keys
                     indexed_edges cached_starts unsupported_fallbacks failure_fallbacks)])
         (require! (exact-nonnegative-integer? (hash-ref state key)) "exact nonnegative witness counter required"))
       (check-equal? (hash-ref state 'enabled) enabled?)
       (check-false (hash-ref state 'active) "unchanged Check Syntax workflow already exported the table")
       (check-equal? (hash-ref state 'pending) 0)
       (check-equal? (hash-ref state 'materializations) 0)
       (check-false (hash-ref state 'in_flight))
       (check-equal? (hash-ref state 'public_keys) 3)
       (check-equal? (hash-ref state 'indexed_edges) 0)
       (check-equal? (hash-ref state 'cached_starts) 0)
       (check-equal? (hash-ref state 'failure_fallbacks) 0)
       (cond [enabled?
              (check-true (positive? (hash-ref state 'accepted)) "genuine owning-editor fast path must run")
              (check-equal? (hash-ref state 'accepted) 8)
              (check-equal? (hash-ref state 'eager_writes) 8)
              (check-equal? (hash-ref state 'stock_calls) 0)
              (check-true (hash-ref state 'exposed))
              (check-equal? (hash-ref state 'unsupported_fallbacks) 0)
              (check-eq? (hash-ref state 'fallback_reason) 'public-exposure)]
             [else
              (check-equal? (hash-ref state 'accepted) 0)
              (check-equal? (hash-ref state 'eager_writes) 0)
              (check-equal? (hash-ref state 'stock_calls) 8)
              (check-false (hash-ref state 'exposed))
              (check-false (hash-ref state 'fallback_reason))])
       (hash-set state 'fallback_reason
                 (if (hash-ref state 'fallback_reason) (symbol->string (hash-ref state 'fallback_reason)) 'null))]
      [else 'null]))
  (define witness-before (witness))
  (define table (send defs syncheck:get-bindings-table))
  (require! (and (hash? table) (not (immutable? table)) (hash-equal? table)
                 (hash-strong? table) (positive? (hash-count table))) "nonempty strong mutable equal? table required")
  (define (endpoint item)
    (require! (and (list? item) (= (length item) 3) (eq? (car item) defs)
                   (exact-integer? (cadr item)) (exact-integer? (caddr item))
                   (<= 0 (cadr item) (caddr item) 54)) "exact same-editor fixture range required")
    (cdr item))
  (define (snapshot)
    (sort
     (for/list ([(key value) (in-hash table)])
       (define start (endpoint key))
       (require! (and (set? value) (set-equal? value) (not (set-mutable? value))
                      (not (set-weak? value)) (positive? (set-count value))) "nonempty immutable equal? set required")
       (cons start (sort (for/list ([end (in-set value)]) (endpoint end)) lex<?)))
     (lambda (a b) (lex<? (car a) (car b)))))
  (define graph (snapshot))
  (define edges
    (sort (apply append (for/list ([row (in-list graph)])
                         (for/list ([end (in-list (cdr row))]) (append (car row) end)))) lex<?))
  (check-equal? (length edges) (length (remove-duplicates edges)) "complete graph has no duplicate edge")
  (check-not-false (member '(27 31 45 49) edges) "bump binding/use direction")
  (check-not-false (member '(32 33 38 39) edges) "parameter binding/use direction")
  ;; Dispatch actual registered stock keymap commands, not a substitute graph walk.
  (define (navigate label command from expected)
    (send defs set-position (car from) (cadr from))
    (check-true (send (send defs get-keymap) call-function command defs (new key-event% [key-code #\x]) #t))
    (define selected (list (send defs get-start-position) (send defs get-end-position)))
    (check-equal? selected expected)
    (list label from selected))
  (define navigation
    (list (navigate "bump-to-binding" (string-constant cs-jump-to-binding) '(45 45) '(27 31))
          (navigate "bump-next" (string-constant cs-jump-to-next-bound-occurrence) '(27 31) '(45 49))
          (navigate "bump-previous" (string-constant cs-jump-to-previous-bound-occurrence) '(45 49) '(27 31))
          (navigate "parameter-to-binding" (string-constant cs-jump-to-binding) '(38 38) '(32 33))
          (navigate "parameter-next" (string-constant cs-jump-to-next-bound-occurrence) '(32 33) '(38 39))))
  (send defs set-position (car selection-before) (cadr selection-before))
  (send canvas on-focus #t)
  (send canvas on-paint)
  (check-eq? (send defs syncheck:get-bindings-table) table "public table identity remains live")
  (check-equal? (snapshot) graph)
  (check-equal? (witness) witness-before "read-only export/navigation must not replay or re-enable eager cache")
  (check-equal? (send defs get-text) text-before)
  (check-equal? (send defs get-filename) filename-before)
  (check-equal? (send defs is-modified?) modified-before)
  (check-equal? (list (send defs get-start-position) (send defs get-end-position)) selection-before)
  (check-eq? (send frame get-definitions-text) defs)
  (check-eq? (send frame get-definitions-canvas) canvas)
  (check-eq? (send frame get-current-tab) tab)
  (check-eq? (send canvas get-editor) defs)
  (for ([(name path) (in-hash source-paths)]) (check-equal? (digest path) (hash-ref expected-pins name)))
  (define result
    (hash 'schema "openracket-native-binding-eager-graph/v1" 'completed #t
          'mode mode 'activation (if candidate? activation "unexported") 'flag (or flag 'null)
          'runtime_root root-env 'version (version) 'sources sources
          'host_sha256 (hash-ref pins 'host) 'workflow_sha256 (hash-ref pins 'workflow)
          'source fixture 'selection selection-before 'graph graph 'edges edges
          'navigation navigation 'eager_witness witness-before
          'checks (hash 'handler_thread #t 'fatal_assertions #t 'table_identity #t
                        'immutable_equal_sets #t 'editor_identity #t 'canvas_identity #t
                        'tab_identity #t 'source_unchanged #t 'selection_restored #t
                        'filename_unchanged #t 'modified_unchanged #t 'sources_unchanged #t)))
  (call-with-output-file output #:exists 'error (lambda (out) (write-json result out) (newline out)))
  (set! written? #t)
  (displayln "OPENRACKET_NATIVE_BINDINGS_OK complete-graph real-navigation escaped-table")
  (flush-output))
