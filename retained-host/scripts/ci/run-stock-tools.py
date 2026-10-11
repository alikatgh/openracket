#!/usr/bin/env python3
"""Independent stock/modern-dark Debugger, Macro Stepper and teaching-test gates."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,struct,subprocess,sys,time
if sys.flags.optimize:raise SystemExit('Optimized Python disables required gates')
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket' and platform.system()=='Darwin'
assert sys.argv[1:] in (['prepare'],['cases'],['verify'])
PHASE=sys.argv[1];TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1];MODERN=STOCK.with_name(STOCK.name+'-native-tools')
EXP=ROOT/'experiments/native-tool-gates';PROOF=TEMP/'OpenRacket Native Tool Proof';PROFILE=PROOF/'profile';ADDON=PROFILE/'.local/share/racket';CACHE=PROFILE/'compiled-cache'
REPORTS=ROOT/'reports/stock-tools-ci';REPORTS.mkdir(parents=True,exist_ok=True);STATE=REPORTS/'results.json'
ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
SPEC=importlib.util.spec_from_file_location('app_contract',ROOT/'scripts/ci/app-ci-contract.py');CONTRACT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CONTRACT)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n');print('OPENRACKET_STOCK_TOOLS_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Actual stock and modern-dark native tools','', 'Six fresh-process cases: stock prerequisite and modern-dark counterpart for Debugger, Macro Stepper and teaching tests. Each uses fresh stock-default128 preferences, independently copied addon registry and private compiled roots. Modern-light is not covered.', '', '| Gate | Outcome | Detail |','|---|---|---|']
 lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 lines+=['','Stock failure blocks only its corresponding modern comparison; every other independent case still runs. Native host has the unchanged60s case process bound,20s tool awaits and original strict READY/exit/result assertions.',
 'These gates are independent of the256MiB annotation diagnostic. No timing claim or previously rejected performance candidate is included. Historical Stop, normal Quit, unsaved prompts and other release gaps remain separate.']
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def env(label,modern=False,setup=False):
 home=PROFILE if setup else TEMP/('stock-tools-'+label)
 addon=ADDON if setup else home/'addon';cache=CACHE if setup else home/'compiled'
 result=CONTRACT.environment(os.environ,(MODERN if modern else STOCK)/'bin/racket',home,addon,cache)
 return result

def command(name,args,environment=None,timeout=120,required=True):
 print('::group::'+name,flush=True);p=subprocess.Popen([str(x) for x in args],env=environment or env('checks'),start_new_session=True)
 try:code=p.wait(timeout=timeout)
 except subprocess.TimeoutExpired:terminate_group(p);code=124
 record(name,code==0,'exit='+str(code));print('::endgroup::',flush=True)
 if code and required:raise RuntimeError(name+' failed')
 return code==0

def coordinator_result_valid(code,output,negative):
 lines=output.splitlines()
 success='OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete'
 injection='OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE'
 if negative:
  return code>0 and code!=124 and lines.count(injection)==1 and success not in output and 'actual' in output and 'deliberately-wrong' in output
 return code==0 and lines.count(success)==1 and injection not in output

def coordinator_regression(mode,e):
 for negative in (False,True):
  label=mode+' standalone coordinator '+('injected-negative' if negative else 'positive')
  args=[e['RACKET'],'-A',e['PLTADDONDIR'],'-R',e['PLTCOMPILEDROOTS'],str(PROOF/'tests/native-tool-coordinator-standalone.rkt')]
  if negative:args.append('--inject-outer-failure')
  print('::group::'+label,flush=True)
  p=subprocess.Popen(args,env=e,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
  try:output,_=p.communicate(timeout=30);code=p.returncode
  except subprocess.TimeoutExpired:
   terminate_group(p);output,_=p.communicate(timeout=5);code=124
  print(output,flush=True)
  passed=coordinator_result_valid(code,output,negative)
  record(label,passed,'exit='+str(code)+'; strict marker and outer-failure behavior checked')
  print('::endgroup::',flush=True)

def tree(operation,root,label,required=True):
 return command(label+' entire original runtime '+operation,[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py',operation,root,TEMP/('stock-tools-'+label+'-tree.json')],timeout=180,required=required)

def screenshot(path,deadline):
 remaining=deadline-time.monotonic()
 if remaining<=0:return False,'No capture time remains within unchanged60s process bound'
 try:
  p=subprocess.run(['/usr/sbin/screencapture','-x',str(path)],timeout=min(15,remaining),capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  b=path.read_bytes();assert b[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(b)<=300*1024
  return True,str(struct.unpack('>II',b[16:24]))+' '+hashlib.sha256(b).hexdigest()
 except Exception as error:return False,str(error)

def emit_image(label,path):
 b=path.read_bytes();s=base64.b64encode(b).decode();print(f'OPENRACKET_SCREENSHOT_BEGIN {label} {len(b)} {hashlib.sha256(b).hexdigest()}',flush=True)
 for i in range(0,len(s),3072):print(f'OPENRACKET_SCREENSHOT_DATA {label} {i//3072:04d} {s[i:i+3072]}',flush=True)
 print(f'OPENRACKET_SCREENSHOT_END {label}',flush=True)

def native_case(case,modern=False):
 mode='modern-dark' if modern else 'pristine-stock';label='tools-'+mode+'-'+case;e=env(label,modern)
 home=pathlib.Path(e['PLTUSERHOME']);assert not home.exists();home.mkdir()
 if modern:shutil.copytree(ADDON,pathlib.Path(e['PLTADDONDIR']),symlinks=True)
 e.update(OPENRACKET_UI='modern' if modern else 'stock',OPENRACKET_HOST_THEME='1' if modern else '0',OPENRACKET_NATIVE_APPEARANCE='1' if modern else '0',OPENRACKET_THEME='dark' if modern else 'light',OPENRACKET_NATIVE_CASE=case)
 if modern:e['OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD']='1'
 ready=REPORTS/(label+'-ready.json');done=REPORTS/(label+'-capture-done');image=REPORTS/(label+'.png');logfile=REPORTS/(label+'.log')
 e.update(OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done));assert not ready.exists() and not done.exists()
 captured=False;detail='Native host never became ready';report={};result=124
 print('::group::'+label,flush=True)
 with logfile.open('w') as log:
  p=subprocess.Popen([e['RACKET'],'-A',e['PLTADDONDIR'],'-R',e['PLTCOMPILEDROOTS'],str(PROOF/'tests/independent-native-host.rkt')],env=e,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  deadline=time.monotonic()+60
  while p.poll() is None and time.monotonic()<deadline:
   if ready.exists():
    captured,detail=screenshot(image,deadline)
    done.write_text('OS capture attempted\n');break
   time.sleep(.1)
  try:result=p.wait(timeout=max(.01,deadline-time.monotonic()))
  except subprocess.TimeoutExpired:
   # Acceptance failed at60s. Up to15s of explicitly labelled diagnostic
   # capture grace follows before cleanup; it can never become a passing result.
   if not captured:captured,detail=screenshot(image,time.monotonic()+15)
   terminate_group(p);result=124
 print(logfile.read_text(errors='replace'),flush=True)
 if ready.exists():
  raw=ready.read_bytes()
  try:
   assert len(raw)<2*1024*1024,'Native READY exceeds evidence bound'
   report=json.loads(raw)
   assert isinstance(report,dict),'READY must be an object'
  except Exception as error:
   report={'status':'malformed-failure','error':str(error),'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_text':raw[:32768].decode('utf-8','replace'),'raw_text_truncated':len(raw)>32768}
  folder=REPORTS/label;folder.mkdir();(folder/'ready.json').write_text(json.dumps(report)+'\n')
  subprocess.run([sys.executable,str(ROOT/'scripts/ci/emit-replay-evidence.py'),str(folder/'ready.json')],check=True,timeout=30)
 passed=result==0 and report.get('status')=='passed' and report.get('follow_on_case')==case and isinstance(report.get('follow_on_result'),dict) and report['follow_on_result'].get('status')=='passed'
 record(label+' native real-tool gate',passed,'exit='+str(result)+' acceptance_deadline_seconds=60 timeout_diagnostic_grace_max_seconds=15 status='+str(report.get('status'))+' case='+str(report.get('follow_on_case')))
 record(label+' native OS capture',captured,detail)
 if captured:emit_image(label if passed else label+('-timeout-diagnostic' if result==124 else '-failure-diagnostic'),image)
 print('::endgroup::',flush=True);return passed

try:
 if PHASE=='prepare':
  tree('baseline',STOCK,'pristine')
  m=EXP/'DELIVERABLE-SHA256.json';assert hashlib.sha256(m.read_bytes()).hexdigest()=='753839e4a470ebf9fb33a95f4100b3954a6f55718cc14c3310cc7cc46d2bd1bc'
  members=json.loads(m.read_text());assert len(members)==20
  for name,h in members.items():
   p=EXP/name;assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==h
  command('Portable exact host reproduction',[sys.executable,EXP/'scripts/prepare-stock-tool-host.py','--check'])
  command('Portable stock-tool source preservation',[sys.executable,EXP/'tests/stock-tool-source-test.py'])
  command('Standalone driver source preservation',[sys.executable,EXP/'tests/coordinator-standalone-source-test.py'])
  command('Stock-tool adapter isolation tests',[sys.executable,ROOT/'scripts/ci/test-stock-tools-adapter.py'])
  CONTRACT.source_copy(ROOT,PROOF,'2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552',155)
  raw=EXP/'FROZEN-NATIVE-ALLOWLIST.json';assert hashlib.sha256(raw.read_bytes()).hexdigest()=='f74d22a1b1e15956d8a86b6b884fb3d69655523d79e125c777a16b5758fb961a'
  allowed=json.loads(raw.read_text())['files'];assert len(allowed)==5
  baseline=json.loads((PROOF/'CONTENTS-SHA256.json').read_text());shutil.copy2(PROOF/'CONTENTS-SHA256.json',PROOF/'BASE-0520-CONTENTS.json')
  for name,h in allowed.items():
   assert hashlib.sha256((EXP/name).read_bytes()).hexdigest()==h
   dest=PROOF/name
   if dest.exists():dest.unlink()
   shutil.copy2(EXP/name,dest);baseline[name]=h
  (PROOF/'CONTENTS-SHA256.json').write_text(json.dumps(baseline,indent=2)+'\n')
  record('Complete native candidate assembled from exact0520 plus five reviewed test files',True,str(len(baseline))+' source files; production scripts unchanged')
  command('Independent modern-only tool runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','native-tools'],os.environ.copy(),180)
  tree('baseline',MODERN,'selected-modern')
  command('Actual unchanged setup for modern tool registration',['/bin/sh',PROOF/'scripts/setup-openracket.sh','--install'],env('setup',True,True),720)
  compile_files=[PROOF/'tests'/n for n in ('native-tool-coordinator-standalone.rkt','native-tool-coordinator.rkt','native-tool-coordinator-test.rkt','independent-native-stock-tools.rkt','independent-native-host.rkt','independent-native-workflows.rkt','independent-native-appearance-workflows.rkt','independent-native-stop-returning.rkt')]
  for mode,modern in [('stock',False),('modern',True)]:
   e=env('compile-'+mode,modern)
   if modern:
    home=pathlib.Path(e['PLTUSERHOME']);home.mkdir();shutil.copytree(ADDON,pathlib.Path(e['PLTADDONDIR']),symlinks=True)
   prefix=[e['RACKET'],'-A',e['PLTADDONDIR'],'-R',e['PLTCOMPILEDROOTS'],'-l','raco','--']
   command(mode+' explicit native tool callers and runtime-path modules compile',prefix+['make',*compile_files],e,180)
   coordinator_regression(mode,e)
 elif PHASE=='cases':
  for case in ('debugger','macro-stepper','teaching-tests'):
   if native_case(case):native_case(case,True)
   else:record('tools-modern-dark-'+case+' comparison not run',False,'Corresponding actual stock gate failed; other independent cases continue')
 elif PHASE=='verify':
  for root,label in ((STOCK,'pristine'),(MODERN,'selected-modern')):
   if (TEMP/('stock-tools-'+label+'-tree.json')).exists():tree('compare',root,label,False)
   else:record(label+' full runtime witness unavailable',False)
except Exception as error:record(PHASE+' orchestration',False,str(error));raise
finally:print('Stock tool report: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
