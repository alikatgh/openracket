import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out

prepare, applier = module("prepare"), module("apply")

class SourceTests(unittest.TestCase):
    def test_exact_bytes_and_only_three_edits(self):
        stock = (ROOT / "vendor/xref.rkt").read_bytes()
        overlay = (ROOT / "overlay/xref.rkt").read_bytes()
        self.assertEqual(prepare.generate(stock), overlay)
        stripped = overlay.replace(prepare.INSERT, b"").replace(prepare.NEW_REPLY, prepare.OLD_REPLY).replace(prepare.NEW_CALLER, prepare.OLD_CALLER)
        self.assertEqual(stripped, stock)
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(prepare.sha(stock), manifest["original_sha256"])
        self.assertEqual(prepare.sha(overlay), manifest["patched_sha256"])

    def test_reject_byte_different_source(self):
        stock = (ROOT / "vendor/xref.rkt").read_bytes()
        for changed in (stock.replace(b"\n", b"\r\n"), stock + b"\n", stock.replace(b"#f", b"#t", 1)):
            with self.assertRaises(ValueError):
                prepare.generate(changed)

    def test_lookup_cache_flush_and_dead_check_unchanged(self):
        stock = (ROOT / "vendor/xref.rkt").read_bytes()
        overlay = (ROOT / "overlay/xref.rkt").read_bytes()
        lookup = stock.split(b"(define (lookup-binding-info", 1)[1].split(b"     (let loop", 1)[0]
        self.assertIn(lookup, overlay)
        self.assertEqual(stock.split(b"(define (flush-index-entry-cache)", 1)[1], overlay.split(b"(define (flush-index-entry-cache)", 1)[1])
        self.assertEqual(stock.count(b"(not (thread-dead? thd))"), overlay.count(b"(not (thread-dead? thd))"))
        self.assertEqual(stock.count(b"(nack-guard-evt"), overlay.count(b"(nack-guard-evt"))
        self.assertIn(b'(equal? (getenv "OPENRACKET_XREF_REPLY_CELL") "1")', overlay)

class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.target = self.root / "share/pkgs/drracket-tool-text-lib/drracket/private/syncheck/xref.rkt"
        self.target.parent.mkdir(parents=True)
        self.stock = (ROOT / "vendor/xref.rkt").read_bytes()
        self.target.write_bytes(self.stock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_idempotent_revert(self):
        self.assertTrue(applier.apply(self.root, self.target, disposable=True)["changed"])
        self.assertFalse(applier.apply(self.root, self.target, disposable=True)["changed"])
        self.assertTrue(applier.apply(self.root, self.target, disposable=True, revert=True)["changed"])
        self.assertEqual(self.target.read_bytes(), self.stock)

    def test_refuse_wrong_target_and_missing_ack(self):
        with self.assertRaises(ValueError):
            applier.apply(self.root, self.target)
        with self.assertRaises(ValueError):
            applier.apply(self.root / "elsewhere", self.target, disposable=True)
        self.target.write_bytes(self.stock + b"\n")
        with self.assertRaises(ValueError):
            applier.apply(self.root, self.target, disposable=True)

    def test_refuse_root_symlink(self):
        alias = self.root / "alias"
        alias.symlink_to(self.target.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            applier.apply(alias, alias / "xref.rkt", disposable=True)

    def test_refuse_hardlink(self):
        import os
        os.link(self.target, self.root / "unrelated")
        with self.assertRaises(ValueError):
            applier.apply(self.root, self.target, disposable=True)
        self.assertEqual((self.root / "unrelated").read_bytes(), self.stock)

if __name__ == "__main__":
    unittest.main()
