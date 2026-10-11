#!/usr/bin/env python3
"""Mac pristine-stock memory-limit sensitivity; no candidate module patch."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,struct,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
EXP=ROOT/'experiments/memory-sensitivity';TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
ORIGINAL=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
STOCK=ORIGINAL.with_name(ORIGINAL.name+'-memory-sensitivity')
assert os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'],['measure'],['verify'])
TELEMETRY=EXP
PHASE=sys.argv[1];REPORTS=ROOT/'reports/memory-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
spec=importlib.util.spec_from_file_location('memory_contract',ROOT/'scripts/ci/memory-ci-contract.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_MEMORY_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Mac stock-memory setting sensitivity','', 'Only the disposable profile memory setting varies (128/256/512 MiB); the original 20 ms budget and stock tools remain. No product default changes.','', '| Check | Outcome | Detail |','|---|---|---|']
 lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def env(mode,purpose):
 assert mode=='stock'
 return contract.environment(os.environ,purpose,temp=TEMP,runtime=STOCK)
def runtime(mode):
 assert mode=='stock'
 return STOCK
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

def verify_sources():
 source_spec=importlib.util.spec_from_file_location('source_pins',ROOT/'scripts/ci/xref-ci-contract.py');pins=importlib.util.module_from_spec(source_spec);source_spec.loader.exec_module(pins)
 result={}
 for key,(parts,pin) in pins.UNCHANGED.items():
  p=collection('stock',parts);assert hashlib.sha256(p.read_bytes()).hexdigest()==pin,key+' changed';result[key]=str(p)
 xref=collection('stock',('xref.rkt','drracket','private','syncheck'))
 assert hashlib.sha256(xref.read_bytes()).hexdigest()=='acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7','Stock xref changed'
 assert not pathlib.Path(result['unit']).with_name('openracket-all-string-snips.rkt').exists()
 assert not (pathlib.Path(result['toolbar']).parent/'private/openracket-paint.rkt').exists()
 result['xref']=str(xref)
 print('OPENRACKET_MEMORY_CI_SOURCE_PATHS '+json.dumps(result),flush=True)
 record('Exact pristine experiment seams and clone collection paths',True,'No scan, budget, autosave, xref or appearance patch')

def host_check(mode):
 label='memory-stock-check-syntax';ready=REPORTS/(label+'-ready.json');done=REPORTS/(label+'-capture-done')
 log=REPORTS/(label+'.log');png=REPORTS/(label+'.png');e=env(mode,'native-host')
 e.update(OPENRACKET_UI='stock',OPENRACKET_NATIVE_CASE='check-syntax',
          OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done))
 assert not ready.exists() and not done.exists()
 print('\n::group::'+label,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen([str(runtime(mode)/'bin/racket'),str(ROOT/'tests/independent-native-host.rkt')],env=e,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
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
  record('Reviewed frozen stock-memory source hashes',True,str(len(manifest)))
  ram=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'],text=True,timeout=10).strip())
  runner={'physical_memory_bytes':ram,'os':platform.platform(),'architecture':platform.machine(),'parallel_large_trials':1,'limits_mib':contract.LIMITS,'order':contract.ORDER}
  print('OPENRACKET_MEMORY_CI_RUNNER '+json.dumps(runner),flush=True)
  (REPORTS/'runner.json').write_text(json.dumps(runner,indent=2)+'\n')
  contract.require_capacity(ram)
  record('At least 4 GiB physical RAM for sequential bounded trials',True,str(ram))
  command('Fresh-profile and balanced limit order tests',[sys.executable,ROOT/'scripts/ci/test-memory-ci-contract.py'])
  command('Lossless diagnostic transport checks',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
  command('Strict memory matrix metadata checks',[sys.executable,ROOT/'scripts/ci/test-memory-matrix.py'])
  command('Full pristine runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',ORIGINAL,TEMP/'memory-pristine-tree.json'],timeout=180)
  command('Independent pristine memory-sensitivity runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','memory-sensitivity'],environment=os.environ.copy(),timeout=180)
  verify_sources()
  perf=EXP/'performance';observer=EXP/'observer'
  private=collection('stock',('module-language.rkt','drracket','private')).parent
  e=env('stock','observer-source-tests');e['OPENRACKET_TEST_STOCK_PRIVATE']=str(private)
  command('Exact observer source boundaries',[sys.executable,observer/'test_source.py'],environment=e,timeout=90,cwd=observer,required=False)
  command('Memory setup, supervisor and observation rejection tests',[sys.executable,'-m','unittest','discover','-v','-s',perf,'-p','test_*.py'],purpose='memory-python-tests',timeout=180,cwd=perf,required=False)
  command('Native preference persistence, single-key delta and refusal tests',[sys.executable,EXP/'profile/test_memory_profile.py','--racket',STOCK/'bin/racket','--runtime-root',STOCK,'-v'],purpose='native-profile-tests',timeout=300,required=False)
  command('Native observer protocol and kill-safety tests',[STOCK/'bin/racket',observer/'test_support.rkt'],purpose='observer-helper-tests',timeout=180,cwd=observer,required=False)
  command('Actual stock host caller compile',[STOCK/'bin/racket','-l','raco','make',ROOT/'tests/independent-native-host.rkt',ROOT/'tests/independent-native-workflows.rkt'],purpose='host-compile',timeout=120,required=False)
  try:host_check('stock')
  except Exception as error:record('Stock host supervisor',False,str(error))
  assert all(r['passed'] for r in ROWS),'Independent correctness failure blocks observer setup and timing'
  try:command('Common compact observer installation and actual module compile',[sys.executable,observer/'prepare.py','--diagnostic-root',STOCK,'--racket',STOCK/'bin/racket'],purpose='observer-prepare',timeout=260)
  finally:
   log=STOCK/'openracket-compact-observer-compile.log'
   if log.is_file():print('OPENRACKET_MEMORY_COMPILE_LOG '+json.dumps(log.read_text()[-12000:]),flush=True)
  installed=json.loads((STOCK/'openracket-compact-observer-manifest.json').read_text());assert installed['compiled'] is True
  print('OPENRACKET_MEMORY_OBSERVER_MANIFEST '+json.dumps(installed),flush=True)
  verify_sources()
  command('Actual memory workload and setting helpers compile',[STOCK/'bin/racket','-l','raco','make',*sorted(perf.glob('*.rkt')),observer/'support.rkt'],purpose='workload-compile',timeout=120)
 elif PHASE=='measure':
  assert ROWS and all(r['passed'] for r in ROWS),'Any earlier correctness failure blocks measurements'
  perf=EXP/'performance';observer=EXP/'observer';rows=[]
  for round_number,limits in enumerate(contract.ORDER,1):
   for limit in limits:
    label=f'round-{round_number}-limit-{limit}';output=REPORTS/label;log=REPORTS/(label+'-supervisor.log')
    command(label+' matched stock GUI workload',[sys.executable,perf/'run.py','--mode','memory-'+str(limit),'--racket',STOCK/'bin/racket','--output',output,'--repetitions','1','--fixture','mixed-1mib','--timeout','60','--xref-activation','stock','--xref-source-sha256','acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7','--observer-support',observer/'support.rkt','--memory-limit-mib',str(limit),'--profile-helper',EXP/'profile/memory-profile.rkt'],purpose=label,timeout=120,required=False,logfile=log)
    trial=output/'mixed-1mib-01/measurements.json';evidence=REPORTS/('evidence-'+label);evidence.mkdir()
    files=[(trial,'measurements.json'),(trial.parent/'memory-profile.json','memory-profile.json'),(output/'summary.json','summary.json'),(trial.parent/'observer/worker-init.json','worker-init.json'),(trial.parent/'observer/worker-init-overhead.json','worker-init-overhead.json')]
    for source,name in files:
     if source.is_file():
      shutil.copyfile(source,evidence/name)
      command(label+' complete '+name+' log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',evidence/name],timeout=30,required=False)
    if trial.is_file():rows.append({'round':round_number,'memory_limit_mib':limit,'runtime_root':str(STOCK),'data':json.loads(trial.read_text())})
    else:
     print('OPENRACKET_MEMORY_MISSING_TRIAL_LOG '+json.dumps(log.read_text()[-12000:]),flush=True)
     record(label+' complete trial record',False,'No measurements.json was produced')
  (REPORTS/'matrix-records.json').write_text(json.dumps(rows,indent=2)+'\n')
  command('Nine memory-limit records with explicit actual tool outcomes',[sys.executable,ROOT/'scripts/ci/validate-memory-matrix.py',REPORTS/'matrix-records.json',hashlib.sha256((EXP/'profile/memory-profile.rkt').read_bytes()).hexdigest()],required=False)
 elif PHASE=='verify':
  command('Original runtime including bytecode unchanged',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',ORIGINAL,TEMP/'memory-pristine-tree.json'],timeout=180)
except Exception as e:record(PHASE+' orchestration',False,str(e));raise
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
