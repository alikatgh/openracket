#!/usr/bin/env python3
"""Isolated 20ms-stock/8ms-budget experiment, with scan and appearance absent."""
import hashlib, json, os, pathlib, statistics, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXP = ROOT/'experiments/color-budget'
os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'], ['correctness'], ['performance'])
PHASE = sys.argv[1]
TEMP = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK = pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
BUDGET = STOCK.with_name(STOCK.name+'-budget')
assert STOCK.is_relative_to(TEMP) and BUDGET.is_relative_to(TEMP)
REPORTS = ROOT/'reports/budget-ci'; REPORTS.mkdir(parents=True,exist_ok=True)
STATE = REPORTS/'results.json'
ROWS = json.loads(STATE.read_text()) if STATE.exists() else []
START_ROWS = len(ROWS)
sys.path.insert(0,str(ROOT/'performance'))
from run import terminate_group

def record(name, ok, detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail})
    STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_BUDGET_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Isolated cooperative coloring-budget experiment','',
           'Commit: '+os.environ['GITHUB_SHA'],
           'Pinned full Racket 9.3: pristine stock20ms versus separate budget8ms deep copy. Scan and appearance overlays absent in both arms.','',
           '| Check | Outcome | Detail |','|---|---|---|']
    lines += ['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
    lines += ['', 'Matched fresh-process typing during initial coloring. This is closed-loop synthetic editor input, not physical input-to-photon. Completion requires exact final source, final lexer validity, contention and equal settings. Background expansion completion is not measured.',
              'Prior native acceptance gates and unresolved long-callback Stop evidence remain in source/history. No artifact, cache, release or package upload.']
    (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def runtime(arm):
    assert arm in ('stock','budget8')
    return STOCK if arm=='stock' else BUDGET

def environment(arm, purpose):
    env=os.environ.copy(); selected=runtime(arm)
    env['RACKET']=str(selected/'bin/racket');env['RACO']=str(selected/'bin/raco')
    for key in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_NATIVE_APPEARANCE','OPENRACKET_NATIVE_GTK_CANDIDATE','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS','OPENRACKET_ALL_STRING_FAST_PATH','OPENRACKET_NATIVE_CASE','OPENRACKET_NATIVE_APPEARANCE_CHECK','OPENRACKET_READY_FILE','OPENRACKET_CAPTURE_DONE'):
        env.pop(key,None)
    if arm=='budget8': env['OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS']='8'
    env['PLTADDONDIR']=str(TEMP/('budget-'+arm+'-addon'))
    env['PLTUSERHOME']=str(TEMP/('budget-'+arm+'-'+purpose))
    env['XDG_CONFIG_HOME']=env['PLTUSERHOME']+'/.config'
    env['XDG_CACHE_HOME']=env['PLTUSERHOME']+'/.cache'
    pathlib.Path(env['PLTUSERHOME']).mkdir(exist_ok=True)
    print('OPENRACKET_BUDGET_PROFILE '+json.dumps({'arm':arm,'purpose':purpose,'addon':env['PLTADDONDIR'],'home':env['PLTUSERHOME'],'scan_flag':env.get('OPENRACKET_ALL_STRING_FAST_PATH'),'budget_flag':env.get('OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS'),'appearance':'unset'}),flush=True)
    return env

def command(name,args,arm='stock',purpose='checks',timeout=90,required=True,extra=None):
    print('\n::group::'+name,flush=True)
    env=environment(arm,purpose)
    if extra:env.update(extra)
    proc=subprocess.Popen([str(a) for a in args],env=env,start_new_session=True)
    try: result=proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired: terminate_group(proc);result=124
    record(name,result==0,'exit='+str(result));print('::endgroup::',flush=True)
    if required and result:raise RuntimeError(name+' failed')
    return result==0

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def frozen_sources():
    manifest=json.loads((EXP/'CONTENTS-SHA256.json').read_text())
    for name,expected in manifest.items():
        p=EXP/name
        assert p.is_file() and not p.is_symlink() and digest(p)==expected,name
    record('Frozen budget experiment source hashes',True,str(len(manifest))+' files')

def paths(arm):
    selected=runtime(arm);env=environment(arm,'source-resolution');found={}
    for key,parts in {'color':('color.rkt','framework','private'),'unit':('unit.rkt','drracket','private'),'framework':('text-misc.rkt','framework','private'),'toolbar':('switchable-button.rkt','mrlib')}.items():
        code='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
        p=pathlib.Path(subprocess.check_output([str(selected/'bin/racket'),'-e',code],env=env,text=True,timeout=30))
        assert not p.is_symlink() and p.resolve().is_relative_to(selected),str(p)
        found[key]=p.resolve()
    return found

def verify(arm):
    p=paths(arm);m=json.loads((EXP/'reports/budget-manifest.json').read_text())
    expected={'color':m['upstream_sha256'] if arm=='stock' else m['patched_sha256'],
              'unit':'535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5',
              'framework':'7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638',
              'toolbar':'532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de'}
    for key,value in expected.items():assert digest(p[key])==value,key+' changed'
    assert not p['unit'].with_name('openracket-all-string-snips.rkt').exists(),'Scan helper must be absent'
    assert not (p['toolbar'].parent/'private/openracket-paint.rkt').exists(),'Appearance overlay must be absent'
    print('OPENRACKET_BUDGET_SOURCE_PATHS '+json.dumps({'arm':arm,**{k:str(v) for k,v in p.items()},'sha256':expected}),flush=True)
    record(arm+' exact installed source verification',True,'Only budget arm color.rkt may differ; scan/appearance absent')
    return p

def activation(arm):
    expectation='stock' if arm=='stock' else '8'
    code='(begin (require (file '+json.dumps(str(EXP/'contention/budget-activation.rkt'))+')) (write (verify-budget-activation '+json.dumps(expectation)+')) (newline) (exit 0))'
    return command(arm+' actual loaded budget activation',[runtime(arm)/'bin/racket','-e',code],arm,'activation',required=False)

def compare_completed_trials():
    arms={}
    for arm in ('stock','budget8'):
        reports=[json.loads(p.read_text()) for p in sorted((REPORTS/('performance-'+arm)).glob('pair-*/mixed-1mib-*/measurements.json'))]
        expectation='stock' if arm=='stock' else '8'
        valid=[r for r in reports if r.get('status')=='complete' and r.get('exit_code')==0 and r.get('timeout') is False
               and all(r.get('ui_environment',{}).get(k)=='unset' for k in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_ALL_STRING_FAST_PATH'))
               and r.get('ui_environment',{}).get('OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS')==('unset' if arm=='stock' else '8')
               and r.get('measurement_kind')=='initial_coloring_typing'
               and r.get('post_typing_lexer_settle',{}).get('complete') is True
               and r.get('exact_resulting_source_verified') is True
               and r.get('keys_starting_with_lexer_invalid',0)>0
               and len(r.get('initial_coloring_key_samples',[]))==80
               and r.get('selected_language_settings',{}).get('status')=='complete'
               and r.get('scan_activation',{}).get('status')=='verified'
               and r.get('scan_activation',{}).get('expected')=='stock'
               and r.get('budget_activation',{}).get('status')=='verified'
               and r.get('budget_activation',{}).get('expected')==expectation]
        arms[arm]={'reports':reports,'valid':valid}
    all_valid=arms['stock']['valid']+arms['budget8']['valid']
    keys=('selected_language_settings','preserved_settings','racket_version','os','vm','fixture_metadata')
    # Fixture paths differ by profile; compare immutable fixture metadata below.
    def fingerprint(r):
        fixture=dict(r['fixture_metadata']);fixture.pop('path',None)
        return {**{k:r[k] for k in keys if k!='fixture_metadata'},'fixture_metadata':fixture}
    equal=bool(all_valid) and all(fingerprint(r)==fingerprint(all_valid[0]) for r in all_valid)
    complete=all(len(a['valid'])==3 for a in arms.values())
    result={'completed_trials':{a:len(d['valid']) for a,d in arms.items()},'expected_per_arm':3,
            'settings_runtime_fixture_equal_for_valid_trials':equal,
            'completed_workload_comparison_available':complete and equal,
            'warning':'Interleaved fresh-process typing during coloring. Background expansion completion, cold filesystem caches and input-to-photon are not measured. Any incomplete or non-contended trial blocks a complete comparison.'}
    if complete and equal:
        result['open_to_completed_workload_ms_median']={a:statistics.median(r['open_to_completed_workload_ms'] for r in d['valid']) for a,d in arms.items()}
        values=result['open_to_completed_workload_ms_median'];result['budget8_over_stock_readiness_ratio']=values['budget8']/values['stock']
    (REPORTS/'paired-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('OPENRACKET_BUDGET_PAIRED_COMPARISON '+json.dumps(result),flush=True)
    record('Complete contended workload and equal selected settings',complete and equal,json.dumps(result))

try:
    if PHASE=='prepare':
        frozen_sources()
        command('Synthetic budget comparison acceptance tests',[sys.executable,ROOT/'scripts/ci/test-budget-comparison.py'])
        command('Budget source, comparator and contention unit tests',[sys.executable,'-m','unittest','discover','-s',EXP/'tests','-p','test_*.py'])
        command('Budget configuration, activation and native fixture tests',[STOCK/'bin/raco','test',EXP/'tests/budget-test.rkt',EXP/'tests/budget-activation-test.rkt',EXP/'tests/native-fixture-test.rkt'])
        command('Contention process supervisor unit tests',[sys.executable,EXP/'contention/test_harness.py'])
        frozen_sources();verify('stock')
        command('Deep-copy independent budget runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','budget'],timeout=180)
        p=paths('budget8');m=json.loads((EXP/'reports/budget-manifest.json').read_text())
        assert digest(p['color'])==m['upstream_sha256']
        source=EXP/'overlay/framework/private/color.rkt';assert digest(source)==m['patched_sha256']
        p['color'].write_bytes(source.read_bytes());verify('budget8');verify('stock')
        command('Compile actual budget and all native callers',[BUDGET/'bin/raco','make',p['color'],EXP/'tests/native-lexer-equivalence.rkt',EXP/'contention/retained-host.rkt',ROOT/'tests/independent-native-host.rkt',ROOT/'tests/independent-native-workflows.rkt',ROOT/'tests/independent-native-stop-returning.rkt'],arm='budget8',timeout=180)
        command('Compile complete budget DrRacket entrypoint',[BUDGET/'bin/raco','make','-l','drracket/drracket'],arm='budget8',timeout=180)
    elif PHASE=='correctness':
        verify('stock');verify('budget8')
        for arm in ('stock','budget8'):
            activation(arm)
            for case in ('baseline','input-eof','wxme','check-syntax','stop-returning'):
                extra={'OPENRACKET_UI':'stock'}
                if case!='baseline':extra['OPENRACKET_NATIVE_CASE']=case
                command(arm+' actual host preservation '+case,[runtime(arm)/'bin/racket',ROOT/'tests/independent-native-host.rkt'],arm,case,timeout=60,required=False,extra=extra)
        lexer_results=[]
        for arm in ('stock','budget8'):
            lexer_results.append(command(arm+' actual retained-editor lexer outcomes',[runtime(arm)/'bin/racket',EXP/'tests/native-lexer-equivalence.rkt'],arm,'native-lexer',timeout=60,required=False,
                extra={'OPENRACKET_LEXER_OUTPUT':str(REPORTS/(arm+'-lexer.json')),'OPENRACKET_LEXER_MODE':arm}))
        if all(lexer_results):
            command('Exact budget lexer/token/style/parenthesis equivalence',[sys.executable,EXP/'tests/compare-native-lexer.py',REPORTS/'stock-lexer.json',REPORTS/'budget8-lexer.json'],required=False)
        else:record('Exact budget lexer/token/style/parenthesis equivalence',False,'At least one independent arm failed; timing remains blocked')
        verify('stock');verify('budget8')
    elif PHASE=='performance':
        for pair in (1,2,3):
            order=('budget8','stock') if pair==2 else ('stock','budget8')
            for arm in order:
                output=REPORTS/('performance-'+arm)/('pair-'+str(pair))
                command('Budget pair '+str(pair)+' '+arm+' matched 1 MiB contention workload',[sys.executable,EXP/'contention/run.py','--mode','budget-stock' if arm=='stock' else 'budget-8','--racket',runtime(arm)/'bin/racket','--output',output,'--fixture','mixed-1mib','--repetitions','1','--timeout','60','--scan-activation','stock','--budget-activation','stock' if arm=='stock' else '8'],arm,'performance-pair-'+str(pair),timeout=75,required=False)
        compare_completed_trials();verify('stock');verify('budget8')
except Exception as error:
    record(PHASE+' orchestration',False,str(error));raise
finally:
    print('Budget report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START_ROWS:]) else 0)
