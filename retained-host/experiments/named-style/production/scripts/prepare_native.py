#!/usr/bin/env python3
"""Stage complete pinned style modules for authorized future native tests.
The caller supplies the installed official 9.3 prefs.rkt dependency. No Racket
process is started by this preparation tool, and no installed file is modified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import overlay

PREFS_SHA256 = '8c9d895ffb2d57212d6298152f3d940adfaef97250b0cf18ce0350e7ef2574a4'

HOOK_DECL = b'''
;; TEST ONLY: deterministic observation immediately before complete publication.
(provide openracket-test-before-publication)
(define openracket-test-before-publication
  (make-parameter (lambda (snapshot index) (void))))
'''
HOOK_ANCHOR = b'               (set! openracket-named-style-cache complete)\n'
HOOK_CALL = b'               ((openracket-test-before-publication) snapshot index)\n'

def hooked_bytes(candidate):
    if candidate.count(HOOK_ANCHOR) != 1:
        raise ValueError('test hook anchor is not unique')
    return candidate.replace(b';; for contracts\n', HOOK_DECL + b'\n;; for contracts\n', 1).replace(HOOK_ANCHOR, HOOK_CALL + HOOK_ANCHOR, 1)

def stage(destination, prefs):
    dependency = prefs.read_bytes()
    if hashlib.sha256(dependency).hexdigest() != PREFS_SHA256:
        raise ValueError('prefs.rkt dependency does not match the official 9.3 source pin')
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {'native_executed': False, 'dependency_source': str(prefs.resolve()),
                'dependency_sha256': hashlib.sha256(dependency).hexdigest(), 'modules': {}}
    for arm, source in [('stock', overlay.stock_bytes()), ('candidate', overlay.candidate_bytes()),
                        ('candidate-hook', hooked_bytes(overlay.candidate_bytes()))]:
        folder = destination / arm
        folder.mkdir()
        (folder / 'style.rkt').write_bytes(source)
        (folder / 'prefs.rkt').write_bytes(dependency)
        manifest['modules'][arm] = overlay.sha256(source)
    (destination / 'prepared.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', required=True, type=Path)
    p.add_argument('--prefs', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(stage(a.destination, a.prefs), indent=2))

if __name__ == '__main__':
    main()
