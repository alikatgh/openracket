#!/usr/bin/env python3
"""Conservative scalar evidence validator. No timing or byte-allocation claims."""
import argparse,json
from generate import CATEGORIES,ROOT,sha
from pathlib import PurePosixPath
STATS=('matches','vectors','slots','max_slots','returns','fallbacks')
KEYS={'schema','enabled','instance','started','active','stop_reason','attempt_cap','match_cap',
      'attempts','matches','diagnostic_faults','scope','allocation_unit','eligibility'}|{
      f"{c.replace('-','_')}_{s}" for c in CATEGORIES for s in STATS}

def validate(state):
    if not isinstance(state,dict) or set(state)!=KEYS:raise ValueError('observation shape')
    if state['schema']!='openracket-object-hash-probe/v1':raise ValueError('schema')
    for key in ('enabled','started','active'):
        if type(state[key]) is not bool:raise ValueError('boolean type')
    if type(state['instance']) is not str or not state['instance'].startswith('object-hash-probe-v1') or len(state['instance'])>256:raise ValueError('instance')
    if state['scope']!='registered-handler-default-hash-entries' or state['allocation_unit']!='original-struct-vector-slots':raise ValueError('scope/unit')
    if state['attempt_cap']!=20000 or type(state['attempt_cap']) is not int or state['match_cap']!=128 or type(state['match_cap']) is not int:raise ValueError('cap')
    for key in ('attempts','matches','diagnostic_faults'):
        if type(state[key]) is not int or state[key]<0:raise ValueError('counter type')
    if not 0<=state['matches']<=128 or not state['matches']<=state['attempts']<=20000:raise ValueError('cap/count consistency')
    if state['active'] or state['stop_reason'] not in ('not-armed','host-complete','host-aborted','match-cap','attempt-cap','diagnostic-fault'):raise ValueError('not stopped/reason')
    if state['started']:
        if not state['enabled'] or state['stop_reason']=='not-armed':raise ValueError('started window has inconsistent terminal state')
    elif state['stop_reason']!='not-armed' or state['attempts'] or state['matches'] or state['diagnostic_faults']:
        raise ValueError('never-started window has activity or terminal reason')
    if state['stop_reason']=='diagnostic-fault' and not state['diagnostic_faults']:raise ValueError('false diagnostic-fault reason')
    if state['stop_reason']=='match-cap' and state['matches']!=128:raise ValueError('false match cap')
    if state['stop_reason']=='attempt-cap' and state['attempts']!=20000:raise ValueError('false attempt cap')
    if not state['enabled'] and (state['started'] or state['attempts'] or state['diagnostic_faults']):raise ValueError('disabled observer activity')
    sums={s:0 for s in STATS}; eligible=0
    for c in CATEGORIES:
        group={s:state[f"{c.replace('-','_')}_{s}"] for s in STATS}
        if any(type(v) is not int or v<0 for v in group.values()):raise ValueError('category scalar type')
        if not group['fallbacks']<=group['returns']<=group['vectors']<=group['matches']:raise ValueError('category completion order')
        if (group['vectors']==0)!=(group['slots']==0) or (group['vectors']==0)!=(group['max_slots']==0):raise ValueError('vector slots without allocations')
        if not group['vectors']<=group['slots'] or not group['max_slots']<=group['slots']<=group['max_slots']*group['vectors']:raise ValueError('slot bounds')
        for k,v in group.items():sums[k]+=v
        if c.endswith('-skipped') and not c.endswith('-not-skipped'):eligible+=group['fallbacks']
    if sums['matches']!=state['matches']:raise ValueError('match reconciliation')
    inspection_failed=state['definitions_inspection_failed_matches']+state['interactions_inspection_failed_matches']
    expected=('unresolved-diagnostic-fault' if state['diagnostic_faults'] else
              'unresolved-inspection-failure' if inspection_failed else
              'unresolved-no-matching-calls' if not state['matches'] else
              'plain-skipped-original-fallback-observed' if eligible else
              'no-plain-skipped-fallback-observed-in-bounded-sample')
    if state['eligibility']!=expected:raise ValueError('eligibility category mismatch')
    complete=state['matches']==sums['vectors']==sums['returns']
    actionable=(state['enabled'] and state['started'] and state['matches']>0 and complete and not state['diagnostic_faults'] and not inspection_failed
                and state['stop_reason'] not in ('host-aborted','diagnostic-fault'))
    return {'schema':'openracket-object-hash-assessment/v1','actionable':actionable,
            'conclusion':('unresolved' if not actionable or not state['matches'] else
                          'eligible-original-fallback-observed' if eligible else
                          'no-eligible-call-observed-in-bounded-sample'),
            'matches':state['matches'],'completed_original_conversions':sums['returns'],
            'original_struct_vectors':sums['vectors'],'original_struct_vector_slots':sums['slots'],
            'incomplete_observations':state['matches']-sums['returns'],
            'candidate_speed_or_byte_saving_claim':False}

