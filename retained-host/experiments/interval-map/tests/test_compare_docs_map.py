#!/usr/bin/env python3
"""Synthetic rejection tests, not substitute/native GUI results."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


gate = module("compare_docs_map", HERE / "compare-docs-map.py")
prepare = module("prepare_native_host", ROOT / "scripts/prepare-native-host.py")


def path(value):
    return ["path", "unix", ["root", "runtime", list(value.encode())]]


def fixture(mode):
    root = "/tmp/disposable-" + mode
    doc = path("doc/reference/generic-numbers.html")
    define_tag = ["list", ["symbol", "form"],
                  ["list", ["list", ["symbol", "lib"], ["string", "racket/private/base.rkt"]], ["symbol", "define"]]]
    intervals = [
        {"start": 18, "end": 25,
         "stored": ["list", ["integer", "18"], ["integer", "25"], define_tag,
                    path("doc/reference/define.html"), ["string", "(form._((lib._racket/private/base..rkt)._define))"]]},
        {"start": 36, "end": 38,
         "stored": ["list", ["integer", "36"], ["integer", "38"], copy.deepcopy(gate.PLUS_TAG),
                    doc, copy.deepcopy(gate.PLUS_ANCHOR)]},
    ]
    sources = {name: {"path": path("share/pkgs/drracket-tool-text-lib/drracket/private/syncheck/" + name + ".rkt"),
                      "sha256": pin} for name, pin in gate.PINS.items()}
    for name in ("gui", "blueboxes-gui", "online-comp"):
        sources[name]["path"] = path("share/pkgs/drracket-core-lib/drracket/private/syncheck/" + name + ".rkt")
    sources["interval-map"] = {"path": path("share/pkgs/data-lib/data/interval-map.rkt"),
                               "sha256": gate.ORIGINAL if mode == "stock" else gate.CANDIDATE}
    return {"schema": gate.SCHEMA, "completed": True,
            "runtime": {"mode": mode, "version": "9.3", "flag": None if mode == "stock" else "1",
                        "activation": "unexported" if mode == "stock" else True,
                        "root": root, "root_bytes": list(root.encode()), "executable": path("bin/racket"), "sources": sources},
            "host": {"sha256": gate.HOST, "workflow_sha256": gate.WORKFLOW, "case": "check-syntax", "ui": "stock",
                     "fatal_check_handler": True, "handler_thread_verified": True,
                     "getter": "existing-module-namespace/lexical-get-docs-im", "source_pins_unchanged": True},
            "editor": {"source": gate.SOURCE, "characters": 54, "selection": [1, 6],
                       **{key: True for key in gate.EDITOR_FLAGS}},
            "interval_count": 2, "intervals": intervals,
            "plus": {"position": 36, "source_end": 37, "stored_end": 38, "interval_index": 1,
                     "definition_tag": copy.deepcopy(gate.PLUS_TAG), "path": copy.deepcopy(doc),
                     "url_anchor": copy.deepcopy(gate.PLUS_ANCHOR), "query_bounds": [36, 38],
                     "at_37": copy.deepcopy(intervals[1]["stored"]), "at_38": ["boolean", False]}}


class DocsMapTests(unittest.TestCase):
    def setUp(self):
        self.stock, self.on = fixture("stock"), fixture("candidate-on")

    def reject(self, mutate, capture="on"):
        mutate(getattr(self, capture))
        with self.assertRaises(gate.GateError):
            gate.compare(self.stock, self.on)

    def test_equal_full_synthetic_capture(self):
        self.assertTrue(gate.compare(self.stock, self.on)["equal"])

    def test_missing_interval_even_with_updated_count(self):
        self.reject(lambda c: (c["intervals"].pop(0), c.update(interval_count=1), c["plus"].update(interval_index=0)))

    def test_empty_intervals(self):
        self.reject(lambda c: c.update(intervals=[], interval_count=0))

    def test_count_mismatch(self):
        self.reject(lambda c: c.update(interval_count=1))

    def test_duplicate_interval(self):
        self.reject(lambda c: (c["intervals"].append(copy.deepcopy(c["intervals"][-1])), c.update(interval_count=3)))

    def test_reordered_intervals(self):
        self.reject(lambda c: c["intervals"].reverse())

    def test_changed_nonplus_geometry(self):
        self.reject(lambda c: c["intervals"][0].update(start=19))

    def test_changed_stored_nonplus_geometry(self):
        self.reject(lambda c: c["intervals"][0]["stored"][1].__setitem__(1, "17"))

    def test_changed_definition_tag(self):
        self.reject(lambda c: c["intervals"][0]["stored"][3][-1][-1].__setitem__(1, "require"))

    def test_changed_full_path(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(4, path("other/reference/define.html")))

    def test_changed_anchor(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(5, ["string", "different"]))

    def test_plus_missing(self):
        self.reject(lambda c: (c["intervals"].pop(), c.update(interval_count=1)))

    def test_plus_geometry(self):
        self.reject(lambda c: c["intervals"][1].update(end=37))

    def test_plus_definition_tag(self):
        self.reject(lambda c: c["plus"]["definition_tag"][-1][-1].__setitem__(1, "-"))

    def test_plus_path(self):
        self.reject(lambda c: c["plus"].update(path=path("doc/reference/pairs.html")))

    def test_plus_anchor(self):
        self.reject(lambda c: c["plus"].update(url_anchor=["string", "wrong"]))

    def test_plus_index(self):
        self.reject(lambda c: c["plus"].update(interval_index=0))

    def test_plus_position(self):
        self.reject(lambda c: c["plus"].update(position=35))

    def test_plus_source_end(self):
        self.reject(lambda c: c["plus"].update(source_end=38))

    def test_plus_stored_end(self):
        self.reject(lambda c: c["plus"].update(stored_end=37))

    def test_changed_query_bounds(self):
        self.reject(lambda c: c["plus"].update(query_bounds=[36, 37]))

    def test_changed_point37_value(self):
        self.reject(lambda c: c["plus"].update(at_37=["boolean", False]))

    def test_point38_includes_plus(self):
        self.reject(lambda c: c["plus"].update(at_38=copy.deepcopy(c["plus"]["at_37"])))

    def test_point38_invented_result(self):
        self.reject(lambda c: c["plus"].update(at_38=copy.deepcopy(c["intervals"][0]["stored"])))

    def test_false_activation(self):
        self.reject(lambda c: c["runtime"].update(activation=False))

    def test_truthy_activation(self):
        self.reject(lambda c: c["runtime"].update(activation=1))

    def test_stock_export_present(self):
        self.reject(lambda c: c["runtime"].update(activation=False), "stock")

    def test_missing_flag(self):
        self.reject(lambda c: c["runtime"].update(flag=None))

    def test_wrong_mode(self):
        self.reject(lambda c: c["runtime"].update(mode="on"))

    def test_wrong_racket_version(self):
        self.reject(lambda c: c["runtime"].update(version="9.2"))

    def test_changed_fixture_source(self):
        self.reject(lambda c: c["editor"].update(source=gate.SOURCE.replace("41", "42")))

    def test_changed_selection(self):
        self.reject(lambda c: c["editor"].update(selection=[0, 0]))

    def test_each_identity_check_required(self):
        for key in gate.EDITOR_FLAGS:
            with self.subTest(key=key):
                self.on = fixture("candidate-on")
                self.reject(lambda c: c["editor"].update({key: False}))

    def test_all_source_pins_required(self):
        for name in self.on["runtime"]["sources"]:
            with self.subTest(name=name):
                self.on = fixture("candidate-on")
                self.reject(lambda c: c["runtime"]["sources"][name].update(sha256="0" * 64))

    def test_changed_resolved_source_path(self):
        self.reject(lambda c: c["runtime"]["sources"]["gui"].update(path=path("other/drracket/private/syncheck/gui.rkt")))

    def test_changed_executable(self):
        self.reject(lambda c: c["runtime"].update(executable=path("other/bin/racket")))

    def test_handler_thread_not_verified(self):
        self.reject(lambda c: c["host"].update(handler_thread_verified=False))

    def test_nonfatal_checks(self):
        self.reject(lambda c: c["host"].update(fatal_check_handler=False))

    def test_wrong_getter(self):
        self.reject(lambda c: c["host"].update(getter="ordinary-symbol-send"))

    def test_wrong_host_pin(self):
        self.reject(lambda c: c["host"].update(sha256="0" * 64))

    def test_wrong_workflow_pin(self):
        self.reject(lambda c: c["host"].update(workflow_sha256="0" * 64))

    def test_wrong_case(self):
        self.reject(lambda c: c["host"].update(case="wxme"))

    def test_wrong_ui(self):
        self.reject(lambda c: c["host"].update(ui="modern"))

    def test_incomplete_capture(self):
        self.reject(lambda c: c.update(completed=False))

    def test_extra_top_field(self):
        self.reject(lambda c: c.update(unreviewed=True))

    def test_extra_nested_field(self):
        self.reject(lambda c: c["intervals"][0].update(unreviewed=True))

    def test_extra_runtime_field(self):
        self.reject(lambda c: c["runtime"].update(unreviewed=True))

    def test_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "capture.json"
            file.write_text('{"completed":false,"completed":true}')
            with self.assertRaises(gate.GateError):
                gate.load_capture(file)

    def test_duplicate_nested_json_key(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "capture.json"
            file.write_text('{"host":{"case":"x","case":"check-syntax"}}')
            with self.assertRaises(gate.GateError):
                gate.load_capture(file)

    def test_non_json_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "capture.json"
            file.write_text('{"x":NaN}')
            with self.assertRaises(gate.GateError):
                gate.load_capture(file)

    def test_root_bytes_mismatch(self):
        self.reject(lambda c: c["runtime"].update(root_bytes=list(b"/different")))

    def test_noncanonical_root(self):
        self.reject(lambda c: c["runtime"].update(root="/tmp/../different"))

    def test_same_clone_root(self):
        self.reject(lambda c: c["runtime"].update(root=self.stock["runtime"]["root"], root_bytes=self.stock["runtime"]["root_bytes"]))

    def test_escaping_path(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(4, path("../doc/reference/define.html")))

    def test_noncanonical_path(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(4, path("doc//reference/define.html")))

    def test_literal_path_not_permitted(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(4, ["path", "unix", ["literal", list(b"/a")]]))

    def test_bool_is_not_byte(self):
        self.reject(lambda c: c["intervals"][0]["stored"][4][2][2].__setitem__(0, True))

    def test_bool_is_not_integer(self):
        self.reject(lambda c: c["intervals"][0].update(start=True))

    def test_unsupported_datum_rejected(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(3, ["opaque", "anything"]))

    def test_untyped_string_rejected(self):
        self.reject(lambda c: c["intervals"][0]["stored"].__setitem__(5, "anchor"))

    def test_duplicate_nested_datum_retained(self):
        # A duplicate inside a stored tag cannot disappear through comparison.
        self.reject(lambda c: c["intervals"][0]["stored"][3].append(copy.deepcopy(c["intervals"][0]["stored"][3][1])))

    def test_noncanonical_integer_datum_rejected(self):
        self.reject(lambda c: c["intervals"][0]["stored"][1].__setitem__(1, "018"))

    def test_arbitrary_root_text_inside_string_not_normalized(self):
        self.stock["intervals"][0]["stored"][5] = ["string", "/tmp/disposable-stock/text"]
        self.on["intervals"][0]["stored"][5] = ["string", "/tmp/disposable-candidate-on/text"]
        with self.assertRaises(gate.GateError):
            gate.compare(self.stock, self.on)


class HostSourceTests(unittest.TestCase):
    def test_exact_two_insertion_derivative(self):
        derived = (HERE / "independent-native-host.rkt").read_bytes()
        source = derived
        for _, addition, _ in prepare.INSERTIONS:
            self.assertEqual(source.count(addition), 1)
            source = source.replace(addition, b"")
        self.assertEqual(hashlib.sha256(source).hexdigest(), prepare.HOST_PIN)
        self.assertEqual(prepare.derive(source), derived)
        self.assertEqual(hashlib.sha256(derived).hexdigest(), gate.HOST)

    def test_tampered_base_refused(self):
        with self.assertRaises(ValueError):
            prepare.derive(b"#lang racket/base\n")

    def test_all_copied_dependencies_unchanged(self):
        for filename, expected in prepare.DEPENDENCIES.items():
            self.assertEqual(hashlib.sha256((HERE / filename).read_bytes()).hexdigest(), expected)
        for filename, expected in prepare.TOOL_DEPENDENCIES.items():
            self.assertEqual(hashlib.sha256((ROOT / "tool" / filename).read_bytes()).hexdigest(), expected)

    def test_postflight_source_seams(self):
        source = (HERE / "interval-docs-postflight.rkt").read_text()
        self.assertEqual(source.count("(eval '(lambda (editor) (send editor get-docs-im)))"), 1)
        self.assertIn("(module->namespace (hash-ref module-paths 'blueboxes-gui))", source)
        self.assertIn("(parameterize ([current-check-handler raise])", source)
        self.assertNotIn("(dynamic-require 'drracket/private/syncheck/blueboxes-gui", source)
        for pin in [gate.ORIGINAL, gate.CANDIDATE, gate.HOST, gate.WORKFLOW, *gate.PINS.values()]:
            self.assertIn(pin, source)
        # The implementation invokes only the nonallocating getter and readers.
        for mutator in ["interval-map-set!", "interval-map-update!", "interval-map-remove!", "preferences:set", "set-position", "change-to-file"]:
            self.assertNotIn("(" + mutator, source)
        self.assertNotIn("(send editor get/start-docs-im)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
