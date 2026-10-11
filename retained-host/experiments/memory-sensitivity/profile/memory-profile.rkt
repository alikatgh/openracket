#lang racket/base
;; A separate, headless, pre-timing process. Never require this in the GUI host.
(require file/sha1 json racket/cmdline racket/file racket/list racket/path
         racket/port racket/gui/dynamic setup/dirs)

(define preference-key 'drracket:child-only-memory-limit)
(define disk-key 'plt:framework-pref:drracket:child-only-memory-limit)
(define default-bytes (* 128 1024 1024))
(define source-pins
  (hasheq 'eval_helpers "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62"
          'framework_preferences "59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c"))
(define max-store-bytes (* 1024 1024))

(define (ensure yes? fmt . arguments)
  (unless yes? (apply error 'memory-profile fmt arguments)))

;; Resolve every existing symlink component, including macOS /var -> /private/var.
;; simplify-path alone does not resolve arbitrary ancestor symlinks.
(define (physical-path p [links 0])
  (ensure (< links 64) "too many symbolic links")
  (define parts (explode-path (path->complete-path p)))
  (for/fold ([base (car parts)]) ([part (in-list (cdr parts))])
    (define candidate
      (cond [(eq? part 'same) base]
            [(eq? part 'up) (simplify-path (build-path base 'up) #f)]
            [else (build-path base part)]))
    (if (link-exists? candidate)
        (physical-path (path->complete-path (resolve-path candidate)
                                            (or (path-only candidate) base))
                       (add1 links))
        candidate)))

(define (within? p root)
  (define pp (explode-path (physical-path p)))
  (define rp (explode-path (physical-path root)))
  (and (> (length pp) (length rp))
       (equal? (take pp (length rp)) rp)))

(define (overlap? a b)
  (or (equal? (physical-path a) (physical-path b)) (within? a b) (within? b a)))

(define (file-sha256 p)
  (call-with-input-file p (lambda (in) (bytes->hex-string (sha256-bytes in)))))

(define (checked-source p runtime-root name)
  (define real (physical-path p))
  (ensure (within? real runtime-root) "~a source is outside runtime root: ~a" name real)
  (ensure (and (file-exists? real) (<= (file-size real) max-store-bytes))
          "~a source is missing or oversized" name)
  (define actual (file-sha256 real))
  (define expected (hash-ref source-pins name))
  (ensure (equal? actual expected) "~a source SHA-256 does not match official 9.3 pin" name)
  (hasheq 'path (path->string real) 'sha256 actual 'expected_sha256 expected))

(define (read-store path)
  (cond
    [(not (file-exists? path)) (hasheq)]
    [else
     (ensure (<= (file-size path) max-store-bytes) "preference store is oversized")
     (call-with-input-file path
       (lambda (in)
         (parameterize ([read-accept-reader #f] [read-accept-lang #f]
                        [read-accept-graph #f] [read-accept-compiled #f])
           (define entries (read in))
           (ensure (and (list? entries) (<= (length entries) 4096)
                        (andmap (lambda (v) (and (list? v) (= (length v) 2)
                                                (symbol? (car v)))) entries)
                        (eof-object? (read in)))
                   "invalid preference store")
           (define result (make-immutable-hasheq
                           (map (lambda (v) (cons (car v) (cadr v))) entries)))
           (ensure (= (hash-count result) (length entries)) "duplicate preference-store key")
           result)))]))

(define (selected-limit s)
  (ensure (member s '("128" "256" "512")) "--limit-mib must be exactly 128, 256, or 512")
  (* (string->number s) 1024 1024))

(define (fresh-directory env-name)
  (define value (getenv env-name))
  (ensure (and value (complete-path? value)) "~a must name an explicit absolute path" env-name)
  (define path (physical-path value))
  (ensure (directory-exists? path) "~a directory must already exist" env-name)
  (ensure (null? (directory-list path)) "~a directory must be empty" env-name)
  path)

(define (only-target-addition? before after selected)
  (and (not (hash-has-key? before disk-key))
       (equal? (hash-ref after disk-key #f) selected)
       (equal? before (hash-remove after disk-key))))

(define (emit-json result out)
  (define contents (jsexpr->string result))
  (ensure (<= (string-length contents) 32768) "JSON report exceeds bound")
  (displayln contents out)
  (flush-output out))

(define (run)
  (define limit-argument #f)
  (define output-argument #f)
  (define root-argument #f)
  (define out #f)
  (define stage "arguments")
  (define preference-write-attempted? #f)
  (with-handlers
      ([exn:fail?
        (lambda (e)
          (define message (exn-message e))
          (define bounded (substring message 0 (min (string-length message) 1600)))
          (when out
            (emit-json (hasheq 'schema_version 1 'status "refused" 'stage stage
                               'error bounded
                               'preference_write_attempted preference-write-attempted?) out)
            (close-output-port out))
          (eprintf "~a\n" bounded)
          (exit 1))])
    (command-line
     #:program "memory-profile.rkt"
     #:once-each
     [("--limit-mib") value "128, 256, or 512" (set! limit-argument value)]
     [("--output") value "New absolute JSON report path" (set! output-argument value)]
     [("--runtime-root") value "Absolute cloned Racket 9.3 runtime root" (set! root-argument value)]
     #:args () (void))
    (ensure (and output-argument (complete-path? output-argument)) "--output must be an absolute path")
    (ensure (and root-argument (complete-path? root-argument)) "--runtime-root must be an absolute path")
    (define root (physical-path root-argument))
    (define output (physical-path output-argument))
    (ensure (directory-exists? root) "runtime root does not exist")
    (ensure (and (path-only output) (directory-exists? (path-only output)))
            "output parent directory must already exist")
    (ensure (not (within? output root)) "output may not be inside runtime")
    (for ([name '("PLTUSERHOME" "PLTADDONDIR")])
      (define value (getenv name))
      (when (and value (complete-path? value))
        (ensure (not (overlap? output value)) "output may not overlap ~a" name)))
    (ensure (not (or (file-exists? output) (directory-exists? output)
                     (link-exists? output-argument))) "output must not already exist")
    (set! out (open-output-file output #:exists 'error))
    (define selected (selected-limit limit-argument))
    (set! stage "runtime-and-profile")
    (ensure (equal? (version) "9.3") "requires Racket 9.3; running ~a" (version))
    (define executable
      (physical-path (or (find-executable-path (find-system-path 'exec-file))
                         (find-system-path 'exec-file))))
    (ensure (within? executable root) "running executable is outside runtime root")
    (define home (fresh-directory "PLTUSERHOME"))
    (define addon (fresh-directory "PLTADDONDIR"))
    (ensure (not (overlap? home addon)) "profile and addon directories must be disjoint")
    (ensure (and (not (overlap? home root)) (not (overlap? addon root)))
            "profile and addon directories must be outside runtime")
    (ensure (equal? home (physical-path (find-system-path 'home-dir))) "PLTUSERHOME not active")
    (ensure (equal? addon (physical-path (find-system-path 'addon-dir))) "PLTADDONDIR not active")
    (define pref-file (physical-path (find-system-path 'pref-file)))
    (ensure (within? pref-file home) "preference file is outside fresh profile")
    ;; On Unix, expand-user-path consults HOME, not PLTUSERHOME. Check the
    ;; actual old-file candidate before the standard API can inherit it.
    (define legacy
      (case (system-type 'os)
        [(unix) (expand-user-path "~/.plt-scheme/plt-prefs.ss")]
        [(macosx) (build-path (find-system-path 'pref-dir) "org.plt-scheme.prefs.ss")]
        [(windows) (build-path (find-system-path 'pref-dir) 'up "PLT Scheme" "plt-prefs.ss")]
        [else (error 'memory-profile "unsupported preference-store platform")]))
    (ensure (not (or (file-exists? legacy) (link-exists? legacy)))
            "legacy fallback preference store exists; cannot prove fresh one-key profile")
    ;; A fresh user profile must not inherit a runtime-wide fallback store.
    (define fallback (build-path (find-config-dir) "racket-prefs.rktd"))
    (ensure (not (or (file-exists? fallback) (link-exists? fallback)))
            "runtime has a fallback preference store; cannot prove fresh one-key profile")
    (define before (read-store pref-file))
    (ensure (zero? (hash-count before)) "fresh preference store is not empty")
    (ensure (not (gui-available?)) "GUI was initialized before profile setup")
    (set! stage "source-pins")
    (define eval-path (collection-file-path "eval-helpers-and-pref-init.rkt" "drracket" "private"))
    (define framework-path (collection-file-path "preferences.rkt" "framework"))
    (define sources
      (hasheq 'eval_helpers (checked-source eval-path root 'eval_helpers)
              'framework_preferences (checked-source framework-path root 'framework_preferences)))
    (set! stage "original-default")
    ;; Resolve and pin first, then load the originals, never a replacement setter.
    (dynamic-require eval-path #f)
    (define get (dynamic-require framework-path 'preferences:get))
    (define set (dynamic-require framework-path 'preferences:set))
    (define default-set? (dynamic-require framework-path 'preferences:default-set?))
    (ensure (default-set? preference-key) "original helper did not register preference")
    (define original (get preference-key))
    (ensure (equal? original default-bytes) "original fresh-profile default is not 128 MiB")
    (ensure (not (gui-available?)) "original default registration initialized GUI")
    (ensure (equal? before (read-store pref-file)) "loading original modules changed preferences")
    (set! stage "persist-and-read-back")
    (set! preference-write-attempted? #t)
    (set preference-key selected)
    (define read-back (get preference-key))
    (ensure (equal? read-back selected) "registered API read-back differs from selected value")
    ;; #f permits cache reuse. #t forces a fresh read; explicit filename disables
    ;; old-profile and configuration fallbacks. See Racket 9.3 get-preference docs.
    (define persisted
      (get-preference disk-key (lambda () (error 'memory-profile "persisted key missing"))
                      #t pref-file))
    (define after (read-store pref-file))
    (ensure (and (equal? persisted selected) (only-target-addition? before after selected))
            "disk verification failed: expected only the registered key addition")
    (ensure (not (gui-available?)) "GUI initialized during profile setup")
    (emit-json
     (hasheq 'schema_version 1 'status "verified" 'phase "before-timed-gui"
             'runtime_version (version) 'runtime_root (path->string root)
             'runtime_executable (path->string executable)
             'preference_key (symbol->string preference-key)
             'persisted_preference_key (symbol->string disk-key)
             'expected_default_limit_bytes default-bytes 'original_default_limit_bytes original
             'expected_limit_bytes selected 'selected_limit_bytes selected
             'readback_limit_bytes read-back 'persisted_limit_bytes persisted
             'profile_was_empty #t 'addon_was_empty #t 'gui_initialized #f
             'legacy_preference_store_absent #t 'runtime_fallback_store_absent #t
             'profile_path (path->string home) 'addon_path (path->string addon)
             'preference_store_path (path->string pref-file)
             'preference_store_sha256 (file-sha256 pref-file)
             'disk_read_method "get-preference/#t/explicit-file + bounded direct read"
             'only_expected_preference_changed #t
             'disk_key_count_before (hash-count before) 'disk_key_count_after (hash-count after)
             'one_key_delta (list (hasheq 'key (symbol->string disk-key)
                                         'before_present #f 'after_value selected))
             'sources sources) out)
    (close-output-port out)))

(module+ main (run))

(module+ test
  (require rackunit)
  (for ([mib '(128 256 512)])
    (check-equal? (selected-limit (number->string mib)) (* mib 1024 1024)))
  (for ([bad '(#f "0" "127" "129" "1024" "256.0" "0256" "#f" "128MiB")])
    (check-exn exn:fail? (lambda () (selected-limit bad))))
  (check-true (only-target-addition? (hasheq 'unrelated '(keep me))
                                   (hasheq 'unrelated '(keep me) disk-key default-bytes)
                                   default-bytes))
  (check-false (only-target-addition? (hasheq 'unrelated 1)
                                    (hasheq 'unrelated 2 disk-key default-bytes) default-bytes))
  (check-false (only-target-addition? (hasheq disk-key default-bytes)
                                    (hasheq disk-key default-bytes) default-bytes))
  (define fixture (make-temporary-file "memory-profile-tests~a" 'directory))
  (dynamic-wind
   void
   (lambda ()
     (define original (collection-file-path "eval-helpers-and-pref-init.rkt" "drracket" "private"))
     (define copied (build-path fixture "eval.rkt"))
     (copy-file original copied)
     (check-equal? (hash-ref (checked-source copied fixture 'eval_helpers) 'sha256)
                   (hash-ref source-pins 'eval_helpers))
     (check-exn exn:fail? (lambda () (checked-source original fixture 'eval_helpers)))
     (call-with-output-file copied #:exists 'append (lambda (out) (display "\n; tampered\n" out)))
     (check-exn exn:fail? (lambda () (checked-source copied fixture 'eval_helpers)))
     (define framework-original (collection-file-path "preferences.rkt" "framework"))
     (define framework-copy (build-path fixture "preferences.rkt"))
     (copy-file framework-original framework-copy)
     (check-equal? (hash-ref (checked-source framework-copy fixture 'framework_preferences) 'sha256)
                   (hash-ref source-pins 'framework_preferences))
     (call-with-output-file framework-copy #:exists 'append (lambda (out) (display "\n; tampered\n" out)))
     (check-exn exn:fail? (lambda () (checked-source framework-copy fixture 'framework_preferences)))
     (define escaped (build-path fixture "escaped.rkt"))
     (make-file-or-directory-link original escaped)
     (check-exn exn:fail? (lambda () (checked-source escaped fixture 'eval_helpers)))
     (define store (build-path fixture "store.rktd"))
     (call-with-output-file store (lambda (out) (write '((unrelated (keep me))) out)))
     (check-equal? (read-store store) (hasheq 'unrelated '(keep me)))
     (call-with-output-file store #:exists 'truncate (lambda (out) (write '((duplicate 1) (duplicate 2)) out)))
     (check-exn exn:fail? (lambda () (read-store store)))
     (call-with-output-file store #:exists 'truncate (lambda (out) (display "#reader racket/base" out)))
     (check-exn exn:fail? (lambda () (read-store store))))
   (lambda () (delete-directory/files fixture))))
