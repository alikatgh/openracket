#!/usr/bin/env python3
"""Six genuine native Quit cases with exact product and independently owned profiles."""
import base64,hashlib,importlib.util,json,os,pathlib,platform,shutil,signal,subprocess,sys
if sys.flags.optimize:raise SystemExit('Optimized Python refused')
ROOT=pathlib.Path(__file__).resolve().parents[2];os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket'
assert os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket'
assert platform.system()=='Darwin' and platform.machine()=='arm64'
assert sys.argv[1:] in (['prepare'],['cases'],['verify'])
PHASE=sys.argv[1];TEMP=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
STOCK=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
RUNTIME=TEMP/'OpenRacket Quit Runtime'/'Racket 9.3';RACKET=RUNTIME/'bin/racket'
EXP=ROOT/'experiments/native-quit';BUILDER=ROOT/'experiments/mac-app-builder';READER=ROOT/'experiments/mac-app-observer/default-handler.rkt'
REPORTS=ROOT/'reports/native-quit-ci';REPORTS.mkdir(parents=True,exist_ok=True)
STATE=REPORTS/'results.json';ROWS=json.loads(STATE.read_text()) if STATE.exists() else [];START=len(ROWS)
LAUNCH_BLOCKED=False
CASE_ROOT=TEMP/"OpenRacket Quit Cases λ's";CHECKS=TEMP/'openracket-quit-checks'
SPEC=importlib.util.spec_from_file_location('app_contract',ROOT/'scripts/ci/app-ci-contract.py');CONTRACT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CONTRACT)
sys.path.insert(0,str(ROOT/'performance'));from run import terminate_group
QUIT_PIN='b4560ffb7831a28c51d378d78da96e5695643e01857f8753a8dda0c312a684a4'
SOURCE_PIN='2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'
BUILDER_PIN='b4e5638c409b018a8dec030ea7dafb60291bfffc2645a5d087d7e91d4cfd77ee'
READER_PIN='175e8b8e8d9a74eb275998054764016bc15addc4eeebeb387eb9167bef43d53b'

def record(name,passed,detail=''):
 ROWS.append(dict(name=name,passed=bool(passed),detail=detail));STATE.write_text(json.dumps(ROWS,indent=2)+'\n')
 print('OPENRACKET_NATIVE_QUIT_CI_RESULT '+json.dumps(ROWS[-1]),flush=True)
 lines=['# Genuine native Quit acceptance','', 'Commit: '+os.environ['GITHUB_SHA'],'','| Gate | Outcome | Detail |','|---|---|---|']
 lines+=['| '+r['name']+' | '+('PASS' if r['passed'] else 'FAIL / incomplete')+' | '+str(r['detail']).replace('|',';').replace('\n',' ')+' |' for r in ROWS]
 lines+=['','Three clean/save/discard pairs use fresh stock128 and actual product-owned256 profiles. This is UI/exit coverage, not performance or matched-memory evidence.',
 'Actual native exec-chain child exit0 and complete modal capture ACKs are mandatory. The150s process and20s driver stage bounds remain frozen;270s outer allows separate30s default-handler queries and failure-only cleanup.',
 'Direct native execution is the selected route, not a fallback around Launch Services or Gatekeeper. Unknown startup/security state or default-handler change blocks later launches.',
 'No security settings, file-handler defaults, quarantine, paid compute, artifacts or caches are changed/uploaded. No Finder/Apple-event Quit route is claimed.']
 (REPORTS/'summary.md').write_text('\n'.join(lines)+'\n')

def environment(home):
 return CONTRACT.environment(os.environ,RACKET,home,home/'.local/share/racket',home/'compiled-cache')
def raco(home):return [RACKET,'-A',home/'.local/share/racket','-R',str(home/'compiled-cache')+':','-l','raco','--']
def block(reason):
 global LAUNCH_BLOCKED
 LAUNCH_BLOCKED=True
 p=REPORTS/'launch-blocked.json'
 if not p.exists():p.write_text(json.dumps({'reason':reason})+'\n')
