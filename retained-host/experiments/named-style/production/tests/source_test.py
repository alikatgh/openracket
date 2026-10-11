#!/usr/bin/env python3
"""Portable checks only. Passing these never implies native Racket parity."""
from pathlib import Path
import ast
import copy
import difflib
import importlib.util
import json
import subprocess
import sys
import tempfile
import os
from unittest import mock
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import overlay
import prepare_native
import run_native

def delimiters(source):
    stack = []
    quoted = escaped = comment = False
    for n, ch in enumerate(source):
        if comment:
            if ch == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': quoted = False
            continue
        if ch == ';': comment = True
        elif ch == '"': quoted = True
        elif ch in '([{': stack.append((ch, n))
        elif ch in ')]}':
            if not stack or '([{'.index(stack[-1][0]) != ')]}'.index(ch):
                raise AssertionError('mismatched lexical delimiter at ' + str(n))
            stack.pop()
    if quoted or stack: raise AssertionError('unclosed lexical delimiter ' + str(stack[-1:]))

def form(source, needle):
    start = source.index(needle)
    stack = []
    quoted = escaped = comment = False
    for n in range(start, len(source)):
        ch = source[n]
        if comment:
            if ch == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': quoted = False
            continue
        if ch == ';': comment = True
        elif ch == '"': quoted = True
        elif ch in '([{': stack.append(ch)
        elif ch in ')]}':
            if not stack or '([{'.index(stack.pop()) != ')]}'.index(ch): raise AssertionError('bad form')
            if not stack: return source[start:n + 1]
    raise AssertionError('unterminated form')

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = overlay.stock_bytes()
        cls.candidate = overlay.candidate_bytes()
        cls.text = cls.candidate.decode()
        cls.lookup = form(cls.text, '(def/public (find-named-style ')

    def test_01_pinned_source_and_reproducible_overlay(self):
        self.assertEqual(overlay.sha256(self.stock), overlay.STOCK_SHA256)
        self.assertEqual((ROOT / 'overlay/style.rkt').read_bytes(), self.candidate)
        self.assertEqual(overlay.revert_bytes(self.candidate), self.stock)

    def test_02_modified_source_and_modified_candidate_refused(self):
        for bad in [self.stock + b'\n', self.stock.replace(b'get-s-join-style', b'get-s-join-shift-style')]:
            with self.assertRaises(ValueError): overlay.apply_bytes(bad)
        for bad in [self.candidate + b'\n', self.stock]:
            with self.assertRaises(ValueError): overlay.revert_bytes(bad)

    def test_03_patch_has_only_insertions(self):
        diff = list(difflib.unified_diff(self.stock.decode().splitlines(), self.text.splitlines()))
        self.assertFalse([x for x in diff if x.startswith('-') and not x.startswith('---')])
        self.assertEqual(len(overlay.INSERTIONS), 5)

    def test_04_only_exact_one_activates(self):
        self.assertIn('(equal? (getenv "OPENRACKET_NAMED_STYLE_INDEX") "1")', self.text)
        self.assertNotIn('(set! openracket-named-style-index-enabled?', self.text)
        self.assertEqual(run_native.MODES, [('unset', None), ('zero', '0'), ('unexpected', 'yes'), ('on', '1')])

    def test_05_stock_lookup_branch_is_exact(self):
        old = form(self.stock.decode(), '(def/public (find-named-style ')
        body = old[old.index('(for/or'): -1]
        self.assertIn(body, self.lookup)
        self.assertTrue(self.lookup.startswith('(def/public (find-named-style [string? name])'))
        disabled = self.lookup[self.lookup.index('(for/or'):]
        self.assertNotIn('set!', disabled)
        self.assertNotIn('hash-', disabled)

    def test_06_all_mutation_and_dispatch_forms_unchanged(self):
        for needle in ['(define (add-member ', '(define/public (do-named-style ', '(def/public (copy ',
                       '(def/public (convert ', '(def/public (new-named-style ', '(def/public (replace-named-style ',
                       '(def/public (style-has-new-child ', '(def/public (find-or-create-style ',
                       '(def/public (find-or-create-join-style ', '(def/public (style-was-changed ',
                       '(def/public (begin-style-change-sequence)', '(def/public (end-style-change-sequence)',
                       '(define/private (call-these-notifications ', '(def/public (notify-on-change ',
                       '(def/public (forget-notification ', '(def/public (set-base-style ',
                       '(def/public (set-shift-style ', '(define (read-styles-from-file ',
                       '(define (write-styles-to-file ']:
            self.assertEqual(form(self.stock.decode(), needle), form(self.text, needle), needle)

    def test_07_snapshot_eligibility_and_one_publication(self):
        self.assertIn('[snapshot members]', self.lookup)
        self.assertIn('[cached openracket-named-style-cache]', self.lookup)
        self.assertIn('(eq? snapshot (car cached))', self.lookup)
        self.assertEqual(self.text.count('(set! openracket-named-style-cache '), 1)
        self.assertIn('(define complete (cons snapshot index))', self.lookup)
        self.assertIn('(set! openracket-named-style-cache complete)', self.lookup)
        self.assertIn('(hash-ref (cdr entry) name #f)', self.lookup)
        self.assertNotIn('(cdr openracket-named-style-cache)', self.lookup)

    def test_08_immutable_first_winner_index(self):
        self.assertIn('(for/fold ([index (hash)]) ([style (in-list snapshot)])', self.lookup)
        self.assertIn('(not (hash-has-key? index style-name))', self.lookup)
        self.assertIn('(hash-set index style-name style)', self.lookup)
        for forbidden in ['make-hash', 'hash-set!', 'hash-clear!', 'hash-remove!', 'hash-ref!']:
            self.assertNotIn(forbidden, self.lookup)

    def test_09_no_query_retention_or_coercion(self):
        self.assertNotIn('(hash-set index name', self.lookup)
        self.assertNotIn('string->immutable-string', self.lookup)
        self.assertNotIn('string-copy', self.lookup)
        self.assertNotIn('(set! name', self.lookup)

    def test_10_no_locks_callbacks_timers_or_catches(self):
        for forbidden in ['semaphore', 'call-with', 'with-handlers', 'thread', 'current-', 'printf', 'display',
                          'openracket-test', 'parameterize-break', 'dynamic-send']:
            self.assertNotIn(forbidden, self.lookup)
        self.assertEqual(self.lookup.count('(send '), 2) # stock and candidate private get-s-name

    def test_11_private_diagnostics_and_export(self):
        self.assertIn('(define-local-member-name get-openracket-named-style-index-state)', self.text)
        self.assertIn('(define (openracket-named-style-index-state style-list)', self.text)
        self.assertIn('(send style-list get-openracket-named-style-index-state)', self.text)
        self.assertIn('         openracket-named-style-index-state\n', self.text)
        self.assertIn('         openracket-named-style-index-enabled?\n', self.text)

    def test_12_diagnostic_is_constant_work_payload_free_readonly(self):
        diagnostic = form(self.text, '(define/public (get-openracket-named-style-index-state)')
        for forbidden in ['set!', 'for/', 'in-list', 'find-named-style', 'get-s-name', 'hash-set', 'current-', 'length']:
            self.assertNotIn(forbidden, diagnostic)
        for key in ['enabled', 'lookups', 'hits', 'rebuilds', 'members-traversed', 'cache-valid', 'named-entries', 'member-count']:
            self.assertIn("'" + key, diagnostic)
        self.assertIn('(hash-count (cdr cached))', diagnostic)

    def test_13_rebuild_counter_after_publication_visits_before(self):
        self.assertLess(self.lookup.index('(set! openracket-named-style-cache complete)'),
                        self.lookup.index('(set! openracket-named-style-rebuilds'))
        self.assertLess(self.lookup.index('(set! openracket-named-style-members-traversed'),
                        self.lookup.index('(define complete'))

    def test_14_name_and_members_source_invariants(self):
        self.assertEqual(self.stock.count(b'(set! members '), 2)
        self.assertEqual(self.candidate.count(b'(set! members '), 2)
        self.assertIn(b'[name (string->immutable-string name)]', self.stock)
        naming = form(self.stock.decode(), '(define/public (do-named-style ')
        self.assertLess(naming.index('(send style s-update'), naming.index('(add-member style)'))
        self.assertIn('(send s get-s-join-style)', self.text)

    def test_15_full_native_modules_are_actual_complete_forms(self):
        with tempfile.TemporaryDirectory() as t:
            prefs = Path(t) / 'prefs.rkt'
            prefs.write_bytes((ROOT / 'vendor/prefs.rkt').read_bytes())
            destination = Path(t) / 'staged'
            manifest = prepare_native.stage(destination, prefs)
            self.assertFalse(manifest['native_executed'])
            self.assertEqual((destination / 'stock/style.rkt').read_bytes(), self.stock)
            self.assertEqual((destination / 'candidate/style.rkt').read_bytes(), self.candidate)
            self.assertEqual((destination / 'candidate/prefs.rkt').read_bytes(), prefs.read_bytes())
            with self.assertRaises(FileExistsError): prepare_native.stage(destination, prefs)

    def test_15b_changed_dependency_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as t:
            prefs = Path(t) / 'prefs.rkt'
            prefs.write_bytes((ROOT / 'vendor/prefs.rkt').read_bytes() + b'\n')
            destination = Path(t) / 'staged'
            with self.assertRaises(ValueError): prepare_native.stage(destination, prefs)
            self.assertFalse(destination.exists())

    def test_16_only_test_fixture_has_publication_hook(self):
        hooked = prepare_native.hooked_bytes(self.candidate)
        restored = hooked.replace(prepare_native.HOOK_CALL, b'').replace(prepare_native.HOOK_DECL + b'\n', b'')
        self.assertEqual(restored, self.candidate)
        self.assertNotIn(b'openracket-test-before-publication', self.candidate)
        self.assertIn(prepare_native.HOOK_CALL + prepare_native.HOOK_ANCHOR, hooked)

    def test_17_racket_source_lexical_delimiters(self):
        for source in [self.stock.decode(), self.text, prepare_native.hooked_bytes(self.candidate).decode()]:
            delimiters(source)
        for path in (ROOT / 'tests/native').glob('*.rkt'): delimiters(path.read_text())

    def test_18_native_identity_contract_and_reentry_coverage(self):
        native = (ROOT / 'tests/native/differential.rkt').read_text()
        for token in ['identical', 'oracle', 'mutable query', 'wrong type still raises contract',
                      '"λ"', '""', '"Basic"', 'copy-convert', 'replace preserves identity',
                      'do-named-style does not dispatch', 'duplicate-notifications', 'get-s-join-style',
                      'duplicate-after-reorder', 'shift-after-reorder', 'nested batching',
                      'notification-error', 'self-removing callback']:
            self.assertIn(token, native)

    def test_19_native_interruption_publication_coverage(self):
        native = (ROOT / 'tests/native/publication.rkt').read_text()
        for token in ['reentrant newer build', 'old captured list', "'(raise escape)",
                      'call-with-composable-continuation', 'resumed stale cache',
                      'make-custodian', 'sync/timeout', 'thread-dead-evt', 'custodian-shutdown-all',
                      'concurrent stale publication', 'no partial table']:
            self.assertIn(token, native)

    def test_20_native_runner_never_part_of_source_execution(self):
        parsed = ast.parse(Path(__file__).read_text())
        calls = [n for n in ast.walk(parsed) if isinstance(n, ast.Call)]
        self.assertFalse([n for n in calls if isinstance(n.func, ast.Attribute)
                          and isinstance(n.func.value, ast.Name)
                          and n.func.value.id == 'subprocess'
                          and n.func.attr in ['run', 'Popen', 'call', 'check_call', 'check_output']])
        self.assertFalse((ROOT / 'reports/native.json').exists())

    def test_21_python_source_compiles_without_running_racket(self):
        for folder in ['scripts', 'tests']:
            for path in (ROOT / folder).glob('*.py'): ast.parse(path.read_text(), filename=str(path))

