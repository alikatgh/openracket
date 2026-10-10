#lang racket/base
(require ffi/unsafe ffi/unsafe/atomic
         "native-appearance.rkt" "native-appearance-gtk-pair.rkt")
(provide make-gtk-appearance-adapter)

;; EXPERIMENTAL, gated separately from Cocoa. Only the already-selected Adwaita
;; family is eligible, and both resolved named/variant CSS providers must prove
;; the real dark counterpart exists (GTK silently falls back for unknown names).
;;
;; Racket 9.3's stock gtk/style.rkt listens to gtk-theme-name, derives its dark
;; bit from that name, then rebuilds cached label/selection colors. Set the app's
;; prefer-dark first and its recognized paired name last, so that real listener
;; observes the final style. No fake notifications or private cache calls.
;;
;; GtkSettings values are process-local. We preserve/restore exact prior values,
;; but public GTK APIs cannot reveal their original app-vs-desktop source. This
;; adapter therefore MUST remain opt-in experimental, not strict-parity default.
;; Never resets properties, writes desktop settings/config, or changes titlebars.
;; Only the default existing GTK screen is in scope.
;; API references:
;; https://docs.gtk.org/gtk3/class.Settings.html
;; https://docs.gtk.org/gtk3/type_func.CssProvider.get_named.html
;; https://docs.gtk.org/gtk3/method.CssProvider.to_string.html
;; gtk_settings_reset_property exists, but using it would erase a preexisting
;; application override. It cannot reconstruct unknown prior source provenance.
(define dark-property "gtk-application-prefer-dark-theme")
(define name-property "gtk-theme-name")
(struct saved-gtk (settings name prefer-dark? [released? #:mutable]))
(define (make-gtk-appearance-adapter gui-thread?)
  (unless (and (eq? (system-type 'os) 'unix) (gui-thread?))
    (error 'native-appearance "GTK adapter requires the existing GUI handler thread"))
  (when (let ([forced (getenv "GTK_THEME")]) (and forced (not (equal? forced ""))))
    (error 'native-appearance "GTK_THEME override prevents verifying app-local appearance"))
  (define gtk (ffi-lib "libgtk-3" '("0" "")))
  (define gobject (ffi-lib "libgobject-2.0" '("0" "")))
  (define glib (ffi-lib "libglib-2.0" '("0" "")))
  (define free (get-ffi-obj "g_free" glib (_fun _pointer -> _void)))
  (define get-settings (get-ffi-obj "gtk_settings_get_default" gtk (_fun -> _pointer)))
  (define get-bool
    (get-ffi-obj "g_object_get" gobject
                 (_fun #:varargs-after 2 _pointer _string/utf-8
                       (value : (_ptr o _int)) (_pointer = #f) -> _void -> (not (zero? value)))))
  (define get-string-pointer
    (get-ffi-obj "g_object_get" gobject
                 (_fun #:varargs-after 2 _pointer _string/utf-8
                       (value : (_ptr o _pointer)) (_pointer = #f) -> _void -> value)))
  (define set-bool
    (get-ffi-obj "g_object_set" gobject
                 (_fun #:varargs-after 2 _pointer _string/utf-8 _int (_pointer = #f) -> _void)))
  (define set-string
    (get-ffi-obj "g_object_set" gobject
                 (_fun #:varargs-after 2 _pointer _string/utf-8 _string/utf-8
                       (_pointer = #f) -> _void)))
  (define css-provider
    (get-ffi-obj "gtk_css_provider_get_named" gtk
                 (_fun _string/utf-8 _string/utf-8 -> _pointer)))
  (define css-string
    (get-ffi-obj "gtk_css_provider_to_string" gtk (_fun _pointer -> _pointer)))
  (define retain (get-ffi-obj "g_object_ref" gobject (_fun _pointer -> _pointer)))
  (define release (get-ffi-obj "g_object_unref" gobject (_fun _pointer -> _void)))
  (define (owned-string->racket pointer)
    (and pointer
         (dynamic-wind void
                       (lambda () (cast pointer _pointer _string/utf-8))
                       (lambda () (free pointer)))))
  (define (get-name object)
    (owned-string->racket (get-string-pointer object name-property)))
  (define (css-ref name variant)
    (define provider (css-provider name variant)) ; borrowed: never unref
    (and provider (owned-string->racket (css-string provider))))
  (define (ready!)
    (unless (gui-thread?) (error 'native-appearance "GTK operation requires the GUI handler thread")))
  (ready!)
  (define settings (get-settings))
  (unless settings (error 'native-appearance "Existing GTK display has no settings object"))
  (unless (call-as-atomic
           (lambda () (recognized-gtk-current-state? (get-name settings)
                                                       (get-bool settings dark-property))))
    (error 'native-appearance "Current GTK name/preference pair cannot safely refresh stock color caches"))
  (define pair
    (call-as-atomic (lambda () (recognized-gtk-theme-pair (get-name settings) css-ref))))
  (unless pair
    (error 'native-appearance "Current GTK theme has no positively verified supported dark/light pair"))
  (define (write! object name prefer-dark?)
    ;; Do not freeze/thaw or synthesize notifications: preserve GTK's own native
    ;; propagation and the retained Racket stock listener.
    (unless (eq? (get-bool object dark-property) prefer-dark?)
      (set-bool object dark-property (if prefer-dark? 1 0)))
    (unless (equal? (get-name object) name)
      (set-string object name-property name))
    (unless (and (eq? (get-bool object dark-property) prefer-dark?)
                 (equal? (get-name object) name))
      (error 'native-appearance "GTK did not retain the requested app-local appearance values")))
  (define adapter
   (native-appearance-adapter
   'gtk3-candidate gui-thread?
   (lambda ()
     (ready!)
     (call-as-atomic
      (lambda ()
        (define name (get-name settings))
        (define prefer-dark? (get-bool settings dark-property))
        (unless (recognized-gtk-current-state? name prefer-dark?)
          (error 'native-appearance "GTK theme changed to an unsupported name/preference pair"))
        (retain settings)
        (saved-gtk settings name prefer-dark? #f))))
   (lambda (mode)
     (ready!)
     (call-as-atomic
      (lambda ()
        ;; If another component selects a different family while active, refuse
        ;; to replace it. The controller can still restore its saved baseline.
        (unless (member (get-name settings)
                        (list (gtk-theme-pair-light pair) (gtk-theme-pair-dark pair)))
          (error 'native-appearance "GTK theme changed to an unsupported family"))
        (write! settings
                (if (eq? mode 'dark) (gtk-theme-pair-dark pair) (gtk-theme-pair-light pair))
                (eq? mode 'dark)))))
   (lambda (saved)
     (ready!)
     (when (saved-gtk-released? saved) (error 'native-appearance "Checkpoint already released"))
     (call-as-atomic
      (lambda () (write! (saved-gtk-settings saved)
                         (saved-gtk-name saved) (saved-gtk-prefer-dark? saved)))))
   (lambda (saved)
     (ready!)
     (unless (saved-gtk-released? saved)
       (set-saved-gtk-released?! saved #t)
       (release (saved-gtk-settings saved))))
   (lambda ()
     (ready!)
     (call-as-atomic
      (lambda () (hash 'backend 'gtk3-candidate
                       'theme-name (get-name settings)
                       'prefer-dark? (get-bool settings dark-property)
                       'resolved-pair-verified? #t
                       'inheritance-source-restorable? #f
                       'stock-color-cache-validated? #f))))))
  (set-native-appearance-adapter-matches?!
   adapter
   (lambda (mode)
     (ready!)
     (call-as-atomic
      (lambda ()
        (and (equal? (get-name settings)
                     (if (eq? mode 'dark) (gtk-theme-pair-dark pair) (gtk-theme-pair-light pair)))
             (eq? (get-bool settings dark-property) (eq? mode 'dark)))))))
  adapter)
