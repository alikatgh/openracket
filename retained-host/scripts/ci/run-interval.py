#!/usr/bin/env python3
"""Exact interval-map-only correctness before separately frozen telemetry."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,struct,subprocess,sys,time
if sys.flags.optimize != 0:raise RuntimeError('Optimized Python execution would disable source/CI gates')
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
EXP=ROOT/'experiments/interval-map';TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
ORIGINAL=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
STOCK=ORIGINAL.with_name(ORIGINAL.name+'-interval-control');CANDIDATE=ORIGINAL.with_name(ORIGINAL.name+'-interval-candidate')
assert os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['prepare'],['helpers'],['correctness'],['telemetry'],['verify'])
TELEMETRY=ROOT/'experiments/interval-map-telemetry'
PRODUCTION_PIN='85858233bf10bb4e0e33c91af17c32cea8c0b1503c6a78c3ecc35e1e3c414b9a'
TELEMETRY_PIN='82bf5dba355c5374b5e0246a92a8b1064eafcffbed9ac3bba3eead52d1353f85'
PHASE=sys.argv[1];REPORTS=ROOT/'reports/interval-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
spec=importlib.util.spec_from_file_location('interval_contract',ROOT/'scripts/ci/interval-ci-contract.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_INTERVAL_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Isolated Mac interval-map direct-set experiment','', 'Only candidate data/interval-map.rkt changes; matching 256 MiB telemetry profiles, original 20 ms batching and stock tools remain. The delivered appearance/autosave preview is separate.','', '| Check | Outcome | Detail |','|---|---|---|']
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
 target=collection(mode,('interval-map.rkt','data'));expected=manifest['patched_sha256' if patched else 'original_sha256']
 assert hashlib.sha256(target.read_bytes()).hexdigest()==expected,'interval-map source pin'
 for relative,pin in manifest['unchanged_support_sha256_relative_to_data'].items():
  support=(target.parent/relative).resolve();assert support.is_relative_to(runtime(mode)) and hashlib.sha256(support.read_bytes()).hexdigest()==pin,relative
  result['support:'+relative]=str(support)
 unit=pathlib.Path(result['unit']);toolbar=pathlib.Path(result['toolbar'])
 assert not unit.with_name('openracket-all-string-snips.rkt').exists()
 assert not (toolbar.parent/'private/openracket-paint.rkt').exists()
 result.update(interval_map=str(target),interval_map_sha256=expected,mode=mode)
 print('OPENRACKET_INTERVAL_CI_SOURCE_PATHS '+json.dumps(result),flush=True)
 record(mode+' exact source/collection verification',True,'Only the candidate interval-map source may differ')
 return target

def host_check(mode):
 label='interval-'+mode+'-check-syntax';ready=REPORTS/(label+'-ready.json');done=REPORTS/(label+'-capture-done')
 log=REPORTS/(label+'.log');png=REPORTS/(label+'.png');e=env(mode,'native-host')
 e.update(OPENRACKET_UI='stock',OPENRACKET_NATIVE_CASE='check-syntax',OPENRACKET_INTERVAL_EXPECT_MODE=mode,
          OPENRACKET_INTERVAL_RUNTIME_ROOT=str(runtime(mode)),OPENRACKET_INTERVAL_DOCS_OUTPUT=str(REPORTS/('docs-'+mode)/'docs-map.json'),
          OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done))
 (REPORTS/('docs-'+mode)).mkdir()
 assert not ready.exists() and not done.exists()
 print('\n::group::'+label,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen([str(runtime(mode)/'bin/racket'),str(ROOT/'scripts/ci/interval-native-host.rkt')],env=e,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
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
 docs=REPORTS/('docs-'+mode)/'docs-map.json'
 if docs.is_file():command(label+' complete actual docs interval map',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',docs],timeout=30,required=False)
 print('::endgroup::',flush=True)
 return passed

try:
 if PHASE=='prepare':
  assert hashlib.sha256((EXP/'CONTENTS-SHA256.json').read_bytes()).hexdigest()==PRODUCTION_PIN
  assert hashlib.sha256((TELEMETRY/'SHA256SUMS').read_bytes()).hexdigest()==TELEMETRY_PIN
  for line in (TELEMETRY/'SHA256SUMS').read_text().splitlines():
   pin,name=line.split('  ',1);p=TELEMETRY/name
   assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
   assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==pin,name
  pins=json.loads((TELEMETRY/'candidate-source-pins.json').read_text());production=json.loads((EXP/'manifest.json').read_text())
  assert pins=={'stock_sha256':production['original_sha256'],'candidate_sha256':production['patched_sha256']}
  record('Reviewed frozen telemetry source hashes',True,TELEMETRY_PIN)
  manifest=json.loads((EXP/'CONTENTS-SHA256.json').read_text())
  for name,h in manifest.items():
   p=EXP/name;assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
   assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==h,name
  record('Reviewed frozen interval-map source hashes',True,str(len(manifest)))
  command('CI stage and native-gate contract checks',[sys.executable,ROOT/'scripts/ci/test-interval-adapter.py'])
  command('CI isolation contract checks',[sys.executable,ROOT/'scripts/ci/test-interval-ci-contract.py'])
  command('Strict interval matrix rejection tests',[sys.executable,ROOT/'scripts/ci/test-interval-matrix.py'])
  command('Lossless interval-map and diagnostic transport checks',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
  command('Full pristine runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',ORIGINAL,TEMP/'interval-pristine-tree.json'],timeout=180)
  for purpose in ('interval-control','interval-candidate'):
   command('Independent '+purpose+' runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py',purpose],environment=os.environ.copy(),timeout=180)
  verify_sources('stock',False);target=verify_sources('candidate-off',False)
  command('Pinned interval-map-only application',[sys.executable,EXP/'scripts/apply.py','--runtime-root',CANDIDATE,'--target',target,'--confirm-disposable-copy'],mode='candidate-off')
  verify_sources('candidate-off',True)
  command('Pinned source and installer refusal tests',[sys.executable,'-m','unittest','discover','-s',EXP/'tests','-p','test_*.py'])
  for mode in ('stock','candidate-off','candidate-on'):
   command(mode+' compile actual interval-map module',[runtime(mode)/'bin/racket','-l','raco','make',collection(mode,('interval-map.rkt','data')),EXP/'tests/interval-map-differential.rkt',EXP/'tests/native-trace.rkt',ROOT/'scripts/ci/interval-native-host.rkt',EXP/'tests/independent-native-host.rkt',EXP/'tests/independent-native-workflows.rkt',EXP/'tests/interval-docs-postflight.rkt',EXP/'tests/rackunit-failure-propagation.rkt',EXP/'tests/rackunit-failure-propagation-test.rkt'],mode=mode,purpose='compile',timeout=120)
 elif PHASE=='helpers':
  propagation_log=REPORTS/'rackunit-failure-propagation.log'
  propagation_ok=command('Actual separate-eventspace fatal-check propagation regression',
          [STOCK/'bin/racket',EXP/'tests/rackunit-failure-propagation-test.rkt'],purpose='failure-propagation',timeout=30,required=False,logfile=propagation_log)
  propagation_text=propagation_log.read_text();print(propagation_text[-32768:],flush=True)
  marker='OPENRACKET_RACKUNIT_PROPAGATION_OK separate-handler nonraising-ambient rejected-return escaped-failure'
  record('Fatal-check regression completed with exact success witness',propagation_ok and propagation_text.splitlines().count(marker)==1,'Requires exit0 plus one exact standalone witness')
  for mode in ('stock','candidate-on'):
   private=collection(mode,('module-language.rkt','drracket','private')).parent
   command(mode+' mandatory telemetry native preflight; no skips',
           [sys.executable,TELEMETRY/'native_preflight.py','--racket',runtime(mode)/'bin/racket','--pristine-source',private,'--profile',TEMP/('interval-'+mode+'-preflight')],mode=mode,purpose='helper-native',timeout=300,cwd=TELEMETRY,required=False)
 elif PHASE=='correctness':
  stock_source=collection('stock',('interval-map.rkt','data'));candidate_source=collection('candidate-off',('interval-map.rkt','data'))
  command('Exact single-setter source reconstruction',[sys.executable,EXP/'tests/check_interval_map_source.py',stock_source,candidate_source],required=False)
  for label,mode,value in (('unset','candidate-off',None),('zero','candidate-off','0'),('one','candidate-on','1')):
   e=env(mode,'differential-'+label)
   if value is not None:e['OPENRACKET_INTERVAL_MAP_FAST_SET']=value
   command(label+' actual interval-map randomized API and mutation differential',
           [runtime(mode)/'bin/racket',EXP/'tests/interval-map-differential.rkt',stock_source,candidate_source,'on' if value=='1' else 'off'],environment=e,timeout=180,required=False)
  captures=[]
  for label,mode,trace_mode in (('stock','stock','stock'),('stock-again','stock','stock'),('off','candidate-off','off'),('on','candidate-on','on')):
   directory=REPORTS/('trace-'+label);directory.mkdir();output=directory/'trace.json';captures.append(output)
   command(label+' full actual monitor/go trace and rename endpoints',
           [runtime(mode)/'bin/racket',EXP/'tests/native-trace.rkt','--mode',trace_mode,'--runtime-root',runtime(mode),'--output',output],mode=mode,purpose='trace-'+label,timeout=200,required=False)
   if output.is_file():command(label+' exact trace log evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',output],timeout=30,required=False)
  command('Complete semantic trace and real rename equivalence; raw order diagnostic',
          [sys.executable,EXP/'tests/compare-trace.py',*captures],purpose='compare-traces',required=False)
  for mode in ('stock','candidate-on'):
   try:host_check(mode)
   except Exception as error:record(mode+' native host supervisor',False,str(error))
  command('Stock/candidate actual GUI docs-map exact lookup and boundary parity',
          [sys.executable,EXP/'tests/compare-docs-map.py',REPORTS/'docs-stock/docs-map.json',REPORTS/'docs-candidate-on/docs-map.json'],purpose='docs-compare',required=False)
 elif PHASE=='telemetry':
  assert ROWS and all(r['passed'] for r in ROWS),'Any earlier correctness failure blocks measurements'
  observer_manifests=[]
  for mode in ('stock','candidate-on'):
   try:command(mode+' identical common GUI observer installation',
           [sys.executable,TELEMETRY/'prepare_gui.py','--diagnostic-root',runtime(mode),'--racket',runtime(mode)/'bin/racket'],mode=mode,purpose='telemetry-prepare',timeout=285)
   finally:
    compile_log=runtime(mode)/'openracket-gui-phase-compile.log'
    if compile_log.is_file():print('OPENRACKET_INTERVAL_COMPILE_LOG '+json.dumps(compile_log.read_text()[-32768:]),flush=True)
   observer_manifests.append(runtime(mode)/'openracket-gui-phase-manifest.json')
   verify_sources(mode,mode!='stock')
  command('Generate one identical immutable workload fixture',[sys.executable,TELEMETRY/'fixtures.py',REPORTS/'fixtures'],timeout=30)
  files=('capture-host.json','capture-supervisor.json','memory-profile.json','gui-observation.json','worker-init.json','worker-phase-1.json','activation.json','heartbeat.json')
  captures=[]
  for pair,mode in contract.trial_order():
   arm='stock' if mode=='stock' else 'candidate';label=f'pair-{pair}-{arm}';output=REPORTS/label
   ok=command(label+' genuine GUI terminal, annotation application and lexer completion',
              [sys.executable,TELEMETRY/'capture.py','--arm',arm,'--racket',runtime(mode)/'bin/racket','--fixture',REPORTS/'fixtures/mixed-1mib.rkt','--output',output],mode=mode,purpose=label,timeout=235,required=False)
   captures.append({'pair':pair,'arm':arm,'path':str(output),'command_passed':ok})
   for name in files:
    path=output/name
    if path.is_file():command(label+' '+name+' lossless evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',path],timeout=30,required=False)
   for name in ('stdout.log','stderr.log'):
    path=output/name
    if path.is_file():
     raw=path.read_bytes();print('OPENRACKET_INTERVAL_LOG_TAIL '+json.dumps({'label':label,'file':name,'bytes':len(raw),'truncated':len(raw)>32768,'text':raw[-32768:].decode('utf-8','replace')}),flush=True)
  pairs=[]
  for pair in range(1,4):
   directory=REPORTS/f'pair-{pair}';directory.mkdir();report=directory/'acceptance.json'
   ok=command('pair-'+str(pair)+' strict complete-work acceptance',
              [sys.executable,TELEMETRY/'accept_interval.py','--stock',REPORTS/f'pair-{pair}-stock','--candidate',REPORTS/f'pair-{pair}-candidate',
               '--stock-manifest',observer_manifests[0],'--candidate-manifest',observer_manifests[1]],purpose=f'accept-{pair}',timeout=45,required=False,logfile=report)
   try:data=json.loads(report.read_text())
   except (OSError,ValueError) as error:data={'accepted':False,'failures':[str(error)]}
   pairs.append({'pair':pair,'command_passed':ok,'data':data})
   if report.is_file():command('pair-'+str(pair)+' acceptance evidence',[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',report],timeout=30,required=False)
  matrix={'captures':captures,'pairs':pairs}
  (REPORTS/'matrix.json').write_text(json.dumps(matrix,indent=2)+'\n')
  command('All six valid captures and three strictly accepted pairs',[sys.executable,ROOT/'scripts/ci/validate-interval-matrix.py',REPORTS/'matrix.json'],required=False)


 elif PHASE=='verify':
  command('Original runtime including bytecode unchanged',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',ORIGINAL,TEMP/'interval-pristine-tree.json'],timeout=180)
except Exception as e:record(PHASE+' orchestration',False,str(e));raise
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
