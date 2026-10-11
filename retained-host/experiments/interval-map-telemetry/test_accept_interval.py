"""Synthetic, fail-closed paired acceptance tests; never native timing evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import accept_interval as accept
from test_accept_gui import arm_fixture


def sha(data): return hashlib.sha256(data).hexdigest()

class IntervalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.arms, self.manifests, self.pins = {}, {}, {}
        support = {name: sha(('support ' + name).encode()) for name in accept.SUPPORT}
        self.patch = patch.dict(accept.SUPPORT, support, clear=True); self.patch.start(); self.addCleanup(self.patch.stop)
        for arm in ('stock', 'candidate'):
            root = base / arm; source = root / 'share/pkgs/drracket-core-lib/drracket/private'
            handler = source / 'syncheck/online-comp.rkt'; handler.parent.mkdir(parents=True)
            handler.write_bytes(b'common exact synthetic handler')
            interval = root / 'share/pkgs/data-lib/data/interval-map.rkt'; interval.parent.mkdir(parents=True)
            interval.write_bytes(('synthetic ' + arm).encode()); self.pins[arm + '_sha256'] = sha(interval.read_bytes())
            for name in support:
                p = interval.parent / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(('support ' + name).encode())
            self.manifests[arm] = {'diagnostic_root': str(root), 'source_root': str(source), 'stock_pins': {'same': 'same'},
                                   'diagnostic_sources': {'syncheck/online-comp.rkt': sha(handler.read_bytes())},
                                   'helpers': {'same': 'same'}}
            data = arm_fixture('control'); data['capture-host.json']['arm'] = arm; data['capture-supervisor.json']['arm'] = arm
            data['memory-profile.json']['profile_path'] = str(root / 'profile')
            data['memory-profile.json']['addon_path'] = str(root / 'addon')
            for row in data['gui-observation.json']['actual_registry']:
                row.update(source=str(handler), source_sha256=sha(handler.read_bytes()), module_spec='#<path:' + str(handler) + '>')
            rec = data['gui-observation.json']['records'][0]
            rec['terminal']['handler_keys'] = ['(#<path:' + str(handler) + '> go)']
            data['capture-host.json'].update(workload_started_monotonic_ms=20, edit_dispatched_monotonic_ms=90,
                workload_completed_monotonic_ms=410, post_join_final_verification_monotonic_ms=460, heartbeat_verified=True)
            data['activation.json'] = {'schema_version': 1, 'kind': 'gui_interval_map_activation', 'arm': arm,
                'verified': True, 'gui_handler_thread': True, 'gui_module_already_instantiated': True,
                'gui_phase0_import_verified': True, 'interval_map_already_instantiated': True, 'gui_namespace_base_phase': 0,
                'gui_module': 'drracket/private/syncheck/gui', 'interval_map_module': 'data/interval-map',
                'flag_name': 'OPENRACKET_INTERVAL_MAP_FAST_SET', 'activation_export': 'openracket-interval-map-fast-set-enabled?',
                'phase_points_enabled': False, 'source': str(interval), 'source_sha256': self.pins[arm + '_sha256'],
                'expected_source_sha256': self.pins[arm + '_sha256'], 'flag_value': None if arm == 'stock' else '1',
                'export_status': 'missing' if arm == 'stock' else 'boolean', 'fast_set_enabled': None if arm == 'stock' else True}
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
                 ('export_status','missing'),('flag_value',None),('fast_set_enabled',False),('gui_phase0_import_verified',False),
                 ('phase_points_enabled',True),('interval_map_already_instantiated',False)]
        for key,value in changes:
            self.arms=copy.deepcopy(original);self.arms['candidate']['activation.json'][key]=value
            with self.subTest(key=key):self.reject()
    def test_actual_source_and_support_mutation_refused(self):
        source=Path(self.arms['candidate']['activation.json']['source']); original=source.read_bytes()
        source.write_bytes(b'changed');self.reject();source.write_bytes(original)
        (source.parent/'skip-list.rkt').write_bytes(b'changed');self.reject()
    def test_foreign_equal_module_source_refused(self):
        act=self.arms['candidate']['activation.json'];foreign=Path(self.temp.name)/'foreign/data/interval-map.rkt'
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
                            ('post_edit_deadline_monotonic_ms',460),('heartbeat_verified',False),('workload_completed_monotonic_ms',240)]:
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

if __name__=='__main__':unittest.main()
