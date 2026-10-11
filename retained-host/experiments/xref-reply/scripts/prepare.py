#!/usr/bin/env python3
"""Build a default-off, exact-byte-pinned Racket 9.3 xref reply experiment."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7"
FLAG = "OPENRACKET_XREF_REPLY_CELL"

INSERT_BEFORE = b"(define xref (load-collections-xref))"
INSERT = ''';; OpenRacket experiment: default-off one-shot replies, no new lookup cache.
(define openracket-xref-reply-cell-enabled?
  (equal? (getenv "OPENRACKET_XREF_REPLY_CELL") "1"))
(provide openracket-xref-reply-cell-enabled?)

'''.encode('utf-8')
OLD_REPLY = '''          (thread
           (λ ()
             (sync (channel-put-evt resp-chan resp)
                   nack-evt)))'''.encode('utf-8')
NEW_REPLY = '''          (if openracket-xref-reply-cell-enabled?
              (begin
                ;; Here resp-chan is a private box and nack-evt is its ready
                ;; semaphore. Accepted requests retain stock lookup/cache work,
                ;; even if their caller has since been canceled.
                (set-box! resp-chan resp)
                (semaphore-post nack-evt))
              (thread
               (λ ()
                 (sync (channel-put-evt resp-chan resp)
                       nack-evt))))'''.encode('utf-8')
OLD_CALLER = '''           (define resp-chan (make-channel))
           (channel-put req-chan (list binding-info (current-directory) resp-chan nack-evt))
           resp-chan'''.encode('utf-8')
NEW_CALLER = '''           (define resp-chan
             (if openracket-xref-reply-cell-enabled? (box #f) (make-channel)))
           (define ready
             (and openracket-xref-reply-cell-enabled? (make-semaphore 0)))
           (channel-put req-chan
                        (list binding-info (current-directory) resp-chan (or ready nack-evt)))
           (if ready
               (wrap-evt ready (λ (_) (unbox resp-chan)))
               resp-chan)'''.encode('utf-8')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def generate(source):
    if sha(source) != PIN:
        raise ValueError("Refusing xref.rkt: original byte SHA256 differs from official 9.3 pin")
    out = source
    for old, new in [(INSERT_BEFORE, INSERT + INSERT_BEFORE),
                     (OLD_REPLY, NEW_REPLY), (OLD_CALLER, NEW_CALLER)]:
        if out.count(old) != 1:
            raise ValueError("Pinned source replacement is not unique")
        out = out.replace(old, new)
    return out

def main():
    src = (ROOT / "vendor/xref.rkt").read_bytes()
    out = generate(src)
    (ROOT / "overlay/xref.rkt").write_bytes(out)
    manifest = {
        "experiment": "xref-one-shot-reply-cell", "racket_version": "9.3",
        "flag": FLAG, "enabled_value": "1", "default_enabled": False,
        "relative_target": "drracket/private/syncheck/xref.rkt",
        "package": "drracket-tool-text-lib",
        "original_sha256": PIN, "patched_sha256": sha(out),
        "upstream_git_blob": "3ca132d8afc9b1353e898c164ea92cf1c0fd144d",
        "source_url": "https://github.com/racket/drracket/blob/v9.3/drracket-tool-text-lib/drracket/private/syncheck/xref.rkt",
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    diff = "".join(difflib.unified_diff(src.decode().splitlines(True),
                                     out.decode().splitlines(True),
                                     "official-9.3/xref.rkt", "experiment/xref.rkt"))
    (ROOT / "patch.diff").write_text(diff)
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
