#!/usr/bin/env python3
"""Explicitly authorized native execution ONLY. Does not prepare/patch runtimes.
Four fresh processes use separately prepared official 9.3 stock/candidate roots.
No downloads, package installation, source mutation, timing or publication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback
import compare

ROOT = Path(__file__).resolve().parents[1]

def canonical(path: Path, directory: bool):
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise ValueError("Paths must be absolute canonical non-symlink paths: " + str(path))
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("Missing explicit native path: " + str(path))
    return path

def native_paths(executable: Path, root: Path):
    canonical(root, True)
    canonical(executable, False)
    executable.relative_to(root)
    if not os.access(executable, os.X_OK):
        raise ValueError("Explicit native Racket executable is not executable")
    return executable, root

def environment(mode, profile):
    env = dict(os.environ)
    # Do not silently scrub another experimental overlay or alternate resolver.
    # These exclusions are independent of the source pin inside each process.
    banned = [k for k in env if k.startswith("OPENRACKET_") or k in {
        "PYTHONOPTIMIZE", "PLTCOLLECTS", "PLTCOMPILEDROOTS", "PLTCONFIGDIR", "PLTLINKS",
        "PLT_LINKS", "PLT_COMPILED_FILE_CHECK", "PLT_ZO_PATH", "PLTDRDEBUG", "PLTDRCM",
        "PLTDRPAR", "PLTUSERHOME", "PLTADDONDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"}]
    if banned:
        raise ValueError("Refusing contaminated inherited environment: " + ", ".join(sorted(banned)))
    env["PLTUSERHOME"] = str(profile)
    env["PLTADDONDIR"] = str(profile / "addon")
    if mode in ("off", "on"):
        env["OPENRACKET_NAMED_STYLE_INDEX"] = "1" if mode == "on" else "0"
    return env

def capture(executable, runtime_root, mode, output, *, timeout=180, run=subprocess.run):
    output.mkdir()
    profile = output / "profile"
    profile.mkdir()
    env = environment(mode, profile)
    expected = compare.STOCK_SHA if mode.startswith("stock") else compare.CANDIDATE_SHA
    command = [str(executable), str(ROOT / "native/bootstrap.rkt"), mode,
               str(runtime_root), expected, str(output)]
    result = {"command": command, "mode": mode, "returncode": None, "timed_out": False,
              "native_executed": False, "profile": str(profile), "timeout_seconds": timeout}
    # Files, not PIPE, retain complete stdout/stderr even on timeout or decoder
    # errors. Their bytes are never shortened into an excerpt.
    try:
        with (output / "stdout.bin").open("wb") as stdout, (output / "stderr.bin").open("wb") as stderr:
            try:
                process = run(command, env=env, stdin=subprocess.DEVNULL,
                              stdout=stdout, stderr=stderr, timeout=timeout, check=False)
                result["native_executed"] = True
                result["returncode"] = process.returncode
            except subprocess.TimeoutExpired:
                result["native_executed"] = True
                result["timed_out"] = True
            except BaseException:
                result["launch_failure"] = traceback.format_exc()
    finally:
        for name in ("stdout.bin", "stderr.bin", "capture.json", "fixture.wxme"):
            path = output / name
            if path.is_file():
                result[name] = {"bytes": path.stat().st_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        (output / "process.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arm in ("stock", "candidate"):
        p.add_argument("--" + arm + "-racket", type=Path, required=True)
        p.add_argument("--" + arm + "-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="new empty output directory")
    p.add_argument("--authorize-native-execution", action="store_true",
                   help="operational interlock; use only after actual user authorization")
    a = p.parse_args()
    if not a.authorize_native_execution:
        p.error("native execution has not been explicitly selected")
    stock, stock_root = native_paths(a.stock_racket, a.stock_root)
    candidate, candidate_root = native_paths(a.candidate_racket, a.candidate_root)
    if stock_root == candidate_root or stock_root in candidate_root.parents or candidate_root in stock_root.parents:
        p.error("stock/candidate roots must be separate prepared runtime trees")
    output = a.output.absolute()
    if output.exists():
        p.error("output must be a new directory; previous evidence is never overwritten")
    output.mkdir(parents=True)
    report = {"schema": "openracket-named-style-editor-run-v1", "passed": False,
              "native_executed": False, "runs": {}, "failures": []}
    captures = {}
    try:
        # Keep running independent arms after a failure so all available native
        # failure details are retained. Any missing/failing arm blocks acceptance.
        for mode in compare.MODES:
            exe, root = (stock, stock_root) if mode.startswith("stock") else (candidate, candidate_root)
            try:
                process = capture(exe, root, mode, output / mode)
                report["runs"][mode] = process
                report["native_executed"] |= process["native_executed"]
                if process["timed_out"] or process["returncode"] != 0:
                    raise ValueError(f"{mode} failed; see complete process.json/stdout.bin/stderr.bin/capture.json")
                file = output / mode / "capture.json"
                if not file.is_file() or file.stat().st_size > 4 * 1024 * 1024:
                    raise ValueError(f"{mode} missing or oversized native capture")
                captures[mode] = json.loads(file.read_text())
                compare.validate(captures[mode], mode)
            except BaseException:
                report["failures"].append({"mode": mode, "details": traceback.format_exc()})
        if not report["failures"]:
            report["comparison"] = compare.compare(captures)
            report["passed"] = True
    except BaseException:
        report["failures"].append({"mode": "comparison", "details": traceback.format_exc()})
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "native_executed": report["native_executed"],
                      "report": str(output / "report.json")}))
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
