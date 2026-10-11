#!/usr/bin/env python3
"""Generate one default-off direct-insert experiment from pinned Racket 9.3 data-lib."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de"
SUPPORT_PINS = {
    "skip-list.rkt": "d92807a371dc56c9dafd556b1f87b13c0f99fd3ec0fa4d4e244afb5e78bef46b",
    "private/skip-list.rkt": "559e7843e71c934ecde37fd2cf8983d84fedfa90729adce1da738cb0a7114833",
    "order.rkt": "a6b436ef6c8842a508634931e52dc7e8bdcfb7391094f7c36cf51d93d03b6f8f",
}
FLAG = "OPENRACKET_INTERVAL_MAP_FAST_SET"
ANCHOR = b"(define not-given (gensym 'not-given))\n"
ADDITION = b'''
;; OpenRacket experiment: avoid a second general traversal after removal has
;; established that the complete interval is empty. Public contracts, removal,
;; interval boundaries and all other operations remain the stock definitions.
(define openracket-interval-map-fast-set-enabled?
  (equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1"))
(provide openracket-interval-map-fast-set-enabled?)
'''
OLD = b"  (interval-map-update*! im start end (lambda (old) value) #f))"
NEW = b'''  (if openracket-interval-map-fast-set-enabled?
      (skip-list-set! (interval-map-s im) start (cons (- end start) value))
      (interval-map-update*! im start end (lambda (old) value) #f)))'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate(source):
    if sha(source) != PIN:
        raise ValueError("Refusing interval-map.rkt: source differs from the official 9.3 pin")
    if source.count(ANCHOR) != 1 or source.count(OLD) != 1:
        raise ValueError("Pinned source seams must be unique")
    return source.replace(ANCHOR, ANCHOR + ADDITION).replace(OLD, NEW)


def main():
    original = (ROOT / "vendor/interval-map.rkt").read_bytes()
    patched = generate(original)
    (ROOT / "overlay/interval-map.rkt").write_bytes(patched)
    manifest = {
        "experiment": "interval-map-direct-set", "racket_version": "9.3",
        "package": "data-lib", "package_version": "1.2.1",
        "upstream_commit": "f6d64c1e3c4913d9fb2fc8057ccd0ea87b5019af",
        "source_url": "https://github.com/racket/data/blob/f6d64c1e3c4913d9fb2fc8057ccd0ea87b5019af/data-lib/data/interval-map.rkt",
        "relative_target": "data/interval-map.rkt", "flag": FLAG,
        "enabled_value": "1", "default_enabled": False,
        "activation_export": "openracket-interval-map-fast-set-enabled?",
        "original_sha256": PIN, "patched_sha256": sha(patched),
        "unchanged_support_sha256_relative_to_data": SUPPORT_PINS,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "patch.diff").write_text("".join(difflib.unified_diff(
        original.decode().splitlines(True), patched.decode().splitlines(True),
        "official-9.3/data/interval-map.rkt", "experiment/data/interval-map.rkt")))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
