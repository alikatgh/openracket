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
    def test_original_regression_wrapper_and_tools_unchanged(self):
        pins = {
            'native-tool-coordinator-test.rkt': '72e040a7e14997477a420024714b810b98f6ecd52dc66ef510c6f9572ee1866d',
            'native-tool-coordinator.rkt': 'a86f91cd5d55b27e1f9f7c535f387d935791daa7ba41b2934e6e3810fecf6384',
            'independent-native-stock-tools.rkt': '06a9734b272fcfa9a62b4d92e43f3a2f45692b26c22e36e9e9d526482490e884',
        }
        for name, digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest(), digest)

    def test_original_submodule_runs_under_strict_outer_handler(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        self.assertIn('(parameterize ([current-check-handler raise])\n  (dynamic-require `(submod ,regression test) #f)', text)
        before_injection = text.split('  (when (equal? arguments #("--inject-outer-failure"))')[0]
        self.assertNotIn('with-handlers', before_injection)
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

    def test_only_injected_check_has_typed_handler_and_same_exception_reraise(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        self.assertEqual(text.count('(with-handlers'), 2)
        self.assertIn('(with-handlers\n        ([exn:test:check?\n          (lambda (failure)', text)
        self.assertIn('(raise failure))])\n      (check-equal? \'actual \'deliberately-wrong))))', text)
        self.assertEqual(text.count('(raise failure)'), 1)
        self.assertEqual(text.count('(exit '), 1)
        for banned in ('[exn:fail?', '[exn?', '(check-exn',
                       'make-exn:', 'error-display-handler', 'current-check-around'):
            self.assertNotIn(banned, text)

    def test_diagnostic_failure_catch_cannot_swallow_original_exception(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        diagnostic = '(with-handlers ([(lambda (_) #t) void])'
        self.assertEqual(text.count(diagnostic), 1)
        self.assertEqual(text.count('(lambda (_) #t)'), 1)
        self.assertIn(diagnostic + '\n              (define infos (exn:test:check-stack failure))', text)
        start = text.index(diagnostic)
        end = text.index('\n            (raise failure)', start)
        guarded = text[start:end]
        self.assertTrue(guarded.endswith('(flush-output)))'))
        source_tests.delimiter_check(guarded)
        for banned in ('(dynamic-require', '(check-equal?', '(raise failure)',
                       '(exit ', 'OPENRACKET_NATIVE_TOOL_COORDINATOR_OK'):
            self.assertNotIn(banned, guarded)
        self.assertIn('(flush-output)))\n            (raise failure))])\n      (check-equal?', text)

    def test_failure_evidence_comes_from_verified_exception_info(self):
        text = (ROOT/'tests/native-tool-coordinator-standalone.rkt').read_text()
        for required in (
                '(only-in rackunit/private/check-info pretty-info? pretty-info-value)',
                '(define infos (exn:test:check-stack failure))',
                '(for/list ([info (in-list infos)]',
                '#:when (eq? (check-info-name info) key)',
                '(check-info-value info)',
                '(and (= (length matches) 1) (car matches))',
                "(define name (unique-info-value 'name))",
                "(define actual (unique-info-value 'actual))",
                "(define expected (unique-info-value 'expected))",
                "(when (and (eq? name 'check-equal?)",
                '(pretty-info? actual)', '(pretty-info? expected)',
                "(eq? (pretty-info-value actual) 'actual)",
                "(eq? (pretty-info-value expected) 'deliberately-wrong))",
                'name (pretty-info-value actual) (pretty-info-value expected))\n                (flush-output)))\n            (raise failure)'):
            self.assertIn(required, text)
        marker = 'OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE'
        self.assertEqual(text.count(marker), 1)
        self.assertIn(marker + ' exception=exn:test:check check=~s actual=~s expected=~s\\n', text)
        self.assertLess(text.index("(eq? (pretty-info-value expected) 'deliberately-wrong)"), text.index(marker))
        self.assertLess(text.index(marker), text.index('(raise failure)'))

if __name__ == '__main__':
    unittest.main()
