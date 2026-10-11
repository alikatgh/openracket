#!/usr/bin/env python3
"""Aggregate six independent complete-work commands and three strict pair gates."""
import json,pathlib,sys

EXPECTED=[(1,'stock'),(1,'candidate'),(2,'candidate'),(2,'stock'),(3,'stock'),(3,'candidate')]

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
    print('OPENRACKET_INTERVAL_MATRIX '+json.dumps(result,sort_keys=True))
    sys.exit(0 if result['accepted'] else 1)
