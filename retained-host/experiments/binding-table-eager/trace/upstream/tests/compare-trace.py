#!/usr/bin/env python3
"""Bounded completed-annotation contract; raw order remains an explicit diagnostic.

This does not establish transient GUI replay/paint-order or timing equivalence.
See TRACE-SEMANTICS.md for the exact consumer-source-backed acceptance boundary.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("strict_trace", HERE / "compare-trace-exact.py")
strict = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strict)
GateError = strict.GateError
require = strict.require
integer = strict.integer
method = strict.method

ARROW = strict.ARROW_METHOD
DOCS = strict.DOC_METHOD
TEXT = "syncheck:add-text-type"
REQUIRE = "syncheck:add-require-open-menu"
TARGET = "syncheck:add-definition-target/phase-level+space"
JUMP = "syncheck:add-jump-to-definition/phase-level+space"
HOVER = "syncheck:add-mouse-over-status"
TAIL = "syncheck:add-tail-arrow"
PREFIX = "syncheck:add-prefixed-require-reference"
SIZES = {ARROW: 15, DOCS: 9, TEXT: 5, REQUIRE: 5, TARGET: 7,
         JUMP: 8, HOVER: 5, TAIL: 4, PREFIX: 7}


def key(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def tagged(value, tag, size=None):
    return (isinstance(value, list) and bool(value) and value[0] == tag
            and (size is None or len(value) == size))


def path(value):
    require(tagged(value, "path", 3) and value[1] in ("unix", "windows"),
            "unsupported encoded path")
    body = value[2]
    require(isinstance(body, list)
            and ((len(body) == 3 and body[:2] in (["root", "runtime"], ["root", "fixture"]))
                 or (len(body) == 2 and body[0] == "literal"))
            and isinstance(body[-1], list)
            and all(type(b) is int and 0 <= b <= 255 for b in body[-1]),
            "unsupported path normalization")


def symbols(value):
    require(tagged(value, "list") and all(tagged(x, "symbol", 2) for x in value[1:]),
            "unsupported submodule sequence")


def complete_events(fixture):
    """Alpha-rename local handles by attaching their own actual tested responses.

    The stock producer creates exactly one channel and a fresh consecutive ID
    for every arrow (online-comp 83-100). Enforce that bijection before dropping
    transport names from semantic records. No event or duplicate is discarded.
    """
    answers = defaultdict(list)
    for answer in fixture["rename_answers"]:
        answers[answer["entry_index"]].append([answer["query"], answer["answer"]])
    events = []
    expected_id = 0
    for index, entry in enumerate(fixture["trace"]):
        name = method(entry)
        require(name in SIZES, f"unsupported annotation method: {name}")
        require(len(entry) == SIZES[name], f"unsupported signature: {name}")
        if name == ARROW:
            require(entry[-2] == ["rename-channel", 0] and integer(entry[-1]) == expected_id,
                    "rename table is not one genuine channel with consecutive unique IDs")
            require([a[0] for a in answers[index]] == strict.QUERIES,
                    "rename answers are not attached to their exact original entry")
            events.append(entry[:-2] + [["tested-rename-answers", answers[index]]])
            expected_id += 1
        else:
            events.append(entry)
    require(expected_id > 0, "no observed arrow endpoint table")
    return events


def project(fixture):
    """Project only the nine observed methods; reject expansion of this model."""
    source = fixture["source"]
    length = len(source)
    require(0 < length <= 10000, "fixture exceeds bounded per-character review")
    events = complete_events(fixture)
    require(len(events) <= 10000, "fixture exceeds bounded event review")
    lanes = {name: [[] for _ in range(length)] for name in ("menus", "def_links", "colors", "tooltips", "arrows")}
    menu_keys = [set() for _ in range(length)]
    docs_map = [None for _ in range(length + 1)]
    docs_order = [[] for _ in range(length + 1)]
    target_order = defaultdict(list)
    targets = {}
    require_order = []
    prefix_order = defaultdict(list)
    endpoint_occurrences = defaultdict(list)
    retained_edges = {}
    require_groups = {}

    def span(left, right):
        left, right = integer(left), integer(right)
        require(0 <= left <= right <= length, "out-of-source range; refusing implicit repair")
        return left, right

    def effective(left, right):
        # gui.rkt 1113-1128. Inputs are already verified in bounds and ordered.
        if left == right:
            if right == length:
                left -= 1
            else:
                right += 1
        return range(left, right)

    def add(lane, left, right, event, menu_key=None):
        for position in effective(left, right):
            if menu_key is not None:
                if menu_key in menu_keys[position]:
                    continue
                menu_keys[position].add(menu_key)
            lanes[lane][position].insert(0, event)

    for index, event in enumerate(events):
        name = method(event)
        if name == ARROW:
            left, right = span(event[2], event[3])
            end_left, end_right = span(event[6], event[7])
            require(all(tagged(event[i], "number", 2) for i in (4, 5, 8, 9)),
                    "unsupported arrow geometry")
            require(type(event[10]) is bool and tagged(event[11], "number", 2),
                    "unsupported arrow actual/phase form")
            integer(event[11])
            require(event[12] is False or event[12] is True or event[12] == ["symbol", "module-lang"],
                    "unsupported require-arrow marker")
            geometry = key([left, right, end_left, end_right])
            endpoint_occurrences[geometry].append(event)
            if (left, right) == (end_left, end_right) or geometry in retained_edges:
                continue
            retained_edges[geometry] = event
            if event[12] is not False:
                # Require arrows alone may permute within their shared binder.
                # Homogeneous source geometry, phase/type and tested predicate
                # answers are mandatory; destinations remain in full inventory.
                group_key = key([left, right])
                signature = event[4:6] + event[10:13] + [event[-1]]
                require(group_key not in require_groups or require_groups[group_key] == signature,
                        "heterogeneous require-source group; order must remain strict")
                require_groups[group_key] = signature
            add("arrows", left, right, event)
            add("arrows", end_left, end_right, event)
        elif name == TAIL:
            left, end = integer(event[2]), integer(event[3])
            require(0 <= left < length and 0 <= end < length, "unsupported tail endpoint")
            add("arrows", left, left + 1, event)
            add("arrows", end, end + 1, event)
        elif name == DOCS:
            left, right = span(event[2], event[3])
            require(index > 0 and events[index - 1] == ["vector", ["symbol", TEXT], event[2], event[3], ["symbol", "document-identifier"]],
                    "documentation is not paired with its actual preceding text-type event")
            path(event[6])
            for position in range(left, right + 1):
                # blueboxes-gui 673-677: exact last-write state includes end+1.
                docs_map[position] = [left, right + 1, event[7], event[6], event[8]]
                docs_order[position].append(event)
            add("menus", left, right, event, key(event[4]))
        elif name == TEXT:
            left, right = span(event[2], event[3])
            require(event[4] == ["symbol", "document-identifier"], "unobserved text-type needs consumer review")
            require(index + 1 < len(events) and method(events[index + 1]) == DOCS
                    and events[index + 1][2:4] == event[2:4],
                    "text-type/docs adjacency changed")
            add("colors", left, right, event)
        elif name == REQUIRE:
            left, right = span(event[2], event[3])
            path(event[4])
            require_order.append(event)
            add("menus", left, right, event, key(event[4]))
        elif name == JUMP:
            left, right = span(event[2], event[3])
            require(tagged(event[4], "symbol", 2), "unsupported definition ID")
            path(event[5])
            symbols(event[6])
            integer(event[7])
            add("def_links", left, right, event)
        elif name == HOVER:
            left, right = span(event[2], event[3])
            require(isinstance(event[4], str), "unsupported tooltip payload")
            add("tooltips", left, right, event)
        elif name == TARGET:
            left, right = span(event[2], event[3])
            require(tagged(event[4], "symbol", 2), "unsupported definition target")
            symbols(event[5])
            integer(event[6])
            target_key = key(event[4:6])
            target_order[target_key].append(event)
            targets[target_key] = [left, right]
        elif name == PREFIX:
            span(event[2], event[3])
            span(event[5], event[6])
            require(tagged(event[4], "symbol", 2), "unsupported prefix payload")
            prefix_order[key(event[2:4])].append(event)

    # These local sequences preserve source choice, local-binding order, and
    # tail/variable interleaving. Only homogeneous require arrows with exactly
    # the same binder get the same token, allowing their destination permutation.
    selection_order = []
    first_binding = []
    paint_order = lanes.pop("arrows")
    for arrows in paint_order:
        sequence = []
        for event in arrows:
            if method(event) == ARROW and event[12] is not False:
                sequence.append(["same-require-source", event[2:6], event[10:13], event[-1]])
            else:
                sequence.append(event)
        selection_order.append(sequence)
        variables = [event for event in arrows if method(event) == ARROW]
        first_binding.append(variables[0][2:4] if variables else None)

    # Unordered maps here represent lookup domains, not trace reordering. Every
    # full event occurrence survives the Counter; order-sensitive sequences and
    # first/last-wins consumer state are separately required to agree exactly.
    contract = {"source": source,
                "event_inventory": dict(Counter(key(event) for event in events)),
                "docs_overwrite_map": docs_map, "docs_overlap_order": docs_order,
                "require_order": require_order, "definition_targets": targets,
                "definition_target_order": dict(target_order), "prefix_order": dict(prefix_order),
                "endpoint_occurrences": dict(endpoint_occurrences), "retained_binding_graph": retained_edges,
                "require_group_signatures": require_groups, "source_selection_order": selection_order,
                "first_binding_destination": first_binding, **lanes}
    return contract, paint_order


def difference(left, right, label):
    return strict.first_difference(left, right, label)


def compare(stock, stock_again, off, on, manifest):
    captures = [("stock", stock), ("stock-again", stock_again), ("off", off), ("on", on)]
    expected_timeout = None
    projections = {}
    paints = {}
    for label, capture in captures:
        strict.validate(capture, "stock" if label.startswith("stock") else label, manifest)
        timeout = {k: capture["runtime"][k] for k in ("fixture_timeout_seconds", "suite_timeout_seconds")}
        if expected_timeout is None:
            expected_timeout = timeout
        require(difference(expected_timeout, timeout, "timeouts") is None, "capture timeout bounds differ")
        projections[label], paints[label] = [], []
        for fixture in capture["fixtures"]:
            contract, paint = project(fixture)
            projections[label].append(contract)
            paints[label].append(paint)
    diagnostics = []
    for label, capture in captures[1:]:
        raw_difference = difference(stock["fixtures"], capture["fixtures"], "fixtures")
        changed = []
        for index, fixture in enumerate(stock["fixtures"]):
            positions = [position for position, (a, b) in enumerate(zip(paints["stock"][index], paints[label][index])) if a != b]
            if positions:
                changed.append({"fixture": fixture["name"], "character_positions": positions})
        diagnostics.append({"left": "stock", "right": label, "exact_raw_order_equal": raw_difference is None,
                            "first_raw_difference": raw_difference,
                            "require_arrow_paint_order_variation": changed})
        found = difference(projections["stock"], projections[label], "annotation_contract")
        if found:
            if label == "stock-again":
                raise GateError("Stock annotation semantics are unstable; candidate interpretation blocked. " + found)
            raise GateError(f"Stock versus {label} annotation semantics differ: {found}")
    fixtures = stock["fixtures"]
    return {"targeted_annotation_semantics_equal": True,
            "stock_annotation_semantics_stable": True,
            "exact_raw_order_equal": all(row["exact_raw_order_equal"] for row in diagnostics),
            "raw_order_diagnostics": diagnostics,
            "fixtures": len(fixtures), "trace_entries_per_capture": sum(len(f["trace"]) for f in fixtures),
            "documentation_annotations_per_capture": sum(f["documentation_count"] for f in fixtures),
            "tested_rename_answers_per_capture": sum(len(f["rename_answers"]) for f in fixtures),
            "actual_enabled_activation": True,
            "claim": "Completed annotation, binding/navigation and five-query rename contract only; transient GUI replay/paint ordering and timing remain unproven."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stock", "stock_again", "off", "on"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--manifest", type=Path, default=(HERE.parent / "manifest.json"))
    args = parser.parse_args()
    try:
        paths = [getattr(args, name) for name in ("stock", "stock_again", "off", "on")]
        raw = [path.read_bytes() for path in paths]
        captures = [json.loads(data) for data in raw]
        result = compare(*captures, json.loads(args.manifest.read_text(encoding="utf-8")))
        result["input_sha256"] = {str(path): hashlib.sha256(data).hexdigest() for path, data in zip(paths, raw)}
        print(json.dumps(result, indent=2))
    except (GateError, ValueError, KeyError, TypeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
