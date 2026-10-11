#!/usr/bin/env python3
"""Source/orchestration contracts, not a Racket compiler or a native GUI pass."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

prepare = load_module(ROOT / 'scripts/prepare-stock-tool-host.py')
BASE_HOST = prepare.DEFAULT_BASE_HOST

def delimiter_check(text):
    """Only lexical bracket integrity, explicitly not expansion/read validation."""
    stack = []
    i = 0
    line = 1
    block = 0
    while i < len(text):
        ch = text[i]
        if ch == '\n':
            line += 1
        if block:
            if text.startswith('#|', i):
                block += 1; i += 2; continue
            if text.startswith('|#', i):
                block -= 1; i += 2; continue
            i += 1; continue
        if text.startswith('#|', i):
            block = 1; i += 2; continue
        if ch == ';':
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
            continue
        if text.startswith('#\\', i):
            i += 2
            if i < len(text):
                i += 1
                while i < len(text) and (text[i].isalnum() or text[i] == '-'):
                    i += 1
            continue
        if ch in ('"', '|'):
            delim = ch
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2; continue
                if text[i] == delim:
                    i += 1; break
                if text[i] == '\n':
                    line += 1
                i += 1
            else:
                raise AssertionError(f'Unterminated literal at line {line}')
            continue
        if ch in '([{':
            stack.append((ch, line))
        elif ch in ')]}':
            if not stack:
                raise AssertionError(f'Unexpected {ch} at line {line}')
            opening, start = stack.pop()
            if '([{'.index(opening) != ')]}'.index(ch):
                raise AssertionError(f'{opening} from line {start} closes with {ch} at line {line}')
        i += 1
    if stack or block:
        raise AssertionError(f'Unclosed delimiters: {stack}; block comments={block}')

class StockToolSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = (ROOT/'tests/independent-native-stock-tools.rkt').read_text()
        cls.host = (ROOT/'tests/independent-native-host.rkt').read_text()
        cls.coord = (ROOT/'tests/native-tool-coordinator.rkt').read_text()

    def test_racket_lexical_delimiters(self):
        for path in sorted((ROOT/'tests').glob('*.rkt')):
            with self.subTest(file=path.name): delimiter_check(path.read_text())

    def test_host_derivative_exact_and_base_unchanged(self):
        base = prepare.read_base_host(BASE_HOST)
        self.assertEqual(hashlib.sha256(base.encode()).hexdigest(), prepare.BASE_HOST_SHA256)
        self.assertEqual(prepare.derive(base), self.host)
        with self.assertRaises(ValueError): prepare.derive(base + '\n')

    def test_host_does_not_wrap_new_coordinator_in_gui_callback(self):
        branch = self.host.split('[(member follow-on-case \'("debugger"')[1].split('[(equal? follow-on-case')[0]
        self.assertNotIn('(on-gui', branch)
        self.assertIn('frame (string->symbol follow-on-case) on-gui wait-for', branch)
        self.assertIn('(set! created-frames (cons created created-frames))', branch)
        self.assertIn('OPENRACKET_NATIVE_READY', self.host)
        self.assertIn('OPENRACKET_CAPTURE_DONE', self.host)

    def test_handler_parameterization_and_errors_not_suppressed(self):
        self.assertIn('(lambda ()\n      (unless (eq? (current-thread) handler-thread)', self.coord)
        self.assertIn('(parameterize ([current-check-handler raise])\n        (thunk))', self.coord)
        self.assertIn('(on-gui (checked thunk))', self.coord)
        self.assertIn('(wait-for description (checked predicate) seconds)', self.coord)
        self.assertNotIn('with-handlers', self.coord)
        self.assertIn('[seconds 20]', self.coord)
        regression = (ROOT/'tests/native-tool-coordinator-test.rkt').read_text()
        for phrase in ('current-check-handler (lambda (_) (void))',
                       '(check-equal? 1 2)', 'predicate failure', 'callback-active?',
                       'actual GUI handler', '(check-equal? last-timeout 20)'):
            self.assertIn(phrase, regression)

    def test_no_private_callback_bypass_or_fake_tool_models(self):
        for banned in ('send frame debug-callback', 'send frame run-macro-stepper',
                       'send tab set-break-status', 'send tab set-single-step?!',
                       'send widget add-deriv', 'send widget set-current-step-index',
                       'send tool-frame show #f', 'set-test-object-', 'preferences:set'):
            self.assertNotIn(banned, self.tool)
        self.assertIn('(send debug command)', self.tool)
        self.assertIn('(send launch command)', self.tool)
        self.assertIn('(send tool-frame close)', self.tool)

    def test_debugger_uses_visible_module_toolbar_and_full_state(self):
        for phrase in ('unique-control (send frame get-button-panel) switchable-button%',
                       '(string-constant debug-tool-button-name)', "'pc (send tab get-pc)",
                       "'break_status", "'frame_endpoints", '(send step command)',
                       '(send resume command)', '(not (equal? (debug-state) first-state))',
                       '(send tab defs-containing-pc)', '(check-false (send tab debug?))'):
            self.assertIn(phrase, self.tool)
        self.assertNotIn('(send frame get-debug-button)', self.tool)

    def test_macro_waits_for_real_cursor_and_navigation_progress(self):
        for phrase in ('macro-stepper-widget%', '(send widget get-current-step-index)',
                       '(exact-nonnegative-integer? (index))', '(send next-button is-enabled?)',
                       '(> (index) start-index)', '(> (index) next-index)',
                       '(sub1 end-index)', '(equal? (browser-text) start-text)',
                       '(new control-event% [event-type \'button])'):
            self.assertIn(phrase, self.tool)
        self.assertLess(self.tool.index('completed derivation and enabled real navigation'),
                        self.tool.index('(click! next-button)'))

    def test_teaching_checks_real_model_source_link_and_clear(self):
        for phrase in ("(module->namespace 'test-engine/test-engine)",
                       '(send ints run-in-evaluation-thread',
                       '(parameterize ([current-namespace user-namespace])',
                       "(api 'current-test-object)", "(api 'fail-reason-srcloc)",
                       '(send report call-clickback', '(srcloc-source (car ranges)) defs',
                       '(send defs insert "3" expected-position (add1 expected-position))',
                       '(eq? report (send tab get-test-editor))', '(zero? (send report last-position))',
                       '(done? (string-constant test-engine-both-tests-passed))'):
            self.assertIn(phrase, self.tool)
        self.assertIn("'line 5 'column 0", self.tool)
        self.assertIn("'actual 3 'expected 4", self.tool)
        self.assertIn('(raise (cdr value))', self.tool)
        self.assertIn('(not (send tab is-running?))', self.tool)
        self.assertIn('(send canvas has-focus?)', self.tool)

    def test_fixture_correction_is_exactly_one_character(self):
        def fixture(name):
            # All three fixture strings deliberately use simple Racket/JSON escapes.
            match = re.search(r'\(define '+re.escape(name)+r'\s+("(?:\\.|[^"\\])*")\)', self.tool)
            self.assertIsNotNone(match)
            return json.loads(match[1])
        failing = fixture('teaching-failing')
        form = '(check-expect (bump 2) 4)'
        start = failing.index(form)
        position = start + len(form) - 2
        self.assertEqual(failing[position], '4')
        corrected = failing[:position] + '3' + failing[position+1:]
        self.assertEqual(corrected, failing.replace(form, '(check-expect (bump 2) 3)'))
        self.assertEqual(failing[:start].count('\n') + 1, 5)
        self.assertEqual(len([1 for x,y in zip(failing,corrected) if x!=y]),1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--base-host', type=Path,
                        help='Explicit pinned base-host file; default is the vendored fixture')
    options, remaining = parser.parse_known_args()
    if options.base_host is not None:
        BASE_HOST = options.base_host
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
