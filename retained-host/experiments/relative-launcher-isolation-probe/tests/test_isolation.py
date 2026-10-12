"""Disposable filesystem and mocked-native tests; never execute a native image."""
import copy
import json
import os
from pathlib import Path
import plistlib
import shutil
import tempfile
import unittest
from unittest import mock

from test_source import fake_macho, image_snapshot, s


class LauncherIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve(strict=True)
        self.runtime = self.base / "Original Runtime λ's"
        for rel in ("collects/racket", "etc", "share/pkgs/drracket", "doc", "lib",
                    "bin", "DrRacket.app/Contents/MacOS", "lib/GRacket.app/Contents/MacOS",
                    "PLT Games.app/Contents", "other/DrRacket.app/Contents"):
            (self.runtime / rel).mkdir(parents=True, exist_ok=True)
        files = {"bin/racket": fake_macho(), "lib/core.dylib": fake_macho(),
                 "lib/GRacket.app/Contents/MacOS/GRacket": fake_macho(),
                 "DrRacket.app/Contents/MacOS/DrRacket": fake_macho(),
                 "collects/racket/base.rkt": b"#lang racket/base\n",
                 "share/pkgs/drracket/main.rkt": b"#lang racket/base\n",
                 "doc/LICENSE.txt": b"fixture license\n", "other/DrRacket.app/keep": b"keep"}
        for rel, data in files.items():
            (self.runtime / rel).write_bytes(data)
        (self.runtime / "bin/racket").chmod(0o755)
        self.write_plist("DrRacket.app", {"CFBundleIdentifier": "org.racket-lang.DrRacket",
                                         "CFBundleDocumentTypes": [], "UTExportedTypeDeclarations": []})
        self.write_plist("lib/GRacket.app", {"CFBundleIdentifier": "org.racket-lang.GRacketCS"})
        self.write_plist("PLT Games.app", {"CFBundleIdentifier": "org.racket-lang.PLT Games"})
        self.write_plist("other/DrRacket.app", {})
        (self.runtime / "lib/alias.dylib").symlink_to("core.dylib")
        self.before = s.inventory(self.runtime)
        self.copied = self.base / "Copied Runtime"

    def tearDown(self):
        self.temp.cleanup()

    def write_plist(self, app, data):
        (self.runtime / app / "Contents/Info.plist").write_bytes(plistlib.dumps(data))

    def copy_runtime(self):
        return s.copy_isolated_runtime(self.runtime, self.copied, s.inventory(self.runtime))

    def assemble(self, outer_claims=None):
        baseline = {"schema": 1, "status": "observed", "default_handler": None, "defaults_changed": False}
        work = self.base / "work"

        def simulate_generator(command, profile, label):
            if label == "generate":
                app = Path(command[-1])
                (app / "Contents/MacOS").mkdir(parents=True)
                (app / "Contents/Resources").mkdir()
                (app / "Contents/MacOS/Path Probe").write_bytes(fake_macho())
                (app / "Contents/Info.plist").write_bytes(plistlib.dumps(outer_claims or {}))
            return {"pid": 123, "stdout": "", "stderr": ""}

        with mock.patch.object(s, "native_only"), mock.patch.object(s, "handler", return_value=baseline), \
             mock.patch.object(s, "bounded_run", side_effect=simulate_generator), \
             mock.patch.object(s.subprocess, "Popen") as popen:
            result = s.build(self.runtime, work, s.inventory_digest(s.inventory(self.runtime)))
            popen.assert_not_called()
        return work, result

    def assert_prelaunch_refusal(self, work, pattern):
        with mock.patch.object(s, "native_only"), mock.patch.object(s, "handler") as handler, \
             mock.patch.object(s, "bounded_run") as run, mock.patch.object(s.subprocess, "Popen") as popen:
            with self.assertRaisesRegex((s.Refusal, OSError), pattern):
                s._run_probe(work / "build.json", self.base / "Relocated λ's Probe.app")
            handler.assert_not_called(); run.assert_not_called(); popen.assert_not_called()
        self.assertFalse((work / "run-profile-0").exists())

    def test_exact_retained_tree_and_complete_excluded_manifest(self):
        plan = self.copy_runtime()
        expected = {k: v for k, v in self.before.items()
                    if k == "DrRacket.app" or k.startswith("DrRacket.app/")}
        self.assertEqual(plan["excluded_entries"], expected)
        self.assertEqual(plan["excluded_entry_count"], len(expected))
        self.assertEqual(plan["original_entry_count"], plan["excluded_entry_count"] + plan["retained_entry_count"])
        s.verify_isolated_runtime(self.copied, self.before, plan)
        self.assertFalse((self.copied / "DrRacket.app").exists())
        self.assertEqual(s.inventory(self.runtime), self.before)
        for rel in ("lib/GRacket.app/Contents/Info.plist", "bin/racket", "doc/LICENSE.txt",
                    "collects/racket/base.rkt", "share/pkgs/drracket/main.rkt", "lib/core.dylib",
                    "PLT Games.app/Contents/Info.plist", "other/DrRacket.app/keep"):
            self.assertEqual((self.copied / rel).read_bytes(), (self.runtime / rel).read_bytes())
        self.assertEqual(os.readlink(self.copied / "lib/alias.dylib"), "core.dylib")
        s.refuse_claims(s.nested_claims(self.copied))
        self.assertEqual(s.check_dependency_paths(self.copied, s.macho_inventory(self.copied)), [])

    def test_missing_exact_launcher_refused(self):
        (self.runtime / "DrRacket.app").rename(self.runtime / "DrRacket.APP")
        with self.assertRaisesRegex(s.Refusal, "exact top-level"):
            self.copy_runtime()
        self.assertFalse(self.copied.exists())

    def test_conflicting_top_level_case_refused(self):
        # A case-insensitive disk cannot hold both spellings. Exercise the
        # inventory guard with real entry metadata and a synthetic second key.
        for spelling in ("drracket.APP", "DRRACKET.app", "DrRacket.APP"):
            with self.subTest(spelling=spelling):
                original = s.inventory(self.runtime)
                conflicting = copy.deepcopy(original)
                conflicting[spelling] = copy.deepcopy(original["DrRacket.app"])
                witness = copy.deepcopy(conflicting)
                with self.assertRaisesRegex(s.Refusal, "conflicting top-level DrRacket.app spelling"):
                    s.runtime_copy_plan(conflicting)
                self.assertEqual(conflicting, witness)
                self.assertEqual(s.inventory(self.runtime), original)
        self.assertFalse(self.copied.exists())

    def test_conflicting_case_fixture_needs_no_case_sensitive_disk(self):
        conflicting = copy.deepcopy(s.inventory(self.runtime))
        conflicting["drracket.APP"] = copy.deepcopy(conflicting["DrRacket.app"])
        # Explicit collision model, not a claim about this machine's disk:
        # any attempted fixture mkdir fails, as a second spelling did on macOS.
        with mock.patch.object(Path, "mkdir", side_effect=FileExistsError("case-insensitive name collision")) as mkdir, \
             mock.patch.object(s, "inventory", return_value=conflicting), \
             mock.patch.object(s.shutil, "copytree") as copytree:
            with self.assertRaisesRegex(s.Refusal, "conflicting top-level DrRacket.app spelling"):
                s.copy_isolated_runtime(self.runtime, self.copied, conflicting)
            mkdir.assert_not_called()
            copytree.assert_not_called()
        self.assertEqual(s.inventory(self.runtime), self.before)
        self.assertFalse(self.copied.exists())

    def test_launcher_symlink_refused(self):
        (self.runtime / "DrRacket.app").rename(self.runtime / "payload")
        (self.runtime / "DrRacket.app").symlink_to("payload", target_is_directory=True)
        with self.assertRaisesRegex(s.Refusal, "real directory"):
            self.copy_runtime()

    def test_retained_link_to_excluded_launcher_refused(self):
        (self.runtime / "alias.app").symlink_to("DrRacket.app", target_is_directory=True)
        with self.assertRaisesRegex(s.Refusal, "depends on excluded"):
            self.copy_runtime()
        self.assertFalse(self.copied.exists())

    def test_original_and_conflicting_destination_paths_refused(self):
        occupied = self.base / "occupied"; occupied.mkdir()
        alias = self.base / "Original alias"; alias.symlink_to(self.runtime.name, target_is_directory=True)
        for destination in (self.runtime, self.runtime / "copy", alias / "copy", occupied,
                            s.HERE / "forbidden-fixture-output"):
            with self.subTest(destination=destination):
                with self.assertRaises(s.Refusal):
                    s.copy_isolated_runtime(self.runtime, destination, self.before)
        self.assertEqual(s.inventory(self.runtime), self.before)

    def test_changed_original_witness_refused_before_copy(self):
        (self.runtime / "doc/LICENSE.txt").write_text("changed")
        with self.assertRaisesRegex(s.Refusal, "changed before copy"):
            s.copy_isolated_runtime(self.runtime, self.copied, self.before)
        self.assertFalse(self.copied.exists())

    def test_changed_retained_file_and_manifest_refused(self):
        plan = self.copy_runtime()
        damaged = copy.deepcopy(plan)
        damaged["excluded_entries"].pop("DrRacket.app/Contents/Info.plist")
        with self.assertRaisesRegex(s.Refusal, "exclusion manifest"):
            s.verify_isolated_runtime(self.copied, self.before, damaged)
        (self.copied / "doc/LICENSE.txt").write_text("changed")
        with self.assertRaisesRegex(s.Refusal, "copied runtime differs"):
            s.verify_isolated_runtime(self.copied, self.before, plan)

    def test_restored_excluded_launcher_refused(self):
        plan = self.copy_runtime()
        shutil.copytree(self.runtime / "DrRacket.app", self.copied / "DrRacket.app")
        with self.assertRaisesRegex(s.Refusal, "copied runtime differs"):
            s.verify_isolated_runtime(self.copied, self.before, plan)

    def test_other_nested_claims_preserved_and_block_launch(self):
        self.write_plist("other/DrRacket.app", {"UTImportedTypeDeclarations": []})
        work, result = self.assemble()
        self.assertTrue(result["native_launch_blocked_by_declarations"])
        self.assert_prelaunch_refusal(work, "document/UTI declarations")

    def test_generated_outer_claims_refused_without_stripping(self):
        with self.assertRaisesRegex(s.Refusal, "generated outer skeleton declares"):
            self.assemble({"CFBundleDocumentTypes": []})
        data = plistlib.loads((self.base / "work/Path Probe.app/Contents/Info.plist").read_bytes())
        self.assertIn("CFBundleDocumentTypes", data)
        self.assertEqual(s.inventory(self.runtime), self.before)

    def test_mixed_case_other_claims_block_launch(self):
        self.write_plist("PLT Games.app", {"UTExportedTypeDeclarations": []})
        p = self.runtime / "PLT Games.app/Contents/Info.plist"
        p.rename(p.with_name("info.PLIST"))
        work, result = self.assemble()
        self.assertTrue(result["native_launch_blocked_by_declarations"])
        self.assert_prelaunch_refusal(work, "document/UTI declarations")

    def test_retained_dependency_into_exclusion_blocks_assembly(self):
        (self.runtime / "lib/core.dylib").write_bytes(fake_macho(["@loader_path/../DrRacket.app/Contents/MacOS/DrRacket"]))
        before = s.inventory(self.runtime)
        with self.assertRaises(FileNotFoundError):
            self.assemble()
        self.assertEqual(s.inventory(self.runtime), before)
        witness = json.loads((self.base / "work/protected-input-witness.json").read_text())
        self.assertTrue(witness["original_runtime_unchanged"])
        self.assertTrue(witness["source_unchanged"])

    def test_unresolved_loader_context_blocks_all_native_queries(self):
        (self.runtime / "lib/core.dylib").write_bytes(fake_macho(["@rpath/unproved.dylib"]))
        work, result = self.assemble()
        self.assertTrue(result["native_launch_blocked_by_loader_context"])
        self.assert_prelaunch_refusal(work, "unresolved loader references")

    def test_changed_original_after_assembly_blocks_launch(self):
        work, result = self.assemble()
        (self.runtime / "doc/LICENSE.txt").write_text("changed")
        self.assert_prelaunch_refusal(work, "original runtime changed since assembly")

    def test_fresh_dependency_audit_does_not_trust_cached_rows(self):
        work, result = self.assemble()
        app = Path(result["bundle"])
        (app / "Contents/MacOS/Other").write_bytes(fake_macho(["@rpath/unknown"]))
        self.assert_prelaunch_refusal(work, "unresolved loader references")

    def test_directory_loader_dependency_refused(self):
        (self.runtime / "lib/core.dylib").write_bytes(fake_macho(["@loader_path/GRacket.app"]))
        with self.assertRaisesRegex(s.Refusal, "loader dependency is not a file"):
            self.assemble()

    def test_manifest_tampering_blocks_all_native_queries(self):
        work, result = self.assemble()
        path = work / "runtime-copy-plan.json"
        plan = json.loads(path.read_text())
        plan["excluded_entries"].pop("DrRacket.app/Contents/Info.plist")
        path.write_text(json.dumps(plan))
        self.assert_prelaunch_refusal(work, "exclusion manifest differs")

    def test_occupied_or_original_relocation_refused(self):
        work, result = self.assemble()
        occupied = self.base / "Occupied.app"; occupied.mkdir()
        for destination in (occupied, self.runtime / "Do Not Move.app"):
            with self.subTest(destination=destination), mock.patch.object(s, "native_only"), \
                 mock.patch.object(s, "handler") as handler, mock.patch.object(s, "bounded_run") as run:
                with self.assertRaises(s.Refusal):
                    s._run_probe(work / "build.json", destination)
                handler.assert_not_called(); run.assert_not_called()
        self.assertTrue(Path(result["bundle"]).exists())
        self.assertEqual(s.inventory(self.runtime), self.before)

    def test_second_location_is_reaudited_before_query(self):
        work, result = self.assemble()
        destination = self.base / "Relocated λ's Probe.app"
        baseline = result["handler_baseline"]
        real_rename = Path.rename

        def fake_probe(command, profile, label):
            app = Path(command[0]).parents[2]
            report = {"modules": {}, "paths": {key: {"sha256": False} for key in
                       ("config_file", "links_file", "package_database")},
                      "loaded_images": [str(app / "Contents/MacOS/ProbeNative")],
                      "child": {"loaded_images": [str(app / "Contents/Resources/runtime/bin/racket")]}}
            for observed in [report, report["child"]]:
                observed["loaded_image_snapshot"] = image_snapshot(observed["loaded_images"])
            (profile / "result.json").write_text(json.dumps(report))
            return {"pid": 123, "stdout": "", "stderr": ""}

        def rename_with_unexpected_claim(path, target):
            value = real_rename(path, target)
            (value / "Contents/Info.plist").write_bytes(plistlib.dumps({"UTImportedTypeDeclarations": []}))
            return value

        with mock.patch.object(s, "native_only"), mock.patch.object(s, "handler", return_value=baseline) as handler, \
             mock.patch.object(s, "bounded_run", side_effect=fake_probe) as run, \
             mock.patch.object(s, "validate_report", return_value={"status": "mock-only"}), \
             mock.patch.object(Path, "rename", rename_with_unexpected_claim):
            with self.assertRaisesRegex(s.Refusal, "document/UTI declarations"):
                s._run_probe(work / "build.json", destination)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(handler.call_count, 2)
        self.assertTrue(destination.exists())
        self.assertFalse((work / "run-profile-1").exists())
        self.assertEqual(s.inventory(self.runtime), self.before)

    def test_successful_mock_assembly_preserves_all_witnesses(self):
        work, result = self.assemble()
        self.assertFalse(result["native_launch_blocked_by_declarations"])
        self.assertFalse(result["native_launch_blocked_by_loader_context"])
        self.assertEqual(result["status"], "assembled-not-launched")
        self.assertEqual(s.inventory(self.runtime), self.before)
        plan = json.loads((work / "runtime-copy-plan.json").read_text())
        s.verify_isolated_runtime(Path(result["bundle"]) / "Contents/Resources/runtime", self.before, plan)
        witness = json.loads((work / "protected-input-witness.json").read_text())
        self.assertTrue(witness["original_runtime_unchanged"])
        self.assertTrue(witness["source_unchanged"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
