#!/usr/bin/env python3
"""Produce a bounded host derivative without editing the frozen host.

Usage: python3 scripts/prepare-stock-tool-host.py [--base-host /path/to/base-host.rkt] [--check]
Default input is the byte-pinned vendored fixture; no sibling checkout is needed.
The legacy positional /path/to/frozen/base form is retained for explicit callers.
The integration owner copies the new modules plus generated host into a NEW
candidate. Never run this program against a frozen publication destination.
"""
import argparse
import hashlib
import difflib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_HOST = ROOT / "tests/reference/independent-native-host-0520.rkt"
BASE_HOST_SHA256 = "5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448"

def derive(source):
    expected = BASE_HOST_SHA256
    actual = hashlib.sha256(source.encode()).hexdigest()
    if actual != expected:
        raise ValueError(f"Unexpected frozen host bytes: {actual}; expected {expected}")
    additions = [
        ('(define-runtime-path returning-stop-module "independent-native-stop-returning.rkt")',
         '(define-runtime-path returning-stop-module "independent-native-stop-returning.rkt")\n'
         '(define-runtime-path stock-tool-module "independent-native-stock-tools.rkt")'),
        ('(unless (member follow-on-case \'("stop" "input-eof" "wxme" "check-syntax" "stop-returning"))',
         '(unless (member follow-on-case \'("stop" "input-eof" "wxme" "check-syntax" "stop-returning"\n'
         '                                             "debugger" "macro-stepper" "teaching-tests"))'),
        ('''          (if (equal? follow-on-case "stop-returning")
              ((dynamic-require returning-stop-module 'run-returning-stop-check!)
               frame on-gui wait-for)
              (on-gui
               (lambda ()
                 ((dynamic-require follow-on-module 'run-follow-on-check!)
                  frame (string->symbol follow-on-case)))))))''',
         '''          (cond
            [(member follow-on-case '("debugger" "macro-stepper" "teaching-tests"))
             ;; Return each action to the GUI event loop before coordinator polling.
             ((dynamic-require stock-tool-module 'run-native-tool-check!)
              frame (string->symbol follow-on-case) on-gui wait-for
              (lambda (created)
                (unless (memq created created-frames)
                  (set! created-frames (cons created created-frames)))))]
            [(equal? follow-on-case "stop-returning")
             ((dynamic-require returning-stop-module 'run-returning-stop-check!)
              frame on-gui wait-for)]
            [else
             (on-gui
              (lambda ()
                ((dynamic-require follow-on-module 'run-follow-on-check!)
                 frame (string->symbol follow-on-case))))])))'''),
    ]
    result = source
    for old, new in additions:
        if result.count(old) != 1:
            raise ValueError(f"Expected exactly one substitution anchor: {old[:100]!r}")
        result = result.replace(old, new)
    return result

def read_base_host(path=None):
    path = DEFAULT_BASE_HOST if path is None else Path(path)
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != BASE_HOST_SHA256:
        raise ValueError(f"Unexpected frozen host bytes at {path}: {actual}; expected {BASE_HOST_SHA256}")
    return raw.decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_root", nargs="?", type=Path,
                        help="Legacy explicit frozen-base directory")
    parser.add_argument("--base-host", type=Path,
                        help="Explicit byte-pinned input file (default: vendored fixture)")
    parser.add_argument("--check", action="store_true",
                        help="Verify the existing generated host, patch and metadata without writing")
    args = parser.parse_args()
    if args.base_root is not None and args.base_host is not None:
        parser.error("Choose either --base-host or the legacy base directory")
    source_path = (args.base_host if args.base_host is not None else
                   args.base_root / "tests/independent-native-host.rkt" if args.base_root is not None else
                   DEFAULT_BASE_HOST)
    source = read_base_host(source_path)
    result = derive(source)
    target = ROOT / "tests" / "independent-native-host.rkt"
    if target.resolve() == source_path.resolve():
        raise ValueError("Refusing to overwrite the frozen input")
    patch = ''.join(difflib.unified_diff(
        source.splitlines(True), result.splitlines(True),
        fromfile="a/tests/independent-native-host.rkt", tofile="b/tests/independent-native-host.rkt"))
    metadata = json.dumps({
        "base_host_sha256": BASE_HOST_SHA256,
        "candidate_host_sha256": hashlib.sha256(result.encode()).hexdigest(),
        "cases": ["debugger", "macro-stepper", "teaching-tests"],
        "native_execution": "pending",
        "base_modified": False,
        "change_scope": "three surgical host substitutions; existing acceptance/READY/capture retained",
    }, indent=2) + '\n'
    outputs = {target: result,
               ROOT / "reports/stock-tool-host.patch": patch,
               ROOT / "reports/stock-tool-host.json": metadata}
    for path, contents in outputs.items():
        if args.check:
            if path.read_bytes() != contents.encode("utf-8"):
                raise ValueError(f"Generated file differs from its pinned derivation: {path}")
        else:
            path.write_bytes(contents.encode("utf-8"))
    print("Pinned host, patch and metadata verified" if args.check else
          "Pinned host, patch and metadata generated")

if __name__ == '__main__':
    main()