EDGES=[[6,17,19,25],[6,17,35,35],[6,17,36,37],[6,17,40,40],
       [6,17,44,44],[6,17,50,50],[27,31,45,49],[32,33,38,39]]
SOURCE_FIELDS={'schema','runtime_root','executable','flag','enabled','build_id','instance','sources',
               'host_sha256','workflow_window','dependency_recompile'}

def canonical(value):
    if type(value) is not str or not value.startswith('/') or value=='/' or str(PurePosixPath(value))!=value or '..' in PurePosixPath(value).parts:
        raise ValueError('canonical absolute path required')
    return PurePosixPath(value)

def validate_run(source,observation,result,graph):
    assessment=validate(observation)
    pins=json.loads((ROOT/'SOURCE-PINS.json').read_text())
    runtime_pins=json.loads((ROOT/'RUNTIME-PINS.json').read_text())
    if type(source) is not dict or set(source)!=SOURCE_FIELDS:raise ValueError('source proof shape')
    if source['schema']!='openracket-object-hash-source/v1' or source['build_id']!=pins['build_id']:raise ValueError('actual build proof')
    if source['instance']!=observation['instance'] or type(source['enabled']) is not bool or source['enabled'] is not observation['enabled'] or source['flag']!=('1' if observation['enabled'] else '0'):raise ValueError('actual instance/activation mismatch')
    if source['host_sha256']!=sha((ROOT/'native/tests/reference-host-0520.rkt').read_bytes()):raise ValueError('actual host proof')
    if source['workflow_window']!='check-syntax-command-through-binding-completion' or source['dependency_recompile']!='separate-required-preflight':raise ValueError('window/preflight status')
    root=canonical(source['runtime_root']);exe=canonical(source['executable'])
    if root not in exe.parents:raise ValueError('executable outside runtime')
    if type(source['sources']) is not dict or set(source['sources'])!=set(runtime_pins):raise ValueError('runtime pin closure')
    for module,pin in runtime_pins.items():
        row=source['sources'][module]
        if type(row) is not dict or set(row)!={'path','sha256'} or row['sha256']!=pin:raise ValueError('resolved module source mismatch')
        path=canonical(row['path'])
        if root not in path.parents or not str(path).endswith('/'+module+'.rkt'):raise ValueError('resolved module outside runtime')
    if type(result) is not dict or result.get('status')!='passed' or result.get('genuine_host') is not True or result.get('repeated_real_run') is not True or result.get('racket')!='9.3' or result.get('ui')!='stock' or result.get('follow_on_case')!='check-syntax':raise ValueError('accepted genuine host completion missing')
    follow=result.get('follow_on_result')
    if type(follow) is not dict or follow.get('status')!='passed' or follow.get('case')!='check-syntax':raise ValueError('workflow did not finish original assertions')
    if type(graph) is not list or any(type(edge) is not list or len(edge)!=4 or any(type(n) is not int for n in edge) for edge in graph) or graph!=EDGES:raise ValueError('original exact binding graph mismatch')
    assessment.update({'source_instance_proved':True,'original_host_workflow_completed':True,
                       'outer_native_acceptance':'separate-required-gate',
                       'dependency_recompile':'separate-required-preflight'})
    return assessment

def read_log(path):
    if path.stat().st_size>8*1024*1024:raise ValueError('raw log bound')
    lines=path.read_bytes().splitlines()
    def pairs(entries):
        d={}
        for k,v in entries:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    def record(prefix):
        records=[line[len(prefix)+1:] for line in lines if line.startswith(prefix+b' ')]
        if len(records)!=1 or len(records[0])>32768:raise ValueError('one bounded original record required: '+prefix.decode())
        return json.loads(records[0],object_pairs_hook=pairs,
                          parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    return validate_run(record(b'OPENRACKET_OBJECT_HASH_SOURCE'),
                        record(b'OPENRACKET_OBJECT_HASH_OBSERVATION'),
                        record(b'OPENRACKET_NATIVE_RESULT'),record(b'OPENRACKET_BINDING_GRAPH'))
if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('raw_log',type=Path);a=p.parse_args()
    print(json.dumps(read_log(a.raw_log),indent=2))
