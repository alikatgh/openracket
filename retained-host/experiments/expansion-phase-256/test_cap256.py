"""Portable cap/weak-service/acceptance contracts; no local native GUI runs."""
import contextlib
import io
import sys
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import accept_completed as accept
import capture
import prepare_phase

HERE = Path(__file__).resolve().parent
HELPER_PIN = '9b761799e61b45388ae21461d358a819274ae1923e88959351a9f9b46337abc0'
WRAPPER_PIN = '9bb3dc30255a4effca1a91f2f407e0af3ae0fce298f2fc20ed823544176daddb'


def evidence():
    monitor = dict(check_syntax_monitor_registry_entries=1, messages=1, trace_batches=1,
                   trace_entries=5, rename_capability_rows=1, error_messages=0, invalid_payloads=0)
    capture_row = dict(status='terminal_observed', actual_child_limit_bytes=accept.CAP,
                       terminal={'tag': 'handler-results'}, monitor_evidence=monitor,
                       snapshot_sha256='a' * 64, registry_sha256='b' * 64)
    host = dict(status='terminal_captured', preserved_preferences=dict(child_limit_bytes=accept.CAP, online_compilation=True, coloring=True))
    capture_sup = dict(memory_profile_setup={'verified': True}, expected_memory_limit_bytes=accept.CAP,
                       gui_started=True, exit_code=0, timeout=False, cleanup={'complete': True})
    replay = dict(status='complete', cleanup={'accepted': True}, actual_worker_child_limit_bytes=accept.CAP,
                  phase_probe_enabled=True, actual_worker_memory_accounting_available=True, snapshot_sha256='a' * 64, registry_sha256='b' * 64,
                  last_terminal_retained_until_cleanup=True, last_place_channels_retained_until_cleanup=1, trials=[])
    for i in (1, 2):
        probe = dict(trial=i, job_generation=i, active=False, phase_points_dropped=0,
                     sample_ticks_dropped=0, input_events_dropped=0, stale_events_discarded=0,
                     phase_points=[dict(phase=label, trial=i, job_generation=i, source_metrics={'monotonic_ms': 10}) for label in accept.REQUIRED_PHASES],
                     attribution_evidence=dict(status='coarse_thread_context_available', working_thread_registered=True,
                                               monitor_thread_registered=True, xref_service_thread_registered=True,
                                               usable_monitor_frames=True, usable_xref_frames=True),
                     xref_service_registration={'status': 'registered_existing_service_thread', 'source_sha256': accept.XREF_PIN}, stock_logger_subscription=False)
        replay['trials'].append(dict(trial=i, outcome='handler-results', terminal={'tag': 'handler-results'},
                                     terminal_summary_matches_integrated_capture=True, monitor_evidence=monitor,
                                     phase_probe=probe, prior_terminal_retained_before_request=i == 2,
                                     retained_place_channels=1, prior_place_channels_retained_before_request=1 if i == 2 else 0))
    return [capture_row, host, capture_sup, replay, dict(status='ok', cleanup={'complete': True}, hard_wall_budget_seconds=157.0)]


