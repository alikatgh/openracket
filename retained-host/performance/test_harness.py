#!/usr/bin/env python3
"""Headless harness tests; these do not launch DrRacket or a display server."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import run as runner
from fixtures import generate, write_fixtures
from run import native_rss, quantiles, run_trial

class HarnessTests(unittest.TestCase):
    def test_exact_lengths_and_safe_edit_anchor(self):
        for size in (100_000, 1_048_576):
            data, anchor = generate(size)
            self.assertEqual(len(data), size)
            self.assertEqual(len(data.decode('ascii')), size)
            self.assertEqual(data[anchor:anchor + 8], b'comments')
            self.assertIn(b'; warm-input-target-', data[data.rfind(b'\n', 0, anchor):anchor])
            self.assertTrue(data.endswith(b'|#\n'))
            self.assertEqual(generate(size), (data, anchor))

    def test_nearest_rank_tails(self):
        self.assertEqual(quantiles([]), {'n': 0})
        self.assertEqual(quantiles([4, 1, 3, 2]),
                         {'n': 4, 'median': 2.5, 'p95': 4, 'p99': 4, 'max': 4})

    def test_arguments_cleared_before_gui_eventspace(self):
        source = (Path(__file__).parent / 'retained-host.rkt').read_text()
        clear = source.index('(current-command-line-arguments #())')
        create_gui = source.index("(dynamic-require 'racket/gui/base")
        self.assertLess(clear, create_gui)
        self.assertNotIn('(parameterize ([current-command-line-arguments', source)

    def test_repeated_startup_failure_skips_remaining_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ['run.py', '--mode', 'test-only', '--output', directory,
                    '--repetitions', '3']
            def fake_trial(args, fixture, repetition):
                return {'status': 'timeout', 'fixture_metadata': fixture,
                        'repetition': repetition, 'native_max_rss_bytes': None,
                        'process_wall_ms': 10}
            with mock.patch.object(runner, 'run_trial', side_effect=fake_trial) as call, \
                 mock.patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            self.assertEqual(call.call_count, 2)
            summary = json.loads((Path(directory) / 'summary.json').read_text())
            self.assertEqual(len(summary['trials']), 2)
            self.assertEqual(len(summary['trials_not_run']), 4)

    def test_cleanup_skips_a_dead_process_group(self):
        process = mock.Mock(pid=12345)
        with mock.patch.object(runner, 'live_group_members', return_value=[]), \
             mock.patch.object(runner.os, 'killpg') as kill:
            runner.terminate_group(process)
        self.assertEqual(kill.call_count, 1)
        self.assertEqual(kill.call_args.args[1], runner.signal.SIGTERM)

    def test_macos_permission_error_requires_no_live_members(self):
        with mock.patch.object(runner.os, 'killpg', side_effect=PermissionError), \
             mock.patch.object(runner, 'live_group_members', return_value=[]):
            self.assertFalse(runner.signal_group(12345, runner.signal.SIGKILL))
        with mock.patch.object(runner.os, 'killpg', side_effect=PermissionError), \
             mock.patch.object(runner, 'live_group_members', return_value=[{'pid': 1}]):
            with self.assertRaises(PermissionError):
                runner.signal_group(12345, runner.signal.SIGKILL)

    def test_native_resource_units(self):
        self.assertEqual(native_rss('Maximum resident set size (kbytes): 42\n', 'Linux'), 43008)
        self.assertEqual(native_rss('  123456  maximum resident set size\n', 'Darwin'), 123456)
        self.assertIsNone(native_rss('', 'Linux'))

    def test_stubborn_descendant_is_really_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            group_file = root / 'process-group.txt'
            executable = root / 'fake-racket'
            executable.write_text(
                '#!/usr/bin/env python3\nimport os, signal, time\n'
                'if os.fork() == 0:\n'
                '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                f'    open({str(group_file)!r}, "w").write(str(os.getpgrp()))\n'
                '    time.sleep(30)\n'
                'else:\n    time.sleep(30)\n')
            executable.chmod(0o755)
            fixture = write_fixtures(root / 'fixtures')[0]
            args = types.SimpleNamespace(output=root, mode='test-only',
                                         racket=str(executable), timeout=.3)
            with contextlib.redirect_stdout(io.StringIO()):
                report = run_trial(args, fixture, 1)
            self.assertEqual(report['status'], 'timeout')
            self.assertTrue(group_file.exists())
            self.assertEqual(runner.live_group_members(int(group_file.read_text())), [])

    def test_timeout_is_recorded_and_process_group_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'fake-racket'
            executable.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n')
            executable.chmod(0o755)
            fixture = write_fixtures(root / 'fixtures')[0]
            args = types.SimpleNamespace(output=root, mode='test-only',
                                         racket=str(executable), timeout=.15)
            with contextlib.redirect_stdout(io.StringIO()):
                report = run_trial(args, fixture, 1)
            self.assertTrue(report['timeout'])
            self.assertEqual(report['status'], 'timeout')
            self.assertNotEqual(report['exit_code'], 0)
            self.assertLess(report['process_wall_ms'], 6000)
            saved = json.loads((root / 'mixed-100k-01/measurements.json').read_text())
            self.assertEqual(saved['status'], 'timeout')

if __name__ == '__main__':
    unittest.main()
