#!/usr/bin/env python3
"""Source/shell checks plus opt-in real Racket 9.3 preference-API tests.

python3 tests/portable-memory-profile-test.py
python3 tests/portable-memory-profile-test.py --racket /official/9.3/bin/racket
No installation, GUI, network access, runtime edits or package downloads.
The native setup/launcher/observer acceptance gate is separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/memory-profile.rkt"
KEY = "plt:framework-pref:drracket:child-only-memory-limit"
RACKET = None
MIB = 1024 ** 2
SCRIPTS = ("memory-profile.rkt", "memory-profile.sh", "proof-env.sh",
           "setup-openracket.sh", "launch-openracket.sh", "launch-stock.sh")


class SourceTests(unittest.TestCase):
    def test_exact_stock_key_api_and_source_pins(self):
        text = HELPER.read_text()
        for expected in ("'drracket:child-only-memory-limit", KEY,
                         "'preferences:get", "'preferences:set",
                         "'preferences:low-level-put-preferences",
                         "(put-preferences keys values #f pref-file)",
                         "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62",
                         "59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c"):
            self.assertIn(expected, text)
        for forbidden in ("preferences:set-default", "custodian-limit-memory",
                          "racket/gui/base", "preferences:restore-defaults"):
            self.assertNotIn(forbidden, text)

    def test_freshness_reserved_before_package_directory_or_install(self):
        text = (ROOT / "scripts/setup-openracket.sh").read_text()
        self.assertLess(text.index("--reserve"), text.index('mkdir -p "$ADDON"'))
        self.assertLess(text.index("--reserve"), text.index("pkg install"))
        self.assertGreater(text.index("--initialize"), text.index("scripts/preflight.rkt"))
        self.assertIn('--initialize "$memory_grant"', text)

    def test_snapshot_and_token_are_consumed_before_api_loading(self):
        text = HELPER.read_text()
        init = text[text.index("(define (initialize"):text.index("(define (change")]
        self.assertLess(init.index('(with-state data "checking")'), init.index("(load-api pref-file)"))
        self.assertIn("(hash-ref data 'token #f) token", init)
        self.assertIn("(hash-ref data 'reservation #f) absent-snapshot", init)
        self.assertIn("(store-snapshot pref-file) absent-snapshot", init)
        reserve = text[text.index("(define (reserve"):text.index("(define (initialize")]
        self.assertLess(reserve.index("(limit-mib chosen)"), reserve.index("(make-directory profile)"))
        self.assertIn('"existing"', reserve)
        self.assertNotIn("system-type", reserve)

    def test_confinement_explicitly_accepts_self_and_directory_boundaries(self):
        text = HELPER.read_text()
        self.assertIn("(find-relative-path boundary target #:more-than-same? #f)", text)
        self.assertIn("(define-values (base name directory?) (split-path path))", text)
        self.assertIn("(not (link-exists? boundary))", text)
        self.assertIn("(not (link-exists? next))", text)

    def test_known_directory_identity_is_canonical_without_relaxing_containment(self):
        text = HELPER.read_text()
        self.assertIn("(define (physical-directory p) (path->directory-path (physical p)))", text)
        self.assertIn("(define root (physical-directory source-root))", text)
        self.assertIn("(path? base) (equal? (physical-directory base) root)", text)
        self.assertIn("(relative-path? relative)", text)
        self.assertIn("(not (memq 'up (explode-path relative)))", text)
        self.assertIn("(check-false (equal? physical-profile-base root))", text)
        self.assertIn("(check-not-false (member profile (profile-aliases)))", text)

    def test_launchers_never_write_or_reapply_memory_preference(self):
        for name in ("launch-openracket.sh", "launch-stock.sh"):
            text = (ROOT / "scripts" / name).read_text()
            for forbidden in ("memory-profile", "preferences:set", "put-preferences",
                              "child-only-memory-limit", "MEMORY_LIMIT_MIB", "--initialize"):
                self.assertNotIn(forbidden, text)
        self.assertIn('export PLTUSERHOME="$ROOT/profile-stock-preferences"',
                      (ROOT / "scripts/launch-stock.sh").read_text())

    def test_delivered_runtime_ui_and_semantics_sources_unchanged(self):
        manifest = json.loads((ROOT / "DELIVERED-BASE-CONTENTS.json").read_text())
        for name, expected in manifest.items():
            if name.startswith(("src/", "overlay/", "tool/", "vendor/", "performance/")):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_shell_syntax(self):
        for name in SCRIPTS:
            if name.endswith(".sh"):
                result = subprocess.run(["sh", "-n", str(ROOT / "scripts" / name)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


class SetupOrchestrationTests(unittest.TestCase):
    """Run the real setup shell with a logging fake executable; install nothing."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=".memory-shell-", dir=ROOT)
        self.base = Path(self.tmp.name)
        self.root = self.base / "proof with spaces"
        (self.root / "scripts").mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        self.log = self.base / "calls.jsonl"
        self.fake = self.base / "fake-racket"
        self.fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
