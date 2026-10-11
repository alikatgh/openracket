#!/usr/bin/env python3
"""Pins the original checks and standalone failure boundary; not native proof."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_tests', ROOT/'tests/stock-tool-source-test.py')
source_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_tests)

class StandaloneSourceTests(unittest.TestCase):
    def test_original_regression_and_wrapper_unchanged(self):
        pins = {
            'native-tool-coordinator-test.rkt': '72e040a7e14997477a420024714b810b98f6ecd52dc66ef510c6f9572ee1866d',
            'native-tool-coordinator.rkt': 'a86f91cd5d55b27e1f9f7c535f387d935791daa7ba41b2934e6e3810fecf6384',
        }
        for name, digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest(), digest)

    def test_original_submodule_runs_under_strict_outer_handler(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        self.assertIn('(parameterize ([current-check-handler raise])\n  (dynamic-require `(submod ,regression test) #f)', text)
        self.assertNotIn('with-handlers', text)
        self.assertIn('(define-runtime-path regression "native-tool-coordinator-test.rkt")', text)
        source_tests.delimiter_check(text)

    def test_negative_control_precedes_unique_success(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        marker = 'OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete'
        self.assertEqual(text.count(marker), 1)
        self.assertEqual(text.count('OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE'), 1)
        self.assertLess(text.index('OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE'), text.index("(check-equal? 'actual 'deliberately-wrong)"))
        self.assertLess(text.index('(check-equal? \'actual \'deliberately-wrong)'), text.index(marker))
        self.assertTrue(text.rstrip().endswith('(exit 0)'))

if __name__ == '__main__':
    unittest.main()
