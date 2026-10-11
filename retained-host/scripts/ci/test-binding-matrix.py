import copy,importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('matrix',pathlib.Path(__file__).with_name('validate-binding-matrix.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def complete():
 def arm(p,a):
  return dict(binding_export={'export':{'canonical_sha256':'a'*64,'key_count':10,'edge_count':20,'owning_editor_endpoints':True,'mutable_strong_equal_hash':True,'immutable_equal_set_values':True,'canonical_format':'racket-written-sorted-exact-integer-quadruples-v1'}},valid=True,actual_arm=a,terminal={'tag':'handler-results'},monitor={'trace_entries':123},source='/fixtures/mixed.rkt',registry=[['share/pkgs/online.rkt','sha','go',False]],actual_prefab='#s(real)',pending_run_settings='(actual)',profile_path=f'/runner/pair-{p}-{a}/profile',addon_path=f'/runner/pair-{p}-{a}/addon')
 return {'captures':[{'pair':p,'arm':a,'path':f'/runner/reports/pair-{p}-{a}','command_passed':True} for p,a in m.EXPECTED],
         'pairs':[{'pair':p,'command_passed':True,'data':{'accepted':True,'failures':[],'arms':{a:arm(p,a) for a in ('stock','candidate')}}} for p in range(1,4)]}
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
if __name__=='__main__':unittest.main()
