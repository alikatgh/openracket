#lang info
(define collection "openracket-native-quit-driver")
(define pkg-desc "Separate CI-only genuine native Quit and temporary unsaved-file driver")
(define version "0.1")
(define pkg-authors '(openracket))
(define deps '("base" "gui-lib" "drracket-plugin-lib" "string-constants-lib"))
(define drracket-tools '(("tool.rkt")))
(define drracket-tool-names '("OpenRacket Native Quit CI Driver"))
