#!/usr/bin/env python3
"""Aggregate six independent complete-work commands and three strict pair gates."""
import importlib.util,json,math,pathlib,sys
spec=importlib.util.spec_from_file_location("input_binding",pathlib.Path(__file__).with_name("named-style-evidence.py"));binding_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding_module)

EXPECTED=[(1,'stock'),(1,'candidate'),(2,'candidate'),(2,'stock'),(3,'stock'),(3,'candidate')]

def number(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False

def style_activity(value,arm):
    if (type(value) is not dict or value.get('kind')!='actual-editor-named-style-counters'
        or value.get('arm')!=arm or value.get('verified') is not True
        or value.get('diagnostic_counters_synchronized') is not False
        or value.get('synthetic_lookup_performed') is not False):raise ValueError('Actual style activity absent')
    rows=value.get('snapshots');labels=['before-open','after-open','ordinary-ready','post-join','final']
    if type(rows) is not list or len(rows)!=5:raise ValueError('All five style snapshots required')
    counts={'lookups','hits','rebuilds','members-traversed','named-entries','member-count'}
    for row,label in zip(rows,labels):
        if type(row) is not dict or row.get('label')!=label or row.get('actual_definitions_editor') is not True or type(row.get('style_list_identity')) is not int or not number(row.get('monotonic_ms')):raise ValueError('Malformed style snapshot')
        state=row.get('state')
        if arm=='stock':
            if state is not None:raise ValueError('Stock candidate state')
        elif (type(state) is not dict or set(state)!=counts|{'enabled','cache-valid'}
              or state['enabled'] is not True or type(state['cache-valid']) is not bool
              or any(type(state[k]) is not int or state[k]<0 for k in counts)):raise ValueError('Style scalar shape')
    ids=[r['style_list_identity'] for r in rows];times=[r['monotonic_ms'] for r in rows]
    if ids[0]!=1 or ids[1] not in (1,2) or ids[1:]!=[ids[1]]*4 or times!=sorted(times):raise ValueError('Style identities or order')
    index=0 if ids[0]==ids[1] else 1
    if value.get('style_list_replaced_on_open') is not (index==1) or value.get('workload_baseline')!=labels[index]:raise ValueError('Cross-instance baseline')
    if arm=='candidate':
        deltas={k:rows[2]['state'][k]-rows[index]['state'][k] for k in counts}
        if value.get('workload_counter_deltas')!=deltas or any(deltas[k]<=0 for k in ('lookups','hits')):raise ValueError('Startup-only or false activity deltas')
    elif value.get('workload_counter_deltas') is not None:raise ValueError('Stock activity deltas fabricated')

def validate(value):
    failures=[];capture_summary=[];pair_summary=[]
    if not isinstance(value,dict):return {'accepted':False,'failures':['matrix must be an object'],'captures':[],'pairs':[]}
    captures=value.get('captures');pairs=value.get('pairs')
    if not isinstance(captures,list):captures=[];failures.append('captures must be a list')
    if not isinstance(pairs,list):pairs=[];failures.append('pairs must be a list')
    if len(captures)!=6:failures.append('exactly six capture rows required')
    if len(pairs)!=3:failures.append('exactly three pair rows required')
    seen_paths=set()
    for index,row in enumerate(captures):
        ok=isinstance(row,dict)
        if ok:
            pair=row.get('pair');arm=row.get('arm');path=row.get('path')
            ok=(index<len(EXPECTED) and type(pair) is int and (pair,arm)==EXPECTED[index]
                and row.get('command_passed') is True and isinstance(path,str)
                and pathlib.Path(path).is_absolute() and pathlib.Path(path).name==f'pair-{pair}-{arm}' and path not in seen_paths)
            if isinstance(path,str):seen_paths.add(path)
        capture_summary.append({'index':index,'passed':bool(ok),'record':row})
        if not ok:failures.append(f'capture row {index} is missing, malformed, reordered, duplicated or failed')
    digest_map=value.get('input_digests')
    if (type(digest_map) is not dict or type(digest_map.get('schema_version')) is not int or digest_map.get('schema_version')!=1
        or digest_map.get('kind')!='named-style-input-digests' or digest_map.get('verified') is not True
        or digest_map.get('errors')!=[] or type(digest_map.get('entries')) is not list
        or len(digest_map['entries'])!=62):failures.append('complete raw/canonical input binding required')
    elif binding_module.binding_errors(digest_map['entries'],{r.get('pair'):r.get('data') for r in pairs if type(r) is dict and type(r.get('pair')) is int}):
        failures.append('raw input digests do not bind exact actual pair receipts')
    baseline=None;profiles=set();addons=set()
    for index,row in enumerate(pairs):
        data=row.get('data') if isinstance(row,dict) else None
        ok=(isinstance(row,dict) and type(row.get('pair')) is int and row['pair']==index+1
            and row.get('command_passed') is True and isinstance(data,dict)
            and data.get('accepted') is True and data.get('failures')==[])
        pair_summary.append({'index':index,'passed':bool(ok),'pair':row.get('pair') if isinstance(row,dict) else None,
                             'command_passed':row.get('command_passed') if isinstance(row,dict) else None,
                             'pair_accepted':data.get('accepted') if isinstance(data,dict) else None})
        if not ok:failures.append(f'pair row {index} is missing, malformed or not strictly accepted')
        arms=data.get('arms') if isinstance(data,dict) else None
        for arm in ('stock','candidate'):
            evidence=arms.get(arm) if isinstance(arms,dict) else None
            try:
                if not isinstance(evidence,dict) or evidence.get('valid') is not True or evidence.get('actual_arm')!=arm:
                    raise ValueError('validated arm identity absent')
                keys=('terminal','monitor','source','registry','actual_prefab','pending_run_settings')
                fingerprint={k:evidence[k] for k in keys}
                export=evidence['binding_export']['export']
                if not isinstance(export,dict) or set(export)!={'key_count','edge_count','canonical_format','canonical_sha256','owning_editor_endpoints','mutable_strong_equal_hash','immutable_equal_set_values'}:raise ValueError('missing complete binding export')
                if not all(type(export[k]) is int and 1<=export[k]<=300000 for k in ('key_count','edge_count')) or export['key_count']>export['edge_count']:raise ValueError('invalid binding counts')
                if export['canonical_format']!='racket-written-sorted-exact-integer-quadruples-v1' or not isinstance(export['canonical_sha256'],str) or len(export['canonical_sha256'])!=64 or any(c not in '0123456789abcdef' for c in export['canonical_sha256']):raise ValueError('invalid binding digest')
                if not all(export[k] is True for k in ('owning_editor_endpoints','mutable_strong_equal_hash','immutable_equal_set_values')):raise ValueError('invalid binding shape')
                binding=evidence['binding_export']
                if binding.get('kind')!='post-readiness-binding-graph' or binding.get('verified') is not True or binding.get('timed') is not False or binding.get('same_public_hash_identity') is not True:raise ValueError('Full untimed graph proof absent')
                style_activity(evidence['style_witness'],arm)
                fingerprint['binding_export']=export
                if any(v is None for v in fingerprint.values()):raise ValueError('missing cross-pair metadata')
                if not all(isinstance(fingerprint[k],dict) for k in ('terminal','monitor')):raise ValueError('terminal/monitor schema')
                if not isinstance(fingerprint['registry'],list) or not fingerprint['registry']:raise ValueError('registry schema')
                if not all(isinstance(fingerprint[k],str) and fingerprint[k] for k in ('source','actual_prefab','pending_run_settings')):raise ValueError('source/settings schema')
                encoded=json.dumps(fingerprint,sort_keys=True,separators=(',',':'),allow_nan=False)
                if baseline is None:baseline=encoded
                elif encoded!=baseline:raise ValueError('complete-work metadata differs across pairs')
                home=evidence['profile_path'];addon=evidence['addon_path']
                if not all(isinstance(p,str) and pathlib.Path(p).is_absolute() for p in (home,addon)):raise ValueError('invalid profile/addon paths')
                if home==addon or home in profiles|addons or addon in profiles|addons:raise ValueError('profile or addon reused across trials')
                profiles.add(home);addons.add(addon)
            except (KeyError,TypeError,ValueError) as error:
                failures.append(f'pair {index+1} {arm}: {error}')
    if len(profiles)!=6 or len(addons)!=6:failures.append('six distinct verified profile/addon pairs required')
    return {'accepted':not failures,'failures':failures,'captures':capture_summary,'pairs':pair_summary,
            'scope':'Three strictly accepted matched pairs; this aggregate does not itself calculate a speed claim.'}

if __name__=='__main__':
    result=validate(json.loads(pathlib.Path(sys.argv[1]).read_text()))
    print('OPENRACKET_NAMED_STYLE_MATRIX '+json.dumps(result,sort_keys=True))
    sys.exit(0 if result['accepted'] else 1)
