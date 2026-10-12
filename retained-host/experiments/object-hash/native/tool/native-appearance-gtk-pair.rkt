#lang racket/base
(provide recognized-gtk-theme-pair recognized-gtk-current-state? (struct-out gtk-theme-pair))

;; Pure capability probe. A provider being non-null is insufficient: GTK may
;; silently fall back. Compare its resolved CSS with the installed dark variant.
;; css-ref takes a theme name and #f/"dark" variant, and returns CSS text or #f.
;; No additional theme families are inferred from arbitrary user theme names.
(struct gtk-theme-pair (light dark) #:transparent)
(define (recognized-gtk-current-state? name prefer-dark?)
  ;; Stock's cache listener keys on the name, not prefer-dark. Adwaita plus a
  ;; true preference could already have dark styles behind a light-name flag;
  ;; a light request would then change no name and leave that cache stale.
  (or (and (equal? name "Adwaita") (not prefer-dark?))
      (equal? name "Adwaita-dark")))
(define (recognized-gtk-theme-pair current-name css-ref)
  (and (member current-name '("Adwaita" "Adwaita-dark"))
       (let ([light (css-ref "Adwaita" #f)]
             [dark (css-ref "Adwaita" "dark")]
             [named-dark (css-ref "Adwaita-dark" #f)]
             [named-dark-variant (css-ref "Adwaita-dark" "dark")])
         (and (andmap (lambda (s) (and (string? s) (positive? (string-length s))))
                      (list light dark named-dark named-dark-variant))
              (not (equal? light dark))
              (equal? dark named-dark)
              (equal? dark named-dark-variant)
              (gtk-theme-pair "Adwaita" "Adwaita-dark")))))
