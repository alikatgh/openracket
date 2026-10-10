#!/usr/bin/env python3
"""Independent Mac stock online-expansion attribution; never a speed comparison."""
import hashlib,json,os,pathlib,platform,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert platform.system()=='Darwin'
assert sys.argv[1:] in (['prepare'],['capture'],['replay'])
PHASE=sys.argv[1];TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
CLONE=STOCK.with_name(STOCK.name+'-replay');RACKET=CLONE/'bin/racket'
EXP=ROOT/'experiments/expansion-replay';REPORTS=ROOT/'reports/replay-ci';REPORTS.mkdir(parents=True,exist_ok=True)
CAPTURE=REPORTS/'capture';RESULTS=REPORTS/'replay';STATE=REPORTS/'results.json'
ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def env():
    e=os.environ.copy()
    for k in list(e):
        if k.startswith('OPENRACKET_') or k in ('PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','PLTCOLLECTS','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):e.pop(k,None)
    e.update(RACKET=str(RACKET),RACO=str(CLONE/'bin/raco'),PLTUSERHOME=str(TEMP/'replay-prepare-profile'),PLTADDONDIR=str(TEMP/'replay-addon'))
    return e

def record(name,ok,detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_REPLAY_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Separate Mac online-expansion attribution','', 'This is an initialization-instrumented stock9.3 clone with actual captured request/registry, all stock handlers and the unchanged128MiB child limit. Diagnostic overhead is present; timings do not establish a product speedup.','', '| Check | Outcome | Detail |','|---|---|---|']
    lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
    lines+=['','A genuine terminal abnormal/error outcome is distinct from protocol timeout, worker death and cleanup failure. Source payloads stay local; bounded JSON metrics/GC evidence is emitted in ordinary logs. No artifact/cache/release upload.']
    (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def command(name,args,environment=None,timeout=120,cwd=None):
    print('\n::group::'+name,flush=True)
    p=subprocess.Popen([str(x) for x in args],env=environment or env(),cwd=cwd or ROOT,start_new_session=True)
    try:code=p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:terminate_group(p);code=124
    record(name,code==0,'exit='+str(code));print('::endgroup::',flush=True)
    if code:raise RuntimeError(name+' failed')

def tail(path):
    if path.is_file():
        raw=path.read_bytes();text=raw[-32768:].decode('utf-8','replace')
        print('OPENRACKET_REPLAY_LOG_TAIL '+json.dumps({'file':path.name,'bytes':len(raw),'truncated':len(raw)>32768,'text':text}),flush=True)

def evidence():
    for directory,names in ((CAPTURE,('capture-summary.json','capture-host.json','capture-supervisor.json')),(RESULTS,('replay.json','supervisor.json'))):
        for name in names:
            path=directory/name
            if path.is_file():command('Bounded '+directory.name+'/'+name+' log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',path],timeout=30)
        tail(directory/'stdout.log');tail(directory/'stderr.log')

try:
    if PHASE=='prepare':
        manifest=EXP/'SHA256SUMS'
        for line in manifest.read_text().splitlines():
            expected,name=line.split('  ',1);p=EXP/name
            assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
            assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
        record('Frozen diagnostic source hashes',True,hashlib.sha256(manifest.read_bytes()).hexdigest())
        command('Readable evidence transport unit tests',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
        command('Dedicated independent stock diagnostic clone',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','replay'],os.environ.copy(),timeout=180)
        expression='(display (collection-file-path "module-language.rkt" "drracket" "private"))'
        pristine=pathlib.Path(subprocess.check_output([str(STOCK/'bin/racket'),'-e',expression],env=env(),text=True,timeout=30)).resolve()
        assert pristine.is_relative_to(STOCK)
        (TEMP/'replay-headless-profile').mkdir(exist_ok=True)
        testenv=env();testenv.update(REPLAY_TEST_RACKET=str(RACKET),REPLAY_TEST_PROFILE=str(TEMP/'replay-headless-profile'),REPLAY_TEST_SOURCE_DIR=str(pristine.parent))
        testenv['PLTUSERHOME']=testenv['REPLAY_TEST_PROFILE']
        command('Source boundaries and real-place mock protocol checks',[sys.executable,'-m','unittest','-v','test_implementation','test_supervise'],testenv,timeout=180,cwd=EXP)
        command('Read-only support and preference restore assertions',[RACKET,EXP/'test_support.rkt'],testenv,timeout=90)
        command('Compile supplied support capture and replay drivers',[RACKET,'-l','raco','make',EXP/'support.rkt',EXP/'capture-host.rkt',EXP/'replay.rkt'],timeout=120)
        try:command('Pinned diagnostic insertions and actual clone compilation',[sys.executable,EXP/'prepare.py','--diagnostic-root',CLONE,'--racket',RACKET],timeout=260)
        finally:tail(CLONE/'openracket-replay-compile.log')
        command('Generate unchanged deterministic fixture',[sys.executable,ROOT/'performance/fixtures.py',REPORTS/'fixtures'],timeout=30)
    elif PHASE=='capture':
        command('Actual native edited-snapshot request and registry capture',[sys.executable,EXP/'capture.py','--racket',RACKET,'--fixture',REPORTS/'fixtures/mixed-1mib.rkt','--output',CAPTURE],timeout=205)
    elif PHASE=='replay':
        command('Two same-process actual worker expansion replays',[sys.executable,EXP/'supervise.py','--racket',RACKET,'--capture',CAPTURE/'capture.rktd','--output',RESULTS,'--trials','2'],timeout=170)
except Exception as error:
    record(PHASE+' diagnostic orchestration',False,str(error));raise
finally:
    evidence()
    print('Replay diagnostic report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
