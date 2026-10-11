#!/usr/bin/env python3
"""Fail-closed comparison of two actual retained-editor documentation maps.

Only the arm/activation/data-source hash and verified clone-root prefix may
vary. Every ordered interval, complete typed stored value, source path suffix,
source hash, identity assertion and fixture field is otherwise compared exactly.
No sorting, bagging, deduplication, inferred data, or textual path rewriting.
"""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import re
import sys

SCHEMA = "openracket-actual-gui-docs-map/v1"
SOURCE = "#lang racket/base\n(define (bump x) (+ x 1))\n(bump 41)\n"
ORIGINAL = "1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de"
CANDIDATE = "1f1636316c3ba3f307fcb33f44d68c00ee9804b775fac7d78916db01d87fec4d"
HOST = "ad0ba1ec80fb8dbcec86f54e1a0088d6a938c62c052d6bcaf7cb12e251134fb8"
WORKFLOW = "b175a92754e8f0e8a0f524ae5947f5eae8da605b0f3274bbc098e20ce1de53bf"
PINS = {
    "blueboxes-gui": "c81a8df93f0012b0ab564009bb4a9ad34d9ce1cde3795e180bfbe33a1008e721",
    "gui": "5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e",
    "xref": "acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7",
    "traversals": "bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00",
    "online-comp": "1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5",
}
PLUS_TAG = ["list", ["symbol", "def"],
            ["list", ["list", ["symbol", "quote"], ["symbol", "#%kernel"]], ["symbol", "+"]]]
PLUS_ANCHOR = ["string", "(def._((quote._~23~25kernel)._+))"]
EDITOR_FLAGS = {
    "source_unchanged", "filename_unchanged", "modified_state_unchanged",
    "definitions_identity_unchanged", "canvas_identity_unchanged",
    "canvas_editor_identity_unchanged", "tab_identity_unchanged",
    "docs_map_identity_unchanged", "intervals_unchanged",
}


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def fields(value, expected, where):
    require(type(value) is dict and set(value) == set(expected), f"{where}: exact field set required")


def integer(value, where):
    require(type(value) is int, f"{where}: exact JSON integer required")
    return value


def byte_string(value, where, nonempty=True):
    require(type(value) is list and (value or not nonempty)
            and all(type(b) is int and 0 <= b <= 255 for b in value), f"{where}: byte array required")
    return bytes(value)


def path_suffix(value, where):
    require(type(value) is list and len(value) == 3 and value[:2] == ["path", "unix"],
            f"{where}: exact native path datum required")
    payload = value[2]
    require(type(payload) is list and len(payload) == 3 and payload[:2] == ["root", "runtime"],
            f"{where}: only a verified runtime-root path is permitted")
    suffix = byte_string(payload[2], where)
    require(not suffix.startswith(b"/") and b"\x00" not in suffix
            and all(part not in (b"", b".", b"..") for part in suffix.split(b"/")),
            f"{where}: noncanonical or escaping path suffix")
    return suffix


def datum(value, where, depth=0, budget=None):
    if budget is None:
        budget = [10000]
    budget[0] -= 1
    require(depth < 64 and budget[0] > 0, f"{where}: datum bound exceeded")
    require(type(value) is list and bool(value) and type(value[0]) is str, f"{where}: typed datum required")
    tag = value[0]
    if tag == "path":
        path_suffix(value, where)
    elif tag in ("string", "symbol"):
        require(len(value) == 2 and type(value[1]) is str, f"{where}: malformed {tag}")
    elif tag == "integer":
        require(len(value) == 2 and type(value[1]) is str
                and re.fullmatch(r"0|-?[1-9][0-9]*", value[1]) is not None,
                f"{where}: noncanonical integer datum")
    elif tag == "boolean":
        require(len(value) == 2 and type(value[1]) is bool, f"{where}: malformed boolean datum")
    elif tag == "bytes":
        require(len(value) == 2, f"{where}: malformed bytes datum")
        byte_string(value[1], where, nonempty=False)
    elif tag in ("list", "vector", "pair"):
        require(tag != "pair" or len(value) == 3, f"{where}: malformed pair datum")
        for index, child in enumerate(value[1:]):
            datum(child, f"{where}[{index}]", depth + 1, budget)
    else:
        raise GateError(f"{where}: unsupported datum tag {tag!r}")


