#lang racket/base
;; One-key, headless setup/rollback for this tree's isolated profile.
;; Never require this module in the DrRacket host or replace its defaults.
(require file/sha1 json racket/file racket/list racket/path
         racket/random racket/runtime-path racket/gui/dynamic setup/dirs)

(define-runtime-path source-root "..")
(define key 'drracket:child-only-memory-limit)
(define disk-key 'plt:framework-pref:drracket:child-only-memory-limit)
(define stock-bytes (* 128 1024 1024))
(define preview-bytes (* 256 1024 1024))
(define marker-name ".openracket-memory-default.json")
(define origin "openracket-fresh-profile-memory-v1")
(define pins
  (list (list "eval-helpers-and-pref-init.rkt" '("drracket" "private")
              "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62")
        (list "preferences.rkt" '("framework")
              "59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c")))

(define (ensure ok? message . args)
  (unless ok? (apply error 'openracket-memory message args)))
(define (exists? p)
  (or (file-exists? p) (directory-exists? p) (link-exists? p)))
;; Resolve ancestor links too, including macOS /var -> /private/var.
(define (physical p [depth 0])
  (ensure (< depth 64) "too many path links")
  (define parts (explode-path (path->complete-path p)))
  (for/fold ([base (car parts)]) ([part (in-list (cdr parts))])
    (define next (simplify-path (build-path base part) #f))
    (if (link-exists? next)
        (physical (path->complete-path (resolve-path next) (path-only next)) (add1 depth))
        next)))
;; Directory identity needs one representation: the native probe showed root's
;; trailing separator survives '..', while physical(split-path base) drops it.
(define (physical-directory p) (path->directory-path (physical p)))
(define root (physical-directory source-root))
(define profile (build-path root "profile"))
(define addon (build-path profile ".local/share/racket"))
(define marker (build-path profile marker-name))
(define (profile-aliases)
  (for/list ([p (in-list (list profile (build-path source-root "profile")
                              (or (getenv "PLTUSERHOME") profile)))]
             #:do [(define path (simplify-path (path->complete-path p) #f))
                   (define-values (base name directory?) (split-path path))]
             ;; split-path retains a directory's last name; file-name-from-path
             ;; returns #f for a syntactically directory-valued profile path.
             #:when (and (equal? name (string->path "profile"))
                         (path? base) (equal? (physical-directory base) root)))
    path))
(define (confined p)
  (define target (simplify-path (path->complete-path p) #f))
  ;; Root aliases (/var versus /private/var, or a symlink to this source tree)
  ;; are allowed. Never resolve away a symlink at/below the profile boundary.
  (define match
    (for/or ([boundary (in-list (profile-aliases))])
      ;; The default #:more-than-same? #t returns an ABSOLUTE path for self.
      ;; We intentionally permit the boundary itself, subject to its link check.
      (define relative (find-relative-path boundary target #:more-than-same? #f))
      (and (relative-path? relative) (not (memq 'up (explode-path relative)))
           (cons boundary relative))))
  (ensure match "path escapes isolated profile: ~a" target)
  (define boundary (car match))
  (define relative (cdr match))
  (ensure (not (link-exists? boundary)) "symbolic-link profile is refused")
  (for/fold ([at boundary]) ([part (in-list (explode-path relative))])
    (define next (build-path at part))
    (ensure (not (link-exists? next)) "symbolic-link profile path is refused: ~a" next)
    next)
  (simplify-path (build-path profile relative) #f))
(define (check-environment)
  (ensure (equal? (version) "9.3") "requires exact Racket 9.3")
  (for ([name '("PLTUSERHOME" "OPENRACKET_PROFILE")])
    (define value (getenv name))
    (ensure (and value (complete-path? value) (equal? (physical value) profile))
            "~a must name this source tree's isolated profile" name))
  (confined profile)
  (ensure (equal? (physical (find-system-path 'home-dir)) profile) "PLTUSERHOME is inactive")
  (ensure (equal? (physical (find-system-path 'addon-dir)) addon) "isolated addon is inactive")
  (confined addon)
  (confined marker)
  (confined (find-system-path 'pref-file)))
(define (limit-mib text)
  (ensure (and (string? text) (regexp-match? #px"^[1-9][0-9]*$" text))
          "limit must be an integer MiB value of at least 8")
  (define value (string->number text))
  (ensure (and (exact-integer? value) (>= value 8)) "limit must be at least 8 MiB")
  (* value 1024 1024))
(define (read-marker)
  (cond
    [(not (exists? marker)) #f]
    [else
     (ensure (and (file-exists? marker) (<= (file-size marker) 8192)) "invalid ownership marker")
     (define data (call-with-input-file marker read-json))
     (ensure (and (hash? data) (equal? (hash-ref data 'origin #f) origin)
                  (equal? (hash-ref data 'profile #f) (path->string profile))
                  (member (hash-ref data 'state #f)
                          '("pending" "checking" "writing" "owned" "preserved" "explicit" "restoring" "restored")))
             "unrecognized ownership marker; no preferences changed")
     data]))
(define (write-marker data)
  (confined marker)
  (call-with-atomic-output-file marker
    (lambda (out temporary) (write-json data out) (newline out))))
(define (with-state data state)
  (hash-set data 'state state))
(define (read-store pref-file)
  (confined pref-file)
  (cond
    [(not (exists? pref-file)) (hasheq)]
    [else
     (ensure (and (file-exists? pref-file) (<= (file-size pref-file) (* 1024 1024)))
             "preference store is invalid or larger than 1 MiB")
     (call-with-input-file pref-file
       (lambda (in)
         (parameterize ([read-accept-reader #f] [read-accept-lang #f]
                        [read-accept-graph #f] [read-accept-compiled #f])
           (define entries (read in))
           (ensure (and (list? entries) (<= (length entries) 4096)
                        (andmap (lambda (v) (and (list? v) (= (length v) 2) (symbol? (car v)))) entries)
                        (eof-object? (read in))) "invalid preference store")
           (define result (make-immutable-hasheq (map (lambda (v) (cons (car v) (cadr v))) entries)))
           (ensure (= (hash-count result) (length entries)) "duplicate preference key")
           result)))]))
(define (fallback-present?)
  ;; The standard preference API can inherit these if its local file is absent.
  ;; Do not import or overwrite a stock-installation/user fallback store.
  (define legacy
    (case (system-type 'os)
      [(unix) (expand-user-path "~/.plt-scheme/plt-prefs.ss")]
      [(macosx) (build-path (find-system-path 'pref-dir) "org.plt-scheme.prefs.ss")]
      [(windows) (build-path (find-system-path 'pref-dir) 'up "PLT Scheme" "plt-prefs.ss")]
      [else (error 'openracket-memory "unsupported preference platform")]))
  (define config (find-config-dir))
  (or (exists? legacy) (and config (exists? (build-path config "racket-prefs.rktd")))))
(define (load-api pref-file)
  (ensure (not (gui-available?)) "memory helper must run before GUI initialization")
  ;; Pin BOTH sources before loading either. The GUI package may be our complete
  ;; private copy, while DrRacket itself may still be installation-scoped.
  (define paths
    (for/list ([pin (in-list pins)])
      (define p (apply collection-file-path (car pin) (cadr pin)))
      (ensure (and (file-exists? p) (<= (file-size p) (* 1024 1024))
                   (equal? (bytes->hex-string (sha256-bytes (file->bytes p))) (caddr pin)))
              "source differs from the pinned official 9.3 module: ~a" p)
      p))
  (dynamic-require (car paths) #f)
  (define get (dynamic-require (cadr paths) 'preferences:get))
  (define set (dynamic-require (cadr paths) 'preferences:set))
  (define low-put (dynamic-require (cadr paths) 'preferences:low-level-put-preferences))
  (ensure (not (gui-available?)) "loading the original preference API initialized the GUI")
  (values get
          (lambda (key value)
            ;; Supported framework parameter, only in this short-lived process.
            ;; An explicit filename prevents legacy/config fallback preferences
            ;; from being imported when the local file does not exist.
            (parameterize ([low-put (lambda (keys values)
                                      (put-preferences keys values #f pref-file))])
              (set key value)))))
(define (json-result state pref-file get [data (read-marker)])
  (define store (read-store pref-file))
  (hasheq 'status state 'runtime_version (version) 'platform (symbol->string (system-type 'os))
          'preference_key (symbol->string key) 'profile (path->string profile)
          'preference_store (path->string pref-file)
          'persisted (hash-has-key? store disk-key)
          'effective_limit_bytes (get key)
          'persisted_limit_bytes (hash-ref store disk-key 'null)
          'ownership_state (if data (hash-ref data 'state) "unowned")
          'gui_initialized (gui-available?)
          'affects "Run and background analysis"))
(define (write-value! pref-file get set before value)
  (ensure (or (exists? pref-file) (not (fallback-present?)))
          "fallback preferences exist; refusing to import them into this profile")
  (ensure (equal? before (read-store pref-file)) "preferences changed during operation; close DrRacket and retry")
  (set key value)
  (ensure (and (equal? (get key) value)
               (equal? (get-preference disk-key (lambda () 'missing) #t pref-file) value)
               (equal? (read-store pref-file) (hash-set before disk-key value)))
          "preference write verification failed; inspect --status before continuing")
  (ensure (not (gui-available?)) "preference mutation initialized the GUI"))

(define absent-snapshot (hasheq 'store_present #f 'store_sha256 'null 'store_entries (hasheq)))
(define (store-snapshot pref-file)
  (define entries (read-store pref-file))
  (hasheq 'store_present (and (file-exists? pref-file) #t)
          'store_sha256 (if (file-exists? pref-file)
                           (bytes->hex-string (sha256-bytes (file->bytes pref-file))) 'null)
          ;; Reservation only succeeds for an absent store. Do not put arbitrary
          ;; private preference values into the ownership marker.
          'store_entries (if (zero? (hash-count entries)) (hasheq) 'nonempty)))
(define (with-operation-lock thunk)
  (ensure (directory-exists? profile) "profile does not exist; run setup first")
  (define lock-file (confined (build-path profile ".openracket-memory-operation.lock")))
  (call-with-file-lock/timeout #f 'exclusive thunk
    (lambda () (error 'openracket-memory "another memory helper is active; retry after it exits"))
    #:lock-file lock-file))
(define (reserve pref-file)
  (define chosen (getenv "OPENRACKET_MEMORY_LIMIT_MIB"))
  (define selected (if chosen (limit-mib chosen) preview-bytes))
  (cond
    [(exists? profile) (ensure (directory-exists? profile) "profile is not a directory") "existing"]
    [else
     ;; Atomic creation establishes freshness, before package/setup mkdirs. A
     ;; failed reservation leaves an existing, unowned profile, never a fresh one.
     (make-directory profile)
     (define snapshot (store-snapshot pref-file))
     (ensure (equal? snapshot absent-snapshot) "preferences appeared during profile reservation")
     (define token (bytes->hex-string (crypto-random-bytes 24)))
     (write-marker (hasheq 'origin origin 'profile (path->string profile)
                          'state "pending" 'token token 'selected selected
                          'automatic (not chosen) 'previous stock-bytes
                          'reservation snapshot))
     token]))
(define (initialize token pref-file)
  (cond
    [(equal? token "existing")
     (hasheq 'status "preserved" 'reason token)]
    [else
     (define data (read-marker))
     (ensure (and data (equal? (hash-ref data 'state) "pending")
                  (equal? (hash-ref data 'token #f) token)) "fresh-profile grant is absent or consumed")
     ;; Consume the token before source/API loading or any initialization check.
     ;; An interrupted/failed attempt cannot later be mistaken for fresh setup.
     (write-marker (with-state data "checking"))
     (ensure (and (equal? (hash-ref data 'reservation #f) absent-snapshot)
                  (exact-integer? (hash-ref data 'selected #f))
                  (>= (hash-ref data 'selected) (* 8 1024 1024))
                  (boolean? (hash-ref data 'automatic 'missing))) "invalid fresh-profile reservation")
     (cond
       ;; Even an empty preference file can mean an explicitly used profile.
       [(or (not (equal? (store-snapshot pref-file) absent-snapshot)) (fallback-present?))
        (write-marker (with-state data "preserved"))
        (hasheq 'status "preserved" 'reason "preferences appeared or a fallback exists")]
       [else
        (define-values (get set) (load-api pref-file))
        (define before (read-store pref-file))
        (ensure (and (not (exists? pref-file)) (equal? (get key) stock-bytes))
                "fresh profile does not have the original stock 128 MiB default")
        (write-marker (with-state data "writing"))
        (write-value! pref-file get set before (hash-ref data 'selected))
        (write-marker (with-state data (if (hash-ref data 'automatic) "owned" "explicit")))
        (json-result "initialized" pref-file get)])]))
(define (change command argument pref-file)
  (ensure (directory-exists? profile) "profile does not exist; run setup first")
  (define data (read-marker))
  (define before (read-store pref-file))
  (define-values (get set) (load-api pref-file))
  (cond
    [(equal? command "--status") (json-result "observed" pref-file get data)]
    [else
     (define restore? (equal? command "--restore"))
     (define value (cond [restore? stock-bytes]
                         [(equal? command "--unlimited") #f]
                         [else (limit-mib argument)]))
     (when restore?
       (ensure (and data (equal? (hash-ref data 'state) "owned")
                    (equal? (hash-ref data 'automatic #f) #t)
                    (equal? (hash-ref data 'previous #f) stock-bytes)
                    (equal? (hash-ref data 'selected #f) preview-bytes)
                    (equal? (hash-ref before disk-key 'missing) preview-bytes)
                    (equal? (get key) preview-bytes))
               "restore refused: no intact owned 256 MiB value; explicit choices are preserved (use --set-mib 128 to request a change)"))
     (ensure (or (exists? pref-file) (not (fallback-present?))) "fallback store exists; refusing preference mutation")
     ;; Relinquish ownership BEFORE an explicit edit, including a same-value edit.
     ;; Interrupted writes remain non-restorable instead of guessing provenance.
     (define next (or data (hasheq 'origin origin 'profile (path->string profile))))
     (write-marker (with-state next (if restore? "restoring" "explicit")))
     (write-value! pref-file get set before value)
     (when restore? (write-marker (with-state next "restored")))
     (json-result (if restore? "restored" "selected") pref-file get)]))

(module+ main
  (define arguments (vector->list (current-command-line-arguments)))
  (ensure (or (member arguments '(("--reserve") ("--status") ("--restore") ("--unlimited")))
              (and (= (length arguments) 2) (member (car arguments) '("--initialize" "--set-mib"))))
          "usage: memory-profile.sh --status | --set-mib N | --unlimited | --restore")
  (define pref-file (check-environment))
  (define command (car arguments))
  (cond
    [(equal? command "--reserve") (displayln (reserve pref-file))]
    [else
     (define (perform)
       (if (equal? command "--initialize")
           (initialize (cadr arguments) pref-file)
           (change command (and (= (length arguments) 2) (cadr arguments)) pref-file)))
     (write-json (if (equal? command "--status") (perform) (with-operation-lock perform)))
     (newline)]))

(module+ test
  (require rackunit)
  ;; Exact native-probe regression: these paths name the same directory but raw
  ;; equal? rejects its trailing-separator variation. Canonicalize only directory
  ;; identity, leaving lexical containment and descendant-link checks unchanged.
  (define-values (profile-base profile-name profile-directory?) (split-path profile))
  (define physical-profile-base (physical profile-base))
  (check-false (equal? physical-profile-base root))
  (check-equal? (explode-path physical-profile-base) (explode-path root))
  (check-equal? (physical-directory profile-base) root)
  (check-equal? (physical-directory (path->directory-path profile-base)) root)
  (check-equal? (physical-directory source-root) root)
  (check-not-false (member profile (profile-aliases)))
  ;; These path contracts run without profile creation or preference writes.
  ;; In particular, self must be accepted before reserve can create the profile.
  (check-not-exn (lambda () (confined profile)))
  (check-not-exn (lambda () (confined (path->directory-path profile))))
  (define child (build-path profile ".guard-probe" "nested.pref"))
  (check-equal? (confined child) child)
  (check-exn exn:fail? (lambda () (confined root)))
  (check-exn exn:fail? (lambda () (confined (build-path root "profile-sibling" "prefs"))))
  (check-exn exn:fail? (lambda () (confined (build-path profile 'up "outside"))))
  (for ([mib '(8 128 256 512 768)])
    (check-equal? (limit-mib (number->string mib)) (* mib 1024 1024)))
  (for ([bad '(#f "0" "7" "-1" "256.0" "0256" " 256" "#f" "unlimited")])
    (check-exn exn:fail? (lambda () (limit-mib bad)))))
