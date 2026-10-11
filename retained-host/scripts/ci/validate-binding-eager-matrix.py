#!/usr/bin/env python3
"""Aggregate six independent complete-work commands and three strict pair gates."""
import json,math,pathlib,sys

EXPECTED=[(1,'stock'),(1,'candidate'),(2,'candidate'),(2,'stock'),(3,'stock'),(3,'candidate')]

def number(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False

def eager_exposure(binding,arm,export):
    """Independently enforce the preregistered compatibility bound and no deferred work."""
    if (not isinstance(binding,dict) or type(binding.get('schema_version')) is not int
        or binding['schema_version']!=1 or binding.get('kind')!='binding-table-eager-public-exposure'
        or binding.get('arm')!=arm or binding.get('verified') is not True
        or binding.get('status')!='complete' or binding.get('same_public_hash_identity') is not True):
        raise ValueError('missing distinct complete eager exposure evidence')
    duration=binding['first_duration_ms'];second_duration=binding['second_duration_ms']
    if not all(number(v) and v>=0 for v in (duration,second_duration)):
        raise ValueError('invalid getter duration')
    points=[binding[k]['monotonic_ms'] for k in ('first_start','first_end','second_start','second_end')]
    if not all(number(v) for v in points) or points!=sorted(points):raise ValueError('invalid getter clocks')
    if duration!=points[1]-points[0] or second_duration!=points[3]-points[2]:raise ValueError('getter duration does not match raw clocks')
    before,first,second=(binding[k] for k in ('before_state','after_first_state','after_second_state'))
    if arm=='stock':
        if any(v is not None for v in (before,first,second,binding['first_getter_max_ms'],binding['first_getter_bound_passed'])):
            raise ValueError('stock contains candidate eager state or bound')
        return
    if not number(binding['first_getter_max_ms']) or binding['first_getter_max_ms']!=1.0 or binding['first_getter_bound_passed'] is not True or duration>1.0:
        raise ValueError('candidate first public getter exceeds or lacks fixed 1.000 ms gate')
    bools={'enabled','active','in_flight','exposed'}
    counts={'generation','accepted','duplicates','eager_writes','stock_calls','pending','materializations','public_keys','indexed_edges','cached_starts','unsupported_fallbacks','failure_fallbacks'}
    for state in (before,first,second):
        if (not isinstance(state,dict) or set(state)!=bools|counts|{'fallback_reason'}
            or any(type(state[k]) is not bool for k in bools)
            or any(type(state[k]) is not int or state[k]<0 for k in counts)):
            raise ValueError('malformed eager state')
    if (before['enabled'] is not True or before['active'] is not True
        or before['in_flight'] is not False or before['exposed'] is not False
        or before['generation']<=0 or before['fallback_reason'] is not False
        or not before['accepted']==before['eager_writes']==before['indexed_edges']==export['edge_count']>0
        or not before['cached_starts']==before['public_keys']==export['key_count']>0
        or any(before[k]!=0 for k in ('pending','materializations','stock_calls','unsupported_fallbacks','failure_fallbacks'))):
        raise ValueError('eager writes or zero-deferred-work proof absent before exposure')
    if (first['enabled'] is not True or first['exposed'] is not True
        or first['active'] is not False or first['in_flight'] is not False
        or first['fallback_reason']!='public-exposure'
        or any(first[k]!=before[k] for k in ('generation','accepted','duplicates','eager_writes','public_keys'))
        or any(first[k]!=0 for k in ('pending','materializations','stock_calls','indexed_edges','cached_starts','unsupported_fallbacks','failure_fallbacks'))
        or first!=second):
        raise ValueError('cache disposal, eager graph preservation or repeated exposure proof absent')

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
    baseline=None;profiles=set();addons=set()
    for index,row in enumerate(pairs):
        data=row.get('data') if isinstance(row,dict) else None
        ok=(isinstance(row,dict) and type(row.get('pair')) is int and row['pair']==index+1
            and row.get('command_passed') is True and isinstance(data,dict)
            and data.get('accepted') is True and data.get('failures')==[]
            and number(data.get('candidate_first_getter_max_ms')) and data['candidate_first_getter_max_ms']==1.0)
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
                eager_exposure(evidence['binding_export'],arm,export)
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
    print('OPENRACKET_BINDING_EAGER_MATRIX '+json.dumps(result,sort_keys=True))
    sys.exit(0 if result['accepted'] else 1)
