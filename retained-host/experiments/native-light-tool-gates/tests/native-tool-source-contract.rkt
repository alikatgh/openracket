#lang racket/base
;; Pure validators shared by native observations and explicit refusal controls.
;; These functions neither drive a tool nor manufacture native evidence.
(require racket/path)
(provide canonical-file-name source-span-valid? fixture-debug-stop?
         debug-stop-progressed? navigation-valid? remaining-seconds)

(define (canonical-file-name source)
  (and (path-string? source)
       ;; Generated marks can name nonexistent embedded directories. Such a
       ;; source is unresolved, never accepted as fixture source.
       (with-handlers ([exn:fail? (lambda (_) #f)])
         (path->string (normalize-path source)))))

(define (source-span-valid? location expected-file contents)
  (define position (hash-ref location 'position #f))
  (define span (hash-ref location 'span #f))
  (and (string? expected-file)
       (equal? (hash-ref location 'canonical_source #f) expected-file)
       (exact-positive-integer? position)
       (exact-positive-integer? span)
       (<= (+ (sub1 position) span) (string-length contents))
       (let ([prefix (substring contents 0 (sub1 position))])
         (and (equal? (hash-ref location 'line #f)
                      (add1 (for/sum ([character (in-string prefix)])
                              (if (char=? character #\newline) 1 0))))
              (equal? (hash-ref location 'column #f)
                      (for/fold ([column 0]) ([character (in-string prefix)])
                        (if (char=? character #\newline) 0 (add1 column))))))))

(define (fixture-debug-stop? observation expected-file contents)
  (define top (hash-ref observation 'top_mark (hash)))
  (define current (hash-ref observation 'current_mark (hash)))
  (define state (hash-ref observation 'state (hash)))
  (and (source-span-valid? top expected-file contents)
       (source-span-valid? current expected-file contents)
       (let ([start (hash-ref top 'position)]
             [end (+ (hash-ref top 'position) (sub1 (hash-ref top 'span)))])
         (or (equal? (hash-ref state 'pc #f) start)
             (equal? (hash-ref state 'pc #f) end)))
       (equal? (hash-ref state 'frame_endpoints #f)
               (list (hash-ref current 'position)
                     (+ (hash-ref current 'position)
                        (sub1 (hash-ref current 'span)))))))

(define (debug-stop-progressed? before after)
  ;; A diagnostic timestamp or stack count alone cannot prove a real Step.
  (not (equal? (for/list ([key '(state top_mark current_mark)])
                 (hash-ref before key #f))
               (for/list ([key '(state top_mark current_mark)])
                 (hash-ref after key #f)))))

(define (navigation-valid? observation expected-file contents start end)
  (and (string? expected-file)
       (string? contents)
       (exact-nonnegative-integer? start)
       (exact-positive-integer? end)
       (< start end)
       (<= end (string-length contents))
       (equal? (hash-ref observation 'canonical_file #f) expected-file)
       (equal? (hash-ref observation 'contents #f) contents)
       (equal? (hash-ref observation 'selection #f) (list start end))
       (eq? (hash-ref observation 'shown #f) #t)
       (eq? (hash-ref observation 'canvas_matches #f) #t)))

(define (remaining-seconds deadline [now (current-inexact-monotonic-milliseconds)])
  (define remaining (/ (- deadline now) 1000.0))
  (unless (> remaining 0)
    (error 'native-tool-gate "Debugger startup exhausted its original 20-second budget"))
  remaining)
