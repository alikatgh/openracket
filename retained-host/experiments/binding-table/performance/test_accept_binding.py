"""Synthetic, fail-closed paired acceptance tests; never native timing evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import accept_binding as accept
from test_accept_gui import arm_fixture


def sha(data): return hashlib.sha256(data).hexdigest()

class BindingAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.arms, self.manifests, self.pins = {}, {}, {}
        for arm in ('stock', 'candidate'):
            root = base / arm; source = root / 'share/pkgs/drracket-core-lib/drracket/private'
            handler = source / 'syncheck/online-comp.rkt'; handler.parent.mkdir(parents=True)
            handler.write_bytes(b'common exact synthetic handler')
            gui = source / 'syncheck/gui.rkt'
            gui.write_bytes(('synthetic observed gui ' + arm).encode())
            self.pins[arm + '_sha256'] = sha(('synthetic original gui ' + arm).encode())
            diagnostic = {name: sha(('common synthetic ' + name).encode()) for name in accept.PINS}
            diagnostic['syncheck/gui.rkt'] = sha(gui.read_bytes())
            diagnostic['syncheck/online-comp.rkt'] = sha(handler.read_bytes())
            self.manifests[arm] = {'diagnostic_root': str(root), 'source_root': str(source), 'arm': arm,
                                   'stock_pins': dict(accept.PINS),
                                   'original_pins': dict(accept.PINS, **{'syncheck/gui.rkt': self.pins[arm + '_sha256']}),
                                   'diagnostic_sources': diagnostic, 'helpers': {'same': 'same'}}
            data = arm_fixture('control'); data['capture-host.json']['arm'] = arm; data['capture-supervisor.json']['arm'] = arm
            data['memory-profile.json']['profile_path'] = str(root / 'profile')
            data['memory-profile.json']['addon_path'] = str(root / 'addon')
            for row in data['gui-observation.json']['actual_registry']:
                row.update(source=str(handler), source_sha256=sha(handler.read_bytes()), module_spec='#<path:' + str(handler) + '>')
            rec = data['gui-observation.json']['records'][0]
            rec['terminal']['handler_keys'] = ['(#<path:' + str(handler) + '> go)']
            data['capture-host.json'].update(workload_started_monotonic_ms=20, edit_dispatched_monotonic_ms=90,
                workload_completed_monotonic_ms=410, post_edit_deadline_monotonic_ms=90090,
                post_join_final_verification_monotonic_ms=460, heartbeat_verified=True,
                post_export_final_verification_monotonic_ms=480, binding_export_verified=True,
                post_export_final_currentness_verified=True)
            data['activation.json'] = {'schema_version': 1, 'kind': 'gui_binding_table_activation', 'arm': arm,
                'verified': True, 'gui_handler_thread': True, 'gui_module_already_instantiated': True,
                'same_gui_module_instance': True, 'gui_namespace_base_phase': 0,
                'gui_module': 'drracket/private/syncheck/gui',
                'flag_name': 'OPENRACKET_BINDING_TABLE_INDEX', 'activation_export': 'openracket-binding-table-index-enabled?',
                'phase_points_enabled': False, 'source': str(gui), 'source_sha256': sha(gui.read_bytes()),
                'expected_source_sha256': sha(gui.read_bytes()), 'flag_value': None if arm == 'stock' else '1',
                'export_status': 'missing' if arm == 'stock' else 'boolean', 'binding_index_enabled': None if arm == 'stock' else True}
            rows=[]; previous=None; scheduled=60
            for i, handled in enumerate((80,150,235,310,380,450),1):
                rows.append(dict(sequence=i, scheduled_monotonic_ms=scheduled, submitted_monotonic_ms=scheduled+1,
                    handler_monotonic_ms=handled, producer_lateness_ms=1, dispatch_latency_ms=handled-scheduled-1,
                    handler_gap_ms=None if previous is None else handled-previous, after_stop=handled>=420))
                previous=handled; scheduled=handled+50
            data['heartbeat.json'] = dict(schema_version=1,kind='gui-heartbeat',clock='monotonic',period_ms=50.0,max_records=4096,
                producer_exited=True,joined=True,join_timed_out=False,outstanding_callbacks=0,dropped_records=0,error_count=0,errors=[],
                submitted_count=len(rows),handled_count=len(rows),record_count=len(rows),started_monotonic_ms=10,stopped_monotonic_ms=420,
                last_handler_monotonic_ms=450,stop_handler_gap_ms=40,records=rows)
            before = dict(enabled=True, active=True, accepted=10, duplicates=2, pending=10,
                          materializations=0, stock_calls=0, unsupported_fallbacks=0,
                          generation=1, fallback_reason=False)
            after = dict(before, active=False, pending=0, materializations=1, stock_calls=10,
                         fallback_reason='public-exposure')
            def point(t):
                return dict(monotonic_ms=t, allocation_bytes=t*100, managed_bytes=500,
                            gc_ms=t, cpu_all_places_ms=t)
            data['binding-export.json'] = dict(schema_version=1, kind='binding-table-public-exposure',
                arm=arm, verified=True, status='complete', same_public_hash_identity=True,
                before_state=None if arm == 'stock' else before,
                after_first_state=None if arm == 'stock' else after,
                after_second_state=None if arm == 'stock' else copy.deepcopy(after),
                first_start=point(461), first_end=point(470), second_start=point(471), second_end=point(472),
                verified_monotonic_ms=475, export=dict(key_count=5, edge_count=10,
                canonical_format='racket-written-sorted-exact-integer-quadruples-v1', canonical_sha256='a'*64,
                owning_editor_endpoints=True, mutable_strong_equal_hash=True, immutable_equal_set_values=True))
            self.arms[arm] = data

    def result(self): return accept.compare_pair(self.arms,self.manifests,self.pins)
    def reject(self):
        result=self.result(); self.assertFalse(result['accepted'],result); self.assertEqual(set(result['arms']),{'stock','candidate'})
        return result
    def test_distinct_clones_normalize_typed_identity_without_mutating_raw(self):
        original=copy.deepcopy(self.arms); result=self.result(); self.assertTrue(result['accepted'],result['failures'])
        self.assertEqual(self.arms,original)
        self.assertEqual(result['arms']['stock']['registry'],result['arms']['candidate']['registry'])
    def test_after_stop_drain_preserves_pre_stop_tail(self):
        self.assertTrue(self.result()['accepted'])
        self.arms['candidate']['heartbeat.json']['stop_handler_gap_ms']=0; self.reject()
    def test_missing_or_null_documents_retained(self):
        original=copy.deepcopy(self.arms)
        for name in accept.FILES:
            for missing in (False,True):
                self.arms=copy.deepcopy(original)
                if missing:del self.arms['candidate'][name]
                else:self.arms['candidate'][name]=None
                with self.subTest(name=name,missing=missing):self.reject()
    def test_explicit_oom_stays_invalid(self):
        self.arms['candidate']['gui-observation.json']['records'][0]['terminal']={'tag':'abnormal-termination','explicit_out_of_memory':True}
        result=self.reject(); self.assertTrue(result['arms']['candidate']['raw_gui_records'][0]['terminal']['explicit_out_of_memory'])
    def test_actual_loaded_dependency_and_flag_must_agree(self):
        original=copy.deepcopy(self.arms)
        changes=[('source_sha256','0'*64),('gui_handler_thread',False),('gui_namespace_base_phase',True),
                 ('export_status','missing'),('flag_value',None),('binding_index_enabled',False),('same_gui_module_instance',False),
                 ('phase_points_enabled',True)]
        for key,value in changes:
            self.arms=copy.deepcopy(original);self.arms['candidate']['activation.json'][key]=value
            with self.subTest(key=key):self.reject()
    def test_actual_source_and_non_gui_delta_mutation_refused(self):
        source=Path(self.arms['candidate']['activation.json']['source']); original=source.read_bytes()
        source.write_bytes(b'changed');self.reject();source.write_bytes(original)
        self.manifests['candidate']['original_pins']['module-language.rkt'] = '0'*64;self.reject()
    def test_foreign_equal_module_source_refused(self):
        act=self.arms['candidate']['activation.json'];foreign=Path(self.temp.name)/'foreign/syncheck/gui.rkt'
        foreign.parent.mkdir(parents=True);foreign.write_bytes(Path(act['source']).read_bytes());act['source']=str(foreign);self.reject()
    def test_linked_module_refused(self):
        act=self.arms['candidate']['activation.json'];source=Path(act['source']);linked=source.with_name('real.rkt');source.rename(linked)
        source.symlink_to(linked);self.reject()
    def test_raw_terminal_keys_still_bound_to_actual_source(self):
        self.arms['candidate']['gui-observation.json']['records'][0]['terminal']['handler_keys']=self.arms['stock']['gui-observation.json']['records'][0]['terminal']['handler_keys']
        self.reject()
    def test_registry_hash_export_monitor_or_path_change_refused(self):
        original=copy.deepcopy(self.arms)
        for key,value in [('export','different'),('monitor',True),('source_sha256','0'*64),('source','/foreign/online-comp.rkt')]:
            self.arms=copy.deepcopy(original)
            for document in ('gui-observation.json','worker-init.json'):
                self.arms['candidate'][document]['actual_registry'][0][key]=value
            with self.subTest(key=key):self.reject()
    def test_heartbeat_nonfinite_boolean_order_and_arithmetic_refused(self):
        original=copy.deepcopy(self.arms)
        for field,value in [('handler_monotonic_ms',True),('scheduled_monotonic_ms',float('nan')),('dispatch_latency_ms',2),
                            ('producer_lateness_ms',0),('handler_gap_ms',0),('after_stop',True),('sequence',True)]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['heartbeat.json']['records'][1][field]=value
            with self.subTest(field=field):self.reject()
    def test_drops_counts_join_and_tail_refused(self):
        original=copy.deepcopy(self.arms)
        for field,value in [('record_count',True),('dropped_records',1),('outstanding_callbacks',1),('joined',False),
                            ('producer_exited',False),('join_timed_out',True),('handled_count',2),('last_handler_monotonic_ms',440)]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['heartbeat.json'][field]=value
            with self.subTest(field=field):self.reject()
    def test_post_join_verification_and_original_deadline_required(self):
        original=copy.deepcopy(self.arms)
        for field,value in [('post_join_final_verification_monotonic_ms',419),('post_join_final_verification_monotonic_ms',True),
                            ('post_edit_deadline_monotonic_ms',460),('post_edit_deadline_monotonic_ms',90091),('heartbeat_verified',False),('workload_completed_monotonic_ms',240)]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['capture-host.json'][field]=value
            with self.subTest(field=field,value=value):self.reject()
    def test_phase_collection_rejected_both_arms(self):
        self.arms['stock']['worker-phase-1.json']['phase_points_enabled']=True;self.reject()
    def test_profile_prefab_and_monitor_equality(self):
        original=copy.deepcopy(self.arms)
        self.arms['candidate']['memory-profile.json']['addon_path']=self.arms['stock']['memory-profile.json']['addon_path'];self.reject()
        self.arms=copy.deepcopy(original);self.arms['candidate']['capture-host.json']['pending_run_serialized_settings']='other';self.reject()
        self.arms=copy.deepcopy(original);self.arms['candidate']['gui-observation.json']['records'][0]['monitor_evidence']['trace_entries']+=1;self.reject()
    def test_missing_common_manifest_fields_fail_without_losing_arms(self):
        del self.manifests['candidate']['helpers'];self.reject()

    def test_common_observer_manifest_must_match(self):
        self.manifests['candidate']['helpers']={'changed':'different'};self.reject()

    def test_all_binding_state_witnesses_are_required_and_strict(self):
        original = copy.deepcopy(self.arms)
        changes = [('active', False), ('enabled', False), ('accepted', 0), ('pending', 0),
                   ('materializations', 1), ('stock_calls', 1), ('unsupported_fallbacks', 1),
                   ('generation', 0), ('duplicates', True), ('fallback_reason', 'public-exposure')]
        for field, value in changes:
            self.arms = copy.deepcopy(original)
            self.arms['candidate']['binding-export.json']['before_state'][field] = value
            with self.subTest(field=field): self.reject()
        for name in ('after_first_state', 'after_second_state'):
            for field, value in [('active', True), ('materializations', 2), ('stock_calls', 9),
                                 ('accepted', 9), ('generation', 2), ('pending', 1),
                                 ('fallback_reason', 'unsupported-input'), ('duplicates', False)]:
                self.arms = copy.deepcopy(original)
                self.arms['candidate']['binding-export.json'][name][field] = value
                with self.subTest(name=name, field=field): self.reject()

    def test_binding_shape_identity_count_digest_and_stock_state(self):
        original = copy.deepcopy(self.arms)
        for field, value in [('key_count', True), ('edge_count', 0), ('canonical_sha256', 'f'*64),
                             ('key_count', 6), ('owning_editor_endpoints', False),
                             ('mutable_strong_equal_hash', False), ('immutable_equal_set_values', False)]:
            self.arms = copy.deepcopy(original)
            self.arms['candidate']['binding-export.json']['export'][field] = value
            with self.subTest(field=field): self.reject()
        self.arms = copy.deepcopy(original)
        self.arms['candidate']['binding-export.json']['same_public_hash_identity'] = False
        self.reject()
        self.arms = copy.deepcopy(original)
        self.arms['stock']['binding-export.json']['before_state'] = {}
        self.reject()

    def test_export_timing_is_separate_and_final_recheck_required(self):
        original = copy.deepcopy(self.arms)
        for name, field, value in [('first_start', 'monotonic_ms', 400), ('first_end', 'monotonic_ms', 500),
                                    ('second_start', 'monotonic_ms', True), ('second_end', 'gc_ms', 0),
                                    ('first_end', 'allocation_bytes', float('inf')),
                                    ('first_end', 'allocation_bytes', 47000.0),
                                    ('first_end', 'managed_bytes', 500.0),
                                    ('first_end', 'gc_ms', True),
                                    ('first_end', 'cpu_all_places_ms', 470.0)]:
            self.arms = copy.deepcopy(original)
            self.arms['candidate']['binding-export.json'][name][field] = value
            with self.subTest(name=name, field=field): self.reject()
        for field, value in [('post_export_final_currentness_verified', False),
                             ('post_export_final_verification_monotonic_ms', 472),
                             ('post_export_final_verification_monotonic_ms', 100000),
                             ('binding_export_verified', False)]:
            self.arms = copy.deepcopy(original)
            self.arms['candidate']['capture-host.json'][field] = value
            with self.subTest(field=field): self.reject()

    def test_transformed_non_gui_delta_and_missing_manifest_pins_refused(self):
        self.manifests['candidate']['diagnostic_sources']['module-language.rkt'] = '0'*64
        self.reject()
        del self.manifests['candidate']['original_pins']
        self.reject()

if __name__=='__main__':unittest.main()
