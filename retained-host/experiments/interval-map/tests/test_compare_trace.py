"""Synthetic mutation tests for the bounded comparator, not native evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("semantic_trace", HERE / "compare-trace.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
MANIFEST_PATH = HERE / "manifest.json"
if not MANIFEST_PATH.exists():
    MANIFEST_PATH = HERE.parent / "manifest.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text())


def sym(value):
    return ["symbol", value]


def num(value):
    return ["number", str(value)]


def encoded_path(value="doc/reference/numbers.html"):
    return ["path", "unix", ["root", "runtime", list(value.encode())]]


def docs(left, right, name="add1", label="View documentation"):
    return [["vector", sym(gate.TEXT), num(left), num(right), sym("document-identifier")],
            ["vector", sym(gate.DOCS), num(left), num(right), sym(name), label,
             encoded_path(), ["list", sym("def"), sym(name)], "anchor-" + name]]


def arrow(left, right, end_left, end_right, require=True):
    return ["vector", sym(gate.ARROW), num(left), num(right), num(.5), num(.5),
            num(end_left), num(end_right), num(.5), num(.5), True, num(0),
            sym("module-lang") if require else False, ["rename-channel", 0], num(0)]


def reindex(fixture, answers_by_object=None):
    """Simulate the real producer's fresh table; preserve attached answers."""
    if answers_by_object is None:
        answers_by_object = {}
    answers = []
    request = 0
    for index, entry in enumerate(fixture["trace"]):
        if gate.method(entry) == gate.ARROW:
            entry[-2:] = [["rename-channel", 0], num(request)]
            values = answers_by_object.get(id(entry), [q == "existing" for q in gate.strict.QUERIES])
            for query, answer in zip(gate.strict.QUERIES, values):
                answers.append({"entry_index": index, "channel": 0, "request_id": request,
                                "query": query, "answer": answer})
            request += 1
    fixture["rename_answers"] = answers
    fixture["documentation_count"] = sum(gate.method(e) == gate.DOCS for e in fixture["trace"])


def fixture(name):
    binding = "bump" if name == "import-aliases" else "add1"
    bindings = [binding] * 4 + (["base:add1"] * 2 if name == "import-aliases" else [])
    source = "#lang racket/base\n;; λ雪🦊\n" + " ".join(bindings) + "\n"
    trace = [["vector", sym(gate.REQUIRE), num(6), num(17), encoded_path("collects/racket/base.rkt")]]
    previous = 0
    positions = []
    for name_at_position in bindings:
        left = source.index(name_at_position, previous)
        previous = left + len(name_at_position)
        trace.extend(docs(left, previous, name_at_position))
        positions.append((left, previous))
    trace.extend([arrow(6, 17, *positions[0]), arrow(6, 17, *positions[1])])
    out = {"name": name, "source": source, "trace": trace, "rename_answers": [],
           "documentation_count": 0, "repeated_key": binding, "repeated_minimum": 4,
           "no_docs_key": "undocumented-value" if name == "undocumented-binding" else False}
    reindex(out)
    return out


def capture(mode):
    sources = {name: {"path": "/runtime/" + name + ".rkt", "sha256": digest}
               for name, digest in gate.strict.PINS.items()}
    sources["interval-map"] = {"path": "/runtime/data/interval-map.rkt", "sha256": MANIFEST[
        "original_sha256" if mode == "stock" else "patched_sha256"]}
    return {"schema": gate.strict.SCHEMA, "completed": True,
            "runtime": {"mode": mode, "version": "9.3", "root": "/runtime", "executable": "/runtime/bin/racket",
                        "fixture_timeout_seconds": 30, "suite_timeout_seconds": 180,
                        "activation": {"stock": "unexported", "off": False, "on": True}[mode],
                        "flag": "1" if mode == "on" else None, "sources": sources},
            "fixtures": [fixture(name) for name in gate.strict.FIXTURES]}


