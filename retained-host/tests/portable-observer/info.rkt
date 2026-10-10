#lang info
(define collection "openracket-portable-observer")
(define pkg-desc "CI-only read-only observer for the real OpenRacket launcher")
(define version "0.1")
(define pkg-authors '(openracket))
(define deps '("base" "gui-lib" "drracket-plugin-lib" "string-constants-lib"))
(define drracket-tools '(("tool.rkt")))
(define drracket-tool-names '("OpenRacket Portable CI Observer"))
