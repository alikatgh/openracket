#lang racket/base
;; Pure/read-only contract helpers. This module loads no GUI or Cocoa code.
(require json racket/file racket/list racket/path racket/string)
(provide validate-config read-json-file control-valid? step-names expected-files
         control-path parse-expected-memory-limit json-safe canonical expected-toolbar-labels current-fixture-toolbar-witness)
(define (canonical value)
  ;; Existing paths only. Resolve every component/alias, then remove trailing
  ;; directory syntax while preserving root, as in the reviewed appbuilder.
  (define path (path->complete-path value))
  (unless (or (file-exists? path) (directory-exists? path))
    (error 'mac-app-observer "Expected existing native/fixture path: ~a" path))
  (path->string (apply build-path (explode-path (normalize-path path)))))
(define (json-safe value)
  (cond [(eq? value 'null) 'null]
        [(symbol? value) (symbol->string value)]
        [(path? value) (path->string value)]
        [(hash? value) (for/hash ([(k v) (in-hash value)]) (values k (json-safe v)))]
        [(list? value) (map json-safe value)]
        [else value]))
(define (parse-expected-memory-limit value)
  (cond [(equal? value "unlimited") #f]
        [(and (string? value) (regexp-match-exact? #px"[0-9]+" value)
              (let ([n (string->number value 10)]) (and (exact-integer? n) (>= n 8))))
         (* (string->number value 10) 1024 1024)]
        [else (error 'mac-app-observer "memory_mib must be decimal >=8 or exactly unlimited: ~s" value)]))
(define (read-json-file path)
  (unless (<= (file-size path) 65536) (error 'mac-app-observer "Oversized JSON control: ~a" path))
  (call-with-input-file path
    (lambda (in)
      (define result (read-json in))
      (unless (eof-object? (read-json in)) (error 'mac-app-observer "Trailing JSON value: ~a" path))
      result)))
(define (token? v) (and (string? v) (regexp-match-exact? #px"[A-Za-z0-9_-]{8,100}" v)))
(define (absolute? v) (and (string? v) (<= 1 (string-length v) 4096)
                           (not (regexp-match? #rx"[\u0000\r\n]" v))
                           (complete-path? (string->path v))))
(define (step-names config) (list (hash-ref config 'mode) "warmfile" "duplicate"))
(define (expected-files config step)
  (if (equal? step "coldempty") '()
      (if (equal? step "coldfile") (take (hash-ref config 'files) 1)
          (hash-ref config 'files))))
(define (validate-config c)
  (define (check b s) (unless b (error 'mac-app-observer "Invalid configuration: ~a" s)))
  (check (hash? c) "object required")
  (check (equal? (sort (hash-keys c) symbol<?)
                 (sort '(schema run_id mode output_dir app_path native_executable_path bundle_id profile_path memory_mib files step_tokens) symbol<?))
         "exact v1 keys required")
  (check (equal? (hash-ref c 'schema) 1) "schema must be 1")
  (check (token? (hash-ref c 'run_id)) "unique safe run_id required")
  (check (member (hash-ref c 'mode) '("coldempty" "coldfile")) "mode")
  (for ([k '(output_dir app_path native_executable_path profile_path)])
    (check (absolute? (hash-ref c k)) (format "absolute ~a" k)))
  (check (and (string? (hash-ref c 'bundle_id))
              (regexp-match-exact? #px"[A-Za-z0-9.-]+" (hash-ref c 'bundle_id))) "bundle_id")
  (parse-expected-memory-limit (hash-ref c 'memory_mib))
  (define files (hash-ref c 'files))
  (check (and (list? files) (andmap absolute? files)
              (= (length files) (if (equal? (hash-ref c 'mode) "coldempty") 1 2))
              (= (length files) (length (remove-duplicates files)))) "distinct files for chosen mode")
  (define tokens (hash-ref c 'step_tokens))
  (check (and (hash? tokens)
              (equal? (sort (map symbol->string (hash-keys tokens)) string<?)
                      (sort (step-names c) string<?))
              (andmap token? (hash-values tokens))
              (= 3 (length (remove-duplicates (hash-values tokens))))) "unique step_tokens for exact three steps")
  c)
(define (control-path config step suffix)
  (build-path (hash-ref config 'output_dir)
              (format "~a.~a.~a.json" (hash-ref config 'run_id) step suffix)))
(define (control-valid? c config step kind)
  (and (hash? c)
       (equal? (hash-ref c 'schema #f) 1)
       (equal? (hash-ref c 'run_id #f) (hash-ref config 'run_id))
       (equal? (hash-ref c 'step #f) step)
       (equal? (hash-ref c 'token #f) (hash-ref (hash-ref config 'step_tokens) (string->symbol step)))
       (case kind
         [(sent) (equal? (hash-ref c 'open_exit #f) 0)]
         [(ack) (eq? (hash-ref c 'capture_ok #f) #t)]
         [else #f])))

;; Stock 9.3 intentionally removes all three language tools for its initial
;; no-language object. This exception is bounded to the original empty document
;; in a coldempty sequence. Named #lang fixtures still require all five buttons.
;; Macro Stepper's ordinary capability is #f for module-language: its registered
;; opt-out toolbar factory supplies the visible module-language button instead.
(define (expected-toolbar-labels mode step unnamed-empty? no-language? module-language?
                                 registered capabilities full-labels)
  (define (check value why)
    (unless value (error 'mac-app-toolbar "~a" why)))
  (check (and (member mode '("coldempty" "coldfile"))
              (member step (list mode "warmfile" "duplicate")))
         "Known sequence and stage required")
  (check (equal? registered '(#t #t #t))
         "Check Syntax, Debug and Macro Stepper capabilities must all be registered")
  (check (and (list? full-labels) (= (length full-labels) 5))
         "The complete localized five-tool order is required")
  (when (equal? step "coldempty")
    (check (and unnamed-empty? no-language?)
           "Fresh coldempty requires the actual empty no-language document"))
  (cond
    [no-language?
     (check (and (equal? mode "coldempty") unnamed-empty? (not module-language?))
            "No-language exception only covers the unnamed empty coldempty document")
     (check (equal? capabilities '(#f #f #f))
            "Stock no-language object must disable the three language capabilities")
     (drop full-labels 3)]
    [else
     (check module-language? "The #lang fixture must select the actual module language")
     full-labels]))

;; A file-stage pass must exercise a real current fixture and its five-tool
;; frame. Named but inactive tabs cannot provide this witness, nor can an allowed
;; blank frame whose toolbar is correctly in the no-language state.
(define (current-fixture-toolbar-witness tabs frame-reports expected)
  (for*/or ([tab (in-list tabs)]
            #:when (and (eq? (hash-ref tab 'current #f) #t)
                        (member (hash-ref tab 'filename #f) expected))
            [frame (in-list frame-reports)]
            #:when (and (equal? (hash-ref frame 'frame_id #f) (hash-ref tab 'frame_id #f))
                        (eq? (hash-ref frame 'full_toolbar_verified #f) #t)
                        (eq? (hash-ref (hash-ref frame 'toolbar_language (hash)) 'module_language #f) #t)))
    (hash 'frame_id (hash-ref tab 'frame_id) 'tab_id (hash-ref tab 'tab_id)
          'filename (hash-ref tab 'filename) 'module_language #t 'full_toolbar_verified #t)))
