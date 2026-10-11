#lang racket/base
;; Mandatory native, headless deterministic tests. Fake clocks exercise fixed
;; production bounds without sleeping for 102.4 seconds. No GUI/performance claim.
(require rackunit racket/list json "queued-sampler.rkt"
         (submod "queued-sampler.rkt" test-support))

(define (token) (vector-immutable 7 3 2 0.0))
(define ordinary-context
  (list (cons 'handle-replay (srcloc "/diagnostic/gui.rkt" 19 2 310 1))))
(define live-ref (make-weak-box (current-thread)))
(define (await evt [label "test synchronization"])
  (define ready (sync/timeout 5 evt))
  (unless ready (error 'queued-sampler-test "Timeout: ~a" label))
  ready)
(define (check-reconciled summary)
  (check-true (hash-ref summary 'snapshot_quiescent))
  (check-equal? (hash-ref summary 'attempts)
                (for/sum ([key '(stored_samples race_discarded stop_discarded
                                invalid_token_discarded attempt_errors_discarded)])
                  (hash-ref summary key)))
  (check-equal? (hash-ref summary 'cadence_ticks)
                (+ (hash-ref summary 'attempts) (hash-ref summary 'idle_ticks)))
  (check-equal? (hash-ref summary 'stored_samples) (length (hash-ref summary 'samples)))
  (check-true (<= (hash-ref summary 'attempts) 1024))
  ;; Fails if a thread, exception, srcloc, mutable payload graph, or raw
  ;; continuation mark set escaped instead of JSON-safe scalar/text evidence.
  (check-true (string? (jsexpr->string summary #:encode 'control)))
  (for ([sample (in-list (hash-ref summary 'samples))])
    (check-true (<= (length (hash-ref sample 'frames)) 8))
    (for ([frame (in-list (hash-ref sample 'frames))])
      (for ([key '(name source)])
        (define value (hash-ref frame key))
        (when (string? value)
          (check-true (immutable? value))
          (check-true (<= (string-length value) 240)))))))
(define (join h)
  (await (sampler-done-evt h) "sampler completion")
  (define summary (sampler-summary h))
  (check-reconciled summary)
  summary)
(define (first-row summary) (car (hash-ref summary 'samples)))

;; Drive exactly one scheduled tick, then wait for a cooperative stop. The test
;; itself cannot stop until the worker has finished storing/discarding that tick.
(define (once pending #:handler [handler live-ref]
              #:capture [capture (lambda (_) ordinary-context)]
              #:render [render render-context]
              #:clock-hook [clock-hook void]
              #:delay [delay 0.0])
  (define now 0.0)
  (define calls 0)
  (define waits 0)
  (define settled (make-semaphore 0))
  (define h
    (sampler-start/injected! pending handler
      #:clock (lambda () (set! calls (add1 calls)) (clock-hook calls) now)
      #:wait (lambda (planned stop clock)
               (set! waits (add1 waits))
               (cond [(= waits 1) (set! now (+ planned delay))]
                     [else (semaphore-post settled) (sync stop)]))
      #:capture capture #:render render))
  (await settled "single tick settled")
  ;; A caller's claim alone must never authorize a mutable-buffer snapshot.
  (define premature (sampler-summary h #t))
  (check-false (hash-ref premature 'snapshot_quiescent))
  (check-true (hash-ref premature 'incomplete))
  (check-equal? (hash-ref premature 'attempts) 'null)
  (sampler-stop! h)
  (sampler-stop! h) ; Repeated stop is harmless and remains nonblocking.
  (join h))

(test-case "enabled normal sample preserves scalar identity and useful frames"
  (define summary (once (box (token))))
  (check-equal? (hash-ref summary 'attempts) 1)
  (check-equal? (hash-ref summary 'stored_samples) 1)
  (check-equal? (hash-ref summary 'usable_source_samples) 1)
  (check-false (hash-ref summary 'incomplete))
  (check-true (hash-ref summary 'stopped))
  (define row (first-row summary))
  (check-equal? (hash-ref row 'state) "live_at_sample")
  (check-equal? (hash-ref row 'request_id) 7)
  (check-equal? (hash-ref row 'application_generation) 3)
  (check-equal? (hash-ref row 'wait_ordinal) 2)
  (check-equal? (hash-ref row 'planned_monotonic_ms) 100.0)
  (check-equal? (hash-ref row 'actual_monotonic_ms) 100.0)
  (check-equal? (hash-ref row 'scheduling_delay_ms) 0.0)
  (check-equal? (hash-ref summary 'missed_cadence_ticks) 0))

(test-case "pre-capture changed identity discards without calling capture"
  (define pending (box (token)))
  (define captures 0)
  (define summary
    (once pending
      #:clock-hook (lambda (n) (when (= n 3) (set-box! pending (token))))
      #:capture (lambda (_) (set! captures (add1 captures)) ordinary-context)))
  (check-equal? captures 0)
  (check-equal? (hash-ref summary 'race_discarded) 1)
  (check-equal? (hash-ref summary 'stored_samples) 0))

(test-case "callback entry clearing token during capture discards row"
  (define pending (box (token)))
  (define summary
    (once pending #:capture (lambda (_) (set-box! pending #f) ordinary-context)))
  (check-equal? (hash-ref summary 'race_discarded) 1)
  (check-equal? (hash-ref summary 'stored_samples) 0))

(test-case "identity check extends through rendering and rejects equal replacement"
  (define original (token))
  (define replacement (token))
  (check-equal? original replacement)
  (check-false (eq? original replacement))
  (define pending (box original))
  (define summary
    (once pending
      #:render (lambda (context)
                 (define rendered (render-context context))
                 (set-box! pending replacement)
                 rendered)))
  (check-equal? (hash-ref summary 'race_discarded) 1)
  (check-equal? (hash-ref summary 'stored_samples) 0))

(test-case "stop while waiting wakes without a candidate or capture"
  (define entered (make-semaphore 0))
  (define captures 0)
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () 0.0)
      #:wait (lambda (_ stop clock) (semaphore-post entered) (sync stop))
      #:capture (lambda (_) (set! captures (add1 captures)) ordinary-context)))
  (await entered)
  (sampler-stop! h)
  (define summary (join h))
  (check-equal? captures 0)
  (check-equal? (hash-ref summary 'attempts) 0)
  (check-true (hash-ref summary 'stopped))
  (check-true (hash-ref summary 'incomplete))
  (check-false (hash-ref (sampler-summary h #f) 'snapshot_quiescent)))

(test-case "stop during capture is cooperative, waits, then discards in-flight row"
  (define now 0.0)
  (define entered (make-semaphore 0))
  (define release (make-semaphore 0))
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock) (set! now planned))
      #:capture (lambda (_)
                  (semaphore-post entered) (sync release) ordinary-context)))
  (await entered)
  (sampler-stop! h)
  (check-false (sync/timeout 0 (sampler-done-evt h)))
  (check-false (hash-ref (sampler-summary h) 'snapshot_quiescent))
  (semaphore-post release)
  (define summary (join h))
  (check-equal? (hash-ref summary 'stop_discarded) 1)
  (check-equal? (hash-ref summary 'attempts) 1)
  (check-equal? (hash-ref summary 'stored_samples) 0))

(test-case "fixed cap counts pending attempts, never idle wakes, and exits normally"
  (define now 0.0)
  (define ticks 0)
  (define pending (box #f))
  (define h
    (sampler-start/injected! pending live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock)
               (set! now planned) (set! ticks (add1 ticks))
               (when (= ticks 1501) (set-box! pending (token))))
      #:capture (lambda (_) ordinary-context)))
  (define summary (join h))
  (check-equal? (hash-ref summary 'attempts) 1024)
  (check-equal? (hash-ref summary 'stored_samples) 1024)
  (check-equal? (hash-ref summary 'idle_ticks) 1500)
  (check-equal? (hash-ref summary 'cadence_ticks) 2524)
  (check-equal? ticks 2524)
  (check-true (hash-ref summary 'capped))
  (check-true (hash-ref summary 'incomplete))
  (check-false (hash-ref summary 'stopped))
  (check-equal? (hash-ref summary 'termination) "capped"))

(test-case "cap also bounds discarded attempts, not just retained rows"
  (define now 0.0)
  (define pending (box (token)))
  (define h
    (sampler-start/injected! pending live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock) (set! now planned))
      #:capture (lambda (_) (set-box! pending (token)) ordinary-context)))
  (define summary (join h))
  (check-equal? (hash-ref summary 'attempts) 1024)
  (check-equal? (hash-ref summary 'race_discarded) 1024)
  (check-equal? (hash-ref summary 'stored_samples) 0)
  (check-true (hash-ref summary 'capped)))

(test-case "eight frames and 240 characters bound retained Unicode rendering"
  (define astral (integer->char #x1F680))
  (define long-name (make-string 400 astral))
  (define long-source (make-string 400 astral))
  (define context
    (make-list 10 (cons long-name (srcloc long-source 1 0 1 1))))
  (define summary (once (box (token)) #:capture (lambda (_) context)))
  (define row (first-row summary))
  (check-equal? (length (hash-ref row 'frames)) 8)
  (check-true (hash-ref row 'frames_truncated))
  (check-equal? (hash-ref row 'text_fields_truncated) 16)
  (check-equal? (hash-ref summary 'text_fields_truncated) 16)
  (check-equal? (hash-ref summary 'frames_truncated) 1)
  (for ([frame (in-list (hash-ref row 'frames))])
    (for ([key '(name source)])
      (define value (hash-ref frame key))
      (check-equal? (string-length value) 240)
      (check-equal? (bytes-length (string->bytes/utf-8 value)) 960)))
  (string-set! long-name 0 #\X)
  (string-set! long-source 0 #\X)
  (check-equal? (string-ref (hash-ref (car (hash-ref row 'frames)) 'source) 0) astral)
  ;; Exactly eight frames has no false truncation report.
  (check-false (hash-ref (render-context (take context 8)) 'frames_truncated)))

(test-case "missing/unsupported sources remain explicit and retain no source object"
  (define context
    (list (cons #f #f) (cons 'opaque (srcloc (box 'private-object) 1 0 1 1))))
  (define summary (once (box (token)) #:capture (lambda (_) context)))
  (define row (first-row summary))
  (check-equal? (hash-ref row 'missing_frame_sources) 2)
  (check-equal? (hash-ref row 'usable_source_frames) 0)
  (check-equal? (map (lambda (f) (hash-ref f 'source_kind)) (hash-ref row 'frames))
                '("missing" "unsupported"))
  (check-true (hash-ref summary 'incomplete)))

(test-case "absent, collected, invalid, and dead handlers stay distinct"
  (define dead (thread void))
  (await (thread-dead-evt dead))
  (for ([handler (in-list (list #f (make-weak-box #f) (make-weak-box 7)
                                (make-weak-box dead)))]
        [state '("not_registered" "weak_reference_collected" "invalid_handler" "dead")]
        [counter '(absent_handlers collected_handlers invalid_handlers dead_handlers)])
    (define summary
      (once (box (token)) #:handler handler
        #:capture (lambda (_) (error 'test "Must not capture unavailable handler"))))
    (check-equal? (hash-ref (first-row summary) 'state) state)
    (check-false (hash-ref (first-row summary) 'capture_performed))
    (check-equal? (hash-ref summary counter) 1)
    (check-equal? (hash-ref summary 'missing_frames) 1)
    (check-true (hash-ref summary 'incomplete))))

(test-case "handler death during capture is reported"
  (define release (make-semaphore 0))
  (define handler (thread (lambda () (sync release))))
  (define summary
    (once (box (token)) #:handler (make-weak-box handler)
      #:capture (lambda (actual)
                  (semaphore-post release) (await (thread-dead-evt actual))
                  ordinary-context)))
  (check-equal? (hash-ref (first-row summary) 'state) "died_during_sample")
  (check-equal? (hash-ref summary 'died_during_capture) 1)
  (check-true (hash-ref summary 'incomplete)))

(test-case "capture and render exceptions preserve bounded partial failure evidence"
  (for ([capture (in-list
                   (list (lambda (_) (error 'test (make-string 400 #\x)))
                         (lambda (_) (list 'malformed-frame))
                         (lambda (_) (raise (box 'private-object)))))])
    (define summary (once (box (token)) #:capture capture))
    (define row (first-row summary))
    (check-equal? (hash-ref row 'state) "sampling_error")
    (check-equal? (hash-ref summary 'capture_errors) 1)
    (check-true (hash-ref summary 'incomplete))
    (check-true (<= (string-length (hash-ref row 'error)) 240)))
  (define long-error
    (once (box (token)) #:capture (lambda (_) (error 'test (make-string 400 #\x)))))
  (check-true (hash-ref (first-row long-error) 'error_truncated)))

(test-case "invalid mutable or nonscalar tokens cannot retain application objects"
  (for ([bad (in-list (list (vector 7 3 2 0.0)
                            (vector-immutable (box 'editor) 3 2 0.0)
                            (vector-immutable 7 3 2 +nan.0)
                            (vector-immutable 7 3 2 +inf.0)
                            (vector-immutable 7 3 2 -1.0)
                            (vector-immutable 7 3 2)
                            'malformed))])
    (define summary
      (once (box bad) #:capture (lambda (_) (error 'test "Must not capture"))))
    (check-equal? (hash-ref summary 'invalid_token_discarded) 1)
    (check-equal? (hash-ref summary 'stored_samples) 0)
    (check-true (hash-ref summary 'incomplete))))

(test-case "delayed wake and slow capture skip cadence without catch-up bursts"
  (define now 0.0)
  (define waits 0)
  (define plans '())
  (define settled (make-semaphore 0))
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock)
               (set! plans (cons planned plans))
               (set! waits (add1 waits))
               (case waits
                 [(1) (set! now (+ planned 250.0))]
                 [(2) (set! now planned)]
                 [else (semaphore-post settled) (sync stop)]))
      #:capture (lambda (_)
                  (when (= waits 1) (set! now (+ now 175.0)))
                  ordinary-context)))
  (await settled)
  (sampler-stop! h)
  (define summary (join h))
  (check-equal? (reverse plans) '(100.0 600.0 700.0))
  (check-equal? (hash-ref summary 'attempts) 2)
  (check-equal? (hash-ref summary 'scheduling_delay_ms) 250.0)
  (check-equal? (hash-ref summary 'max_scheduling_delay_ms) 250.0)
  (check-equal? (hash-ref summary 'capture_duration_ms) 175.0)
  (check-equal? (hash-ref summary 'max_capture_duration_ms) 175.0)
  (check-equal? (hash-ref summary 'missed_cadence_ticks) 4)
  (check-equal? (hash-ref (first-row summary) 'missed_before_capture_ticks) 2)
  (check-equal? (hash-ref (first-row summary) 'missed_cadence_ticks) 4))

(test-case "idle wakes record delay and missed cadence without an attempt"
  (define summary (once (box #f) #:delay 350.0))
  (check-equal? (hash-ref summary 'idle_ticks) 1)
  (check-equal? (hash-ref summary 'attempts) 0)
  (check-equal? (hash-ref summary 'scheduling_delay_ms) 350.0)
  (check-equal? (hash-ref summary 'missed_cadence_ticks) 3))

(test-case "early wake retries same cadence without inventing a sample"
  (define now 0.0)
  (define waits 0)
  (define settled (make-semaphore 0))
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock)
               (set! waits (add1 waits))
               (case waits
                 [(1) (set! now 50.0)]
                 [(2) (set! now planned)]
                 [else (semaphore-post settled) (sync stop)]))
      #:capture (lambda (_) ordinary-context)))
  (await settled) (sampler-stop! h)
  (define summary (join h))
  (check-equal? (hash-ref summary 'early_wakes) 1)
  (check-equal? (hash-ref summary 'cadence_ticks) 1)
  (check-equal? (hash-ref summary 'attempts) 1))

(test-case "unexpected sampler failure keeps previously stored rows"
  (define now 0.0)
  (define waits 0)
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock)
               (set! waits (add1 waits))
               (if (= waits 1) (set! now planned) (error 'test "wait failure")))
      #:capture (lambda (_) ordinary-context)))
  (define summary (join h))
  (check-equal? (hash-ref summary 'termination) "sampler_error")
  (check-equal? (hash-ref summary 'sampler_errors) 1)
  (check-equal? (hash-ref summary 'stored_samples) 1)
  (check-true (hash-ref summary 'incomplete)))

(test-case "unexpected clock failure within attempt has explicit disposition"
  (define now 0.0)
  (define clocks 0)
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda ()
                (set! clocks (add1 clocks))
                (when (= clocks 3) (error 'test "clock failure")) now)
      #:wait (lambda (planned stop clock) (set! now planned))
      #:capture (lambda (_) ordinary-context)))
  (define summary (join h))
  (check-equal? (hash-ref summary 'attempts) 1)
  (check-equal? (hash-ref summary 'attempt_errors_discarded) 1)
  (check-equal? (hash-ref summary 'sampler_errors) 1)
  (check-true (hash-ref summary 'incomplete)))

(test-case "disabled sampler has no worker activity and an immediate immutable summary"
  (define h
    (sampler-start/injected! (box (token)) live-ref #:enabled? #f
      #:clock (lambda () (error 'test "Disabled sampler read clock"))
      #:wait (lambda args (error 'test "Disabled sampler waited"))
      #:capture (lambda (_) (error 'test "Disabled sampler captured"))))
  (define summary (join h))
  (check-false (hash-ref summary 'enabled))
  (check-false (hash-ref summary 'incomplete))
  (check-false (hash-ref summary 'capped))
  (check-equal? (hash-ref summary 'termination) "disabled")
  (check-equal? (hash-ref summary 'started_monotonic_ms) 'null)
  (check-equal? (hash-ref summary 'finished_monotonic_ms) 'null)
  (check-equal? (hash-ref summary 'attempts) 0)
  (check-equal? (hash-ref summary 'samples) '())
  (check-true (immutable? summary))
  (sampler-stop! h))

(test-case "native public continuation API samples the actual supplied live thread"
  (define now 0.0)
  (define waits 0)
  (define settled (make-semaphore 0))
  (define h
    (sampler-start/injected! (box (token)) live-ref
      #:clock (lambda () now)
      #:wait (lambda (planned stop clock)
               (set! waits (add1 waits))
               (if (= waits 1) (set! now planned)
                   (begin (semaphore-post settled) (sync stop))))))
  (await settled) (sampler-stop! h)
  (define summary (join h))
  (check-equal? (hash-ref summary 'capture_errors) 0)
  (check-equal? (hash-ref summary 'stored_samples) 1)
  (check-equal? (hash-ref (first-row summary) 'state) "live_at_sample")
  (check-true (hash-ref (first-row summary) 'capture_performed)))

(test-case "public start obeys exact environment enable switch"
  (define variables (environment-variables-copy (current-environment-variables)))
  (parameterize ([current-environment-variables variables])
    (putenv "OPENRACKET_GUI_APPLICATION_POINTS" "0")
    (define disabled (sampler-start! (box #f) live-ref))
    (check-false (hash-ref (join disabled) 'enabled))
    (putenv "OPENRACKET_GUI_APPLICATION_POINTS" "1")
    (define enabled (sampler-start! (box #f) live-ref))
    (sampler-stop! enabled)
    (check-true (hash-ref (join enabled) 'enabled))))
