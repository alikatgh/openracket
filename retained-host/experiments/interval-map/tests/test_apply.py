import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("interval_apply", ROOT / "scripts/apply.py")
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.exp = self.base / "experiment"
        self.clone = self.base / "proof with spaces" / "runtime"
        self.target = self.clone / "share/pkgs/data-lib/data/interval-map.rkt"
        self.target.parent.mkdir(parents=True)
        for sub in ("vendor", "overlay"):
            (self.exp / sub).mkdir(parents=True)
        self.original = b"original exact bytes\n"
        self.patched = b"candidate exact bytes\n"
        (self.exp / "vendor/interval-map.rkt").write_bytes(self.original)
        (self.exp / "overlay/interval-map.rkt").write_bytes(self.patched)
        self.target.write_bytes(self.original)
        self.target.chmod(0o640)
        self.support = self.target.parent / "private/skip-list.rkt"
        self.support.parent.mkdir()
        self.support.write_bytes(b"unchanged support\n")
        self.manifest = {
            "relative_target": "data/interval-map.rkt",
            "original_sha256": digest(self.original),
            "patched_sha256": digest(self.patched),
            "unchanged_support_sha256_relative_to_data": {
                "private/skip-list.rkt": digest(self.support.read_bytes())}}
        (self.exp / "manifest.json").write_text(json.dumps(self.manifest))
        self.root_patch = patch.object(applier, "ROOT", self.exp)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.tmp.cleanup()

    def apply(self, **kw):
        return applier.apply(self.clone, self.target, disposable=True, **kw)

    def test_apply_idempotence_revert_exact_bytes_modes_and_support(self):
        support_before = self.support.read_bytes()
        self.assertTrue(self.apply()["changed"])
        self.assertEqual(self.target.read_bytes(), self.patched)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertFalse(self.apply()["changed"])
        self.assertTrue(self.apply(revert=True)["changed"])
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(self.apply(revert=True)["changed"])
        self.assertEqual(self.support.read_bytes(), support_before)

    def test_explicit_disposable_ack_required(self):
        with self.assertRaisesRegex(ValueError, "acknowledgement"):
            applier.apply(self.clone, self.target)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_target_tampering_refused(self):
        self.target.write_bytes(b"changed source")
        with self.assertRaisesRegex(ValueError, "preimage"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), b"changed source")

    def test_support_tampering_refused_before_mutation(self):
        self.support.write_bytes(b"changed dependency")
        with self.assertRaisesRegex(ValueError, "supporting source"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_untrusted_overlay_refused(self):
        (self.exp / "overlay/interval-map.rkt").write_bytes(b"unreviewed")
        with self.assertRaisesRegex(ValueError, "source hash"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_hardlinked_source_refused_even_when_already_patched(self):
        self.target.write_bytes(self.patched)
        other = self.base / "shared-original"
        os.link(self.target, other)
        with self.assertRaisesRegex(ValueError, "Hard-linked"):
            self.apply()
        self.assertEqual(other.read_bytes(), self.patched)

    def test_symlinked_parent_and_target_refused(self):
        alias = self.base / "runtime-alias"
        alias.symlink_to(self.clone, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            applier.apply(alias, alias / self.target.relative_to(self.clone), disposable=True)
        other = self.target.with_name("source-original.rkt")
        self.target.rename(other)
        self.target.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            self.apply()
        self.assertEqual(other.read_bytes(), self.original)

    def test_outside_and_wrong_collection_targets_refused(self):
        outside = self.base / "data/interval-map.rkt"
        outside.parent.mkdir()
        outside.write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, "inside"):
            applier.apply(self.clone, outside, disposable=True)
        wrong = self.clone / "interval-map.rkt"
        wrong.write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, "collection path"):
            applier.apply(self.clone, wrong, disposable=True)
        self.assertEqual(self.target.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
