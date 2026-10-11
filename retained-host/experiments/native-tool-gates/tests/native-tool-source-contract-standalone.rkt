#lang racket/base
;; Mandatory direct headless gate. These are refusal controls, not GUI proof.
(require racket/file racket/path rackunit "native-tool-source-contract.rkt")

(parameterize ([current-check-handler raise])
  (define fixture "#lang racket/base\n(+ 1 2)\n")
  (define filename "/fixture/source.rkt")
  (define location
    (hash 'source filename 'canonical_source filename
          'position 19 'span 7 'line 2 'column 0))
  (define state (hash 'pc 19 'break_status "entry-break" 'frame_endpoints '(19 25)))
  (define observation (hash 'state state 'top_mark location 'current_mark location))
  (check-true (source-span-valid? location filename fixture))
  (check-true (source-span-valid?
               (hash 'canonical_source filename 'position 1 'span 1 'line 1 'column 0)
               filename fixture))
  (check-true (fixture-debug-stop? observation filename fixture))
  (for ([change (in-list (list (cons 'canonical_source "/elsewhere/source.rkt")
                              (cons 'canonical_source #f)
                              (cons 'line 1) (cons 'column 1)
                              (cons 'position 0) (cons 'position 20)
                              (cons 'span 0) (cons 'span 700)))])
    (define wrong (hash-set location (car change) (cdr change)))
    (check-false (source-span-valid? wrong filename fixture))
    (check-false (fixture-debug-stop? (hash-set observation 'top_mark wrong) filename fixture))
    (check-false (fixture-debug-stop? (hash-set observation 'current_mark wrong) filename fixture)))
  (check-false (fixture-debug-stop?
                (hash-set observation 'state (hash-set state 'pc 20)) filename fixture))
  (check-false (fixture-debug-stop?
                (hash-set observation 'state (hash-set state 'frame_endpoints '(19 24)))
                filename fixture))
  (check-true (fixture-debug-stop?
               (hash-set observation 'state (hash-set state 'pc 25)) filename fixture))
  (check-false (debug-stop-progressed? observation observation))
  (check-false (debug-stop-progressed? observation (hash-set observation 'diagnostic_time 99)))
  (check-true (debug-stop-progressed?
               observation (hash-set observation 'state (hash-set state 'break_status "exit-break"))))

  (define navigation
    (hash 'canonical_file filename 'contents fixture 'selection '(18 25)
          'shown #t 'canvas_matches #t))
  (check-true (navigation-valid? navigation filename fixture 18 25))
  (for ([change (in-list (list (cons 'canonical_file "/elsewhere/source.rkt")
                              (cons 'contents "wrong source")
                              (cons 'selection '(0 0)) (cons 'selection '(19 25))
                              (cons 'selection '(18 24)) (cons 'shown #f)
                              (cons 'canvas_matches #f)))])
    (check-false (navigation-valid? (hash-set navigation (car change) (cdr change))
                                    filename fixture 18 25)))
  ;; Even matching observed/expected ranges cannot authorize malformed bounds.
  (for ([bounds (in-list (list '(bad 25) '(18 #f) '(18.0 25) '(18 25.0)
                              '(-1 25) '(0 0) '(18 18) '(25 18) '(18 100)))])
    (check-false (navigation-valid? (hash-set navigation 'selection bounds)
                                    filename fixture (car bounds) (cadr bounds))))
  (check-equal? (remaining-seconds 20000 0) 20.0)
  (check-equal? (remaining-seconds 20000 19500) 0.5)
  (check-exn exn:fail? (lambda () (remaining-seconds 20000 20000)))
  (check-exn exn:fail? (lambda () (remaining-seconds 20000 20001)))
  (for ([source (in-list (list #f 'generated '(not a path)))])
    (check-false (canonical-file-name source)))

  (define temporary (make-temporary-file "openracket-source-contract-~a" 'directory))
  (dynamic-wind
    void
    (lambda ()
      (define real (build-path temporary "real"))
      (define alias (build-path temporary "alias"))
      (make-directory real)
      (make-file-or-directory-link real alias)
      (check-equal? (canonical-file-name real) (canonical-file-name alias))
      (check-equal? (canonical-file-name (build-path real "fixture.rkt"))
                    (canonical-file-name (build-path alias "fixture.rkt")))
      (check-false (canonical-file-name (build-path temporary "absent" "fixture.rkt"))))
    (lambda () (delete-directory/files temporary)))
  (displayln "OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals"))
