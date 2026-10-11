#!/usr/bin/env python3
"""Strict actual-handler gate; no sorting, eliding entries, or path rewriting.

Capture twice with stock, then candidate default-off and enabled in fresh native
processes. The native encoder only replaces path-valued descendants of its
verified runtime/fixture roots and real rename channel identities. Path bytes
below the roots and every trace entry are retained. A changing stock control
blocks this gate.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "openracket-actual-online-comp-trace/v1"
PINS = {
    "xref": "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7",
    "traversals": "bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00",
    "online-comp": "1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5",
}
FIXTURES = ["repeated-base", "unicode", "phase-one", "import-aliases", "undocumented-binding"]
QUERIES = ["openracket-fresh-name", "existing", "add1", "λ", "δ"]
DOC_METHOD = "syncheck:add-docs-menu"
ARROW_METHOD = "syncheck:add-arrow/name-dup/pxpy"
ID_SET_METHOD = "syncheck:add-id-set"


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def integer(value):
    """Decode the encoder's exact integer without conflating #f and zero."""
    require(isinstance(value, list) and len(value) == 2 and value[0] == "number",
            f"expected an encoded number, got {value!r}")
    require(isinstance(value[1], str), "number spelling must be a string")
    try:
        result = int(value[1])
    except ValueError as error:
        raise GateError(f"expected an exact integer: {value!r}") from error
    require(str(result) == value[1], f"noncanonical exact integer: {value!r}")
    return result


def method(entry):
    require(isinstance(entry, list) and len(entry) >= 2 and entry[0] == "vector",
            "each complete handler entry must be an encoded vector")
    require(isinstance(entry[1], list) and len(entry[1]) == 2 and entry[1][0] == "symbol",
            "handler method must be an encoded symbol")
    return entry[1][1]


def first_difference(left, right, location="fixtures"):
    if type(left) is not type(right):
        return f"{location}: type {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return f"{location}: field set differs"
        for key in left:
            found = first_difference(left[key], right[key], f"{location}.{key}")
            if found:
                return found
    elif isinstance(left, list):
        if len(left) != len(right):
            return f"{location}: length {len(left)} != {len(right)}"
        for index, (a, b) in enumerate(zip(left, right)):
            found = first_difference(a, b, f"{location}[{index}]")
            if found:
                return found
    elif left != right:
        return f"{location}: {left!r} != {right!r}"
    return None


