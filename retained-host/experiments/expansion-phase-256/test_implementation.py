#!/usr/bin/env python3
"""Source-boundary and real-place protocol tests; no GUI or real DrRacket expansion."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from inspect_contract import sources
from prepare import transform_language, transform_worker, READY, registry_capture_expression, PINS

HERE = Path(__file__).resolve().parent
RACKET = Path(os.environ.get('REPLAY_TEST_RACKET', '/workspace/shared/racket-toolchain/racket/bin/racket'))
HOST = Path('/workspace/shared/openracket-drracket-host')

def env():
    result = dict(os.environ)
    result['PLTUSERHOME'] = str(Path(os.environ.get('REPLAY_TEST_PROFILE', str(HOST / 'profile'))).resolve())
    for k in list(result):
        if k.startswith('OPENRACKET_'):
            result.pop(k)
    return result

def core_sources():
    """CI uses pinned installed pristine sources; local archive evidence is optional."""
    explicit = os.environ.get('REPLAY_TEST_SOURCE_DIR')
    if explicit:
        root = Path(explicit).resolve()
        result = {}
        for name, expected in PINS.items():
            data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'Official 9.3 source pin mismatch: {root / name}')
            result['drracket/private/' + name] = data.decode('utf-8')
        return result
    packages, _ = sources(HOST)
    return {key: packages['drracket-core-lib'][key]
            for key in ('drracket/private/module-language.rkt', 'drracket/private/expanding-place.rkt')}

class SourceBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = core_sources()

    def test_explicit_source_directory_uses_pins_without_opening_cached_archives(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for name in PINS:
                (Path(directory) / name).write_text(self.core['drracket/private/' + name])
            with mock.patch.dict(os.environ, {'REPLAY_TEST_SOURCE_DIR': directory}), \
                 mock.patch.object(sys.modules[__name__], 'sources', side_effect=AssertionError('Archive access is forbidden in this test')):
                self.assertEqual(core_sources(), self.core)

    def test_changed_explicit_source_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for name in PINS:
                (Path(directory) / name).write_text(self.core['drracket/private/' + name])
            with (Path(directory) / 'expanding-place.rkt').open('a') as out:
                out.write('\n; modified source\n')
            with mock.patch.dict(os.environ, {'REPLAY_TEST_SOURCE_DIR': directory}):
                with self.assertRaisesRegex(ValueError, 'source pin mismatch'):
                    core_sources()

    def test_explicit_test_profile_is_used(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            with mock.patch.dict(os.environ, {'REPLAY_TEST_PROFILE': directory}):
                self.assertEqual(env()['PLTUSERHOME'], str(Path(directory).resolve()))

    def test_previous_terminal_released_only_at_replacement_response_and_objects_survive_cleanup(self):
        text = (HERE / 'replay.rkt').read_text()
        release = text[text.index('(define (release-prior!)'):text.index('(define (hold-capabilities!')]
        self.assertIn('(set! last-terminal #f)', release)
        self.assertEqual(text.count('(set! last-terminal #f)'), 1)
        cleanup = text.index('(define cleaned? (cleanup!))')
        sink = text.index('(void/reference-sink last-terminal previous-capabilities current-capabilities)', cleanup)
        self.assertGreater(sink, cleanup)
        self.assertIn('(only-in ffi/unsafe void/reference-sink)', text)
        self.assertIn('(set! current-capabilities capabilities)', text)
        self.assertIn('(when terminal (set! last-terminal terminal))', text)
        self.assertIn('(unless first-response? (set! previous-capabilities capabilities))', text)

    def test_worker_has_only_one_guarded_insertion(self):
        original = self.core['drracket/private/expanding-place.rkt']
        patched = transform_worker(original)
        self.assertEqual(patched.replace(READY, '', 1), original)
        self.assertIn('(when (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")', READY)
        self.assertNotIn('OPENRACKET_EXPANSION_CAPTURE', READY.split('\n', 1)[1])

    def test_missing_and_duplicate_anchors_fail_closed(self):
        for text in ['', '  (let loop ([current-job #f]\n' * 2]:
            with self.assertRaises(ValueError):
                transform_worker(text)

    def test_caller_captures_exact_values_before_original_send(self):
        patched = transform_language(self.core['drracket/private/module-language.rkt'])
        self.assertEqual(patched.count("'capture-registry!"), 1)
        self.assertEqual(patched.count("'capture-request!"), 1)
        self.assertEqual(patched.count("'capture-result!"), 1)
        self.assertEqual(patched.count("'capture-status!"), 1)
        self.assertNotIn('OPENRACKET_EXPANSION_REPLAY', patched)
        self.assertLess(patched.index("'capture-request!"), patched.index('(place-channel-put expanding-place to-send)'))

    @unittest.skipUnless(RACKET.is_file(), 'Native Racket gate required; executable unavailable')
    def test_generated_modules_are_reader_valid_without_instantiation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for name, transform in [('module-language.rkt', transform_language), ('expanding-place.rkt', transform_worker)]:
                path = Path(directory) / name
                path.write_text(transform(self.core['drracket/private/' + name]))
                code = f'(parameterize ([read-accept-reader #t]) (call-with-input-file {json.dumps(str(path))} (lambda (in) (void (read-syntax \'test in)))))'
                subprocess.run([str(RACKET), '-e', code], env=env(), check=True, timeout=10, capture_output=True)

    @unittest.skipUnless(RACKET.is_file(), 'Native Racket gate required; executable unavailable')
    def test_disabled_worker_boundary_never_loads_support_or_uses_channels(self):
        program = '''#lang racket/base
(define calls 0)
(define (getenv key) #f)
(define (dynamic-require . args) (set! calls (add1 calls)) (error 'disabled "support was loaded"))
(define p #f)
(define (preferences:get . args) (error 'disabled "preferences were queried"))
''' + READY + '''(unless (= calls 0) (error 'disabled "unexpected observer activity"))
(displayln "flag-off boundary passed")
'''
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / 'disabled.rkt'
            path.write_text(program)
            result = subprocess.run([str(RACKET), str(path)], env=env(), check=True, timeout=10, capture_output=True, text=True)
            self.assertIn('flag-off boundary passed', result.stdout)

    @unittest.skipUnless(RACKET.is_file(), 'Native Racket gate required; executable unavailable')
    def test_disabled_capture_returns_actual_registry_without_observer_or_preferences_calls(self):
        patched = transform_language(self.core['drracket/private/module-language.rkt'])
        start = patched.index('               (define openracket-capture-request-id')
        end = patched.index('               (place-channel-put expanding-place to-send)', start)
        request_observer = patched[start:end]
        program = '''#lang racket/base
(require racket/list)
(define (getenv key) #f)
(define (dynamic-require . args) (error 'disabled "capture helper loaded"))
(define (preferences:get . args) (error 'disabled "capture preferences queried"))
(define handlers (list (list 'handler-module 'go #f) (list 'handler-module 'monitor #t)))
(define (drracket:module-language-tools:get-online-expansion-handlers) handlers)
(define drracket:module-language-tools:online-expansion-handler-mod-path first)
(define drracket:module-language-tools:online-expansion-handler-id second)
(define drracket:module-language-tools:online-expansion-handler-monitor? third)
(define registry ''' + registry_capture_expression() + ''')
(define to-send (vector-immutable 'snapshot 'source 'response 'settings 'status 'files))
''' + request_observer + '''
(unless (equal? registry handlers) (error 'disabled "actual registry changed"))
(unless (not openracket-capture-request-id) (error 'disabled "capture selected a request"))
(displayln "flag-off capture boundary passed")
'''
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / 'disabled-capture.rkt'
            path.write_text(program)
            run = subprocess.run([str(RACKET), str(path)], env=env(), check=True, timeout=10, capture_output=True, text=True)
            self.assertIn('flag-off capture boundary passed', run.stdout)

@unittest.skipUnless(RACKET.is_file(), 'Native real-place gates required; executable unavailable')
class RealPlaceProtocol(unittest.TestCase):
    def run_mode(self, mode, trials=1):
        directory = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        capture, output = root / 'capture', root / 'output'
        e = env()
        subprocess.run([str(RACKET), str(HERE / 'make-mock-capture.rkt'), str(capture)],
                       cwd=HERE, env=e, check=True, timeout=10, capture_output=True)
        e.update({'OPENRACKET_EXPANSION_REPLAY': '1', 'OPENRACKET_REPLAY_MOCK_MODE': mode,
                  'OPENRACKET_REPLAY_SUPPORT': str(HERE / 'support.rkt'),
                  'OPENRACKET_REPLAY_CONFIG': json.dumps({'capture': str(capture / 'capture.rktd'),
                    'output': str(output), 'trials': trials, 'init_timeout_seconds': 3,
                    'terminal_timeout_seconds': .15 if mode in ('timeout', 'second-no-response') else 3,
                    'cleanup_timeout_seconds': 1})})
        run = subprocess.run([str(RACKET), str(HERE / 'replay.rkt')], cwd=HERE, env=e,
                             capture_output=True, text=True, timeout=12)
        if not (output / 'replay.json').exists():
            self.fail(run.stdout + run.stderr)
        return run, json.loads((output / 'replay.json').read_text())

    def test_cold_and_warm_terminal_results_with_live_capabilities(self):
        run, report = self.run_mode('success', 2)
        self.assertEqual(run.returncode, 0, run.stderr + json.dumps(report))
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(len(report['trials']), 2)
        for row in report['trials']:
            self.assertIn('process_cpu_counter_ms_all_places', row['before'])
            self.assertIn('managed_bytes_observed_from_root', row['before'])
            self.assertIn('gc_counter_ms_observed_from_root', row['before'])
            self.assertNotIn('root_place_cpu_counter_ms', row['before'])
            self.assertIn('gc_counter_delta_ms_observed_from_worker', row)
            self.assertEqual(row['outcome'], 'handler-results')
            self.assertGreaterEqual(row['elapsed_ms'], 25)
            self.assertEqual(row['monitor_messages'], 1)
            self.assertEqual(row['retained_capabilities'], 1)
            self.assertEqual(row['retained_place_channels'], 1)
            self.assertTrue(row['terminal_summary_matches_integrated_capture'])
            self.assertTrue(row['worker_gc']['worker_clock_within_root_query'])
        self.assertFalse(report['trials'][0]['prior_terminal_retained_before_request'])
        self.assertTrue(report['trials'][1]['prior_terminal_retained_before_request'])
        self.assertEqual(report['trials'][1]['prior_capabilities_retained_before_request'], 1)
        self.assertEqual(report['trials'][1]['prior_place_channels_retained_before_request'], 1)
        self.assertEqual(report['last_place_channels_retained_until_cleanup'], 1)
        self.assertTrue(report['actual_worker_memory_accounting_available'])
        self.assertTrue(report['cleanup']['place_dead'])

    def test_explicit_abnormal_terminal_is_observed_not_hidden(self):
        run, report = self.run_mode('abnormal')
        self.assertEqual(run.returncode, 0, run.stderr + json.dumps(report))
        row = report['trials'][0]
        self.assertEqual(row['outcome'], 'abnormal-termination')
        self.assertTrue(row['terminal']['explicit_out_of_memory'])
        self.assertFalse(row['terminal_summary_matches_integrated_capture'])

    def test_finished_expansion_without_terminal_times_out(self):
        run, report = self.run_mode('timeout')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(report['trials'][0]['outcome'], 'supervisor_interval_timeout')
        self.assertEqual(report['trials'][0]['statuses'], ['finished-expansion'])
        self.assertTrue(report['cleanup']['place_dead'])

    def test_place_death_is_distinct_from_stock_abnormal_terminal(self):
        run, report = self.run_mode('death')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(report['trials'][0]['outcome'], 'worker_place_died')
        self.assertTrue(report['cleanup']['place_dead'])

    def test_second_request_without_any_response_retains_previous_result_through_cleanup(self):
        for mode, outcome in [('second-no-response', 'supervisor_interval_timeout'),
                              ('second-death-no-response', 'worker_place_died')]:
            with self.subTest(mode=mode):
                run, report = self.run_mode(mode, 2)
                self.assertEqual(run.returncode, 1)
                self.assertEqual(report['trials'][0]['outcome'], 'handler-results')
                second = report['trials'][1]
                self.assertEqual(second['outcome'], outcome)
                self.assertEqual(second['statuses'], [])
                self.assertEqual(second['monitor_messages'], 0)
                self.assertTrue(second['prior_terminal_retained_before_request'])
                self.assertEqual(second['prior_capabilities_retained_before_request'], 1)
                self.assertTrue(report['last_terminal_retained_until_cleanup'])
                self.assertEqual(report['last_capabilities_retained_until_cleanup'], 1)
                self.assertEqual(second['prior_place_channels_retained_before_request'], 1)
                self.assertEqual(report['last_place_channels_retained_until_cleanup'], 1)
                self.assertTrue(report['cleanup']['place_dead'])

    def test_malformed_cleanup_acknowledgement_fails_acceptance_but_other_cleanup_runs(self):
        run, report = self.run_mode('cleanup-wrong')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(report['status'], 'cleanup_failed')
        self.assertFalse(report['cleanup']['control_stopped'])
        self.assertTrue(report['cleanup']['place_dead'])
        self.assertTrue(report['cleanup']['root_logger_stopped'])
        self.assertTrue(report['cleanup']['diagnostic_custodian_shutdown'])

    def test_missing_cleanup_acknowledgement_fails_acceptance_and_kills_place(self):
        run, report = self.run_mode('cleanup-missing')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(report['status'], 'cleanup_failed')
        self.assertFalse(report['cleanup']['control_stopped'])
        self.assertTrue(report['cleanup']['place_dead'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
