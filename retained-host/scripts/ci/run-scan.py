#!/usr/bin/env python3
"""One isolated native scan experiment: correctness before matched timing."""
import hashlib, json, os, pathlib, statistics, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXP = ROOT/'experiments/snip-fastpath'
os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'], ['correctness'], ['performance'])
PHASE = sys.argv[1]
TEMP = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK = pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
SCAN = STOCK.with_name(STOCK.name+'-scan')
assert STOCK.is_relative_to(TEMP) and SCAN.is_relative_to(TEMP)
REPORTS = ROOT/'reports/scan-ci'; REPORTS.mkdir(parents=True,exist_ok=True)
STATE = REPORTS/'results.json'
ROWS = json.loads(STATE.read_text()) if STATE.exists() else []
START_ROWS = len(ROWS)
sys.path.insert(0,str(ROOT/'performance'))
from run import terminate_group

def record(name, ok, detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail})
    STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_SCAN_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Private scan experiment native checks','',
           'Commit: '+os.environ['GITHUB_SHA'],
           'Pinned full Racket 9.3; pristine stock and a separate deep copy. No appearance or color-budget experiment.','',
           '| Check | Outcome | Detail |','|---|---|---|']
    lines += ['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
    lines += ['', 'Only this fixture/scope is covered. Timing is not input-to-photon; runner results do not establish hardware-wide performance. Unfinished initial/final coloring is excluded from completed-workload comparisons.',
              'Prior appearance/Stop release gates remain in source/history; this speed-focused batch does not replace them. No artifact, cache, release or package upload.']
    (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def environment(arm, purpose):
    assert arm in ('stock','candidate')
    env=os.environ.copy()
    selected=STOCK if arm=='stock' else SCAN
    env['RACKET']=str(selected/'bin/racket'); env['RACO']=str(selected/'bin/raco')
    for name in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_NATIVE_APPEARANCE','OPENRACKET_NATIVE_GTK_CANDIDATE','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS','OPENRACKET_ALL_STRING_FAST_PATH'):
        env.pop(name,None)
    if arm == 'candidate': env['OPENRACKET_ALL_STRING_FAST_PATH']='1'
    env['PLTADDONDIR']=str(TEMP/('scan-'+arm+'-addon'))
    env['PLTUSERHOME']=str(TEMP/('scan-'+arm+'-'+purpose))
    env['XDG_CONFIG_HOME']=env['PLTUSERHOME']+'/.config'
    env['XDG_CACHE_HOME']=env['PLTUSERHOME']+'/.cache'
    pathlib.Path(env['PLTUSERHOME']).mkdir(exist_ok=True)
    print('OPENRACKET_SCAN_PROFILE '+json.dumps({'arm':arm,'purpose':purpose,'addon':env['PLTADDONDIR'],'home':env['PLTUSERHOME'],'scan_flag':env.get('OPENRACKET_ALL_STRING_FAST_PATH'),'budget_flag':env.get('OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS'),'appearance':'unset'}),flush=True)
    return env

def runtime(arm): return STOCK if arm=='stock' else SCAN

def command(name,args,arm='stock',purpose='checks',timeout=90,required=True):
    print('\n::group::'+name,flush=True)
    proc=subprocess.Popen([str(a) for a in args],env=environment(arm,purpose),start_new_session=True)
    try:
        result=proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_group(proc); result=124
    record(name,result==0,'exit='+str(result))
    print('::endgroup::',flush=True)
    if required and result: raise RuntimeError(name+' failed')
    return result==0

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def paths(arm):
    selected=runtime(arm); env=environment(arm,'source-resolution'); found={}
    for key,parts in {'unit':('unit.rkt','drracket','private'),'framework':('text-misc.rkt','framework','private'),'toolbar':('switchable-button.rkt','mrlib')}.items():
        code='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
        p=pathlib.Path(subprocess.check_output([str(selected/'bin/racket'),'-e',code],env=env,text=True,timeout=30))
        assert not p.is_symlink() and p.resolve().is_relative_to(selected), str(p)
        found[key]=p.resolve()
    found['helper']=found['unit'].with_name('openracket-all-string-snips.rkt')
    return found

def verify(arm):
    p=paths(arm)
    command(arm+' exact installed source verification',[sys.executable,EXP/'scripts/verify-installed-candidate.py','--root',runtime(arm),'--unit',p['unit'],'--framework',p['framework'],'--helper',p['helper'],'--mode',arm],arm,'source-check')
    assert digest(p['toolbar'])=='532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de', 'Stock toolbar changed'
    assert not (p['toolbar'].parent/'private/openracket-paint.rkt').exists(), 'Appearance overlay must be absent'
    print('OPENRACKET_SCAN_SOURCE_PATHS '+json.dumps({'arm':arm,**{k:str(v) for k,v in p.items()}}),flush=True)
    return p

def compare_completed_trials():
    arms={}
    for arm in ('stock','candidate'):
        reports=[json.loads(p.read_text()) for p in sorted((REPORTS/('performance-'+arm)).glob('pair-*/mixed-1mib-*/measurements.json'))]
        valid=[r for r in reports if r.get('status')=='complete' and r.get('initial_lexer_settle',{}).get('complete') is True and r.get('final_lexer_settle',{}).get('complete') is True and r.get('selected_language_settings',{}).get('status')=='complete' and r.get('scan_activation',{}).get('status')=='verified' and r.get('scan_activation',{}).get('expected')==arm]
        arms[arm]={'reports':reports,'valid':valid}
    all_valid=arms['stock']['valid']+arms['candidate']['valid']
    equal=bool(all_valid) and all(r['selected_language_settings']==all_valid[0]['selected_language_settings'] and r['preserved_settings']==all_valid[0]['preserved_settings'] for r in all_valid)
    complete=all(len(a['valid'])==3 for a in arms.values())
    result={'completed_trials':{a:len(d['valid']) for a,d in arms.items()},'expected_per_arm':3,'settings_equal_for_valid_trials':equal,'completed_workload_comparison_available':complete and equal,'warning':'Interleaved fresh-process lexer/editor workloads on one runner; total background-tool completion, cold filesystem caches and input-to-photon are not measured. Previous baseline is not substituted.'}
    if complete and equal:
        result['initial_open_to_lexer_observation_ms_median']={a:statistics.median(r['initial_open_to_lexer_observation_ms'] for r in d['valid']) for a,d in arms.items()}
        values=result['initial_open_to_lexer_observation_ms_median']
        result['candidate_over_stock_readiness_ratio']=values['candidate']/values['stock']
    (REPORTS/'paired-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('OPENRACKET_SCAN_PAIRED_COMPARISON '+json.dumps(result),flush=True)
    record('Complete paired workload and equal selected settings',complete and equal,json.dumps(result))

try:
    if PHASE=='prepare':
        manifest=json.loads((EXP/'CONTENTS-SHA256.json').read_text())
        for name,expected in manifest.items():
            p=EXP/name; assert p.is_file() and not p.is_symlink() and digest(p)==expected,name
        record('Frozen experiment source hashes',True,str(len(manifest))+' files')
        for test in ('generator-integrity-test.py','installed-source-test.py'):
            command(test,[sys.executable,EXP/'tests'/test])
        command('Native lexer comparator unit tests',[sys.executable,'-m','unittest','discover','-s',EXP/'tests','-p','test_comparator.py'])
        command('Headless scan source and lifecycle checks',[STOCK/'bin/raco','test',EXP/'tests/source-preservation-test.rkt',EXP/'tests/independent-fastpath-lifecycle-test.rkt',EXP/'tests/native-fixture-test.rkt'])
        command('Shared benchmark supervisor checks',[sys.executable,ROOT/'performance/test_harness.py'])
        command('Shared benchmark metadata, activation and lifecycle checks',[STOCK/'bin/raco','test',ROOT/'performance/settings-test.rkt',ROOT/'performance/activation-test.rkt',ROOT/'performance/lifecycle-test.rkt'])
        verify('stock')
        command('Deep-copy independent candidate runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','scan'],timeout=180)
        p=paths('candidate'); m=json.loads((EXP/'reports/fastpath-manifest.json').read_text())
        assert digest(p['unit'])==m['sources']['drracket/private/unit.rkt']['upstream_sha256']
        assert digest(p['framework'])==m['sources']['framework/private/text-misc.rkt']['upstream_sha256']
        assert not p['helper'].exists()
        helper=EXP/'overlay/drracket/private/openracket-all-string-snips.rkt'; unit=EXP/'overlay/drracket/private/unit.rkt'
        assert digest(helper)==m['helper_sha256'] and digest(unit)==m['sources']['drracket/private/unit.rkt']['patched_sha256']
        p['helper'].write_bytes(helper.read_bytes()); p['unit'].write_bytes(unit.read_bytes())
        verify('candidate'); verify('stock')
        command('Compile actual candidate and native test modules',[SCAN/'bin/raco','make',p['helper'],p['unit'],EXP/'tests/independent-native-fastpath-test.rkt',EXP/'tests/native-lexer-equivalence.rkt'],arm='candidate',timeout=180)
        command('Compile complete candidate DrRacket entrypoint',[SCAN/'bin/raco','make','-l','drracket/drracket'],arm='candidate',timeout=180)
    elif PHASE=='correctness':
        verify('stock');verify('candidate')
        command('Native editor preservation cases with asserted private activation',[SCAN/'bin/racket',EXP/'tests/independent-native-fastpath-test.rkt'],arm='candidate',purpose='native-editors',timeout=60,required=False)
        lexer_results=[]
        for arm in ('stock','candidate'):
            env=environment(arm,'native-lexer')
            env.update(OPENRACKET_LEXER_OUTPUT=str(REPORTS/(arm+'-lexer.json')),OPENRACKET_LEXER_MODE=arm)
            print('::group::'+arm+' actual retained-editor lexer outcomes',flush=True)
            proc=subprocess.Popen([str(runtime(arm)/'bin/racket'),str(EXP/'tests/native-lexer-equivalence.rkt')],env=env,start_new_session=True)
            try: result=proc.wait(timeout=60)
            except subprocess.TimeoutExpired: terminate_group(proc);result=124
            record(arm+' actual retained-editor lexer outcomes',result==0,'exit='+str(result));print('::endgroup::',flush=True)
            lexer_results.append(result==0)
        if all(lexer_results):
            command('Exact native lexer/token/style/parenthesis equivalence',[sys.executable,EXP/'tests/compare-native-lexer.py',REPORTS/'stock-lexer.json',REPORTS/'candidate-lexer.json'],required=False)
        else:
            record('Exact native lexer/token/style/parenthesis equivalence',False,'Not compared: at least one independent arm failed; timing remains blocked')
        verify('stock');verify('candidate')
    elif PHASE=='performance':
        for pair in (1,2,3):
            order=('candidate','stock') if pair==2 else ('stock','candidate')
            for arm in order:
                mode='pristine-stock' if arm=='stock' else 'scan-candidate'
                output=REPORTS/('performance-'+arm)/('pair-'+str(pair))
                command('Pair '+str(pair)+' '+arm+' matched 1 MiB workload',[sys.executable,ROOT/'performance/run.py','--mode',mode,'--racket',runtime(arm)/'bin/racket','--output',output,'--fixture','mixed-1mib','--repetitions','1','--timeout','60','--scan-activation',arm],arm=arm,purpose='performance-pair-'+str(pair),timeout=75,required=False)
        compare_completed_trials();verify('stock');verify('candidate')
except Exception as error:
    record(PHASE+' orchestration',False,str(error));raise
finally:
    print('Scan report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START_ROWS:]) else 0)
