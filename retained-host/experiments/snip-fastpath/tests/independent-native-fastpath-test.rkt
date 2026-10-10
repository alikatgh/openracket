#lang racket/base
;; Native-only correctness gate. Requires the installed private overlay and
;; OPENRACKET_ALL_STRING_FAST_PATH=1. No GUI execution is authorized locally.
(require racket/class racket/contract racket/file racket/gui/base racket/list racket/port
         rackunit rackunit/text-ui framework
         drracket/private/openracket-all-string-snips)

(define stock% (text:all-string-snips-mixin text%))
(define private% (openracket:all-string-snips-mixin text%))
(define classes (list stock% private%))
(define (on-gui thunk)
  (define done (make-semaphore))
  (define result #f)
  (queue-callback
   (lambda ()
     (with-handlers ([(lambda (_) #t) (lambda (e) (set! result (cons 'error e)))])
       (parameterize ([current-check-handler raise])
         (set! result (cons 'value (thunk)))))
     (semaphore-post done)) #f)
  (yield (semaphore-peek-evt done))
  (if (eq? (car result) 'error) (raise (cdr result)) (cdr result)))
(define (snips editor)
  (let loop ([s (send editor find-first-snip)] [out '()])
    (if s (loop (send s next) (cons s out)) (reverse out))))
(define (kind s)
  (cond [(is-a? s string-snip%) 'string]
        [(is-a? s image-snip%) 'image]
        [(is-a? s editor-snip%) 'editor]
        [else 'custom]))
(define (query-signature editor)
  (define all (snips editor))
  (for/list ([start (in-list (cons #f all))])
    (define rest (if start (cdr (memq start all)) all))
    (define expected (for/or ([s (in-list rest)]) (and (not (is-a? s string-snip%)) s)))
    (define actual (send editor find-next-non-string-snip start))
    (check-eq? actual expected "Native result agrees with an independent full snip walk")
    (and actual (list (send editor get-snip-position actual) (kind actual)))))
(define (paired proc)
  (define results (for/list ([base% (in-list classes)]) (proc base%)))
  (check-equal? (cadr results) (car results) "Private and original native editors agree")
  (car results))
(define custom-snip%
  (class snip%
    (super-new)
    (send this set-count 1)
    (define/override (copy) (new custom-snip%))))
(define string-child%
  (class string-snip%
    (init [content "derived café λ"])
    (super-make-object content)
    (define/override (copy)
      (new string-child% [content (send this get-text 0 (send this get-count))]))))
(define (append! editor value) (send editor insert value (send editor last-position)))
(define (port-items editor)
  (define p
    (open-input-text-editor
     editor 0 'end
     (lambda (s)
       (case (kind s)
         [(image) 'image]
         [(editor) (list 'editor (send (send s get-editor) get-text))]
         [else 'custom]))))
  (dynamic-wind void
                (lambda ()
                  (let loop ([out '()])
                    (define v (read-char-or-special p))
                    (if (eof-object? v) (reverse out) (loop (cons v out)))))
                (lambda () (close-input-port p))))
(define (image!)
  (define bitmap (make-bitmap 5 4 #t))
  (define bytes (make-bytes (* 4 5 4) 170))
  (for ([i (in-range 0 (bytes-length bytes) 4)]) (bytes-set! bytes i 255))
  (send bitmap set-argb-pixels 0 0 5 4 bytes)
  (make-object image-snip% bitmap))
(define (rich-summary editor)
  (define entries
    (for/list ([s (in-list (snips editor))])
    (cond
      [(is-a? s image-snip%)
       (define bm (send s get-bitmap))
       (define data (make-bytes (* 4 (send bm get-width) (send bm get-height))))
       (send bm get-argb-pixels 0 0 (send bm get-width) (send bm get-height) data)
       (list 'image (send bm get-width) (send bm get-height) data)]
      [(is-a? s editor-snip%) (list 'editor (send (send s get-editor) get-text))]
      [else (list (kind s) (send s get-text 0 (send s get-count)))])))
  ;; Serialization may legally coalesce adjacent string snips. Compare exact
  ;; text and rich payloads without imposing an incidental segmentation rule.
  (reverse
   (for/fold ([out '()]) ([entry (in-list entries)])
     (if (and (pair? out) (eq? (car entry) 'string) (eq? (caar out) 'string))
         (cons (list 'string (string-append (cadar out) (cadr entry))) (cdr out))
         (cons entry out)))))

(define cases
  (test-suite
   "Independent actual native private snip-scan preservation"
   (test-case "activation and original public interface are genuine"
     (on-gui
      (lambda ()
        (check-true openracket-fast-path-selected?)
        (check-not-eq? openracket:all-string-snips-mixin text:all-string-snips-mixin)
        (for ([base% (in-list classes)])
          (check-true (is-a? (new base%) text:all-string-snips<%>))))))
   (test-case "exact stock strings take the fast path and rich content delegates"
     (on-gui
      (lambda ()
        (define counts
          (for/list ([mixin (in-list (list text:all-string-snips-mixin
                                          openracket:all-string-snips-mixin))])
            (define calls 0)
            ;; This lower test-only observer proves an actual hit; it is not an
            ;; installed Framework override or part of the production seam.
            (define counted%
              (class text%
                (super-new)
                (define/override (find-next-non-string-snip s)
                  (set! calls (add1 calls))
                  (super find-next-non-string-snip s))))
            (define editor (new (mixin counted%)))
            (send editor insert "ordinary stock café λ")
            (check-true (send editor all-string-snips?))
            (check-true (pair? (snips editor)))
            (for ([s (in-list (snips editor))])
              (check-eq? (object-interface s) (class->interface string-snip%))
              (check-false (has-contract? s) "Editor-created native strings remain eligible"))
            (set! calls 0)
            (check-false (send editor find-next-non-string-snip #f))
            (check-false (send editor find-next-non-string-snip (send editor find-first-snip)))
            (define plain-calls calls)
            (define rich (new custom-snip%))
            (append! editor rich)
            (set! calls 0)
            (check-eq? (send editor find-next-non-string-snip #f) rich)
            (check-equal? calls 1 "Rich content reaches the actual lower method")
            plain-calls))
        (check-equal? counts '(2 0)))))
   (test-case "custom string merge can make rich content without insertion hooks"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define armed? (box #f))
           (define merges 0)
           (define merging-string%
             (class string-snip%
               (init [content "x"])
               (super-make-object content)
               (define/override (merge-with previous)
                 (and (unbox armed?)
                      (begin (set! merges (add1 merges)) (new custom-snip%))))))
           (define editor (new base%))
           (append! editor (new merging-string% [content "a"]))
           (append! editor (new merging-string% [content "b"]))
           (check-equal? (length (snips editor)) 2)
           (check-true (send editor all-string-snips?))
           ;; The pinned native set-position checks the OLD selection boundary.
           ;; Its later merge invokes neither on-insert nor after-insert.
           (send editor set-position 1)
           (set-box! armed? #t)
           (send editor set-position 0)
           (check-true (> merges 0) "The native custom merge actually ran")
           (define rich (for/or ([s (in-list (snips editor))])
                          (and (not (is-a? s string-snip%)) s)))
           (check-not-false rich "Independent traversal sees a rich merge result")
           (check-true (send editor all-string-snips?)
                       "The original all-string cache remains stale after this merge")
           (check-eq? (send editor find-next-non-string-snip #f) rich)
           (list (send editor last-position) (query-signature editor)))))))
   (test-case "Unicode fragmented text and streaming input ports agree"
     (on-gui
      (lambda ()
        (define source (apply string-append (make-list 300 "(list \"café λ 日本語\" 42)\n")))
        (paired
         (lambda (base%)
           (define editor (new base%))
           (send editor insert source)
           (check-true (send editor all-string-snips?))
           (check-true (> (length (snips editor)) 10))
           (define p (open-input-text-editor editor 0 'end values 'unicode #f
                                             #:lock-while-reading? #t))
           (define restored (port->string p))
           (close-input-port p)
           (check-equal? restored source)
           (check-false (send editor is-locked?))
           (list restored (query-signature editor)))))))
   (test-case "foreign/detached snips, arity and invalid types preserve stock contracts"
     (on-gui
      (lambda ()
        (define (outcome thunk)
          (with-handlers ([exn:fail?
                           (lambda (e)
                             (cond [(exn:fail:contract:arity? e) '(error arity)]
                                   [(exn:fail:contract? e) '(error contract)]
                                   [else (raise e)]))])
            (list 'value (thunk))))
        (define results
          (for/list ([base% (in-list classes)])
            (define editor (new base%)) (send editor insert "abc λ")
            (define foreign-editor (new text%))
            (define foreign (new custom-snip%)) (send foreign-editor insert foreign)
            (define foreign-string (make-object string-snip% "foreign"))
            (append! foreign-editor foreign-string)
            (define starts
              (list #f (send editor find-first-snip) foreign foreign-string
                    (new custom-snip%) (new string-child%) (make-object string-snip% "detached")))
            (define start-results
              (for/list ([s (in-list starts)])
                (outcome (lambda () (send editor find-next-non-string-snip s)))))
            (define empty-editor (new base%))
            (define empty-results
              (for/list ([s (in-list starts)])
                (outcome (lambda () (send empty-editor find-next-non-string-snip s)))))
            (check-equal? empty-results start-results
                          "Stock checks detached admin even before its empty-editor shortcut")
            (send foreign release-from-owner)
            (check-false (send foreign get-admin))
            (define released-result
              (outcome (lambda () (send editor find-next-non-string-snip foreign))))
            (for ([n '(0 1 2)])
              (check-equal? (object-method-arity-includes? editor 'find-next-non-string-snip n) (= n 1)))
            (define invalid-results
              (append
               (list (outcome (lambda () (send editor find-next-non-string-snip)))
                     (outcome (lambda () (send editor find-next-non-string-snip #f #f))))
               (for/list ([v '(1 "snip" #(snip))])
                 (outcome (lambda () (send editor find-next-non-string-snip v))))))
            (list start-results released-result invalid-results)))
        ;; The pinned native implementation calls object=? on the snip admin.
        ;; An unowned/released snip has #f admin and raises a contract error.
        ;; Preserve that actual outcome instead of normalizing it to #f.
        (check-equal? (car results)
                      '(((value #f) (value #f) (value #f) (value #f)
                         (error contract) (error contract) (error contract))
                        (error contract)
                        ((error arity) (error arity) (error contract) (error contract) (error contract))))
        (check-equal? (cadr results) (car results)
                      "Candidate preserves every original value or exception category"))))
   (test-case "contract-wrapped native string arguments preserve stock internal-field access"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define editor (new base%)) (send editor insert "contract café λ")
           (define original (send editor find-first-snip))
           (check-eq? (object-interface original) (class->interface string-snip%))
           (define range-calls 0)
           (define wrapped
             (contract
              (object/c [get-admin (->m (lambda (v) (set! range-calls (add1 range-calls)) #t))])
              original 'snip-provider 'snip-client))
           (check-true (impersonator? wrapped))
           (check-true (has-contract? wrapped))
           (check-eq? (object-interface wrapped) (object-interface original))
           (set! range-calls 0)
           (check-false (send editor find-next-non-string-snip wrapped))
           (check-equal? range-calls 0
                         "Stock's internal admin read has no public contract callback")
           range-calls)))))
   (test-case "custom and string-subclass snips preserve exact suffix queries"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define editor (new base%))
           (append! editor (new string-child%))
           (check-true (send editor all-string-snips?))
           (define rich (new custom-snip%))
           (append! editor rich) (append! editor " end")
           (check-false (send editor all-string-snips?))
           (check-eq? (send editor find-next-non-string-snip #f) rich)
           (list (send editor get-text) (query-signature editor) (port-items editor)))))))
   (test-case "image and nested-editor specials are not flattened by input ports"
     (on-gui
      (lambda ()
        (define result
          (paired
           (lambda (base%)
             (define editor (new base%)) (append! editor "λ")
             (append! editor (image!))
             (define nested (new text%)) (send nested insert "nested café 日本語")
             (append! editor (new editor-snip% [editor nested]))
             (append! editor "z")
             (list (query-signature editor) (port-items editor)))))
        (check-equal? (cadr result) '(#\λ image (editor "nested café 日本語") #\z)))))
   (test-case "native modified callback sees rich insertion before after-insert begins"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define armed? #f) (define after-begun? #f) (define observations '())
           (define rich (new custom-snip%))
           (define observed%
             (class base%
               (super-new)
               (define/override (set-modified modified?)
                 ;; Only classify the interval after independent traversal proves
                 ;; the rich snip is linked, and before any after-insert hook.
                 ;; The pinned text.rkt success path calls set-modified here.
                 (when (and armed? modified? (not after-begun?) (memq rich (snips this)))
                   (set! observations (cons (query-signature this) observations)))
                 (super set-modified modified?))
               (define/augment (after-insert start len)
                 (set! after-begun? #t)
                 (inner (void) after-insert start len))))
           (define editor (new observed%))
           (set! after-begun? #f) (set! armed? #t)
           (append! editor rich)
           (check-true (pair? observations) "Actual pre-after-insert native interval was observed")
           (list observations (query-signature editor)))))))
   (test-case "actual inner after-insert queries see the newly inserted rich snip"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define observations '())
           (define observed%
             (class base%
               (super-new)
               (define/augment (after-insert start len)
                 (set! observations (cons (query-signature this) observations))
                 (inner (void) after-insert start len))))
           (define editor (new observed%))
           (append! editor "prefix") (append! editor (new custom-snip%))
           (list (reverse observations) (query-signature editor)))))))
   (test-case "nested native mutation remains guarded through the outer callback"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define nested? #f) (define observations '())
           (define observed%
             (class base%
               (super-new)
               (define/augment (after-insert start len)
                 (unless nested?
                   (set! nested? #t)
                   (append! this (new custom-snip%))
                   (set! observations (query-signature this)))
                 (inner (void) after-insert start len))))
           (define editor (new observed%))
           (append! editor "prefix")
           (list observations (query-signature editor)))))))
   (test-case "native callback exception cannot make an installed rich snip invisible"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define raise? #t)
           (define observed%
             (class base%
               (super-new)
               (define/augment (after-insert start len)
                 (when raise? (error 'independent-plugin "after native mutation"))
                 (inner (void) after-insert start len))))
           (define editor (new observed%)) (define rich (new custom-snip%))
           (check-exn exn:fail? (lambda () (append! editor rich)))
           (set! raise? #f)
           (check-eq? (send editor find-next-non-string-snip #f) rich)
           (query-signature editor))))))
   (test-case "actual undo/redo preserve rich snips and suffix scans"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define editor (new base%))
           (send editor set-max-undo-history 20)
           (send editor insert "original café λ") (send editor clear-undos)
           (send editor begin-edit-sequence)
           (append! editor (new custom-snip%))
           (send editor end-edit-sequence)
           (define inserted (query-signature editor))
           (send editor undo)
           (check-equal? (send editor get-text) "original café λ")
           (check-false (send editor find-next-non-string-snip #f))
           (send editor redo)
           (check-equal? (query-signature editor) inserted)
           (port-items editor))))))
   (test-case "WXME image/nested editor round trip preserves bytes, content and scan results"
     (on-gui
      (lambda ()
        (paired
         (lambda (base%)
           (define editor (new base%)) (append! editor "document λ\n")
           (append! editor (image!))
           (define nested (new text%)) (send nested insert "nested 日本語")
           (append! editor (new editor-snip% [editor nested]))
           (define before (rich-summary editor))
           (define file (make-temporary-file "independent-fastpath-~a.wxme"))
           (dynamic-wind
            void
            (lambda ()
              (check-true (send editor save-file file 'standard))
              (define restored (new base%))
              (check-true (send restored load-file file 'standard))
              (check-equal? (rich-summary restored) before)
              (list (rich-summary restored) (query-signature restored) (port-items restored)))
            (lambda () (delete-file file))))))))
   (test-case "outer editor overrides and generic Framework superclass dispatch remain intact"
     (on-gui
      (lambda ()
        (for ([base% (in-list classes)])
          (define calls 0)
          (define outer%
            (class base%
              (super-new)
              (define/override (find-next-non-string-snip s)
                (set! calls (add1 calls))
                (super find-next-non-string-snip s))))
          (define editor (new outer%)) (send editor insert "ordinary text")
          (set! calls 0)
          (check-false (send editor find-next-non-string-snip #f))
          (check-equal? calls 1))
        (define generic-calls 0)
        (define custom-base%
          (class text%
            (super-new)
            (define/override (find-next-non-string-snip s)
              (set! generic-calls (add1 generic-calls))
              (super find-next-non-string-snip s))))
        (define generic (new (text:all-string-snips-mixin custom-base%)))
        (send generic insert "still generic") (set! generic-calls 0)
        (check-false (send generic find-next-non-string-snip #f))
        (check-equal? generic-calls 1))))))

(define (run!)
  (define failures (run-tests cases))
  (printf "OPENRACKET_NATIVE_FASTPATH_RESULT enabled=~s failures=~a\n"
          openracket-fast-path-selected? failures)
  (flush-output)
  (unless (zero? failures) (error 'independent-native-fastpath "~a native failures" failures)))
(module+ test (run!))
(module+ main (run!))
