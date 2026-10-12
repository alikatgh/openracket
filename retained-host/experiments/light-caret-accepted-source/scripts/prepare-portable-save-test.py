#!/usr/bin/env python3
"""Derive combined-host save gate from the exact already-passing 1448 harness."""
from pathlib import Path
import hashlib, json, difflib
ROOT=Path(__file__).resolve().parents[1]
original=(ROOT/'tests/reference/autosave-host-1448.rkt').read_bytes()
assert hashlib.sha256(original).hexdigest()=='8667ce69410f8d9abc5f3097c63bcf587d006aee4681733cb6697707a43ca466'
s=original.decode()
replacements=[
(';; Native-only correctness caller. PREPARED, NOT EXECUTED LOCALLY.',
 ';; Combined installed appearance/autosave gate derived from passing 1448 caller.\n;; This combined caller remains unexecuted until its separate native gate.'),
("(memq mode '(stock candidate-off candidate-on))", "(memq mode '(candidate-off candidate-on))"),
('"OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"\n               "OPENRACKET_HOST_THEME" "OPENRACKET_THEME" "OPENRACKET_UI"',
 '"OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"'),
('  (define flag (getenv "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD"))',
 '''  (for ([entry '(("OPENRACKET_UI" . "modern") ("OPENRACKET_HOST_THEME" . "1")
                 ("OPENRACKET_THEME" . "dark") ("OPENRACKET_NATIVE_APPEARANCE" . "1"))])
    (assert! (equal? (getenv (car entry)) (cdr entry))
             (format "Combined appearance environment mismatch: ~a" (car entry))))
  (define flag (getenv "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD"))'''),
('"532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de")',
 '''"d80e67b0285da13291d5650b56de4a616db5a217e63c51a6cf95c040603add31")
  (source! "openracket-paint.rkt" '("mrlib" "private")
           "38c8f8197ed6f08373b4768a053abf1ff09cc1ff0e475e6d3d72a237775fa354")'''),
("       (define verify? (pref-get 'framework:verify-change-format))",
 '''       (assert! (eq? (pref-get 'openracket:appearance-state) 'applied)
                "Combined host appearance must actually be applied")
       (define scheme-name (dynamic-require 'framework 'color-prefs:get-current-color-scheme-name))
       (assert! (and (eq? (scheme-name #:wob? #f) '|OpenRacket Light|)
                     (eq? (scheme-name #:wob? #t) '|OpenRacket Dark|))
                "Both installed OpenRacket schemes must be selected")
       (define painter-mode (dynamic-require 'mrlib/private/openracket-paint 'get-modern-host-theme))
       (assert! (eq? (painter-mode) 'dark) "Combined toolbar must match the dark editor")
       (define verify? (pref-get 'framework:verify-change-format))'''),
('"native stock-default save/copy/WXME/autosave artifact reload"',
 '"combined modern host: stock-default save/copy/WXME/autosave artifact reload"'),
("'other_experiments \"absent\"", "'other_experiments \"scan and color budget absent; retained appearance active\"")
]
for before,after in replacements:
 assert s.count(before)==1,before
 s=s.replace(before,after,1)
# Check complete invertibility so no unlisted helper, save or failure assertion changes.
restored=s
for before,after in reversed(replacements):
 assert restored.count(after)==1,after
 restored=restored.replace(after,before,1)
assert restored.encode()==original
out=ROOT/'tests/portable-native-save-host.rkt';out.write_text(s)
(ROOT/'reports/portable-save-caller.patch').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),s.splitlines(True),fromfile='passing-autosave-1448',tofile='portable-combined-save')))
(ROOT/'reports/portable-save-caller.json').write_text(json.dumps({'original_sha256':hashlib.sha256(original).hexdigest(),'combined_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'allowed_changes':[before for before,_ in replacements],'save_fixture_bytes_unchanged':True,'native_combined_run':False},indent=2)+'\n')
print(out)
