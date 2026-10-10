#!/usr/bin/env python3
"""Generate an isolated, exact-9.3 cooperative budget experiment; never install."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
PIN = 'da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578'
ANCHOR = '(provide color@)\n'
OLD = '[(defer) ((+ start-time 20.0) . <= . (current-inexact-milliseconds))]'
NEW = '[(defer) ((+ start-time openracket-experimental-color-budget-ms) . <= . (current-inexact-milliseconds))]'
CONFIG = ''';; Isolated experiment, default stock 20 ms. This is a cooperative token-loop
;; check, not a deadline: it cannot preempt a lexer call, a don't-stop token, GC,
;; or end-edit-sequence. It changes no lexer state or token/style operations.
(provide openracket-experimental-color-budget-ms)
(define openracket-experimental-color-budget-ms
  (let ([value (getenv "OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS")])
    (cond
      [(or (not value) (equal? value "20")) 20.0]
      [(equal? value "12") 12.0]
      [(equal? value "8") 8.0]
      [(equal? value "4") 4.0]
      [else (error 'openracket-color-budget
                   "experimental budget must be 4, 8, 12, or 20 ms; got ~s" value)])))

'''
raw = (ROOT / 'vendor/color-v9.3.rkt').read_bytes()
if hashlib.sha256(raw).hexdigest() != PIN:
    raise SystemExit('Refuse byte-different upstream source')
source = raw.decode()
assert source.count(ANCHOR) == source.count(OLD) == 1
patched = source.replace(ANCHOR, CONFIG + ANCHOR).replace(OLD, NEW)
# All the lexer, state reuse, don't-stop, style and scheduling code is byte-exact.
assert patched.replace(CONFIG, '', 1).replace(NEW, OLD, 1) == source
out = ROOT / 'overlay/framework/private/color.rkt'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(patched)
manifest = {'racket': '9.3', 'package': 'gui-lib',
            'package_catalog_sha1': '31187c9593c5eaabcb1850c0120408d7d9734496',
            'module': 'framework/private/color.rkt', 'upstream_sha256': PIN,
            'patched_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
            'environment': 'OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS',
            'accepted_values_ms': [4, 8, 12, 20], 'default_ms': 20,
            'native_tested': False, 'speedup_proven': False,
            'activation': 'isolated experiment only; never combine changes for first attribution'}
(ROOT / 'reports/budget-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(ROOT / 'reports/stock-color-budget.patch').write_text(''.join(difflib.unified_diff(
    source.splitlines(True), patched.splitlines(True),
    fromfile='stock9.3/framework/private/color.rkt', tofile='candidate/framework/private/color.rkt')))
print(out)
