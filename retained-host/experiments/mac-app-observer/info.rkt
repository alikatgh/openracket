#lang info
(define collection "openracket-mac-app-observer")
(define pkg-desc "CI-only read-only native OpenRacket application observer")
(define version "0.1")
(define pkg-authors '(openracket))
(define deps '("base" "gui-lib" "drracket-plugin-lib" "string-constants-lib"))
(define drracket-tools '(("tool.rkt")))
(define drracket-tool-names '("OpenRacket Native App CI Observer"))