a = sys.argv[1:]
p = pathlib.Path(os.environ['PLTUSERHOME'])
with open(os.environ['FAKE_LOG'], 'a') as out:
    out.write(json.dumps({'args': a, 'profile_exists': p.exists()}) + '\\n')
if '--reserve' in a:
    if os.environ.get('FAKE_RESERVE_FAILURE'): sys.exit(19)
    print('existing' if p.exists() else 'a' * 48)
elif '--initialize' in a:
    print(json.dumps({'status': 'initialized', 'grant': a[-1]}))
elif '-e' in a:
    s = a[a.index('-e') + 1]
    if '(version)' in s: print('9.3', end='')
    elif '(display "available")' in s: print('available', end='')
    elif 'pkg-directory "openracket-gui-lib"' in s:
        print(str(p / '.local/share/racket/9.3/pkgs/gui-lib'), end='')
    elif 'switchable-button.rkt' in s:
        print(str(p / '.local/share/racket/9.3/pkgs/gui-lib/mrlib/switchable-button.rkt'), end='')
sys.exit(0)
''')
        self.fake.chmod(0o755)
        self.env = dict(os.environ, RACKET=str(self.fake), FAKE_LOG=str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def setup(self):
        result = subprocess.run(["sh", str(self.root / "scripts/setup-openracket.sh"), "--install"],
                                env=self.env, capture_output=True, text=True, timeout=15)
        calls = [json.loads(s) for s in self.log.read_text().splitlines()]
        return result, calls

    def test_real_shell_passes_one_grant_after_preflight(self):
        result, calls = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        reserve = next(c for c in calls if "--reserve" in c["args"])
        self.assertFalse(reserve["profile_exists"])
        initialize = next(c for c in calls if "--initialize" in c["args"])
        self.assertTrue(initialize["profile_exists"])
        self.assertEqual(initialize["args"][-1], "a" * 48)
        self.assertIn("scripts/preflight.rkt", calls[-2]["args"])
        self.assertIs(initialize, calls[-1])

    def test_failed_reservation_prevents_packages_and_profile_creation(self):
        self.env["FAKE_RESERVE_FAILURE"] = "1"
        result, calls = self.setup()
        self.assertEqual(result.returncode, 19)
        self.assertFalse((self.root / "profile").exists())
        self.assertFalse(any("pkg" in c["args"] for c in calls))

    def test_repeated_setup_passes_existing_without_new_grant(self):
        self.assertEqual(self.setup()[0].returncode, 0)
        self.log.unlink()
        result, calls = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[-1]["args"][-1], "existing")


class NativeHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RACKET:
            raise unittest.SkipTest("native tests need --racket with an existing full official Racket 9.3")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=".memory-native-", dir=ROOT)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "proof with spaces"
        (self.root / "scripts").mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        self.profile = self.root / "profile"
        self.addon = self.profile / ".local/share/racket"
        self.marker = self.profile / ".openracket-memory-default.json"
        self.home = self.base / "ordinary-home"
        self.home.mkdir()
        self.env = os.environ.copy()
        for name in list(self.env):
            if name.startswith("OPENRACKET_") or name in (
                    "PLTCOLLECTS", "PLTCONFIGDIR", "PLT_COMPILED_FILE_CHECK", "DISPLAY"):
                self.env.pop(name)
        self.env.update(RACKET=RACKET, HOME=str(self.home), PLTUSERHOME=str(self.profile),
                        OPENRACKET_PROFILE=str(self.profile), PLTADDONDIR=str(self.addon),
                        PLTCOMPILEDROOTS=str(self.profile / "compiled-cache") + ":")

    def tearDown(self):
        self.tmp.cleanup()

    def run_racket(self, *args, env=None):
        return subprocess.run([RACKET, *args], env=env or self.env, capture_output=True,
                              text=True, timeout=120)

    def helper(self, *args):
        return self.run_racket(str(self.root / "scripts/memory-profile.rkt"), *args)

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def reserve(self):
        grant = self.ok(self.helper("--reserve")).stdout.strip()
        self.assertRegex(grant, r"^[a-f0-9]{48}$")
        return grant

    def initialize(self):
        return json.loads(self.ok(self.helper("--initialize", self.reserve())).stdout)

    def status(self):
        return json.loads(self.ok(self.helper("--status")).stdout)

    def pref_file(self):
        result = self.ok(self.run_racket("-e", "(display (find-system-path 'pref-file))"))
        return Path(result.stdout)

    def raw_store(self, contents):
        path = self.pref_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def raw_set(self, value):
        self.ok(self.run_racket("-e", "(require drracket/private/eval-helpers-and-pref-init "
                               "framework/preferences)(preferences:set 'drracket:child-only-memory-limit "
                               + value + ")"))

    def test_fresh_default_and_reserved_absent_snapshot(self):
        report = self.initialize()
        self.assertEqual(report["effective_limit_bytes"], 256 * MIB)
        self.assertEqual(report["persisted_limit_bytes"], 256 * MIB)
        self.assertIs(report["gui_initialized"], False)
        marker = json.loads(self.marker.read_text())
        self.assertEqual(marker["state"], "owned")
        self.assertEqual(marker["reservation"], {"store_present": False,
                                                "store_sha256": None, "store_entries": {}})
        self.assertEqual(self.status()["effective_limit_bytes"], 256 * MIB)

    def test_00_confined_self_child_and_outside_before_profile_creation(self):
        helper = self.root / "scripts/memory-profile.rkt"
        # The unit gate must not create profile/ through its own compilation.
        # Product reservation still uses the ordinary profile-first environment.
        unit_env = dict(self.env, PLTCOMPILEDROOTS=str(self.base / "unit-compiled-cache") + ":")
        result = self.ok(self.run_racket("-l", "raco", "--", "test", str(helper), env=unit_env))
        self.assertNotIn("FAILURE", result.stderr)
        self.assertNotIn("ERROR", result.stderr)
        self.assertFalse(self.profile.exists())

    def test_directory_valued_profile_environment_is_allowed(self):
        self.env["PLTUSERHOME"] = str(self.profile) + os.sep
        self.env["OPENRACKET_PROFILE"] = str(self.profile) + os.sep
        self.assertEqual(self.initialize()["effective_limit_bytes"], 256 * MIB)

    def test_existing_empty_profile_is_never_fresh(self):
        self.profile.mkdir()
        grant = self.ok(self.helper("--reserve")).stdout.strip()
        self.assertEqual(grant, "existing")
        self.ok(self.helper("--initialize", grant))
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.pref_file().exists())
        self.assertEqual(self.status()["effective_limit_bytes"], 128 * MIB)

    def test_existing_custom_and_unlimited_preferences_survive_setup(self):
        for value in (str(768 * MIB), "#f", str(256 * MIB)):
            with self.subTest(value=value):
                path = self.raw_store(f"(({KEY} {value}) (unrelated (keep me)))")
                before = path.read_bytes()
                self.assertEqual(self.ok(self.helper("--reserve")).stdout.strip(), "existing")
                self.ok(self.helper("--initialize", "existing"))
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse(self.marker.exists())

    def test_existing_store_without_key_is_preserved_byte_for_byte(self):
        path = self.raw_store("((unrelated (keep me)))")
        before = path.read_bytes()
        self.assertEqual(self.ok(self.helper("--reserve")).stdout.strip(), "existing")
        self.ok(self.helper("--initialize", "existing"))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.status()["effective_limit_bytes"], 128 * MIB)

    def test_preference_file_appearing_during_setup_consumes_grant(self):
        for contents in ("()", "((unrelated keep))", f"(({KEY} {512 * MIB}))"):
            with self.subTest(contents=contents):
                if self.profile.exists():
                    shutil.rmtree(self.profile)
                grant = self.reserve()
                path = self.raw_store(contents)
                report = json.loads(self.ok(self.helper("--initialize", grant)).stdout)
                self.assertEqual(report["status"], "preserved")
                self.assertEqual(path.read_text(), contents)
                self.assertEqual(json.loads(self.marker.read_text())["state"], "preserved")
                self.assertNotEqual(self.helper("--initialize", grant).returncode, 0)

    def test_invalid_fresh_option_does_not_create_profile(self):
        for value in ("", "0", "7", "-1", "256.0", "0256", "unlimited", "garbage"):
            with self.subTest(value=value):
                self.env["OPENRACKET_MEMORY_LIMIT_MIB"] = value
                self.assertNotEqual(self.helper("--reserve").returncode, 0)
                self.assertFalse(self.profile.exists())

    def test_fresh_optout_and_custom_are_explicit(self):
        for value in (128, 256, 512, 768):
            with self.subTest(value=value):
                if self.profile.exists():
                    shutil.rmtree(self.profile)
                self.env["OPENRACKET_MEMORY_LIMIT_MIB"] = str(value)
                report = self.initialize()
                self.assertEqual(report["effective_limit_bytes"], value * MIB)
                self.assertEqual(report["ownership_state"], "explicit")
                self.assertNotEqual(self.helper("--restore").returncode, 0)

    def test_restore_changes_only_key_and_never_reapplies(self):
        report = self.initialize()
        path = Path(report["preference_store"])
        self.raw_store(f"(({KEY} {256 * MIB}) (unrelated (keep me)))")
        restored = json.loads(self.ok(self.helper("--restore")).stdout)
        self.assertEqual(restored["effective_limit_bytes"], 128 * MIB)
        self.assertEqual(restored["ownership_state"], "restored")
        self.assertIn("(unrelated (keep me))", path.read_text())
        before = path.read_bytes()
        self.assertEqual(self.ok(self.helper("--reserve")).stdout.strip(), "existing")
        self.ok(self.helper("--initialize", "existing"))
        self.assertEqual(path.read_bytes(), before)
        self.assertNotEqual(self.helper("--restore").returncode, 0)

    def test_restore_refuses_changed_missing_and_unlimited_user_choices(self):
        for value in (str(512 * MIB), "#f", None):
            with self.subTest(value=value):
                if self.profile.exists():
                    shutil.rmtree(self.profile)
                self.initialize()
                path = self.raw_store("((unrelated keep))" if value is None
                                      else f"(({KEY} {value}) (unrelated keep))")
                before = path.read_bytes()
                self.assertNotEqual(self.helper("--restore").returncode, 0)
                self.assertEqual(path.read_bytes(), before)

    def test_explicit_same_value_relinquishes_ownership(self):
        self.initialize()
        self.ok(self.helper("--set-mib", "256"))
        self.assertEqual(self.status()["ownership_state"], "explicit")
        self.assertNotEqual(self.helper("--restore").returncode, 0)
        self.assertEqual(self.status()["effective_limit_bytes"], 256 * MIB)

    def test_stock_gui_api_custom_and_unlimited_remain_supported(self):
        self.initialize()
        self.raw_set(str(768 * MIB))
        self.assertEqual(self.status()["effective_limit_bytes"], 768 * MIB)
        self.raw_set("#f")
        self.assertIs(self.status()["effective_limit_bytes"], False)
        self.ok(self.helper("--set-mib", "128"))
        self.ok(self.helper("--unlimited"))
        self.assertIs(self.status()["effective_limit_bytes"], False)

    def test_failed_setup_never_regains_freshness(self):
        grant = self.reserve()
        # Simulate setup stopping after the initial reservation, before initialize.
        self.assertEqual(self.ok(self.helper("--reserve")).stdout.strip(), "existing")
        self.ok(self.helper("--initialize", "existing"))
        self.assertFalse(self.pref_file().exists())
        self.assertEqual(json.loads(self.marker.read_text())["token"], grant)

    def test_failed_initialization_consumes_grant(self):
        grant = self.reserve()
        # Break only a temporary helper copy's expected hash, not installed code.
        helper = self.root / "scripts/memory-profile.rkt"
        helper.write_text(helper.read_text().replace(
            "e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62", "0" * 64))
        self.assertNotEqual(self.helper("--initialize", grant).returncode, 0)
        self.assertEqual(json.loads(self.marker.read_text())["state"], "checking")
        self.assertFalse(self.pref_file().exists())
        shutil.copy2(HELPER, helper)
        self.assertNotEqual(self.helper("--initialize", grant).returncode, 0)

    def test_helper_rejects_foreign_profile_and_symlink_preferences(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        self.env["PLTUSERHOME"] = str(foreign)
        self.assertNotEqual(self.helper("--reserve").returncode, 0)
        self.assertEqual(list(foreign.iterdir()), [])
        self.env["PLTUSERHOME"] = str(self.profile)
        self.profile.symlink_to(foreign, target_is_directory=True)
        self.assertNotEqual(self.helper("--reserve").returncode, 0)
        self.profile.unlink()
        self.initialize()
        path = self.pref_file()
        saved = path.read_bytes()
        path.unlink()
        target = foreign / "preferences.rktd"
        target.write_bytes(saved)
        path.symlink_to(target)
        self.assertNotEqual(self.helper("--set-mib", "512").returncode, 0)
        self.assertEqual(target.read_bytes(), saved)

    def test_source_root_alias_is_allowed_but_profile_child_alias_is_not(self):
        alias = self.base / "source-root-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.env.update(PLTUSERHOME=str(alias / "profile"),
                        OPENRACKET_PROFILE=str(alias / "profile"),
                        PLTADDONDIR=str(alias / "profile/.local/share/racket"))
        helper = str(alias / "scripts/memory-profile.rkt")
        grant = self.ok(self.run_racket(helper, "--reserve")).stdout.strip()
        report = json.loads(self.ok(self.run_racket(helper, "--initialize", grant)).stdout)
        self.assertEqual(report["effective_limit_bytes"], 256 * MIB)
        self.assertEqual(Path(report["profile"]), self.profile)
        path = self.pref_file()
        real_path = path.resolve()
        outside = self.base / "outside-pref-directory"
        real_path.parent.rename(outside)
        real_path.parent.symlink_to(outside, target_is_directory=True)
        before = (outside / real_path.name).read_bytes()
        self.assertNotEqual(self.run_racket(helper, "--set-mib", "512").returncode, 0)
        self.assertEqual((outside / real_path.name).read_bytes(), before)

    def test_stock_write_lock_failure_preserves_store_and_is_visible(self):
        self.initialize()
        mode = self.ok(self.run_racket("-e", "(require racket/file)(display (preferences-lock-file-mode))")).stdout
        if mode != "exists":
            self.skipTest("existence-based preference lock fixture applies to Mac/Unix")
        path = self.pref_file()
        before = path.read_bytes()
        lock = Path(self.ok(self.run_racket("-e", "(require racket/file)"
                                           "(display (make-lock-file-name (find-system-path 'pref-file)))")).stdout)
        lock.write_text("held by fixture")
        result = self.helper("--set-mib", "512")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lock", result.stderr.lower())
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(self.marker.read_text())["state"], "explicit")
        self.assertEqual(list(path.parent.glob("TMPPREF*")), [])

    def test_fresh_stock_comparison_retains_128(self):
        self.initialize()
        env = dict(self.env, PLTUSERHOME=str(self.root / "profile-stock-preferences"))
        result = self.ok(self.run_racket("-e", "(require drracket/private/eval-helpers-and-pref-init "
                                        "framework/preferences)(display (preferences:get "
                                        "'drracket:child-only-memory-limit))", env=env))
        self.assertEqual(result.stdout, str(128 * MIB))
        self.assertEqual(self.status()["effective_limit_bytes"], 256 * MIB)

    def test_supported_wrapper_and_native_pure_unit_tests(self):
        self.initialize()
        result = subprocess.run(["sh", str(self.root / "scripts/memory-profile.sh"), "--set-mib", "384"],
                                env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(json.loads(self.ok(result).stdout)["effective_limit_bytes"], 384 * MIB)
        result = self.ok(self.run_racket("-l", "raco", "--", "test", str(HELPER)))
        self.assertNotIn("FAILURE", result.stderr)
        self.assertNotIn("ERROR", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--racket", help="existing full official Racket 9.3 executable")
    options, remaining = parser.parse_known_args()
    if options.racket:
        RACKET = str(Path(options.racket).resolve(strict=True))
    unittest.main(argv=[sys.argv[0], *remaining])
