#lang racket/base
;; Headless RackUnit payload proof. No GUI/native tool claim.
(require rackunit racket/list "native-tool-failure-diagnostics.rkt")
(define arguments (current-command-line-arguments))
(unless (or (equal? arguments #()) (equal? arguments #("--inject-failure")))
  (error 'diagnostics-test "Unsupported arguments"))
(parameterize ([current-check-handler raise])
  (define original
    (with-handlers ([exn:test:check? values])
      (check-equal? 'actual 'deliberately-wrong)
      (error 'diagnostics-test "The negative control did not fail")))
  (define payload (failure->diagnostic original))
  (check-equal? (hash-ref payload 'exception_type) "exn:test:check")
  (define infos (hash-ref payload 'check_info))
  (define (unique-info name)
    (define matches (filter (lambda (i) (equal? (hash-ref i 'name) name)) infos))
    (check-equal? (length matches) 1)
    (car matches))
  (check-equal? (hash-ref (unique-info "name") 'value) "check-equal?")
  (check-equal? (hash-ref (unique-info "actual") 'value) "actual")
  (check-equal? (hash-ref (unique-info "expected") 'value) "deliberately-wrong")
  (check-true (hash-ref (unique-info "actual") 'pretty_info))
  (check-true (hash-ref (unique-info "expected") 'pretty_info))
  (check-true (regexp-match? #rx"native-tool-failure-diagnostics-standalone[.]rkt"
                            (hash-ref (unique-info "location") 'value)))
  (check-true (regexp-match? #rx"check-equal[?]"
                            (hash-ref (unique-info "expression") 'value)))
  ;; Inspecting the payload must not replace the exception crossing a caller.
  (define received
    (with-handlers ([exn:test:check? values])
      (failure->diagnostic original)
      (raise original)))
  (check-eq? received original)
  ;; The same reporter boundary used by the real host must contain output
  ;; exceptions and arbitrary raised values, while the caller rethrows exactly
  ;; the original check failure. Assertions remain outside reporter catches.
  (define closed-output (open-output-string))
  (close-output-port closed-output)
  (for ([reporter (in-list
                  (list (lambda (_) 'ignored-result)
                        (lambda (_) (display "cannot write" closed-output))
                        (lambda (_) (raise 'diagnostic-output-token))))])
    (define seen #f)
    (define reraised
      (with-handlers ([exn:test:check? values])
        (with-handlers ([exn:test:check?
                         (lambda (failure)
                           (report-failure! failure
                                            (lambda (reported)
                                              (set! seen reported)
                                              (reporter reported)))
                           (raise failure))])
          (raise original))))
    (check-eq? seen original)
    (check-eq? reraised original))
  (define ordinary (exn:fail "ordinary" (current-continuation-marks)))
  (check-equal? (hash-ref (failure->diagnostic ordinary) 'exception_type) "exn:fail")
  (check-equal? (hash-ref (failure->diagnostic ordinary) 'check_info) '())
  (when (equal? arguments #("--inject-failure"))
    (displayln "OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE")
    (flush-output)
    (with-handlers
        ([exn:test:check?
          (lambda (failure)
            (report-failure!
             failure
             (lambda (reported)
               (define data (failure->diagnostic reported))
               (define fields (hash-ref data 'check_info))
               (define (matches? name value)
                 (define matches (filter (lambda (i) (equal? (hash-ref i 'name) name)) fields))
                 (and (= (length matches) 1)
                      (equal? (hash-ref (car matches) 'value) value)))
               ;; Missing/wrong payload cannot produce the supervisor's marker.
               (when (and (eq? reported failure)
                          (equal? (hash-ref data 'exception_type) "exn:test:check")
                          (matches? "name" "check-equal?")
                          (matches? "actual" "actual")
                          (matches? "expected" "deliberately-wrong"))
                 (displayln "OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong")
                 (flush-output))
               ;; A broken output sink must not replace this real failed check.
               (display "cannot write" closed-output)))
            (raise failure))])
      (check-equal? 'actual 'deliberately-wrong))))
(displayln "OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained")
