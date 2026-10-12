#lang racket/base

(require racket/class
         racket/gui/base
         racket/unit
         drracket/tool
         framework
         string-constants
         "appearance-state.rkt"
         "frame-chrome.rkt"
         "layout.rkt"
         "native-appearance.rkt"
         "native-appearance-platform.rkt")
(provide tool@)

(define-logger openracket-appearance)
(define enabled-pref 'openracket:appearance-enabled?)
(define state-pref 'openracket:appearance-state)
(define snapshot-pref 'openracket:appearance-snapshot)
(define synchronize-painter! void)
(define set-painter-blended! void)
(define native-controller #f) ; one app-scoped owner across every retained frame
(define native-committed? #f)
(define startup-native-considered? #f)
(define native-state-write? (make-parameter #f))
(define native-state-generation 0)
;; Weak keys neither keep closed frames alive nor accumulate dead registrations.
(define toolbar-parents (make-weak-hasheq))

(define (refresh-retained-toolbars!)
  (define (visit widget)
    (when (is-a? widget canvas<%>) (send widget refresh))
    (when (is-a? widget area-container<%>)
      (for ([child (in-list (send widget get-children))]) (visit child))))
  (for ([parent (in-hash-keys toolbar-parents)]) (visit parent)))

(define (track-toolbar-parent-mixin super%)
  (class super%
    (inherit get-button-panel)
    (super-new)
    ;; The original parent includes Save and the plugin button panel. Do not
    ;; traverse other frame areas, reparent widgets, or replace their callbacks.
    (hash-set! toolbar-parents (send (get-button-panel) get-parent) #t)))
(define (modern-session?)
  (host-theme-enabled? (getenv "OPENRACKET_HOST_THEME") (getenv "OPENRACKET_UI")))

(define (native-appearance-opted-in?)
  (and (modern-session?) (equal? (getenv "OPENRACKET_NATIVE_APPEARANCE") "1")))

(define (native-appearance-eligible?)
  (and (native-appearance-opted-in?) (eq? (preferences:get state-pref) 'applied)))

(define (set-appearance-state! value)
  ;; Our transactions explicitly manage native ownership. Only external state
  ;; restoration (stock Preferences Undo/Escape/defaults) needs reconciliation.
  (parameterize ([native-state-write? #t]) (preferences:set state-pref value)))

(define (begin-native-state-transaction!)
  (set! native-state-generation (add1 native-state-generation)))

(define (suspend-native-appearance!)
  ;; Clear before restoring preferences/native state: both synchronous finalizers
  ;; and already-queued mode notifications must see the inactive gate.
  (set! native-committed? #f)
  (set-painter-blended! #f))

(define (deactivate-native-appearance! #:strict? [strict? #f])
  (suspend-native-appearance!)
  (when native-controller
    (define restored (native-appearance-restore! native-controller))
    (unless (memq (native-appearance-result-status restored) '(restored unchanged))
      (log-openracket-appearance-warning "Native appearance restore requires retry: ~a" restored)
      (when strict?
        (error 'openracket-appearance "Native appearance could not be restored; retry Restore: ~a" restored)))))

(define (current-native-mode)
  (if (eq? (preferences:get 'framework:white-on-black-mode?) 'platform)
      'platform
      (if (color-prefs:white-on-black-color-scheme?) 'dark 'light)))

(define (synchronize-native-appearance!
         [mode (current-native-mode)])
  (when native-committed?
    (cond
      [(not (native-appearance-eligible?)) (deactivate-native-appearance!)]
      [else
       (define applied
         (if (eq? mode 'platform)
             (native-appearance-follow-original! native-controller)
             (native-appearance-set! native-controller mode)))
       (cond
         [(eq? (native-appearance-result-status applied) 'following)
          ;; No app override is active; retain the ordinary safe painter until
          ;; platform-following blend acceptance is genuinely verified.
          (set-painter-blended! #f)]
         [(and (memq (native-appearance-result-status applied) '(applied unchanged))
               (native-appearance-active? native-controller))
          (set-painter-blended! #t)]
         [else
          (log-openracket-appearance-warning "Native appearance remains unsupported: ~a" applied)
          (deactivate-native-appearance!)])])))

(define (activate-native-appearance!)
  (when (native-appearance-eligible?)
    (unless native-controller
      (define adapter
        (make-platform-native-appearance-adapter
         #:enabled? #t
         ;; GTK remains a separate native-test candidate. Value restoration does
         ;; not recover property-source inheritance, so do not enable it here.
         #:allow-gtk-candidate? #f
         #:on-unavailable
         (lambda (reason)
           (log-openracket-appearance-warning "Native appearance unavailable: ~a" reason))))
      (when adapter
        (set! native-controller (make-native-appearance-controller adapter #:enabled? #t))))
    (when native-controller
      (set! native-committed? #t)
      (synchronize-native-appearance!))))

(define (layout-enabled?)
  (and (modern-session?) (preferences:get enabled-pref)))

(define (current-chrome-palette)
  (make-chrome-palette
   (color-prefs:lookup-in-color-scheme 'framework:basic-canvas-background)
   (color-prefs:lookup-in-color-scheme 'framework:default-text-color)))

;; Optional retained-host painter. The theme package also works with untouched
;; stock DrRacket. Only a missing optional module is ignored, not painter bugs.
(define (optional-painter-export name)
  (with-handlers ([exn:fail:filesystem:missing-module? (lambda (e) #f)])
    (dynamic-require 'mrlib/private/openracket-paint name (lambda () #f))))

(define (install-painter-bridge!)
  (define set-theme! (optional-painter-export 'set-modern-host-theme!))
  (define set-roles! (optional-painter-export 'set-modern-role-labels!))
  (set! set-painter-blended! (or (optional-painter-export 'set-modern-chrome-blended!) void))
  (set-painter-blended! #f)
  (when set-roles!
    (set-roles!
     (hash (string-constant check-syntax) 'check
           (string-constant debug-tool-button-name) 'debug
           (string-constant macro-stepper) 'macro
           (string-constant execute-button-label) 'run
           (string-constant break-button-label) 'stop
           (string-constant break-button-kill-label) 'stop)))
  (when (or set-theme! (native-appearance-opted-in?))
    (define sync-queued? #f)
    (define (sync-theme!)
      (when set-theme! (set-theme! (if (color-prefs:white-on-black-color-scheme?) 'dark 'light)))
      (synchronize-native-appearance!)
      (refresh-retained-toolbars!))
    (define (schedule-theme-sync!)
      (unless sync-queued?
        (set! sync-queued? #t)
        (queue-callback
         (lambda ()
           (set! sync-queued? #f)
           ;; Framework invokes preference callbacks BEFORE committing the
           ;; new value. Read the final mode on the next event, not in the
           ;; color-entry callback (which otherwise observes the old mode).
           (sync-theme!)))))
    (set! synchronize-painter! sync-theme!)
    (sync-theme!)
    ;; Keep following Framework's mode, including native Preferences changes,
    ;; platform-driven mode changes, and custom schemes with equal backgrounds.
    (color-prefs:register-color-scheme-entry-change-callback
     'framework:basic-canvas-background (lambda (background) (schedule-theme-sync!)))
    (preferences:add-callback
     'framework:white-on-black-mode?
     (lambda (preference incoming-mode) (schedule-theme-sync!)))
    (when (native-appearance-opted-in?)
      (define state-sync-queued? #f)
      (define pending-state-generation #f)
      (preferences:add-callback
       state-pref
       (lambda (preference incoming-state)
         (unless (native-state-write?)
           ;; A newer external write can reuse the queued callback, but must
           ;; record its own generation after an intervening internal action.
           (set! pending-state-generation native-state-generation)
           (unless state-sync-queued?
             (set! state-sync-queued? #t)
             (queue-callback
              (lambda ()
                (set! state-sync-queued? #f)
                ;; Framework's Undo Changes/Escape restores its full snapshot.
                ;; Read final committed values only when no later internal
                ;; transaction superseded this external state notification.
                (when (equal? pending-state-generation native-state-generation)
                  (if (native-appearance-eligible?)
                      (activate-native-appearance!)
                      (deactivate-native-appearance!))
                  (sync-theme!)))))))))))

(define (capture-appearance)
  (for/list ([key (in-list appearance-pref-keys)])
    (cons key (preferences:get key))))

(define (restore-snapshot! snapshot #:native-restore? [native-restore? #t])
  (begin-native-state-transaction!)
  (dynamic-wind
    (if native-restore?
        (lambda () (deactivate-native-appearance! #:strict? #t))
        suspend-native-appearance!)
    (lambda ()
      (restore-appearance!
       snapshot preferences:set
       (lambda (dark?) (color-prefs:get-current-color-scheme-name #:wob? dark?))
       color-prefs:set-current-color-scheme))
    synchronize-painter!))

(define (apply-appearance!)
  (begin-native-state-transaction!)
  (define before (capture-appearance))
  (define native-before? native-committed?)
  (define native-mode-before
    (and native-before? (current-native-mode)))
  (define bookkeeping-before
    (for/list ([key (in-list (list snapshot-pref enabled-pref state-pref))])
      (cons key (preferences:get key))))
  (with-handlers ([exn:fail?
                   (lambda (e)
                     (with-handlers ([exn:fail?
                                      (lambda (rollback-error)
                                        (log-openracket-appearance-warning
                                         "Appearance rollback reported an error: ~a"
                                         (exn-message rollback-error)))])
                       ;; Keep the original owned native baseline during failed
                       ;; reapply; explicit user Restore is a separate path.
                       (restore-snapshot! before #:native-restore? #f))
                     (for ([entry (in-list bookkeeping-before)])
                       (with-handlers ([exn:fail?
                                        (lambda (rollback-error)
                                          (log-openracket-appearance-warning
                                           "Appearance state rollback reported an error: ~a"
                                           (exn-message rollback-error)))])
                         (if (eq? (car entry) state-pref)
                             (set-appearance-state! (cdr entry))
                             (preferences:set (car entry) (cdr entry)))))
                     (if native-before?
                         (begin
                           (set! native-committed? #t)
                           (synchronize-native-appearance! native-mode-before))
                         (deactivate-native-appearance!))
                     (log-openracket-appearance-warning
                      "Appearance was not applied; retained host continues: ~a"
                      (exn-message e))
                     #f)])
    (color-prefs:set-current-color-scheme '|OpenRacket Light|)
    (color-prefs:set-current-color-scheme '|OpenRacket Dark|)
    ;; An unknown scheme silently falls back to Classic in Framework. Detect
    ;; a missing info-domain/setup entry rather than claiming success.
    (unless (and (eq? (color-prefs:get-current-color-scheme-name #:wob? #f)
                      '|OpenRacket Light|)
                 (eq? (color-prefs:get-current-color-scheme-name #:wob? #t)
                      '|OpenRacket Dark|))
      (error 'openracket-appearance
             "OpenRacket color schemes are not registered; run local package setup"))
    (preferences:set 'framework:white-on-black-mode?
                     (initial-color-mode
                      (getenv "OPENRACKET_THEME")
                      (preferences:get 'framework:white-on-black-mode?)))
    (preferences:set
     'framework:standard-style-list:font-name
     (preferred-editor-face
      (get-face-list 'mono)
      (preferences:get 'framework:standard-style-list:font-name)))
    ;; Framework 9.3 uses #(per-monitor-sizes default-size), not a bare integer.
    (preferences:set 'framework:standard-style-list:font-size (vector (hash) 13))
    (preferences:set 'framework:standard-style-list:smoothing 'smoothed)
    (unless (eq? (preferences:get state-pref) 'applied)
      (preferences:set snapshot-pref before))
    (preferences:set enabled-pref #t)
    (set-appearance-state! 'applied)
    (activate-native-appearance!)
    ;; Our transaction is now committed; first-frame painting must not depend
    ;; on whether the queued synchronization event has run yet.
    (synchronize-painter!)
    #t))

(define (initialize-once!)
  (define resume-saved-native?
    (and (not startup-native-considered?) (native-appearance-eligible?)))
  (set! startup-native-considered? #t)
  (when (and (modern-session?) (eq? (preferences:get state-pref) 'fresh))
    ;; Persist only successful initialization. A missing scheme is retryable
    ;; after package setup; a user's later preference changes are never reset.
    ;; Theme setup must not prevent the real DrRacket frame from opening.
    (with-handlers ([exn:fail?
                     (lambda (e)
                       (log-openracket-appearance-warning
                        "Nonfatal appearance initialization failure: ~a" (exn-message e)))])
      (apply-appearance!)))
  ;; A previously committed profile starts with its saved editor appearance.
  ;; Consider its explicit native opt-in once per process, not once per frame.
  ;; Later restore/failure must never be undone by opening another stock window.
  (when resume-saved-native?
    (activate-native-appearance!)
    (synchronize-painter!)))

(define tool@
  (unit
    (import drracket:tool^)
    (export drracket:tool-exports^)
    (define (phase1) (void))
    (define (phase2) (void))

    ;; Registration itself is gated: installing this package into an ordinary
    ;; DrRacket profile merely makes the two color schemes available to choose.
    (when (modern-session?)
      (preferences:set-default enabled-pref #t boolean?)
      (preferences:set-default state-pref 'fresh
                               (lambda (v) (and (memq v '(fresh applied restored)) #t)))
      (preferences:set-default snapshot-pref #f snapshot-value?)
      (install-painter-bridge!)

      (preferences:add-panel
       "OpenRacket"
       (lambda (parent)
         (define panel
           (new vertical-panel% [parent parent] [alignment '(left top)]
                [border 16] [spacing 12]))
         (new message% [parent panel]
              [label "Appearance for the original DrRacket editor and tools."])
         (new check-box% [parent panel]
              [label "Roomier editor and toolbar spacing (new windows)"]
              [value (preferences:get enabled-pref)]
              [callback (lambda (box event)
                          (preferences:set enabled-pref (send box get-value)))])
         (new button% [parent panel] [label "Apply OpenRacket appearance"]
              [callback (lambda (button event)
                          (unless (apply-appearance!)
                            (message-box "OpenRacket appearance"
                                         "The appearance change failed. See the log for details."
                                         #f '(ok caution))))])
         (new button% [parent panel] [label "Restore previous appearance"]
              [callback
               (lambda (button event)
                 (with-handlers ([exn:fail?
                                  (lambda (e)
                                    (log-openracket-appearance-warning
                                     "Appearance restore failed: ~a" (exn-message e))
                                    (message-box "OpenRacket appearance"
                                                 "Some appearance settings could not be restored. See the log for details."
                                                 #f '(ok caution)))])
                   (restore-snapshot! (preferences:get snapshot-pref))
                   (preferences:set enabled-pref #f)
                   (set-appearance-state! 'restored)))])
         (new message% [parent panel]
              [label "Fonts and Colors remain in the standard Preferences tabs."])
         panel))

      (drracket:get/extend:extend-definitions-canvas
       (make-canvas-spacing-mixin layout-enabled?))
      (drracket:get/extend:extend-interactions-canvas
       (make-canvas-spacing-mixin layout-enabled?))
      (drracket:get/extend:extend-definitions-canvas
       (make-editor-chrome-mixin layout-enabled? current-chrome-palette))
      (drracket:get/extend:extend-interactions-canvas
       (make-editor-chrome-mixin layout-enabled? current-chrome-palette))
      (drracket:get/extend:extend-unit-frame
       (make-frame-spacing-mixin initialize-once! layout-enabled?))
      (drracket:get/extend:extend-unit-frame
       (make-status-chrome-mixin layout-enabled?))
      (drracket:get/extend:extend-unit-frame track-toolbar-parent-mixin))))
