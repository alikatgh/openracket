"""Synthetic schema/arithmetic mutations only; no GUI or timing observations."""
import copy
import unittest
from accept_gui import compare
from test_accept_gui import arm_fixture
from validate_sampler import COUNTS, TIMES


class SamplerValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = {arm: arm_fixture(arm) for arm in ('control', 'observed')}
    def sampler(self, arm='observed'):
        return self.data[arm]['queued-samples.json']
    def row(self):
        return self.sampler()['samples'][0]
    def host(self, arm='observed'):
        return self.data[arm]['capture-host.json']
    def denied(self):
        self.assertFalse(compare(self.data)['accepted'])
    def test_complete_disabled_and_live_sample(self):
        result = compare(self.data)
        self.assertTrue(result['accepted'], result)
        self.assertEqual(result['arms']['observed']['queued_sampler']['sampled_distinct_wait_lower_bound_ms'], 2)
        self.assertFalse(result['arms']['control']['queued_sampler']['enabled'])
    def test_each_fixed_bound_and_activation(self):
        for key, value in [('sample_period_ms', 200), ('attempt_cap', 1025), ('frame_cap', 9),
                           ('text_cap', 241), ('enabled', False), ('stock_logger_subscription', True)]:
            self.setUp(); self.sampler()[key] = value; self.denied()
    def test_incomplete_capped_unjoined_fail(self):
        for key, value in [('snapshot_quiescent', False), ('capped', True), ('incomplete', True),
                           ('stopped', False), ('termination', 'capped')]:
            self.setUp(); self.sampler()[key] = value; self.denied()
        for key in ('sampler_joined', 'gui_handler_verified', 'post_join_current'):
            self.setUp(); self.host()[key] = False; self.denied()
    def test_all_counters_and_timings_refuse_boolean_negative_nonfinite(self):
        for key in COUNTS + TIMES:
            for value in (True, -1, None, float('nan'), float('inf')):
                self.setUp(); self.sampler()[key] = value; self.denied()
    def test_missing_or_empty_stack_evidence(self):
        self.sampler()['samples'] = []; self.denied()
        self.setUp(); self.sampler()['usable_source_samples'] = 0; self.denied()
        self.setUp(); del self.data['observed']['queued-samples.json']; self.denied()
    def test_discarded_races_and_stops_remain_explicit(self):
        self.sampler().update(attempts=3, race_discarded=1, stop_discarded=1, cadence_ticks=4, idle_ticks=1)
        self.assertTrue(compare(self.data)['accepted'])
        self.sampler()['race_discarded'] = 0; self.denied()
    def test_unsafe_capture_states_and_observer_errors(self):
        for key in ('invalid_token_discarded', 'attempt_errors_discarded', 'capture_errors', 'absent_handlers',
                    'collected_handlers', 'dead_handlers', 'invalid_handlers', 'died_during_capture', 'sampler_errors'):
            self.setUp(); self.sampler()[key] = 1; self.denied()
        for state in ('dead', 'sampling_error', 'not_registered', 'died_during_sample'):
            self.setUp(); self.row()['state'] = state; self.denied()
        self.setUp(); self.row()['capture_performed'] = False; self.denied()
    def test_request_generation_and_wait_ordinal(self):
        for key in ('request_id', 'application_generation', 'wait_ordinal'):
            for value in (0, True, 2):
                self.setUp(); self.row()[key] = value; self.denied()
    def test_sample_timing_arithmetic(self):
        for key in ('capture_duration_ms', 'scheduling_delay_ms', 'missed_before_capture_ticks', 'missed_cadence_ticks'):
            self.setUp(); self.row()[key] += 1; self.denied()
        self.setUp(); self.row()['capture_started_monotonic_ms'] = 242; self.denied()
        self.setUp(); self.row()['queued_monotonic_ms'] = 242; self.denied()
    def test_pending_age_bounded_by_actual_gap(self):
        self.row()['queued_monotonic_ms'] = 231; self.denied()
    def test_distinct_pending_lower_bounds_cannot_exceed_total_wait(self):
        app = self.data['observed']['application-profile.json']['records'][0]
        app.update(yield_count=2, resume_count=2)
        app['batch_active']['count'] = 3
        app['requeue_wait']['count'] = 2
        # Both pending ages are3, while actual total waiting is only4.
        first = self.row(); first['queued_monotonic_ms'] = 238
        second = copy.deepcopy(first)
        second.update(wait_ordinal=2, queued_monotonic_ms=239, actual_monotonic_ms=241,
                      capture_started_monotonic_ms=241, capture_finished_monotonic_ms=242,
                      scheduling_delay_ms=41)
        self.sampler()['samples'].append(second)
        self.sampler().update(attempts=2, stored_samples=2, usable_source_samples=2, cadence_ticks=2,
                              capture_duration_ms=2, scheduling_delay_ms=81, max_scheduling_delay_ms=41)
        self.denied()
    def test_sample_may_start_after_its_cadence_tick(self):
        # Publication can occur between the actual tick timestamp and capture start.
        row = self.row()
        row.update(queued_monotonic_ms=240.25, capture_started_monotonic_ms=240.5,
                   capture_duration_ms=.5)
        self.sampler().update(capture_duration_ms=.5, max_capture_duration_ms=.5)
        self.assertTrue(compare(self.data)['accepted'])
    def test_counter_aggregate_covers_stored_rows(self):
        for key in ('capture_duration_ms', 'max_capture_duration_ms', 'scheduling_delay_ms',
                    'max_scheduling_delay_ms', 'usable_source_samples'):
            self.setUp(); self.sampler()[key] = 0; self.denied()
    def test_bounded_frames_and_source_identity(self):
        self.row()['frames'] *= 9; self.denied()
        for field in ('name', 'source'):
            self.setUp(); self.row()['frames'][0][field] = 'x' * 241; self.denied()
            self.setUp(); self.row()['frames'][0][field + '_truncated'] = True; self.denied()
        self.setUp(); self.row()['frames'][0]['source_kind'] = 'missing'; self.denied()
        self.setUp(); self.row()['frames'][0]['line'] = True; self.denied()
    def test_honest_text_and_depth_truncation_allowed(self):
        row = self.row(); frame = row['frames'][0]
        frame.update(name='🧭' * 240, name_truncated=True)
        row['frames'] = [copy.deepcopy(frame) for _ in range(8)]
        row.update(frames_truncated=True, text_fields_truncated=8, usable_source_frames=8)
        self.sampler().update(frames_truncated=1, text_fields_truncated=8)
        self.assertTrue(compare(self.data)['accepted'])
    def test_missing_sources_explicit_when_other_frames_useful(self):
        row = self.row()
        row['frames'].append(dict(name=None, source=None, name_truncated=False, source_truncated=False,
                                 source_kind='missing', line=None, column=None, position=None))
        row['missing_frame_sources'] = 1
        self.assertTrue(compare(self.data)['accepted'])
        row['missing_frame_sources'] = 0; self.denied()
    def test_unclosed_lifecycle_deadline_and_final_order(self):
        for key, value in [('sampler_stop_requested_monotonic_ms', 399), ('sampler_joined_monotonic_ms', 449),
                           ('post_join_verified_monotonic_ms', 450), ('post_join_verified_monotonic_ms', 90100)]:
            self.setUp(); self.host()[key] = value; self.denied()
        self.setUp(); self.sampler()['finished_monotonic_ms'] = 452; self.denied()
        self.setUp(); self.sampler()['started_monotonic_ms'] = 101; self.denied()
    def test_disabled_control_has_no_timing_or_samples(self):
        for key, value in [('started_monotonic_ms', 0), ('finished_monotonic_ms', 0), ('attempts', 1),
                           ('scheduling_delay_ms', 1), ('stopped', True), ('termination', 'stopped')]:
            self.setUp(); self.sampler('control')[key] = value; self.denied()


class NestedArrowValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = {arm: arm_fixture(arm) for arm in ('control', 'observed')}
    def detail(self): return self.data['observed']['application-profile.json']['records'][0]['arrow_detail']
    def denied(self): self.assertFalse(compare(self.data)['accepted'])
    def test_exact_operation_inventory(self):
        for mode in ('missing', 'duplicate', 'reorder'):
            self.setUp(); rows=self.detail()['operations']
            if mode=='missing': rows.pop()
            if mode=='duplicate': rows[-1]=rows[0]
            if mode=='reorder': rows.reverse()
            self.denied()
    def test_boolean_short_circuit_counts_and_no_open_state(self):
        for key in ('binding_true', 'binding_false', 'open_method_depth'):
            self.setUp(); self.detail()[key] += 1; self.denied()
            self.setUp(); self.detail()[key] = True; self.denied()
        self.setUp(); self.detail()['open_nested']=True; self.denied()
        for i in range(3):
            self.setUp(); self.detail()['operations'][i]['count']-=1; self.denied()
    def test_nested_wall_is_inside_arrow_total_and_maximum(self):
        self.detail()['operations'][0].update(wall_ms=5); self.denied()
        self.setUp(); self.detail()['operations'][0].update(max_wall_ms=1.1); self.denied()
    def test_nested_detail_unavailable_in_control(self):
        self.data['control']['application-profile.json']['records'][0]['arrow_detail']={}; self.denied()

if __name__ == '__main__': unittest.main()
