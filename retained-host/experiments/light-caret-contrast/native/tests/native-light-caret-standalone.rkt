#lang racket/base
;; Direct headless controls only; these never stand in for native screenshots.
(require rackunit racket/list json "native-light-caret-contract.rkt"
         "native-tool-failure-diagnostics.rkt"
         (only-in rackunit/private/check-info pretty-info? pretty-info-value))
(define arguments (current-command-line-arguments))
(unless (or (equal? arguments #())
            (equal? arguments #("--inject-wrong-state"))
            (equal? arguments #("--inject-wrong-color")))
  (error 'native-light-caret "Unsupported arguments"))
(define (fixture arm)
  (define state (hash-ref expected-caret-states (string->symbol arm)))
  (hash-set* state 'visible_first_line 0 'visible_last_line 4 'rendered_line 2
             'line_top 40 'line_bottom 60 'view_left 0 'view_top 0
             'view_width 800 'view_height 400
             'contrast_ratio (contrast-ratio (hash-ref state 'gutter_foreground)
                                             (hash-ref state 'gutter_background))))
(parameterize ([current-check-handler raise])
  (for ([arm '("original" "patched")])
    (define good (fixture arm))
    (check-not-exn (lambda () (validate-caret-state! good arm))))
  (define good (fixture "patched"))
  ;; Ordinary output failure must not prevent the intended typed state check.
  (check-not-exn (lambda () (emit-caret-state! (lambda () (error 'output "fixture")))))
  (check-not-exn (lambda () (emit-caret-state! (lambda () (raise 'output-fixture)))))
  (check-exn exn:test:check?
             (lambda ()
               (emit-caret-state! (lambda () (error 'output "fixture")))
               (validate-caret-state! (hash-set good 'selection_collapsed #f) "patched")))
  ;; Model a break raised during printf/flush and retain its exact identity.
  (let/ec escape
    (define original-break (exn:break "output break fixture" (current-continuation-marks) escape))
    (check-exn (lambda (failure) (eq? failure original-break))
               (lambda () (emit-caret-state! (lambda () (raise original-break))))))
  (check-not-exn (lambda () (validate-caret-state!
                            (read-json (open-input-string (jsexpr->string good))) "patched")))
  (for ([key (in-list (hash-keys good))])
    (check-exn exn:test:check? (lambda () (validate-caret-state! (hash-remove good key) "patched"))))
  (for ([key '(registered_definitions registered_canvas same_original_definitions
               same_canvas_editor frame_shown canvas_shown canvas_focus
               line_numbers_interface showing_line_numbers selection_collapsed)])
    (for ([bad '(#f 1 "true")])
      (check-exn exn:test:check?
                 (lambda () (validate-caret-state! (hash-set good key bad) "patched")))))
  (for ([delta (list (cons 'gutter_foreground '(36 94 219))
                     (cons 'gutter_background '(247 248 250))
                     (cons 'selection_end 69) (cons 'current_paragraph 0)
                     (cons 'highlight_text_color '(255 255 255))
                     (cons 'view_top 50) (cons 'view_height 1)
                     (cons 'visible_first_line 3) (cons 'visible_last_line 1)
                     (cons 'renderer_sha256 "wrong") (cons 'info_sha256 "wrong")
                     (cons 'contrast_ratio 4.5) (cons 'extra #t))])
    (check-exn exn:test:check?
               (lambda () (validate-caret-state! (hash-set good (car delta) (cdr delta)) "patched"))))
  (when (positive? (vector-length arguments))
    (define color? (equal? arguments #("--inject-wrong-color")))
    (define control (if color? "wrong-color" "wrong-state"))
    (define actual (if color? '(0 0 0) #f))
    (define expected (if color? '(35 91 215) #t))
    (printf "OPENRACKET_CARET_INJECTING_FAILURE ~a\n" control)
    (flush-output)
    (with-handlers
        ([exn:test:check?
          (lambda (failure)
            (report-failure!
             failure
             (lambda (original)
               (define infos (exn:test:check-stack original))
               (define (unique name)
                 (define matches (filter (lambda (info) (eq? (check-info-name info) name)) infos))
                 (and (= (length matches) 1) (check-info-value (car matches))))
               (define observed-actual (unique 'actual))
               (define observed-expected (unique 'expected))
               (when (and (eq? (unique 'name) 'check-equal?)
                          (pretty-info? observed-actual) (pretty-info? observed-expected)
                          (equal? (pretty-info-value observed-actual) actual)
                          (equal? (pretty-info-value observed-expected) expected))
                 (printf "OPENRACKET_CARET_FAILURE control=~a exception=exn:test:check check=check-equal?\n" control)
                 (flush-output))))
            (raise failure))])
      (validate-caret-state!
       (hash-set good (if color? 'gutter_foreground 'selection_collapsed) actual) "patched"))))
(displayln "OPENRACKET_CARET_OK original-patched-typed-state-color-viewport-refusals")
(exit 0)
