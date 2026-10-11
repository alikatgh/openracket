"""Synthetic, fail-closed paired acceptance tests; never native timing evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import accept_named_style as accept
from test_accept_gui import arm_fixture


def sha(data): return hashlib.sha256(data).hexdigest()

class NamedStyleAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.arms, self.manifests, self.pins = {}, {}, {}
        for arm in ('stock', 'candidate'):
            root = base / arm; source = root / 'share/pkgs/drracket-core-lib/drracket/private'
            handler = source / 'syncheck/online-comp.rkt'; handler.parent.mkdir(parents=True)
            handler.write_bytes(b'common exact synthetic handler')
            gui = source / 'syncheck/gui.rkt'
            gui.write_bytes(b'common synthetic observed gui')
            style = root/'share/pkgs/snip-lib/racket/snip/private/style.rkt'; style.parent.mkdir(parents=True)
            style.write_bytes(('synthetic style ' + arm).encode())
            self.pins[arm + '_sha256'] = sha(style.read_bytes())
            diagnostic = {name: sha(('common synthetic ' + name).encode()) for name in accept.PINS}
            diagnostic['syncheck/gui.rkt'] = sha(gui.read_bytes())
            diagnostic['syncheck/online-comp.rkt'] = sha(handler.read_bytes())
            self.manifests[arm] = {'diagnostic_root': str(root), 'source_root': str(source), 'arm': arm,
                                   'stock_pins': dict(accept.PINS),
                                   'original_pins': dict(accept.PINS),
                                   'style_source': {'source':str(style), 'module':'racket/snip/private/style', 'sha256':self.pins[arm+'_sha256']},
                                   'diagnostic_sources': diagnostic, 'helpers': {'same': 'same'}}
            data = arm_fixture('control'); data['capture-supervisor.json']['experiment'] = 'named-style-index'; data['capture-host.json']['arm'] = arm; data['capture-supervisor.json']['arm'] = arm
            data['capture-supervisor.json'].update(expected_style_source_sha256=self.pins[arm+'_sha256'], production_style_source_sha256=self.pins[arm+'_sha256'], expected_gui_source_sha256=diagnostic['syncheck/gui.rkt'])
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
                post_export_final_currentness_verified=True, style_witness_verified=True)
            data['activation.json'] = dict(schema_version=1, kind='gui_named_style_index_activation', arm=arm,
                verified=True, gui_handler_thread=True, gui_module_already_instantiated=True,
                style_module_already_instantiated=True, syncheck_module_already_instantiated=True,
                syncheck_source=str(gui), syncheck_source_sha256=sha(gui.read_bytes()), same_gui_imported_style_instance=True, actual_editor_style_list=True,
                gui_namespace_base_phase=0, style_namespace_base_phase=0, gui_module='racket/gui/base',
                style_module='racket/snip/private/style', flag_name='OPENRACKET_NAMED_STYLE_INDEX',
                activation_export='openracket-named-style-index-enabled?', state_export='openracket-named-style-index-state',
                state_export_status='missing' if arm == 'stock' else 'procedure', phase_points_enabled=False,
                unexpected_experiment_flags=[], source=str(style), runtime_root=str(root),
                source_sha256=self.pins[arm+'_sha256'], expected_source_sha256=self.pins[arm+'_sha256'],
                flag_value=None if arm == 'stock' else '1', export_status='missing' if arm == 'stock' else 'boolean',
                named_style_index_enabled=None if arm == 'stock' else True)
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
            data['binding-export.json'] = dict(schema_version=1, kind='post-readiness-binding-graph', arm=arm,
                verified=True, status='complete', timed=False, same_public_hash_identity=True,
                started_monotonic_ms=462, verified_monotonic_ms=475, export=dict(key_count=5, edge_count=10,
                canonical_format='racket-written-sorted-exact-integer-quadruples-v1', canonical_sha256='a'*64,
                owning_editor_endpoints=True, mutable_strong_equal_hash=True, immutable_equal_set_values=True))
            def state(n):
                return {'enabled':True, 'cache-valid':True, 'lookups':n, 'hits':n-5, 'rebuilds':2,
                        'members-traversed':35, 'named-entries':3, 'member-count':5}
            data['style-witness.json'] = dict(schema_version=1, kind='actual-editor-named-style-counters', arm=arm,
                verified=True, diagnostic_counters_synchronized=False, synthetic_lookup_performed=False,
                workload_baseline='before-open', style_list_replaced_on_open=False,
                snapshots=[dict(label=label, style_list_identity=1, actual_definitions_editor=True,
                   monotonic_ms=t, state=None if arm == 'stock' else state(n))
                   for label,t,n in zip(accept.LABELS, (5,85,411,461,481), (100,101,150,151,151))])
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
                 ('export_status','missing'),('flag_value',None),('named_style_index_enabled',False),('same_gui_imported_style_instance',False),
                 ('phase_points_enabled',True), ('unexpected_experiment_flags', ['OPENRACKET_BINDING_TABLE_INDEX']),
                 ('unexpected_experiment_flags', None)]
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


    def test_all_style_fields_exact_types_required_at_every_checkpoint(self):
        original = copy.deepcopy(self.arms)
        for index in range(5):
            for field in accept.STATE_FIELDS:
                for mode in ('missing', 'wrong-type'):
                    self.arms = copy.deepcopy(original)
                    state = self.arms['candidate']['style-witness.json']['snapshots'][index]['state']
                    if mode == 'missing': del state[field]
                    else: state[field] = 1 if field in accept.STATE_BOOL_FIELDS else True
                    with self.subTest(index=index,field=field,mode=mode): self.reject()
            self.arms = copy.deepcopy(original)
            self.arms['candidate']['style-witness.json']['snapshots'][index]['state']['extra'] = 0
            self.reject()

    def test_startup_only_activity_never_qualifies(self):
        rows = self.arms['candidate']['style-witness.json']['snapshots']
        for row in rows: row['state']['lookups'] = row['state']['hits'] = 99999
        raw=copy.deepcopy(self.arms['candidate']['style-witness.json'])
        result=self.reject(); self.assertEqual(result['arms']['candidate']['raw_style_witness'],raw)

    def test_open_replacement_is_explicit_and_uses_postopen_baseline(self):
        w=self.arms['candidate']['style-witness.json']
        for row in w['snapshots'][1:]:row['style_list_identity']=2
        self.reject()
        w.update(style_list_replaced_on_open=True, workload_baseline='after-open')
        self.assertTrue(self.result()['accepted'], self.result())
        w['snapshots'][0]['state']['lookups']=100000
        self.assertTrue(self.result()['accepted']) # different-instance startup count never subtracted
        w['snapshots'][2]['state']=copy.deepcopy(w['snapshots'][1]['state'])
        self.reject()

    def test_late_style_replacement_missing_rows_synthetic_or_synchronized_rejected(self):
        original=copy.deepcopy(self.arms)
        for mutation in (lambda w:w['snapshots'][3].update(style_list_identity=2),
                         lambda w:w.update(synthetic_lookup_performed=True),
                         lambda w:w.update(diagnostic_counters_synchronized=True),
                         lambda w:w['snapshots'].pop(),
                         lambda w:w['snapshots'][0].update(style_list_identity=True),
                         lambda w:w['snapshots'][2].update(monotonic_ms=float('nan')),
                         lambda w:w['snapshots'][2].update(actual_definitions_editor=False)):
            self.arms=copy.deepcopy(original);mutation(self.arms['candidate']['style-witness.json']);self.reject()

    def test_unsynchronized_counter_ratios_are_not_invented_invariants(self):
        rows=self.arms['candidate']['style-witness.json']['snapshots']
        rows[2]['state'].update(hits=999999, rebuilds=1, **{'members-traversed':1, 'member-count':1, 'named-entries':0, 'cache-valid':False})
        result=self.result();self.assertTrue(result['accepted'],result)
        deltas=result['arms']['candidate']['style_witness']['workload_counter_deltas']
        self.assertEqual(deltas['rebuilds'],-1)
        self.assertEqual(result['arms']['candidate']['style_witness']['snapshots'], rows)

    def test_private_reader_module_import_source_and_flags_are_mandatory(self):
        original=copy.deepcopy(self.arms)
        for field,value in [('style_module','wrong'),('gui_module','wrong'),('style_namespace_base_phase',True),
                            ('style_module_already_instantiated',False),('actual_editor_style_list',False),
                            ('state_export_status','missing'),('state_export','wrong'),('runtime_root','/foreign')]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['activation.json'][field]=value
            with self.subTest(field=field):self.reject()

    def test_identical_gui_source_required_and_style_source_must_differ(self):
        self.manifests['candidate']['diagnostic_sources']['syncheck/gui.rkt']='f'*64;self.reject()

    def test_old_getter_experiment_and_getter_bounds_absent(self):
        result=self.result();self.assertTrue(result['accepted'])
        self.assertNotIn('candidate_first_getter_max_ms', result)
        self.arms['candidate']['binding-export.json']['first_start']={};self.reject()

    def test_untimed_graph_shape_digest_and_postexport_guards_required(self):
        original=copy.deepcopy(self.arms)
        for field,value in [('canonical_sha256','0'*64),('edge_count',11),('key_count',True),
                            ('owning_editor_endpoints',False),('immutable_equal_set_values',False)]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['binding-export.json']['export'][field]=value;self.reject()
        for field,value in [('timed',True),('same_public_hash_identity',False),('verified_monotonic_ms',90091)]:
            self.arms=copy.deepcopy(original);self.arms['candidate']['binding-export.json'][field]=value;self.reject()
        for field in ('binding_export_verified','post_export_final_currentness_verified','style_witness_verified'):
            self.arms=copy.deepcopy(original);self.arms['candidate']['capture-host.json'][field]=False;self.reject()

    def test_old_experiment_labels_are_rejected(self):
        original=copy.deepcopy(self.arms)
        for file,key,value in [('activation.json','kind','gui_binding_table_eager_activation'),
                               ('activation.json','flag_name','OPENRACKET_BINDING_TABLE_EAGER'),
                               ('binding-export.json','kind','binding-table-eager-public-exposure'),
                               ('capture-supervisor.json','experiment','binding-table-eager')]:
            self.arms=copy.deepcopy(original);self.arms['candidate'][file][key]=value;self.reject()

    def test_oversized_exact_json_timestamps_fail_without_losing_other_arm(self):
        import json
        from accept_gui import number
        huge = json.loads('{"t":' + '1' + '0' * 400 + '}')['t']
        self.assertFalse(number(huge)); self.assertFalse(accept.same(huge, 1))
        original = copy.deepcopy(self.arms)
        mutations = [lambda d:d['capture-host.json'].update(post_edit_deadline_monotonic_ms=huge),
                     lambda d:d['heartbeat.json'].update(started_monotonic_ms=huge),
                     lambda d:d['heartbeat.json']['records'][0].update(handler_monotonic_ms=huge),
                     lambda d:d['gui-observation.json']['records'][0]['gui_points']['application-enter'].update(monotonic_ms=huge),
                     lambda d:d['style-witness.json']['snapshots'][0].update(monotonic_ms=huge)]
        for mutate in mutations:
            self.arms=copy.deepcopy(original); mutate(self.arms['candidate'])
            result=self.reject()
            self.assertTrue(result['arms']['stock']['valid'])
            self.assertEqual(result['arms']['candidate']['raw_gui_records'],self.arms['candidate']['gui-observation.json']['records'])
            self.assertEqual(result['arms']['candidate']['raw_style_witness'],self.arms['candidate']['style-witness.json'])

if __name__=='__main__':unittest.main()
