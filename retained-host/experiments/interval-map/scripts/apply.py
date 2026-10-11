#!/usr/bin/env python3
"""Apply/revert the sole source change inside an acknowledged independent runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def confined_file(path, root):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlinked runtime/source path refused; supply canonical clone paths")
    path = path.resolve()
    if not path.is_file() or not path.is_relative_to(root):
        raise ValueError("Source must be a regular file inside the independent runtime")
    if path.stat().st_nlink != 1:
        raise ValueError("Hard-linked source refused; deep copy the runtime first")
    return path


def apply(runtime_root, target, *, disposable=False, revert=False):
    if not disposable:
        raise ValueError("Explicit acknowledgement of an independent disposable runtime is required")
    root_input = Path(runtime_root).absolute()
    for part in (root_input, *root_input.parents):
        if part.is_symlink():
            raise ValueError("Symlinked runtime root refused; supply its canonical path")
    root = root_input.resolve()
    if not root.is_dir():
        raise ValueError("Independent runtime root must exist")
    target = confined_file(target, root)
    manifest = json.loads((ROOT / "manifest.json").read_text())
    suffix = Path(manifest["relative_target"]).parts
    if tuple(target.parts[-len(suffix):]) != suffix:
        raise ValueError("Target is not the pinned data/interval-map.rkt collection path")
    support = {}
    for relative, pin in manifest["unchanged_support_sha256_relative_to_data"].items():
        source = confined_file(target.parent / relative, root)
        digest = sha(source.read_bytes())
        if digest != pin:
            raise ValueError(f"Unchanged supporting source differs from its official pin: {relative}")
        support[relative] = {"path": str(source), "sha256": digest}
    original = (ROOT / "vendor/interval-map.rkt").read_bytes()
    patched = (ROOT / "overlay/interval-map.rkt").read_bytes()
    if sha(original) != manifest["original_sha256"] or sha(patched) != manifest["patched_sha256"]:
        raise ValueError("Experiment source hash mismatch")
    before = target.read_bytes()
    replacement = original if revert else patched
    expected = manifest["patched_sha256"] if revert else manifest["original_sha256"]
    if sha(before) == sha(replacement):
        return {"changed": False, "path": str(target), "sha256": sha(before), "support": support}
    if sha(before) != expected:
        raise ValueError("Target differs from the exact expected preimage")
    mode = target.stat().st_mode & 0o777
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".interval-map-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if sha(target.read_bytes()) != sha(replacement):
        raise RuntimeError("Post-write hash verification failed")
    return {"changed": True, "path": str(target), "sha256": sha(replacement), "support": support}


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
