"""Portable validation of the comparator; these synthetic records are not native evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compare_trace_exact", ROOT / "tests/compare-trace-exact.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
MANIFEST = json.loads((ROOT / "manifest.json").read_text())


def symbol(value):
    return ["symbol", value]


def number(value):
    return ["number", str(value)]


def fixture(name):
    key = "bump" if name == "import-aliases" else "add1"
    keys = [key] * 4
    if name == "import-aliases":
        keys += ["base:add1", "base:add1"]
    source = "#lang racket/base\n;; λ雪🦊\n" + " ".join(keys) + "\n"
    trace = []
    previous = 0
    for key_at_position in keys:
        left = source.index(key_at_position, previous)
        previous = left + len(key_at_position)
        trace.append(["vector", symbol(gate.DOC_METHOD), number(left), number(previous),
                      symbol(key_at_position), "View documentation for add1",
                      ["path", "unix", ["root", "runtime", list(b"doc/reference/generic-numbers.html")]],
                      ["list", symbol("def"), ["list", "racket/base", symbol("add1")]],
                      "(def._((quote._~23~25kernel)._add1))"])
    arrow_index = len(trace)
    trace.append(["vector", symbol(gate.ARROW_METHOD), number(1), number(2), number(0.5), number(0.5),
                  number(4), number(5), number(0.5), number(0.5), True, number(0), False,
                  ["rename-channel", 0], number(0)])
    answers = [{"entry_index": arrow_index, "channel": 0, "request_id": 0, "query": query,
                "answer": query == "existing"} for query in gate.QUERIES]
    return {"name": name, "source": source, "trace": trace, "rename_answers": answers,
            "documentation_count": len(keys), "repeated_key": key, "repeated_minimum": 4,
            "no_docs_key": "undocumented-value" if name == "undocumented-binding" else False}


def capture(mode):
    sources = {name: {"path": "/runtime/" + name + ".rkt", "sha256": pin}
               for name, pin in gate.PINS.items()}
    sources["interval-map"] = {"path": "/runtime/data/interval-map.rkt", "sha256":
                       MANIFEST["original_sha256" if mode == "stock" else "patched_sha256"]}
    return {"schema": gate.SCHEMA, "completed": True,
            "runtime": {"mode": mode, "version": "9.3", "root": "/runtime", "executable": "/runtime/bin/racket",
                        "fixture_timeout_seconds": 30, "suite_timeout_seconds": 180,
                        "activation": {"stock": "unexported", "off": False, "on": True}[mode],
                        "flag": "1" if mode == "on" else None, "sources": sources},
            "fixtures": [fixture(name) for name in gate.FIXTURES]}


class CompareTraceTests(unittest.TestCase):
    def setUp(self):
        self.captures = [capture(mode) for mode in ("stock", "stock", "off", "on")]

    def compare(self):
        return gate.compare(*self.captures, MANIFEST)

    def test_equal_ordered_logical_trace_passes(self):
        result = self.compare()
        self.assertTrue(result["equal"])
        self.assertTrue(result["stock_control_stable"])
        self.assertEqual(result["fixtures"], 5)
        self.assertEqual(result["rename_answers"], 25)

    def test_stock_instability_blocks_before_candidate_interpretation(self):
        trace = self.captures[1]["fixtures"][0]["trace"]
        trace[0], trace[1] = trace[1], trace[0]
        self.captures[3]["runtime"]["activation"] = False
        with self.assertRaisesRegex(gate.GateError, "Stock-to-stock control is unstable.*trace"):
            self.compare()

    def test_labels_paths_definition_tags_and_anchors_are_not_elided(self):
        mutations = {
            "label": (5, "Another documentation label"),
            "path": (6, ["path", "unix", ["root", "runtime", list(b"doc/wrong.html")]]),
            "path-convention": (6, ["path", "windows", ["root", "runtime", list(b"doc/reference/generic-numbers.html")]]),
            "definition-tag": (7, ["list", symbol("def"), symbol("wrong")]),
            "anchor": (8, "different-anchor"),
        }
        for label, (index, value) in mutations.items():
            with self.subTest(field=label):
                changed = copy.deepcopy(self.captures)
                changed[3]["fixtures"][0]["trace"][0][index] = value
                with self.assertRaisesRegex(gate.GateError, "Stock versus on differs"):
                    gate.compare(*changed, MANIFEST)

    def test_reordered_candidate_is_not_sorted(self):
        trace = self.captures[3]["fixtures"][0]["trace"]
        trace[0], trace[1] = trace[1], trace[0]
        with self.assertRaisesRegex(gate.GateError, "Stock versus on differs.*trace"):
            self.compare()

    def test_duplicate_non_docs_entry_is_retained(self):
        self.captures[3]["fixtures"][0]["trace"].append(
            ["vector", symbol("syncheck:add-text-type"), number(1), number(2), symbol("document-identifier")])
        with self.assertRaisesRegex(gate.GateError, "Stock versus on differs.*length"):
            self.compare()

    def test_missing_docs_fails(self):
        self.captures[3]["fixtures"][0]["documentation_count"] = 0
        with self.assertRaisesRegex(gate.GateError, "documentation control failed"):
            self.compare()

    def test_false_or_numeric_activation_is_not_enabled(self):
        for bad in (False, 1, "true", None):
            with self.subTest(activation=bad):
                changed = copy.deepcopy(self.captures)
                changed[3]["runtime"]["activation"] = bad
                with self.assertRaisesRegex(gate.GateError, "activation disagrees"):
                    gate.compare(*changed, MANIFEST)

    def test_default_off_requires_unset_flag(self):
        self.captures[2]["runtime"]["flag"] = "0"
        with self.assertRaisesRegex(gate.GateError, "environment flag disagrees"):
            self.compare()

    def test_handler_source_pin_is_required(self):
        self.captures[3]["runtime"]["sources"]["online-comp"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(gate.GateError, "source pin mismatch"):
            self.compare()

    def test_every_rename_query_requires_actual_boolean_response(self):
        self.captures[3]["fixtures"][0]["rename_answers"].pop()
        with self.assertRaisesRegex(gate.GateError, "not every real rename endpoint"):
            self.compare()

    def test_rename_answers_are_compared(self):
        self.captures[3]["fixtures"][0]["rename_answers"][0]["answer"] = True
        with self.assertRaisesRegex(gate.GateError, "Stock versus on differs.*rename_answers"):
            self.compare()

    def test_unicode_positions_are_character_positions(self):
        self.captures[3]["fixtures"][1]["trace"][0][2] = number(1)
        with self.assertRaisesRegex(gate.GateError, "Unicode/source positions differ"):
            self.compare()

    def test_failed_or_incomplete_capture_cannot_pass(self):
        self.captures[3]["completed"] = False
        with self.assertRaisesRegex(gate.GateError, "successful actual-handler completion"):
            self.compare()

    def test_invalid_timeout_evidence_fails(self):
        cases = [("fixture_timeout_seconds", value) for value in (None, 0, -1, 121, True, float("nan"), float("inf"))]
        cases += [("suite_timeout_seconds", value) for value in (None, 0, 181, 180.0, True)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.captures)
                changed[3]["runtime"][field] = value
                with self.assertRaisesRegex(gate.GateError, "timeout evidence missing"):
                    gate.compare(*changed, MANIFEST)

    def test_all_four_captures_require_matching_timeout_bounds(self):
        for index in (1, 2, 3):
            with self.subTest(capture=index):
                changed = copy.deepcopy(self.captures)
                changed[index]["runtime"]["fixture_timeout_seconds"] = 60
                with self.assertRaisesRegex(gate.GateError, "timeout bounds differ"):
                    gate.compare(*changed, MANIFEST)


if __name__ == "__main__":
    unittest.main()
