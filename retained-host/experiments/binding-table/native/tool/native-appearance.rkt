#lang racket/base

;; Reversible app-local appearance lifecycle. No GUI, FFI, preferences, filesystem,
;; or desktop settings are touched by this module. Native work is injectable.
;; Integration contract:
;; - Construct opt-in on the existing GUI handler thread; never start a GUI.
;; - Apply only for an explicitly active successful appearance transaction.
;; - Restore on that transaction's rollback/restore; ordinary palette refreshes
;;   must not reactivate a restored controller. Close permanently rejects apply.
;; - The first snapshot survives reapply. Later checkpoints only protect each
;;   individual mutation. Restore releases the first snapshot exactly once.
;; - Reapplying the same successful mode while active returns 'unchanged only
;;   when the adapter's read-only matches? verifier confirms current native
;;   state. No capture/set occurs. Restore resets this feedback-loop guard.
;; - active? means a native change is owned or rollback is uncertain and needs
;;   restoration. A failed release can report failure after appearance restored;
;;   it never retries a potentially already-consumed native reference.
(provide (struct-out native-appearance-adapter)
         (struct-out native-appearance-result)
         make-native-appearance-controller
         native-appearance-set! native-appearance-follow-original!
         native-appearance-restore! native-appearance-close!
         native-appearance-active? native-appearance-inspect)

;; capture returns an owned opaque checkpoint; #f is a valid checkpoint (Cocoa
;; nil appearance). dispose! releases its ownership, never changes appearance.
;; The optional auto-field matches? keeps the seven-argument constructor stable.
;; Production adapters install a read-only live verifier; without it, the
;; controller never assumes a cached requested mode proves current native state.
(struct native-appearance-adapter
  (name gui-thread? capture set! restore! dispose! inspect
        [matches? #:auto #:mutable])
  #:auto-value #f #:transparent)
(struct native-appearance-result (status backend detail) #:transparent)
(struct controller (adapter enabled? captured? original active? closed? mode) #:mutable)

(define (make-native-appearance-controller adapter #:enabled? [enabled? #f])
  (unless (or (not adapter) (native-appearance-adapter? adapter))
    (raise-argument-error 'make-native-appearance-controller
                          "(or/c #f native-appearance-adapter?)" adapter))
  (controller adapter (and enabled? #t) #f #f #f #f #f))
(define (result c status [detail #f])
  (native-appearance-result status
                           (and (controller-adapter c)
                                (native-appearance-adapter-name (controller-adapter c)))
                           detail))
(define (native-appearance-active? c) (controller-active? c))
(define (thread-ready? c)
  ((native-appearance-adapter-gui-thread? (controller-adapter c))))
(define (guard c #:setting? [setting? #f])
  (cond [(controller-closed? c) (result c 'closed)]
        [(and setting? (not (controller-enabled? c))) (result c 'disabled)]
        [(not (controller-adapter c)) (result c 'unsupported)]
        [(not (thread-ready? c)) (result c 'wrong-thread)]
        [else #f]))

(define (native-appearance-set! c mode)
  (unless (memq mode '(light dark))
    (raise-argument-error 'native-appearance-set! "(or/c 'light 'dark)" mode))
  (with-handlers ([exn:fail? (lambda (e) (result c 'failed (exn-message e)))])
    (or (guard c #:setting? #t)
        (and (controller-active? c) (eq? mode (controller-mode c))
             (native-appearance-adapter-matches? (controller-adapter c))
             ((native-appearance-adapter-matches? (controller-adapter c)) mode)
             (result c 'unchanged mode))
        (let* ([a (controller-adapter c)]
               [first? (not (controller-captured? c))]
               [checkpoint ((native-appearance-adapter-capture a))])
          ;; Preserve ownership before the native setter can fail after mutation.
          (when first?
            (set-controller-original! c checkpoint)
            (set-controller-captured?! c #t))
          (define mutation-error
            (with-handlers ([exn:fail? values])
              ((native-appearance-adapter-set! a) mode)
              #f))
          (cond
            [mutation-error
             (define rollback-error
               (with-handlers ([exn:fail? values])
                 ((native-appearance-adapter-restore! a) checkpoint)
                 #f))
             ;; A failed rollback may leave native appearance changed. Keep the
             ;; original owned and expose active? so integration can retry.
             (when rollback-error (set-controller-active?! c #t))
             ;; Do not claim a known current mode after uncertain rollback.
             (when rollback-error (set-controller-mode! c #f))
             (when (or (not first?) (not rollback-error))
               (when first?
                 (set-controller-original! c #f)
                 (set-controller-captured?! c #f)
                 (set-controller-active?! c #f)
                 (set-controller-mode! c #f))
               ((native-appearance-adapter-dispose! a) checkpoint))
             (result c 'failed
                     (if rollback-error
                         (format "~a; rollback failed: ~a"
                                 (exn-message mutation-error) (exn-message rollback-error))
                         (exn-message mutation-error)))]
            [else
             (set-controller-active?! c #t)
             (set-controller-mode! c mode)
             ;; Disposal is deliberately outside the mutation handler. A native
             ;; release failure must not restore/release an already-used token.
             (unless first? ((native-appearance-adapter-dispose! a) checkpoint))
             (result c 'applied mode)])))))

(define (native-appearance-follow-original! c)
  ;; Framework's 'platform setting must not pin the current resolved mode.
  ;; Keep the first baseline owned across explicit/platform toggles, but restore
  ;; its exact app inheritance/value while following it. Final Restore releases.
  (with-handlers ([exn:fail? (lambda (e) (result c 'failed (exn-message e)))])
    (or (guard c #:setting? #t)
        (let ([a (controller-adapter c)])
          (cond
            [(not (controller-captured? c))
             (define original ((native-appearance-adapter-capture a)))
             (set-controller-original! c original)
             (set-controller-captured?! c #t)]
            [else
             (with-handlers ([exn:fail?
                              (lambda (e)
                                (set-controller-active?! c #t)
                                (set-controller-mode! c #f)
                                (raise e))])
               ((native-appearance-adapter-restore! a) (controller-original c)))])
          (set-controller-active?! c #f)
          (set-controller-mode! c #f)
          (result c 'following)))))

(define (native-appearance-restore! c)
  (with-handlers ([exn:fail? (lambda (e) (result c 'failed (exn-message e)))])
    (cond [(not (controller-captured? c)) (result c 'unchanged)]
          [(guard c) => values]
          [else
           (define a (controller-adapter c))
           (define original (controller-original c))
           ((native-appearance-adapter-restore! a) original)
           ;; Mark ownership consumed before disposal: a disposal failure must
           ;; never produce a second release of the same native object.
           (set-controller-original! c #f)
           (set-controller-captured?! c #f)
           (set-controller-active?! c #f)
           (set-controller-mode! c #f)
           ((native-appearance-adapter-dispose! a) original)
           (result c 'restored)])))

(define (native-appearance-close! c)
  (define restored (native-appearance-restore! c))
  (when (memq (native-appearance-result-status restored) '(restored unchanged))
    (set-controller-closed?! c #t))
  restored)

(define (native-appearance-inspect c)
  (with-handlers ([exn:fail? (lambda (e) (result c 'failed (exn-message e)))])
    (or (guard c)
        ((native-appearance-adapter-inspect (controller-adapter c))))))
