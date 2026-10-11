import copy,importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('matrix',pathlib.Path(__file__).with_name('validate-binding-eager-matrix.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def exposure(arm):
 before=dict(enabled=True,active=True,in_flight=False,exposed=False,generation=1,accepted=20,duplicates=4,eager_writes=20,stock_calls=0,pending=0,materializations=0,public_keys=10,indexed_edges=20,cached_starts=10,unsupported_fallbacks=0,failure_fallbacks=0,fallback_reason=False)
 after=dict(before,active=False,exposed=True,indexed_edges=0,cached_starts=0,fallback_reason='public-exposure')
 return dict(schema_version=1,kind='binding-table-eager-public-exposure',arm=arm,verified=True,status='complete',same_public_hash_identity=True,first_duration_ms=.5,second_duration_ms=.25,first_start={'monotonic_ms':10},first_end={'monotonic_ms':10.5},second_start={'monotonic_ms':11},second_end={'monotonic_ms':11.25},before_state=before if arm=='candidate' else None,after_first_state=after if arm=='candidate' else None,after_second_state=copy.deepcopy(after) if arm=='candidate' else None,first_getter_max_ms=1.0 if arm=='candidate' else None,first_getter_bound_passed=True if arm=='candidate' else None)
def complete():
 def arm(p,a):
  return dict(binding_export={**exposure(a),'export':{'canonical_sha256':'a'*64,'key_count':10,'edge_count':20,'owning_editor_endpoints':True,'mutable_strong_equal_hash':True,'immutable_equal_set_values':True,'canonical_format':'racket-written-sorted-exact-integer-quadruples-v1'}},valid=True,actual_arm=a,terminal={'tag':'handler-results'},monitor={'trace_entries':123},source='/fixtures/mixed.rkt',registry=[['share/pkgs/online.rkt','sha','go',False]],actual_prefab='#s(real)',pending_run_settings='(actual)',profile_path=f'/runner/pair-{p}-{a}/profile',addon_path=f'/runner/pair-{p}-{a}/addon')
 return {'captures':[{'pair':p,'arm':a,'path':f'/runner/reports/pair-{p}-{a}','command_passed':True} for p,a in m.EXPECTED],
         'pairs':[{'pair':p,'command_passed':True,'data':{'accepted':True,'failures':[],'candidate_first_getter_max_ms':1.0,'arms':{a:arm(p,a) for a in ('stock','candidate')}}} for p in range(1,4)]}
class MatrixTests(unittest.TestCase):
 def test_complete(self):self.assertTrue(m.validate(complete())['accepted'])
 def test_every_capture_failure_retained(self):
  for i in range(6):
   d=complete();d['captures'][i]['command_passed']=False;r=m.validate(d);self.assertFalse(r['accepted']);self.assertEqual(len(r['captures']),6);self.assertEqual(len(r['pairs']),3)
 def test_missing_duplicate_and_order(self):
  for rows in (complete()['captures'][:-1],complete()['captures'][::-1],[complete()['captures'][0]]*6):
   d=complete();d['captures']=rows;self.assertFalse(m.validate(d)['accepted'])
 def test_pair_malformed_or_failed(self):
  for data in (None,[],{}, {'accepted':1,'failures':[]},{'accepted':True,'failures':['incomplete']},{'accepted':False,'failures':[]}):
   d=complete();d['pairs'][1]['data']=data;r=m.validate(d);self.assertFalse(r['accepted']);self.assertEqual(len(r['pairs']),3)
 def test_pair_process_failed_or_reordered(self):
  d=complete();d['pairs'][1]['command_passed']=False;self.assertFalse(m.validate(d)['accepted'])
  d=complete();d['pairs'].reverse();self.assertFalse(m.validate(d)['accepted'])
 def test_reject_relative_reused_and_mislabelled_paths(self):
  for path in ('pair-1-stock','/runner/wrong','/runner/reports/pair-1-stock'):
   d=complete();d['captures'][1]['path']=path;self.assertFalse(m.validate(d)['accepted'])
 def test_wrong_schema_and_boolean_pair(self):
  for d in (None,[],{'captures':None,'pairs':None}):self.assertFalse(m.validate(d)['accepted'])
  d=complete();d['captures'][0]['pair']=True;self.assertFalse(m.validate(d)['accepted'])
 def test_cross_pair_mutations_rejected_even_when_each_pair_is_accepted(self):
  for key,value in [('terminal',{'tag':'handler-results','compiled_bytes':999}),('monitor',{'trace_entries':321}),('source','/other.rkt'),('registry',[['different','sha','go',False]]),('actual_prefab','other'),('pending_run_settings','other')]:
   d=complete()
   for arm in ('stock','candidate'):d['pairs'][1]['data']['arms'][arm][key]=value
   self.assertFalse(m.validate(d)['accepted'],key)
 def test_reused_profile_or_addon_across_pairs_rejected(self):
  for key in ('profile_path','addon_path'):
   d=complete();d['pairs'][1]['data']['arms']['stock'][key]=d['pairs'][0]['data']['arms']['stock'][key];self.assertFalse(m.validate(d)['accepted'])
 def test_export_differs_across_pairs(self):
  for key,value in [('canonical_sha256','b'*64),('key_count',11),('edge_count',21),('immutable_equal_set_values',False)]:
   d=complete()
   for a in ('stock','candidate'):d['pairs'][1]['data']['arms'][a]['binding_export']['export'][key]=value
   self.assertFalse(m.validate(d)['accepted'])
 def test_missing_arm_metadata_preserves_all_summaries(self):
  d=complete();d['pairs'][0]['data']['arms']['stock']=None;r=m.validate(d);self.assertFalse(r['accepted']);self.assertEqual(len(r['pairs']),3);self.assertEqual(len(r['captures']),6)
 def test_first_getter_fixed_boundary_and_raw_clock_binding(self):
  d=complete();b=d['pairs'][0]['data']['arms']['candidate']['binding_export'];b['first_duration_ms']=1.;b['first_end']['monotonic_ms']=11.;self.assertTrue(m.validate(d)['accepted'])
  for value in (1.000001,True,-1,float('nan'),float('inf'),10**400,'0.5'):
   d=complete();b=d['pairs'][0]['data']['arms']['candidate']['binding_export'];b['first_duration_ms']=value
   if type(value) in (int,float):b['first_end']['monotonic_ms']=10+value
   r=m.validate(d);self.assertFalse(r['accepted']);self.assertEqual(len(r['captures']),6);self.assertEqual(len(r['pairs']),3)
  d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export']['first_end']['monotonic_ms']=10.75;self.assertFalse(m.validate(d)['accepted'])
 def test_bound_cannot_be_widened_or_truthy_boolean(self):
  for value in (None,True,2,'1.0'):
   d=complete();d['pairs'][0]['data']['candidate_first_getter_max_ms']=value;self.assertFalse(m.validate(d)['accepted'])
   d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export']['first_getter_max_ms']=value;self.assertFalse(m.validate(d)['accepted'])
  d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export']['first_getter_bound_passed']=1;self.assertFalse(m.validate(d)['accepted'])
 def test_distinct_eager_schema_and_stock_absence(self):
  for arm in ('stock','candidate'):
   for key,value in [('kind','binding-table-public-exposure'),('schema_version',True),('same_public_hash_identity',False)]:
    d=complete();d['pairs'][0]['data']['arms'][arm]['binding_export'][key]=value;self.assertFalse(m.validate(d)['accepted'])
  for key in ('before_state','after_first_state','after_second_state','first_getter_max_ms','first_getter_bound_passed'):
   d=complete();d['pairs'][0]['data']['arms']['stock']['binding_export'][key]={};self.assertFalse(m.validate(d)['accepted'])
 def test_pending_work_fallbacks_and_state_shape_refused(self):
  for state in ('before_state','after_first_state','after_second_state'):
   for key in ('pending','materializations','stock_calls','unsupported_fallbacks','failure_fallbacks'):
    d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export'][state][key]=1;self.assertFalse(m.validate(d)['accepted'])
   for key,value in [('accepted',True),('enabled',1),('generation',-1),('extra',0)]:
    d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export'][state][key]=value;self.assertFalse(m.validate(d)['accepted'])
 def test_actual_eager_write_and_preservation_evidence(self):
  for state,key,value in [('before_state','accepted',19),('before_state','eager_writes',19),('before_state','indexed_edges',19),('before_state','cached_starts',9),('before_state','public_keys',9),('before_state','active',False),('before_state','generation',0),('before_state','fallback_reason','unsupported-input'),('after_first_state','accepted',19),('after_first_state','indexed_edges',1),('after_first_state','cached_starts',1),('after_first_state','fallback_reason',False),('after_second_state','duplicates',5)]:
   d=complete();d['pairs'][0]['data']['arms']['candidate']['binding_export'][state][key]=value;self.assertFalse(m.validate(d)['accepted'])
 def test_malformed_exposure_keeps_six_rows(self):
  for value in (None,[],{},False):
   d=complete();d['pairs'][1]['data']['arms']['candidate']['binding_export']=value;r=m.validate(d);self.assertFalse(r['accepted']);self.assertEqual(len(r['captures']),6);self.assertEqual(len(r['pairs']),3)
if __name__=='__main__':unittest.main()
