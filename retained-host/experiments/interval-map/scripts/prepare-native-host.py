#!/usr/bin/env python3
"""Generate the two-insertion docs postflight host and copy pinned dependencies.

Input is the frozen retained-host root; output stays in this experiment. The
original startup, Run, follow-on Check Syntax, paint, READY and capture code is
byte-for-byte retained. No native execution is claimed by this generator.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_PIN = "5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448"
DEPENDENCIES = {
    "independent-native-workflows.rkt": "b175a92754e8f0e8a0f524ae5947f5eae8da605b0f3274bbc098e20ce1de53bf",
    "independent-native-appearance-workflows.rkt": "c536f3f3b85aa9a5660ef7842d921c9708c9ee6c7cb82c463423e70ec265fda2",
    "independent-native-stop-returning.rkt": "7b2fd5bece5ab3f86d7dcaa0931e62d67366a667806c146eadffc7c4998bcb57",
}
TOOL_DEPENDENCIES = {
    "native-appearance.rkt": "f7a0bfc2cc4bc8b6356f7d79c3393b7b23a2dc3ef0cc1924b9a1e88a0c4c2c86",
    "native-appearance-platform.rkt": "0a2af8a0d8195feb76b18a5884bdb47ba813c37c12c31fb0986be1c0ada4ce2d",
    "native-appearance-cocoa.rkt": "7b5c9068efd32da6adefae2b6f57c640ba5d0a553b148679af37bd74128876b4",
    "native-appearance-gtk.rkt": "4eeecb46a48fb3de03da06820d46426ea537c3b0b14199d67c0a3c88931fd6a4",
}
INSERTIONS = (
    (b'(define-runtime-path returning-stop-module "independent-native-stop-returning.rkt")\n',
     b'(define-runtime-path interval-docs-module "interval-docs-postflight.rkt")\n', "after"),
    (b'  ;; A low-priority event turn allows actual paint work to follow the last update.\n',
     b'  ;; Read-only docs-map postflight after the unchanged genuine Check Syntax case.\n'
     b'  (on-gui (lambda ()\n'
     b"            ((dynamic-require interval-docs-module 'run-interval-docs-postflight!) frame)))\n\n", "before"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def derive(source):
    if sha(source) != HOST_PIN:
        raise ValueError("Frozen retained-host source pin mismatch")
    result = source
    for seam, addition, side in INSERTIONS:
        if source.count(seam) != 1 or result.count(seam) != 1:
            raise ValueError("Host insertion seam is not unique")
        result = result.replace(seam, seam + addition if side == "after" else addition + seam)
    restored = result
    for _, addition, _ in INSERTIONS:
        if restored.count(addition) != 1:
            raise ValueError("Host addition count mismatch")
        restored = restored.replace(addition, b"")
    if restored != source:
        raise ValueError("Host derivative altered existing bytes")
    return result


def prepare(base, destination=ROOT):
    source_path = base / "tests/independent-native-host.rkt"
    target = destination / "tests/independent-native-host.rkt"
    if source_path.resolve() == target.resolve():
        raise ValueError("Refusing to overwrite the frozen host")
    source = source_path.read_bytes()
    result = derive(source)
    dependencies = {name: (base / "tests" / name).read_bytes() for name in DEPENDENCIES}
    for name, data in dependencies.items():
        if sha(data) != DEPENDENCIES[name]:
            raise ValueError(f"Frozen dependency pin mismatch: {name}")
    tools = {name: (base / "tool" / name).read_bytes() for name in TOOL_DEPENDENCIES}
    for name, data in tools.items():
        if sha(data) != TOOL_DEPENDENCIES[name]:
            raise ValueError(f"Frozen dormant tool dependency pin mismatch: {name}")
    (destination / "tool").mkdir(parents=True, exist_ok=True)
    (destination / "tests").mkdir(parents=True, exist_ok=True)
    (destination / "reports").mkdir(parents=True, exist_ok=True)
    target.write_bytes(result)
    for name, data in dependencies.items():
        (destination / "tests" / name).write_bytes(data)
    for name, data in tools.items():
        (destination / "tool" / name).write_bytes(data)
    patch = "".join(difflib.unified_diff(
        source.decode().splitlines(True), result.decode().splitlines(True),
        fromfile="frozen/tests/independent-native-host.rkt",
        tofile="interval-map/tests/independent-native-host.rkt"))
    (destination / "reports/native-docs-host.patch").write_text(patch)
    report = {"base_host_sha256": HOST_PIN, "derived_host_sha256": sha(result),
              "insertions": 2, "existing_bytes_unchanged": True,
              "unchanged_local_dependencies": DEPENDENCIES,
              "unchanged_dormant_tool_dependencies": TOOL_DEPENDENCIES,
              "dormant_support_only": "copied test dependencies; stock UI and no appearance case required",
              "native_execution": "not run locally; Racket and GUI unavailable"}
    (destination / "reports/native-docs-host.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_retained_host", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.frozen_retained_host), indent=2))
