#lang racket/base
(require rackunit racket/file racket/path racket/place json "gui-observer.rkt")
(current-check-handler raise)

(define directory (make-temporary-file "gui-observer-test~a" 'directory))
(define handler (build-path directory "handler.rkt"))
(call-with-output-file handler (lambda (out) (display "#lang racket/base\n" out)))
(define source (build-path directory "fixture.rkt"))
(define snapshot "#lang racket/base\n(define x 1)\nx\n")
(putenv "OPENRACKET_GUI_OBSERVER_OUTPUT" (path->string directory))
(putenv "OPENRACKET_GUI_EXPECTED_SOURCE" (path->string source))
(putenv "OPENRACKET_GUI_EXPECTED_CHARACTERS" (number->string (string-length snapshot)))
(putenv "OPENRACKET_GUI_EXPECTED_SHA256" (digest (string->bytes/utf-8 snapshot)))
(define-values (response-a response-b) (place-channel))
(define-values (status-a status-b) (place-channel))
(define settings (make-prefab-struct 'prefab-module-settings #() '(default) #t #t 'none #t))
(define actual (vector-immutable snapshot source response-a settings status-a '()))
(gui-hook 'registry (list (list handler 'monitor #t) (list handler 'go #f)))
(define id (gui-hook 'request actual 268435456))
(check-equal? id 1)
(gui-hook 'response id (vector 'monitor-message (list handler 'monitor)
                               (list (vector 'syncheck:add-id-set '() response-b 7))))
(gui-hook 'response id (vector 'handler-results (list (list (list handler 'go) (void))) '() #f))
(gui-hook 'point id 'terminal-callback-enter #t)
(gui-hook 'point id 'terminal-callback-return)
(define (record id)
  (for/first ([rec (in-list (hash-ref (observer-summary) 'records))]
              #:when (= (hash-ref rec 'request_id) id)) rec))
(define token
  (parameterize ([current-gui-request-id id]) (gui-hook 'application-enter)))
(define bx (box '()))
;; The stock queued closure explicitly captures the token. Invoking it with the
;; dynamic parameter cleared must still complete the correct generation.
(define queued
  (lambda ()
    (define live-before-reset? (gui-hook 'application-live? token (and (unbox bx) #t)))
    (set-box! bx #f)
    (gui-hook 'application-complete token live-before-reset?)))
(parameterize ([current-gui-request-id #f]) (queued))
(check-true (hash-ref (record id) 'application_current))
(check-true (hash-has-key? (hash-ref (record id) 'gui_points) 'application-complete))
(check-equal? (hash-ref (hash-ref (record id) 'monitor_evidence) 'rename_capability_rows) 1)
(check-equal? (hash-ref (hash-ref (record id) 'monitor_evidence) 'trace_entries) 1)
;; Replacing an application in the SAME request invalidates its previous token.
(define second (parameterize ([current-gui-request-id id]) (gui-hook 'application-enter)))
(check-false (hash-ref (record id) 'application_current))
(check-false (gui-hook 'application-live? token #t))
(gui-hook 'application-complete token #t)
(check-false (hash-ref (record id) 'application_current))
(check-equal? (hash-ref (record id) 'stale_application_events) 1)
;; Cancellation cannot later be mistaken for normal completion of the same token.
(check-false (gui-hook 'application-live? second #f))
(gui-hook 'application-cancel second #f)
(check-false (gui-hook 'application-live? second #t))
(gui-hook 'application-complete second #t)
(check-false (hash-ref (record id) 'application_current))
;; A new real request invalidates an older queued continuation even before its
;; own application begins. Duplicate exact snapshots are visible, never guessed.
(define id2 (gui-hook 'request actual 268435456))
(check-equal? id2 2)
(check-equal? (hash-ref (observer-summary) 'matching_request_ids) '(1 2))
(check-false (gui-hook 'application-live? second #t))
(gui-hook 'application-complete second #t)
(check-false (hash-ref (record id2) 'application_current))
;; All observer records are serializable scalar trees; no captured channels,
;; editor object, syntax, whole source snapshot or handler result is retained.
(define encoded (jsexpr->string (observer-summary)))
(check-false (regexp-match? #rx"define x 1" encoded))
(check-false (file-exists? (build-path directory "gui-observation.json")))
(check-equal? (hash-ref (observer-summary) 'error_count) 0)
;; Oversized identity evidence fails closed instead of silently clipping a key.
(gui-hook 'response id2 (vector 'handler-results (list (list (list (make-string 2000 #\x) 'go) #f)) '() #f))
(check-true (positive? (hash-ref (observer-summary) 'error_count)))
(delete-directory/files directory)
