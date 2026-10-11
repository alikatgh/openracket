#!/usr/bin/env python3
"""One isolated native named-style experiment; product gates precede six complete-work trials."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,subprocess,sys
if sys.flags.optimize:raise RuntimeError('Optimized Python execution refused')
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
EXP=ROOT/'experiments/named-style';PRODUCTION=EXP/'production';EDITOR=EXP/'editor';CONTROLS=EXP/'controls';TELEMETRY=EXP/'performance'
TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve();ORIGINAL=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
STOCK=ORIGINAL.with_name(ORIGINAL.name+'-named-style-control');CANDIDATE=ORIGINAL.with_name(ORIGINAL.name+'-named-style-candidate')
assert os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket' and os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in ([p] for p in ('prepare','helpers','production','editor','controls','telemetry','verify'))
PHASE=sys.argv[1];REPORTS=ROOT/'reports/named-style-ci';REPORTS.mkdir(parents=True,exist_ok=True)
CLEANUP_BLOCK=REPORTS/'launch-blocked.json';CLEANUP_UNVERIFIED=False
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
COMPOSITION_PIN='6eb7d2b994519ac2db5c15edc3ec75daf0eadffc17c6dedb7da5ed471f494273'
TELEMETRY_PIN='840fe01e282b60ee8613a87c63e7e7ed21233741c3fb30eb923dcd3bec75bdc4'
FILES=('capture-host.json','capture-supervisor.json','memory-profile.json','gui-observation.json','worker-init.json','worker-phase-1.json','activation.json','heartbeat.json','binding-export.json','style-witness.json')
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/ci'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
contract=module('named_style_contract','named-style-ci-contract.py');evidence=module('named_style_evidence','named-style-evidence.py')
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_NAMED_STYLE_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Isolated Mac named-style lookup experiment','','Default-off style-only candidate. Same full GUI work,256MiB,stock20ms scheduling and all tools; all failures retained. No adoption or speed claim from gate success.','','| Check | Outcome | Detail |','|---|---|---|']
 lines += ['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+r['detail'].replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')
def env(mode='stock',purpose='checks'):return contract.environment(os.environ,mode,purpose,temp=TEMP,stock=STOCK,candidate=CANDIDATE)
def runtime(mode):return contract.selected_runtime(mode,STOCK,CANDIDATE)
def command(name,args,*,mode='stock',purpose='checks',timeout=90,environment=None,cwd=None,required=True,logfile=None):
 global CLEANUP_UNVERIFIED
 if (CLEANUP_UNVERIFIED or CLEANUP_BLOCK.exists()) and PHASE!='verify':
  record(name,False,'launch blocked after unverified process-group cleanup; original witness remains allowed')
  if required:raise RuntimeError(name+' blocked by prior cleanup failure')
  return False
 print('\n::group::'+name,flush=True);code=None;stream=None;started=False;completion_known=False
 lease=PHASE!='verify'
 try:
  # A pre-launch lease survives even if writing later cleanup diagnostics fails.
  # No subprocess starts when this initial durable write fails.
  if lease:CLEANUP_BLOCK.write_text(json.dumps({'command':name,'status':'launch-in-progress'})+'\n')
  if logfile:stream=pathlib.Path(logfile).open('w')
  p=subprocess.Popen([str(x) for x in args],env=env(mode,purpose) if environment is None else environment,cwd=cwd or ROOT,start_new_session=True,stdout=stream,stderr=subprocess.STDOUT if stream else None)
  started=True
  try:code=p.wait(timeout=timeout);completion_known=True
  except subprocess.TimeoutExpired:
   code=124
   try:terminate_group(p);completion_known=True
   except Exception as error:
    CLEANUP_UNVERIFIED=True
    failure={'command':name,'pid':p.pid,'error':str(error),'status':'cleanup-unverified-no-further-launches'}
    try:CLEANUP_BLOCK.write_text(json.dumps(failure,indent=2)+'\n')
    except Exception as persistence_error:failure['persistence_error']=str(persistence_error)
    record(name+' cleanup',False,json.dumps(failure))
 except Exception as error:
  if started and not completion_known:CLEANUP_UNVERIFIED=True
  record(name,False,'launch/wait/report: '+str(error))
 finally:
  if stream:stream.close()
  if lease and (not started or completion_known) and not CLEANUP_UNVERIFIED:
   try:CLEANUP_BLOCK.unlink(missing_ok=True)
   except Exception as error:
    CLEANUP_UNVERIFIED=True;record(name+' lease cleanup',False,str(error))
 if code is not None:record(name,code==0 and not CLEANUP_UNVERIFIED,'exit='+str(code))
 print('::endgroup::',flush=True)
 ok=code==0 and not CLEANUP_UNVERIFIED
 if not ok and required:raise RuntimeError(name+' failed')
 return ok

def collection(mode,module_name):
 if CLEANUP_UNVERIFIED or CLEANUP_BLOCK.exists():raise RuntimeError('Collection lookup blocked by unverified process cleanup')
 parts=module_name.split('/');parts[-1]+='.rkt';parts=[parts[-1],*parts[:-1]]
 expression='(display (collection-file-path '+' '.join(json.dumps(x) for x in parts)+'))'
 p=pathlib.Path(subprocess.check_output([runtime(mode)/'bin/racket','-e',expression],env=env(mode,'resolution'),text=True,timeout=30)).resolve()
 assert p.is_file() and not p.is_symlink() and p.is_relative_to(runtime(mode)) and p.stat().st_nlink==1,str(p)
 return p

def verify_sources(mode,patched,observed=False):
 pins=json.loads((CONTROLS/'RUNTIME-PINS.json').read_text());observed_pins={}
 if observed:
  m=json.loads((runtime(mode)/'openracket-gui-phase-manifest.json').read_text())
  observed_pins={'drracket/private/'+name.removesuffix('.rkt'):pin for name,pin in m['diagnostic_sources'].items()}
 result={}
 for name,pin in pins.items():
  p=collection(mode,name);expected=pin['candidate' if patched else 'stock'] if isinstance(pin,dict) else pin
  expected=observed_pins.get(name,expected);actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==expected,name
  result[name]={'path':str(p),'sha256':actual}
 assert not collection(mode,'drracket/private/unit').with_name('openracket-all-string-snips.rkt').exists()
 assert not (collection(mode,'mrlib/switchable-button').parent/'private/openracket-paint.rkt').exists()
 print('OPENRACKET_NAMED_STYLE_SOURCE_PATHS '+json.dumps({'mode':mode,'observed':observed,'sources':result}),flush=True)
 record(mode+' exact source/collection pins',True,'Only pinned style source and equally applied common observers may differ')
 return pathlib.Path(result['racket/snip/private/style']['path'])

def emit(path,label=None):
 path=pathlib.Path(path)
 try:
  if not path.is_file():return False
  if label is not None:
   folder=REPORTS/'transport'/label;folder.mkdir(parents=True,exist_ok=True);target=folder/path.name
   assert not target.exists();shutil.copyfile(path,target);path=target
  return command('Lossless '+path.parent.name+'/'+path.name,[sys.executable,ROOT/'scripts/ci/emit-replay-evidence.py',path],timeout=45,required=False)
 except Exception as error:
  record('Evidence '+str(path),False,'read/copy/emit: '+str(error))
  return False

def logs_and_reports(directory):
 directory=pathlib.Path(directory)
 try:
  if not directory.exists():return
  paths=sorted(directory.rglob('*'))
 except Exception as error:
  record('Evidence directory '+str(directory),False,str(error));return
 for path in paths:
  try:
   if not path.is_file():continue
   if path.name=='native.json':
    transport=REPORTS/'native-text-transport';transport.mkdir(exist_ok=True);copy=transport/'native.json'
    evidence.transport_json_copy(path,copy);emit(copy)
   elif path.name in ('report.json','process.json','capture.json','ready.json','trace.json'):emit(path)
   elif path.name in ('stdout.bin','stderr.bin'):
    raw=path.read_bytes();print('OPENRACKET_NAMED_STYLE_LOG_TAIL '+json.dumps({'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'truncated':len(raw)>8192,'text':raw[-8192:].decode('utf-8','replace')}),flush=True)
   elif path.name=='screenshot.png':
    b=path.read_bytes()
    if b[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(b)<=300*1024:
     label='named-style-'+path.parent.name
     print(f'OPENRACKET_SCREENSHOT_BEGIN {label} {len(b)} {hashlib.sha256(b).hexdigest()}',flush=True)
     encoded=base64.b64encode(b).decode()
     for i in range(0,len(encoded),3072):print(f'OPENRACKET_SCREENSHOT_DATA {label} {i//3072:04d} {encoded[i:i+3072]}',flush=True)
     print(f'OPENRACKET_SCREENSHOT_END {label}',flush=True)
  except Exception as error:record('Evidence '+str(path),False,str(error))

def verify_frozen():
 manifest=EXP/'CONTENTS-SHA256.json';assert hashlib.sha256(manifest.read_bytes()).hexdigest()==COMPOSITION_PIN
 members=json.loads(manifest.read_text())
 assert set(members)|{'CONTENTS-SHA256.json'}=={str(p.relative_to(EXP)) for p in EXP.rglob('*') if p.is_file()}
 for name,pin in members.items():
  p=EXP/name;assert not pathlib.Path(name).is_absolute() and '..' not in pathlib.Path(name).parts
  assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==pin,name
 assert hashlib.sha256((TELEMETRY/'SHA256SUMS').read_bytes()).hexdigest()==TELEMETRY_PIN
 production=json.loads((PRODUCTION/'manifest.json').read_text());pins=json.loads((TELEMETRY/'candidate-source-pins.json').read_text())
 assert pins['module']=='racket/snip/private/style'
 assert all(pins[k]==production[k] for k in ('stock_sha256','candidate_sha256'))
 record('Exact immutable1620 composition and telemetry',True,str(len(members))+' members; all original owner bytes')

try:
 if (CLEANUP_UNVERIFIED or CLEANUP_BLOCK.exists()) and PHASE!='verify':raise RuntimeError('Phase blocked by unverified process-group cleanup')
 if PHASE=='prepare':
  verify_frozen()
  for name in ('test-named-style-adapter.py','test-named-style-ci-contract.py','test-named-style-matrix.py','test-named-style-evidence.py','test-replay-evidence.py'):
   command('CI source/transport '+name,[sys.executable,ROOT/'scripts/ci'/name])
  command('Full pristine runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',ORIGINAL,TEMP/'named-style-pristine-tree.json'],timeout=180)
  for purpose in ('named-style-control','named-style-candidate'):
   command('Independent '+purpose,[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py',purpose],environment=os.environ.copy(),timeout=180)
  verify_sources('stock',False);target=verify_sources('candidate-off',False)
  command('Exact named-style-only application',[sys.executable,PRODUCTION/'scripts/overlay.py','apply','--runtime-root',CANDIDATE,'--target',target,'--confirm-disposable-copy'],mode='candidate-off')
  verify_sources('candidate-off',True)
  command('Production46 source/applier/refusal tests',[sys.executable,PRODUCTION/'tests/source_test.py'])
  command('Model15000 identity comparisons; not native proof',[sys.executable,PRODUCTION/'tests/snapshot_model.py'])
  for package in (EDITOR,CONTROLS):command(package.name+' portable checks',[sys.executable,'-m','unittest','discover','-s',package/'tests','-v'],cwd=package)
  trace=CONTROLS/'trace'
  for name in ('generate-comparator.py','generate-named-style-comparator.py'):command('Exact trace derivative '+name,[sys.executable,trace/name,'--check'])
  command('All trace wrapper refusals',[sys.executable,'-m','unittest','discover','-s',trace,'-p','test_*trace.py','-v'])
  command('Original trace semantic mutations',[sys.executable,'-m','unittest','discover','-s',trace/'upstream/tests','-p','test_compare_trace*.py','-v'])
  staged=REPORTS/'native-module-compile'
  command('Stage exact full style/fault modules for native compile',[sys.executable,PRODUCTION/'scripts/prepare_native.py','--destination',staged,'--prefs',collection('stock','racket/snip/private/prefs')])
  native_modules=sorted((CONTROLS/'native').rglob('*.rkt'))+sorted((EDITOR/'native').glob('*.rkt'))+sorted((PRODUCTION/'tests/native').glob('*.rkt'))+[trace/'upstream/tests/native-trace.rkt']+sorted(staged.rglob('*.rkt'))
  for mode in ('stock','candidate-off','candidate-on'):
   command(mode+' compile actual style and all native dependencies',[runtime(mode)/'bin/racket','-l','raco','make',collection(mode,'racket/snip/private/style'),*native_modules],mode=mode,purpose='compile',timeout=240)
 elif PHASE=='helpers':
  for mode in ('stock','candidate-on'):
   command(mode+' mandatory telemetry native preflight; zero skips',[sys.executable,TELEMETRY/'native_preflight.py','--racket',runtime(mode)/'bin/racket','--pristine-source',collection('stock','drracket/private/module-language').parent,'--profile',TEMP/('named-style-'+mode+'-preflight')],mode=mode,purpose='helper-native',timeout=300,cwd=TELEMETRY,required=False)
 elif PHASE=='production':
  destination=REPORTS/'production';destination.mkdir()
  command('Actual stock/unset/0/unexpected/1 style differential and publication controls',[sys.executable,PRODUCTION/'scripts/run_native.py','--racket',STOCK/'bin/racket','--official-style-source',collection('stock','racket/snip/private/style'),'--prefs',collection('stock','racket/snip/private/prefs'),'--report',destination/'native.json'],timeout=700,required=False)
  logs_and_reports(destination)
 elif PHASE=='editor':
  destination=REPORTS/'editor'
  command('Actual stock/stock-again/off/on incremental editor styles and rich WXME',[sys.executable,EDITOR/'scripts/run_native.py','--stock-racket',STOCK/'bin/racket','--stock-root',STOCK,'--candidate-racket',CANDIDATE/'bin/racket','--candidate-root',CANDIDATE,'--output',destination,'--authorize-native-execution'],environment=contract.clean_environment(os.environ),timeout=760,required=False)
  logs_and_reports(destination)
 elif PHASE=='controls':
  destination=REPORTS/'controls'
  command('Actual stock/off/on Check Syntax and four full annotation/rename controls',[sys.executable,CONTROLS/'scripts/run_native.py','--stock-root',STOCK,'--candidate-root',CANDIDATE,'--output',destination,'--authorize-native-execution'],environment=contract.clean_environment(os.environ),timeout=1040,required=False)
  logs_and_reports(destination)
 elif PHASE=='telemetry':
  assert ROWS and all(r['passed'] for r in ROWS),'Any earlier gate failure blocks measurement'
  manifests=[];inputs=[]
  for mode in ('stock','candidate-on'):
   arm='stock' if mode=='stock' else 'candidate'
   try:command(arm+' identical common GUI observation',[sys.executable,TELEMETRY/'prepare_gui.py','--arm',arm,'--diagnostic-root',runtime(mode),'--racket',runtime(mode)/'bin/racket'],mode=mode,purpose='telemetry-prepare',timeout=285)
   finally:
    path=runtime(mode)/'openracket-gui-phase-compile.log'
    try:
     if path.is_file():print('OPENRACKET_NAMED_STYLE_COMPILE_LOG '+json.dumps(path.read_bytes()[-8192:].decode('utf-8','replace')),flush=True)
    except Exception as error:record('Compilation log '+str(path),False,str(error))
   verify_sources(mode,mode!='stock',observed=True)
   manifest=runtime(mode)/'openracket-gui-phase-manifest.json';manifests.append(manifest)
   transport=REPORTS/arm;transport.mkdir();target=transport/'prepared-manifest.json';shutil.copyfile(manifest,target);emit(target)
   inputs.append((manifest,arm+'-prepared-manifest'))
  command('Generate shared immutable fixture',[sys.executable,TELEMETRY/'fixtures.py',REPORTS/'fixtures'],timeout=30)
  captures=[]
  for pair,mode in contract.trial_order():
   arm='stock' if mode=='stock' else 'candidate';label=f'pair-{pair}-{arm}';output=REPORTS/label
   ok=command(label+' full terminal/annotation/lexer readiness',[sys.executable,TELEMETRY/'capture.py','--arm',arm,'--manifest',runtime(mode)/'openracket-gui-phase-manifest.json','--racket',runtime(mode)/'bin/racket','--fixture',REPORTS/'fixtures/mixed-1mib.rkt','--output',output],mode=mode,purpose=label,timeout=235,required=False)
   captures.append({'pair':pair,'arm':arm,'path':str(output),'command_passed':ok})
   for name in FILES:
    path=output/name;inputs.append((path,label+'-'+path.stem));emit(path)
   for name in ('stdout.log','stderr.log'):
    path=output/name
    try:
     if not path.is_file():continue
     raw=path.read_bytes();print('OPENRACKET_NAMED_STYLE_LOG_TAIL '+json.dumps({'label':label,'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'truncated':len(raw)>8192,'text':raw[-8192:].decode('utf-8','replace')}),flush=True)
    except Exception as error:record('Trial log '+str(path),False,str(error))
  pairs=[];acceptances=[]
  for pair in range(1,4):
   directory=REPORTS/f'pair-{pair}';directory.mkdir();report=directory/'acceptance.json';acceptances.append(report)
   ok=command('pair-'+str(pair)+' strict complete-work acceptance',[sys.executable,TELEMETRY/'accept_named_style.py','--stock',REPORTS/f'pair-{pair}-stock','--candidate',REPORTS/f'pair-{pair}-candidate','--stock-manifest',manifests[0],'--candidate-manifest',manifests[1]],purpose=f'accept-{pair}',timeout=45,required=False,logfile=report)
   try:data=json.loads(report.read_text())
   except (OSError,ValueError) as error:data={'accepted':False,'failures':[str(error)]}
   pairs.append({'pair':pair,'command_passed':ok,'data':data});emit(report)
  digest_map=evidence.create_map(inputs,acceptances,REPORTS/'input-digests.json');emit(REPORTS/'input-digests.json')
  record('Original/canonical inputs bound to actual acceptance receipts',digest_map['verified'],json.dumps(digest_map['errors']))
  matrix={'captures':captures,'pairs':pairs,'input_digests':digest_map}
  (REPORTS/'matrix.json').write_text(json.dumps(matrix,indent=2)+'\n');emit(REPORTS/'matrix.json')
  command('All six complete matched trials; preserve every partial row',[sys.executable,ROOT/'scripts/ci/validate-named-style-matrix.py',REPORTS/'matrix.json'],required=False)
 elif PHASE=='verify':
  command('Full original runtime including bytecode unchanged',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',ORIGINAL,TEMP/'named-style-pristine-tree.json'],timeout=180)
except Exception as e:record(PHASE+' orchestration',False,str(e));raise
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
