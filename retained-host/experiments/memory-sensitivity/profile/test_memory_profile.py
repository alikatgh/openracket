#!/usr/bin/env python3
"""Native helper tests. Uses an existing full Racket 9.3 runtime; never installs.

python3 test_memory_profile.py --racket /clone/bin/racket --runtime-root /clone
Without those arguments only source-contract tests run; native tests are skipped.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "memory-profile.rkt"
RACKET = None
RUNTIME = None
PINS = {
    "eval_helpers": "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62",
    "framework_preferences": "59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c",
}


class SourceContractTests(unittest.TestCase):
    def test_fixed_value_allowlist_and_source_pins(self):
        text = HELPER.read_text()
        self.assertIn("'(\"128\" \"256\" \"512\")", text)
        for pin in PINS.values():
            self.assertIn(pin, text)

    def test_only_original_registered_setter(self):
        text = HELPER.read_text()
        self.assertIn("(dynamic-require eval-path #f)", text)
        self.assertIn("(dynamic-require framework-path 'preferences:set)", text)
        self.assertEqual(text.count("(set preference-key selected)"), 1)
        self.assertNotIn("(preferences:set-default", text)
        self.assertNotIn("(put-preferences", text)
        self.assertNotIn("(custodian-limit-memory", text)
        self.assertNotIn("racket/gui/base", text)


class NativeHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RACKET or not RUNTIME:
            raise unittest.SkipTest("Existing full Racket 9.3 runtime was not supplied")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="openracket-memory-profile-")
        self.base = Path(self.temp.name)
        self.home = self.base / "profile"
        self.addon = self.base / "addon"
        self.home.mkdir()
        self.addon.mkdir()
        self.output = self.base / "report.json"
        self.env = os.environ.copy()
        for name in list(self.env):
            if name.startswith("OPENRACKET_") or name in (
                    "PLTCOLLECTS", "PLTCONFIGDIR", "PLT_COMPILED_FILE_CHECK", "DISPLAY"):
                self.env.pop(name)
        self.env.update(HOME=str(self.home), PLTUSERHOME=str(self.home), PLTADDONDIR=str(self.addon))

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, limit="256", runtime=None):
        result = subprocess.run(
            [RACKET, str(HELPER), "--limit-mib", limit,
             "--output", str(self.output), "--runtime-root", runtime or RUNTIME],
            env=self.env, capture_output=True, text=True, timeout=90)
        report = json.loads(self.output.read_text()) if self.output.exists() else None
        return result, report

    def check_refused(self, result, report):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIsNotNone(report, result.stderr)
        self.assertEqual(report["status"], "refused")
        self.assertFalse(report["preference_write_attempted"])

    def test_real_values_128_256_512(self):
        for limit in (128, 256, 512):
            with self.subTest(limit=limit):
                # Every arm gets a separate never-used profile and addon directory.
                home = self.base / f"profile-{limit}"
                addon = self.base / f"addon-{limit}"
                home.mkdir()
                addon.mkdir()
                self.env.update(HOME=str(home), PLTUSERHOME=str(home), PLTADDONDIR=str(addon))
                self.output = self.base / f"report-{limit}.json"
                result, report = self.invoke(str(limit))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(report["status"], "verified")
                self.assertEqual(report["original_default_limit_bytes"], 128 * 1024**2)
                for field in ("expected_limit_bytes", "selected_limit_bytes",
                              "readback_limit_bytes", "persisted_limit_bytes"):
                    self.assertEqual(report[field], limit * 1024**2)
                self.assertTrue(report["profile_was_empty"])
                self.assertTrue(report["only_expected_preference_changed"])
                self.assertFalse(report["gui_initialized"])
                self.assertEqual(report["disk_key_count_before"], 0)
                self.assertEqual(report["disk_key_count_after"], 1)
                self.assertEqual(len(report["one_key_delta"]), 1)
                store = Path(report["preference_store_path"])
                self.assertTrue(store.is_relative_to(home.resolve()))
                self.assertEqual(hashlib.sha256(store.read_bytes()).hexdigest(),
                                 report["preference_store_sha256"])
                for name, pin in PINS.items():
                    source = report["sources"][name]
                    self.assertEqual(source["sha256"], pin)
                    self.assertEqual(source["sha256"],
                                     hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest())
                    self.assertTrue(Path(source["path"]).is_relative_to(Path(RUNTIME).resolve()))
                # Independent fresh process: no framework cache, no preference setter.
                expression = (
                    "(begin (require racket/file json) "
                    "(write-json (get-preference "
                    "'plt:framework-pref:drracket:child-only-memory-limit "
                    "(lambda () #f) #t "
                    "(vector-ref (current-command-line-arguments) 0))))")
                disk = subprocess.run([RACKET, "-e", expression, "--", str(store)],
                                      env=self.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(disk.returncode, 0, disk.stderr)
                self.assertEqual(json.loads(disk.stdout), limit * 1024**2)

    def test_invalid_value_refused_before_mutation(self):
        for limit in ("0", "127", "129", "1024", "256.0", "0256", "#f"):
            with self.subTest(limit=limit):
                self.output = self.base / f"invalid-{limit}.json"
                self.check_refused(*self.invoke(limit))
                self.assertEqual(list(self.home.iterdir()), [])
                self.assertEqual(list(self.addon.iterdir()), [])

    def test_nonempty_profile_preserved(self):
        sentinel = self.home / "untouched"
        sentinel.write_bytes(b"preserve unrelated profile bytes\n")
        self.check_refused(*self.invoke())
        self.assertEqual(sentinel.read_bytes(), b"preserve unrelated profile bytes\n")
        self.assertEqual(list(self.home.iterdir()), [sentinel])

    def test_nonempty_addon_refused(self):
        (self.addon / "untouched").write_text("keep")
        self.check_refused(*self.invoke())
        self.assertEqual(list(self.home.iterdir()), [])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Unix legacy HOME fallback")
    def test_legacy_home_fallback_refused_before_read_or_write(self):
        external = self.base / "separate-home"
        legacy_dir = external / ".plt-scheme"
        legacy_dir.mkdir(parents=True)
        legacy = legacy_dir / "plt-prefs.ss"
        contents = b"((unrelated-secret legacy-value))\n"
        legacy.write_bytes(contents)
        self.env["HOME"] = str(external)
        result, report = self.invoke()
        self.check_refused(result, report)
        self.assertIn("legacy fallback", report["error"])
        self.assertEqual(legacy.read_bytes(), contents)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_missing_profile_variable_refused(self):
        self.env.pop("PLTUSERHOME")
        self.check_refused(*self.invoke())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_overlapping_profiles_refused(self):
        self.env["PLTADDONDIR"] = str(self.home)
        self.check_refused(*self.invoke())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_wrong_runtime_root_refused(self):
        fake = self.base / "not-runtime"
        fake.mkdir()
        self.check_refused(*self.invoke(runtime=str(fake)))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_external_collection_source_refused(self):
        overlay = self.base / "overlay"
        framework = overlay / "framework"
        framework.mkdir(parents=True)
        # Not executed: preflight must refuse the out-of-runtime source first.
        (framework / "preferences.rkt").write_text(
            '#lang racket/base\n(error "UNTRUSTED SOURCE EXECUTED")\n')
        self.env["PLTCOLLECTS"] = str(overlay) + os.pathsep
        result, report = self.invoke()
        self.check_refused(result, report)
        self.assertEqual(report["stage"], "source-pins")
        self.assertIn("outside runtime root", report["error"])
        self.assertNotIn("UNTRUSTED SOURCE EXECUTED", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_reused_profile_refused_without_store_change(self):
        result, report = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        store = Path(report["preference_store_path"])
        original = store.read_bytes()
        self.output = self.base / "second.json"
        self.check_refused(*self.invoke("512"))
        self.assertEqual(store.read_bytes(), original)

    def test_existing_output_is_not_overwritten(self):
        self.output.write_text("keep prior report")
        result = subprocess.run(
            [RACKET, str(HELPER), "--limit-mib", "256", "--output", str(self.output),
             "--runtime-root", RUNTIME], env=self.env, capture_output=True, text=True, timeout=90)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "keep prior report")
        self.assertEqual(list(self.home.iterdir()), [])

    def test_native_unit_source_pin_store_and_delta_checks(self):
        # Tests make/tamper their own temporary copies, never runtime sources.
        expression = f'(dynamic-require \'(submod (file {json.dumps(str(HELPER))}) test) #f)'
        result = subprocess.run([RACKET, "-e", expression], env=self.env,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAILURE", result.stderr)
        self.assertNotIn("ERROR", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--racket")
    parser.add_argument("--runtime-root")
    options, rest = parser.parse_known_args()
    if bool(options.racket) != bool(options.runtime_root):
        parser.error("--racket and --runtime-root must be supplied together")
    if options.racket:
        RACKET = str(Path(options.racket).resolve(strict=True))
        RUNTIME = str(Path(options.runtime_root).resolve(strict=True))
    unittest.main(argv=[sys.argv[0], *rest])
