#lang racket/base
;; Headless contract suite. Requires official full Racket 9.3, no Python, no GUI.
;; Not executed by this source-only handoff. Each fake executable is /bin/sh.
(require rackunit racket/file racket/list racket/path racket/port racket/runtime-path
         racket/string racket/system json xml/plist "make-app.rkt")
(define-runtime-path here ".")
(define-runtime-path default-frozen "../openracket-preview-memory-freeze-20261011-0520")
;; CI supplies its actual verified copy explicitly; no sibling layout required.
(define frozen
  (checked-absolute (or (getenv "OPENRACKET_BUILDER_TEST_SOURCE")
                        (path->string default-frozen))))
;; Refuse every fixture before testing if its full source identity is wrong.
(verify-source frozen)
(define (put p s [mode #o644])
  (make-directory* (path-only p))
  (call-with-output-file p (lambda (out) (display s out)) #:exists 'truncate/replace)
  (file-or-directory-permissions p mode))
(define (read-lines p) (string-split (file->string p) "\n"))
(define (env-set env key value)
  (environment-variables-set! env (string->bytes/utf-8 key) (and value (string->bytes/utf-8 value))))
(define (env-ref env key)
  (define b (environment-variables-ref env (string->bytes/utf-8 key)))
  (and b (bytes->string/utf-8 b)))
(define (with-fixture proc [inherited-claims? #t])
  (define root (canonical-path (make-temporary-file "openracket-contract-~a" 'directory)))
  (dynamic-wind void
    (lambda ()
      (define source (build-path root "Preview ' λ $dollar folder"))
      (make-directory* (build-path source "scripts"))
      (make-directory (build-path source "profile"))
      (for ([name '("launch-openracket.sh" "proof-env.sh" "preflight.rkt")])
        (copy-file (build-path frozen "scripts" name) (build-path source "scripts" name)))
      (define racket (build-path root "Official Racket ' λ" "racket"))
      (put racket #<<RUNTIME
#!/bin/sh
printf '%s\n' "$@" >> "$TEST_CALLS"
if [ "$#" = 2 ] && [ "$1" = -e ] && [ "$2" = '(display (version))' ]; then
  printf '%s' "${TEST_VERSION:-9.3}"
elif [ "$#" = 2 ] && [ "$1" = -e ] && [ "$2" = '(display (system-type))' ]; then
  printf macosx
else
  for arg do
    case "$arg" in */preflight.rkt)
      if [ "${TEST_PREFLIGHT_FAIL:-0}" = 1 ]; then echo 'fake preflight failed' >&2; exit 17; fi
      printf '{"status":"passed","fake":true}\n';;
    esac
  done
fi
RUNTIME
           #o755)
      (define bundle (build-path root "App folder ' λ" "OpenRacket Preview.app"))
      (define native (build-path bundle "Contents/MacOS/OpenRacket Preview"))
      (put native #<<NATIVE
#!/bin/sh
printf '%s\n' "$@" > "$TEST_CAPTURE.args"
/usr/bin/env > "$TEST_CAPTURE.env"
pwd -P > "$TEST_CAPTURE.cwd"
printf '%s\n' "$$" > "$TEST_CAPTURE.pid"
NATIVE
           #o755)
      (call-with-output-file (build-path bundle "Contents/Info.plist")
        (lambda (out) (write-plist '(dict (assoc-pair "CFBundleExecutable" "OpenRacket Preview")
                                          (assoc-pair "CFBundleIdentifier" "org.racket-lang.example")
                                          (assoc-pair "CFBundleIconFile" "Starter.icns")
                                          ;; Simulate inherited generator claims, including
                                          ;; an extension claim and a UTI/wildcard claim.
                                          (assoc-pair "CFBundleDocumentTypes"
                                            (array
                                              (dict (assoc-pair "CFBundleTypeName" "Inherited source")
                                                    (assoc-pair "CFBundleTypeRole" "Editor")
                                                    (assoc-pair "CFBundleTypeExtensions" (array "rkt" "rktl" "ss" "scm" "wxme"))
                                                    (assoc-pair "LSHandlerRank" "Owner"))
                                              (dict (assoc-pair "CFBundleTypeName" "Inherited fallback")
                                                    (assoc-pair "CFBundleTypeRole" "Viewer")
                                                    (assoc-pair "CFBundleTypeExtensions" (array "*"))
                                                    (assoc-pair "LSItemContentTypes" (array "public.text"))
                                                    (assoc-pair "LSHandlerRank" "Alternate"))))
                                          (assoc-pair "LSUIElement" (true))) out)))
      (unless inherited-claims?
        (define info-path (build-path bundle "Contents/Info.plist"))
        (define info (call-with-input-file info-path read-plist))
        (call-with-output-file info-path
          (lambda (out)
            (write-plist
              (cons 'dict (filter (lambda (a) (not (equal? (cadr a) "CFBundleDocumentTypes"))) (cdr info)))
              out))
          #:exists 'truncate/replace))
      (define native-before (file->bytes native))
      (decorate-bundle bundle source racket "saved")
      ;; Mock only the alert transport in fixtures: failure cases must not open
      ;; real modal dialogs. Native acceptance tests the unchanged real script.
      (put (build-path bundle "Contents/Resources/report-error.applescript") "on run argv\nreturn\nend run\n")
      (define env (environment-variables-copy (current-environment-variables)))
      (env-set env "TEST_CAPTURE" (path->string (build-path root "capture")))
      (env-set env "TEST_CALLS" (path->string (build-path root "calls")))
      (for ([key '("TEST_VERSION" "TEST_PREFLIGHT_FAIL")]) (env-set env key #f))
      (proc root source racket bundle native native-before env))
    (lambda () (delete-directory/files root))))
(define (launch root bundle env [args null])
  (parameterize ([current-environment-variables env] [current-directory root])
    (define-values (process stdout stdin stderr)
      (apply subprocess #f #f #f (build-path bundle "Contents/MacOS/OpenRacket-launch") args))
    (define pid (subprocess-pid process))
    (close-output-port stdin)
    ;; Tests emit only tiny outputs; never call real GUI code from this fixture.
    (define out (port->string stdout)) (define err (port->string stderr))
    (subprocess-wait process)
    (close-input-port stdout) (close-input-port stderr)
    (values (subprocess-status process) out err pid)))
(define (captured-env root)
  (for/hash ([line (in-list (read-lines (build-path root "capture.env")))])
    (define pieces (regexp-match #rx"^([^=]+)=(.*)$" line))
    (values (cadr pieces) (caddr pieces))))
(define (args root) (read-lines (build-path root "capture.args")))
(define-syntax-rule (fixture-test name (root source racket bundle native native-before env) body ...)
  (test-case name (with-fixture (lambda (root source racket bundle native native-before env) body ...))))
(module+ test
  (test-case "01 exact frozen manifest" (verify-source frozen))
  (fixture-test "02 native executable unchanged"
    (root source racket bundle native native-before env)
    (check-equal? (file->bytes native) native-before))
  (fixture-test "03 normal metadata without inherited or generated document claims"
    (root source racket bundle native native-before env)
    (define info (call-with-input-file (build-path bundle "Contents/Info.plist") read-plist))
    (define h (for/hash ([a (in-list (cdr info))]) (values (cadr a) (caddr a))))
    (check-equal? (hash-ref h "CFBundleExecutable") "OpenRacket-launch")
    (check-equal? (hash-ref h "CFBundlePackageType") "APPL")
    (check-false (hash-has-key? h "LSUIElement"))
    (check-false (hash-has-key? h "LSEnvironment"))
    (check-equal? (hash-ref h "LSMultipleInstancesProhibited") '(true))
    (check-false (hash-has-key? h "CFBundleDocumentTypes"))
    (check-equal? (hash-ref h "CFBundleIconFile") "Starter.icns")
    (check-false (hash-has-key? h "UTExportedTypeDeclarations"))
    (check-false (hash-has-key? h "UTImportedTypeDeclarations"))
    ;; Also prove a generator without any document key gains no new claim.
    (with-fixture
      (lambda (root source racket bundle native native-before env)
        (define info (call-with-input-file (build-path bundle "Contents/Info.plist") read-plist))
        (check-false (assoc "CFBundleDocumentTypes" (map cdr (cdr info))))
        (check-equal? (file->bytes native) native-before))
      #f))
  (fixture-test "04 spaces Unicode quotes argv and exec PID"
    (root source racket bundle native native-before env)
    ;; Feed an actual trailing-slash source through the same CLI canonicalizer
    ;; and configuration serializer, then prove native routing and PID below.
    (define with-slash (checked-absolute (string-append (path->string source) "/")))
    (check-equal? (path->string with-slash) (path->string source))
    (check-equal? (checked-absolute (string-append (path->string source) "/.")) source)
    (put (build-path bundle "Contents/Resources/openracket-config.sh")
         (config-shell with-slash racket "OpenRacket Preview" "saved"))
    (define names (list "relative λ ' $.rkt" "--check" (path->string (build-path root "absolute with spaces.rkt"))))
    (define-values (code out err pid) (launch root bundle env names))
    (check-equal? code 0 err)
    (check-equal? (take (args root) 7)
                  (list "-A" (path->string (build-path source "profile/.local/share/racket"))
                        "-R" (string-append (path->string (build-path source "profile/compiled-cache")) ":") "-l" "drracket" "--"))
    (check-equal? (drop (args root) 7) (map (lambda (p) (path->string (path->complete-path p root))) names))
    (check-equal? (string->number (string-trim (file->string (build-path root "capture.pid")))) pid))
  (fixture-test "05 poisoned launch environment cleared"
    (root source racket bundle native native-before env)
    (for ([key (append isolation-overrides '("OPENRACKET_MEMORY_LIMIT_MIB" "OPENRACKET_THEME"))]) (env-set env key "poison"))
    (env-set env "OPENRACKET_UI" "stock") (env-set env "OPENRACKET_HOST_THEME" "0")
    (define-values (code out err pid) (launch root bundle env)) (check-equal? code 0 err)
    (define actual (captured-env root))
    (for ([key (append isolation-overrides '("OPENRACKET_MEMORY_LIMIT_MIB" "OPENRACKET_THEME"))])
      (check-false (hash-has-key? actual key)))
    (for ([pair '(("OPENRACKET_UI" . "modern") ("OPENRACKET_HOST_THEME" . "1")
                  ("OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD" . "1") ("OPENRACKET_NATIVE_APPEARANCE" . "1"))])
      (check-equal? (hash-ref actual (car pair)) (cdr pair)))
    (check-equal? (hash-ref actual "RACKET") (path->string racket))
    (check-equal? (hash-ref actual "PLTUSERHOME") (path->string (build-path source "profile"))))
  (fixture-test "06 explicit theme"
    (root source racket bundle native native-before env)
    (put (build-path bundle "Contents/Resources/openracket-config.sh") (config-shell source racket "OpenRacket Preview" "dark"))
    (define-values (code out err pid) (launch root bundle env)) (check-equal? code 0 err)
    (check-equal? (hash-ref (captured-env root) "OPENRACKET_THEME") "dark"))
  (fixture-test "07 old Finder flag ignored"
    (root source racket bundle native native-before env)
    (define-values (code out err pid) (launch root bundle env '("-psn_123_456" "file.rkt")))
    (check-equal? code 0 err) (check-equal? (drop (args root) 7) (list (path->string (build-path root "file.rkt")))))
  (fixture-test "08 PSN-like filename preserved"
    (root source racket bundle native native-before env)
    (define-values (code out err pid) (launch root bundle env '("-psn_x_456")))
    (check-equal? code 0 err) (check-equal? (drop (args root) 7) (list (path->string (build-path root "-psn_x_456")))))
  (fixture-test "09 failed preflight does not launch"
    (root source racket bundle native native-before env)
    (env-set env "TEST_PREFLIGHT_FAIL" "1")
    (define-values (code out err pid) (launch root bundle env))
    (check-not-equal? code 0) (check-regexp-match #rx"preview check failed" err)
    (check-false (file-exists? (build-path root "capture.pid"))))
  (fixture-test "10 wrong runtime version"
    (root source racket bundle native native-before env)
    (env-set env "TEST_VERSION" "9.4")
    (define-values (code out err pid) (launch root bundle env))
    (check-not-equal? code 0) (check-regexp-match #rx"preview check failed" err)
    (check-false (file-exists? (build-path root "capture.pid"))))
  (fixture-test "11 missing runtime"
    (root source racket bundle native native-before env)
    (delete-file racket)
    (define-values (code out err pid) (launch root bundle env))
    (check-not-equal? code 0) (check-regexp-match #rx"configured Racket 9.3 executable is missing" err))
  (fixture-test "12 empty filename refused"
    (root source racket bundle native native-before env)
    (define-values (code out err pid) (launch root bundle env '("")))
    (check-not-equal? code 0) (check-regexp-match #rx"empty filename" err))
  (fixture-test "13 managed profile symlinks refused without writes"
    (root source racket bundle native native-before env)
    (for ([child '("profile" "profile/.local" "profile/.local/share" "profile/.local/share/racket" "profile/.cache" "profile/compiled-cache")])
      (define profile (build-path source "profile"))
      (if (link-exists? profile) (delete-file profile) (delete-directory/files profile))
      (define link (build-path source child))
      (make-directory* (path-only link))
      (define outside (build-path root (string-replace child "/" "-")))
      (make-directory outside) (make-file-or-directory-link outside link)
      (define-values (code out err pid) (launch root bundle env))
      (check-not-equal? code 0) (check-regexp-match #rx"symbolic link" err)
      (check-equal? (directory-list outside) null)))
  (fixture-test "14 bundle relocation"
    (root source racket bundle native native-before env)
    (define moved (build-path root "Moved app ' λ.app")) (rename-file-or-directory bundle moved)
    (define-values (code out err pid) (launch root moved env)) (check-equal? code 0 err)
    (check-equal? (string-trim (file->string (build-path root "capture.cwd"))) (path->string source)))
  (fixture-test "15 exact final invocation only"
    (root source racket bundle native native-before env)
    (parameterize ([current-environment-variables env])
      (check-true (system* (build-path bundle "Contents/Resources/runtime-dispatch.sh") "-A" "/wrong" "-R" "/wrong:" "-l" "drracket" "--")))
    (check-false (file-exists? (build-path root "capture.pid")))
    (check-regexp-match #rx"/wrong" (file->string (build-path root "calls"))))
  (fixture-test "16 builder platform or existing output refusal"
    (root source racket bundle native native-before env)
    (check-exn (if (eq? (system-type) 'macosx) #rx"existing paths are never replaced" #rx"must run on macOS")
               (lambda () (build source racket bundle "saved" (path-only racket)))))
  (fixture-test "17 canonical runtime layout and boundaries"
    (root source racket bundle native native-before env)
    (define runtime-root (build-path root "Full official runtime"))
    (for ([name '("bin" "collects/racket" "etc" "lib")]) (make-directory* (build-path runtime-root name)))
    (for ([name '("bin/racket" "bin/raco" "collects/racket/base.rkt")]) (put (build-path runtime-root name) "fixture"))
    (define selected (build-path runtime-root "bin/racket")) (define output (build-path root "new.app"))
    (verify-runtime-boundary runtime-root selected source output)
    (for ([locations (list (list (build-path runtime-root "preview") output)
                          (list source (build-path runtime-root "new.app")) (list root output))])
      (check-exn exn:fail? (lambda () (verify-runtime-boundary runtime-root selected (car locations) (cadr locations)))))
    (define alias (build-path root "runtime-alias")) (make-file-or-directory-link runtime-root alias)
    (check-exn exn:fail? (lambda () (verify-runtime-boundary runtime-root selected source (build-path alias "new.app"))))
    (check-exn exn:fail? (lambda () (verify-runtime-boundary runtime-root racket source output))))
  (fixture-test "18 queried runtime report boundaries"
    (root source racket bundle native native-before env)
    (define r (build-path root "Runtime"))
    (define report (hash 'version "9.3" 'os "macosx" 'collects (path->string (build-path r "collects"))
                         'config (path->string (build-path r "etc")) 'lib (path->string (build-path r "lib"))
                         'pkgs (path->string (build-path r "share/pkgs")) 'console-bin (path->string (build-path r "bin"))
                         'gui-bin (path->string r) 'gui-exe (path->string (build-path r "lib/GRacket.app/Contents/MacOS/GRacket"))))
    (verify-runtime-report report r)
    (verify-runtime-report
      (for/fold ([v report]) ([key '(collects config console-bin)])
        (hash-set v key (string-append (hash-ref v key) "/"))) r)
    ;; macOS /var is commonly a symlink to /private/var. Check both directions
    ;; only where those paths actually denote the same canonical location.
    (when (and (directory-exists? "/var") (directory-exists? "/private/var")
               (equal? (explode-path (canonical-path "/var"))
                       (explode-path (canonical-path "/private/var"))))
      (check-true (inside? "/var" "/private/var"))
      (check-true (inside? "/private/var" "/var")))
    (for ([key '(collects config lib pkgs console-bin gui-bin gui-exe)])
      (check-exn exn:fail? (lambda () (verify-runtime-report (hash-set report key "/outside") r)))))
  (fixture-test "19 build environment overrides"
    (root source racket bundle native native-before env)
    (for ([key (append isolation-overrides '("OPENRACKET_MEMORY_LIMIT_MIB"))]) (env-set env key "poison"))
    (define clean (parameterize ([current-environment-variables env]) (isolated-environment source racket "saved")))
    (for ([key (append isolation-overrides '("OPENRACKET_MEMORY_LIMIT_MIB"))]) (check-false (env-ref clean key)))
    (check-equal? (env-ref clean "PLTCOMPILEDROOTS") (string-append (path->string (build-path source "profile/compiled-cache")) ":")))
  (test-case "20 malformed configuration paths"
    (for ([value '("relative" "/tmp/bad\nname" "/tmp/bad\rname" "/tmp/bad\u0000name")])
      (check-exn exn:fail? (lambda () (checked-absolute value #:exists? #f))))))
