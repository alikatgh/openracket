#lang racket/base
;; PREPARED, NOT EXECUTED. Native GUI and disposable profile required.
;; Call run-independent-native-save-check! on a genuine disposable DrRacket
;; frame's handler thread, in separate stock / candidate-off / candidate-on runs.
;; Do not load this module on an unauthorized local/native display.
(require racket/class racket/file racket/gui/base racket/list racket/port
         framework rackunit)
(provide run-independent-native-save-check!)

(define (snips editor)
  (let loop ([s (send editor find-first-snip)] [out '()])
    (if s (loop (send s next) (cons s out)) (reverse out))))
(define (bitmap-data bm)
  (define pixels (make-bytes (* 4 (send bm get-width) (send bm get-height))))
  (send bm get-argb-pixels 0 0 (send bm get-width) (send bm get-height) pixels)
  (list (send bm get-width) (send bm get-height) pixels))
(define (payload editor)
  ;; Ignore incidental coalescing of adjacent native string snips.
  (reverse
   (for/fold ([out '()]) ([s (in-list (snips editor))])
     (define item
       (cond [(is-a? s image-snip%) (cons 'image (bitmap-data (send s get-bitmap)))]
             [(is-a? s editor-snip%) (list 'editor (payload (send s get-editor)))]
             [(is-a? s string-snip%) (list 'string (send s get-text 0 (send s get-count)))]
             [else (error 'native-gate "Unexpected snip class; preserve evidence")]))
     (if (and (pair? out) (eq? (car item) 'string) (eq? (caar out) 'string))
         (cons (list 'string (string-append (cadar out) (cadr item))) (cdr out))
         (cons item out)))))
(define (wxme? file)
  (define bytes (file->bytes file))
  (and (regexp-match? #rx#"WXME" (subbytes bytes 0 (min 1024 (bytes-length bytes)))) #t))
(define (reopen file)
  (define fresh (new text%))
  (check-true (send fresh load-file file 'guess #f))
  fresh)
(define (add-rich! editor)
  (define bm (make-bitmap 7 5 #t))
  (define pixels (make-bytes (* 4 7 5) 113))
  (for ([i (in-range 0 (bytes-length pixels) 4)]) (bytes-set! pixels i 255))
  (send bm set-argb-pixels 0 0 7 5 pixels)
  (define nested (new text%)) (send nested insert "nested café λ 日本語\n")
  (send editor insert (make-object image-snip% bm) (send editor last-position))
  (send editor insert (new editor-snip% [editor nested]) (send editor last-position)))

(define (run-independent-native-save-check! frame mode)
  (unless (memq mode '(stock candidate-off candidate-on))
    (error 'native-gate "Expected stock, candidate-off, or candidate-on"))
  (unless (eq? (current-thread) (eventspace-handler-thread (send frame get-eventspace)))
    (error 'native-gate "Must run on the real frame's handler thread"))
  (parameterize ([current-check-handler raise])
    (define selected?
      (dynamic-require 'framework/private/text-misc
                       'openracket-experimental-save-scan-guard? (lambda () 'not-exported)))
    (check-equal? selected? (case mode [(stock) 'not-exported] [(candidate-off) #f] [else #t]))
    (check-false (preferences:get 'framework:verify-change-format)
                 "Pinned fresh-stock default must be #f; this fixture never changes preferences")
    (define defs (send frame get-definitions-text))
    (check-equal? (send defs last-position) 0 "Use a fresh disposable frame; never overwrite a working buffer")
    (check-false (send defs get-filename) "Use an unnamed disposable buffer")
    (define dir (make-temporary-file "openracket-autosave-native-~a" 'directory))
    (define (reset! text name format)
      (send defs erase)
      (send defs set-filename (build-path dir name))
      (send defs insert text)
      (send defs set-file-format format)
      (send defs set-modified #t))
    (define plain "#lang racket/base\n;; café λ 日本語\n(+ 20 22)\n")
    ;; Real ordinary same-format save: required conversion from standard to text.
    (reset! plain "plain.rkt" 'standard)
    (define plain-path (send defs get-filename))
    (check-true (send defs save-file plain-path 'same #f))
    (check-equal? (file->bytes plain-path) (string->bytes/utf-8 plain))
    (check-eq? (send defs get-file-format) 'text)
    (check-false (send defs is-modified?))
    ;; Real copy save must leave filename and modified state alone.
    (send defs insert ";; copied\n" (send defs last-position))
    (define before-copy (send defs get-text))
    (define copy-path (build-path dir "plain-copy.rkt"))
    (check-true (send defs save-file copy-path 'copy #f))
    (check-equal? (file->bytes copy-path) (string->bytes/utf-8 before-copy))
    (check-equal? (send defs get-filename) plain-path)
    (check-true (send defs is-modified?))
    ;; Rich same-format save must change text to standard, then preserve image
    ;; pixels and nested-editor data on both ordinary-save and copy round trips.
    (reset! plain "rich.wxme" 'text)
    (add-rich! defs)
    (define expected-rich (payload defs))
    (define rich-path (send defs get-filename))
    (check-true (send defs save-file rich-path 'same #f))
    (check-eq? (send defs get-file-format) 'standard)
    (check-true (wxme? rich-path))
    (check-equal? (payload (reopen rich-path)) expected-rich)
    (send defs set-modified #t)
    (define rich-copy (build-path dir "rich-copy.wxme"))
    (check-true (send defs save-file rich-copy 'copy #f))
    (check-true (wxme? rich-copy))
    (check-equal? (payload (reopen rich-copy)) expected-rich)
    (check-equal? (send defs get-filename) rich-path)
    (check-true (send defs is-modified?))
    ;; Actual stock do-autosave path selects format, creates a recovery artifact,
    ;; and restores the original editor format. Reopening validates artifact
    ;; recoverability; this does NOT claim crash/restart recovery-dialog coverage.
    (for ([rich? '(#f #t)])
      (define original-format (if rich? 'text 'standard))
      (reset! plain (if rich? "recover-rich.rkt" "recover-plain.rkt") original-format)
      (when rich? (add-rich! defs))
      (define original-name (send defs get-filename))
      (define expected (payload defs))
      (define auto-name (send defs do-autosave))
      (check-true (path-string? auto-name))
      (check-true (file-exists? auto-name))
      ;; Stock generate-autosave-name writes this exact recovery mapping before
      ;; returning. Read the real TOC immediately, before reset/cleanup can alter it.
      (define toc-path
        (build-path (find-system-path 'pref-dir)
                    (if (eq? (system-type) 'unix) ".plt-autosave-toc.rktd" "PLT-autosave-toc.rktd")))
      (check-true (file-exists? toc-path))
      (define toc (call-with-input-file toc-path read))
      (check-true (list? toc))
      (check-not-false (member (list (path->bytes original-name) (path->bytes auto-name)) toc)
                       "Actual recovery TOC must map the original file to this exact autosave artifact")
      (printf "OPENRACKET_AUTOSAVE_TOC_VERIFIED rich=~s original=~s artifact=~s toc=~s\n"
              rich? original-name auto-name toc-path)
      (check-equal? (wxme? auto-name) rich?)
      (check-equal? (payload (reopen auto-name)) expected)
      (check-eq? (send defs get-file-format) original-format)
      (check-equal? (send defs get-filename) original-name)
      (check-true (send defs is-modified?)))
    ;; An actual native inner veto must prevent on-save and file creation.
    (define seen '())
    (define reject%
      (class (text:clever-file-format-mixin text%)
        (super-new)
        (define/augment (can-save-file? name format) (set! seen (cons 'can seen)) #f)
        (define/augment (on-save-file name format) (set! seen (cons 'on seen)))
        (define/augment (after-save-file okay?) (set! seen (cons 'after seen)))))
    (define rejected (new reject%)) (send rejected insert "veto")
    (define rejected-path (build-path dir "must-not-exist.rkt"))
    (check-false (send rejected save-file rejected-path 'copy #f))
    (check-equal? seen '(can))
    (check-false (file-exists? rejected-path))
    ;; Preserve files for diagnostics and manual crash/recovery-dialog follow-up.
    (printf "NATIVE_SAVE_ARTIFACT_CHECKS_COMPLETED mode=~s directory=~s\n" mode dir)
    (printf "VERIFICATION_ENABLED_FORMAT_DIALOG_GATE=UNRUN\n")
    (printf "CRASH_RESTART_RECOVERY_DIALOG_GATE=UNRUN\n")
    dir))
