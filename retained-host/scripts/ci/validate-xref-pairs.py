"""Strict six-record metadata gate; outcomes stay separate from speed claims."""
import json,pathlib,sys

def fingerprint(report,root):
 root=pathlib.Path(root).resolve();worker=report['observer_validation']['actual_worker']
 registry=[]
 for row in worker['actual_handler_registry']:
  # module_spec is supplemental display text and stays untouched in raw evidence.
  # Compare the typed resolved module identity and actual dispatch flags only.
  registry.append({'module':str(pathlib.Path(row['module']).resolve().relative_to(root)),
                   'export':row['export'],'monitor':row['monitor']})
 return {'settings':report['selected_language_settings'],'preferences':report['preserved_settings'],
         'ui':report['ui_environment'],'prefab':report['online_expansion_outcome']['actual_prefab'],
         'registry':registry,'helper':report['observer_support_sha256'],
         'fixture':{k:v for k,v in report['fixture_metadata'].items() if k!='path'},
         'runtime':[report[k] for k in ('racket_version','vm','os')]}

def validate(rows):
 assert len(rows)==6,'Exactly three complete stock/candidate pairs required'
 keys={(r['pair'],r['mode']) for r in rows};assert keys=={(i,m) for i in range(1,4) for m in ('stock','candidate-on')}
 fingerprints=[];by_key={};outcomes=[]
 for row in rows:
  d=row['data'];assert d['status']=='complete' and d['exit_code']==0 and d['timeout'] is False,'Incomplete trial remains a failed gate'
  o=d['observer_validation'];assert o['verified'] is True and o['errors']==[]
  assert d['selected_language_settings']['status']=='complete' and d['selected_language_settings']['errors']=={}
  assert len(d['initial_coloring_key_samples'])==80 and d['exact_resulting_source_verified'] is True
  assert d['post_typing_lexer_settle']['complete'] is True and d['online_terminal_wait']['complete'] is True
  assert d['measurement_kind']=='matched_gui_with_common_compact_observer'
  fingerprints.append(fingerprint(d,row['runtime_root']));by_key[(row['pair'],row['mode'])]=d
  outcomes.append({'pair':row['pair'],'mode':row['mode'],'tool_succeeded':o['tool_succeeded'],
                   'tool_outcome_category':o['tool_outcome_category'],'contention_observed':o['contention_observed'],
                   'explicit_out_of_memory':d['online_expansion_outcome']['terminal'].get('explicit_out_of_memory',False)})
 assert all(f==fingerprints[0] for f in fingerprints[1:]),'Settings, fixture, registry or observer bytes differ across arms'
 pairs=[]
 for i in range(1,4):
  a,b=(by_key[(i,m)] for m in ('stock','candidate-on'))
  ao,bo=(x['observer_validation'] for x in (a,b))
  at,bt=(x['online_expansion_outcome']['terminal'] for x in (a,b))
  same=(ao['tool_outcome_category']==bo['tool_outcome_category'] and at.get('explicit_out_of_memory',False)==bt.get('explicit_out_of_memory',False))
  pairs.append({'pair':i,'same_actual_outcome':same,'both_tools_succeeded':ao['tool_succeeded'] is True and bo['tool_succeeded'] is True,
                'both_observed_contention':ao['contention_observed'] is True and bo['contention_observed'] is True,
                'interpretation':'Different outcomes block an equal-work ratio; observed OOM remains an unsuccessful tool outcome.'})
 return {'valid':True,'matched_metadata':True,'trials':outcomes,'pairs':pairs}
if __name__=='__main__':
 try:result=validate(json.loads(pathlib.Path(sys.argv[1]).read_text()))
 except (AssertionError,KeyError,ValueError,TypeError) as e:print(json.dumps({'valid':False,'error':str(e)}));sys.exit(1)
 print(json.dumps(result,indent=2))
