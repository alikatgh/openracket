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
                       '(send link-editor call-clickback 0 (send link-editor last-position))',
                       "(dynamic-require 'framework 'srcloc-snip:snip%)",
                       '(get-field srcloc failure-link)',
                       '(send defs set-position 0 0)',
                       '(navigation-valid? observed expected-file teaching-failing',
                       'failure-start (+ failure-start (string-length failure-form))',
                       '(send group locate-file link-source)',
                       '(check-eq? located frame',
                       '(send frame change-to-tab tab)',
                       '(if (string? link-source) (string->path link-source) link-source)',
                       '(send defs insert "3" expected-position (add1 expected-position))',
                       '(eq? report (send frame get-interactions-text))',
                       '(string-contains? flat-report failure-detail)',
                       '(check-equal? (source-links ints) \'())',
                       '(not (memq failure-link (source-links ints)))',
                       '(done? (string-constant test-engine-both-tests-passed))'):
            self.assertIn(phrase, self.tool)
        self.assertIn("'line 5 'column 0", self.tool)
        self.assertIn("'actual 3 'expected 4", self.tool)
        self.assertIn('(raise (cdr value))', self.tool)
        self.assertIn('(not (send tab is-running?))', self.tool)
        self.assertIn('(send canvas has-focus?)', self.tool)
        teaching = self.tool.split('      [(teaching-tests)')[1]
        self.assertNotIn('get-test-editor', teaching)
        self.assertNotIn('get-error-ranges', teaching)
        self.assertNotIn('set-clickback', teaching)
        self.assertNotIn('initialize-test-object!', teaching)
        self.assertNotIn('test-display-results!', teaching)

    def test_failure_payload_keeps_typed_rackunit_info(self):
        helper = (ROOT/'tests/native-tool-failure-diagnostics.rkt').read_text()
        self.assertIn("'failure_payload (failure->diagnostic exception)", self.host)
        for phrase in ('exn:test:check?', 'exn:test:check-stack', 'check-info-name',
                       'check-info-value', 'pretty-info-value', "'pretty_info"):
            self.assertIn(phrase, helper)
        self.assertNotIn('(raise ', helper)
        self.assertNotIn('current-check-handler', helper)
        self.assertEqual(helper.count('with-handlers'), 1)
        self.assertIn('(with-handlers ([(lambda (_) #t) (lambda (_) (void))])', helper)
        self.assertIn('(reporter failure)', helper)
        self.assertIn('(report-failure!\n         e', self.host)
        self.assertIn('(failure-diagnostics! original)))\n        (cleanup!)\n        (exit 1)', self.host)
        regression = (ROOT/'tests/native-tool-failure-diagnostics-standalone.rkt').read_text()
        for phrase in ('(parameterize ([current-check-handler raise])',
                       "(check-equal? 'actual 'deliberately-wrong)",
                       '(check-eq? received original)', '(unique-info "location")',
                       '(unique-info "expression")'):
            self.assertIn(phrase, regression)
        for phrase in ('(check-eq? seen original)', '(check-eq? reraised original)',
                       '(display "cannot write" closed-output)',
                       "(raise 'diagnostic-output-token)", '(raise failure))])',
                       'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE',
                       'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check',
                       'output-failures-contained'):
            self.assertIn(phrase, regression)

    def test_passing_macro_bytes_and_debugger_source_assertions_preserved(self):
        macro = '      [(macro-stepper)' + self.tool.split('      [(macro-stepper)')[1].split('      [(teaching-tests)')[0]
        self.assertEqual(hashlib.sha256(macro.encode()).hexdigest(),
                         '0cf56eac6c88e29d530c21fa8cafacb1ece3d453e12fcab4a44545242548d83d')
        source = '       (define (assert-source!)' + self.tool.split('       (define (assert-source!)')[1].split('       (define mark-source')[0]
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         '172b71fbec2ff99f285eea1d68bf9be97dd1bb77726e9e0b89eb377e54aca882')
        self.assertIn("(if (memq which '(debugger teaching-tests))", self.tool)
        self.assertIn('(normalize-path raw-directory)\n        raw-directory)', self.tool)

    def test_source_traversal_has_one_twenty_second_launch_budget(self):
        debug = self.tool.split('      [(debugger)')[1].split('      [(macro-stepper)')[0]
        self.assertEqual(debug.count('20000.0'), 1)
        self.assertLess(debug.index('(define startup-deadline'), debug.index('(send debug command)'))
        self.assertEqual(debug.count('(remaining-seconds startup-deadline)'), 3)
        self.assertIn('(debug-stop-progressed? stop observed)', debug)
        self.assertIn('(loop next (add1 steps))', debug)
        self.assertIn('(check-true (send step is-shown?))', debug)
        self.assertIn('(emit "debugger-startup-stop"', debug)
        self.assertEqual(debug.count('(check-true (fixture-debug-stop? observed expected-file debugger-fixture))'), 2)
        teaching = self.tool.split('      [(teaching-tests)')[1]
        self.assertLess(teaching.index('(check-eq? located frame'), teaching.index('(send link-editor call-clickback'))
        self.assertLess(teaching.index('(valid-navigation? observed)'), teaching.index('(send frame change-to-tab tab)'))
        self.assertIn("'contents (send target get-text)", teaching)
        self.assertIn("'canonical_file (canonical-file-name (send target get-filename))", teaching)
        self.assertIn("'selection (list (send target get-start-position) (send target get-end-position))", teaching)

    def test_headless_source_contract_refuses_false_navigation_and_progress(self):
        helper = (ROOT/'tests/native-tool-source-contract.rkt').read_text()
        standalone = (ROOT/'tests/native-tool-source-contract-standalone.rkt').read_text()
        for phrase in ('(path-string? source)', '(with-handlers ([exn:fail? (lambda (_) #f)])',
                       "'canonical_source #f", '(exact-positive-integer? position)',
                       '(exact-positive-integer? span)', "'frame_endpoints #f",
                       "'(state top_mark current_mark)", "'canonical_file #f", "'contents #f",
                       "'selection #f", "'shown #f", "'canvas_matches #f", '(unless (> remaining 0)',
                       '(exact-nonnegative-integer? start)', '(exact-positive-integer? end)',
                       '(< start end)', '(<= end (string-length contents))'):
            self.assertIn(phrase, helper)
        for phrase in ('(parameterize ([current-check-handler raise])',
                       '"/elsewhere/source.rkt"', "(cons 'line 1)", "(cons 'column 1)",
                       "(cons 'position 0)", "(cons 'span 700)", "'pc 20", "'(19 24)",
                       "'diagnostic_time 99", "'(0 0)", "'(19 25)", "'(18 24)",
                       "'(bad 25)", "'(18 #f)", "'(18.0 25)", "'(18 25.0)",
                       "'(-1 25)", "'(18 18)", "'(25 18)", "'(18 100)",
                       '(remaining-seconds 20000 20000)', '(remaining-seconds 20000 20001)',
                       "(list #f 'generated '(not a path))", '"absent" "fixture.rkt"',
                       '(make-file-or-directory-link real alias)',
                       'OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals'):
            self.assertIn(phrase, standalone)
        self.assertNotIn('racket/gui', helper + standalone)

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
