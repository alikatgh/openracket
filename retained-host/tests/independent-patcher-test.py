#!/usr/bin/env python3
"""Independent, destructive-input tests in temporary copies, never the installed profile."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class IndependentPatchIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="openracket-patch-audit-")
        self.root = Path(self.tmp.name)
        for name in ("scripts", "src", "vendor", "overlay", "reports", "artifacts"):
            (self.root / name).mkdir()
        for name in ("prepare-overlay.py", "apply-overlay.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        for name in ("switchable-button-v9.3.rkt", "upstream-sha256.txt"):
            shutil.copyfile(ROOT / "vendor" / name, self.root / "vendor" / name)
        shutil.copyfile(ROOT / "src/paint.rkt", self.root / "src/paint.rkt")
        self.run_script("prepare-overlay.py", expect_success=True)
        self.target = self.root / "profile/.local/share/racket/9.3/pkgs/gui-lib/mrlib/switchable-button.rkt"
        self.target.parent.mkdir(parents=True)
        (self.target.parent / "private").mkdir()
        shutil.copyfile(self.root / "vendor/switchable-button-v9.3.rkt", self.target)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, script, *args, expect_success=False):
        result = subprocess.run(["python3", str(self.root / "scripts" / script), *args], text=True, capture_output=True)
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_pristine_apply_then_revert_is_byte_exact(self):
        original = self.target.read_bytes()
        self.run_script("apply-overlay.py", expect_success=True)
        self.assertEqual(self.target.read_bytes(), (self.root / "overlay/mrlib/switchable-button.rkt").read_bytes())
        self.run_script("apply-overlay.py", "--revert", expect_success=True)
        self.assertEqual(self.target.read_bytes(), original)

    def test_apply_rejects_unrelated_target_without_changes(self):
        self.target.write_bytes(b"unrelated target\n")
        before = self.target.read_bytes()
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), before)

    def test_prepare_rejects_byte_different_crlf_source(self):
        source = self.root / "vendor/crlf.rkt"
        source.write_bytes((self.root / "vendor/switchable-button-v9.3.rkt").read_bytes().replace(b"\n", b"\r\n"))
        before = (self.root / "overlay/mrlib/switchable-button.rkt").read_bytes()
        result = self.run_script("prepare-overlay.py", "--source", str(source))
        self.assertNotEqual(result.returncode, 0, "Exact-byte source pin accepted CRLF-transformed bytes")
        self.assertEqual((self.root / "overlay/mrlib/switchable-button.rkt").read_bytes(), before)

    def test_apply_rejects_tampered_overlay_without_changes(self):
        overlay = self.root / "overlay/mrlib/switchable-button.rkt"
        overlay.write_bytes(overlay.read_bytes() + b"\n; unreviewed payload\n")
        before = self.target.read_bytes()
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0, "Installed unverified overlay despite manifest mismatch")
        self.assertEqual(self.target.read_bytes(), before)

    def test_revert_rejects_tampered_vendor_without_changes(self):
        self.run_script("apply-overlay.py", expect_success=True)
        vendor = self.root / "vendor/switchable-button-v9.3.rkt"
        vendor.write_bytes(vendor.read_bytes() + b"\n; not pristine\n")
        before = self.target.read_bytes()
        result = self.run_script("apply-overlay.py", "--revert")
        self.assertNotEqual(result.returncode, 0, "Revert installed unverified vendor bytes")
        self.assertEqual(self.target.read_bytes(), before)

    def test_target_symlink_escape_is_refused(self):
        outside = self.root / "unrelated-installation.rkt"
        outside.write_bytes(self.target.read_bytes())
        before = outside.read_bytes()
        self.target.unlink()
        self.target.symlink_to(outside)
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_bytes(), before)

    def test_profile_root_symlink_is_refused(self):
        profile = self.root / "profile"
        outside = self.root / "unrelated-profile"
        profile.rename(outside)
        profile.symlink_to(outside, target_is_directory=True)
        escaped_target = outside / self.target.relative_to(profile)
        before = escaped_target.read_bytes()
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0, "Resolved profile symlink redefined the isolation boundary")
        self.assertEqual(escaped_target.read_bytes(), before)

    def test_apply_rejects_tampered_painter_without_changes(self):
        painter = self.root / "src/paint.rkt"
        painter.write_bytes(painter.read_bytes() + b"\n; unreviewed painter\n")
        before = self.target.read_bytes()
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), before)

    def test_missing_target_does_not_create_runtime(self):
        self.target.unlink()
        result = self.run_script("apply-overlay.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

if __name__ == "__main__":
    unittest.main(verbosity=2)