def timeout_cleanup(p,owned_case):
 detail={'exit':124,'failure_only':True,'native_cleanup_error':None,'supervisor_cleanup_error':None,'block_write_error':None}
 out=''
 try:
  try:block('Outer supervisor timeout; later launches require diagnosis')
  except Exception as error:detail['block_write_error']=str(error)
  if owned_case is not None:
   launch=owned_case/'launch.json'
   if launch.exists():
    d=json.loads(launch.read_text());pid=d.get('pid');assert type(pid) is int and pid>1 and pid!=os.getpid()
    ps=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,pgid=,command='],text=True,timeout=3)
    matches=[line.strip().split(None,3) for line in ps.splitlines() if len(line.strip().split(None,3))==4 and line.strip().split(None,3)[0]==str(pid)]
    if matches:
     assert matches[0][1]==str(p.pid) and matches[0][2]==str(pid) and str(owned_case) in matches[0][3],'Recorded native child ownership mismatch'
     os.killpg(pid,signal.SIGKILL);detail['verified_native_group_killed']=pid
 except Exception as error:detail['native_cleanup_error']=str(error)
 finally:
  # The supervisor is always our direct owned child, even if native identity
  # inspection fails. Never signal the unverified native PID in that case.
  try:
   terminate_group(p);out,_=p.communicate(timeout=10)
  except Exception as error:detail['supervisor_cleanup_error']=str(error)
 detail['supervisor_returncode_after_cleanup']=p.poll()
 print('OPENRACKET_QUIT_OUTER_CLEANUP '+json.dumps(detail),flush=True)
 return out,detail

