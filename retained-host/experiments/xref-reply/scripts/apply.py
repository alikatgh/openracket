#!/usr/bin/env python3
"""Apply/revert only inside an explicitly acknowledged disposable runtime copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def apply(runtime_root, target, *, disposable=False, revert=False):
    if not disposable:
        raise ValueError("A disposable runtime copy must be explicitly acknowledged")
    root_input, target_input = Path(runtime_root).absolute(), Path(target).absolute()
    # Reject aliases at every component, rather than resolving an alias into the
    # purported permitted boundary and accepting the unrelated destination.
    for path in (root_input, target_input):
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError("Symlinked runtime roots or target paths are refused")
    root, target = root_input.resolve(), target_input.resolve()
    if not root.is_dir() or not target.is_file() or not target.is_relative_to(root):
        raise ValueError("Target must be a regular file inside the disposable copy")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    if tuple(target.parts[-4:]) != tuple(Path(manifest["relative_target"]).parts):
        raise ValueError("Target is not the pinned syncheck/xref.rkt collection path")
    original = (ROOT / "vendor/xref.rkt").read_bytes()
    patched = (ROOT / "overlay/xref.rkt").read_bytes()
    if sha(original) != manifest["original_sha256"] or sha(patched) != manifest["patched_sha256"]:
        raise ValueError("Experiment source hash mismatch")
    before = target.read_bytes()
    expected = manifest["patched_sha256"] if revert else manifest["original_sha256"]
    replacement = original if revert else patched
    if sha(before) == sha(replacement):
        return {"changed": False, "sha256": sha(before), "path": str(target)}
    if sha(before) != expected:
        raise ValueError("Installed target does not match the exact expected pin")
    if target.stat().st_nlink != 1:
        raise ValueError("Hard-linked target refused; deep copy the runtime first")
    mode = target.stat().st_mode & 0o777
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".xref-reply-", delete=False) as tmp:
            name = Path(tmp.name)
            tmp.write(replacement)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(name, mode)
        os.replace(name, target)
        name = None
    finally:
        if name is not None:
            name.unlink(missing_ok=True)
    if sha(target.read_bytes()) != sha(replacement):
        raise RuntimeError("Post-write verification failed")
    return {"changed": True, "sha256": sha(replacement), "path": str(target)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--confirm-disposable-copy", action="store_true")
    p.add_argument("--revert", action="store_true")
    a = p.parse_args()
    print(json.dumps(apply(a.runtime_root, a.target, disposable=a.confirm_disposable_copy,
                           revert=a.revert), indent=2))

if __name__ == "__main__":
    main()
