#!/usr/bin/env python3
"""Headless fake-process tests. Never starts Racket, a display, or a GUI."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import supervise


FAKE_PREAMBLE = r'''
import json, os, pathlib, signal, sys, time
config = json.loads(os.environ['OPENRACKET_REPLAY_CONFIG'])
assert os.environ['OPENRACKET_EXPANSION_REPLAY'] == '1'
assert 'OPENRACKET_EXPANSION_CAPTURE' not in os.environ
assert {key for key in os.environ if key.startswith('OPENRACKET_')} == {
    'OPENRACKET_EXPANSION_REPLAY', 'OPENRACKET_REPLAY_CONFIG', 'OPENRACKET_REPLAY_SUPPORT'}
assert pathlib.Path(os.environ['OPENRACKET_REPLAY_SUPPORT']).is_absolute()
out = pathlib.Path(config['output'])
def phase(event, trial=1, **extra):
    print('OPENRACKET_REPLAY_PHASE_JSON ' + json.dumps(dict(
        event=event, trial=trial, monotonic_ms=time.monotonic() * 1000, **extra)), flush=True)
def finish():
    (out / 'replay.json').write_text(json.dumps({'fake_child_only': True}))
    phase('cleanup')
    phase('finished')
'''


@unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="replay-supervisor-test-")
        self.output = Path(self.temp.name) / "run"
        self.config = {"capture": "fake-capture-not-read", "output": str(self.output),
                       "trials": 2, "init_timeout_seconds": 0.15,
                       "terminal_timeout_seconds": 0.25, "cleanup_timeout_seconds": 0.35}

    def tearDown(self):
        self.temp.cleanup()

    def run_child(self, body, **kwargs):
        env = dict(os.environ, OPENRACKET_EXPANSION_CAPTURE="must-not-propagate",
                   OPENRACKET_CAPTURE_OUTPUT="must-not-propagate",
                   OPENRACKET_CAPTURE_EXPECTED_SHA256="must-not-propagate",
                   OPENRACKET_APPEARANCE="must-not-propagate",
                   OPENRACKET_SCAN="must-not-propagate",
                   OPENRACKET_COLOR_BUDGET="must-not-propagate",
                   OPENRACKET_AUTOSAVE="must-not-propagate",
                   OPENRACKET_UNRECOGNIZED_FUTURE_FLAG="must-not-propagate")
        return supervise.run_supervised(
            [sys.executable, "-u", "-c", FAKE_PREAMBLE + body], self.output, self.config,
            env=env, startup_cushion_seconds=0.1, sample_seconds=0.02,
            poll_seconds=0.01, **kwargs)

    def test_success_raw_logs_events_rss_and_environment(self):
        report = self.run_child(r'''
phase('initializing', 0)
sys.stderr.buffer.write(b'e' * 200000 + b'\x00\xff\n'); sys.stderr.flush()
sys.stdout.buffer.write(b'x' * 200000 + b'\x00\xff\n'); sys.stdout.flush()
for trial in (1, 2):
    phase('interval_start', trial)
    data = bytearray(2 * 1024 * 1024)
    time.sleep(.10)
    phase('interval_end', trial, outcome='completed')
finish()
''')
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(report["death"]["returncode"], 0)
        self.assertFalse(report["timeout"]["triggered"])
        self.assertTrue(report["cleanup"]["child_reaped"])
        self.assertTrue(report["cleanup"]["complete"])
        self.assertEqual(report["stdout_unparsed_bytes"], 0)
        self.assertEqual(len(report["intervals"]), 2)
        for interval in report["intervals"]:
            self.assertEqual(interval["outcome"], "completed")
            self.assertEqual(interval["closure"], "interval_end")
            self.assertGreater(interval["rss_sample_count"], 0)
            # Unavailable measurements may stay null on restricted hosts.
            if interval["rss_available_sample_count"]:
                self.assertGreater(interval["rss_observed_peak_bytes"], 0)
        self.assertIn(b"x" * 200000 + b"\x00\xff\n", (self.output / "stdout.log").read_bytes())
        self.assertEqual((self.output / "stderr.log").read_bytes(), b"e" * 200000 + b"\x00\xff\n")
        self.assertEqual(json.loads((self.output / "supervisor.json").read_text())["status"], "ok")

    def test_clears_all_inherited_openracket_controls_before_setting_own(self):
        inherited = {
            "OPENRACKET_EXPANSION_CAPTURE": "1", "OPENRACKET_APPEARANCE": "1",
            "OPENRACKET_SCAN": "1", "OPENRACKET_COLOR_BUDGET": "1",
            "OPENRACKET_AUTOSAVE": "1", "OPENRACKET_UNKNOWN_FLAG": "1",
            "OPENRACKET_EXPANSION_REPLAY": "stale",
            "OPENRACKET_REPLAY_CONFIG": "not valid JSON",
            "OPENRACKET_REPLAY_SUPPORT": "/stale/support.rkt",
            "UNRELATED_ENVIRONMENT_VALUE": "preserved",
        }
        with mock.patch.dict(os.environ, inherited):
            report = supervise.run_supervised(
                [sys.executable, "-u", "-c", FAKE_PREAMBLE +
                 "assert os.environ['UNRELATED_ENVIRONMENT_VALUE'] == 'preserved'\nfinish()\n"],
                self.output, self.config, startup_cushion_seconds=0.1,
                sample_seconds=0.02, poll_seconds=0.01)
        self.assertEqual(report["status"], "ok", (self.output / "stderr.log").read_text())

    def test_timeout_kills_term_resistant_child_and_reaps(self):
        before = time.monotonic()
        report = self.run_child(r'''
signal.signal(signal.SIGTERM, signal.SIG_IGN)
phase('initializing', 0)
phase('interval_start')
while True: time.sleep(.1)
''')
        self.assertEqual(report["status"], "timeout")
        self.assertTrue(report["timeout"]["triggered"])
        self.assertIn("SIGKILL", report["cleanup"]["signals"])
        self.assertEqual(report["death"]["signal"], signal.SIGKILL)
        self.assertTrue(report["cleanup"]["complete"], report["cleanup"])
        self.assertLess(time.monotonic() - before, report["hard_wall_budget_seconds"] + 0.4)
        self.assertEqual(report["intervals"][0]["closure"], "supervisor_stop")

    def test_supervisor_sigterm_still_kills_and_reaps(self):
        report = self.run_child(r'''
signal.signal(signal.SIGTERM, signal.SIG_IGN)
phase('initializing', 0)
os.kill(os.getppid(), signal.SIGTERM)
while True: time.sleep(.1)
''')
        self.assertEqual(report["status"], "interrupted")
        self.assertFalse(report["timeout"]["triggered"])
        self.assertTrue(report["cleanup"]["complete"], report["cleanup"])
        self.assertIn("SIGKILL", report["cleanup"]["signals"])
        self.assertIn("SIGTERM", [e["detail"] for e in report["errors"]])

    @unittest.skipUnless(hasattr(os, "fork"), "requires fork")
    def test_early_driver_death_cleans_term_resistant_descendant(self):
        report = self.run_child(r'''
readfd, writefd = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(readfd)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(writefd, b'ready')
    os.close(writefd)
    while True: time.sleep(.1)
os.close(writefd)
os.read(readfd, 5)
print('descendant=' + str(pid), flush=True)
os._exit(7)
''')
        self.assertEqual(report["status"], "driver_failed")
        self.assertEqual(report["death"]["returncode"], 7)
        self.assertTrue(report["death"]["unexpected"])
        self.assertTrue(report["cleanup"]["complete"], report["cleanup"])
        self.assertIn("SIGKILL", report["cleanup"]["signals"])
        self.assertEqual(report["cleanup"]["remaining_live_pids"], [])

    def test_launch_failure_still_writes_separate_failure_report(self):
        report = supervise.run_supervised(
            [str(Path(self.temp.name) / "missing-executable")], self.output, self.config,
            startup_cushion_seconds=0)
        self.assertEqual(report["status"], "supervisor_error")
        self.assertFalse(report["cleanup"]["attempted"])
        self.assertIsNone(report["death"]["returncode"])
        self.assertFalse(report["timeout"]["triggered"])
        self.assertTrue((self.output / "supervisor.json").is_file())

    def test_missing_result_is_not_success(self):
        report = self.run_child("phase('finished')\n")
        self.assertEqual(report["status"], "driver_failed")
        self.assertFalse(report["driver_result"]["exists"])
        self.assertIn("driver_result", [e["category"] for e in report["errors"]])

    def test_missing_finished_event_is_not_success(self):
        report = self.run_child("(out / 'replay.json').write_text('{}')\n")
        self.assertEqual(report["status"], "driver_failed")
        self.assertTrue(report["death"]["unexpected"])

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        original = self.output / "replay.json"
        original.write_text('{"preserve": true}')
        with self.assertRaisesRegex(ValueError, "fresh output directory"):
            self.run_child("finish()\n")
        self.assertEqual(original.read_text(), '{"preserve": true}')

    def test_unavailable_rss_is_null(self):
        real_snapshot = supervise.process_group_snapshot
        def without_rss(*args, **kwargs):
            result = real_snapshot(*args, **kwargs)
            result["rss_bytes"] = None
            return result
        with mock.patch.object(supervise, "process_group_snapshot", side_effect=without_rss):
            report = self.run_child("phase('interval_start')\ntime.sleep(.10)\nphase('interval_end')\nfinish()\n")
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["rss_samples"])
        self.assertTrue(all(s["rss_bytes"] is None for s in report["rss_samples"]))
        self.assertIsNone(report["intervals"][0]["rss_observed_peak_bytes"])

    def test_unknown_group_has_null_rss(self):
        result = supervise.process_group_snapshot(2**30)
        self.assertIsNone(result["rss_bytes"])
        if result["complete"]:
            self.assertEqual(result["members"], [])

    def test_ps_membership_and_rss_without_kill_zero_probe(self):
        response = subprocess.CompletedProcess(["ps"], 0, " 123 456 100 S\n 124 456 20 Z\n 999 999 50 S\n", "")
        with mock.patch.object(supervise.sys, "platform", "darwin"), \
             mock.patch.object(supervise.subprocess, "run", return_value=response) as run:
            result = supervise.process_group_snapshot(456)
        self.assertEqual(result["rss_bytes"], 100 * 1024)
        self.assertEqual([m["pid"] for m in supervise.live_members(result)], [123])
        self.assertEqual(run.call_args.args[0][0], "ps")

    def test_empty_mac_group_does_not_signal_or_treat_eperm_as_alive(self):
        proc = mock.Mock(pid=123456789, returncode=0)
        response = subprocess.CompletedProcess(["ps"], 0, "", "")
        with mock.patch.object(supervise.sys, "platform", "darwin"), \
             mock.patch.object(supervise.subprocess, "run", return_value=response), \
             mock.patch.object(supervise.os, "killpg", side_effect=PermissionError("EPERM")) as kill:
            result = supervise.cleanup_group(proc, time.monotonic() + 0.1)
        kill.assert_not_called()
        self.assertTrue(result["complete"], result)

    def test_group_disappearing_at_signal_eperm_is_already_clean(self):
        proc = mock.Mock(pid=123456789, returncode=0)
        occupied = {"members": [{"pid": 123, "state": "S"}], "complete": True, "errors": []}
        empty = {"members": [], "complete": True, "errors": []}
        with mock.patch.object(supervise, "process_group_snapshot", side_effect=[occupied, empty, empty, empty, empty]), \
             mock.patch.object(supervise.os, "killpg", side_effect=PermissionError("EPERM")):
            result = supervise.cleanup_group(proc, time.monotonic() + 0.1)
        self.assertTrue(result["complete"], result)
        self.assertEqual(result["errors"], [])

    def test_unknown_membership_is_not_claimed_clean(self):
        proc = mock.Mock(pid=123456789, returncode=0)
        unknown = {"members": None, "complete": False, "errors": ["ps unavailable"]}
        with mock.patch.object(supervise, "process_group_snapshot", return_value=unknown), \
             mock.patch.object(supervise.os, "killpg", side_effect=ProcessLookupError):
            result = supervise.cleanup_group(proc, time.monotonic() + 0.04)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["remaining_live_pids"])


class LaunchContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="replay-launch-test-")
        self.root = Path(self.temp.name)
        self.capture = self.root / "capture.rktd"
        self.capture.write_text("fake capture; no Racket driver reads this")
        self.cwd = self.root / "captured-cwd"
        self.cwd.mkdir()
        self.launch = {"environment": {key: False for key in supervise.LAUNCH_ENV_KEYS},
                       "cwd": str(self.cwd), "snapshot_sha256": "a" * 64,
                       "registry_sha256": "b" * 64}

    def tearDown(self):
        self.temp.cleanup()

    def write_launch(self):
        self.capture.with_suffix(".launch.json").write_text(json.dumps(self.launch))

    def test_restores_allowed_strings_and_unsets_false(self):
        self.launch["environment"]["PLTUSERHOME"] = str(self.root / "user-home")
        self.launch["environment"]["PLTCOLLECTS"] = ""
        self.write_launch()
        with mock.patch.dict(os.environ, {"PLTADDONDIR": "inherited", "UNCHANGED_TEST": "preserved"}):
            launch, env = supervise.load_launch_context(self.capture)
        self.assertEqual(env["PLTUSERHOME"], str(self.root / "user-home"))
        self.assertEqual(env["PLTCOLLECTS"], "")
        self.assertNotIn("PLTADDONDIR", env)
        self.assertEqual(env["UNCHANGED_TEST"], "preserved")
        self.assertEqual(launch["snapshot_sha256"], "a" * 64)

    def test_rejects_nonallowlisted_and_missing_environment_keys(self):
        self.launch["environment"]["PATH"] = "/arbitrary"
        self.write_launch()
        with self.assertRaisesRegex(ValueError, "fixed allowlist"):
            supervise.load_launch_context(self.capture)
        del self.launch["environment"]["PATH"]
        del self.launch["environment"]["PLTUSERHOME"]
        self.write_launch()
        with self.assertRaisesRegex(ValueError, "fixed allowlist"):
            supervise.load_launch_context(self.capture)

    def test_rejects_environment_values_other_than_strings_or_false(self):
        for value in (True, None, 1, 0, [], {}, "bad\x00value"):
            with self.subTest(value=value):
                self.launch["environment"]["PLTUSERHOME"] = value
                self.write_launch()
                with self.assertRaisesRegex(ValueError, "must be a string"):
                    supervise.load_launch_context(self.capture)

    def test_rejects_invalid_cwd_and_metadata(self):
        for value in ("relative", str(self.root / "missing"), False):
            with self.subTest(cwd=value):
                self.launch["cwd"] = value
                self.write_launch()
                with self.assertRaisesRegex(ValueError, "cwd"):
                    supervise.load_launch_context(self.capture)
        self.launch["cwd"] = str(self.cwd)
        self.launch["snapshot_sha256"] = "invalid"
        self.write_launch()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            supervise.load_launch_context(self.capture)

    @unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
    def test_cli_restores_cwd_and_environment_for_fake_executable(self):
        self.launch["environment"]["PLTUSERHOME"] = str(self.root / "captured-home")
        self.write_launch()
        fake = self.root / "fake-racket"
        fake.write_text("#!" + sys.executable + "\n" + FAKE_PREAMBLE + r'''
assert pathlib.Path.cwd() == pathlib.Path(config['capture']).parent / 'captured-cwd'
assert os.environ['PLTUSERHOME'] == str(pathlib.Path(config['capture']).parent / 'captured-home')
assert 'PLTADDONDIR' not in os.environ
assert pathlib.Path(sys.argv[1]).name == 'replay.rkt'
assert pathlib.Path(sys.argv[1]).is_absolute()
assert pathlib.Path(os.environ['OPENRACKET_REPLAY_SUPPORT']).name == 'support.rkt'
finish()
''')
        fake.chmod(0o700)
        output = self.root / "output"
        with mock.patch.dict(os.environ, {"PLTADDONDIR": "must-be-removed", "OPENRACKET_CAPTURE_OUTPUT": "remove"}), \
             contextlib.redirect_stdout(io.StringIO()):
            result = supervise.main(["--racket", str(fake), "--capture", str(self.capture),
                                     "--output", str(output)])
        self.assertEqual(result, 0, (output / "stderr.log").read_text())
        report = json.loads((output / "supervisor.json").read_text())
        self.assertEqual(report["cwd"], str(self.cwd))
        self.assertEqual(report["launch_context"], self.launch)
        self.assertEqual(report["config"]["trials"], 2)
        self.assertEqual(report["hard_wall_budget_seconds"], 157)


class PhaseReaderTests(unittest.TestCase):
    def make_reader(self, raw):
        report = {"errors": [], "phase_events": [], "intervals": [],
                  "death": {"finished_event_received": False}}
        return supervise.PhaseReader(io.BytesIO(raw), report, supervise.monotonic_ms()), report

    def test_fragmented_events_and_unterminated_garbage_are_bounded(self):
        event = supervise.PHASE_PREFIX + b'{"event":"interval_start","trial":1,"monotonic_ms":1}\n'
        reader, report = self.make_reader(b'x' * 200000 + b'\n' + event)
        while reader.poll(31):
            self.assertLessEqual(len(reader.pending), supervise.MAX_LINE_BYTES)
        self.assertEqual(len(report["phase_events"]), 1)
        self.assertEqual(reader.active["trial"], 1)

    def test_bad_event_is_reported_without_losing_valid_next_event(self):
        raw = (supervise.PHASE_PREFIX + b'{"event":"interval_start","trial":1,"monotonic_ms":NaN}\n' +
               supervise.PHASE_PREFIX + b'{"event":"finished","trial":1,"monotonic_ms":2}\n')
        reader, report = self.make_reader(raw)
        reader.poll()
        self.assertEqual(len(report["errors"]), 1)
        self.assertTrue(report["death"]["finished_event_received"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
