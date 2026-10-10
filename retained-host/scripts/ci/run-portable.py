#!/usr/bin/env python3
"""Real Mac portable setup/launch and installed-host recovery acceptance."""
import base64,hashlib,json,os,pathlib,platform,shutil,struct,subprocess,sys,time

ROOT=pathlib.Path(__file__).resolve().parents[2]
os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert platform.system()=='Darwin','This bounded installation gate is Mac-first'
assert sys.argv[1:] in (['prepare'],['install'],['launch'],['save'],['verify'])
PHASE=sys.argv[1]
TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
RUNTIME=STOCK.with_name(STOCK.name+'-portable')
PROOF=TEMP/'OpenRacket Portable Proof'
PROFILE=PROOF/'profile';ADDON=PROFILE/'.local/share/racket';CACHE=PROFILE/'compiled-cache'
REPORTS=ROOT/'reports/portable-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else []
START_ROWS=len(ROWS)
sys.path.insert(0,str(ROOT/'performance'))
from run import terminate_group

def record(name,ok,detail=''):
    ROWS.append({'name':name,'passed':bool(ok),'detail':detail})
    STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
    print('OPENRACKET_PORTABLE_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
    lines=['# Actual Mac portable installation and launch','', 'Commit: '+os.environ['GITHUB_SHA'],'',
           '| Check | Outcome | Detail |','|---|---|---|']
    lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
    lines+=['','This gate invokes the real setup and launcher scripts. A read-only CI observer checks the launcher-created fixture frame, original controls, actual app-local appearance and loaded autosave flag. Separate callers exercise actual combined-host save/recovery behavior.',
            'Runtime immutability covers every original file including compiled bytecode. This is a source-overlay install, not a signed/notarized standalone application. Earlier Stop failures and unrun extension/dialog/platform coverage remain recorded release gaps.',
            'Synthetic native PNGs are bounded lossless job-log evidence. No artifact, cache, release or package upload.']
    (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def environment(purpose,installed=False):
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('OPENRACKET_') or key in ('PLTADDONDIR','PLTCOMPILEDROOTS','PLTUSERHOME','XDG_CONFIG_HOME','XDG_CACHE_HOME'):
            env.pop(key,None)
    env['RACKET']=str((RUNTIME if installed else STOCK)/'bin/racket')
    env['RACO']=str(pathlib.Path(env['RACKET']).with_name('raco'))
    home=TEMP/('portable-ci-'+purpose)
    home.mkdir(exist_ok=True)
    env.update(PLTUSERHOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),XDG_CACHE_HOME=str(home/'.cache'))
    if installed:
        env.update(PLTADDONDIR=str(ADDON),PLTCOMPILEDROOTS=str(CACHE)+':')
    else:
        env['PLTADDONDIR']=str(TEMP/'portable-ci-pristine-addon')
        env['PLTCOMPILEDROOTS']=str(TEMP/'portable-ci-checks-compiled')+':'
    return env

def command(name,args,env=None,timeout=120,required=True):
    print('\n::group::'+name,flush=True)
    proc=subprocess.Popen([str(a) for a in args],env=env or environment('checks'),start_new_session=True)
    try:result=proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:terminate_group(proc);result=124
    record(name,result==0,'exit='+str(result));print('::endgroup::',flush=True)
    if required and result:raise RuntimeError(name+' failed')
    return result==0

def tree_check(operation,root,required=True):
    label='pristine' if root==STOCK else 'selected-portable'
    return command(label+' complete runtime '+operation,[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py',operation,root,TEMP/('portable-'+label+'-tree.json')],timeout=180,required=required)

def check_resolution():
    env=environment('resolution',True)
    modules={'toolbar':('switchable-button.rkt','mrlib'),'autosave':('text-misc.rkt','framework','private'),
             'unit':('unit.rkt','drracket','private'),'appearance':('tool.rkt','openracket-appearance')}
    result={}
    for key,parts in modules.items():
        code='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
        p=pathlib.Path(subprocess.check_output([env['RACKET'],'-e',code],env=env,text=True,timeout=30)).resolve()
        parent=PROFILE if key in ('toolbar','autosave') else (PROOF/'tool' if key=='appearance' else RUNTIME)
        assert p.is_relative_to(parent),str(p)+' resolved outside '+str(parent)
        result[key]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    code="(write (list (find-system-path 'addon-dir) (find-system-path 'pref-file) (current-compiled-file-roots)))"
    observed=subprocess.check_output([env['RACKET'],'-e',code],env=env,text=True,timeout=30)
    print('OPENRACKET_PORTABLE_RESOLVED_PATHS '+json.dumps({'modules':result,'runtime_paths':observed}),flush=True)
    record('Installed profile/runtime collection confinement',True,json.dumps(result))

def capture(path):
    try:result=subprocess.run(['/usr/sbin/screencapture','-x',str(path)],timeout=15,capture_output=True,text=True)
    except (OSError,subprocess.TimeoutExpired) as error:return False,str(error)[:300]
    if result.returncode or not path.exists():return False,result.stderr[:300]
    data=path.read_bytes()
    if data[:8]!=b'\x89PNG\r\n\x1a\n' or not 1024<=len(data)<=300*1024:return False,'PNG outside lossless 1KiB–300KiB evidence bound'
    width,height=struct.unpack('>II',data[16:24])
    if width<640 or height<400:return False,'Unexpected native desktop dimensions'
    return True,f'{width}x{height}, {len(data)} bytes, SHA256 '+hashlib.sha256(data).hexdigest()

def emit_image(label,path):
    data=path.read_bytes();encoded=base64.b64encode(data).decode('ascii')
    print(f'OPENRACKET_SCREENSHOT_BEGIN {label} {len(data)} {hashlib.sha256(data).hexdigest()}',flush=True)
    for i in range(0,len(encoded),3072):print(f'OPENRACKET_SCREENSHOT_DATA {label} {i//3072:04d} {encoded[i:i+3072]}',flush=True)
    print(f'OPENRACKET_SCREENSHOT_END {label}',flush=True)

def launch(label,stock=False,optout=False):
    env=environment(label,True)
    ready=REPORTS/(label+'-ready.json');done=REPORTS/(label+'-capture-done');image=REPORTS/(label+'.png')
    assert not ready.exists() and not done.exists()
    fixture=PROOF/'portable-fixture-λ.rkt'
    if not fixture.exists():fixture.write_text('#lang racket\n;; Real portable launcher fixture: λ 中文\n(+ 20 22)\n',encoding='utf-8')
    env.update(OPENRACKET_PORTABLE_FIXTURE=str(fixture),OPENRACKET_NATIVE_READY_FILE=str(ready),
               OPENRACKET_NATIVE_CAPTURE_DONE=str(done),OPENRACKET_PORTABLE_EXPECT_UI='stock' if stock else 'modern',
               OPENRACKET_PORTABLE_EXPECT_SAVE_GUARD='0' if stock or optout else '1',OPENRACKET_THEME='dark')
    if optout:env['OPENRACKET_AUTOSAVE_GUARD']='0'
    if stock:
        # Deliberate inherited values must be cleared by the actual stock launcher.
        env.update(OPENRACKET_UI='modern',OPENRACKET_HOST_THEME='1',OPENRACKET_NATIVE_APPEARANCE='1',OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD='1')
    logfile=REPORTS/(label+'.log');report={};captured=False;capture_detail='No ready metadata'
    print('\n::group::'+label+' real launcher',flush=True)
    with logfile.open('w') as log:
        proc=subprocess.Popen(['bash',str(PROOF/'scripts'/('launch-stock.sh' if stock else 'launch-openracket.sh')),str(fixture)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+100
        while proc.poll() is None and time.monotonic()<deadline:
            if ready.exists():
                try:report=json.loads(ready.read_text())
                except (ValueError,OSError):time.sleep(.05);continue
                captured,capture_detail=capture(image)
                done.write_text('Native capture attempted\n')
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:terminate_group(proc)
                break
            time.sleep(.1)
        timed_out=proc.poll() is None
        if timed_out:
            captured,capture_detail=capture(image)
            terminate_group(proc)
        result=proc.returncode
    print(logfile.read_text(errors='replace'),flush=True)
    passed=not timed_out and result==0 and report.get('status')=='passed' and report.get('genuine_host') is True
    record(label+' real launcher/native state',passed,'exit='+str(result)+' ready_status='+str(report.get('status')))
    record(label+' native OS screenshot',captured,capture_detail)
    if captured:emit_image(label if passed else label+'-failure-diagnostic',image)
    print('::endgroup::',flush=True)
    return passed

try:
    if PHASE=='prepare':
        command('Portable adapter isolation unit tests',[sys.executable,ROOT/'scripts/ci/test-portable-adapter.py'])
        command('Runtime immutability witness unit tests',[sys.executable,ROOT/'scripts/ci/test-runtime-tree-check.py'])
        manifest=json.loads((ROOT/'CONTENTS-SHA256.json').read_text())
        assert not PROOF.exists()
        for name,digest in manifest.items():
            assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts,name
            source=ROOT/name;assert source.is_file() and not source.is_symlink() and hashlib.sha256(source.read_bytes()).hexdigest()==digest,name
            dest=PROOF/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        record('Copy verified portable source into fresh spaced path',True,str(len(manifest))+' source files; '+str(PROOF))
        clone_env=os.environ.copy()
        command('Deep-copy independent official portable runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','portable'],clone_env,timeout=180)
        tree_check('baseline',STOCK);tree_check('baseline',RUNTIME)
        for name in ('portable-profile-test.py','portable-source-test.py','autosave-source-test.py'):
            command(name,[sys.executable,PROOF/'tests'/name])
        command('Portable installer observer and combined save contract tests',[STOCK/'bin/raco','test',PROOF/'tests/portable-autosave-installer-test.rkt',PROOF/'tests/independent-autosave-model-test.rkt',PROOF/'tests/portable-observer-contract-test.rkt',PROOF/'tests/portable-save-caller-contract-test.rkt'])
    elif PHASE=='install':
        env=environment('setup',True)
        command('Actual setup-openracket --install',[ 'bash',PROOF/'scripts/setup-openracket.sh','--install'],env,timeout=720)
        command('Actual launch-openracket --check',['bash',PROOF/'scripts/launch-openracket.sh','--check'],env,timeout=90)
        check_resolution()
        raco=[RUNTIME/'bin/racket','-A',ADDON,'-R',str(CACHE)+':','-l','raco','--']
        command('Register CI-only read-only launcher observer',raco+['pkg','install','--scope','user','--batch','--no-setup','--deps','fail','--link','--name','openracket-portable-observer',PROOF/'tests/portable-observer'],env,timeout=90)
        command('Compile observer tool registration',raco+['setup','--avoid-main','--no-docs','--no-launcher','--no-foreign-libs','--no-install','--no-post-install','--pkgs','openracket-portable-observer'],env,timeout=240)
        command('Compile combined actual native save callers',raco+['make',PROOF/'tests/portable-native-save-host.rkt',PROOF/'tests/independent-native-save-recovery.rkt',PROOF/'tests/review-native-save-failure.rkt'],env,timeout=180)
        tree_check('compare',STOCK);tree_check('compare',RUNTIME)
    elif PHASE=='launch':
        launch('portable-modern-default')
        launch('portable-modern-optout',optout=True)
        launch('portable-stock-launcher',stock=True)
        check_resolution()
    elif PHASE=='save':
        for mode in ('candidate-on','candidate-off'):
            env=environment('combined-save-'+mode,True)
            env.update(OPENRACKET_UI='modern',OPENRACKET_HOST_THEME='1',OPENRACKET_THEME='dark',OPENRACKET_NATIVE_APPEARANCE='1')
            if mode=='candidate-on':env['OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD']='1'
            command('Combined installed host '+mode+' save and recovery',[RUNTIME/'bin/racket',PROOF/'tests/portable-native-save-host.rkt',mode],env,timeout=200,required=False)
    elif PHASE=='verify':
        tree_check('compare',STOCK,False)
        tree_check('compare',RUNTIME,False)
except Exception as error:
    record(PHASE+' orchestration',False,str(error));raise
finally:print('Portable report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START_ROWS:]) else 0)
