#!/usr/bin/env python3
"""Independent Mac stock online-expansion phase attribution; never a speed comparison."""
import hashlib,json,os,pathlib,platform,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert platform.system()=='Darwin'
assert sys.argv[1:] in (['prepare'],['capture'],['replay'],['accept'],['verify'])
PHASE=sys.argv[1];TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
CLONE=STOCK.with_name(STOCK.name+'-phase256');RACKET=CLONE/'bin/racket'
EXP=ROOT/'experiments/expansion-phase-256';REPORTS=ROOT/'reports/completed-phase-ci';REPORTS.mkdir(parents=True,exist_ok=True)
CAPTURE=REPORTS/'capture';RESULTS=REPORTS/'replay';STATE=REPORTS/'results.json'
ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def env():
    e=os.environ.copy()
    for k in list(e):
        if k.startswith('OPENRACKET_') or k in ('PLTCONFIGDIR','PLT_COMPILED_FILE_CHECK','PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','PLTCOLLECTS','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):e.pop(k,None)
    e.update(RACKET=str(RACKET),RACO=str(CLONE/'bin/raco'),PLTUSERHOME=str(TEMP/'phase256-prepare-profile'),PLTADDONDIR=str(TEMP/'phase256-addon'))
    return e

def record(name,ok,detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_REPLAY_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Separate Mac online-expansion attribution','', 'This is an initialization/phase-instrumented stock Racket 9.3 clone with actual captured request/registry, all stock handlers and the explicitly selected 256 MiB child limit. Diagnostic overhead is present; timings do not establish a product speedup.','', '| Check | Outcome | Detail |','|---|---|---|']
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
    for directory,names in ((CAPTURE,('capture-summary.json','capture-host.json','capture-supervisor.json','memory-profile.json')),(RESULTS,('replay.json','supervisor.json','acceptance.json'))):
        for name in names:
            path=directory/name
            if path.is_file():command('Bounded '+directory.name+'/'+name+' log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',path],timeout=30)
        tail(directory/'stdout.log');tail(directory/'stderr.log')

try:
    if PHASE=='prepare':
        manifest=EXP/'SHA256SUMS'
        assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='44b6c593c61eb752b7da04eece27245f127d9c448dff576b52751f354e0c7e56'
        for line in manifest.read_text().splitlines():
            expected,name=line.split('  ',1);p=EXP/name
            assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
            assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
        record('Frozen diagnostic source hashes',True,hashlib.sha256(manifest.read_bytes()).hexdigest())
        command('Completed phase adapter isolation tests',[sys.executable,ROOT/'scripts/ci/test-completed-phases-adapter.py'])
        command('Readable evidence transport unit tests',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
        command('Pristine complete runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',STOCK,TEMP/'phase256-pristine-tree.json'],timeout=180)
        command('Dedicated independent stock diagnostic clone',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','phase256'],os.environ.copy(),timeout=180)
        expression='(display (collection-file-path "module-language.rkt" "drracket" "private"))'
        pristine=pathlib.Path(subprocess.check_output([str(STOCK/'bin/racket'),'-e',expression],env=env(),text=True,timeout=30)).resolve()
        assert pristine.is_relative_to(STOCK)
        command('All native preflight gates; no skipped Racket tests accepted',
                [sys.executable,EXP/'native_preflight.py','--racket',RACKET,'--pristine-source',pristine.parent,
                 '--profile',TEMP/'phase256-headless-profile'],timeout=300,cwd=EXP)
        try:command('Pinned diagnostic insertions and actual clone compilation',[sys.executable,EXP/'prepare_phase.py','--diagnostic-root',CLONE,'--racket',RACKET],timeout=260)
        finally:tail(CLONE/'openracket-replay-compile.log')
        command('Generate unchanged deterministic fixture',[sys.executable,ROOT/'performance/fixtures.py',REPORTS/'fixtures'],timeout=30)
    elif PHASE=='capture':
        command('Actual native edited-snapshot request and registry capture',[sys.executable,EXP/'capture.py','--racket',RACKET,'--fixture',REPORTS/'fixtures/mixed-1mib.rkt','--output',CAPTURE],timeout=235)
    elif PHASE=='replay':
        command('Two same-process actual worker expansion replays',[sys.executable,EXP/'supervise.py','--racket',RACKET,'--capture',CAPTURE/'capture.rktd','--output',RESULTS,'--trials','2','--phase-probe'],timeout=170)
    elif PHASE=='accept':
        command('Completed handler results, clean monitor trace, three-role phase context and cleanup acceptance',
                [sys.executable,EXP/'accept_completed.py','--capture',CAPTURE,'--results',RESULTS],timeout=30)
    elif PHASE=='verify':
        command('Pristine complete runtime unchanged after diagnostic',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',STOCK,TEMP/'phase256-pristine-tree.json'],timeout=180)
except Exception as error:
    record(PHASE+' diagnostic orchestration',False,str(error));raise
finally:
    evidence()
    print('Replay diagnostic report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
