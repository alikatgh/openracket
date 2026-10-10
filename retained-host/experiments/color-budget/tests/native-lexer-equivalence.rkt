#lang racket/base
;; Native correctness only. Run separately in same-appearance stock/candidate
;; runtimes. The caller owns fresh profiles, activation and an outer timeout.
(require racket/class racket/file racket/list racket/format json
         syntax-color/racket-lexer syntax-color/lexer-contract)
(unless (zero? (vector-length (current-command-line-arguments)))
  (error 'native-lexer-equivalence "use environment configuration, not GUI arguments"))
(define output (getenv "OPENRACKET_LEXER_OUTPUT"))
(unless output (error 'native-lexer-equivalence "OPENRACKET_LEXER_OUTPUT is required"))
(define report (make-hasheq))
(hash-set! report 'status "running")
(hash-set! report 'mode (or (getenv "OPENRACKET_LEXER_MODE") "unlabelled"))
(hash-set! report 'racket_version (version))
(hash-set! report 'cases (make-hasheq))
(hash-set! report 'activation_environment
           (for/hasheq ([key '("OPENRACKET_ALL_STRING_FAST_PATH"
                              "OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"
                              "OPENRACKET_UI" "OPENRACKET_HOST_THEME" "OPENRACKET_THEME")])
             (values (string->symbol key) (or (getenv key) "unset"))))
(define (summary)
  (for/hasheq ([(key value) (in-hash report)] #:unless (eq? key 'cases))
    (values key value)))
(define (persist!)
  (call-with-output-file output #:exists 'truncate/replace
    (lambda (out) (write-json report out) (newline out))))
(define (check value message)
  (unless value (error 'native-lexer-equivalence "~a" message)))
(define (emit kind data)
  (printf "OPENRACKET_LEXER_~a_JSON_BEGIN\n" kind)
  (write-json data) (newline)
  (printf "OPENRACKET_LEXER_~a_JSON_END\n" kind) (flush-output))
(define fixture-text
  (string-append
   "#lang racket/base\n"
   "; Unicode λ 世界 🌿 and misleading ([{ delimiters\n"
   "(define greeting \"λ 世界 🌿; \\\"quoted\\\"\")\n"
   "(define pattern #rx\"[a-z]+\")\n"
   "#| nested #| comment |# with ) ] } |#\n"
   "(define (sample x)\n  (define data `((alpha ,x) #(1 2 3)))\n"
   "  (for/list ([n (in-range 4)] #:when (even? n))\n"
   "    (list (+ x n) greeting pattern data #t #\\space)))\n"
   "#;(ignored [balanced])\n(sample 2)\n"))
(define fixture (make-temporary-file "openracket-lexer-~a.rkt"))
(call-with-output-file fixture #:exists 'truncate
  (lambda (out) (display fixture-text out)))
(persist!)
(with-handlers ([exn:fail?
                 (lambda (e)
                   (hash-set! report 'status "failed")
                   (hash-set! report 'error (exn-message e))
                   (persist!) (emit "SUMMARY" (summary))
                   (when (file-exists? fixture) (delete-file fixture))
                   (exit 1))])
  (current-command-line-arguments #())
  (define queue-callback (dynamic-require 'racket/gui/base 'queue-callback))
  (define gui-yield (dynamic-require 'racket/gui/base 'yield))
  (define windows (dynamic-require 'racket/gui/base 'get-top-level-windows))
  (define (pause n)
    (gui-yield (alarm-evt (+ (current-inexact-milliseconds) (* 1000 n)))))
  (define (await-lexer! editor)
    (define limit (+ (current-inexact-monotonic-milliseconds) 10000))
    ;; Check after dispatching queued work, and require three successive valid
    ;; observations. Each mutation is separately checked, never just startup.
    (let loop ([valid-count 0])
      (pause .020)
      (define valid? (send editor is-lexer-valid?))
      (cond [(and valid? (= valid-count 2)) (void)]
            [(>= (current-inexact-monotonic-milliseconds) limit)
             (error 'native-lexer-equivalence "lexer did not settle within10s")]
            [else (loop (if valid? (add1 valid-count) 0))])))
  (define (rgba color)
    (list (send color red) (send color green) (send color blue) (send color alpha)))
  (define (style-data style)
    ;; All public resolved appearance properties of a style, not object identity.
    (hasheq 'name (or (send style get-name) 'null)
            'family (~a (send style get-family)) 'face (or (send style get-face) 'null)
            'size (send style get-size) 'weight (~a (send style get-weight))
            'slant (~a (send style get-style)) 'smoothing (~a (send style get-smoothing))
            'underlined (send style get-underlined) 'pixels (send style get-size-in-pixels)
            'alignment (~a (send style get-alignment))
            'transparent_backing (send style get-transparent-text-backing)
            'foreground (rgba (send style get-foreground))
            'background (rgba (send style get-background))))
  (define (snapshot editor)
    (check (send editor is-lexer-valid?) "snapshot must follow completed coloring")
    (define text (send editor get-text))
    (define length (send editor last-position))
    (define tokens
      (for/list ([position (in-range length)])
        (define-values (start end) (send editor get-token-range position))
        (list position (~s (send editor classify-position position)) start end)))
    (define parens
      (for/list ([position (in-range length)]
                 #:when (eq? (send editor classify-position position) 'parenthesis))
        (list position (string (string-ref text position))
              (send editor forward-match position length)
              (send editor backward-match (add1 position) 0))))
    (define styles
      (let loop ([snip (send editor find-first-snip)] [position 0] [spans null])
        (cond
          [(not snip)
           (check (= position length) "style spans must cover every editor position")
           (reverse spans)]
          [else
           (define end (+ position (send snip get-count)))
           (define style (style-data (send snip get-style)))
           (define next-spans
             (cond [(= position end) spans]
                   [(and (pair? spans) (equal? style (caddar spans)))
                    (cons (list (caar spans) end style) (cdr spans))]
                   [else (cons (list position end style) spans)]))
           (loop (send snip next) end next-spans)])))
    (hasheq 'text text 'characters length 'lexer_valid #t
            'tokens_by_position tokens 'parenthesis_graph parens 'normalized_style_spans styles))
  (define (record-case! name editor expected)
    (await-lexer! editor)
    (check (equal? expected (send editor get-text)) (format "text mismatch in ~a" name))
    (define data (snapshot editor))
    (hash-set! (hash-ref report 'cases) (string->symbol name) data)
    (persist!) (emit "CASE" (hasheq 'name name 'data data)))
  (define done (make-semaphore))
  (define failure #f)
  (queue-callback
   (lambda ()
     (with-handlers ([exn:fail? (lambda (e) (set! failure e))])
       (dynamic-require 'drracket/drracket #f)
       (define frame
         (let ([limit (+ (current-inexact-monotonic-milliseconds) 20000)])
           (let loop ()
             (define found
               (for/or ([window (in-list (windows))])
                 (and (object-method-arity-includes? window 'get-definitions-text 0)
                      (send window is-shown?) window)))
             (cond [found found]
                   [(>= (current-inexact-monotonic-milliseconds) limit)
                    (error 'native-lexer-equivalence "no actual DrRacket frame within20s")]
                   [else (pause .020) (loop)]))))
       (define editor (send frame get-definitions-text))
       (hash-set! report 'definitions_composition
                  "actual shown DrRacket frame get-definitions-text; stock or externally pinned unit.rkt candidate")
       (define preferences:get (dynamic-require 'framework 'preferences:get))
       (hash-set! report 'preserved_preferences
                  (for/hasheq ([key '(framework:coloring-active drracket:online-compilation-default-on
                                     drracket:child-only-memory-limit framework:standard-style-list:font-size)])
                    (values key (~s (preferences:get key)))))
       (send frame change-to-file fixture)
       (record-case! "definitions-initial" editor fixture-text)
       (send editor clear-undos)
       (define at (string-length "#lang racket/base\n"))
       (define inserted "#| pending Unicode edit λ ) ] |#\n")
       (define changed (string-append (substring fixture-text 0 at) inserted (substring fixture-text at)))
       (define (edit! thunk)
         (define before (send editor get-revision-number))
         (send editor begin-edit-sequence)
         (thunk)
         (send editor end-edit-sequence)
         (check (not (= before (send editor get-revision-number))) "edit did not change revision"))
       (edit! (lambda () (send editor insert inserted at at)))
       (record-case! "definitions-insert" editor changed)
       (edit! (lambda () (send editor delete at (+ at (string-length inserted)))))
       (record-case! "definitions-delete" editor fixture-text)
       (send editor undo)
       (record-case! "definitions-undo" editor changed)
       (send editor redo)
       (record-case! "definitions-redo" editor fixture-text)
       ;; Invalidate a string token into an error and restore it, exercising more
       ;; than a same-classification comment edit.
       (define quote-position
         (car (car (regexp-match-positions #rx"\"λ" fixture-text))))
       (define escape-position (add1 quote-position))
       (define invalid-escape "\\q")
       (edit! (lambda () (send editor insert invalid-escape escape-position escape-position)))
       (record-case! "definitions-string-invalidated" editor
                     (string-append (substring fixture-text 0 escape-position) invalid-escape
                                    (substring fixture-text escape-position)))
       (check (for/or ([position (in-range (send editor last-position))])
                (eq? (send editor classify-position position) 'error))
              "malformed string escape must produce a lexer error token")
       (send editor undo)
       (record-case! "definitions-string-restored" editor fixture-text)
       (define recorded (hash-ref report 'cases))
       (for ([restored '(definitions-delete definitions-redo definitions-string-restored)])
         (check (equal? (hash-ref recorded 'definitions-initial) (hash-ref recorded restored))
                (format "restored source did not restore all token/paren/style observations: ~a" restored)))
       (check (equal? (hash-ref recorded 'definitions-insert) (hash-ref recorded 'definitions-undo))
              "undo did not restore inserted source observations")
       ;; Independent Framework case for the budget experiment. Scan-only unit.rkt
       ;; substitution does not affect this color:text% composition.
       (define color:text% (dynamic-require 'framework 'color:text%))
       (define custom (new color:text%))
       (define must-continue? #f)
       (define previous-port #f)
       (define group-complete (box #t))
       (define violations 0)
       (define calls 0)
       (define (stateful-lexer in offset mode)
         (when (and must-continue? (not (eq? in previous-port)))
           (set! violations (add1 violations)))
         (set! previous-port in)
         (when (zero? (modulo (or mode 0) 3))
           (set! group-complete (box #f)))
         (set! calls (add1 calls))
         ;; A single long token call and groups longer than either 8 or 20 ms
         ;; are deliberate correctness stimuli, never performance samples.
         (sleep (if (= calls 1) .045 .012))
         (define-values (lexeme type paren start end) (racket-lexer in))
         (define next-mode (add1 (or mode 0)))
         (set! must-continue? (and (not (eq? type 'eof)) (not (zero? (modulo next-mode 3)))))
         (unless must-continue? (set-box! group-complete #t))
         (when must-continue?
           ;; A delayed probe must inspect its own group's completion, never a
           ;; later group's shared state.
           (define this-group group-complete)
           (queue-callback
            (lambda () (unless (unbox this-group) (set! violations (add1 violations)))) #t))
         (values lexeme type paren start end 0
                 (if must-continue? (dont-stop next-mode) next-mode)))
       (send custom start-colorer (lambda (_) "Standard") stateful-lexer
             '((|(| |)|) (|[| |]|) (|{| |}|)))
       (define custom-text "(define λ (list 1 2 3))\n; 世界\n[λ \"text\"]\n")
       (send custom insert custom-text)
       (record-case! "framework-stateful-dont-stop" custom custom-text)
       (check (zero? violations) "a don't-stop group was interrupted or received a different input port")
       (hash-set! report 'dont_stop_violations violations)
       (hash-set! report 'stateful_lexer_calls calls)
       (send custom stop-colorer)
       (send editor set-modified #f)
       (send frame show #f))
     (semaphore-post done)) #f)
  (gui-yield (semaphore-peek-evt done))
  (when failure (raise failure))
  (hash-set! report 'status "complete")
  (persist!) (emit "SUMMARY" (summary))
  (delete-file fixture)
  (exit 0))
