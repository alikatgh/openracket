#!/usr/bin/env python3
"""Exact, fail-closed insertion overlay for the official Racket 9.3 style source.
No native code is run, no source is downloaded, and no default target is chosen.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STOCK_SHA256 = '2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0'
FLAG = 'OPENRACKET_NAMED_STYLE_INDEX'

def sha256(data):
    return hashlib.sha256(data).hexdigest()

# Every edit is a reversible insertion: the stock method/branches remain intact.
INSERTIONS = [
    (b'         style-list%\n', b'''         openracket-named-style-index-enabled?
         openracket-named-style-index-state
''', 'after'),
    (b'(define-struct notify-key (f))\n', b'''
;; OPENRACKET NAMED STYLE INDEX: default-off, pinned-source experiment.
(define openracket-named-style-index-enabled?
  (equal? (getenv "OPENRACKET_NAMED_STYLE_INDEX") "1"))

;; A fresh local member key avoids collisions with existing subclass methods.
(define-local-member-name get-openracket-named-style-index-state)
(define (openracket-named-style-index-state style-list)
  (unless (is-a? style-list style-list%)
    (raise-argument-error 'openracket-named-style-index-state
                          "style-list% instance" style-list))
  (send style-list get-openracket-named-style-index-state))
''', 'after'),
    (b'  (define member-count 1)\n', b'''
  ;; The only cache cell holds one complete immutable (members . index) pair.
  ;; Names in members were made immutable before insertion by the stock code.
  ;; A stale build may replace a newer cache, but cannot match a newer snapshot.
  (define openracket-named-style-cache #f)
  (define openracket-named-style-lookups 0)
  (define openracket-named-style-hits 0)
  (define openracket-named-style-rebuilds 0)
  (define openracket-named-style-members-traversed 0)

  ;; Read-only, O(1), payload-free. No lookup, rebuild, or eager prewarming.
  ;; Counters are diagnostic scalars, not synchronized cross-thread accounting.
  (define/public (get-openracket-named-style-index-state)
    (let ([cached openracket-named-style-cache]
          [snapshot members])
      (hasheq 'enabled openracket-named-style-index-enabled?
              'lookups openracket-named-style-lookups
              'hits openracket-named-style-hits
              'rebuilds openracket-named-style-rebuilds
              'members-traversed openracket-named-style-members-traversed
              'cache-valid (and cached (eq? snapshot (car cached)))
              'named-entries (if cached (hash-count (cdr cached)) 0)
              'member-count member-count)))
''', 'after'),
    (b'  (def/public (find-named-style [string? name])\n', b'''    (if openracket-named-style-index-enabled?
        (let* ([snapshot members]
               [cached openracket-named-style-cache])
          (set! openracket-named-style-lookups
                (add1 openracket-named-style-lookups))
          (define entry
            (cond
              [(and cached (eq? snapshot (car cached)))
               (set! openracket-named-style-hits
                     (add1 openracket-named-style-hits))
               cached]
              [else
               (define index
                 (for/fold ([index (hash)]) ([style (in-list snapshot)])
                   (set! openracket-named-style-members-traversed
                         (add1 openracket-named-style-members-traversed))
                   (define style-name (send style get-s-name))
                   (if (and style-name (not (hash-has-key? index style-name)))
                       (hash-set index style-name style)
                       index)))
               (define complete (cons snapshot index))
               (set! openracket-named-style-cache complete)
               (set! openracket-named-style-rebuilds
                     (add1 openracket-named-style-rebuilds))
               complete]))
          (hash-ref (cdr entry) name #f))
''', 'after'),
    (b'      (and (equal? name (send s get-s-name))\n           s)))\n\n  (define/public (do-named-style', b'    )\n', 'middle'),
]

# Last insertion is at the exact end of the original find-named-style form.
# Insert the wrapping if close BEFORE the original method's closing paren:
# its exact original body bytes remain a contiguous subsequence.
def apply_bytes(data):
    if sha256(data) != STOCK_SHA256:
        raise ValueError('refusing unpinned input; expected official 9.3 style.rkt SHA256 ' + STOCK_SHA256)
    out = data
    for anchor, addition, where in INSERTIONS[:-1]:
        if out.count(anchor) != 1:
            raise ValueError('source anchor is not unique')
        out = out.replace(anchor, anchor + addition, 1)
    # The additional close belongs to the method: stock s))) now closes the if.
    anchor, addition, _ = INSERTIONS[-1]
    if out.count(anchor) != 1:
        raise ValueError('lookup-end anchor is not unique')
    out = out.replace(anchor, anchor.replace(b'\n\n  (define/public', b'\n' + addition + b'\n  (define/public'), 1)
    return out

def stock_bytes():
    data = (ROOT / 'vendor/style.rkt').read_bytes()
    if sha256(data) != STOCK_SHA256:
        raise ValueError('vendored source failed its official source pin')
    return data

def candidate_bytes():
    return apply_bytes(stock_bytes())

def revert_bytes(data):
    expected = candidate_bytes()
    if data != expected:
        raise ValueError('refusing to revert anything other than the exact generated candidate')
    out = data
    anchor, addition, _ = INSERTIONS[-1]
    extended = anchor.replace(b'\n\n  (define/public', b'\n' + addition + b'\n  (define/public')
    out = out.replace(extended, anchor, 1)
    for anchor, addition, where in reversed(INSERTIONS[:-1]):
        out = out.replace(anchor + addition, anchor, 1)
    if out != stock_bytes():
        raise ValueError('insertion removal did not restore the exact pinned source')
    return out

def canonical_path(path):
    given = Path(path).absolute()
    for part in (given, *given.parents):
        if part.is_symlink():
            raise ValueError('symlinked path or ancestor refused; supply a canonical disposable-copy path')
    canonical = given.resolve(strict=True)
    if canonical != given:
        raise ValueError('noncanonical path refused; supply its fully resolved path')
    return canonical


def confined_file(path, root):
    source = canonical_path(path)
    if not source.is_file() or not source.is_relative_to(root):
        raise ValueError('source must be a regular file beneath the explicit runtime root')
    if source.stat().st_nlink != 1:
        raise ValueError('hard-linked source refused; use an independent deep copy')
    return source


def operate(action, runtime_root, target, *, disposable=False):
    if action not in ('verify', 'apply', 'revert'):
        raise ValueError('invalid source operation')
    if action != 'verify' and not disposable:
        raise ValueError('explicit acknowledgement of an independent disposable runtime copy is required')
    root = canonical_path(runtime_root)
    if not root.is_dir():
        raise ValueError('runtime root must be an existing directory')
    source = confined_file(target, root)
    suffix = ('racket', 'snip', 'private', 'style.rkt')
    if source.parts[-len(suffix):] != suffix:
        raise ValueError('target must end with the pinned racket/snip/private/style.rkt collection path')
    dependency = confined_file(source.with_name('prefs.rkt'), root)
    if dependency.read_bytes() != (ROOT / 'vendor/prefs.rkt').read_bytes():
        raise ValueError('sibling prefs.rkt differs from its official pinned source')
    if sha256(dependency.read_bytes()) != '8c9d895ffb2d57212d6298152f3d940adfaef97250b0cf18ce0350e7ef2574a4':
        raise ValueError('vendored prefs.rkt failed its pin')
    original = stock_bytes()
    candidate = candidate_bytes()
    current = source.read_bytes()
    if current not in (original, candidate):
        raise ValueError('target is neither exact pinned stock nor exact generated candidate')
    if action == 'verify':
        replacement = current
    elif action == 'apply':
        replacement = candidate if current == candidate else apply_bytes(current)
    else:
        replacement = original if current == original else revert_bytes(current)
    changed = replacement != current
    if changed:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=source.parent, prefix='.named-style-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(replacement)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, source.stat().st_mode & 0o777)
            os.replace(temporary, source)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if source.read_bytes() != replacement:
            raise RuntimeError('post-write source verification failed')
    return {'status': 'stock' if replacement == original else 'candidate', 'changed': changed,
            'runtime_root': str(root), 'path': str(source), 'sha256': sha256(replacement),
            'stock_sha256': sha256(original), 'candidate_sha256': sha256(candidate),
            'prefs_sha256': sha256(dependency.read_bytes())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['generate', 'verify', 'apply', 'revert'])
    p.add_argument('--target', type=Path)
    p.add_argument('--runtime-root', type=Path)
    p.add_argument('--confirm-disposable-copy', action='store_true')
    args = p.parse_args()
    if args.action == 'generate':
        if args.target or args.runtime_root or args.confirm_disposable_copy:
            p.error('generate writes only overlay/style.rkt; runtime/target options are not accepted')
        candidate = candidate_bytes()
        (ROOT / 'overlay/style.rkt').write_bytes(candidate)
        result = {'status': 'generated', 'stock_sha256': STOCK_SHA256,
                  'candidate_sha256': sha256(candidate), 'flag': FLAG, 'activation': 'exact string 1 only'}
    else:
        if args.target is None or args.runtime_root is None:
            p.error('--runtime-root and --target must explicitly identify the canonical runtime and source')
        result = operate(args.action, args.runtime_root, args.target,
                         disposable=args.confirm_disposable_copy)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
