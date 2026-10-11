"""Synthetic mutations, not runtime or performance evidence."""
import copy
import unittest
from test_accept_gui import arm_fixture
from accept_gui import compare

class ApplicationValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = {arm: arm_fixture(arm) for arm in ('control', 'observed')}
    def rec(self):
        return self.data['observed']['application-profile.json']['records'][0]
    def denied(self):
        self.assertFalse(compare(self.data)['accepted'])
    def test_counts_and_wall_accounting_report(self):
        result = compare(self.data)
        self.assertTrue(result['accepted'])
        observed = result['arms']['observed']['application_profile']
        self.assertEqual(observed['other_batch_wall_ms'], 4)
        self.assertEqual(observed['batch_span_wall_ms'], 20)
        self.assertEqual(observed['measured_entry_call_wall_ms'], 8)
    def test_counts_need_not_equal_between_arms(self):
        r = self.data['control']['application-profile.json']['records'][0]
        r['batch_active']['count'] = 4
        r['requeue_wait']['count'] = r['yield_count'] = r['resume_count'] = 3
        self.assertTrue(compare(self.data)['accepted'])
    def test_exact_fixed_tags(self):
        for mode in ('missing','duplicate','reordered','unknown'):
            with self.subTest(mode=mode):
                self.setUp()
                tags = self.rec()['tag_buckets']
                if mode == 'missing': tags.pop()
                if mode == 'duplicate': tags[-1] = tags[0]
                if mode == 'reordered': tags.reverse()
                if mode == 'unknown': tags[0]['tag'] = 'syncheck:unknown'
                self.denied()
    def test_tag_counts_independently_reconcile_rename_capabilities(self):
        tags = self.rec()['tag_buckets']
        # Preserve total trace count while moving one row out of the rename classes.
        tags[0]['count'] -= 1
        tags[2]['count'] += 1
        self.denied()
        self.setUp()
        tags = self.rec()['tag_buckets']
        # Moving a row between the two genuine rename classes preserves the witness.
        tags[0]['count'] -= 1
        tags[10]['count'] += 1
        self.assertTrue(compare(self.data)['accepted'])

    def test_every_trace_entry_must_reconcile(self):
        for key in ('entries_started', 'entries_completed'):
            self.setUp(); self.rec()[key] -= 1; self.denied()
        self.setUp(); self.rec()['tag_buckets'][0]['count'] -= 1; self.denied()
    def test_failures_and_unclosed_states_rejected(self):
        for key in ('errors','unknown_tags','reentrant_entries','stale_events','unmatched_events',
                    'open_entry_depth','observer_failures','dropped_records'):
            self.setUp()
            r = self.data['observed']['application-profile.json'] if key in ('observer_failures','dropped_records') else self.rec()
            r[key] = 1; self.denied()
        for key in ('open_final','active_batch','queued_wait','cancelled'):
            self.setUp(); self.rec()[key] = True; self.denied()
    def test_invalid_numbers_and_bools(self):
        for key in ('wall_ms','max_wall_ms','count'):
            for value in (True, -1, None, float('nan'), float('inf')):
                self.setUp(); self.rec()['tag_buckets'][0][key] = value; self.denied()
    def test_active_wait_span_and_sum_consistency(self):
        for key in ('batch_active','requeue_wait'):
            self.setUp(); self.rec()[key]['wall_ms'] += 1; self.denied()
        self.setUp(); self.rec()['last_batch_end_ms'] += 1; self.denied()
        self.setUp(); self.rec()['tag_buckets'][0]['wall_ms'] = 15; self.denied()
    def test_slice_wait_and_current_generation_must_reconcile(self):
        for key in ('yield_count','resume_count','application_generation','request_id'):
            self.setUp(); self.rec()[key] += 1; self.denied()
    def test_final_calls_once_and_four_only(self):
        for mutation in ('missing','duplicate','count','nonfinite'):
            self.setUp(); rows = self.rec()['final_updates']
            if mutation == 'missing': rows.pop()
            if mutation == 'duplicate': rows[-1] = rows[0]
            if mutation == 'count': rows[0]['count'] = 2
            if mutation == 'nonfinite': rows[0]['wall_ms'] = float('nan')
            self.denied()
    def test_failure_snapshot_cannot_be_accepted(self):
        self.data['observed']['application-profile.json']['snapshot_quiescent'] = False
        self.denied()
    def test_control_contains_only_shared_counts(self):
        for key,value in [('entries_started',1), ('tag_buckets',[{}]), ('first_batch_start_ms',1),
                          ('final_updates',[{}])]:
            self.setUp(); self.data['control']['application-profile.json']['records'][0][key] = value; self.denied()
        self.setUp(); self.data['control']['application-profile.json']['probe_enabled'] = True; self.denied()

if __name__ == '__main__': unittest.main()