def number_datum(value, where):
    datum(value, where)
    require(value[0] == "integer", f"{where}: exact integer datum required")
    return int(value[1])


def validate(capture, mode):
    fields(capture, {"schema", "completed", "runtime", "host", "editor", "interval_count", "intervals", "plus"}, mode)
    require(capture["schema"] == SCHEMA and capture["completed"] is True, f"{mode}: completed native capture required")
    runtime = capture["runtime"]
    fields(runtime, {"mode", "version", "flag", "activation", "root", "root_bytes", "executable", "sources"}, "runtime")
    require(mode in ("stock", "candidate-on") and runtime["mode"] == mode, f"{mode}: wrong arm")
    require(runtime["version"] == "9.3", f"{mode}: wrong Racket version")
    expected_activation = "unexported" if mode == "stock" else True
    require(type(runtime["activation"]) is type(expected_activation) and runtime["activation"] == expected_activation,
            f"{mode}: wrong actual export activation")
    require(runtime["flag"] == (None if mode == "stock" else "1"), f"{mode}: wrong flag")
    root = runtime["root"]
    require(type(root) is str and root.startswith("/") and not root.startswith("//") and root != "/"
            and str(PurePosixPath(root)) == root and ".." not in PurePosixPath(root).parts
            and "\x00" not in root, f"{mode}: canonical explicit clone root required")
    require(byte_string(runtime["root_bytes"], "root_bytes") == root.encode("utf-8"),
            f"{mode}: original clone-root bytes disagree")
    executable = path_suffix(runtime["executable"], "runtime.executable")
    require(executable.split(b"/")[-1] in (b"racket", b"Racket"), f"{mode}: actual Racket executable required")
    sources = runtime["sources"]
    pins = {**PINS, "interval-map": ORIGINAL if mode == "stock" else CANDIDATE}
    fields(sources, pins, "sources")
    for name, pin in pins.items():
        fields(sources[name], {"path", "sha256"}, f"sources.{name}")
        require(sources[name]["sha256"] == pin, f"{mode}: {name} source pin mismatch")
        suffix = path_suffix(sources[name]["path"], f"sources.{name}.path")
        expected_suffix = ("data/interval-map.rkt" if name == "interval-map"
                           else f"drracket/private/syncheck/{name}.rkt").encode()
        require(suffix == expected_suffix or suffix.endswith(b"/" + expected_suffix),
                f"{mode}: {name} resolved source path mismatch")
    host = capture["host"]
    fields(host, {"sha256", "workflow_sha256", "case", "ui", "fatal_check_handler",
                  "handler_thread_verified", "getter", "source_pins_unchanged"}, "host")
    require(host["sha256"] == HOST and host["workflow_sha256"] == WORKFLOW,
            f"{mode}: unchanged real-host workflow pins required")
    require(host["case"] == "check-syntax" and host["ui"] == "stock", f"{mode}: actual stock Check Syntax required")
    require(host["getter"] == "existing-module-namespace/lexical-get-docs-im", f"{mode}: wrong accessor")
    for key in ("fatal_check_handler", "handler_thread_verified", "source_pins_unchanged"):
        require(host[key] is True, f"{mode}: {key} proof missing")
    editor = capture["editor"]
    fields(editor, {"source", "characters", "selection", *EDITOR_FLAGS}, "editor")
    require(editor["source"] == SOURCE and integer(editor["characters"], "characters") == 54,
            f"{mode}: exact original 54-character source required")
    require(type(editor["selection"]) is list and len(editor["selection"]) == 2
            and all(type(v) is int for v in editor["selection"]) and editor["selection"] == [1, 6],
            f"{mode}: real workflow selection changed")
    for key in EDITOR_FLAGS:
        require(editor[key] is True, f"{mode}: {key} proof missing")
    intervals = capture["intervals"]
    require(type(intervals) is list and 0 < len(intervals) <= 256
            and integer(capture["interval_count"], "interval_count") == len(intervals), f"{mode}: nonempty complete interval list required")
    previous_end = -1
    for index, interval in enumerate(intervals):
        where = f"{mode}.intervals[{index}]"
        fields(interval, {"start", "end", "stored"}, where)
        start, end = integer(interval["start"], where), integer(interval["end"], where)
        require(0 <= start < end <= 55 and previous_end <= start, f"{where}: nonoverlapping ordered geometry required")
        previous_end = end
        value = interval["stored"]
        datum(value, where)
        require(len(value) == 6 and value[0] == "list", f"{where}: full five-field docs-range value required")
        stored_start, stored_end = number_datum(value[1], where), number_datum(value[2], where)
        require(0 <= stored_start <= start and end <= stored_end <= 55 and stored_start <= stored_end - 1,
                f"{where}: stored start/end+1 geometry differs")
        require(value[3][0] == "list" and len(value[3]) >= 2
                and value[3][1][0] == "symbol" and value[3][1][1] in ("def", "form"),
                f"{where}: full definition tag missing")
        path_suffix(value[4], where)
        require(value[5][0] == "string" or value[5] == ["boolean", False], f"{where}: invalid URL anchor type")
    plus = capture["plus"]
    fields(plus, {"position", "source_end", "stored_end", "interval_index", "definition_tag", "path", "url_anchor", "query_bounds", "at_37", "at_38"}, "plus")
    require([integer(plus[k], f"plus.{k}") for k in ("position", "source_end", "stored_end")] == [36, 37, 38],
            f"{mode}: + position/end/end+1 changed")
    index = integer(plus["interval_index"], "plus.interval_index")
    require(0 <= index < len(intervals), f"{mode}: + interval index missing")
    require(plus["definition_tag"] == PLUS_TAG and plus["url_anchor"] == PLUS_ANCHOR,
            f"{mode}: exact + definition tag/URL anchor changed")
    suffix = path_suffix(plus["path"], "plus.path")
    require(suffix.endswith(b"/reference/generic-numbers.html"), f"{mode}: exact + reference path changed")
    expected = {"start": 36, "end": 38,
                "stored": ["list", ["integer", "36"], ["integer", "38"], PLUS_TAG, plus["path"], PLUS_ANCHOR]}
    require(intervals[index] == expected, f"{mode}: actual + map value differs from positive control")
    require(type(plus["query_bounds"]) is list and len(plus["query_bounds"]) == 2
            and all(type(v) is int for v in plus["query_bounds"]) and plus["query_bounds"] == [36, 38],
            f"{mode}: actual + query bounds differ")
    datum(plus["at_37"], "plus.at_37")
    datum(plus["at_38"], "plus.at_38")
    require(plus["at_37"] == expected["stored"], f"{mode}: point 37 must return actual + value")
    expected_at_38 = next((entry["stored"] for entry in intervals if entry["start"] <= 38 < entry["end"]),
                          ["boolean", False])
    require(plus["at_38"] == expected_at_38 and plus["at_38"] != expected["stored"],
            f"{mode}: point 38 must agree with full map and exclude + value")
    return capture


