import copy,importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('matrix',pathlib.Path(__file__).with_name('validate-xref-pairs.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def rows():
 result=[]
 for pair in range(1,4):
  for mode in ('stock','candidate-on'):
   root='/tmp/runtime-'+mode
   worker={'actual_handler_registry':[{'module':root+'/share/pkgs/drracket/drracket/private/syncheck/online-comp.rkt','module_spec':'#<path:'+root+'/share/pkgs/drracket/drracket/private/syncheck/online-comp.rkt>','export':x,'monitor':x=='monitor'} for x in ('go','monitor')]}
   d={'status':'complete','exit_code':0,'timeout':False,'measurement_kind':'matched_gui_with_common_compact_observer','racket_version':'9.3','vm':'chez-scheme','os':'macosx','selected_language_settings':{'status':'complete','errors':{},'effective_annotations':'debug'},'preserved_settings':{'limit':'128MiB'},'ui_environment':{'theme':'unset'},'fixture_metadata':{'name':'mixed-1mib','sha256':'synthetic','path':root+'/fixture.rkt'},'observer_support_sha256':'same-helper','online_expansion_outcome':{'actual_prefab':'same-prefab','terminal':{'tag':'abnormal-termination','explicit_out_of_memory':True}},'initial_coloring_key_samples':[{} for _ in range(80)],'exact_resulting_source_verified':True,'post_typing_lexer_settle':{'complete':True},'online_terminal_wait':{'complete':True},'observer_validation':{'verified':True,'errors':[],'actual_worker':worker,'tool_succeeded':False,'tool_outcome_category':'abnormal-termination','contention_observed':True}}
   result.append({'pair':pair,'mode':mode,'runtime_root':root,'data':d})
 return result
class PairTests(unittest.TestCase):
 def test_equal_valid_oom_is_not_tool_success(self):
  result=m.validate(rows());self.assertTrue(result['valid']);self.assertTrue(all(p['same_actual_outcome'] for p in result['pairs']));self.assertFalse(any(p['both_tools_succeeded'] for p in result['pairs']))
 def test_different_actual_outcomes_remain_visible(self):
  data=rows();d=data[1]['data'];d['observer_validation'].update(tool_succeeded=True,tool_outcome_category='handler-results');d['online_expansion_outcome']['terminal']={'tag':'handler-results'}
  result=m.validate(data);self.assertFalse(result['pairs'][0]['same_actual_outcome']);self.assertTrue(result['trials'][1]['tool_succeeded'])
 def test_absolute_registry_display_spec_is_preserved_but_not_compared(self):
  data=rows();original=copy.deepcopy(data)
  self.assertNotEqual(data[0]['data']['observer_validation']['actual_worker']['actual_handler_registry'][0]['module_spec'],data[1]['data']['observer_validation']['actual_worker']['actual_handler_registry'][0]['module_spec'])
  self.assertTrue(m.validate(data)['matched_metadata']);self.assertEqual(data,original)
 def test_failed_trial_blocks_matrix(self):
  for field,value in [('status','timeout'),('exit_code',1),('timeout',True)]:
   data=rows();data[0]['data'][field]=value
   with self.assertRaises(AssertionError):m.validate(data)
 def test_missing_and_duplicate_pairs_block_matrix(self):
  data=rows();data[1]=copy.deepcopy(data[0])
  with self.assertRaises(AssertionError):m.validate(data)
  with self.assertRaises(AssertionError):m.validate(rows()[:-1])
 def test_settings_or_registry_or_helper_differences_refused(self):
  for key,value in [('selected_language_settings',{'status':'complete','errors':{},'effective_annotations':'none'}),('observer_support_sha256','changed'),('preserved_settings',{'limit':'256MiB'})]:
   data=rows();data[1]['data'][key]=value
   with self.assertRaises(AssertionError):m.validate(data)
  data=rows();data[1]['data']['observer_validation']['actual_worker']['actual_handler_registry'].reverse()
  with self.assertRaises(AssertionError):m.validate(data)
 def test_absent_contention_is_not_a_typing_claim(self):
  data=rows();data[1]['data']['observer_validation']['contention_observed']=False
  self.assertFalse(m.validate(data)['pairs'][0]['both_observed_contention'])
 def test_external_handler_path_refused(self):
  data=rows();data[0]['data']['observer_validation']['actual_worker']['actual_handler_registry'][0]['module']='/elsewhere/online-comp.rkt'
  with self.assertRaises(ValueError):m.validate(data)
if __name__=='__main__':unittest.main()
