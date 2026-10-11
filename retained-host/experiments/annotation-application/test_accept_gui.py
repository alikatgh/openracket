"""Synthetic schema rejection tests; these are never native performance evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from accept_gui import BASE, CAP, FILES, GUI_POINTS, METRICS, PHASES, SNAPSHOT, compare, strict_json, verify_registry_sources

from validate_application import TAGS, FINALS

def application_fixture(arm, entries=292728):
    timed = arm == 'observed'
    def acc(n, total=0, maximum=0):
        return dict(count=n, wall_ms=total if timed else None, max_wall_ms=maximum if timed else None)
    r = dict(request_id=1, application_generation=1, completed=True, cancelled=False,
             errors=0, unknown_tags=0, reentrant_entries=0, stale_events=0, unmatched_events=0,
             entries_started=entries if timed else 0, entries_completed=entries if timed else 0,
             open_entry_depth=0, open_final=False, active_batch=False, queued_wait=False,
             yield_count=1, resume_count=1, batch_active=acc(2, 16, 10), requeue_wait=acc(1, 4, 4),
             first_batch_start_ms=231 if timed else None, last_batch_end_ms=251 if timed else None,
             tag_buckets=[dict(acc(74675 if i == 0 else (entries - 74675 if i == 2 else 0), 8 if i == 0 else 0,
                                   1 if i == 0 else 0), tag=tag) for i, tag in enumerate(TAGS)] if timed else [],
             final_updates=[dict(acc(1, 1, 1), operation=name) for name in FINALS] if timed else [])
    return dict(schema_version=1, kind='genuine-gui-annotation-application', probe_enabled=timed,
                common_batch_counts=True, snapshot_quiescent=True, selected_count=1, dropped_records=0, observer_failures=0,
                records=[r])

def metric(t):
    return {k: t for k in METRICS}

def arm_fixture(arm):
    times = {'request-observed': 100, 'monitor-received': 200,
             'monitor-callback-queue-attempt': 210, 'monitor-callback-enter': 220,
             'application-enter': 230, 'monitor-callback-return': 240,
             'application-complete': 250, 'terminal-received': 300,
             'terminal-callback-queue-attempt': 310, 'terminal-callback-enter': 320,
             'terminal-callback-return': 330}
    points = {k: metric(times[k]) for k in GUI_POINTS}
    registry = [{'module_spec': 'online-comp.rkt', 'export': name, 'monitor': monitor,
                 'source': '/test/online-comp.rkt', 'source_sha256': 'a' * 64}
                for name, monitor in [('go', False), ('monitor', True)]]
    terminal = {'tag': 'handler-results', 'compiled_bytes': 270280, 'handler_keys': ['go']}
    rec = {'request_id': 1, 'snapshot_sha256': SNAPSHOT, 'snapshot_characters': 1048577,
           'snapshot_kind': 'string', 'source': '/test/fixture.rkt', 'actual_prefab': 'actual-prefab',
           'actual_prefab_truncated': False, 'prefab_annotations_none': True,
           'actual_child_limit_bytes': CAP, 'terminal': terminal, 'terminal_callback_current': True,
           'application_current': True, 'application_generation': 1, 'point_duplicates': 0,
           'application_cancelled': False, 'stale_application_events': 0,
           'monitor_evidence': {'messages': 1, 'trace_batches': 1, 'trace_entries': 292728,
                               'rename_capability_rows': 74675, 'error_messages': 0, 'invalid_payloads': 0},
           'gui_points': points}
    host = {'status': 'gui_application_complete', 'arm': arm, 'racket_version': '9.3', 'os': 'macosx',
            'edited_snapshot_sha256': SNAPSHOT, 'final_snapshot_sha256': SNAPSHOT,
            'final_snapshot_characters': 1048577, 'source_unchanged': True, 'lexer_valid_at_completion': True,
            'preserved_preferences': {'child_limit_bytes': CAP, 'coloring': True, 'online_compilation': True},
            'actual_worker_child_limit_bytes': CAP, 'actual_worker_memory_accounting_available': True,
            'matching_request_id': 1, 'fixture': '/test/fixture.rkt',
            'post_edit_deadline_monotonic_ms': 90100, 'first_final_lexer_valid_observed_monotonic_ms': 400,
            'pending_run_serialized_settings': 'pending-next-run'}
    for field, key in [('terminal_received_monotonic_ms', 'terminal-received'),
                       ('terminal_callback_enter_monotonic_ms', 'terminal-callback-enter'),
                       ('terminal_callback_return_monotonic_ms', 'terminal-callback-return'),
                       ('application_complete_monotonic_ms', 'application-complete')]:
        host[field] = times[key]
    sup = {'status': 'gui_application_complete', 'arm': arm, 'exit_code': 0, 'timeout': False,
           'cleanup': {'complete': True}, 'gui_started': True, 'native_gui_capture_only': True,
           'standalone_replay': False, 'host_evidence_errors': [], 'base_fixture_sha256': BASE,
           'edited_snapshot_sha256': SNAPSHOT, 'edited_snapshot_characters': 1048577,
           'edited_snapshot_bytes': 1048577, 'memory_profile_setup': {'verified': True, 'errors': []}}
    profile = {'status': 'verified', 'phase': 'before-timed-gui', 'runtime_version': '9.3',
               'profile_was_empty': True, 'addon_was_empty': True, 'only_expected_preference_changed': True,
               'legacy_preference_store_absent': True, 'runtime_fallback_store_absent': True,
               'gui_initialized': False, 'disk_key_count_before': 0, 'disk_key_count_after': 1,
               'one_key_delta': [{'key': 'plt:framework-pref:drracket:child-only-memory-limit',
                                 'before_present': False, 'after_value': CAP}],
               'profile_path': '/test/' + arm + '/profile', 'addon_path': '/test/' + arm + '/addon'}
    for k in ('expected_limit_bytes', 'selected_limit_bytes', 'readback_limit_bytes', 'persisted_limit_bytes'):
        profile[k] = CAP
    worker = {'actual_child_limit_bytes': CAP, 'memory_accounting_available': True,
              'snapshot_sha256': SNAPSHOT, 'source': '/test/fixture.rkt', 'actual_prefab': 'actual-prefab',
              'terminal': 'handler-results', 'selected_job_count': 1, 'selected_job_id': 1,
              'dropped_jobs': 0, 'observer_failures': 0, 'emission_after_stock_terminal_send': True,
              'phase_points_enabled': False, 'phase_points': []}
    return dict(zip(FILES, [host, sup,
        {'error_count': 0, 'errors': [], 'dropped_records': 0, 'records': [rec],
         'matching_request_ids': [1], 'request_count': 1, 'actual_registry': registry},
        {'child_limit_bytes': CAP, 'memory_accounting_available': True, 'actual_registry': registry},
        worker, profile, application_fixture(arm)]))

class AcceptanceTests(unittest.TestCase):
    def setUp(self): self.data = {a: arm_fixture(a) for a in ('control', 'observed')}
    def denied(self): self.assertFalse(compare(self.data)['accepted'])
    def rec(self): return self.data['observed']['gui-observation.json']['records'][0]
    def test_synthetic_complete_and_application_before_terminal(self):
        self.assertTrue(compare(self.data)['accepted'])
    def test_application_after_terminal_is_also_valid(self):
        self.rec()['gui_points']['application-complete'] = metric(350)
        self.data['observed']['capture-host.json']['application_complete_monotonic_ms'] = 350
        app = self.data['observed']['application-profile.json']['records'][0]
        app['last_batch_end_ms'] = 351
        app['requeue_wait'].update(wall_ms=104, max_wall_ms=104)
        self.assertTrue(compare(self.data)['accepted'])
    def test_actual_oom_preserved_as_failure(self):
        self.rec()['terminal'] = {'tag': 'abnormal-termination', 'explicit_out_of_memory': True}
        self.denied()
    def test_incomplete_or_failed_process(self):
        self.data['observed']['capture-supervisor.json']['timeout'] = True
        self.denied()
    def test_null_missing_and_invalid_rows_preserved(self):
        for key in FILES:
            data = copy.deepcopy(self.data); data['observed'][key] = None
            result = compare(data)
            self.assertFalse(result['accepted']); self.assertIn('control', result['arms'])
    def test_duplicate_matching_job(self):
        self.data['observed']['worker-phase-1.json']['selected_job_count'] = 2
        self.denied()
    def test_boolean_job_id_refused(self):
        self.data['observed']['worker-phase-1.json']['selected_job_id'] = True
        self.denied()
    def test_wrong_cap_or_accounting(self):
        self.data['observed']['worker-phase-1.json']['memory_accounting_available'] = False
        self.denied()
    def test_stale_application(self):
        self.rec()['application_current'] = False
        self.denied()
    def test_cancelled_endpoint(self):
        self.rec()['gui_points']['application-cancelled-or-stale'] = metric(250)
        self.denied()
    def test_stale_event_and_cancelled_flags(self):
        for key, value in [('stale_application_events', 1), ('application_cancelled', True)]:
            data = copy.deepcopy(self.data)
            data['observed']['gui-observation.json']['records'][0][key] = value
            self.assertFalse(compare(data)['accepted'])
    def test_bool_nan_and_missing_timestamps(self):
        for value in (True, float('nan'), None):
            data = copy.deepcopy(self.data)
            data['observed']['gui-observation.json']['records'][0]['gui_points']['monitor-received']['monotonic_ms'] = value
            self.assertFalse(compare(data)['accepted'])
    def test_source_identity_mismatch(self):
        self.data['observed']['worker-phase-1.json']['snapshot_sha256'] = '0' * 64
        self.denied()
    def test_wrong_registry_monitor_flag(self):
        self.data['observed']['worker-init.json']['actual_registry'][0]['monitor'] = True
        self.denied()
    def test_truncated_actual_settings(self):
        self.rec()['actual_prefab_truncated'] = True
        self.denied()
    def test_observed_producer_points_rejected(self):
        self.data['observed']['worker-phase-1.json']['phase_points_enabled'] = True
        self.denied()
    def test_control_collected_phases(self):
        self.data['control']['worker-phase-1.json']['phase_points'] = [{'phase': 'unexpected'}]
        self.denied()
    def test_one_key_profile_or_freshness_mismatch(self):
        self.data['observed']['memory-profile.json']['profile_path'] = '/test/control/profile'
        self.denied()
    def test_paired_monitor_count_mismatch(self):
        self.rec()['monitor_evidence']['trace_entries'] += 1
        self.denied()
    def test_duplicate_and_nonfinite_json_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            for text in ('{"a":1,"a":2}', '{"a":NaN}', 'null'):
                path.write_text(text)
                with self.assertRaises(ValueError): strict_json(path)
    def test_actual_registry_must_use_verified_clone_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'private/syncheck/online-comp.rkt'
            source.parent.mkdir(parents=True); source.write_bytes(b'fixture handler bytes')
            pin = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = {'diagnostic_root': str(root), 'source_root': str(root / 'private'),
                        'diagnostic_sources': {'syncheck/online-comp.rkt': pin}}
            rows = [(str(source), pin, 'go', False), (str(source), pin, 'monitor', True)]
            arms = {a: {'registry': rows[:]} for a in ('control', 'observed')}
            self.assertEqual(verify_registry_sources(arms, manifest)['sha256'], pin)
            foreign = root / 'elsewhere.rkt'; foreign.write_bytes(source.read_bytes())
            arms['observed']['registry'] = [(str(foreign), pin, 'go', False), rows[1]]
            with self.assertRaises(ValueError): verify_registry_sources(arms, manifest)
            arms['observed']['registry'] = rows[:]
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_registry_sources(arms, manifest)

if __name__ == '__main__': unittest.main()
