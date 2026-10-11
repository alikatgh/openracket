#lang racket/base
(require setup/xref 
         scribble/xref
         racket/match)
(provide get-index-entry-info
         flush-index-entry-cache)

;; OpenRacket experiment: default-off one-shot replies, no new lookup cache.
(define openracket-xref-reply-cell-enabled?
  (equal? (getenv "OPENRACKET_XREF_REPLY_CELL") "1"))
(provide openracket-xref-reply-cell-enabled?)

(define xref (load-collections-xref))

(define req-chan (make-channel))

(define thd
  (thread
   (λ ()
     (define cache (make-hash))
     (define (lookup-binding-info binding-info)
       (let/ec escape
         (define (fail) (escape #f))
         (define definition-tag (xref-binding->definition-tag xref binding-info #f))
         (unless definition-tag (fail))
         (define-values (path tag) (xref-tag->path+anchor xref definition-tag))
         (unless path (fail))
         (define index-entry (xref-tag->index-entry xref definition-tag))
         (and index-entry
              (list (entry-desc index-entry)
                    path
                    definition-tag
                    tag))))

     (let loop ()
       (match (channel-get req-chan)
         [(list binding-info cd resp-chan nack-evt)
          (define resp
            (parameterize ([current-directory cd])
              (and xref
                   (hash-ref! cache binding-info (λ () (lookup-binding-info binding-info))))))
          (if openracket-xref-reply-cell-enabled?
              (begin
                ;; Here resp-chan is a private box and nack-evt is its ready
                ;; semaphore. Accepted requests retain stock lookup/cache work,
                ;; even if their caller has since been canceled.
                (set-box! resp-chan resp)
                (semaphore-post nack-evt))
              (thread
               (λ ()
                 (sync (channel-put-evt resp-chan resp)
                       nack-evt))))]
         [#f (set! cache (make-hash))])
       (loop)))))

;; these functions are called from a thread that might be killed
;; (but the body of this module is run in a context where it is
;; guaranteed that that custodian doesn't get shut down)
(define (get-index-entry-info binding-info)
  (and (not (thread-dead? thd))
       (sync
        (nack-guard-evt
         (λ (nack-evt)
           (define resp-chan
             (if openracket-xref-reply-cell-enabled? (box #f) (make-channel)))
           (define ready
             (and openracket-xref-reply-cell-enabled? (make-semaphore 0)))
           (channel-put req-chan
                        (list binding-info (current-directory) resp-chan (or ready nack-evt)))
           (if ready
               (wrap-evt ready (λ (_) (unbox resp-chan)))
               resp-chan))))))

(define (flush-index-entry-cache)
  (unless (thread-dead? thd)
    (thread (λ () (channel-put-evt req-chan #f)))
    (void)))
