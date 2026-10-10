#lang racket/base
(require ffi/unsafe ffi/unsafe/objc ffi/unsafe/nsalloc
         "native-appearance.rkt" "native-appearance-cocoa-policy.rkt")
(provide make-cocoa-appearance-adapter)

;; This factory is loaded only for an already-running Cocoa GUI. It does not
;; set NSUserDefaults, Info.plist, NSWindow style masks, titlebars, or OS settings.
;; API: https://developer.apple.com/documentation/appkit/nsapplication/appearance
;; Racket 9.3 cocoa/queue.rkt:129-141 already observes effectiveAppearance and
;; schedules its stock dark-mode event and canvas refresh. Its cocoa/procs.rkt
;; reads native colors under that effective appearance. No additional observers
;; or custom refresh callbacks are installed here.
;; Aqua/DarkAqua is Apple's recommended way to let AppKit automatically choose a
;; high-contrast variant. Until that path is genuinely verified for this adapter,
;; we conservatively refuse a NEW mutation in high-contrast state. Exact saved
;; appearance restoration stays allowed; do not assign accessibility names.
;; https://developer.apple.com/documentation/appkit/nsappearance/name-swift.struct/accessibilityhighcontrastdarkaqua
(struct saved-cocoa (appearance [released? #:mutable]))
(define (make-cocoa-appearance-adapter gui-thread?)
  (unless (and (eq? (system-type 'os) 'macosx) (gui-thread?))
    (error 'native-appearance "Cocoa adapter requires the existing GUI handler thread"))
  (define appkit
    (ffi-lib "/System/Library/Frameworks/AppKit.framework/AppKit"))
  (import-class NSApplication NSAppearance NSThread NSWorkspace)
  (define (ready!)
    (unless (and (gui-thread?) (tell #:type _BOOL NSThread isMainThread))
      (error 'native-appearance "Cocoa operation requires the existing main GUI thread")))
  (ready!)
  (define app (tell NSApplication sharedApplication))
  (for ([selector '("appearance" "setAppearance:" "effectiveAppearance")])
    (unless (tell #:type _BOOL app respondsToSelector: (sel_registerName selector))
      (error 'native-appearance "NSApplication appearance is unavailable")))
  (define aqua (get-ffi-obj "NSAppearanceNameAqua" appkit _id))
  (define dark-aqua (get-ffi-obj "NSAppearanceNameDarkAqua" appkit _id))
  (define light-name (tell #:type _string/utf-8 aqua UTF8String))
  (define dark-name (tell #:type _string/utf-8 dark-aqua UTF8String))
  (define (same-id? a b)
    (or (and (not a) (not b)) (and a b (ptr-equal? a b))))
  (define (set-exact! appearance)
    (unless (same-id? appearance (tell app appearance))
      (tellv app setAppearance: appearance))
    (unless (same-id? appearance (tell app appearance))
      (error 'native-appearance "NSApplication did not retain the requested appearance")))
  (define (name-of appearance)
    (and appearance
         (tell #:type _string/utf-8 (tell appearance name) UTF8String)))
  (define workspace (tell NSWorkspace sharedWorkspace))
  (define contrast-selector (sel_registerName "accessibilityDisplayShouldIncreaseContrast"))
  (define (increase-contrast?)
    (if (tell #:type _BOOL workspace respondsToSelector: contrast-selector)
        (tell #:type _BOOL workspace accessibilityDisplayShouldIncreaseContrast)
        'unknown))
  (define (eligible!)
    (unless (cocoa-standard-appearance-eligible?
             (name-of (tell app appearance))
             (name-of (tell app effectiveAppearance)) (increase-contrast?)
             #:light-name light-name #:dark-name dark-name)
      (error 'native-appearance "High-contrast or unknown Cocoa appearance remains untouched")))
  (with-autorelease (eligible!))
  (define adapter
   (native-appearance-adapter
   'cocoa gui-thread?
   (lambda ()
     (ready!)
     (with-autorelease
       ;; Recheck before capture, so an accessibility change while active cannot
       ;; cause even a rollback setter invocation for a rejected mode change.
       (eligible!)
       (define previous (tell app appearance))
       (when previous (tellv previous retain))
       (saved-cocoa previous #f)))
   (lambda (mode)
     (ready!)
     (with-autorelease
       (eligible!)
       (define target (tell NSAppearance appearanceNamed: (if (eq? mode 'dark) dark-aqua aqua)))
       (unless target (error 'native-appearance "Requested native appearance is unavailable"))
       (set-exact! target)
       ;; A retained explicit property alone does not prove the native interface
       ;; actually adopted the requested effective appearance. Roll back if not.
       (eligible!)
       (unless (cocoa-effective-mode-matches?
                mode (name-of (tell app effectiveAppearance))
                #:light-name light-name #:dark-name dark-name)
         (error 'native-appearance "Cocoa effective appearance does not match the requested mode"))))
   (lambda (saved)
     (ready!)
     (when (saved-cocoa-released? saved) (error 'native-appearance "Checkpoint already released"))
     (with-autorelease (set-exact! (saved-cocoa-appearance saved))))
   (lambda (saved)
     (ready!)
     (unless (saved-cocoa-released? saved)
       (set-saved-cocoa-released?! saved #t)
       (when (saved-cocoa-appearance saved) (tellv (saved-cocoa-appearance saved) release))))
   (lambda ()
     (ready!)
     (with-autorelease
       (hash 'backend 'cocoa
             'explicit-name (name-of (tell app appearance))
             'effective-name (name-of (tell app effectiveAppearance))
             'increase-contrast? (increase-contrast?))))))
  (set-native-appearance-adapter-matches?!
   adapter
   (lambda (mode)
     (ready!)
     (with-autorelease
       (define explicit (name-of (tell app appearance)))
       (and (cocoa-standard-appearance-eligible?
             explicit (name-of (tell app effectiveAppearance)) (increase-contrast?)
             #:light-name light-name #:dark-name dark-name)
            (cocoa-effective-mode-matches? mode explicit
                                           #:light-name light-name #:dark-name dark-name)
            (cocoa-effective-mode-matches? mode (name-of (tell app effectiveAppearance))
                                           #:light-name light-name #:dark-name dark-name)))))
  adapter)