class ValidatorTests(unittest.TestCase):
    def evidence(self):
        out = {}
        for mode, flag in run_native.MODES:
            on = flag == '1'
            out[mode] = {'schema': 'openracket-named-style-native-v1', 'mode': mode, 'passed': True,
                         'checks': 200, 'scenario-count': 12, 'observations': [['identity', [1, 2, 3]]],
                         'diagnostics': {'enabled': on, 'lookups': 4 if on else 0, 'hits': 2 if on else 0,
                           'rebuilds': 2 if on else 0, 'members-traversed': 3 if on else 0,
                           'cache-valid': on, 'named-entries': 2 if on else 0, 'member-count': 2}}
        return out

    def test_22_nonvacuous_fixture_accepted(self):
        self.assertTrue(run_native.validate_modes(self.evidence()))

    def test_23_each_missing_mode_refused(self):
        for mode, _ in run_native.MODES:
            value = self.evidence(); del value[mode]
            with self.assertRaises(ValueError): run_native.validate_modes(value)

    def test_24_wrong_duplicate_identity_rejected(self):
        value = self.evidence(); value['on']['observations'][0][1][0] = 2
        with self.assertRaises(ValueError): run_native.validate_modes(value)

    def test_25_missing_counter_activity_refused(self):
        for key in ['lookups', 'hits', 'rebuilds', 'members-traversed', 'named-entries']:
            value = self.evidence(); value['on']['diagnostics'][key] = 0
            with self.assertRaises(ValueError): run_native.validate_modes(value)

    def test_26_disabled_index_activity_refused(self):
        for mode in ['unset', 'zero', 'unexpected']:
            value = self.evidence(); value[mode]['diagnostics']['rebuilds'] = 1
            with self.assertRaises(ValueError): run_native.validate_modes(value)

    def test_27_activation_trace_and_vacuity_refused(self):
        for key, bad in [('passed', False), ('checks', 0), ('scenario-count', 0), ('observations', []), ('schema', 'wrong')]:
            value = self.evidence(); value['on'][key] = bad
            with self.assertRaises(ValueError): run_native.validate_modes(value)
        value = self.evidence(); value['on']['diagnostics']['enabled'] = False
        with self.assertRaises(ValueError): run_native.validate_modes(value)

