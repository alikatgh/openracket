#!/usr/bin/env python3
"""Generate a default-off format guard; no installs, launches or network access."""
from pathlib import Path
import hashlib, json, difflib
ROOT = Path(__file__).resolve().parents[1]
PIN = '7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638'
raw = (ROOT/'vendor/text-misc-v9.3.rkt').read_bytes()
if hashlib.sha256(raw).hexdigest() != PIN:
    raise SystemExit('Refuse byte-different official Framework source')
source = raw.decode('utf-8')
CONFIG = ''';; Default-off experiment: skip only unnecessary format-conversion scans.
;; The separate required autosave format-selection scan remains stock.
;; Non-same-format virtual scan callback counts can differ when explicitly on.
(define openracket-experimental-save-scan-guard?
  (equal? (getenv "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD") "1"))

'''
EXPORT = '(provide text-misc@ openracket-experimental-save-scan-guard?)'
OLD1 = "(and (not (all-string-snips))\n               (eq? format 'same)"
NEW1 = "(and (or (not openracket-experimental-save-scan-guard?) (eq? format 'same))\n               (not (all-string-snips))\n               (eq? format 'same)"
OLD2 = "(when (and (all-string-snips)\n                   (eq? format 'same)"
NEW2 = "(when (and (or (not openracket-experimental-save-scan-guard?) (eq? format 'same))\n                   (all-string-snips)\n                   (eq? format 'same)"
assert source.count('(provide text-misc@)') == source.count(OLD1) == source.count(OLD2) == 1
patched = source.replace('(provide text-misc@)', CONFIG + EXPORT).replace(OLD1, NEW1).replace(OLD2, NEW2)
assert patched.replace(CONFIG,'',1).replace(EXPORT,'(provide text-misc@)',1).replace(NEW1,OLD1,1).replace(NEW2,OLD2,1) == source
out = ROOT/'overlay/framework/private/text-misc.rkt'
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(patched)
manifest = {
    'racket':'9.3', 'package':'gui-lib',
    'package_catalog_sha1':'31187c9593c5eaabcb1850c0120408d7d9734496',
    'module':'framework/private/text-misc.rkt',
    'upstream_sha256': PIN,
    'patched_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
    'environment':'OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1',
    'activation_export':'openracket-experimental-save-scan-guard?',
    'default_enabled':False,
    'scope':'two format-conversion scan predicates only; no cache or save-hook removal',
    'stock_autosave_format_selection':'unchanged',
    'extension_caveat':'non-same-format custom find-first-snip/next callback counts can differ when enabled',
    'native_tested':False, 'measured_benefit':False,
}
(ROOT/'reports/autosave-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(ROOT/'reports/stock-autosave-guard.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),patched.splitlines(True),fromfile='stock9.3/framework/private/text-misc.rkt',tofile='candidate/framework/private/text-misc.rkt')))
print(out)
