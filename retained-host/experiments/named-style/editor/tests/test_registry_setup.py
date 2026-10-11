"""Portable source/typed-negative checks, not execution of a native registry."""
import copy
import hashlib
from pathlib import Path
import unittest
from test_compare import c, capture

ROOT = Path(__file__).resolve().parents[1]

class RegistrySetupTests(unittest.TestCase):
    def test_only_additive_comparator_changes(self):
        source = (ROOT / "scripts/compare.py").read_text()
        source = source.replace('SEMANTIC_KEYS = ("registry_setup", "fixture_search",',
                                'SEMANTIC_KEYS = ("fixture_search",')
        start = source.index("# Additive exact registry contract;")
        end = source.index("class GateError(ValueError):", start)
        source = source[:start] + source[end:]
        start = source.index("def registry_setup(v, path):")
        end = source.index("def diagnostics(v, mode, path):", start)
        source = source[:start] + source[end:]
        source = source.replace('    registry_setup(v["registry_setup"], p + ".registry_setup")\n', '')
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         "e7309f8bfeca1e6c308cf507da5486364e94d87acefb30c8a97015d430bb3e32")

    def test_exact_before_after_witness_is_required(self):
        for field, replacement in (
            (("before", "index"), 0),
            (("before", "registered_same_object"), 0),
            (("after", "index"), -1),
            (("after", "index"), 3.0),
            (("after", "registered_same_object"), False),
            (("after", "registered_same_object"), 1),
            (("prior_entries_same",), False),
            (("stock_class_same",), False),
        ):
            with self.subTest(field=field, replacement=replacement):
                value = capture("stock")
                target = value["registry_setup"]
                for key in field[:-1]:
                    target = target[key]
                target[field[-1]] = replacement
                with self.assertRaises(c.GateError):
                    c.validate(value, "stock")

    def test_wrong_class_version_order_and_missing_evidence_fail(self):
        for kind in ("name", "version", "numeric-version", "boolean-version", "numeric-index", "boolean-index", "order", "missing", "extra"):
            with self.subTest(kind=kind):
                value = capture("stock")
                classes = value["registry_setup"]["after"]["classes"]
                if kind == "name": classes[-1]["class"] = "fake:wxmedia"
                elif kind == "version": classes[-1]["version"] = 3
                elif kind == "numeric-version": classes[-1]["version"] = 4.0
                elif kind == "boolean-version": classes[1]["version"] = True
                elif kind == "numeric-index": classes[1]["index"] = 1.0
                elif kind == "boolean-index": classes[1]["index"] = True
                elif kind == "order": classes.reverse()
                elif kind == "missing": del value["registry_setup"]
                else: value["registry_setup"]["ignored"] = True
                with self.assertRaises(c.GateError):
                    c.validate(value, "stock")

    def test_actual_setup_precedes_unchanged_save_and_load(self):
        source = (ROOT / "native/editor-gate.rkt").read_text()
        self.assertLess(source.index("(make-rich!))", source.index("(define (run-on-handler!")),
                        source.index("(setup-editor-snip! embedded record!)"))
        self.assertLess(source.index("(setup-editor-snip! embedded record!)"),
                        source.index("(send rich save-file path 'standard)"))
        self.assertLess(source.index("(run-registration-controls!)"), source.index("(make-eventspace)"))
        self.assertEqual(source.count("(send restored load-file path 'standard)"), 1)
        self.assertEqual(source.count("(setup-editor-snip! embedded record!)"), 1)

    def test_source_guards_actual_identity_and_rejects_conflict_before_add(self):
        source = (ROOT / "native/registry-setup.rkt").read_text()
        for term in ('(eq? cls the-editor-snip-class)', '(send embedded get-snipclass)',
                     '(get-the-snip-class-list)', '(send registry nth i)',
                     '(eq? entry cls)', '(andmap eq? after expected)',
                     '(require-registered! registry cls)'):
            self.assertIn(term, source)
        self.assertLess(source.index('"conflicting wxmedia class object or version"'),
                        source.index('(send registry add cls)'))
        self.assertEqual(source.count('(send registry add cls)'), 1)
        self.assertNotIn('(send registry find ', source)
        self.assertNotIn('dynamic-require', source)

    def test_mandatory_native_negative_controls_use_same_helper(self):
        source = (ROOT / "native/registry-setup.rkt").read_text()
        for term in ('"absent class must fail validation"', "[version '(4 3)]",
                     '"conflict rejected before mutation"', "[behavior '(ignore wrong reorder)]",
                     '"existing exact class is not added again"', '"wrong requested version rejected"',
                     '(require-registered! absent expected)', '(ensure-registration! bad expected)'):
            self.assertIn(term, source)

if __name__ == "__main__":
    unittest.main()
