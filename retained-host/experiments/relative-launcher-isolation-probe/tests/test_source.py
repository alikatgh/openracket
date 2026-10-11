"""Portable tests only. Synthetic files are not a Racket/native execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("supervise", ROOT / "supervise.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fake_macho(deps=(), rpaths=()):
    commands = []
    for cmd, values in [(0xC, deps), (0x8000001C, rpaths)]:
        for value in values:
            data = value.encode() + b"\0"
            size = 12 + len(data)
            size = (size + 7) // 8 * 8
            commands.append(struct.pack("<III", cmd, size, 12) + data + bytes(size - 12 - len(data)))
    payload = b"".join(commands)
    return struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 2, len(commands), len(payload), 0, 0) + payload


class Portable(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve(strict=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_destination_with_unicode_spaces_apostrophe(self):
        p = self.base / "Moved Unicode λ's probe.app"
        self.assertEqual(s.fresh_leaf(p, ".app"), p)

    def test_new_destination_canonicalizes_aliased_parent(self):
        parent = self.base / "Real parent"; parent.mkdir()
        alias = self.base / "Parent alias"; alias.symlink_to(parent.name, target_is_directory=True)
        p = alias / "Moved Unicode λ's probe.app"
        expected = parent / p.name
        self.assertNotEqual(p, expected)
        self.assertEqual(s.fresh_leaf(p, ".app"), expected)
        self.assertFalse(p.exists())
        self.assertFalse(expected.exists())

    def test_existing_destination_alias_refused(self):
        target = self.base / "Existing.app"; target.mkdir()
        alias = self.base / "Alias.app"; alias.symlink_to(target.name, target_is_directory=True)
        with self.assertRaisesRegex(s.Refusal, "refusing occupied output"):
            s.fresh_leaf(alias, ".app")

    def test_occupied_destination_refused(self):
        p = self.base / "App.app"
        p.mkdir()
        with self.assertRaises(s.Refusal): s.fresh_leaf(p, ".app")

    def test_dangling_destination_refused(self):
        p = self.base / "App.app"
        p.symlink_to("missing")
        with self.assertRaises(s.Refusal): s.fresh_leaf(p, ".app")

    def test_relative_destination_refused(self):
        with self.assertRaises(s.Refusal): s.fresh_leaf(Path("App.app"), ".app")

    def test_sibling_prefix_not_contained(self):
        self.assertFalse(s.inside(self.base / "runtime-other", self.base / "runtime"))

    def test_absolute_internal_symlink_refused(self):
        root = self.base / "root"; root.mkdir()
        (root / "x").write_text("x")
        (root / "link").symlink_to(root / "x")
        with self.assertRaises(s.Refusal): s.inventory(root)

    def test_relative_escaping_symlink_refused(self):
        root = self.base / "root"; root.mkdir()
        (self.base / "x").write_text("x")
        (root / "link").symlink_to("../x")
        with self.assertRaises(s.Refusal): s.inventory(root)

    def test_relocatable_internal_framework_symlink(self):
        root = self.base / "root"; root.mkdir()
        (root / "x").write_text("x")
        (root / "link").symlink_to("x")
        self.assertEqual(s.inventory(root)["link"]["target"], "x")

    def test_inventory_detects_bytes_modes_times(self):
        root = self.base / "root"; root.mkdir()
        p = root / "x"; p.write_text("x")
        before = s.inventory(root)
        p.chmod(0o600)
        self.assertNotEqual(before, s.inventory(root))
        p.write_text("y")
        self.assertNotEqual(before["x"]["sha256"], s.inventory(root)["x"]["sha256"])

    def test_nested_claims_block_even_without_outer_claims(self):
        path = self.base / "Outer.app/Contents/Resources/runtime/DrRacket.app/Contents/Info.plist"
        path.parent.mkdir(parents=True)
        path.write_bytes(plistlib.dumps({"CFBundleDocumentTypes": [{"CFBundleTypeExtensions": ["rkt"]}]}))
        rows = s.nested_claims(self.base / "Outer.app")
        self.assertEqual(len(rows), 1)
        with self.assertRaises(s.Refusal): s.refuse_claims(rows)

    def test_nested_empty_declaration_is_review_gate(self):
        with self.assertRaises(s.Refusal): s.refuse_claims([{"declarations": {"UTImportedTypeDeclarations": []}}])

    def test_aliased_bundle_backing_directory_claims_block(self):
        path = self.base / "Payload/Contents/Info.plist"
        path.parent.mkdir(parents=True)
        path.write_bytes(plistlib.dumps({"UTExportedTypeDeclarations": []}))
        (self.base / "Alias.app").symlink_to("Payload")
        with self.assertRaises(s.Refusal): s.refuse_claims(s.nested_claims(self.base))

    def test_mixed_case_bundle_claims_block(self):
        path = self.base / "Nested.APP/Contents/info.PLIST"
        path.parent.mkdir(parents=True)
        path.write_bytes(plistlib.dumps({"CFBundleDocumentTypes": []}))
        with self.assertRaises(s.Refusal): s.refuse_claims(s.nested_claims(self.base))

    def test_clean_environment_drops_poison(self):
        with mock.patch.dict(os.environ, {"PLTCOLLECTS": "/evil", "PLTLINKS": "/evil", "DYLD_LIBRARY_PATH": "/evil", "BASH_ENV": "/evil", "OPENRACKET_PROFILE": "/real-user"}):
            env = s.clean_env(self.base)
        self.assertEqual(set(env), {"PATH", "HOME", "TMPDIR", "LANG"})
        self.assertTrue(env["HOME"].startswith(str(self.base)))

    def test_fresh_test_profile_no_user_state(self):
        p = s.new_profile(self.base, "test-profile")
        self.assertEqual(p.stat().st_mode & 0o777, 0o700)
        self.assertEqual(set(x.name for x in p.iterdir()), {"home", "tmp", "addons", "compiled", "TEST-PROFILE"})
        with self.assertRaises(s.Refusal): s.new_profile(self.base, "test-profile")

    def test_native_commands_refuse_linux_without_spawning(self):
        with mock.patch.object(s.sys, "platform", "linux"), mock.patch.object(s.subprocess, "Popen") as popen:
            with self.assertRaises(s.Refusal): s.build(self.base, self.base / "work", "0" * 64)
            with self.assertRaises(s.Refusal): s.run_probe(self.base / "build.json", self.base / "Renamed.app")
            popen.assert_not_called()

    def test_terminal_process_group_must_be_gone(self):
        profile = s.new_profile(self.base, "profile")
        proc = mock.Mock(pid=987654, returncode=0)
        proc.poll.return_value = 0
        with mock.patch.object(s.subprocess, "Popen", return_value=proc), mock.patch.object(s.os, "killpg") as killpg, mock.patch.object(s, "STOP_TIMEOUT", 0):
            with self.assertRaises(s.NativeCleanupUncertain):
                s.bounded_run(["not-executed-mock"], profile, "mock")
            self.assertEqual(killpg.call_args_list, [mock.call(987654, 0), mock.call(987654, s.signal.SIGKILL), mock.call(987654, 0)])
            self.assertEqual(proc.wait.call_args, mock.call(timeout=0))

    def test_terminal_empty_process_group_is_accepted(self):
        profile = s.new_profile(self.base, "profile")
        proc = mock.Mock(pid=987654, returncode=0)
        proc.poll.return_value = 0
        with mock.patch.object(s.subprocess, "Popen", return_value=proc), mock.patch.object(s.os, "killpg", side_effect=ProcessLookupError):
            self.assertEqual(s.bounded_run(["not-executed-mock"], profile, "mock")["pid"], 987654)

    def test_macho_parser(self):
        rows = s.macho_commands(fake_macho(["@executable_path/../Resources/runtime/lib/Racket.framework/Versions/9.3_CS/Racket"], ["@loader_path/lib"]))
        self.assertEqual(rows[0]["cpu_type"], 0x0100000C)
        self.assertEqual(rows[0]["rpaths"], ["@loader_path/lib"])

    def test_truncated_macho_refused(self):
        with self.assertRaises(s.Refusal): s.macho_commands(b"\xcf\xfa\xed\xfe")

    def test_external_absolute_dependency_refused(self):
        rows = [{"path": "binary", "slices": [{"dependencies": ["/Applications/Racket/lib/Racket"], "rpaths": []}]}]
        with self.assertRaises(s.Refusal): s.check_dependency_paths(self.base, rows)

    def test_system_dependency_allowed(self):
        rows = [{"path": "binary", "slices": [{"dependencies": ["/usr/lib/libSystem.B.dylib"], "rpaths": []}]}]
        self.assertEqual(s.check_dependency_paths(self.base, rows), [])

    def test_system_prefix_parent_escape_refused(self):
        self.assertFalse(s.is_system_path("/usr/lib/../../tmp/outside.dylib"))
        self.assertFalse(s.is_system_path("/System/Library/../../tmp/outside.dylib"))
        rows = [{"path": "binary", "slices": [{"dependencies": ["/usr/lib/../../tmp/outside.dylib"], "rpaths": []}]}]
        with self.assertRaises(s.Refusal): s.check_dependency_paths(self.base, rows)

    def test_relative_dependency_is_pending_until_native_witness(self):
        rows = [{"path": "binary", "slices": [{"dependencies": ["@executable_path/lib/Racket"], "rpaths": []}]}]
        self.assertEqual(len(s.check_dependency_paths(self.base, rows)), 1)

    def test_active_closure_requires_measured_dependency(self):
        main = self.base / "main"; lib = self.base / "lib"
        main.write_bytes(fake_macho(["@executable_path/lib"])); lib.write_bytes(fake_macho())
        rows = s.macho_inventory(self.base)
        with self.assertRaises(s.Refusal): s.loaded_closure(self.base, [str(main)], main, rows)
        self.assertEqual(len(s.loaded_closure(self.base, [str(main), str(lib)], main, rows)), 1)

    def test_active_rpath_resolution(self):
        main = self.base / "main"; lib = self.base / "lib"
        main.write_bytes(fake_macho(["@rpath/lib"], ["@executable_path/."])); lib.write_bytes(fake_macho())
        self.assertEqual(len(s.loaded_closure(self.base, [str(main), str(lib)], main, s.macho_inventory(self.base))), 1)

    def test_generator_options_and_no_automatic_payload(self):
        source = (ROOT / "make-launcher.rkt").read_text()
        for text in ["#:gracket? #t", "#:launcher? #t", "#:variant 'cs", "#:collects-path null",
                     "(relative? . #t)", "(forget-exe? . #t)", "@executable_path/../Resources/runtime/lib/"]:
            self.assertIn(text, source)
        self.assertNotIn("copy-directory/files", source)
        supervisor = (ROOT / "supervise.py").read_text()
        self.assertLess(supervisor.index('profile, "generate"'), supervisor.index('copy_plan = copy_isolated_runtime('))

    def test_pre_package_link_path_assertion(self):
        source = (ROOT / "probe/boot.rkt").read_text()
        self.assertLess(source.index('(call-with-output-file*'), source.index('(unless (and (use-collection-link-paths)'))
        self.assertLess(source.index('(unless (and (use-collection-link-paths)'), source.index('(dynamic-require'))

    def test_process_preserving_bootstrap_and_absolute_overrides(self):
        source = (ROOT / "bootstrap.sh").read_text()
        for text in ['exec /usr/bin/env -i', '-E "$RUNTIME/bin/racket"', '-X "$RUNTIME/collects"',
                     '-G "$RUNTIME/etc"', '-A "$PROFILE/addons" -U -R "$PROFILE/compiled"']:
            self.assertIn(text, source)
        self.assertNotIn("mkdir", source)

    def test_no_native_trigger_workflow_or_network(self):
        self.assertFalse((ROOT / ".github").exists())
        source = (ROOT / "supervise.py").read_text()
        for forbidden in ["shell=True", "urllib", "requests.", "xattr", "spctl", "codesign", "LSRegisterURL", "LSSetDefault", "raco pkg", "upload-artifact"]:
            self.assertNotIn(forbidden, source)

    def test_racket_lexical_delimiters_not_reader_gate(self):
        for path in ROOT.rglob("*.rkt"):
            text = path.read_text(); stack = []; i = 0; string = False
            while i < len(text):
                c = text[i]
                if string:
                    if c == "\\": i += 2; continue
                    if c == '"': string = False
                elif c == ";":
                    end = text.find("\n", i)
                    i = len(text) if end < 0 else end; continue
                elif c == '"': string = True
                elif c in "([{": stack.append(c)
                elif c in ")]}":
                    self.assertTrue(stack, str(path))
                    self.assertEqual(stack.pop(), {")": "(", "]": "[", "}": "{"}[c], str(path))
                i += 1
            self.assertFalse(string, str(path)); self.assertFalse(stack, str(path))


class ReportValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.base = Path(self.temp.name).resolve(strict=True)
        self.app = self.base / "Moved λ's Probe.app"; self.runtime = self.app / "Contents/Resources/runtime"
        self.profile = self.base / "fresh-profile"
        for p in [self.runtime / "collects", self.runtime / "etc", self.runtime / "share/pkgs",
                  self.runtime / "bin", self.app / "Contents/MacOS", self.profile / "addons"]:
            p.mkdir(parents=True, exist_ok=True)
        for p in [self.runtime / "bin/racket", self.app / "Contents/MacOS/ProbeNative", self.app / "Contents/MacOS/ProbeBootstrap"]:
            p.write_bytes(fake_macho())
        def rec(p):
            return {"raw": str(p), "absolute": str(p), "exists": p.exists(), "resolved": str(p.resolve()) if p.exists() else False}
        self.rec = rec
        paths = {"system": {k: rec(p) for k, p in {"exec-file": self.runtime / "bin/racket", "run-file": self.app / "Contents/MacOS/ProbeNative",
                 "collects-dir": self.runtime / "collects", "config-dir": self.runtime / "etc", "addon-dir": self.profile / "addons"}.items()},
                 "use_collection_link_paths": True, "use_user_specific_search_paths": False,
                 "setup": {"pkgs": rec(self.runtime / "share/pkgs")}}
        for key, path in {"config_file": self.runtime / "etc/config.rktd", "links_file": self.runtime / "share/links.rktd",
                          "package_database": self.runtime / "share/pkgs/pkgs.rktd"}.items():
            if key != "config_file": path.write_text("()")
            paths[key] = {"path": rec(path), "sha256": s.file_digest(path) if path.exists() else False}
        identity = {"pid": 100, "running_pid": 100, "same_running_application": True,
                    "main_bundle_path": str(self.app), "running_bundle_path": str(self.app),
                    "main_bundle_identifier": s.BUNDLE_ID, "running_bundle_identifier": s.BUNDLE_ID,
                    "process_image_path": str(self.app / "Contents/MacOS/ProbeNative"),
                    "running_executable_path": str(self.app / "Contents/MacOS/ProbeNative"),
                    "main_bundle_executable_path": str(self.app / "Contents/MacOS/ProbeBootstrap")}
        modules = {}
        for name in ["racket_base", "setup_dirs", "pkg_lib", "gui_base", "drracket_main"]:
            p = self.runtime / "collects" / name; p.write_text(name)
            modules[name] = {"path": rec(p), "sha256": s.file_digest(p)}
        self.report = {"schema": 1, "status": "observed", "version": "9.3", "os": "macosx", "gc": "cs",
                       "startup": copy.deepcopy(paths), "paths": copy.deepcopy(paths), "modules": modules,
                       "identity": identity, "loaded_images": [str(self.app / "Contents/MacOS/ProbeNative"), "/usr/lib/libSystem.B.dylib"],
                       "child": {"schema": 1, "status": "observed", "pid": 101, "version": "9.3", "gc": "cs", "paths": copy.deepcopy(paths), "loaded_images": [str(self.runtime / "bin/racket")]}}

    def tearDown(self): self.temp.cleanup()
    def validate(self): return s.validate_report(self.report, self.app, self.profile, 100)

    def test_complete_synthetic_report(self): self.assertEqual(self.validate()["status"], "path-and-identity-observation-validated")
    def test_disabled_collection_links_refused(self):
        self.report["startup"]["use_collection_link_paths"] = False
        with self.assertRaises(s.Refusal): self.validate()
    def test_external_config_refused(self):
        self.report["paths"]["system"]["config-dir"] = self.rec(self.base)
        with self.assertRaises(s.Refusal): self.validate()
    def test_external_config_alias_refused(self):
        outside = self.base / "outside-config"; outside.mkdir()
        alias = self.runtime / "config-alias"
        alias.symlink_to(outside, target_is_directory=True)
        self.report["paths"]["system"]["config-dir"] = self.rec(alias)
        with self.assertRaisesRegex(s.Refusal, "escaped active path"):
            self.validate()
    def test_source_module_escape_refused(self):
        p = self.base / "source.rkt"; p.write_text("x")
        self.report["modules"]["gui_base"] = {"path": self.rec(p), "sha256": s.file_digest(p)}
        with self.assertRaises(s.Refusal): self.validate()
    def test_fake_process_identity_refused(self):
        self.report["identity"]["process_image_path"] = str(self.runtime / "bin/racket")
        with self.assertRaises(s.Refusal): self.validate()
    def test_bundle_rename_not_old_path(self):
        self.report["identity"]["main_bundle_path"] = str(self.base)
        with self.assertRaises(s.Refusal): self.validate()
    def test_different_pid_refused(self):
        self.report["identity"]["pid"] = 333
        with self.assertRaises(s.Refusal): self.validate()
    def test_external_dylib_refused(self):
        p = self.base / "external.dylib"; p.write_bytes(fake_macho())
        self.report["loaded_images"].append(str(p))
        with self.assertRaises(s.Refusal): self.validate()
    def test_child_external_path_refused(self):
        self.report["child"]["paths"]["system"]["exec-file"] = self.rec(self.base)
        with self.assertRaises(s.Refusal): self.validate()
    def test_hash_mismatch_refused(self):
        self.report["modules"]["gui_base"]["sha256"] = "0" * 64
        with self.assertRaises(s.Refusal): self.validate()
    def test_wrong_child_version_refused(self):
        self.report["child"]["version"] = "9.2"
        with self.assertRaises(s.Refusal): self.validate()
    def test_missing_config_cannot_claim_hash(self):
        self.report["paths"]["config_file"]["sha256"] = "0" * 64
        with self.assertRaises(s.Refusal): self.validate()
    def test_forged_canonical_path_refused(self):
        record = self.report["paths"]["system"]["config-dir"]
        record["absolute"] = str(self.base)
        with self.assertRaises(s.Refusal): self.validate()
    def test_parent_escape_canonicalized_before_containment(self):
        outside = str(self.app / "..")
        self.report["paths"]["escape"] = {"absolute": outside, "resolved": outside,
                                           "raw": outside, "exists": True}
        with self.assertRaises(s.Refusal): self.validate()
    def test_missing_package_database_refused(self):
        path = self.runtime / "share/pkgs/pkgs.rktd"; path.unlink()
        self.report["paths"]["package_database"] = {"path": self.rec(path), "sha256": False}
        with self.assertRaises(s.Refusal): self.validate()

    def test_boolean_schema_refused(self):
        self.report["schema"] = True
        with self.assertRaises(s.Refusal): self.validate()

    def test_boolean_child_schema_refused(self):
        self.report["child"]["schema"] = True
        with self.assertRaises(s.Refusal): self.validate()

    def test_malformed_native_pids_refused(self):
        for where, key in [("identity", "pid"), ("identity", "running_pid"), ("child", "pid")]:
            original = self.report[where][key]
            for value in [False, True, 0, -1, 101.0, "101", None]:
                with self.subTest(where=where, key=key, value=value):
                    self.report[where][key] = value
                    with self.assertRaises(s.Refusal): self.validate()
            self.report[where][key] = original

    def test_non_boolean_path_exists_refused(self):
        path = self.report["paths"]["system"]["config-dir"]
        for value in [0, 1, "true", None]:
            with self.subTest(value=value):
                path["exists"] = value
                with self.assertRaises(s.Refusal): self.validate()

    def test_non_boolean_module_path_exists_refused(self):
        self.report["modules"]["gui_base"]["path"]["exists"] = 1
        with self.assertRaises(s.Refusal): self.validate()

    def assert_cleanup_failure_blocks_native_followups(self, mode):
        baseline = {"schema": 1, "status": "observed", "default_handler": "org.example.Editor", "defaults_changed": False}
        record = {"status": "assembled-not-launched", "bundle": str(self.app),
                  "native_sha256": s.file_digest(self.app / "Contents/MacOS/ProbeNative"),
                  "original_runtime": str(self.base / "absent-original"), "handler_baseline": baseline}
        original = s.inventory(self.runtime)
        original["DrRacket.app"] = {"kind": "directory", "mode": 0o755, "mtime_ns": 0}
        plan, retained = s.runtime_copy_plan(original)
        self.assertEqual(retained, s.inventory(self.runtime))
        record.update(original_runtime_digest=s.inventory_digest(original),
                      runtime_copy_plan="runtime-copy-plan.json",
                      retained_runtime_digest=plan["retained_inventory_digest"],
                      static_loader_context_pending=[])
        record_path = self.base / "build.json"
        record_path.write_text(json.dumps(record))
        (self.base / "original-runtime.json").write_text(json.dumps(original))
        (self.base / "runtime-copy-plan.json").write_text(json.dumps(plan))
        destination = self.base / "New Name.app"
        proc = mock.Mock(pid=987654, returncode=0)
        proc.poll.return_value = 0
        proc.wait.return_value = 0
        signal_effect = None
        if mode == "signal":
            proc.poll.side_effect = OSError("poll interrupted")
            signal_effect = PermissionError("cannot signal owned group")
        elif mode == "wait":
            proc.poll.side_effect = OSError("poll interrupted")
            proc.wait.side_effect = OSError("cannot wait for owned leader")
        elif mode == "recheck":
            proc.poll.side_effect = OSError("poll interrupted")
            signal_effect = [None, PermissionError("cannot recheck owned group")]
        elif mode == "terminal-check":
            signal_effect = PermissionError("cannot verify terminal group")
        elif mode == "bounded-death-wait":
            proc.poll.side_effect = OSError("poll interrupted")
        with mock.patch.object(s, "native_only"), mock.patch.object(s, "handler", return_value=baseline) as handler, \
             mock.patch.object(s.subprocess, "Popen", return_value=proc) as popen, \
             mock.patch.object(s.os, "killpg", side_effect=signal_effect), mock.patch.object(s, "STOP_TIMEOUT", 0):
            with self.assertRaises(s.NativeCleanupUncertain): s._run_probe(record_path, destination)
            self.assertEqual(popen.call_count, 1)
            self.assertEqual(handler.call_count, 1)
            self.assertEqual(handler.call_args.args[2], "handler-before-launch")
        self.assertTrue(self.app.exists())
        self.assertFalse(destination.exists())
        self.assertFalse((self.base / "run-profile-1").exists())
        witness = json.loads((self.base / "run-profile-0/post-launch-witness.json").read_text())
        self.assertFalse(witness["owned_process_group_cleanup_certain"])
        self.assertEqual(witness["handler_after"]["status"], "unobserved-owned-process-group-cleanup-uncertain")

    def test_signal_error_blocks_query_and_relocation(self):
        self.assert_cleanup_failure_blocks_native_followups("signal")
    def test_wait_error_blocks_query_and_relocation(self):
        self.assert_cleanup_failure_blocks_native_followups("wait")
    def test_recheck_error_blocks_query_and_relocation(self):
        self.assert_cleanup_failure_blocks_native_followups("recheck")
    def test_terminal_check_error_blocks_query_and_relocation(self):
        self.assert_cleanup_failure_blocks_native_followups("terminal-check")
    def test_bounded_death_wait_blocks_query_and_relocation(self):
        self.assert_cleanup_failure_blocks_native_followups("bounded-death-wait")


if __name__ == "__main__":
    unittest.main(verbosity=2)