def command(name,args,home=CHECKS,timeout=120,required=True,extra=None,owned_case=None):
 e=environment(home);e.update(extra or {})
 print('\n::group::'+name,flush=True)
 p=subprocess.Popen([str(a) for a in args],env=e,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
 try:out,_=p.communicate(timeout=timeout);code=p.returncode
 except subprocess.TimeoutExpired:
  out,detail=timeout_cleanup(p,owned_case);code=124
  record(name+' failure-only outer cleanup',detail['block_write_error'] is None and detail['native_cleanup_error'] is None and detail['supervisor_cleanup_error'] is None and p.poll() is not None,json.dumps(detail))
 print(out,flush=True);record(name,code==0,'exit='+str(code));print('::endgroup::',flush=True)
 if required and code!=0:raise RuntimeError(name+' failed')
 return code,out

def witness(operation,label,path):
 file=REPORTS/('witness-'+label+'.json');now=CONTRACT.snapshot(path)
 if operation=='baseline':
  assert not file.exists();file.write_text(json.dumps({'root':str(path),'entries':now},sort_keys=True)+'\n');result=CONTRACT.same_snapshot(now,now)
 else:
  before=json.loads(file.read_text());assert before['root']==str(path);result=CONTRACT.same_snapshot(before['entries'],now)
 print('OPENRACKET_QUIT_IMMUTABILITY '+json.dumps(dict(operation=operation,label=label,**result)),flush=True)
 record(label+' full bytes/modes/mtime/symlink '+operation,result['unchanged'],json.dumps(result));return result['unchanged']

def default_handler(label,baseline=False):
 try:
  _,out=command('Read-only .rkt default handler '+label,[RACKET,'-U',READER],CHECKS/'default-reader',30)
  d=json.loads(out);assert type(d['schema']) is int and d['schema']==1 and d['status']=='observed' and d['defaults_changed'] is False and d['extension']=='rkt'
  path=REPORTS/('default-'+label+'.json');assert not path.exists();path.write_text(json.dumps(d,indent=2)+'\n')
  if not baseline:
   before=json.loads((REPORTS/'default-before-generation.json').read_text());assert (before['uti'],before['default_handler'])==(d['uti'],d['default_handler'])
  record('Original default handler preserved '+label,True,json.dumps(d));return d
 except Exception as error:block('Default handler unknown/changed: '+str(error));raise

def exact_sources():
 assert hashlib.sha256((EXP/'FROZEN-NATIVE-ALLOWLIST.json').read_bytes()).hexdigest()==QUIT_PIN
 members=json.loads((EXP/'FROZEN-NATIVE-ALLOWLIST.json').read_text())['files'];assert len(members)==23
 assert set(members)|{'FROZEN-NATIVE-ALLOWLIST.json'}=={str(p.relative_to(EXP)) for p in EXP.rglob('*') if p.is_file()}
 pins=json.loads((EXP/'driver/source-pins.json').read_text());assert len(pins)==12
 assert len({p['module'] for p in pins})==12 and any(p['module']=='mred/private/mrtop.rkt' for p in pins)
 for n,h in members.items():
  p=EXP/n;assert not p.is_symlink() and p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==h,n
 assert hashlib.sha256((BUILDER/'CANDIDATE-SHA256.json').read_bytes()).hexdigest()==BUILDER_PIN
 for n,h in json.loads((BUILDER/'CANDIDATE-SHA256.json').read_text()).items():assert hashlib.sha256((BUILDER/n).read_bytes()).hexdigest()==h,n
 assert hashlib.sha256(READER.read_bytes()).hexdigest()==READER_PIN
 record('Exact frozen Quit/builder/default-reader sources',True,QUIT_PIN)

def document(label,name,value):
 dest=REPORTS/'transport'/label;dest.mkdir(parents=True,exist_ok=True);p=dest/name;assert not p.exists();p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 subprocess.run([sys.executable,str(ROOT/'scripts/ci/emit-replay-evidence.py'),str(p)],check=True,timeout=30)
def evidence(label,root):
 failures=[]
 # Only known bounded synthetic control/evidence files, never package databases.
 paths=[root/n for n in ('case-config.json','launch.json','transcript.json','acceptance.json','supervisor-failure.json','failure-result.json','default-before.json','default-after.json','stock-control-metadata.json')]
 paths+=sorted((root/'evidence').glob('*.json'))
 for p in paths:
  if p.exists():
   try:
    assert p.stat().st_size<=8*1024*1024
    stem=p.stem
    if stem.startswith('quit-') and '.' in stem:stem=stem.split('.',1)[1]
    stem=stem.replace('.','-');document(label+'-'+stem,'summary.json',json.loads(p.read_text()))
   except Exception as error:failures.append(str(p)+': '+str(error))
 for p in sorted((root/'captures').glob('*.png')):
  try:
   data=p.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(data)<=300*1024
   name=label+'-'+p.stem.replace('-1','-one').replace('-2','-two');encoded=base64.b64encode(data).decode()
   print(f'OPENRACKET_SCREENSHOT_BEGIN {name} {len(data)} {hashlib.sha256(data).hexdigest()}',flush=True)
   for i in range(0,len(encoded),3072):print(f'OPENRACKET_SCREENSHOT_DATA {name} {i//3072:04d} {encoded[i:i+3072]}',flush=True)
   print('OPENRACKET_SCREENSHOT_END '+name,flush=True)
  except Exception as error:failures.append(str(p)+': '+str(error))
 log=root/'process.log'
 if log.exists():print('OPENRACKET_QUIT_PROCESS_LOG '+label+'\n'+log.read_text(errors='replace')[-32000:],flush=True)
 record(label+' complete available evidence transport',not failures,json.dumps(failures))

def prepare_case(case,mode):
 label='quit-'+mode+'-'+case;root=CASE_ROOT/label;assert not root.exists();root.mkdir(parents=True)
 if mode=='stock':
  home=root/'profile';home.mkdir();(home/'.local/share/racket').mkdir(parents=True);(home/'compiled-cache').mkdir();(home/'.cache').mkdir()
  app=root/'OpenRacketStockQuitControl.app'
  command(label+' official native stock generation',[RACKET,'-U','-A',home/'.local/share/racket','-R',str(home/'compiled-cache')+':',BUILDER/'make-native-launcher.rkt',app],home,120)
  command(label+' stock no-association metadata proof',[sys.executable,EXP/'scripts/prepare-stock-bundle.py',app],home,30)
 else:
  proof=root/"Preview Source λ's";CONTRACT.source_copy(ROOT,proof,SOURCE_PIN,155);home=proof/'profile';assert not home.exists()
  command(label+' actual unchanged preview setup',['/bin/sh',proof/'scripts/setup-openracket.sh','--install'],home,720)
  command(label+' actual preview preflight',['/bin/sh',proof/'scripts/launch-openracket.sh','--check'],home,90)
  _,out=command(label+' actual memory ownership',['/bin/sh',proof/'scripts/memory-profile.sh','--status'],home,30)
  memory=json.loads(out);assert memory['effective_limit_bytes']==256*1024**2 and memory['ownership_state']=='owned'
  document(label+'-memory','memory-profile.json',memory)
  app=root/'OpenRacket Preview.app'
  command(label+' unchanged Racket-only product build',['/bin/sh',BUILDER/'build-app.sh','--source',proof,'--runtime-root',RUNTIME,'--racket',RACKET,'--output',app,'--theme','dark'],home,180)
  document(label+'-build','summary.json',json.loads((app/'Contents/Resources/build-record.json').read_text()))
 default_handler(label+'-after-generation')
 driver=root/'driver';shutil.copytree(EXP/'driver',driver);assert not (driver/'quit-config.json').exists()
 command(label+' private driver registration',raco(home)+['pkg','install','--scope','user','--batch','--no-setup','--deps','fail','--link','--name','openracket-native-quit-driver',driver],home,90)
 command(label+' scoped driver setup',raco(home)+['setup','--avoid-main','--no-docs','--no-launcher','--no-foreign-libs','--no-install','--no-post-install','--pkgs','openracket-native-quit-driver'],home,240)
 _,out=command(label+' actual driver collection resolution',[RACKET,'-A',home/'.local/share/racket','-R',str(home/'compiled-cache')+':','-e','(display (collection-file-path "tool.rkt" "openracket-native-quit-driver"))'],home,30)
 resolved=pathlib.Path(out.strip()).resolve();assert resolved==(driver/'tool.rkt').resolve() and hashlib.sha256(resolved.read_bytes()).hexdigest()==json.loads((EXP/'FROZEN-NATIVE-ALLOWLIST.json').read_text())['files']['driver/tool.rkt']
 command(label+' explicit native driver contracts compile',raco(home)+['make',driver/'tool.rkt',driver/'contract.rkt',driver/'cocoa-identity.rkt',EXP/'tests/contract-test.rkt'],home,180)
 code,out=command(label+' eight native contract cases',raco(home)+['test',EXP/'tests/contract-test.rkt'],home,60,required=False)
 assert code==0 and out.splitlines().count('8 tests passed')==1,'Exact eight native contracts required'
 command(label+' fresh bounded case configuration',[sys.executable,EXP/'scripts/make-case-config.py','--root',root,'--mode',mode,'--case',case,'--app',app,'--profile',home,'--runtime',RUNTIME],home,30)
 return label,root,home,driver

def run_case(case,mode):
 label='quit-'+mode+'-'+case;root=CASE_ROOT/label;ok=False
 try:
  if LAUNCH_BLOCKED or (REPORTS/'launch-blocked.json').exists():raise RuntimeError('Earlier startup/security/default-handler state requires diagnosis')
  label,root,home,driver=prepare_case(case,mode)
  code,_=command(label+' genuine Quit and natural exit',[sys.executable,EXP/'scripts/run-case.py',root/'case-config.json','--driver',driver,'--default-reader',READER],home,270,required=False,owned_case=root)
  report=root/'acceptance.json'
  if report.exists():
   d=json.loads(report.read_text());assert code==0 and d['status']=='passed' and d['case']==case and d['mode']==mode and d['natural_exit']==0 and d['cleanup_used'] is False and d['default_handler_unchanged'] is True
   assert 0<=d['elapsed_seconds']<150;ok=True
  else:
   transcript=json.loads((root/'transcript.json').read_text()) if (root/'transcript.json').exists() else []
   failed=json.loads((root/'failure-result.json').read_text()) if (root/'failure-result.json').exists() else {}
   ps=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,state=,command='],text=True,timeout=3)
   survivors=[line for line in ps.splitlines() if str(root)+'/OpenRacket' in line and '/Contents/' in line]
   if not transcript or failed.get('cleanup',{}).get('remaining') or survivors:block(label+' unresolved startup or surviving process; no further launch')
  default_handler(label+'-after-case')
 except Exception as error:
  ok=False;record(label+' orchestration',False,str(error))
 finally:
  evidence(label,root);record(label+' final complete natural-Quit acceptance',ok)
 return ok

try:
 if PHASE=='prepare':
  witness('baseline','pristine',STOCK);exact_sources()
  for name in ('test_contract.py','test_source.py','test_stock_bundle.py'):
   command('Quit portable '+name,[sys.executable,'-B',EXP/'tests'/name],extra={'OPENRACKET_QUIT_BASELINE_ROOT':str(ROOT)})
  command('Quit adapter contracts',[sys.executable,'-B',ROOT/'scripts/ci/test-native-quit-adapter.py'])
  command('Deep independent runtime for native Quit',[sys.executable,ROOT/'scripts/ci/copy-independent-runtime.py','mac-app'],timeout=180,extra={'OPENRACKET_CI_STOCK_RACKET':str(STOCK/'bin/racket')})
  clone=STOCK.with_name(STOCK.name+'-mac-app');assert not RUNTIME.exists();RUNTIME.parent.mkdir();clone.rename(RUNTIME)
  witness('baseline','selected-runtime',RUNTIME)
  original={k:v for k,v in os.environ.items() if k not in CONTRACT.FORBIDDEN and not k.startswith('OPENRACKET_')}
  raw=subprocess.check_output([str(STOCK/'bin/racket'),'-U','-e',"(display (find-system-path 'pref-file))"],env=original,text=True,timeout=30)
  prefs=pathlib.Path(raw);assert prefs.is_absolute();(REPORTS/'original-preference-path.json').write_text(json.dumps(str(prefs)));witness('baseline','official-preferences',prefs)
  command('Explicit unchanged generator/default-reader compile',raco(CHECKS)+['make',BUILDER/'make-native-launcher.rkt',BUILDER/'make-app.rkt',READER],timeout=180)
  default_handler('before-generation',baseline=True)
 elif PHASE=='cases':
  assert all(r['passed'] for r in ROWS),'Preparation failure blocks all actual launches'
  CASE_ROOT.mkdir()
  for case in ('clean','save','discard'):
   stock_ok=run_case(case,'stock')
   if stock_ok:run_case(case,'modern-dark')
   else:record('quit-modern-dark-'+case+' stock prerequisite',False,'Corresponding stock case did not pass; modern not run')
  finals=[r for r in ROWS if r['name'].endswith(' final complete natural-Quit acceptance')]
  expected=['quit-'+mode+'-'+case+' final complete natural-Quit acceptance' for case in ('clean','save','discard') for mode in ('stock','modern-dark')]
  accepted=[r['name'] for r in finals]==expected and all(r['passed'] for r in ROWS)
  configs=[json.loads(p.read_text()) for p in CASE_ROOT.glob('*/case-config.json')]
  accepted=accepted and len(configs)==6 and len({c['profile_path'] for c in configs})==6 and len({c['app_path'] for c in configs})==6
  document('quit-matrix','matrix.json',{'accepted':accepted,'expected':expected,'actual':finals,'rows':ROWS})
  record('All six ordered fresh native Quit cases',accepted)
 elif PHASE=='verify':
  for label,path in [('pristine',STOCK),('selected-runtime',RUNTIME)]:
   try:witness('compare',label,path)
   except Exception as error:record(label+' final witness',False,str(error))
  try:
   prefs=pathlib.Path(json.loads((REPORTS/'original-preference-path.json').read_text()));witness('compare','official-preferences',prefs)
  except Exception as error:record('Official preference final witness',False,str(error))
  try:default_handler('after-all')
  except Exception as error:record('Final original default-handler witness',False,str(error))
except Exception as error:
 record(PHASE+' orchestration',False,str(error));raise
finally:print('Native Quit evidence: '+str(REPORTS/'summary.md'),flush=True)
sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)
