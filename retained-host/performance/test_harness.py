#!/usr/bin/env python3
"""Headless harness tests; these do not launch DrRacket or a display server."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
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

    def test_native_resource_units(self):
        self.assertEqual(native_rss('Maximum resident set size (kbytes): 42\n', 'Linux'), 43008)
        self.assertEqual(native_rss('  123456  maximum resident set size\n', 'Darwin'), 123456)
        self.assertIsNone(native_rss('', 'Linux'))

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
