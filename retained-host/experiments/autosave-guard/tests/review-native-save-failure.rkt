#lang racket/base
;; Native-only independent failure/retry gate. Invoke on the real GUI handler
;; in a fresh stock/candidate-off/candidate-on profile. No local GUI execution.
(require racket/class racket/file racket/gui/base racket/list framework rackunit)
(provide run-review-native-save-failure-check!)

(define (payload editor)
  (define reversed
    (let loop ([s (send editor find-first-snip)] [out '()])
      (cond
        [(not s) out]
        [else
         (define item
           (cond
             [(is-a? s string-snip%) (list 'string (send s get-text 0 (send s get-count)))]
             [(is-a? s image-snip%)
              (define bm (send s get-bitmap))
              (define data (make-bytes (* 4 (send bm get-width) (send bm get-height))))
              (send bm get-argb-pixels 0 0 (send bm get-width) (send bm get-height) data)
              (list 'image (send bm get-width) (send bm get-height) data)]
             [(is-a? s editor-snip%) (list 'editor (payload (send s get-editor)))]
             [else (error 'save-failure-review "Unrecognized fixture snip")]))
         (loop (send s next)
               (if (and (pair? out) (eq? (car item) 'string) (eq? (caar out) 'string))
                   (cons (list 'string (string-append (cadar out) (cadr item))) (cdr out))
                   (cons item out)))])))
  (reverse reversed))

(define (run-review-native-save-failure-check!)
  (unless (eq? (current-thread) (eventspace-handler-thread (current-eventspace)))
    (error 'save-failure-review "Must run on the GUI handler"))
  (parameterize ([current-check-handler raise])
    (check-false (preferences:get 'framework:verify-change-format)
                 "The fresh stock default must remain unchanged")
    (define dir (make-temporary-file "openracket-save-failure-review-~a" 'directory))
    (define blocked (build-path dir "directory-is-not-a-file"))
    (make-directory blocked)
    (for* ([rich? '(#f #t)] [save-format '(copy same)])
      (define seen '())
      (define observed%
        (class (text:clever-file-format-mixin text%)
          (super-new)
          (define/augment (can-save-file? name fmt)
            (set! seen (append seen (list (list 'can fmt))))
            (inner #t can-save-file? name fmt))
          (define/augment (on-save-file name fmt)
            (set! seen (append seen (list (list 'on fmt))))
            (inner (void) on-save-file name fmt))
          (define/augment (after-save-file okay?)
            (set! seen (append seen (list (list 'after okay?))))
            (inner (void) after-save-file okay?))))
      (define editor (new observed%))
      (define original (build-path dir (format "original-~a-~a.rkt" rich? save-format)))
      (define original-bytes #"ORIGINAL FILE MUST REMAIN UNCHANGED\n")
      (call-with-output-file original #:exists 'error
        (lambda (out) (write-bytes original-bytes out)))
      (send editor set-filename original)
      (send editor insert "#lang racket/base\n;; café λ 日本語\n(+ 20 22)\n")
      (when rich?
        (define bm (make-bitmap 3 2 #t))
        (define data (make-bytes (* 4 3 2) 42))
        (for ([i (in-range 0 (bytes-length data) 4)]) (bytes-set! data i 255))
        (send bm set-argb-pixels 0 0 3 2 data)
        (send editor insert (make-object image-snip% bm) (send editor last-position))
        (define nested (new text%)) (send nested insert "nested λ 日本語")
        (send editor insert (new editor-snip% [editor nested]) (send editor last-position)))
      (send editor set-file-format (if (and rich? (eq? save-format 'same)) 'text 'standard))
      (send editor set-modified #t)
      (define before (payload editor))
      ;; Native open-output-file must fail on an existing directory. No privilege,
      ;; permission mutation or intentionally malformed editor API is involved.
      (check-exn exn:fail:filesystem?
                 (lambda () (send editor save-file blocked save-format #f)))
      (check-equal? seen (list (list 'can save-format) (list 'on save-format) '(after #f)))
      (check-equal? (send editor get-filename) original)
      (check-true (send editor is-modified?))
      ;; Stock format conversion happens before opening the destination. A failed
      ;; 'same save preserves that conversion; a 'copy save leaves format alone.
      (define expected-format (if (and (not rich?) (eq? save-format 'same)) 'text 'standard))
      (check-eq? (send editor get-file-format) expected-format)
      (check-equal? (payload editor) before)
      (check-equal? (file->bytes original) original-bytes)
      (check-true (directory-exists? blocked))
      (check-equal? (directory-list blocked) '())
      ;; A failed write must not leave the editor unusable. Retry normally and
      ;; prove the resulting plain/WXME artifact can reconstruct the full payload.
      (define retry (build-path dir (format "retry-~a-~a.rkt" rich? save-format)))
      (set! seen '())
      (check-true (send editor save-file retry save-format #f))
      (check-equal? seen (list (list 'can save-format) (list 'on save-format) '(after #t)))
      (define loaded (new text%))
      (check-true (send loaded load-file retry 'guess #f))
      (check-equal? (payload loaded) before)
      (check-equal? (send editor get-filename) (if (eq? save-format 'copy) original retry))
      (check-equal? (send editor is-modified?) (eq? save-format 'copy))
      (check-eq? (send editor get-file-format) expected-format)
      (check-equal? (file->bytes original) original-bytes))
    (printf "OPENRACKET_NATIVE_SAVE_FAILURE_RETRY passed=4 directory=~s\n" dir)
    dir))
