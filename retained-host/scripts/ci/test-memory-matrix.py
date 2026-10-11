import copy,importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('memory_matrix','validate-memory-matrix.py');fixtures=module('xref_fixture','test-xref-pairs.py');HELPER='a'*64

def rows():
 template=fixtures.rows()[0];result=[];root=template['runtime_root']
 for r in (1,2,3):
  for limit in m.LIMITS:
   d=copy.deepcopy(template['data']);b=limit*1024**2;label=f'{r}-{limit}'
   d.update(expected_memory_limit_bytes=b,measurement_kind='stock_memory_configuration_with_common_compact_observer')
   d['preserved_settings']={m.PREFERENCE:str(b),'coloring':'#t'}
   d['observer_validation']['actual_worker'].update(child_memory_limit=b,memory_accounting_available=True,xref_flag=None,xref_export_status='missing',xref_reply_cell_enabled=None,xref_sha256='acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7')
   cfg={'status':'verified','phase':'before-timed-gui','runtime_version':'9.3','runtime_root':root,'runtime_executable':root+'/bin/racket','original_default_limit_bytes':128*1024**2,'expected_default_limit_bytes':128*1024**2,'legacy_preference_store_absent':True,'runtime_fallback_store_absent':True,'profile_was_empty':True,'addon_was_empty':True,'gui_initialized':False,'only_expected_preference_changed':True,'disk_key_count_before':0,'disk_key_count_after':1,'preference_key':m.PREFERENCE,'persisted_preference_key':'plt:framework-pref:'+m.PREFERENCE,'one_key_delta':[{'key':'plt:framework-pref:'+m.PREFERENCE,'before_present':False,'after_value':b}],'profile_path':'/tmp/home-'+label,'addon_path':'/tmp/addon-'+label,'preference_store_path':'/tmp/home-'+label+'/prefs.rktd','preference_store_sha256':'b'*64,'sources':{}}
   for name in ('expected_limit_bytes','selected_limit_bytes','readback_limit_bytes','persisted_limit_bytes'):cfg[name]=b
   for name,pin in {'eval_helpers':'e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62','framework_preferences':'59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c'}.items():cfg['sources'][name]={'path':root+'/'+name,'sha256':pin,'expected_sha256':pin}
   d['memory_limit_configuration']=cfg;d['memory_profile_setup']={'verified':True,'errors':[],'exit_code':0,'timeout':False,'configuration':cfg,'helper_sha256':HELPER}
   result.append({'round':r,'memory_limit_mib':limit,'runtime_root':root,'data':d})
 return result
class MemoryMatrix(unittest.TestCase):
 def test_valid_matrix_keeps_oom_distinct(self):
  data=rows();original=copy.deepcopy(data);r=m.validate(data,HELPER);self.assertTrue(r['valid'],r);self.assertEqual(data,original);self.assertFalse(any(t['tool_succeeded'] for t in r['trials']))
 def test_changed_outcome_remains_visible(self):
  data=rows();data[1]['data']['observer_validation'].update(tool_succeeded=True,tool_outcome_category='handler-results');data[1]['data']['online_expansion_outcome']['terminal']={'tag':'handler-results','explicit_out_of_memory':False}
  r=m.validate(data,HELPER);self.assertTrue(r['valid']);self.assertTrue(r['trials'][1]['tool_succeeded'])
 def test_incomplete_records_preserved_and_fail(self):
  data=rows();data[2]['data'].update(status='timeout',timeout=True,exit_code=-9)
  r=m.validate(data,HELPER);self.assertFalse(r['valid']);self.assertEqual(len(r['trials']),9);self.assertTrue(r['trials'][2]['timeout'])
 def test_failed_null_outcome_and_malformed_rows_remain_visible(self):
  for outcome in (None,[],{'terminal':None}):
   data=rows();data[0]['data'].update(status='failed',online_expansion_outcome=outcome,observer_validation=None)
   r=m.validate(data,HELPER);self.assertFalse(r['valid']);self.assertEqual(len(r['trials']),9);self.assertEqual(r['trials'][0]['status'],'failed')
  for value in (None,[],42):
   data=rows();data[0]['data']=value;r=m.validate(data,HELPER);self.assertFalse(r['valid']);self.assertEqual(len(r['trials']),9)
  data=rows();data[0]=None;r=m.validate(data,HELPER);self.assertFalse(r['valid']);self.assertEqual(len(r['trials']),9)
 def test_missing_duplicate_and_wrong_limit_rejected(self):
  self.assertFalse(m.validate(rows()[:-1],HELPER)['valid'])
  data=rows();data[1]=copy.deepcopy(data[0]);self.assertFalse(m.validate(data,HELPER)['valid'])
  data=rows();data[0]['memory_limit_mib']=1024;self.assertFalse(m.validate(data,HELPER)['valid'])
 def test_actual_worker_mismatch_rejected(self):
  for key,value in [('child_memory_limit',1),('memory_accounting_available',False),('xref_flag','1'),('xref_sha256','changed')]:
   data=rows();data[0]['data']['observer_validation']['actual_worker'][key]=value;self.assertFalse(m.validate(data,HELPER)['valid'])
 def test_one_key_and_persisted_configuration_required(self):
  for key,value in [('readback_limit_bytes',1),('disk_key_count_after',2),('gui_initialized',True),('legacy_preference_store_absent',False),('runtime_fallback_store_absent',False),('profile_was_empty',False),('one_key_delta',[])]:
   data=rows();data[0]['data']['memory_limit_configuration'][key]=value;self.assertFalse(m.validate(data,HELPER)['valid'])
 def test_helper_and_source_pins_required(self):
  self.assertFalse(m.validate(rows(),'c'*64)['valid'])
  data=rows();data[0]['data']['memory_limit_configuration']['sources']['eval_helpers']['sha256']='bad';self.assertFalse(m.validate(data,HELPER)['valid'])
 def test_unrelated_preferences_and_settings_equal(self):
  for key,value in [('coloring','#f'),(m.PREFERENCE,'123')]:
   data=rows();data[0]['data']['preserved_settings'][key]=value;self.assertFalse(m.validate(data,HELPER)['valid'])
  data=rows();data[0]['data']['selected_language_settings']['effective_annotations']='none';self.assertFalse(m.validate(data,HELPER)['valid'])
 def test_fresh_profiles_and_clone_paths_required(self):
  data=rows();a=data[0]['data']['memory_limit_configuration'];b=data[1]['data']['memory_limit_configuration'];b['profile_path']=a['profile_path'];b['addon_path']=a['addon_path'];b['preference_store_path']=a['preference_store_path'];self.assertFalse(m.validate(data,HELPER)['valid'])
  data=rows();data[0]['data']['memory_limit_configuration']['runtime_root']='/elsewhere';self.assertFalse(m.validate(data,HELPER)['valid'])
if __name__=='__main__':unittest.main()
