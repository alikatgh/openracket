import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fixtures import write_fixtures
from validate_observation import STOCK_PREFAB, validate


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runtime = self.root / 'runtime'
        self.racket = self.runtime / 'bin/racket'
        self.racket.parent.mkdir(parents=True)
        self.racket.touch()
        self.observer = self.root / 'observer'
        self.observer.mkdir()
        (self.observer / 'worker-init-overhead.json').write_text(json.dumps({
            'event': 'worker-observer-one-shot-cost', 'primary_write_and_close_ms': 1.0,
            'observer_through_primary_write_ms': 2.0, 'timing_file_write_measured': False,
            'indirect_gc_and_scheduling_effects_measured': False}))
        self.fixture = write_fixtures(self.root / 'fixtures')[0]
        source = Path(self.fixture['path']).read_bytes()
        i = self.fixture['edit_position']
        digest = hashlib.sha256(source[:i] + b'x' + b'a' * 80 + source[i:]).hexdigest()
        self.worker = {
            'event': 'worker-init-after-handler-imports', 'worker_context': True,
            'xref_already_instantiated': True, 'racket_version': '9.3',
            'child_memory_limit': 134217728, 'memory_accounting_available': True, 'xref_sha256': '0' * 64,
            'xref_path': str(self.runtime / 'pkgs/xref.rkt'),
            'xref_export_status': 'missing', 'xref_reply_cell_enabled': None, 'xref_flag': None,
            'actual_handler_registry': [
                {'module': str(self.runtime / 'pkgs/online-comp.rkt'), 'export': name, 'monitor': monitor}
                for name, monitor in [('go', False), ('monitor', True)]]}
        self.outcome = {
            'request_id': 1, 'generation': 1, 'snapshot_sha256': digest,
            'final_match': True, 'callback_current': True, 'callback_delivered_ms': 42.0,
            'terminal': {'tag': 'handler-results'}, 'actual_prefab': STOCK_PREFAB,
            'actual_prefab_truncated': False, 'monitor_messages': 1,
            'monitor_string_errors': 0, 'monitor_pair_messages': 1,
            'monitor_empty_messages': 0, 'monitor_other_messages': 0}
        self.report = {
            'online_expansion_outcome': copy.deepcopy(self.outcome),
            'online_expansion_observer': {'enabled': True, 'complete_observation': True,
                'dropped_requests': 0, 'observer_error_count': 0, 'generation': 1,
                'expected_sha256': digest, 'expected_characters': len(source) + 81,
                'records': [self.outcome], 'request_count': 1},
            'exact_resulting_source_verified': True, 'post_typing_lexer_settle': {'complete': True},
            'online_terminal_wait': {'complete': True},
            'selected_language_settings': {'status': 'complete', 'errors': {}, 'effective_annotations': 'debug'},
            'preserved_settings': {'drracket:child-only-memory-limit': '134217728',
                                  'framework:coloring-active': '#t', 'drracket:online-compilation-default-on': '#t'},
            'scan_activation': {'status': 'verified', 'expected': 'stock'},
            'budget_activation': {'status': 'verified', 'expected': 'stock'},
            'initial_coloring_key_samples': [{} for _ in range(80)], 'keys_starting_with_lexer_invalid': 80}

    def check(self, arm='stock'):
        (self.observer / 'worker-init.json').write_text(json.dumps(self.worker))
        return validate(self.report, self.observer, self.fixture, arm, '0' * 64, self.racket)

    def test_stock_and_candidate_loaded_activation(self):
        self.assertTrue(self.check()['verified'])
        self.worker.update(xref_export_status='boolean', xref_reply_cell_enabled=True, xref_flag='1')
        self.assertTrue(self.check('candidate')['verified'])
        self.assertFalse(self.check('stock')['verified'])

    def test_failed_monitor_is_real_outcome_not_hidden_success(self):
        for target in (self.outcome, self.report['online_expansion_outcome']):
            target.update(monitor_string_errors=1, monitor_pair_messages=0)
        result = self.check()
        self.assertTrue(result['verified'], result)
        self.assertFalse(result['tool_succeeded'])

    def test_oom_is_valid_observation_not_success(self):
        for target in (self.outcome, self.report['online_expansion_outcome']):
            target.update(terminal={'tag': 'abnormal-termination', 'explicit_out_of_memory': True},
                          monitor_messages=0, monitor_pair_messages=0)
        result = self.check()
        self.assertTrue(result['verified'], result)
        self.assertFalse(result['tool_succeeded'])

    def test_separate_status_channel_does_not_imply_total_order(self):
        self.outcome['status'] = 'finished-expansion'
        self.report['online_expansion_outcome']['status'] = None
        self.assertTrue(self.check()['verified'])

    def test_changed_settings_stale_callbacks_and_misplaced_modules_fail(self):
        for key, value in [('actual_prefab_truncated', True), ('actual_prefab', 'changed'),
                           ('callback_current', False), ('snapshot_sha256', 'changed')]:
            with self.subTest(key=key):
                old = self.report['online_expansion_outcome'][key]
                self.report['online_expansion_outcome'][key] = value
                self.assertFalse(self.check()['verified'])
                self.report['online_expansion_outcome'][key] = old
        self.worker['xref_path'] = str(self.root / 'outside/xref.rkt')
        self.assertFalse(self.check()['verified'])

    def test_boolean_nonfinite_timestamp_and_missing_overhead_fail(self):
        for value in (True, float('nan'), float('inf'), -1):
            self.report['online_expansion_outcome']['callback_delivered_ms'] = value
            self.assertFalse(self.check()['verified'])
        self.report['online_expansion_outcome']['callback_delivered_ms'] = 42.0
        (self.observer / 'worker-init-overhead.json').unlink()
        self.assertFalse(self.check()['verified'])

    def test_unavailable_memory_accounting_fails(self):
        self.worker['memory_accounting_available'] = False
        self.assertFalse(self.check()['verified'])

    def test_registry_and_child_limit_changes_fail(self):
        self.worker['actual_handler_registry'][1]['monitor'] = False
        self.assertFalse(self.check()['verified'])
        self.worker['actual_handler_registry'][1]['monitor'] = True
        self.worker['child_memory_limit'] *= 2
        self.assertFalse(self.check()['verified'])


if __name__ == '__main__':
    unittest.main()