def first_difference(left, right, where="capture"):
    if type(left) is not type(right):
        return f"{where}: type differs"
    if type(left) is dict:
        if left.keys() != right.keys():
            return f"{where}: fields differ"
        for key in left:
            found = first_difference(left[key], right[key], f"{where}.{key}")
            if found:
                return found
    elif type(left) is list:
        if len(left) != len(right):
            return f"{where}: list length differs"
        for index, (a, b) in enumerate(zip(left, right)):
            found = first_difference(a, b, f"{where}[{index}]")
            if found:
                return found
    elif left != right:
        return f"{where}: value differs"
    return None


def comparable(capture):
    result = copy.deepcopy(capture)
    runtime = result["runtime"]
    for allowed in ("mode", "flag", "activation", "root", "root_bytes"):
        del runtime[allowed]
    del runtime["sources"]["interval-map"]["sha256"]
    return result


def compare(stock, candidate):
    validate(stock, "stock")
    validate(candidate, "candidate-on")
    require(stock["runtime"]["root"] != candidate["runtime"]["root"], "distinct disposable stock/candidate clone roots required")
    difference = first_difference(comparable(stock), comparable(candidate))
    require(difference is None, f"stock versus candidate-on differs: {difference}")
    return {"equal": True, "actual_retained_editor": True,
            "ordered_documentation_intervals": stock["interval_count"],
            "exact_plus_documentation": True, "actual_enabled_activation": True}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_capture(path):
    def bad_constant(value):
        raise GateError(f"non-JSON numeric constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=bad_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("candidate_on", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(compare(load_capture(args.stock), load_capture(args.candidate_on)), indent=2))
    except (GateError, KeyError, IndexError, TypeError, UnicodeError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