class ApplierTests(unittest.TestCase):
    def make_runtime(self, root):
        target = root / 'collects/racket/snip/private/style.rkt'
        target.parent.mkdir(parents=True)
        target.write_bytes(overlay.stock_bytes())
        target.with_name('prefs.rkt').write_bytes((ROOT / 'vendor/prefs.rkt').read_bytes())
        return target

    def test_28_canonical_temp_apply_verify_revert_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            # macOS temporary roots can themselves be exposed through aliases.
            root = Path(tmp).resolve()
            target = self.make_runtime(root)
            self.assertEqual(overlay.operate('verify', root, target)['status'], 'stock')
            result = overlay.operate('apply', root, target, disposable=True)
            self.assertTrue(result['changed'])
            self.assertEqual(target.read_bytes(), overlay.candidate_bytes())
            self.assertFalse(overlay.operate('apply', root, target, disposable=True)['changed'])
            self.assertEqual(overlay.operate('verify', root, target)['status'], 'candidate')
            self.assertTrue(overlay.operate('revert', root, target, disposable=True)['changed'])
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())
            self.assertFalse(overlay.operate('revert', root, target, disposable=True)['changed'])

    def test_29_explicit_disposable_acknowledgement_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); target = self.make_runtime(root)
            for action in ['apply', 'revert']:
                with self.assertRaises(ValueError): overlay.operate(action, root, target)
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())

    def test_30_root_ancestor_alias_refused_even_with_canonical_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve(); root = base / 'real'; root.mkdir()
            target = self.make_runtime(root)
            alias = base / 'alias'; alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError): overlay.operate('apply', alias, target, disposable=True)
            with self.assertRaises(ValueError): overlay.operate('apply', alias / 'collects', target, disposable=True)
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())

    def test_31_target_ancestor_alias_and_file_alias_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); target = self.make_runtime(root)
            alias = root / 'alias'; alias.symlink_to(root / 'collects', target_is_directory=True)
            with self.assertRaises(ValueError):
                overlay.operate('apply', root, alias / 'racket/snip/private/style.rkt', disposable=True)
            alias_file = target.with_name('alias.rkt'); alias_file.symlink_to(target)
            with self.assertRaises(ValueError): overlay.operate('apply', root, alias_file, disposable=True)
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())

    def test_32_hardlink_outside_root_and_wrong_suffix_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve(); root = base / 'runtime'; root.mkdir()
            target = self.make_runtime(root)
            elsewhere = base / 'elsewhere'; elsewhere.mkdir()
            other = self.make_runtime(elsewhere)
            with self.assertRaises(ValueError): overlay.operate('apply', root, other, disposable=True)
            wrong = target.with_name('wrong.rkt'); wrong.write_bytes(overlay.stock_bytes())
            with self.assertRaises(ValueError): overlay.operate('apply', root, wrong, disposable=True)
            os.link(target, target.with_name('hardlink.rkt'))
            with self.assertRaises(ValueError): overlay.operate('apply', root, target, disposable=True)
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())

    def test_33_sibling_dependency_change_or_alias_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); target = self.make_runtime(root)
            prefs = target.with_name('prefs.rkt'); prefs.write_bytes(prefs.read_bytes() + b'\n')
            with self.assertRaises(ValueError): overlay.operate('apply', root, target, disposable=True)
            prefs.unlink(); prefs.symlink_to((ROOT / 'vendor/prefs.rkt').resolve())
            with self.assertRaises(ValueError): overlay.operate('apply', root, target, disposable=True)
            self.assertEqual(target.read_bytes(), overlay.stock_bytes())

