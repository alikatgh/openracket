#!/usr/bin/env python3
"""Read pinned cached archives; prepare review-only seams. Never run or patch a host."""
import argparse
import difflib
import hashlib
import json
import zipfile
from pathlib import Path
from prepare import READY as READY_INSERT, transform_worker

PINNED = {
    "drracket-core-lib": "d55515fcc1d1da846555ea0b5c1b593c4af619ef",
    "drracket-plugin-lib": "536a7093639c0eabc33bfb77be13a9b2a0d2ad0f",
}
FIXTURE_SHA256 = "766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e"
READY_MARKER = "  (let loop ([current-job #f]\n"


def sources(host):
    manifest = json.loads((host / "reports/cached-packages.json").read_text())
    result, evidence = {}, {}
    for package, expected in PINNED.items():
        row = next(r for r in manifest if r["url"].endswith(f"/{package}.zip"))
        archive = host / row["file"]
        actual = hashlib.sha1(archive.read_bytes()).hexdigest()
        if actual != expected or row["checksum"] != expected:
            raise ValueError(f"Pinned archive mismatch: {package}")
        with zipfile.ZipFile(archive) as z:
            result[package] = {n: z.read(n).decode("utf-8") for n in z.namelist()
                               if n.endswith(".rkt")}
        evidence[package] = {"url": row["url"], "sha1": actual, "verified": True}
    return result, evidence


def ready_copy(worker):
    if worker.count(READY_MARKER) != 1:
        raise ValueError("Readiness insertion anchor is not unique")
    return transform_worker(worker)


def diff(before, after, filename):
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile="stock/" + filename,
                                        tofile="diagnostic-only/" + filename))


def build_report(host):
    packages, archives = sources(host)
    core = packages["drracket-core-lib"]
    worker = core["drracket/private/expanding-place.rkt"]
    language = core["drracket/private/module-language.rkt"]
    tool_lib = core["drracket/tool-lib.rkt"]
    sig = packages["drracket-plugin-lib"]["drracket/private/drsig.rkt"]
    namespace = {"__name__": "fixture_contract_inspection"}
    generator = host / "performance/fixtures.py"
    exec(compile(generator.read_text(), str(generator), "exec"), namespace)
    snapshot, edit_position = namespace["generate"](1_048_576)
    actual_fixture_hash = hashlib.sha256(snapshot).hexdigest()
    if actual_fixture_hash != FIXTURE_SHA256:
        raise ValueError("The deterministic fixture no longer matches the pinned baseline")
    selected = {
        "worker_exported_start": "(provide start)" in worker,
        "registry_public_export_absent": "get-online-expansion-handlers" not in tool_lib,
        "registry_internal_signature_present": "get-online-expansion-handlers" in sig,
        "stock_online_annotations_none": "online expansion which we never instrument\n                               'none" in language,
        "child_limit_default_128_mib": "(* 1024 1024 128)" in core["drracket/private/eval-helpers-and-pref-init.rkt"],
        "readiness_copy_removes_back_to_exact_stock": ready_copy(worker).replace(READY_INSERT, "", 1) == worker,
        "request_has_six_exact_fields": "                                   currently-open-files))\n               (place-channel-put expanding-place to-send)" in language,
        "snapshot_keeps_string_or_wxme": "(save-port bp 'standard)" in language and "(values str fn)" in language,
    }
    if not all(selected.values()):
        raise ValueError(f"Source contract changed: {selected}")
    return {
        "schema_version": 1,
        "status": "source_contract_verified_native_run_pending",
        "native_or_expansion_execution": False,
        "performance_measurements": None,
        "archives": archives,
        "source_checks": selected,
        "worker_sha256": hashlib.sha256(worker.encode()).hexdigest(),
        "module_language_sha256": hashlib.sha256(language.encode()).hexdigest(),
        "fixture": {"bytes": len(snapshot), "characters": len(snapshot.decode("ascii")),
                    "sha256": actual_fixture_hash, "edit_position": edit_position,
                    "source_identity": "Must be captured from actual request; not substituted with this local path"},
        "native_gates_pending": [
            "Run capture.py on an authorized native CI clone to obtain the real edited snapshot/registry.",
            "Use the guarded initialization-instrumented worker copy; never claim byte-identical stock.",
            "Run supervise.py in the captured environment and inspect actual outcomes, parity and cleanup.",
        ],
        "scope": "Isolated expansion workload and support threads; not causal allocator attribution of concurrent GUI run",
    }, worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, default=Path("/workspace/shared/openracket-drracket-host"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    output = args.output.resolve()
    owned = Path(__file__).resolve().parent
    if output != owned and owned not in output.parents:
        parser.error("Outputs must stay inside this diagnostic directory")
    report, worker = build_report(args.host)
    output.mkdir(parents=True, exist_ok=True)
    (output / "observed-contract.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "readiness-proposal.diff").write_text(diff(worker, ready_copy(worker), "drracket/private/expanding-place.rkt"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
