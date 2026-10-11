#!/usr/bin/env python3
"""Destination-built native Mac app: actual builder and Launch Services evidence."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,plistlib,shutil,signal,secrets,struct,subprocess,sys,time
if sys.flags.optimize:raise SystemExit('Python optimization disables required assertions; refused')
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true'
assert os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert platform.system()=='Darwin' and platform.machine()=='arm64'
assert sys.argv[1:] in (['prepare'],['install'],['build'],['observer'],['launch'],['relocate'],['verify'])
PHASE=sys.argv[1];TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
RUNTIME=TEMP/'OpenRacket App Runtime'/'Racket 9.3'
PROOF=TEMP/"OpenRacket App Proof λ's";PROFILE=PROOF/'profile';ADDON=PROFILE/'.local/share/racket';CACHE=PROFILE/'compiled-cache'
BUILDER=ROOT/'experiments/mac-app-builder';HEARTBEAT=ROOT/'experiments/heartbeat-cas'
OBSERVER_SOURCE=ROOT/'experiments/mac-app-observer';OBSERVER=TEMP/'OpenRacket App Observer'
APP_PARENT=TEMP/"OpenRacket App Output λ's";APP=APP_PARENT/'OpenRacket Preview.app'
MOVED=TEMP/"Relocated App λ's"/'Moved OpenRacket Preview.app'
REPORTS=ROOT/'reports/mac-app-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
SPEC=importlib.util.spec_from_file_location('app_contract',ROOT/'scripts/ci/app-ci-contract.py');CONTRACT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CONTRACT)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group
BUILDER_PIN='b4e5638c409b018a8dec030ea7dafb60291bfffc2645a5d087d7e91d4cfd77ee'
OBSERVER_PIN='3a4d1cdabbdbbcce4ecdcf40132748db168fc6515479112036c24df78aabb2e1'
SOURCE_PIN='2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'


def record(name,passed,detail=''):
 ROWS.append({'name':name,'passed':bool(passed),'detail':detail});STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_MAC_APP_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Destination-built Mac app validation','', 'Commit: '+os.environ['GITHUB_SHA'],'','| Gate | Outcome | Detail |','|---|---|---|']
 lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+str(r['detail']).replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 lines+=['','This is a Racket-only, destination-built app tethered to the verified source and full official runtime. A runner-built bundle cannot be delivered as a portable app for another computer.',
 'Actual Launch Services dispatch and read-only observer evidence are distinct from shell fixture tests. Final observer exit is test cleanup, not normal Quit acceptance.',
 'Historical observer README registration examples retain -U; the reviewed CI deliberately uses the separate no-U installed-profile prefix, with explicit private addon/cache and exact collection-source resolution. The stale recipe is not the executed acceptance command.',
 'Broader unsaved-Quit, forced-instance, rich/two-file delivery, failure UX, accessibility/IME and transferred-app/Gatekeeper cases remain pending unless explicitly recorded. No performance adoption follows from packaging.',
 'Only bounded synthetic screenshots and JSON use ordinary job logs. No artifact/cache/release upload or paid runner. No intentional default-handler or security-setting writes; any observed automatic association change fails acceptance.']
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def env(label,installed=False):
 home=PROFILE if installed else TEMP/('app-ci-'+label)
 return CONTRACT.environment(os.environ,RUNTIME/'bin/racket',home,ADDON if installed else home/'addon',CACHE if installed else home/'compiled')

def command(name,args,environment=None,timeout=120,required=True,expect=0):
 print('\n::group::'+name,flush=True)
 p=subprocess.Popen([str(a) for a in args],env=environment or env('checks'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,text=True)
 try:out,_=p.communicate(timeout=timeout);code=p.returncode
 except subprocess.TimeoutExpired:
  terminate_group(p);out,_=p.communicate(timeout=10);code=124
 print(out,flush=True);passed=code==expect
 record(name,passed,'exit='+str(code));print('::endgroup::',flush=True)
 if required and not passed:raise RuntimeError(name+' failed')
 return code,out

def witness(operation,label,path):
 dest=TEMP/('mac-app-witness-'+label+'.json');current=CONTRACT.snapshot(path)
 if operation=='baseline':
  assert not dest.exists();dest.write_text(json.dumps({'root':str(path),'entries':current},sort_keys=True)+'\n');result=CONTRACT.same_snapshot(current,current)
 else:
  before=json.loads(dest.read_text());assert before['root']==str(path);result=CONTRACT.same_snapshot(before['entries'],current)
 print('OPENRACKET_APP_IMMUTABILITY '+json.dumps({'operation':operation,'label':label,'path':str(path),**result}),flush=True)
 record(label+' complete bytes/modes/mtime/symlink witness '+operation,result['unchanged'],json.dumps(result))
 return result['unchanged']

def verify_builder():
 manifest=BUILDER/'CANDIDATE-SHA256.json';assert hashlib.sha256(manifest.read_bytes()).hexdigest()==BUILDER_PIN
 files=json.loads(manifest.read_text());assert len(files)==14
 for name,digest in files.items():
  path=BUILDER/name;assert path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
 assert hashlib.sha256((HEARTBEAT/'SHA256SUMS').read_bytes()).hexdigest()=='94bba4c9f571972a4996e399a4f766bbb0257d8bb742f38fa847a0e4c8e88285'
 for row in (HEARTBEAT/'SHA256SUMS').read_text().splitlines():
  digest,name=row.split('  ');assert hashlib.sha256((HEARTBEAT/name).read_bytes()).hexdigest()==digest
 record('Exact builder and separate heartbeat helper sources',True,BUILDER_PIN)

def raco_prefix():return [RUNTIME/'bin/racket','-U','-A',ADDON,'-R',str(CACHE)+':','-l','raco','--']

def installed_raco_prefix():
 # -U disables user collection links even with-A. This separate prefix is only
 # for the explicitly isolated installed-profile registration path.
 return [RUNTIME/'bin/racket','-A',ADDON,'-R',str(CACHE)+':','-l','raco','--']

def default_handler(label):
 code,out=command('Read-only original .rkt default handler '+label,[RUNTIME/'bin/racket','-U',OBSERVER/'default-handler.rkt'],env('default-handler'),30)
 result=json.loads(out);assert result['schema']==1 and result['status']=='observed' and result['defaults_changed'] is False
 assert result['extension']=='rkt' and result['role_mask']==4294967295
 (REPORTS/('default-handler-'+label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 if label!='before-build':
  before=json.loads((REPORTS/'default-handler-before-build.json').read_text())
  assert (result['uti'],result['default_handler'])==(before['uti'],before['default_handler']),'Original .rkt handler changed'
 record('Original .rkt UTI/default handler '+label,True,json.dumps(result))
 return result

def require_default_handler_unchanged(label):
 try:return default_handler(label)
 except Exception as error:
  if not (REPORTS/'launch-blocked.json').exists():
   atomic_json(REPORTS/'launch-blocked.json',{'label':label,'reason':'Original file-handler preservation failed or could not be verified','error':str(error)})
  raise

def application_manifest(app):
 info=plistlib.loads((app/'Contents/Info.plist').read_bytes());build=json.loads((app/'Contents/Resources/build-record.json').read_text())
 assert info['CFBundleExecutable']=='OpenRacket-launch' and info['CFBundlePackageType']=='APPL'
 assert info['LSMultipleInstancesProhibited'] is True
 assert 'LSEnvironment' not in info and 'LSUIElement' not in info and 'LSBackgroundOnly' not in info
 assert 'CFBundleDocumentTypes' not in info,'Product app must not advertise file associations'
 native=app/'Contents/MacOS'/build['native_executable'];assert native.is_file() and os.access(native,os.X_OK)
 assert os.access(app/'Contents/MacOS/OpenRacket-launch',os.X_OK)
 assert build['source_manifest_sha256']==SOURCE_PIN and pathlib.Path(build['source'])==PROOF and pathlib.Path(build['runtime_root'])==RUNTIME
 assert build['self_contained'] is False and build['developer_id_signed'] is False and build['notarized'] is False
 files=CONTRACT.snapshot(app)
 doc={'path':str(app),'plist':info,'build':build,'native_executable':str(native),'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'entries':files}
 (REPORTS/'application-build.json').write_text(json.dumps(doc,indent=2)+'\n')
 print('OPENRACKET_APP_BUILD '+json.dumps({k:v for k,v in doc.items() if k!='entries'}),flush=True)
 emit_document('app-build','summary.json',{'count':len(files),'tree_sha256':CONTRACT.same_snapshot(files,files)['tree_sha256'],'files':[{'path':name,'metadata':value} for name,value in files.items()]})
 return doc

def atomic_json(path,value):
 assert not path.exists(),'Refusing existing control/evidence: '+str(path)
 temporary=path.with_name(path.name+'.tmp');assert not temporary.exists()
 temporary.write_text(json.dumps(value,ensure_ascii=False)+'\n');temporary.replace(path)

def emit_document(label,name,value):
 directory=REPORTS/label;directory.mkdir(exist_ok=True);path=directory/name
 atomic_json(path,value)
 subprocess.run([sys.executable,str(ROOT/'scripts/ci/emit-replay-evidence.py'),str(path)],check=True,timeout=30)

def capture(label):
 path=REPORTS/(label+'.png')
 try:
  p=subprocess.run(['/usr/sbin/screencapture','-x',str(path)],capture_output=True,text=True,timeout=15)
  if p.returncode:raise RuntimeError(p.stderr[:500])
  data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(data)<=300*1024
  width,height=struct.unpack('>II',data[16:24]);assert width>=640 and height>=400
  record(label+' OS screenshot',True,json.dumps({'width':width,'height':height,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}))
  return path
 except Exception as e:
  record(label+' OS screenshot',False,str(e));return None

def emit_image(label,path):
 data=path.read_bytes();encoded=base64.b64encode(data).decode('ascii')
 print(f'OPENRACKET_SCREENSHOT_BEGIN {label} {len(data)} {hashlib.sha256(data).hexdigest()}',flush=True)
 for i in range(0,len(encoded),3072):print(f'OPENRACKET_SCREENSHOT_DATA {label} {i//3072:04d} {encoded[i:i+3072]}',flush=True)
 print(f'OPENRACKET_SCREENSHOT_END {label}',flush=True)

def processes():
 out=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,state=,command='],text=True,timeout=3)
 result=[]
 for line in out.splitlines():
  parts=line.strip().split(None,3)
  if len(parts)==4:result.append({'pid':int(parts[0]),'ppid':int(parts[1]),'state':parts[2],'command':parts[3]})
 return result

def app_processes(app):return [p for p in processes() if str(app)+'/Contents/' in p['command']]
def pid_alive(pid):return any(p['pid']==pid and not p['state'].startswith('Z') for p in processes())

def cleanup_app(app):
 # Only processes whose current argv identifies this disposable generated bundle.
 rows=app_processes(app)
 for sig,delay in ((signal.SIGTERM,2),(signal.SIGKILL,2)):
  for row in app_processes(app):
   assert row['pid']>1 and row['pid']!=os.getpid()
   try:os.kill(row['pid'],sig)
   except ProcessLookupError:pass
  deadline=time.monotonic()+delay
  while app_processes(app) and time.monotonic()<deadline:time.sleep(.1)
 clean=not app_processes(app)
 record('Bounded app test cleanup',clean,json.dumps({'original_processes':rows,'remaining':app_processes(app)}))
 return clean

def dispatch_open(arguments,timeout,label,step):
 try:
  return subprocess.run(arguments,capture_output=True,text=True,timeout=timeout)
 except subprocess.TimeoutExpired:
  # Persist the stop condition before any optional diagnostic can fail.
  atomic_json(REPORTS/'launch-blocked.json',{'label':label,'step':step,'reason':'Launch Services dispatch timed out; startup state unresolved','argv':arguments})
  raise

def launch_sequence(label,mode,app):
 assert not app_processes(app),'Earlier generated app is still running'
 directory=REPORTS/(label+'-control');assert not directory.exists();directory.mkdir()
 build=json.loads((app/'Contents/Resources/build-record.json').read_text());info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
 fixtures=TEMP/'OpenRacket App Documents';fixtures.mkdir(exist_ok=True)
 a=fixtures/"Cold file λ's.rkt";b=fixtures/"Warm file 中文's.rkt"
 if not a.exists():a.write_text('#lang racket\n;; Cold genuine file event: λ 中文\n(+ 20 22)\n',encoding='utf-8')
 if not b.exists():b.write_text('#lang racket\n;; Warm genuine file event: λ 中文\n(+ 19 23)\n',encoding='utf-8')
 steps=[mode,'warmfile','duplicate'];run_id=label+'-'+secrets.token_hex(6);tokens={s:secrets.token_hex(24) for s in steps}
 config={'schema':1,'run_id':run_id,'mode':mode,'output_dir':str(directory),'app_path':str(app),'native_executable_path':str(app/'Contents/MacOS'/build['native_executable']),'bundle_id':info['CFBundleIdentifier'],'profile_path':str(PROFILE),'memory_mib':'256','files':[str(b)] if mode=='coldempty' else [str(a),str(b)],'step_tokens':tokens}
 config_path=OBSERVER/'observer-config.json'
 if config_path.exists():config_path.unlink()
 atomic_json(config_path,config);config_path.chmod(0o444)
 prior_logs=set(PROFILE.glob('openracket-app-launch.*'));first_pid=None;ok=True;sequence_deadline=time.monotonic()+300
 try:
  for index,step in enumerate(steps):
   target=[] if step=='coldempty' else [a if step=='coldfile' else b]
   arguments=['/usr/bin/open','-a',str(app),*[str(x) for x in target]]
   if time.monotonic()>=sequence_deadline:raise TimeoutError('Independent300s app sequence bound expired')
   started_wall=time.time();started_mono=time.monotonic()
   p=dispatch_open(arguments,min(30,max(.1,sequence_deadline-time.monotonic())),label,step)
   dispatch={'started_unix_seconds':started_wall,'elapsed_seconds':time.monotonic()-started_mono,'argv':arguments,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'method':'actual Launch Services /usr/bin/open -a'}
   print('OPENRACKET_MAC_APP_DISPATCH '+json.dumps({'run_id':run_id,'label':label,'step':step,**dispatch}),flush=True)
   if p.returncode:
    atomic_json(REPORTS/'launch-blocked.json',{'label':label,'step':step,'reason':'Launch Services rejected ordinary launch','dispatch':dispatch})
    path=capture(label+'-'+step+'-failure-diagnostic')
    if path:emit_image(label+'-'+step+'-failure-diagnostic',path)
    raise RuntimeError('Launch Services rejected '+step+': '+p.stderr+'; further launch/relocation attempts blocked pending diagnosis')
   require_default_handler_unchanged(label+'-'+step+'-after-dispatch')
   envelope={'schema':1,'run_id':run_id,'step':step,'token':tokens[step]}
   if index:atomic_json(directory/(run_id+'.'+step+'.sent.json'),{**envelope,'open_exit':0})
   ready=directory/(run_id+'.'+step+'.ready.json');deadline=min(sequence_deadline,time.monotonic()+85)
   while not ready.exists() and time.monotonic()<deadline:time.sleep(.1)
   if not ready.exists():
    if index==0 and not (REPORTS/'launch-blocked.json').exists():
     atomic_json(REPORTS/'launch-blocked.json',{'label':label,'step':step,'reason':'Initial native readiness absent; possible startup dialog remains undismissed'})
    path=capture(label+'-'+step+'-timeout-diagnostic')
    if path:emit_image(label+'-'+step+'-timeout-diagnostic',path)
    raise RuntimeError('No native READY for '+step)
   assert ready.stat().st_size<2*1024*1024,'Unbounded READY refused'
   report=json.loads(ready.read_text());native_passed=report.get('status')=='passed'
   state_error=None;owned=[];observed_pid=None
   try:
    observed_pid=CONTRACT.validate_ready(report,config,step,first_pid)
    owned=[r for r in processes() if r['pid']==observed_pid or r['ppid']==observed_pid or str(app)+'/Contents/' in r['command']]
   except Exception as error:state_error=error
   image_label=label+'-'+step+('' if native_passed else '-failure-diagnostic')
   picture=capture(image_label)
   # ACK immediately after real capture; log transport follows outside the20s window.
   if picture:atomic_json(directory/(run_id+'.'+step+'.ack.json'),{**envelope,'capture_ok':True})
   handler_error=None
   try:require_default_handler_unchanged(label+'-'+step+'-after-ready')
   except Exception as error:handler_error=error
   emit_document(label+'-'+step,'ready.json',report)
   if picture:emit_image(image_label,picture)
   assert picture is not None,'OS screenshot failed; no successful ACK fabricated'
   if handler_error:raise handler_error
   if state_error:raise state_error
   first_pid=observed_pid
   print('OPENRACKET_MAC_APP_PROCESS_TREE '+json.dumps({'run_id':run_id,'label':label,'step':step,'processes':owned}),flush=True)
   assert any(r['pid']==first_pid for r in owned),'Reported native process disappeared before observation'
   assert len([r for r in owned if str(app)+'/Contents/' in r['command']])==1,'Extra bundle bootstrap/native process at stable observation'
   record(label+' '+step+' genuine native identity/file state',True,'pid='+str(first_pid)+'; checks='+str(report.get('checks')))
  complete=directory/(run_id+'.complete.json');deadline=time.monotonic()+15
  while (not complete.exists() or (first_pid and pid_alive(first_pid))) and time.monotonic()<deadline:time.sleep(.1)
  assert complete.exists(),'Final observer completion missing'
  result=json.loads(complete.read_text());assert result['status']=='passed' and result['all_screenshots_acknowledged'] is True and result['same_pid'] is True and result['pid']==first_pid
  assert not pid_alive(first_pid),'Native app did not exit after observer test cleanup'
  emit_document(label,'acceptance.json',result)
  record(label+' observer cleanup complete',True,'Actual process gone; Launch Services exit status is unavailable; normal Quit remains untested')
 except Exception as error:
  if first_pid is None and not (REPORTS/'launch-blocked.json').exists():
   atomic_json(REPORTS/'launch-blocked.json',{'label':label,'reason':'Initial native identity/readiness not established','error':str(error)})
  ok=False;record(label+' native sequence',False,str(error))
 finally:
  if not cleanup_app(app):ok=False
  try:require_default_handler_unchanged(label+'-after-cleanup')
  except Exception as error:ok=False;record(label+' default-handler preservation after cleanup',False,str(error))
  for path in sorted(set(PROFILE.glob('openracket-app-launch.*'))-prior_logs):
   raw=path.read_bytes();assert len(raw)<2*1024*1024,'App log exceeded bounded synthetic diagnostic size'
   print('::group::'+label+' actual app log '+path.name,flush=True);print(raw.decode('utf-8','replace'),flush=True);print('::endgroup::',flush=True)
  config_path.unlink(missing_ok=True)
 return ok

try:
 if PHASE=='prepare':
  # These complete witnesses begin before any builder or native test import.
  witness('baseline','pristine',STOCK)
  command('App CI isolation and byte/mtime witness tests',[sys.executable,ROOT/'scripts/ci/test-app-ci-contract.py'])
  command('App adapter source-contract tests',[sys.executable,ROOT/'scripts/ci/test-mac-app-adapter.py'])
  command('Lossless evidence transport tests',[sys.executable,ROOT/'scripts/ci/test-replay-evidence.py'])
  verify_builder()
  CONTRACT.source_copy(ROOT,PROOF,SOURCE_PIN,155)
  record('Exact tested preview copied to fresh Unicode/apostrophe/spaced source',True,str(PROOF))
  CONTRACT.source_copy(OBSERVER_SOURCE,OBSERVER,OBSERVER_PIN,14,'DELIVERABLE-SHA256.json')
  source_env=env('observer-source');source_env['OPENRACKET_OBSERVER_BASELINE_TOOL']=str(PROOF/'tests/portable-observer/tool.rkt')
  command('Read-only observer portable source contracts',[sys.executable,'-B',OBSERVER/'tests/source-test.py'],source_env)
  command('Deep-copy independent app runtime',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','mac-app'],os.environ.copy(),180)
  clone=STOCK.with_name(STOCK.name+'-mac-app');assert not RUNTIME.exists();RUNTIME.parent.mkdir();clone.rename(RUNTIME)
  for p in RUNTIME.rglob('*'):
   if p.is_symlink():assert not p.resolve().is_relative_to(STOCK)
   elif p.is_file():assert (p.stat().st_dev,p.stat().st_ino)!=((STOCK/p.relative_to(RUNTIME)).stat().st_dev,(STOCK/p.relative_to(RUNTIME)).stat().st_ino)
  witness('baseline','selected-runtime',RUNTIME)
  command('Independent corrected heartbeat native regression',[RUNTIME/'bin/racket','-U','-l','raco','test',HEARTBEAT/'test_heartbeat.rkt'],env('heartbeat'),30)
  original={k:v for k,v in os.environ.items() if k not in CONTRACT.FORBIDDEN and not k.startswith('OPENRACKET_')}
  raw=subprocess.check_output([str(STOCK/'bin/racket'),'-U','-e',"(display (find-system-path 'pref-file))"],env=original,text=True,timeout=30)
  preference=pathlib.Path(raw);assert preference.is_absolute()
  (REPORTS/'original-preference-path.json').write_text(json.dumps(str(preference)))
  witness('baseline','official-user-preferences',preference)
  assert not PROFILE.exists();record('Product profile absent before actual setup',True)
 elif PHASE=='install':
  command('Actual verified preview setup',['/bin/sh',PROOF/'scripts/setup-openracket.sh','--install'],env('setup',True),720)
  command('Actual unchanged preview preflight',['/bin/sh',PROOF/'scripts/launch-openracket.sh','--check'],env('preflight',True),90)
  code,out=command('Actual fresh preview memory ownership status',['/bin/sh',PROOF/'scripts/memory-profile.sh','--status'],env('memory',True),90)
  memory=json.loads(out);assert memory['effective_limit_bytes']==256*1024**2 and memory['ownership_state']=='owned'
  (REPORTS/'memory-profile.json').write_text(json.dumps(memory,indent=2)+'\n')
  try:default_handler('before-build')
  except Exception as error:record('Read-only default-handler native baseline',False,str(error))
  verify_builder();e=env('builder',True);e['OPENRACKET_BUILDER_TEST_SOURCE']=str(PROOF)
  builder_code,_=command('Compile actual Racket-only builder, tests and official launcher generator',raco_prefix()+['make',BUILDER/'make-app.rkt',BUILDER/'test-app.rkt',BUILDER/'make-native-launcher.rkt'],e,180,required=False)
  code,out=command('Twenty actual native Racket builder contract cases',raco_prefix()+['test',BUILDER/'test-app.rkt'],e,180,required=False) if builder_code==0 else (1,'compile failed; tests not run')
  record('All20 actual builder RackUnit cases executed',code==0 and '20 tests passed' in out,'Exact native count required')
  code,out=command('Thirty-two read-only app observer native contract/state cases',raco_prefix()+['test',OBSERVER/'tests/contract-test.rkt',OBSERVER/'tests/observer-state-test.rkt'],e,60,required=False)
  record('All32 actual observer RackUnit cases executed',code==0 and '32 tests passed' in out,'Exact native count required')
  command('Explicit native app observer and Cocoa/default-reader compilation',raco_prefix()+['make',OBSERVER/'tool.rkt',OBSERVER/'cocoa-identity.rkt',OBSERVER/'default-handler.rkt'],e,180,required=False)
  witness('compare','pristine',STOCK);witness('compare','selected-runtime',RUNTIME)
 elif PHASE=='build':
  APP_PARENT.mkdir();e=env('builder',True)
  reference=TEMP/'Native reference';reference.mkdir();reference_app=reference/APP.name
  command('Generate independent untouched official native launcher reference',[RUNTIME/'bin/racket','-U','-A',ADDON,'-R',str(CACHE)+':',BUILDER/'make-native-launcher.rkt',reference_app],e,120)
  ref_info=plistlib.loads((reference_app/'Contents/Info.plist').read_bytes());ref_native=reference_app/'Contents/MacOS'/ref_info['CFBundleExecutable']
  ref_hash=hashlib.sha256(ref_native.read_bytes()).hexdigest()
  command('Actual Racket-only destination app build',['/bin/sh',BUILDER/'build-app.sh','--source',PROOF,'--runtime-root',RUNTIME,'--racket',RUNTIME/'bin/racket','--output',APP,'--theme','dark'],e,180)
  doc=application_manifest(APP)
  record('Product builder passed its same-object native-byte preservation assertion',True,doc['native_sha256'])
  print('OPENRACKET_APP_REFERENCE_COMPARISON '+json.dumps({'reference_sha256':ref_hash,'product_sha256':doc['native_sha256'],'equal':doc['native_sha256']==ref_hash,'independent_generation_determinism_gate':False}),flush=True)
  command('Native plist syntax',['/usr/bin/plutil','-lint',APP/'Contents/Info.plist'],e,30)
  command('Inspect native executable architecture',['/usr/bin/file',doc['native_executable']],e,30)
  for label,args in [('codesign-inspect',['/usr/bin/codesign','-dv','--verbose=4',APP]),('codesign-verify',['/usr/bin/codesign','--verify','--deep','--strict',APP]),('gatekeeper-assessment',['/usr/sbin/spctl','--assess','--type','execute','--verbose=4',APP])]:
   # Inspection status is evidence, not permission to bypass an OS launch denial.
   p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=30)
   print('OPENRACKET_APP_SIGNATURE '+json.dumps({'label':label,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}),flush=True)
  collision=APP_PARENT/'Refuse existing';collision.mkdir()
  paths=[collision/'directory.app',collision/'file.app',collision/'link.app',APP]
  paths[0].mkdir();paths[1].write_text('owned collision witness');paths[2].symlink_to(collision/'missing')
  for n,path in enumerate(paths):
   before=CONTRACT.snapshot(path)
   p=subprocess.run(['/bin/sh',str(BUILDER/'build-app.sh'),'--source',str(PROOF),'--runtime-root',str(RUNTIME),'--racket',str(RUNTIME/'bin/racket'),'--output',str(path)],env=e,capture_output=True,text=True,timeout=30)
   assert p.returncode!=0 and CONTRACT.snapshot(path)==before
   record('Refuse existing output '+str(n),True,p.stderr[-1500:])
  # No app has been launched; inspect only processes whose command names this bundle.
  ps=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,command='],text=True)
  matching=[line for line in ps.splitlines() if str(APP) in line]
  assert not matching,'Unexpected GUI launch during generation: '+repr(matching)
  record('Generation opened no app process',True)
  require_default_handler_unchanged('after-generation')
 elif PHASE=='observer':
  assert not (OBSERVER/'observer-config.json').exists()
  command('Register separate CI-only read-only native app observer',installed_raco_prefix()+['pkg','install','--scope','user','--batch','--no-setup','--deps','fail','--link','--name','openracket-mac-app-observer',OBSERVER],env('observer',True),90)
  command('Compile observer package registration without main runtime writes',installed_raco_prefix()+['setup','--avoid-main','--no-docs','--no-launcher','--no-foreign-libs','--no-install','--no-post-install','--pkgs','openracket-mac-app-observer'],env('observer',True),240)
  expression='(display (collection-file-path "tool.rkt" "openracket-mac-app-observer"))'
  code,out=command('Resolve actual isolated observer collection after registration',[RUNTIME/'bin/racket','-A',ADDON,'-R',str(CACHE)+':','-e',expression],env('observer',True),30)
  resolved=pathlib.Path(out.strip()).resolve();expected=OBSERVER/'tool.rkt'
  assert resolved==expected.resolve()
  expected_sha=json.loads((OBSERVER/'DELIVERABLE-SHA256.json').read_text())['tool.rkt']
  actual_sha=hashlib.sha256(resolved.read_bytes()).hexdigest();assert actual_sha==expected_sha
  record('Registered observer resolves to exact private reviewed source',True,json.dumps({'path':str(resolved),'sha256':actual_sha,'private_addon':str(ADDON)}))
 elif PHASE=='launch':
  launch_sequence('mac-app-coldempty','coldempty',APP)
  if not (REPORTS/'launch-blocked.json').exists():launch_sequence('mac-app-coldfile','coldfile',APP)
  else:record('Further app launches withheld',False,'Ordinary launch refusal/unobserved startup requires diagnosis; no alternate launch attempted')
 elif PHASE=='relocate':
  if (REPORTS/'launch-blocked.json').exists():raise RuntimeError('App relocation launch withheld after prior unresolved launch refusal/startup')
  assert not app_processes(APP),'Cannot relocate a running app'
  before=CONTRACT.snapshot(APP);MOVED.parent.mkdir();APP.rename(MOVED)
  assert CONTRACT.snapshot(MOVED)==before,'Relocation changed bundle bytes/modes/mtime'
  record('App-only relocation retained exact generated bundle',True,str(MOVED))
  launch_sequence('mac-app-relocated','coldfile',MOVED)
 elif PHASE=='verify':
  for label,path in [('pristine',STOCK),('selected-runtime',RUNTIME)]:
   if (TEMP/('mac-app-witness-'+label+'.json')).exists():witness('compare',label,path)
   else:record(label+' witness unavailable',False)
  p=REPORTS/'original-preference-path.json'
  if p.exists():witness('compare','official-user-preferences',pathlib.Path(json.loads(p.read_text())))
  if (REPORTS/'default-handler-before-build.json').exists():require_default_handler_unchanged('after-all')
except Exception as error:
 record(PHASE+' orchestration',False,str(error));raise
finally:print('Mac app evidence: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
