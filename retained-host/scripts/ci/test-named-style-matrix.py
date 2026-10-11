import copy,importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('matrix',ROOT/'validate-named-style-matrix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
e=m.binding_module

def fixture():
 export={'key_count':3,'edge_count':8,'canonical_format':'racket-written-sorted-exact-integer-quadruples-v1','canonical_sha256':'a'*64,'owning_editor_endpoints':True,'mutable_strong_equal_hash':True,'immutable_equal_set_values':True}
 entries=[{'label':label,'path':'/runtime/'+label+'.json','bytes':1,'raw_sha256':'b'*64,'canonical_sha256':'c'*64} for label in sorted(e.expected_labels())]
 pairs=[]
 for pair in range(1,4):
  arms={}
  for arm in ('stock','candidate'):
   rows=[]
   for i,label in enumerate(['before-open','after-open','ordinary-ready','post-join','final']):
    state=None
    if arm=='candidate':state={'enabled':True,'cache-valid':False,'lookups':100+(5 if i>=2 else 0),'hits':50+(3 if i>=2 else 0),'rebuilds':10,'members-traversed':200,'named-entries':20,'member-count':30}
    rows.append({'label':label,'style_list_identity':1,'actual_definitions_editor':True,'monotonic_ms':100+i,'state':state})
   style={'kind':'actual-editor-named-style-counters','arm':arm,'verified':True,'diagnostic_counters_synchronized':False,'synthetic_lookup_performed':False,'snapshots':rows,'workload_baseline':'before-open','style_list_replaced_on_open':False,'workload_counter_deltas':None if arm=='stock' else {'lookups':5,'hits':3,'rebuilds':0,'members-traversed':0,'named-entries':0,'member-count':0}}
   arms[arm]={'valid':True,'actual_arm':arm,'terminal':{'tag':'handler-results'},'monitor':{'messages':1},'source':'/fixture','registry':[['relative/module','hash','monitor',True]],'actual_prefab':'settings','pending_run_settings':'settings','profile_path':f'/tmp/pair-{pair}-{arm}-profile','addon_path':f'/tmp/pair-{pair}-{arm}-addon','binding_export':{'kind':'post-readiness-binding-graph','verified':True,'timed':False,'same_public_hash_identity':True,'export':copy.deepcopy(export)},'style_witness':style}
  pins={r['path']:r['raw_sha256'] for r in entries if r['label'].startswith(f'pair-{pair}-')}
  pairs.append({'pair':pair,'command_passed':True,'data':{'accepted':True,'failures':[],'arms':arms,'input_sha256':pins}})
 return {'captures':[{'pair':p,'arm':a,'path':f'/report/pair-{p}-{a}','command_passed':True} for p,a in m.EXPECTED],'pairs':pairs,'input_digests':{'schema_version':1,'kind':'named-style-input-digests','verified':True,'errors':[],'entries':entries}}
class MatrixTests(unittest.TestCase):
 def test_complete_fixture_and_false_cache_currency_allowed(self):self.assertTrue(m.validate(fixture())['accepted'])
 def reject(self,mutate):
  x=fixture();mutate(x);r=m.validate(x);self.assertFalse(r['accepted']);self.assertTrue(r['failures']);return r
 def test_failed_capture_retains_all_six(self):self.assertEqual(len(self.reject(lambda x:x['captures'][0].update(command_passed=False))['captures']),6)
 def test_failed_pair_null_rows_and_missing_arms(self):
  for mutate in (lambda x:x['pairs'][0]['data'].update(accepted=False),lambda x:x['pairs'].__setitem__(1,None),lambda x:x['pairs'][0]['data']['arms'].__setitem__('stock',None)):
   self.assertEqual(len(self.reject(mutate)['pairs']),3)
 def test_order_duplicates_and_bad_pair_bool_refused(self):
  for mutate in (lambda x:x['captures'].reverse(),lambda x:x['captures'].__setitem__(1,x['captures'][0]),lambda x:x['pairs'][0].update(pair=True)):
   self.reject(mutate)
 def test_unlike_internally_matched_pairs_refused(self):
  def change(x):
   for arm in ('stock','candidate'):x['pairs'][1]['data']['arms'][arm]['terminal']['tag']='other'
  self.reject(change)
 def test_graph_change_and_missing_fields(self):
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['binding_export']['export'].update(edge_count=9))
  self.reject(lambda x:x['pairs'][0]['data']['arms']['stock']['binding_export']['export'].pop('canonical_sha256'))
 def test_profile_or_addon_reuse(self):
  self.reject(lambda x:x['pairs'][2]['data']['arms']['candidate'].update(addon_path='/tmp/pair-1-stock-profile'))
 def test_startup_only_activity_or_false_deltas(self):
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['snapshots'][2]['state'].update(lookups=100))
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['workload_counter_deltas'].update(hits=4))
 def test_bool_counter_late_replacement_and_missing_snapshot(self):
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['snapshots'][2]['state'].update(lookups=True))
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['snapshots'][3].update(style_list_identity=2))
  self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['snapshots'].pop())
 def test_huge_timestamp_preserves_other_summaries(self):
  r=self.reject(lambda x:x['pairs'][0]['data']['arms']['candidate']['style_witness']['snapshots'][0].update(monotonic_ms=10**400));self.assertEqual(len(r['pairs']),3)
 def test_digest_map_required_and_verified(self):
  self.reject(lambda x:x.pop('input_digests'));self.reject(lambda x:x['input_digests'].update(verified=False))
 def test_malformed_pair_key_and_schema_bool_retain_summaries(self):
  self.assertEqual(len(self.reject(lambda x:x['pairs'][0].update(pair=[]))['pairs']),3)
  self.reject(lambda x:x['input_digests'].update(schema_version=True))
  self.reject(lambda x:x['input_digests']['entries'][0].update(bytes=0))
 def test_digest_duplicate_path_and_wrong_receipt(self):
  self.reject(lambda x:x['input_digests']['entries'][1].update(path=x['input_digests']['entries'][0]['path']))
  self.reject(lambda x:x['pairs'][0]['data'].update(input_sha256={}))
if __name__=='__main__':unittest.main()