class RunnerFailureTests(unittest.TestCase):
    def positive(self, mode):
        data = ValidatorTests().evidence()[mode]
        return {'command': ['fake'], 'returncode': 0, 'stdout': json.dumps(data) + '\n',
                'stderr': '', 'timed_out': False, 'launched': True}

    def test_34_counts_reject_boolean_float_negative_or_string(self):
        for key in ['checks', 'scenario-count']:
            for value in [True, 200.0, -1, '200']:
                evidence = ValidatorTests().evidence(); evidence['on'][key] = value
                with self.assertRaises(ValueError): run_native.validate_modes(evidence)
        for key in ['lookups', 'hits', 'rebuilds', 'members-traversed', 'named-entries', 'member-count']:
            for value in [True, 2.0, -1, '2']:
                evidence = ValidatorTests().evidence(); evidence['on']['diagnostics'][key] = value
                with self.assertRaises(ValueError): run_native.validate_modes(evidence)

    def test_35_timeout_retains_command_and_partial_output(self):
        timeout = subprocess.TimeoutExpired(['fake-racket'], 120, output=b'partial stdout', stderr=b'partial stderr')
        with mock.patch.object(run_native.subprocess, 'run', side_effect=timeout):
            result = run_native.command_result(['fake-racket'], {}, 120)
        self.assertTrue(result['timed_out'])
        self.assertTrue(result['launched'])
        self.assertEqual(result['command'], ['fake-racket'])
        self.assertEqual(result['stdout'], 'partial stdout')
        self.assertEqual(result['stderr'], 'partial stderr')
        with self.assertRaises(ValueError): run_native.last_json(result)

    def test_36_launch_failure_is_not_claimed_as_execution(self):
        with mock.patch.object(run_native.subprocess, 'run', side_effect=FileNotFoundError('not installed')):
            result = run_native.command_result(['fake-racket'], {}, 120)
        self.assertFalse(result['launched'])
        self.assertIn('not installed', result['error'])

    def test_37_failed_first_mode_keeps_other_modes_and_terminal_fail(self):
        outputs = [{'command': ['fake'], 'returncode': None, 'stdout': 'partial', 'stderr': 'timed out',
                    'timed_out': True, 'launched': True}]
        outputs.extend(self.positive(mode) for mode in ['zero', 'unexpected', 'on'])
        outputs.append({'command': ['fake'], 'returncode': 0, 'stdout': json.dumps({
                        'schema': 'openracket-named-style-publication-v1', 'passed': True, 'checks': 40}),
                        'stderr': '', 'timed_out': False, 'launched': True})
        outputs.append({'command': ['fake'], 'returncode': 1, 'stdout': '',
                        'stderr': run_native.NEGATIVE_INJECTION + '\n' + run_native.NEGATIVE_ERROR + '\n',
                        'timed_out': False, 'launched': True})
        report = {'passed': False, 'native_executed': False, 'errors': [], 'runs': {}}
        with mock.patch.object(run_native, 'command_result', side_effect=outputs) as execute:
            run_native.execute_prepared(report, 'fake-racket', Path('/unused'))
        self.assertEqual(execute.call_count, 6)
        self.assertEqual(set(report['runs']), {'unset', 'zero', 'unexpected', 'on', 'publication', 'negative-control'})
        self.assertFalse(report['passed'])
        self.assertEqual(report['runs']['unset']['stdout'], 'partial')
        self.assertIn('validation_error', report['runs']['unset'])
        self.assertTrue(report['runs']['negative-control']['expected_failure_observed'])

    def test_38_json_parse_error_retained_as_independent_run_failure(self):
        report = {'runs': {}, 'errors': [], 'native_executed': False}
        result = {'returncode': 0, 'stdout': '{bad json', 'stderr': 'diagnostic', 'launched': True}
        with mock.patch.object(run_native, 'command_result', return_value=result):
            self.assertIsNone(run_native.collect_run(report, 'on', ['fake'], {}, 120))
        self.assertIn('validation_error', report['runs']['on'])
        self.assertEqual(report['runs']['on']['stderr'], 'diagnostic')
        self.assertTrue(report['errors'])

    def test_39_negative_control_rejects_false_success_timeout_and_no_marker(self):
        for result in [{'returncode': 0, 'stdout': '', 'stderr': 'negative-control-wrong-object-identity'},
                       {'returncode': 1, 'stdout': '', 'stderr': 'unrelated'},
                       {'returncode': 1, 'stdout': '', 'stderr': 'negative-control-wrong-object-identity', 'timed_out': True},
                       {'returncode': 1, 'stdout': '{}', 'stderr': 'negative-control-wrong-object-identity'}]:
            report = {'runs': {}, 'errors': [], 'native_executed': False}
            with mock.patch.object(run_native, 'command_result', return_value=result):
                run_native.collect_run(report, 'negative', ['fake'], {}, 120, negative=True)
            self.assertTrue(report['errors'])
            self.assertFalse(report['runs']['negative']['expected_failure_observed'])

