#lang racket/base
(require rackunit racket/file racket/path racket/runtime-path
         "../scripts/apply-autosave.rkt")
(define-runtime-path source-root "..")
(define stock (file->bytes (build-path source-root "vendor/text-misc-v9.3.rkt")))
(define patched (file->bytes (build-path source-root "overlay/framework/private/text-misc.rkt")))
(define (fixture proc)
  (define temporary (make-temporary-file "openracket-save-install~a" 'directory))
  (dynamic-wind
    void
    (lambda ()
      (define profile (build-path temporary "profile"))
      (define gui (build-path profile "gui-lib"))
      (define target (build-path gui "framework/private/text-misc.rkt"))
      (make-directory* (path-only target))
      (call-with-output-file target (lambda (out) (write-bytes stock out)))
      (proc temporary profile gui target))
    (lambda () (delete-directory/files temporary))))
(test-case "Exact source applies idempotently and reverts byte-for-byte"
  (fixture
   (lambda (_ profile gui target)
     (check-equal? (apply-autosave! source-root profile gui) target)
     (check-equal? (file->bytes target) patched)
     (apply-autosave! source-root profile gui)
     (check-equal? (file->bytes target) patched)
     (apply-autosave! source-root profile gui #:revert? #t)
     (check-equal? (file->bytes target) stock))))
(test-case "Unrelated installed source is refused without mutation"
  (fixture
   (lambda (_ profile gui target)
     (call-with-output-file target #:exists 'truncate (lambda (out) (display "foreign" out)))
     (check-exn exn:fail? (lambda () (apply-autosave! source-root profile gui)))
     (check-equal? (file->bytes target) #"foreign"))))
(test-case "Outside-profile target is refused"
  (fixture
   (lambda (temporary profile gui target)
     (check-exn exn:fail? (lambda () (apply-autosave! source-root (build-path temporary "other") gui)))
     (check-equal? (file->bytes target) stock))))
(test-case "Profile root and intermediate symbolic links are refused"
  (fixture
   (lambda (temporary profile gui target)
     (define alias (build-path temporary "alias"))
     (make-file-or-directory-link profile alias)
     (check-exn exn:fail? (lambda () (apply-autosave! source-root alias (build-path alias "gui-lib"))))
     (define linked (build-path profile "linked-gui"))
     (make-file-or-directory-link gui linked)
     (check-exn exn:fail? (lambda () (apply-autosave! source-root profile linked)))
     (check-equal? (file->bytes target) stock))))
(test-case "Tampered forward and rollback inputs are refused before target mutation"
  (fixture
   (lambda (temporary profile gui target)
     (define sources (build-path temporary "sources"))
     (for ([relative '("vendor/text-misc-v9.3.rkt" "overlay/framework/private/text-misc.rkt")])
       (define destination (build-path sources relative))
       (make-directory* (path-only destination))
       (copy-file (build-path source-root relative) destination))
     (define candidate (build-path sources "overlay/framework/private/text-misc.rkt"))
     (call-with-output-file candidate #:exists 'append (lambda (out) (newline out)))
     (check-exn exn:fail? (lambda () (apply-autosave! sources profile gui)))
     (check-equal? (file->bytes target) stock)
     (copy-file (build-path source-root "overlay/framework/private/text-misc.rkt") candidate #t)
     (apply-autosave! sources profile gui)
     (call-with-output-file (build-path sources "vendor/text-misc-v9.3.rkt") #:exists 'append
       (lambda (out) (newline out)))
     (check-exn exn:fail? (lambda () (apply-autosave! sources profile gui #:revert? #t)))
     (check-equal? (file->bytes target) patched))))
