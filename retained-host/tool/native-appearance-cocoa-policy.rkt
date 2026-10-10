#lang racket/base
(provide cocoa-standard-appearance-eligible? cocoa-effective-mode-matches?)

;; Conservative first-candidate policy. AppKit documents automatic high-contrast
;; variants for Aqua/DarkAqua, but our native candidate has not yet verified that
;; behavior across supported macOS releases. Refuse new mutation whenever the
;; system setting or either current appearance identifies high contrast. Exact
;; prior snapshot restoration is always allowed separately.
(define (cocoa-standard-appearance-eligible?
         explicit-name effective-name increase-contrast?
         #:light-name [light-name "NSAppearanceNameAqua"]
         #:dark-name [dark-name "NSAppearanceNameDarkAqua"])
  (define (standard? name) (or (equal? name light-name) (equal? name dark-name)))
  (and (boolean? increase-contrast?)
       (not increase-contrast?)
       (or (not explicit-name) (standard? explicit-name))
       (standard? effective-name)))

(define (cocoa-effective-mode-matches?
         mode effective-name
         #:light-name [light-name "NSAppearanceNameAqua"]
         #:dark-name [dark-name "NSAppearanceNameDarkAqua"])
  (case mode
    [(light) (equal? effective-name light-name)]
    [(dark) (equal? effective-name dark-name)]
    [else #f]))
