#!/usr/bin/env python3
"""Exact xref-only correctness before separately frozen telemetry."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,struct,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
EXP=ROOT/'experiments/xref-reply';TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
ORIGINAL=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
STOCK=ORIGINAL.with_name(ORIGINAL.name+'-xref-control');CANDIDATE=ORIGINAL.with_name(ORIGINAL.name+'-xref-candidate')
assert os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'],['correctness'],['telemetry'],['verify'])
TELEMETRY=EXP
PHASE=sys.argv[1];REPORTS=ROOT/'reports/xref-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
spec=importlib.util.spec_from_file_location('xref_contract',ROOT/'scripts/ci/xref-ci-contract.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_XREF_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Isolated Mac xref reply experiment','', 'Only candidate xref.rkt changes; original 128 MiB / 20 ms defaults and stock tools remain. The delivered appearance/autosave preview is separate.','', '| Check | Outcome | Detail |','|---|---|---|']
 lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def env(mode,purpose):return contract.environment(os.environ,mode,purpose,temp=TEMP,stock=STOCK,candidate=CANDIDATE)
def runtime(mode):return contract.selected_runtime(mode,STOCK,CANDIDATE)
def command(name,args,mode='stock',purpose='checks',timeout=90,environment=None,cwd=None,required=True,logfile=None):
 print('\n::group::'+name,flush=True)
 stream=pathlib.Path(logfile).open('w') if logfile else None
 try:
  p=subprocess.Popen([str(x) for x in args],env=environment or env(mode,purpose),cwd=cwd or ROOT,start_new_session=True,stdout=stream,stderr=subprocess.STDOUT if stream else None)
  try:code=p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:terminate_group(p);code=124
 finally:
  if stream:stream.close()
 record(name,code==0,'exit='+str(code));print('::endgroup::',flush=True)
 if code and required:raise RuntimeError(name+' failed')
 return code==0

def collection(mode,parts):
 expression='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
 p=pathlib.Path(subprocess.check_output([str(runtime(mode)/'bin/racket'),'-e',expression],env=env(mode,'resolution'),text=True,timeout=30)).resolve()
 assert p.is_file() and not p.is_symlink() and p.is_relative_to(runtime(mode)),str(p)
 return p

def verify_sources(mode,patched):
 manifest=json.loads((EXP/'manifest.json').read_text());result={}
 for key,(parts,pin) in contract.UNCHANGED.items():
  p=collection(mode,parts);assert hashlib.sha256(p.read_bytes()).hexdigest()==pin,key+' changed';result[key]=str(p)
 target=collection(mode,('xref.rkt','drracket','private','syncheck'));expected=manifest['patched_sha256' if patched else 'original_sha256']
 assert hashlib.sha256(target.read_bytes()).hexdigest()==expected,'xref source pin'
 unit=pathlib.Path(result['unit']);toolbar=pathlib.Path(result['toolbar'])
 assert not unit.with_name('openracket-all-string-snips.rkt').exists()
 assert not (toolbar.parent/'private/openracket-paint.rkt').exists()
 result.update(xref=str(target),xref_sha256=expected,mode=mode)
 print('OPENRACKET_XREF_CI_SOURCE_PATHS '+json.dumps(result),flush=True)
 record(mode+' exact source/collection verification',True,'Only the candidate xref source may differ')
 return target

def host_check(mode):
 label='xref-'+mode+'-check-syntax';ready=REPORTS/(label+'-ready.json');done=REPORTS/(label+'-capture-done')
 log=REPORTS/(label+'.log');png=REPORTS/(label+'.png');e=env(mode,'native-host')
 e.update(OPENRACKET_UI='stock',OPENRACKET_NATIVE_CASE='check-syntax',OPENRACKET_XREF_EXPECT_MODE=mode,
          OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done))
 assert not ready.exists() and not done.exists()
 print('\n::group::'+label,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen([str(runtime(mode)/'bin/racket'),str(ROOT/'scripts/ci/xref-native-host.rkt')],env=e,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  deadline=time.monotonic()+100
  while p.poll() is None and time.monotonic()<deadline:
   if ready.exists():
    # Full synthetic desktop avoids macOS frame/menu coordinate mismatch.
    try:subprocess.run(['/usr/sbin/screencapture','-x',str(png)],timeout=15,check=False)
    except (OSError,subprocess.TimeoutExpired):pass
    done.write_text('Native capture attempted\n');break
   time.sleep(.2)
  try:code=p.wait(timeout=max(1,deadline-time.monotonic()))
  except subprocess.TimeoutExpired:
   if not png.exists():
    try:subprocess.run(['/usr/sbin/screencapture','-x',str(png)],timeout=15,check=False)
    except (OSError,subprocess.TimeoutExpired):pass
   terminate_group(p);code=124
 print(log.read_text(),flush=True)
 data=json.loads(ready.read_text()) if ready.exists() else {}
 passed=code==0 and data.get('status')=='passed' and data.get('follow_on_case')=='check-syntax'
 record(label+' real host and Check Syntax',passed,json.dumps({'exit':code,'report':data}))
 if png.exists():
  b=png.read_bytes()
  if b[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(b)<=300*1024:
   image_label=label if passed else label+'-failure-diagnostic'
   print(f'OPENRACKET_SCREENSHOT_BEGIN {image_label} {len(b)} {hashlib.sha256(b).hexdigest()}',flush=True)
   encoded=base64.b64encode(b).decode()
   for i in range(0,len(encoded),3072):print(f'OPENRACKET_SCREENSHOT_DATA {image_label} {i//3072:04d} {encoded[i:i+3072]}',flush=True)
   print(f'OPENRACKET_SCREENSHOT_END {image_label}',flush=True)
 print('::endgroup::',flush=True)
 return passed

try:
 if PHASE=='prepare':
  manifest=json.loads((EXP/'CONTENTS-SHA256.json').read_text())
  for name,h in manifest.items():
   p=EXP/name;assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
   assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==h,name
  record('Reviewed frozen xref source hashes',True,str(len(manifest)))
  command('CI isolation contract checks',[sys.executable,ROOT/'scripts/ci/test-xref-ci-contract.py'])
  command('Lossless xref and diagnostic transport checks',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
  command('Strict paired metadata and outcome classifier checks',[sys.executable,ROOT/'scripts/ci/test-xref-pairs.py'])
  command('Full pristine runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',ORIGINAL,TEMP/'xref-pristine-tree.json'],timeout=180)
  for purpose in ('xref-control','xref-candidate'):
   command('Independent '+purpose+' runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py',purpose],environment=os.environ.copy(),timeout=180)
  verify_sources('stock',False);target=verify_sources('candidate-off',False)
  command('Pinned xref-only application',[sys.executable,EXP/'scripts/apply.py','--runtime-root',CANDIDATE,'--target',target,'--confirm-disposable-copy'],mode='candidate-off')
  verify_sources('candidate-off',True)
  command('Pinned source and installer refusal tests',[sys.executable,'-m','unittest','discover','-s',EXP/'tests','-p','test_*.py'])
  for mode in ('stock','candidate-off','candidate-on'):
   command(mode+' compile actual xref module',[runtime(mode)/'bin/racket','-l','raco','make',collection(mode,('xref.rkt','drracket','private','syncheck')),EXP/'tests/independent-reply-test.rkt',EXP/'tests/native-trace.rkt',ROOT/'scripts/ci/xref-native-host.rkt',ROOT/'tests/independent-native-host.rkt',ROOT/'tests/independent-native-workflows.rkt'],mode=mode,purpose='compile',timeout=120)
 elif PHASE=='correctness':
  # Independent helper checks collect before product gates; timing still requires every gate.
  perf=TELEMETRY/'performance';observer=TELEMETRY/'observer'
  private=collection('stock',('module-language.rkt','drracket','private')).parent
  e=env('stock','observer-source-tests');e['OPENRACKET_TEST_STOCK_PRIVATE']=str(private)
  command('Exact observer source boundaries',[sys.executable,observer/'test_source.py'],environment=e,timeout=90,cwd=observer,required=False)
  command('Telemetry supervisor and observation rejection tests',[sys.executable,'-m','unittest','-v','test_harness','test_observation'],purpose='telemetry-python-tests',timeout=90,cwd=perf,required=False)
  command('Native observer protocol and kill-safety tests',[STOCK/'bin/racket',observer/'test_support.rkt'],purpose='observer-helper-tests',timeout=180,cwd=observer,required=False)
  for mode in ('stock','candidate-on'):
   command(mode+' uninstrumented telemetry caller/helper compile',[runtime(mode)/'bin/racket','-l','raco','make',perf/'retained-host.rkt',perf/'settings.rkt',perf/'activation.rkt',perf/'budget-activation.rkt',observer/'support.rkt'],mode=mode,purpose='telemetry-precompile',timeout=120,required=False)
  command('Actual stock/off/on reply concurrency and cancellation suite',[STOCK/'bin/racket',EXP/'tests/independent-reply-test.rkt'],purpose='service-correctness',timeout=180,required=False)
  captures=[]
  for label,mode,trace_mode in (('stock','stock','stock'),('stock-again','stock','stock'),('off','candidate-off','off'),('on','candidate-on','on')):
   directory=REPORTS/('trace-'+label);directory.mkdir();output=directory/'trace.json';captures.append(output)
   command(label+' full actual monitor/go trace and rename endpoints',[runtime(mode)/'bin/racket',EXP/'tests/native-trace.rkt','--mode',trace_mode,'--runtime-root',runtime(mode),'--output',output],mode=mode,purpose='trace-'+label,timeout=200,required=False)
   if output.is_file():command(label+' exact trace log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',output],timeout=30,required=False)
  command('Stock/off/on complete semantic trace and rename equivalence; raw order diagnostic',[sys.executable,EXP/'tests/compare-trace.py',*captures],purpose='compare-traces',required=False)
  for mode in ('stock','candidate-on'):
   try:host_check(mode)
   except Exception as error:record(mode+' native host supervisor',False,str(error))
 elif PHASE=='telemetry':
  assert ROWS and all(r['passed'] for r in ROWS),'Any earlier correctness failure blocks measurements'
  perf=TELEMETRY/'performance';observer=TELEMETRY/'observer'
  manifests=[]
  for mode in ('stock','candidate-on'):
   try:command(mode+' identical compact observer installation and actual module compile',[sys.executable,observer/'prepare.py','--diagnostic-root',runtime(mode),'--racket',runtime(mode)/'bin/racket'],mode=mode,purpose='observer-prepare',timeout=260)
   finally:
    log=runtime(mode)/'openracket-compact-observer-compile.log'
    if log.is_file():print('OPENRACKET_XREF_COMPILE_LOG '+json.dumps(log.read_text()[-12000:]),flush=True)
   manifest=json.loads((runtime(mode)/'openracket-compact-observer-manifest.json').read_text());assert manifest['compiled'] is True
   manifests.append({k:manifest[k] for k in ('support_sha256','generator_sha256','files')})
   verify_sources(mode,mode!='stock')
   command(mode+' actual telemetry caller/helper compile',[runtime(mode)/'bin/racket','-l','raco','make',perf/'retained-host.rkt',perf/'settings.rkt',perf/'activation.rkt',perf/'budget-activation.rkt',observer/'support.rkt'],mode=mode,purpose='telemetry-compile',timeout=120)
  assert manifests[0]==manifests[1],'Both arms require byte-identical observer insertions'
  record('Both runtime copies use identical observer bytes',True,json.dumps(manifests[0]))
  rows=[];manifest=json.loads((EXP/'manifest.json').read_text())
  for pair in range(1,4):
   order=('candidate-on','stock') if pair==2 else ('stock','candidate-on')
   for mode in order:
    arm='stock' if mode=='stock' else 'candidate';label=f'pair-{pair}-{arm}';output=REPORTS/label;log=REPORTS/(label+'-supervisor.log')
    pin=manifest['original_sha256' if mode=='stock' else 'patched_sha256']
    command(label+' matched real GUI workload',[sys.executable,perf/'run.py','--mode','xref-'+arm,'--racket',runtime(mode)/'bin/racket','--output',output,'--repetitions','1','--fixture','mixed-1mib','--timeout','60','--xref-activation',arm,'--xref-source-sha256',pin,'--observer-support',observer/'support.rkt'],mode=mode,purpose=label,timeout=85,required=False,logfile=log)
    trial=output/'mixed-1mib-01/measurements.json';evidence=REPORTS/('evidence-'+label);evidence.mkdir()
    files=[(trial,'measurements.json'),(output/'summary.json','summary.json'),(trial.parent/'observer/worker-init.json','worker-init.json'),(trial.parent/'observer/worker-init-overhead.json','worker-init-overhead.json')]
    for source,name in files:
     if source.is_file():
      shutil.copyfile(source,evidence/name)
      command(label+' complete '+name+' log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',evidence/name],timeout=30,required=False)
    if trial.is_file():rows.append({'pair':pair,'mode':mode,'runtime_root':str(runtime(mode)),'data':json.loads(trial.read_text())})
    else:
     print('OPENRACKET_XREF_MISSING_TRIAL_LOG '+json.dumps(log.read_text()[-12000:]),flush=True)
     record(label+' complete trial record',False,'No measurements.json was produced')
  (REPORTS/'paired-records.json').write_text(json.dumps(rows,indent=2)+'\n')
  command('Six complete matched metadata records with explicit actual tool outcomes',[sys.executable,ROOT/'scripts/ci/validate-xref-pairs.py',REPORTS/'paired-records.json'],required=False)

 elif PHASE=='verify':
  command('Original runtime including bytecode unchanged',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',ORIGINAL,TEMP/'xref-pristine-tree.json'],timeout=180)
except Exception as e:record(PHASE+' orchestration',False,str(e));raise
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
