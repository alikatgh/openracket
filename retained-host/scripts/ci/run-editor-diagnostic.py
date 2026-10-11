#!/usr/bin/env python3
"""Focused four-arm WXME diagnostics only; no timing or candidate adoption."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,subprocess,sys
if sys.flags.optimize:raise RuntimeError('Optimized Python execution refused')
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
EXP=ROOT/'experiments/named-style';PRODUCTION=EXP/'production';EDITOR=EXP/'editor';CONTROLS=EXP/'controls';TELEMETRY=EXP/'performance'
TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve();ORIGINAL=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
STOCK=ORIGINAL.with_name(ORIGINAL.name+'-named-style-control');CANDIDATE=ORIGINAL.with_name(ORIGINAL.name+'-named-style-candidate')
assert os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket' and os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in ([p] for p in ('prepare','editor','verify'))
PHASE=sys.argv[1];REPORTS=ROOT/'reports/editor-diagnostic-ci';REPORTS.mkdir(parents=True,exist_ok=True)
CLEANUP_BLOCK=REPORTS/'launch-blocked.json';CLEANUP_UNVERIFIED=False
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
COMPOSITION_PIN='21f908b7d7618173777991f0243ebdf6435b9a627b8c07d61211ea7259673232'
TELEMETRY_PIN='840fe01e282b60ee8613a87c63e7e7ed21233741c3fb30eb923dcd3bec75bdc4'
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/ci'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
contract=module('named_style_contract','named-style-ci-contract.py');evidence=module('named_style_evidence','named-style-evidence.py')
emitter=module('editor_diagnostic_emitter','emit-replay-evidence.py')
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group

def record(name,ok,detail=''):
 ROWS.append({'name':name,'passed':bool(ok),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_EDITOR_DIAGNOSTIC_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Focused Mac WXME editor diagnostics','','Four unchanged stock/stock-again/off/on editor captures. Original failures and full diagnostic bytes remain evidence of failure. No timing, candidate adoption or native correctness claim from successful diagnostic collection.','','| Check | Outcome | Detail |','|---|---|---|']
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

def emit(path):
 # Existing pure emitter runs in-process, including after a blocked native lease.
 # Evidence collection never launches another process or clears the lease.
 path=pathlib.Path(path)
 try:
  if not path.is_file():return False
  emitter.emit(path);return True
 except Exception as error:
  record('Evidence '+str(path),False,'read/emit: '+str(error));return False

def transport_bytes(path,folder):
 path=pathlib.Path(path)
 assert path.is_file() and not path.is_symlink()
 raw=path.read_bytes()
 # Chunk raw bytes before the unchanged bounded JSON emitter. This transports
 # malformed JSON and non-UTF8 output too, without dropping any original byte.
 value={'schema':1,'kind':'editor-diagnostic-original-bytes','file':path.name,
        'source_relative_path':str(path.relative_to(REPORTS)),
        'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
        'encoding':'base64','chunks':[base64.b64encode(raw[i:i+12288]).decode('ascii') for i in range(0,len(raw),12288)]}
 folder.mkdir(parents=True,exist_ok=False);target=folder/'supervisor.json'
 target.write_text(json.dumps(value,separators=(',',':'))+'\n');return emit(target)

def logs_and_reports(directory):
 directory=pathlib.Path(directory)
 try:
  if not directory.exists():return
  paths=sorted(directory.rglob('*'))
 except Exception as error:
  record('Evidence directory '+str(directory),False,str(error));return
 for number,path in enumerate(paths):
  try:
   if not path.is_file() or path.name not in ('report.json','process.json','capture.json','stdout.bin','stderr.bin','fixture.wxme'):continue
   # Transport raw files independently first; malformed capture JSON never hides
   # its bytes or other arms. JSON transport additionally exposes nested arrays.
   transport_bytes(path,REPORTS/'transport'/('raw-%04d'%number))
   if path.suffix=='.json':
    folder=REPORTS/'transport'/('json-%04d'%number);folder.mkdir(parents=True)
    target=folder/path.name;evidence.transport_json_copy(path,target);emit(target)
  except Exception as error:record('Evidence '+str(path),False,str(error))

def verify_frozen():
 assert len(COMPOSITION_PIN)==64 and all(c in '0123456789abcdef' for c in COMPOSITION_PIN),'Reviewed diagnostic composition pin is pending'
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
 record('Exact reviewed diagnostic composition and unchanged telemetry',True,str(len(members))+' members; all original owner bytes')

try:
 if (CLEANUP_UNVERIFIED or CLEANUP_BLOCK.exists()) and PHASE!='verify':raise RuntimeError('Phase blocked by unverified process-group cleanup')
 if PHASE=='prepare':
  # Baseline before any preparatory native call; final witness remains independent
  # even if source verification or portable checks fail.
  command('Full pristine runtime baseline',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','baseline',ORIGINAL,TEMP/'editor-diagnostic-pristine-tree.json'],timeout=180)
  verify_frozen()
  for name in ('test-editor-diagnostic-adapter.py','test-named-style-ci-contract.py','test-named-style-evidence.py','test-replay-evidence.py'):
   command('CI source/transport '+name,[sys.executable,ROOT/'scripts/ci'/name])
  for purpose in ('named-style-control','named-style-candidate'):
   command('Independent '+purpose,[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py',purpose],environment=os.environ.copy(),timeout=180)
  verify_sources('stock',False);target=verify_sources('candidate-off',False)
  command('Exact named-style-only application',[sys.executable,PRODUCTION/'scripts/overlay.py','apply','--runtime-root',CANDIDATE,'--target',target,'--confirm-disposable-copy'],mode='candidate-off')
  verify_sources('candidate-off',True)
  command('Production46 source/applier/refusal tests',[sys.executable,PRODUCTION/'tests/source_test.py'])
  command('Model15000 identity comparisons; not native proof',[sys.executable,PRODUCTION/'tests/snapshot_model.py'])
  for package in (EDITOR,CONTROLS):command(package.name+' portable checks',[sys.executable,'-m','unittest','discover','-s',package/'tests','-v'],cwd=package)
  trace=CONTROLS/'trace'
  for name in ('generate-comparator.py','generate-named-style-comparator.py'):command('Exact trace derivative source check '+name,[sys.executable,trace/name,'--check'])
  command('Portable trace wrapper refusals',[sys.executable,'-m','unittest','discover','-s',trace,'-p','test_*trace.py','-v'])
  command('Portable trace semantic mutations',[sys.executable,'-m','unittest','discover','-s',trace/'upstream/tests','-p','test_compare_trace*.py','-v'])
  portable_env=env('stock','portable-source')
  portable_env['GUI_TEST_SOURCE_DIR']=str(collection('stock','drracket/private/module-language').parent)
  portable_modules=('test_accept_gui','test_accept_named_style','test_capture','test_gui_source','test_prepared_runtime','test_telemetry')
  command('Unchanged telemetry portable source checks only',[sys.executable,'-m','unittest','-v',*portable_modules],environment=portable_env,cwd=TELEMETRY)
  # Recursive inventory makes every new editor module a required compile input.
  native_modules=sorted((EDITOR/'native').rglob('*.rkt'))
  assert {EDITOR/'native/failure-observation.rkt',EDITOR/'native/reload-diagnostic.rkt'}<=set(native_modules),'Mandatory diagnostic modules missing'
  for mode in ('stock','candidate-off','candidate-on'):
   command(mode+' compile actual style and every editor native module',[runtime(mode)/'bin/racket','-l','raco','make',collection(mode,'racket/snip/private/style'),*native_modules],mode=mode,purpose='compile',timeout=240)
 elif PHASE=='editor':
  destination=REPORTS/'editor'
  try:
   command('Actual stock/stock-again/off/on incremental editor styles and rich WXME',[sys.executable,EDITOR/'scripts/run_native.py','--stock-racket',STOCK/'bin/racket','--stock-root',STOCK,'--candidate-racket',CANDIDATE/'bin/racket','--candidate-root',CANDIDATE,'--output',destination,'--authorize-native-execution'],environment=contract.clean_environment(os.environ),timeout=760,required=False)
  finally:logs_and_reports(destination)
 elif PHASE=='verify':
  command('Full original runtime including bytecode unchanged',[sys.executable,ROOT/'scripts/ci/runtime-tree-check.py','compare',ORIGINAL,TEMP/'editor-diagnostic-pristine-tree.json'],timeout=180)
except Exception as e:record(PHASE+' orchestration',False,str(e));raise
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
