#lang racket/base
;; A real framework Racket editor fixture, NOT a full DrRacket tool workflow.
(require framework json racket/class racket/exn racket/file racket/gui/base racket/list racket/string
         "snapshot.rkt" "reload-diagnostic.rkt")
(provide run-gate!)
(define original
  "#lang racket/base\n(define café \"λ\")\n(define (bump x) (+ x 41))\n; comment ☃\n(bump 1)\n")
(define edited (string-replace original "\"λ\"" "[1 2]"))
(define (fixture-target! t record!)
  (define query "\"λ\"")
  (define absent-query "\"OPENRACKET_ABSENT_λ\"")
  (define length (send t last-position))
  (define selection-start (send t get-start-position))
  (define selection-end (send t get-end-position))
  ;; find-string defaults to the selection, which insertion leaves at EOF.
  ;; The positive lookup must explicitly cover the complete actual editor.
  (define target (send t find-string query 'forward 0 'eof))
  ;; Exercise the old cursor-relative mistake and an absent whole-document
  ;; query as actual native negative controls, without moving the selection.
  (define default-target (send t find-string query))
  (define eof-target (send t find-string query 'forward length 'eof))
  (define absent-target (send t find-string absent-query 'forward 0 'eof))
  (define found-text
    (and (exact-nonnegative-integer? target)
         (<= (+ target (string-length query)) length)
         (send t get-text target (+ target (string-length query)))))
  ;; Persist bounded raw values before any assertion so failures retain the
  ;; actual target (#f versus integer), selection and queried source range.
  (record! 'fixture_search
           (hasheq 'query query 'absent_query absent-query 'text_length length
                   'selection_start selection-start 'selection_end selection-end
                   'target target 'default_target default-target 'eof_target eof-target
                   'absent_target absent-target 'found_text found-text))
  (same! selection-start length "post-insertion selection starts at EOF")
  (same! selection-end length "post-insertion selection ends at EOF")
  (same! default-target #f "cursor-relative search at EOF finds no earlier string")
  (same! eof-target #f "explicit forward search at EOF finds no earlier string")
  (same! absent-target #f "absent whole-document query stays absent")
  (check! (exact-nonnegative-integer? target) "Unicode string exists at actual editor position")
  (same! target (string-length "#lang racket/base\n(define café ")
         "found Unicode string has exact source-derived character position")
  (same! found-text query "found actual editor range contains the exact Unicode string")
  target)
(define (await! description predicate deadline)
  (let loop ()
    (cond [(predicate) (void)]
          [(>= (current-inexact-monotonic-milliseconds) deadline)
           (error 'editor-gate "Timed out waiting for ~a" description)]
          [else
           ;; Preserve normal GUI dispatch, including stock low-priority lexer
           ;; callbacks. No synchronous tokenize/finish-now/freeze shortcut.
           (yield (alarm-evt (+ (current-inexact-milliseconds) 20)))
           (loop)])))
(define (token-view t expected)
  (same! (send t get-text) expected "actual editor text")
  (check! (send t is-lexer-valid?) "lexer completed before any query could force work")
  (check! (not (send t is-stopped?)) "actual framework colorer is running")
  (define n (send t last-position))
  (define positions
    (for/list ([p (in-range n)])
      (define-values (start end) (send t get-token-range p))
      (check! (and (exact-nonnegative-integer? start) (exact-nonnegative-integer? end)
                   (<= start p) (< p end) (<= end n)) "real token covers each position")
      (hasheq 'position p 'type (json-scalar (send t classify-position p))
              'start start 'end end 'style (position-style t p))))
  ;; Capture every public navigation endpoint, in positional order. This
  ;; preserves the whole paren/navigation graph, including #f and cutoffs.
  (define navigation
    (for/list ([p (in-range (add1 n))])
      (hasheq 'position p 'forward (send t forward-match p n)
              'backward (send t backward-match p 0))))
  (check! (send t is-lexer-valid?) "readback keeps already-completed lexer valid")
  (hasheq 'document (editor-view t) 'tokens positions 'navigation navigation
          'lexer_valid #t))
(define (token-at snap pos)
  (list-ref (hash-ref snap 'tokens) pos))
(define (style-name-at snap pos)
  (define document (hash-ref snap 'document))
  (define ref (hash-ref (token-at snap pos) 'style))
  (hash-ref (list-ref (hash-ref document 'styles) ref) 'name))
(define (all-styles sl) (for/list ([i (in-range (send sl number))]) (send sl index-to-style i)))
(define (same-identities! before after why)
  (check! (and (= (length before) (length after)) (andmap eq? before after)) why))
(define (make-rich!)
  (define t (new text%))
  (define sl (new style-list%))
  (send t set-style-list sl)
  (define d (new style-delta%))
  (send d set-delta 'change-size 15)
  (send d set-delta-foreground (make-object color% 12 34 56))
  (send d set-delta 'change-weight 'bold)
  (define named (send sl new-named-style "fixture:深蓝λ"
                      (send sl find-or-create-style (send sl basic-style) d)))
  (define shift-delta (new style-delta%))
  (send shift-delta set-delta 'change-underline #t)
  (define shift (send sl new-named-style "fixture:underline"
                      (send sl find-or-create-style (send sl basic-style) shift-delta)))
  (define joined (send sl find-or-create-join-style named shift))
  (send t insert "head café|tail λ")
  (send t change-style named 0 4)
  (send t change-style joined 5 9)
  (send t change-style named 10 (send t last-position))
  (define bitmap (make-bitmap 3 2 #t))
  ;; Opaque, distinct exact pixels avoid alpha premultiplication ambiguity.
  (define pixels (bytes 255 255 0 0 255 0 255 0 255 0 0 255
                        255 12 34 56 255 78 90 123 255 210 220 230))
  (send bitmap set-argb-pixels 0 0 3 2 pixels)
  (define image (make-object image-snip% bitmap))
  (send t insert image (send t last-position))
  (define nested (new text%))
  (send nested set-style-list sl)
  (send nested insert "nested λ café")
  (send nested change-style named 0 (send nested last-position))
  (define embedded (new editor-snip% [editor nested] [with-border? #t]
                        [left-margin 2] [top-margin 3] [right-margin 4] [bottom-margin 5]
                        [left-inset 1] [top-inset 2] [right-inset 3] [bottom-inset 4]
                        [min-width 40] [max-width 240] [min-height 20] [max-height 100]))
  (send t insert embedded (send t last-position))
  (send t insert "|end" (send t last-position))
  (send t change-style named (- (send t last-position) 4) (send t last-position))
  (check! (eq? (send (send t find-snip 0 'after-or-none) get-style)
               (send (send t find-snip 10 'after-or-none) get-style)) "repeated named style aliases exact object")
  (values t sl image bitmap embedded nested))
(define (run-on-handler! output private-list% state record! stage!)
  (check! (eq? (current-thread) (eventspace-handler-thread (current-eventspace)))
          "fixture runs on the genuine GUI eventspace handler")
  (define deadline (+ (current-inexact-monotonic-milliseconds) 30000))
  (define frame (new frame% [label "Named-style editor correctness"] [width 520] [height 360]))
  (dynamic-wind
    void
    (lambda ()
      (define transitions '())
      (define observed-text%
        (class racket:text%
          (define/augment (on-lexer-valid valid?)
            (set! transitions (append transitions (list valid?)))
            (inner (void) on-lexer-valid valid?))
          (super-new)))
      (define t (new observed-text%))
      (define sl (send t get-style-list))
      (check! (and (is-a? t text%) (is-a? t color:text<%>) (is-a? t racket:text<%>)
                  (is-a? sl style-list%) (is-a? sl private-list%))
              "public GUI editor uses compatible actual private runtime styles")
      (define canvas (new editor-canvas% [parent frame] [editor t]))
      (send frame show #t)
      (await! "native frame is visible" (lambda () (send frame is-shown?)) deadline)
      (check! (eq? (send canvas get-editor) t) "native canvas retains exact editor")
      (check! (preferences:get 'framework:coloring-active) "default profile has real coloring enabled")
      (define initial-diagnostics (if state (state sl) 'null))
      (record! 'diagnostics_before initial-diagnostics)
      (stage! "actual-editor-created")
      (send t insert original)
      (check! (not (send t is-lexer-valid?)) "insertion invalidates actual lexer before yielding")
      (await! "initial lexer completion" (lambda () (send t is-lexer-valid?)) deadline)
      (define initial (token-view t original))
      (record! 'initial initial)
      (define target (fixture-target! t record!))
      (same! (hash-ref (token-at initial target) 'type) "string" "stock lexer string classification")
      (same! (style-name-at initial target) "framework:syntax-color:scheme:string" "actual Racket string style name")
      (record! 'diagnostics_initial (if state (state sl) 'null))
      (stage! "initial-lexer-readback")
      (define before-edit-transitions (length transitions))
      (send t begin-edit-sequence)
      (send t delete target (+ target 3))
      (send t insert "[1 2]" target target)
      (send t end-edit-sequence)
      (same! (send t get-text) edited "Unicode edit exact source")
      (check! (not (send t is-lexer-valid?)) "edit invalidates actual incremental lexer before yielding")
      (await! "edited lexer completion" (lambda () (send t is-lexer-valid?)) deadline)
      (define after (token-view t edited))
      (same! (hash-ref (token-at after target) 'type) "parenthesis" "edit becomes real parenthesis token")
      (same! (style-name-at after target) "framework:syntax-color:scheme:parenthesis" "actual paren style")
      (same! (hash-ref (token-at after (+ target 1)) 'type) "constant" "edited numeric constant classification")
      (same! (style-name-at after (+ target 1)) "framework:syntax-color:scheme:constant" "actual constant style")
      (same! (send t forward-match target (send t last-position)) (+ target 5) "actual bracket end geometry")
      (same! (send t backward-match (+ target 5) 0) target "actual bracket start geometry")
      (same! (drop transitions before-edit-transitions) '(#f #t) "one invalidation/revalidation after edit")
      (check! (eq? (send canvas get-editor) t) "same native editor after incremental work")
      (record! 'edited after)
      (record! 'lexer_transitions transitions)
      (record! 'diagnostics_edited (if state (state sl) 'null))
      (record! 'identity (hasheq 'private_style_compatible #t 'public_style_compatible #t
                                'canvas_editor_same #t 'handler_thread #t))
      (stage! "edited-lexer-readback")
      (define-values (rich rich-sl image bitmap embedded nested) (make-rich!))
      (send canvas set-editor rich)
      (check! (eq? (send canvas get-editor) rich) "rich editor is displayed on real canvas")
      (define original-snips (snips rich))
      (define original-styles (all-styles rich-sl))
      (record! 'rich_before (editor-view rich))
      (define path (build-path output "fixture.wxme"))
      (check! (send rich save-file path 'standard) "actual standard WXME save succeeds")
      (check! (< (file-size path) (* 256 1024)) "bounded rich file")
      (check! (regexp-match? #rx#"WXME" (subbytes (file->bytes path) 0 (min 100 (file-size path))))
              "saved file is actual WXME")
      (same-identities! original-snips (snips rich) "save keeps exact original snip identities/order")
      (same-identities! original-styles (all-styles rich-sl) "save keeps exact style identities/order")
      (check! (and (eq? (send image get-bitmap) bitmap) (eq? (send embedded get-editor) nested))
              "save preserves actual bitmap and embedded editor object identities")
      (record! 'rich_after_save (editor-view rich))
      (stage! "rich-saved-with-identities")
      (define-values (restored reader-events) (make-reload-observer))
      (send restored set-style-list (new style-list%))
      (check! (call/observe-reload-failure
               (lambda () (send restored load-file path 'standard))
               path rich restored reader-events record!)
              "actual standard WXME load succeeds")
      (send canvas set-editor restored)
      (check! (and (eq? (send canvas get-editor) restored)
                  (is-a? (send restored get-style-list) private-list%)) "restored native editor uses actual runtime styles")
      (define restored-view (editor-view restored))
      (record! 'rich_restored restored-view)
      (record! 'wxme (hasheq 'format "standard" 'bytes (file-size path)
                            'save_snip_identities #t 'save_style_identities #t
                            'save_bitmap_identity #t 'save_nested_editor_identity #t))
      ;; A last normal yield may dispatch queued GUI callbacks. Revalidate
      ;; both retained documents afterwards; no evidence-grace period is added.
      (yield (alarm-evt (+ (current-inexact-milliseconds) 20)))
      (check! (< (current-inexact-monotonic-milliseconds) deadline) "closed-loop deadline still holds")
      (same! (send t get-text) edited "source retained after final GUI yield")
      (check! (send t is-lexer-valid?) "lexer remains complete after final GUI yield")
      (same! (editor-view restored) restored-view "restored readback is stable after final yield")
      (record! 'edited_final (token-view t edited))
      (record! 'rich_final (editor-view restored))
      (record! 'diagnostics_final (if state (state sl) 'null))
      (stage! "final-gui-readback"))
    (lambda () (send frame show #f))))
(define (run-gate! output private-list% state record! stage!)
  (run-failure-observation-controls!)
  (define done (make-semaphore))
  (define failure #f)
  (define callback-errors '())
  (define original-error-display (error-display-handler))
  ;; A fresh genuine GUI eventspace inherits this ordinary thread parameter.
  ;; Keep the primitive dispatcher and all queue priorities unchanged. Retain
  ;; asynchronously reported callback failures instead of silently accepting
  ;; an otherwise completed document after an event-loop exception.
  (define eventspace
    (parameterize
        ([error-display-handler
          (lambda (message e)
            (set! callback-errors
                  (append callback-errors
                          (list (hasheq 'message message
                                        'details (if (exn? e) (exn->string e) (format "~s" e))))))
            (original-error-display message e))])
      (make-eventspace)))
  (parameterize ([current-eventspace eventspace])
    (queue-callback
     (lambda ()
       (with-handlers ([(lambda (_) #t) (lambda (e) (set! failure (list e)))])
         (run-on-handler! output private-list% state record! stage!))
       (semaphore-post done))
     #f))
  (define deadline (alarm-evt (+ (current-inexact-milliseconds) 40000)))
  (define result (yield (choice-evt (wrap-evt (semaphore-peek-evt done) (lambda (_) 'done))
                                   (wrap-evt deadline (lambda (_) 'timeout)))))
  (record! 'gui_callback_errors callback-errors)
  (unless (eq? result 'done) (error 'editor-gate "GUI handler did not finish within 40 seconds"))
  (when failure (raise (car failure)))
  (unless (null? callback-errors) (error 'editor-gate "Asynchronous GUI callback failure; full details retained")))