class ExactNegativeControlTests(unittest.TestCase):
    def evidence(self):
        return {'returncode': 1, 'stdout': '', 'stderr': run_native.NEGATIVE_INJECTION + '\n'
                + run_native.NEGATIVE_ERROR + '\n  context...:\n   test-context\n',
                'timed_out': False, 'launched': True}

    def test_40_exact_positive_exit_and_unique_injected_error_accepted(self):
        self.assertTrue(run_native.negative_control_passed(self.evidence()))
        native = (ROOT / 'tests/native/differential.rkt').read_text()
        self.assertEqual(native.count(run_native.NEGATIVE_INJECTION), 1)
        self.assertLess(native.index(run_native.NEGATIVE_INJECTION),
                        native.index('"negative-control-wrong-object-identity"'))
        self.assertNotIn(run_native.NEGATIVE_INJECTION, overlay.candidate_bytes().decode())

    def test_41_signals_zero_noninteger_launch_and_timeout_refused(self):
        for exit_code in [-9, -15, 0, None, True, 1.0, '1']:
            result = self.evidence(); result['returncode'] = exit_code
            self.assertFalse(run_native.negative_control_passed(result))
        for key, value in [('timed_out', True), ('launched', False), ('error', 'launch failed')]:
            result = self.evidence(); result[key] = value
            self.assertFalse(run_native.negative_control_passed(result))

    def test_42_altered_operands_prefix_suffix_and_loose_substrings_refused(self):
        for replacement in [run_native.NEGATIVE_ERROR.replace('#f != #t', '#t != #f'),
                            run_native.NEGATIVE_ERROR.replace('#f != #t', '#f != #f'),
                            run_native.NEGATIVE_ERROR.replace('#f != #t', '0 != 1'),
                            'prefix ' + run_native.NEGATIVE_ERROR,
                            run_native.NEGATIVE_ERROR + ' suffix',
                            'negative-control-wrong-object-identity']:
            result = self.evidence(); result['stderr'] = result['stderr'].replace(run_native.NEGATIVE_ERROR, replacement)
            self.assertFalse(run_native.negative_control_passed(result))

    def test_43_duplicate_exact_or_embedded_injection_or_error_refused(self):
        for extra in [run_native.NEGATIVE_INJECTION, 'prefix ' + run_native.NEGATIVE_INJECTION,
                      run_native.NEGATIVE_ERROR, run_native.NEGATIVE_ERROR.replace('#t', '#f')]:
            for stream in ['stdout', 'stderr']:
                result = self.evidence(); result[stream] += '\n' + extra
                self.assertFalse(run_native.negative_control_passed(result))

    def test_44_missing_wrong_stream_or_reordered_marker_refused(self):
        for text in [run_native.NEGATIVE_ERROR + '\n',
                     run_native.NEGATIVE_INJECTION + '\n',
                     run_native.NEGATIVE_ERROR + '\n' + run_native.NEGATIVE_INJECTION + '\n',
                     'prefix ' + run_native.NEGATIVE_INJECTION + '\n' + run_native.NEGATIVE_ERROR]:
            result = self.evidence(); result['stderr'] = text
            self.assertFalse(run_native.negative_control_passed(result))
        result = self.evidence(); result['stdout'] = result['stderr']; result['stderr'] = ''
        self.assertFalse(run_native.negative_control_passed(result))

    def test_45_success_or_partial_json_contamination_refused_in_either_stream(self):
        for text in ['{"passed": true}', '  {"passed": true}',
                     'prefix {"schema":"openracket-named-style-native-v1","passed":true}',
                     '{}', '  {incomplete-success-record']:
            for stream in ['stdout', 'stderr']:
                result = self.evidence(); result[stream] += '\n' + text
                self.assertFalse(run_native.negative_control_passed(result))

if __name__ == '__main__':
    unittest.main(verbosity=2)
