"""Strict matched-setting matrix. Failed and incomplete tool outcomes stay visible."""
import re,copy,importlib.util,json,pathlib,sys
spec=importlib.util.spec_from_file_location('xref_pairs',pathlib.Path(__file__).with_name('validate-xref-pairs.py'));base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
LIMITS=(128,256,512);PREFERENCE='drracket:child-only-memory-limit'
def fingerprint(report,root,expected_bytes):
 f=base.fingerprint(report,root)
 assert f['preferences'][PREFERENCE]==str(expected_bytes),'Actual GUI preference does not match requested memory limit'
 f=copy.deepcopy(f);del f['preferences'][PREFERENCE]
 return f

def validate(rows,helper_sha256):
 errors=[];records=[];fingerprints=[];seen=set();profiles=set();addons=set()
 if not re.fullmatch("[0-9a-f]{64}",helper_sha256):return {"valid":False,"errors":[{"error":"Expected reviewed helper hash required"}],"trials":[]}
 for row in rows:
  label={'round':row.get('round'),'memory_limit_mib':row.get('memory_limit_mib')} if isinstance(row,dict) else {'round':None,'memory_limit_mib':None};summary=dict(label)
  try:
   assert isinstance(row,dict),'Record must be an object'
   round_number=row['round'];limit=row['memory_limit_mib'];assert type(round_number) is int and round_number in (1,2,3) and type(limit) is int and limit in LIMITS,'Unknown matrix arm'
   key=(round_number,limit);assert key not in seen,'Duplicate matrix arm';seen.add(key)
   d=row['data'];assert isinstance(d,dict),'Measurement record must be an object'
   o=d.get('observer_validation');o=o if isinstance(o,dict) else {}
   outcome=d.get('online_expansion_outcome');terminal=outcome.get('terminal') if isinstance(outcome,dict) else None;terminal=terminal if isinstance(terminal,dict) else {}
   summary.update(status=d.get('status'),exit_code=d.get('exit_code'),timeout=d.get('timeout'),tool_succeeded=o.get('tool_succeeded'),tool_outcome_category=o.get('tool_outcome_category'),explicit_out_of_memory=terminal.get('explicit_out_of_memory'),contention_observed=o.get('contention_observed'))
   assert d['status']=='complete' and d['exit_code']==0 and d['timeout'] is False,'Incomplete trial'
   assert o['verified'] is True and o['errors']==[],'Observer verification failed'
   worker=o['actual_worker'];expected=limit*1024**2
   assert worker['child_memory_limit']==expected and worker['memory_accounting_available'] is True,'Actual worker limit/accounting mismatch'
   assert worker['xref_flag'] is None and worker['xref_export_status']=='missing' and worker['xref_reply_cell_enabled'] is None,'xref experiment must be absent'
   assert worker['xref_sha256']=='acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7','Original xref source required'
   assert d['selected_language_settings']['status']=='complete' and d['selected_language_settings']['errors']=={}
   assert len(d['initial_coloring_key_samples'])==80 and d['exact_resulting_source_verified'] is True
   assert d['post_typing_lexer_settle']['complete'] is True and d['online_terminal_wait']['complete'] is True
   assert d['measurement_kind']=='stock_memory_configuration_with_common_compact_observer'
   setup=d['memory_profile_setup'];cfg=d['memory_limit_configuration'];runtime=pathlib.Path(row['runtime_root']).resolve()
   assert d['expected_memory_limit_bytes']==expected
   assert setup['verified'] is True and setup['errors']==[] and setup['exit_code']==0 and setup['timeout'] is False
   assert setup['configuration']==cfg and setup['helper_sha256']==helper_sha256,'Reviewed setup helper/evidence mismatch'
   assert cfg['status']=='verified' and cfg['phase']=='before-timed-gui' and cfg['runtime_version']=='9.3'
   assert pathlib.Path(cfg['runtime_root']).resolve()==runtime and pathlib.Path(cfg['runtime_executable']).resolve()==runtime/'bin/racket'
   for field in ('expected_limit_bytes','selected_limit_bytes','readback_limit_bytes','persisted_limit_bytes'):
    assert type(cfg[field]) is int and cfg[field]==expected,'Setup limit mismatch: '+field
   assert cfg['original_default_limit_bytes']==cfg['expected_default_limit_bytes']==128*1024**2
   assert cfg['legacy_preference_store_absent'] is True and cfg['runtime_fallback_store_absent'] is True
   assert cfg['profile_was_empty'] is True and cfg['addon_was_empty'] is True and cfg['gui_initialized'] is False
   assert cfg['only_expected_preference_changed'] is True and cfg['disk_key_count_before']==0 and cfg['disk_key_count_after']==1
   disk_key='plt:framework-pref:'+PREFERENCE
   assert cfg['preference_key']==PREFERENCE and cfg['persisted_preference_key']==disk_key
   assert cfg['one_key_delta']==[{'key':disk_key,'before_present':False,'after_value':expected}]
   home=pathlib.Path(cfg['profile_path']).resolve();addon=pathlib.Path(cfg['addon_path']).resolve()
   assert home!=addon and not home.is_relative_to(runtime) and not addon.is_relative_to(runtime)
   assert home not in profiles and addon not in addons,'Fresh profile/addon reused between trials'
   profiles.add(home);addons.add(addon)
   assert pathlib.Path(cfg['preference_store_path']).resolve().is_relative_to(home)
   assert re.fullmatch('[0-9a-f]{64}',cfg['preference_store_sha256'])
   pins={'eval_helpers':'e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62','framework_preferences':'59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c'}
   assert set(cfg['sources'])==set(pins)
   for name,pin in pins.items():
    source=cfg['sources'][name];assert source['sha256']==source['expected_sha256']==pin and pathlib.Path(source['path']).resolve().is_relative_to(runtime)

   fingerprints.append(fingerprint(d,row['runtime_root'],expected));summary['valid']=True
  except (AssertionError,KeyError,ValueError,TypeError,AttributeError) as e:
   summary.update(valid=False,error=str(e));errors.append({**label,'error':str(e)})
  records.append(summary)
 expected={(r,m) for r in (1,2,3) for m in LIMITS}
 if len(rows)!=9 or seen!=expected:errors.append({'error':'Exactly nine distinct cyclic-limit records are required','missing':sorted(expected-seen)})
 if fingerprints and not all(f==fingerprints[0] for f in fingerprints[1:]):errors.append({'error':'Settings besides the one memory preference, fixture, registry, observer or runtime differ'})
 return {'valid':not errors,'errors':errors,'trials':records,'scope':'Capacity/settings sensitivity only. Incomplete trials and actual unsuccessful tool outcomes stay explicit; differing outcomes are not equal completed work.'}
if __name__=='__main__':
 result=validate(json.loads(pathlib.Path(sys.argv[1]).read_text()),sys.argv[2]);print(json.dumps(result,indent=2));sys.exit(0 if result['valid'] else 1)