def validate(capture, mode, manifest):
    require(isinstance(capture, dict), "capture must be an object")
    require(capture.get("schema") == SCHEMA and capture.get("completed") is True,
            f"{mode}: missing successful actual-handler completion")
    runtime = capture.get("runtime", {})
    require(runtime.get("mode") == mode, f"{mode}: wrong capture mode")
    require(runtime.get("version") == "9.3", f"{mode}: wrong Racket version")
    expected = {"stock": "unexported", "off": False, "on": True}[mode]
    require(type(runtime.get("activation")) is type(expected) and runtime.get("activation") == expected,
            f"{mode}: actual exported activation disagrees")
    require(runtime.get("flag") == ("1" if mode == "on" else None),
            f"{mode}: environment flag disagrees")
    require(isinstance(runtime.get("root"), str) and bool(runtime["root"])
            and isinstance(runtime.get("executable"), str) and bool(runtime["executable"]),
            f"{mode}: verified runtime root/executable evidence missing")
    require(type(runtime.get("fixture_timeout_seconds")) in (int, float)
            and 0 < runtime["fixture_timeout_seconds"] <= 120
            and type(runtime.get("suite_timeout_seconds")) is int
            and runtime.get("suite_timeout_seconds") == 180,
            f"{mode}: native operation timeout evidence missing")
    sources = runtime.get("sources", {})
    pins = {**PINS, "interval-map": manifest["original_sha256" if mode == "stock" else "patched_sha256"]}
    require(set(sources) == set(pins), f"{mode}: source evidence incomplete")
    for name, pin in pins.items():
        require(sources[name].get("sha256") == pin, f"{mode}: {name} source pin mismatch")
        require(isinstance(sources[name].get("path"), str) and bool(sources[name]["path"]),
                f"{mode}: {name} source path missing")
    fixtures = capture.get("fixtures")
    require(isinstance(fixtures, list) and [f.get("name") for f in fixtures] == FIXTURES,
            f"{mode}: fixture set/order differs")
    all_answers = []
    for fixture in fixtures:
        name = fixture["name"]
        source = fixture.get("source")
        require(isinstance(source, str) and source.startswith("#lang racket/base\n"),
                f"{mode}/{name}: original source missing")
        trace = fixture.get("trace")
        require(isinstance(trace, list) and bool(trace), f"{mode}/{name}: trace missing")
        docs = [entry for entry in trace if method(entry) == DOC_METHOD]
        require(bool(docs) and fixture.get("documentation_count") == len(docs),
                f"{mode}/{name}: nonempty documentation control failed")
        repeats = set()
        prefixed = set()
        for doc in docs:
            require(len(doc) == 9, f"{mode}/{name}: documentation signature changed")
            left, right = integer(doc[2]), integer(doc[3])
            require(0 <= left <= right <= len(source), f"{mode}/{name}: documentation positions invalid")
            require(isinstance(doc[4], list) and len(doc[4]) == 2 and doc[4][0] == "symbol",
                    f"{mode}/{name}: documentation key invalid")
            key = doc[4][1]
            require(isinstance(doc[5], str) and bool(doc[5]), f"{mode}/{name}: docs label missing")
            require(isinstance(doc[6], list) and len(doc[6]) == 3 and doc[6][0] == "path"
                    and doc[6][1] in ("unix", "windows") and isinstance(doc[6][2], list)
                    and ((len(doc[6][2]) == 3 and doc[6][2][:2] in (["root", "runtime"], ["root", "fixture"]))
                         or (len(doc[6][2]) == 2 and doc[6][2][0] == "literal"))
                    and isinstance(doc[6][2][-1], list) and bool(doc[6][2][-1])
                    and all(type(byte) is int and 0 <= byte <= 255 for byte in doc[6][2][-1]),
                    f"{mode}/{name}: full docs path missing")
            require(doc[7] is not False, f"{mode}/{name}: definition tag missing")
            if key == fixture.get("repeated_key"):
                require(source[left:right] == key, f"{mode}/{name}: Unicode/source positions differ")
                repeats.add(left)
            if key == "base:add1":
                prefixed.add(left)
            require(not fixture.get("no_docs_key") or key != fixture["no_docs_key"],
                    f"{mode}/{name}: undocumented local binding unexpectedly documented")
        minimum = fixture.get("repeated_minimum")
        require(type(minimum) is int and minimum >= 2 and len(repeats) >= minimum,
                f"{mode}/{name}: documented repeated references missing")
        if name == "import-aliases":
            require(len(prefixed) >= 2, f"{mode}/{name}: prefixed alias docs missing")
        expected_requests = []
        seen_channels = set()
        for index, entry in enumerate(trace):
            if method(entry) in (ARROW_METHOD, ID_SET_METHOD):
                require(len(entry) == (15 if method(entry) == ARROW_METHOD else 5),
                        f"{mode}/{name}: rename method signature changed")
                channel = entry[-2]
                require(isinstance(channel, list) and len(channel) == 2 and channel[0] == "rename-channel"
                        and type(channel[1]) is int and channel[1] >= 0,
                        f"{mode}/{name}: genuine normalized rename channel missing")
                seen_channels.add(channel[1])
                request_id = integer(entry[-1])
                require(request_id >= 0, f"{mode}/{name}: rename request ID invalid")
                for query in QUERIES:
                    expected_requests.append({"entry_index": index, "channel": channel[1],
                                              "request_id": request_id, "query": query})
        require(bool(expected_requests) and seen_channels == set(range(len(seen_channels))),
                f"{mode}/{name}: rename channels missing/noncanonical")
        answers = fixture.get("rename_answers")
        require(isinstance(answers, list) and len(answers) == len(expected_requests),
                f"{mode}/{name}: not every real rename endpoint was exercised")
        for expected_request, answer in zip(expected_requests, answers):
            require(set(answer) == {*expected_request, "answer"} and type(answer.get("answer")) is bool,
                    f"{mode}/{name}: actual boolean rename answer missing")
            require({key: answer[key] for key in expected_request} == expected_request,
                    f"{mode}/{name}: rename request correspondence differs")
            all_answers.append(answer["answer"])
    require(any(all_answers) and not all(all_answers), f"{mode}: both true and false rename answers required")
    return fixtures


def compare(stock, stock_again, off, on, manifest):
    baseline = validate(stock, "stock", manifest)
    baseline_again = validate(stock_again, "stock", manifest)
    timeout_fields = ("fixture_timeout_seconds", "suite_timeout_seconds")
    expected_timeouts = {key: stock["runtime"][key] for key in timeout_fields}
    repeated_timeouts = {key: stock_again["runtime"][key] for key in timeout_fields}
    require(first_difference(expected_timeouts, repeated_timeouts, "timeouts") is None,
            "Stock-to-stock timeout bounds differ; candidate comparison is blocked")
    difference = first_difference(baseline, baseline_again)
    if difference:
        raise GateError("Stock-to-stock control is unstable; candidate comparison is blocked. " + difference)
    for mode, capture in [("off", off), ("on", on)]:
        candidate = validate(capture, mode, manifest)
        candidate_timeouts = {key: capture["runtime"][key] for key in timeout_fields}
        require(first_difference(expected_timeouts, candidate_timeouts, "timeouts") is None,
                f"Stock versus {mode} timeout bounds differ")
        difference = first_difference(baseline, candidate)
        if difference:
            raise GateError(f"Stock versus {mode} differs: {difference}")
    return {"equal": True, "stock_control_stable": True, "fixtures": len(baseline),
            "ordered_trace_entries": sum(len(f["trace"]) for f in baseline),
            "documentation_annotations": sum(f["documentation_count"] for f in baseline),
            "rename_answers": sum(len(f["rename_answers"]) for f in baseline),
            "actual_enabled_activation": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stock", "stock_again", "off", "on"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        captures = [json.loads(getattr(args, name).read_text(encoding="utf-8"))
                    for name in ("stock", "stock_again", "off", "on")]
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        print(json.dumps(compare(*captures, manifest), indent=2))
    except (GateError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