class Cap256Contracts(unittest.TestCase):
    def test_reviewed_profile_helpers_are_byte_identical(self):
        for name, pin in [('memory-profile.rkt', HELPER_PIN), ('profile_setup.py', WRAPPER_PIN)]:
            self.assertEqual(hashlib.sha256((HERE / name).read_bytes()).hexdigest(), pin)

    def test_profile_setup_precedes_marker_and_gui_and_is_only256(self):
        source = (HERE / 'capture.py').read_text()
        self.assertLess(source.index('setup = prepare_memory_profile'), source.index("(profile / 'openracket-diagnostic-profile').write_text"))
        self.assertLess(source.index("if not setup['verified']"), source.index('subprocess.Popen(command'))
        self.assertIn('memory_limit_mib=256', source)
        self.assertIn("'PLTADDONDIR': str(output / 'addon')", source)
        self.assertIn('process.wait(timeout=190)', source)
        self.assertIn('90000', (HERE / 'capture-host.rkt').read_text())

    def test_failed_setup_never_creates_marker_or_starts_gui(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fixture = root / 'fixture.rkt'
            fixture.write_bytes(b'a' * 1048576)
            output = root / 'capture'
            def setup(args, env, directory, terminate):
                self.assertEqual(args.memory_limit_mib, 256)
                self.assertEqual(list(Path(env['PLTUSERHOME']).iterdir()), [])
                self.assertEqual(Path(env['PLTADDONDIR']), output / 'addon')
                return {'verified': False, 'errors': ['controlled setup failure']}
            with mock.patch.object(capture, 'BASE_SHA256', hashlib.sha256(fixture.read_bytes()).hexdigest()), \
                 mock.patch.object(capture, 'prepare_memory_profile', side_effect=setup), \
                 mock.patch.object(capture.subprocess, 'Popen', side_effect=AssertionError('GUI must not start')), \
                 mock.patch.object(sys, 'argv', ['capture.py', '--racket', str(root / 'racket'), '--fixture', str(fixture), '--output', str(output)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(), 1)
            self.assertFalse((output / 'profile/openracket-diagnostic-profile').exists())
            self.assertFalse(json.loads((output / 'capture-supervisor.json').read_text())['gui_started'])

    def test_real_source_is_only_read_and_weakly_referenced(self):
        source = (HERE / 'phase-probe.rkt').read_text()
        lookup = source[source.index('(define (existing-service-thread-reference'):source.index('(define (start-probe!')]
        for expr in ('(module->namespace module-path)', '(namespace-variable-value', "'thd #t", '(make-weak-box actual)', 'xref source pin mismatch'):
            self.assertIn(expr, lookup)
        self.assertNotIn('(dynamic-require', lookup)
        self.assertNotIn('(thread\n', lookup)
        self.assertIn("(set! xref-ref #f)", source)
        self.assertIn("(hash-set! refs 'xref-service xref-ref)", source)
        self.assertIn('Shared service observed during the active request', source)

    def test_exact_native_context_pins(self):
        self.assertEqual(prepare_phase.CONTEXT_PINS, {
            'xref.rkt': 'acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7',
            'traversals.rkt': 'bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = {name: root/name for name in prepare_phase.CONTEXT_PINS}
            for path in paths.values():
                path.write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'Unexpected official context source'):
                prepare_phase.verify_context_sources(paths, root)

    @unittest.skipUnless(os.name == 'posix', 'POSIX directory aliases')
    def test_context_alias_canonicalization_preserves_confinement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            actual = base / 'actual'
            actual.mkdir()
            paths = {name: actual/name for name in prepare_phase.CONTEXT_PINS}
            for path in paths.values():
                path.write_bytes(b'pinned fixture')
            pin = hashlib.sha256(b'pinned fixture').hexdigest()
            with mock.patch.dict(prepare_phase.CONTEXT_PINS, {name: pin for name in paths}, clear=True):
                alias = base / 'alias'
                alias.symlink_to(actual, target_is_directory=True)
                aliased_paths = {name: alias/name for name in paths}
                with self.assertRaisesRegex(ValueError, 'independently cloned inside runtime'):
                    prepare_phase.verify_context_sources(aliased_paths, alias)
                self.assertEqual(set(prepare_phase.verify_context_sources(aliased_paths, alias.resolve())), set(paths))
                outside = base / 'outside.rkt'
                outside.write_bytes(b'pinned fixture')
                escaped = actual / 'xref.rkt'
                escaped.unlink()
                escaped.symlink_to(outside)
                with self.assertRaisesRegex(ValueError, 'independently cloned inside runtime'):
                    prepare_phase.verify_context_sources(paths, actual)

    def test_producer_times_reject_boolean_negative_nan_and_infinity(self):
        for bad in (True, False, -1, float('nan'), float('inf'), float('-inf'), None, '10'):
            rows = evidence()
            for point in rows[3]['trials'][0]['phase_probe']['phase_points']:
                if point['phase'] in ('worker-phase-10', 'worker-start'):
                    point['source_metrics']['monotonic_ms'] = bad
            with self.subTest(timestamp=bad):
                self.assertFalse(accept.assess(*rows)['accepted'])

    def test_positive_but_partial_monitor_counts_fail_parity(self):
        for key in ('trace_entries', 'rename_capability_rows'):
            rows = evidence()
            # Fixtures share a monitor dictionary intentionally; replace this row
            # independently to model one partial replay without changing capture.
            rows[3]['trials'][0]['monitor_evidence'] = dict(rows[0]['monitor_evidence'])
            rows[3]['trials'][0]['monitor_evidence'][key] += 1
            self.assertFalse(accept.assess(*rows)['accepted'])

    def test_complete_request_accepts(self):
        self.assertTrue(accept.assess(*evidence())['accepted'])

    def test_finished_expansion_oom_missing_service_trace_errors_drops_fail(self):
        mutations = [
            lambda e: e[3]['trials'][0].update(outcome='finished-expansion'),
            lambda e: e[0].update(terminal={'tag': 'abnormal-termination'}),
            lambda e: e[3]['trials'][0]['phase_probe']['attribution_evidence'].update(xref_service_thread_registered=False),
            lambda e: e[3]['trials'][0]['phase_probe'].update(input_events_dropped=1),
            lambda e: e[3]['trials'][1]['monitor_evidence'].update(error_messages=1),
            lambda e: e[3]['trials'][0]['phase_probe'].update(phase_points=[]),
            lambda e: e[3].update(actual_worker_child_limit_bytes=134217728),
            lambda e: e[4].update(hard_wall_budget_seconds=200),
            lambda e: e[3]['cleanup'].update(accepted=False),
            lambda e: e[3].update(actual_worker_memory_accounting_available=False),
            lambda e: e[3]['trials'][0].update(retained_place_channels=0),
            lambda e: e[3]['trials'][0]['phase_probe']['xref_service_registration'].update(source_sha256='wrong'),
            lambda e: e[3]['trials'][1].update(prior_place_channels_retained_before_request=0),
            lambda e: e[3].update(last_place_channels_retained_until_cleanup=0),
        ]
        for change in mutations:
            rows = copy.deepcopy(evidence())
            change(rows)
            with self.subTest(change=change):
                self.assertFalse(accept.assess(*rows)['accepted'])

if __name__ == '__main__':
    unittest.main()
