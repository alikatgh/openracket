"""Python-only source preservation and synthetic mutation tests; no native evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load("binding_generator", HERE / "generate-named-style-comparator.py")
gate = load("binding_gate", HERE / "compare-named-style-trace.py")
original_tests = load("original_semantic_tests", HERE / "upstream/tests/test_compare_trace.py")
MANIFEST = original_tests.MANIFEST


class BindingSemanticTests(original_tests.SemanticTraceTests):
    """Run every unchanged original semantic mutation against the new wrapper."""
    def setUp(self):
        self.captures = [original_tests.capture("stock") for _ in range(4)]

    def run_gate(self):
        return gate.compare(*self.captures, MANIFEST)

    def reject(self, expression=""):
        # Each source-preserving import owns its own GateError class.
        with self.assertRaisesRegex(gate.GateError, expression):
            self.run_gate()

    def test_truthful_external_labels_and_no_activation_claim(self):
        result = self.run_gate()
        self.assertEqual(result["external_capture_labels"],
                         ["stock", "stock-again", "named-style-candidate-off", "named-style-candidate-on"])
        self.assertEqual([d["right"] for d in result["raw_order_diagnostics"]],
                         result["external_capture_labels"][1:])
        self.assertEqual(result["xref_capture_mode"], "stock")
        self.assertNotIn("actual_enabled_activation", result)
        self.assertEqual(result["named_style_gui_activation"], "not_assessed_by_this_worker_trace_gate")

    def test_all_four_slots_require_stock_xref_metadata(self):
        mutations = (("mode", "off"), ("mode", "on"), ("activation", False),
                     ("activation", True), ("flag", "1"), ("flag", "0"),
                     ("version", "9.2"), ("root", ""), ("executable", ""),
                     ("fixture_timeout_seconds", False), ("suite_timeout_seconds", 181))
        for slot in range(4):
            for field, value in mutations:
                with self.subTest(slot=slot, field=field, value=value):
                    saved = copy.deepcopy(self.captures)
                    self.captures[slot]["runtime"][field] = value
                    self.reject()
                    self.captures = saved

    def test_every_stock_source_pin_is_required_in_every_slot(self):
        for slot in range(4):
            for source in ("xref", "traversals", "online-comp"):
                for field, value in (("sha256", "0" * 64), ("path", "")):
                    with self.subTest(slot=slot, source=source, field=field):
                        saved = copy.deepcopy(self.captures)
                        self.captures[slot]["runtime"]["sources"][source][field] = value
                        self.reject()
                        self.captures = saved

    def test_forged_candidate_xref_captures_are_rejected(self):
        for slot in range(4):
            for mode in ("off", "on"):
                with self.subTest(slot=slot, mode=mode):
                    saved = copy.deepcopy(self.captures)
                    self.captures[slot] = original_tests.capture(mode)
                    self.reject("wrong capture mode")
                    self.captures = saved

    def test_completed_and_fixture_controls_still_fail_closed(self):
        for slot in range(4):
            for field, value in (("completed", False), ("schema", "other"), ("fixtures", [])):
                with self.subTest(slot=slot, field=field):
                    saved = copy.deepcopy(self.captures)
                    self.captures[slot][field] = value
                    self.reject()
                    self.captures = saved

    def test_mismatched_valid_timeout_rejected(self):
        self.captures[2]["runtime"]["fixture_timeout_seconds"] = 31
        self.reject("timeout bounds differ")

    def test_cannot_substitute_gui_manifest_or_a_new_xref_pin(self):
        for manifest in ({"original_sha256": "0" * 64}, {}):
            with self.subTest(manifest=manifest), self.assertRaisesRegex(gate.GateError, "pinned unchanged xref"):
                gate.compare(*self.captures, manifest)

    def test_compare_does_not_mutate_inputs_on_pass_or_failure(self):
        before = copy.deepcopy(self.captures)
        self.run_gate()
        self.assertEqual(self.captures, before)
        self.captures[3]["fixtures"][0]["rename_answers"][0]["answer"] = True
        before = copy.deepcopy(self.captures)
        self.reject()
        self.assertEqual(self.captures, before)

    def test_cli_hashes_unchanged_raw_bytes_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f"capture-{n}.json" for n in range(4)]
            for path, capture in zip(paths, self.captures):
                path.write_text(json.dumps(capture, indent=3), encoding="utf-8")
            raw = [path.read_bytes() for path in paths]
            cmd = [sys.executable, str(HERE / "compare-named-style-trace.py"), *map(str, paths)]
            result = subprocess.run(cmd, text=True, capture_output=True, check=True)
            data = json.loads(result.stdout)
            self.assertEqual(data["input_sha256"],
                             {str(p): hashlib.sha256(b).hexdigest() for p, b in zip(paths, raw)})
            self.assertEqual([p.read_bytes() for p in paths], raw)
            self.assertNotIn("actual_enabled_activation", data)
            self.captures[3]["runtime"]["mode"] = "on"
            paths[3].write_text(json.dumps(self.captures[3]), encoding="utf-8")
            result = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("wrong capture mode", result.stderr)
            self.assertEqual(result.stdout, "")


class PreservationTests(unittest.TestCase):
    def test_seven_byte_exact_original_source_pins(self):
        generator.verify_sources()

    def test_wrapper_is_exactly_generated_from_pinned_original(self):
        self.assertEqual((HERE / "compare-named-style-trace.py").read_bytes(),
                         generator.generated_source().encode("utf-8"))

    def test_projection_difference_and_validator_are_original_functions(self):
        self.assertIs(gate.project, gate.proven.project)
        self.assertIs(gate.difference, gate.proven.difference)
        self.assertIs(gate.strict.validate, gate.proven.strict.validate)

    def test_native_manifest_relative_layout_and_stock_pins_preserved(self):
        source = (HERE / "upstream/tests/native-trace.rkt").read_text(encoding="utf-8")
        self.assertIn('(define-runtime-path manifest-path "../manifest.json")', source)
        self.assertEqual(MANIFEST["original_sha256"], generator.XREF_ORIGINAL_SHA256)
        for pin in gate.strict.PINS.values():
            self.assertIn(pin, source)


if __name__ == "__main__":
    unittest.main()
