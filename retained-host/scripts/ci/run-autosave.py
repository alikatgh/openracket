#!/usr/bin/env python3
"""Native correctness then actual stock/candidate autosave measurement."""
import hashlib,json,os,pathlib,statistics,subprocess,sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
EXP=ROOT/'experiments/autosave-guard'
os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'],['correctness'],['performance'])
PHASE=sys.argv[1]
TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
CANDIDATE=STOCK.with_name(STOCK.name+'-autosave')
assert STOCK.is_relative_to(TEMP) and CANDIDATE.is_relative_to(TEMP)
REPORTS=ROOT/'reports/autosave-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json'
ROWS=json.loads(STATE.read_text()) if STATE.exists() else []
START_ROWS=len(ROWS)
sys.path.insert(0,str(ROOT/'performance'))
from run import terminate_group

def record(name,ok,detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail})
    STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_AUTOSAVE_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Isolated actual autosave experiment','',
           'Commit: '+os.environ['GITHUB_SHA'],
           'Pinned full Racket9.3; pristine stock and an independent autosave-only deep copy. Scan, budget and appearance overlays absent.','',
           '| Check | Outcome | Detail |','|---|---|---|']
    lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
    lines+=['','Timing covers a real synchronous do-autosave, its GUI delay and verified fresh-editor recovery artifact. It does not establish crash/restart recovery-dialog parity, enabled format-confirmation dialog parity, initial-coloring improvement or arbitrary third-party callback equivalence.',
            'Original Stop failures and prior scan/budget results remain independent evidence, not removed release gates. No artifact, cache, release or package upload.']
    (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def runtime(mode):
    assert mode in ('stock','candidate-off','candidate-on')
    return STOCK if mode=='stock' else CANDIDATE

def environment(mode,purpose):
    env=os.environ.copy();selected=runtime(mode)
    env['RACKET']=str(selected/'bin/racket');env['RACO']=str(selected/'bin/raco')
    for key in list(env):
        if key.startswith('OPENRACKET_') and key not in ('OPENRACKET_CI_STOCK_RACKET','OPENRACKET_CI_INSTALL','OPENRACKET_CI_STOCK_ADDON'):
            env.pop(key,None)
    if mode=='candidate-on':env['OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD']='1'
    env['PLTADDONDIR']=str(TEMP/('autosave-'+mode+'-addon'))
    env['PLTUSERHOME']=str(TEMP/('autosave-'+mode+'-'+purpose))
    env['XDG_CONFIG_HOME']=env['PLTUSERHOME']+'/.config'
    env['XDG_CACHE_HOME']=env['PLTUSERHOME']+'/.cache'
    pathlib.Path(env['PLTUSERHOME']).mkdir(exist_ok=True)
    print('OPENRACKET_AUTOSAVE_CI_PROFILE '+json.dumps({'mode':mode,'purpose':purpose,'addon':env['PLTADDONDIR'],'home':env['PLTUSERHOME'],'save_guard':env.get('OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD'),'other_experiments':'unset'}),flush=True)
    return env

def command(name,args,mode='stock',purpose='checks',timeout=90,required=True):
    print('\n::group::'+name,flush=True)
    proc=subprocess.Popen([str(a) for a in args],env=environment(mode,purpose),start_new_session=True)
    try:result=proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:terminate_group(proc);result=124
    record(name,result==0,'exit='+str(result));print('::endgroup::',flush=True)
    if required and result:raise RuntimeError(name+' failed')
    return result==0

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def frozen_sources():
    manifest=json.loads((EXP/'CONTENTS-SHA256.json').read_text())
    for name,expected in manifest.items():
        p=EXP/name
        assert p.is_file() and not p.is_symlink() and digest(p)==expected,name
    record('Frozen autosave experiment source hashes',True,str(len(manifest))+' files')

def paths(mode):
    selected=runtime(mode);env=environment(mode,'source-resolution');found={}
    modules={'text':('text-misc.rkt','framework','private'),'editor':('editor-misc.rkt','framework','private'),
             'native-editor':('editor.rkt','mred','private'),'color':('color.rkt','framework','private'),
             'unit':('unit.rkt','drracket','private'),'toolbar':('switchable-button.rkt','mrlib')}
    for key,parts in modules.items():
        code='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
        p=pathlib.Path(subprocess.check_output([str(selected/'bin/racket'),'-e',code],env=env,text=True,timeout=30))
        assert not p.is_symlink() and p.resolve().is_relative_to(selected),str(p)
        found[key]=p.resolve()
    return found

def verify(mode):
    p=paths(mode);m=json.loads((EXP/'reports/autosave-manifest.json').read_text())
    expected={'text':m['upstream_sha256'] if mode=='stock' else m['patched_sha256'],
              'editor':'3becc626874477283cdd1b9f45631f11baed586aa37a3c95d67a4a0a2b677885',
              'native-editor':'1eef92a431da2c2cf40d193237d4ab9879adae9518c71b39ba5af0dc6b32f75a',
              'color':'da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578',
              'unit':'535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5',
              'toolbar':'532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de'}
    for key,value in expected.items():assert digest(p[key])==value,key+' changed'
    assert not p['unit'].with_name('openracket-all-string-snips.rkt').exists(),'Scan helper must be absent'
    assert not (p['toolbar'].parent/'private/openracket-paint.rkt').exists(),'Appearance overlay must be absent'
    print('OPENRACKET_AUTOSAVE_CI_SOURCE_PATHS '+json.dumps({'mode':mode,**{k:str(v) for k,v in p.items()},'sha256':expected}),flush=True)
    record(mode+' exact installed source verification',True,'Only candidate text-misc.rkt differs; original autosave/native save/color/unit/toolbar preserved')
    return p

def compare_completed_trials():
    arms={}
    recovery_fields=('recovery_toc_entry_verified','new_artifact_path_verified','exact_recovered_source','original_file_unchanged','filename_restored','format_restored','still_modified')
    for arm in ('stock','candidate'):
        reports=[json.loads(p.read_text()) for p in sorted((REPORTS/('performance-'+arm)).glob('pair-*/mixed-1mib-*/measurements.json'))]
        valid=[r for r in reports if r.get('status')=='complete' and r.get('exit_code')==0 and r.get('timeout') is False
               and r.get('measurement_kind')=='settled_editor_autosave'
               and r.get('initial_lexer_settle',{}).get('complete') is True
               and r.get('final_lexer_settle',{}).get('complete') is True
               and all(r.get('autosave_recovery',{}).get(k) is True for k in recovery_fields)
               and r.get('autosave_recovery',{}).get('artifact_bytes',0)>0
               and r.get('autosave_recovery',{}).get('recovered_characters')==r.get('fixture_metadata',{}).get('characters',-2)+1
               and r.get('loaded_characters')==r.get('fixture_metadata',{}).get('characters',-2)
               and all(r.get('autosave_preconditions',{}).get(k) is True for k in ('lexer_valid','modified','autosave_enabled'))
               and all(r.get('ui_environment',{}).get(k)=='unset' for k in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_ALL_STRING_FAST_PATH','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS'))
               and r.get('selected_language_settings',{}).get('status')=='complete'
               and all(k in r.get('preserved_settings',{}) for k in ('framework:autosaving-on?','framework:autosave-delay','framework:backup-files?','framework:verify-change-format'))
               and 'UNAVAILABLE' not in r['preserved_settings'].values()
               and r.get('scan_activation',{}).get('status')=='verified' and r.get('scan_activation',{}).get('expected')=='stock'
               and r.get('autosave_activation',{}).get('status')=='verified' and r.get('autosave_activation',{}).get('expected')==arm
               and all(isinstance(r.get(snapshot,{}).get(k),(int,float)) for snapshot in ('memory_before_autosave','memory_after_autosave_command','memory_after_autosave') for k in ('racket_managed_bytes','racket_cumulative_allocated_bytes','racket_peak_allocated_bytes','process_cpu_ms','gc_ms'))
               and isinstance(r.get('native_max_rss_bytes'),(int,float)) and r['native_max_rss_bytes']>0
               and all(isinstance(r.get('actual_autosave',{}).get(k),(int,float)) for k in ('command_ms','command_plus_low_priority_fence_ms'))
               and isinstance(r.get('autosave_queued_gui_probe_ms'),(int,float))]
        arms[arm]={'reports':reports,'valid':valid}
    all_valid=arms['stock']['valid']+arms['candidate']['valid']
    def fingerprint(r):
        fixture=dict(r['fixture_metadata']);fixture.pop('path',None)
        return {**{k:r[k] for k in ('selected_language_settings','preserved_settings','racket_version','os','vm')},'fixture_metadata':fixture}
    equal=bool(all_valid) and all(fingerprint(r)==fingerprint(all_valid[0]) for r in all_valid)
    complete=all(len(a['valid'])==3 for a in arms.values())
    result={'completed_trials':{a:len(d['valid']) for a,d in arms.items()},'expected_per_arm':3,
            'settings_runtime_fixture_equal_for_valid_trials':equal,'completed_workload_comparison_available':complete and equal,
            'warning':'One actual autosave per fresh process after lexer readiness. Recovery artifacts reloaded in a fresh editor. Background expansion completion, crash-restart dialogs, cold caches and physical input-to-photon are not measured.'}
    if complete and equal:
        result['actual_autosave_command_ms_median']={a:statistics.median(r['actual_autosave']['command_ms'] for r in d['valid']) for a,d in arms.items()}
        values=result['actual_autosave_command_ms_median'];result['candidate_over_stock_autosave_ratio']=values['candidate']/values['stock'] if values['stock'] else None
    (REPORTS/'paired-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('OPENRACKET_AUTOSAVE_PAIRED_COMPARISON '+json.dumps(result),flush=True)
    record('Complete actual autosave/recovery workload and equal selected settings',complete and equal,json.dumps(result))

try:
    if PHASE=='prepare':
        frozen_sources()
        command('Synthetic autosave comparison acceptance checks',[sys.executable,ROOT/'scripts/ci/test-autosave-comparison.py'])
        command('Autosave source-preservation tests',[sys.executable,'-m','unittest','discover','-s',EXP/'tests','-p','test_*.py'])
        command('Autosave parsed-source model checks',[STOCK/'bin/raco','test',EXP/'tests/independent-model-test.rkt',EXP/'tests/independent-native-caller-contract-test.rkt',EXP/'tests/activation-test.rkt'])
        command('Autosave process supervisor checks',[sys.executable,EXP/'performance/test_harness.py'])
        frozen_sources();verify('stock')
        command('Deep-copy independent autosave runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','autosave'],timeout=180)
        p=paths('candidate-off');m=json.loads((EXP/'reports/autosave-manifest.json').read_text())
        assert digest(p['text'])==m['upstream_sha256']
        source=EXP/'overlay/framework/private/text-misc.rkt';assert digest(source)==m['patched_sha256']
        p['text'].write_bytes(source.read_bytes());verify('candidate-off');verify('stock')
        for mode in ('stock','candidate-off'):
            command(mode+' compile native save and failure callers',[runtime(mode)/'bin/raco','make',EXP/'tests/independent-native-autosave-host.rkt',EXP/'tests/independent-native-save-recovery.rkt',EXP/'tests/review-native-save-failure.rkt',EXP/'performance/retained-host.rkt'],mode=mode,purpose='compile-native',timeout=180)
        command('Compile actual autosave module',[CANDIDATE/'bin/raco','make',p['text']],mode='candidate-off',timeout=180)
        command('Compile complete autosave DrRacket entrypoint',[CANDIDATE/'bin/raco','make','-l','drracket/drracket'],mode='candidate-off',timeout=180)
    elif PHASE=='correctness':
        verify('stock');verify('candidate-off')
        for mode in ('stock','candidate-off','candidate-on'):
            command(mode+' native save Unicode WXME hooks and recovery artifact',[runtime(mode)/'bin/racket',EXP/'tests/independent-native-autosave-host.rkt',mode],mode,'native-save',timeout=200,required=False)
        verify('stock');verify('candidate-on')
    elif PHASE=='performance':
        for pair in (1,2,3):
            order=('candidate','stock') if pair==2 else ('stock','candidate')
            for arm in order:
                mode='stock' if arm=='stock' else 'candidate-on'
                output=REPORTS/('performance-'+arm)/('pair-'+str(pair))
                command('Autosave pair '+str(pair)+' '+arm+' matched 1 MiB workload',[sys.executable,EXP/'performance/run.py','--mode','autosave-'+arm,'--racket',runtime(mode)/'bin/racket','--output',output,'--fixture','mixed-1mib','--repetitions','1','--timeout','60','--scan-activation','stock','--autosave-activation',arm],mode,'performance-pair-'+str(pair),timeout=75,required=False)
        compare_completed_trials();verify('stock');verify('candidate-on')
except Exception as error:
    record(PHASE+' orchestration',False,str(error));raise
finally:print('Autosave report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START_ROWS:]) else 0)