class SemanticTraceTests(unittest.TestCase):
    def setUp(self):
        self.captures = [capture(mode) for mode in ("stock", "stock", "off", "on")]

    def run_gate(self):
        return gate.compare(*self.captures, MANIFEST)

    def change_all(self, change):
        for capture_ in self.captures:
            change(capture_["fixtures"][0])
            reindex(capture_["fixtures"][0])

    def reject(self, expression=""):
        with self.assertRaisesRegex(gate.GateError, expression):
            self.run_gate()

    def test_identical_trace_contract(self):
        result = self.run_gate()
        self.assertTrue(result["targeted_annotation_semantics_equal"])
        self.assertTrue(result["exact_raw_order_equal"])

    def test_homogeneous_require_permutation_keeps_raw_failure_visible(self):
        for index in (1, 2, 3):
            fixture_ = self.captures[index]["fixtures"][0]
            fixture_["trace"][-2:] = reversed(fixture_["trace"][-2:])
            reindex(fixture_)
        result = self.run_gate()
        self.assertTrue(result["targeted_annotation_semantics_equal"])
        self.assertFalse(result["exact_raw_order_equal"])
        self.assertTrue(result["raw_order_diagnostics"][0]["require_arrow_paint_order_variation"])

    def test_disjoint_complete_doc_groups_can_commute(self):
        fixture_ = self.captures[3]["fixtures"][0]
        fixture_["trace"][1:5] = fixture_["trace"][3:5] + fixture_["trace"][1:3]
        reindex(fixture_)
        self.assertTrue(self.run_gate()["targeted_annotation_semantics_equal"])

    def test_changed_edge_phase_require_or_geometry_is_rejected(self):
        for index, value in [(6, num(1)), (11, num(1)), (12, False), (4, num(.2)), (8, num(.2))]:
            with self.subTest(field=index):
                saved = copy.deepcopy(self.captures)
                self.captures[3]["fixtures"][0]["trace"][-1][index] = value
                self.reject()
                self.captures = saved

    def test_missing_or_duplicate_annotation_is_rejected(self):
        hover = ["vector", sym(gate.HOVER), num(1), num(2), "same tooltip"]
        self.change_all(lambda f: f["trace"].append(copy.deepcopy(hover)))
        for operation in ("missing", "duplicate"):
            with self.subTest(operation=operation):
                saved = copy.deepcopy(self.captures)
                trace = self.captures[3]["fixtures"][0]["trace"]
                trace.pop() if operation == "missing" else trace.append(copy.deepcopy(hover))
                self.reject("event_inventory")
                self.captures = saved

    def test_answer_change_is_rejected(self):
        self.captures[3]["fixtures"][0]["rename_answers"][0]["answer"] = True
        self.reject()

    def test_answer_moved_to_different_logical_arrow_is_rejected(self):
        # Local arrows have distinct tested answers. Moving those responses is
        # not a harmless transport-handle alpha-renaming.
        for capture_ in self.captures:
            f = capture_["fixtures"][0]
            f["trace"][-2][12] = False
            f["trace"][-1][12] = False
            f["rename_answers"][0]["answer"] = True
        answers = self.captures[3]["fixtures"][0]["rename_answers"]
        answers[0]["answer"], answers[5]["answer"] = answers[5]["answer"], answers[0]["answer"]
        self.reject("event_inventory")

    def test_nonbijective_rename_table_is_rejected(self):
        f = self.captures[3]["fixtures"][0]
        f["trace"][-1][-1] = num(0)
        for answer in f["rename_answers"][5:]:
            answer["request_id"] = 0
        self.reject("consecutive unique IDs")

    def test_overlapping_docs_and_menu_order_is_rejected(self):
        self.change_all(lambda f: f["trace"].extend(docs(0, 0, "first-doc") + docs(0, 0, "second-doc")))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-4:] = f["trace"][-2:] + f["trace"][-4:-2]
        self.reject("docs_overwrite_map|docs_overlap_order|menus")

    def test_docs_end_plus_one_overlap_is_preserved(self):
        self.change_all(lambda f: f["trace"].extend(docs(0, 1, "left-doc") + docs(1, 2, "right-doc")))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-4:] = f["trace"][-2:] + f["trace"][-4:-2]
        self.reject("docs_overwrite_map|docs_overlap_order")

    def test_same_menu_key_keeps_first_callback_and_all_occurrences(self):
        self.change_all(lambda f: f["trace"].extend(docs(0, 0, "same", "first") + docs(0, 0, "same", "second")))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-4:] = f["trace"][-2:] + f["trace"][-4:-2]
        self.reject("docs_overlap_order|menus")

    def test_tooltip_local_order_is_conservatively_preserved(self):
        self.change_all(lambda f: f["trace"].extend([
            ["vector", sym(gate.HOVER), num(0), num(1), "first"],
            ["vector", sym(gate.HOVER), num(0), num(1), "second"]]))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        self.reject("tooltips")

    def test_overlapping_definition_links_keep_navigation_choice(self):
        self.change_all(lambda f: f["trace"].extend([
            ["vector", sym(gate.JUMP), num(0), num(1), sym(name), encoded_path(), ["list"], num(0)]
            for name in ("first", "second")]))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        self.reject("def_links")

    def test_definition_target_same_key_last_write_is_preserved(self):
        self.change_all(lambda f: f["trace"].extend([
            ["vector", sym(gate.TARGET), num(start), num(start + 1), sym("same"), ["list"], num(0)]
            for start in (0, 2)]))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        self.reject("definition_targets|definition_target_order")

    def test_local_arrow_overlap_order_is_not_normalized(self):
        self.change_all(lambda f: [e.__setitem__(12, False) for e in f["trace"] if gate.method(e) == gate.ARROW])
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        reindex(f)
        self.reject("source_selection_order")

    def test_tail_and_variable_overlap_order_is_not_normalized(self):
        self.change_all(lambda f: f["trace"].append(["vector", sym(gate.TAIL), num(6), num(7)]))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-3:] = f["trace"][-1:] + f["trace"][-3:-1]
        reindex(f)
        self.reject("source_selection_order")

    def test_require_arrows_with_different_binders_keep_selection_order(self):
        self.change_all(lambda f: f["trace"][-1].__setitem__(2, num(5)))
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        reindex(f)
        self.reject("source_selection_order|first_binding_destination")

    def test_duplicate_endpoint_first_metadata_is_preserved(self):
        def add_duplicate(f):
            old = f["trace"][-1]
            old[12] = False
            new = copy.deepcopy(old)
            new[10] = False
            f["trace"].append(new)
        self.change_all(add_duplicate)
        f = self.captures[3]["fixtures"][0]
        f["trace"][-2:] = reversed(f["trace"][-2:])
        reindex(f)
        self.reject("endpoint_occurrences|retained_binding_graph")

    def test_unknown_method_and_unobserved_text_type_fail_closed(self):
        self.captures[3]["fixtures"][0]["trace"].append(["vector", sym("syncheck:unknown")])
        self.reject("unsupported annotation method")
        self.captures[3]["fixtures"][0]["trace"].pop()
        self.captures[3]["fixtures"][0]["trace"][1][4] = sym("new-style")
        self.reject("unobserved text-type")

    def test_docs_pair_adjacency_is_preserved(self):
        f = self.captures[3]["fixtures"][0]
        f["trace"][1:3] = reversed(f["trace"][1:3])
        self.reject("paired with its actual preceding")

    def test_stock_semantic_instability_remains_a_blocker(self):
        self.captures[1]["fixtures"][0]["trace"][2][5] = "different docs label"
        self.reject("Stock annotation semantics are unstable")

    def test_source_only_corruption_is_rejected(self):
        self.captures[3]["fixtures"][0]["source"] += ";; changed source only\n"
        self.reject("annotation_contract\\[0\\].source")


if __name__ == "__main__":
    unittest.main()
