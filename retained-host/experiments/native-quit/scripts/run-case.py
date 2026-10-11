#!/usr/bin/env python3
"""One prepared genuine native case. No setup/download/launch fallback occurs here.
Run only on a later authorized free native Mac gate, after preparation and freeze.
"""
import argparse,hashlib,json,math,os,pathlib,platform,plistlib,signal,struct,subprocess,sys,time
import quit_contract as C
if sys.flags.optimize:raise SystemExit('Optimized Python refused')

def fresh_json(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False);f.write('\n')
def atomic_json(path,value):
    C.need(not path.exists() and not path.is_symlink(),'Existing control refused')
    tmp=path.with_name(path.name+'.tmp');fresh_json(tmp,value);tmp.rename(path)
def load_json(path,limit=65536):
    raw=path.read_bytes();C.need(len(raw)<=limit,'Oversized JSON')
    def unique(pairs):
        d={}
        for k,v in pairs:C.need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    def reject_constant(value):raise ValueError('Nonstandard JSON constant refused: '+value)
    def finite_number(value):
        result=float(value);C.need(math.isfinite(result),'Nonfinite JSON number refused');return result
    return json.loads(raw,object_pairs_hook=unique,parse_constant=reject_constant,parse_float=finite_number)
def environment(c):
    forbidden={'PYTHONOPTIMIZE','PLTCOLLECTS','PLTCONFIGDIR','PLTLINKS','PLT_COMPILED_FILE_CHECK','PLT_ZO_PATH','PLTDRDEBUG','PLTDRCM','PLTDRPAR','PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}
    e={k:v for k,v in os.environ.items() if k not in forbidden and not k.startswith('OPENRACKET_')}
    home=C.path(c,'profile_path');addon=home/'.local/share/racket';cache=home/'compiled-cache'
    C.need(addon.is_dir() and cache.is_dir(),'Prepared addon/cache required')
    for p in (home,home/'.local',home/'.local/share',addon,cache):C.need(not p.is_symlink(),'Symlinked managed profile refused')
    e.update(PLTUSERHOME=str(home),PLTADDONDIR=str(addon),PLTCOMPILEDROOTS=str(cache)+':',XDG_CACHE_HOME=str(home/'.cache'),PATH='/usr/bin:/bin:/usr/sbin:/sbin')
    if c['mode']=='stock':e.update(OPENRACKET_UI='stock',OPENRACKET_HOST_THEME='0',OPENRACKET_NATIVE_APPEARANCE='0')
    return e

def launch_argv(c):
    app=C.path(c,'app_path');native=C.path(c,'native_executable_path')
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    C.need(info['CFBundleIdentifier']==c['bundle_id'] and info['CFBundlePackageType']=='APPL','Actual app metadata')
    C.need('CFBundleDocumentTypes' not in info and 'LSEnvironment' not in info,'No association or environment claims')
    C.need(os.access(native,os.X_OK),'Actual native entry executable')
    if c['mode']=='stock':
        C.need((app/'Contents/MacOS'/info['CFBundleExecutable']).resolve()==native,'Stock original native entry')
        p=C.path(c,'profile_path')
        return [str(native),'-A',str(p/'.local/share/racket'),'-R',str(p/'compiled-cache')+':','-l','drracket','--',str(C.path(c,'fixture_path'))]
    C.need(info['CFBundleExecutable']=='OpenRacket-launch','Unchanged product bootstrap entry')
    build=load_json(app/'Contents/Resources/build-record.json')
    C.need(build['source_manifest_sha256']=='2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552','Exact original 0520 product')
    C.need(pathlib.Path(build['runtime_root']).resolve()==C.path(c,'runtime_root'),'Actual selected runtime')
    C.need((pathlib.Path(build['source'])/'profile').resolve()==C.path(c,'profile_path'),'Actual builder-owned profile')
    C.need((app/'Contents/MacOS'/build['native_executable']).resolve()==native,'Actual product native executable')
    C.need(build['self_contained'] is False and build['developer_id_signed'] is False and build['notarized'] is False,'Original tethered unsigned scope')
    entry=app/'Contents/MacOS/OpenRacket-launch';C.need(entry.is_file() and os.access(entry,os.X_OK),'Existing product entry')
    return [str(entry),str(C.path(c,'fixture_path'))]

def processes():
    out=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,state=,command='],text=True,timeout=3)
    rows=[]
    for line in out.splitlines():
        p=line.strip().split(None,3)
        if len(p)==4:rows.append({'pid':int(p[0]),'ppid':int(p[1]),'state':p[2],'command':p[3]})
    return rows
def bundle_processes(c):return [r for r in processes() if str(C.path(c,'app_path'))+'/Contents/' in r['command'] and not r['state'].startswith('Z')]
def capture(path,deadline):
    remaining=deadline-time.monotonic();C.need(remaining>0,'No screenshot time left')
    subprocess.run(['/usr/sbin/screencapture','-x',str(path)],check=True,capture_output=True,timeout=min(15,remaining))
    b=path.read_bytes();C.need(b[:8]==b'\x89PNG\r\n\x1a\n' and 1024<=len(b)<=300*1024,'Bounded actual PNG required')
    w,h=struct.unpack('>II',b[16:24]);C.need(w>=640 and h>=400,'Actual OS screenshot size')
    return {'path':str(path),'sha256':C.digest(b),'bytes':len(b),'width':w,'height':h}
def failure_cleanup(p,c):
    # Called only after a durable failure. No result here can produce acceptance.
    sent=[]
    for sig,seconds in ((signal.SIGTERM,2),(signal.SIGKILL,2)):
        if p.poll() is not None:break
        C.need(p.pid>1 and p.pid!=os.getpid(),'Owned child PID only')
        try:os.killpg(p.pid,sig);sent.append({'process_group':p.pid,'signal':int(sig)})
        except ProcessLookupError:pass
        try:p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:pass
    return {'failure_only':True,'signals':sent,'returncode_after_cleanup':p.poll(),'remaining':bundle_processes(c)}
def default_handler(c,reader):
    e=environment(c);root=C.path(c,'root_dir')/'default-query-profile';root.mkdir(exist_ok=True)
    e.update(PLTUSERHOME=str(root),PLTADDONDIR=str(root/'addon'),PLTCOMPILEDROOTS=str(root/'compiled')+':',XDG_CACHE_HOME=str(root/'.cache'))
    p=subprocess.run([str(C.path(c,'runtime_root')/'bin/racket'),'-U',str(reader)],env=e,capture_output=True,text=True,timeout=30)
    C.need(p.returncode==0,'Read-only default-handler query failed')
    r=json.loads(p.stdout);C.need(r.get('status')=='observed' and r.get('defaults_changed') is False and r.get('extension')=='rkt','Default-handler witness')
    return r

def main():
    parser=argparse.ArgumentParser();parser.add_argument('config',type=pathlib.Path);parser.add_argument('--driver',required=True,type=pathlib.Path);parser.add_argument('--default-reader',required=True,type=pathlib.Path)
    args=parser.parse_args()
    C.need(platform.system()=='Darwin' and platform.machine()=='arm64','Native macOS arm64 only')
    C.need(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket' and os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket','Existing authorized native CI context required')
    c=C.validate_config(load_json(args.config));root=C.path(c,'root_dir');out=C.path(c,'output_dir')
    C.need(not list(out.iterdir()),'Fresh empty output required')
    driver=args.driver.resolve(strict=True);C.need(C.inside(driver,root) and not args.driver.is_symlink(),'Per-case private registered driver required')
    config_path=driver/'quit-config.json';C.need(not config_path.exists(),'Refusing already-configured driver')
    C.need(C.digest(args.default_reader.read_bytes())=='175e8b8e8d9a74eb275998054764016bc15addc4eeebeb387eb9167bef43d53b','Exact accepted read-only default reader')
    argv=launch_argv(c);env=environment(c);C.need(not bundle_processes(c),'Existing bundle process refused')
    captures=root/'captures';captures.mkdir();native_before=C.digest(C.path(c,'native_executable_path').read_bytes())
    handler_before=default_handler(c,args.default_reader);fresh_json(root/'default-before.json',handler_before)
    atomic_json(config_path,c);config_path.chmod(0o444)
    records=[];p=None;failure=None;baseline=None;cleanup_used=False;prior=None;elapsed=None
    start=time.monotonic();deadline=start+150
    try:
        with (root/'process.log').open('x',encoding='utf-8') as log:
            p=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            fresh_json(root/'launch.json',{'argv':argv,'pid':p.pid,'method':'fresh supervised native executable','deadline_seconds':150,'security_fallback':False})
            for stage in C.stages(c):
                ready=C.file_for(c,stage,'ready')
                while not ready.exists():
                    C.need(not (out/'failure.json').exists(),'Driver failed')
                    C.need(p.poll() is None,'Premature process exit')
                    C.need(time.monotonic()<deadline,'Frozen process deadline expired')
                    time.sleep(.025)
                C.need(time.monotonic()<deadline and not (out/'failure.json').exists(),'Late/failed stage refused')
                r=load_json(ready,2*1024*1024)
                if stage=='terminal-response':
                    C.validate_terminal(r,c,p.pid,prior);records.append({'stage':stage,'report':r});break
                h=C.validate_ready(r,c,stage,p.pid,baseline)
                if baseline is None:baseline=h
                owned=bundle_processes(c);C.need(len(owned)==1 and owned[0]['pid']==p.pid,'One actual native bundle process')
                C.need(p.poll() is None,'Actual process live before capture')
                picture=capture(captures/(stage+'.png'),deadline)
                C.need(p.poll() is None and time.monotonic()<deadline,'Process must remain live until ACK')
                atomic_json(C.file_for(c,stage,'ack'),{**C.envelope(c,stage),'capture_ok':True})
                records.append({'stage':stage,'report':r,'capture_ok':True,'ack_written':True,'screenshot_sha256':picture['sha256'],'screenshot':picture,'processes':owned})
                prior=r
            C.need(time.monotonic()<deadline,'No process-exit time remains')
            returncode=p.wait(timeout=deadline-time.monotonic());elapsed=time.monotonic()-start
            C.need(returncode==0,'Natural child exit nonzero')
        text=(root/'process.log').read_text(errors='replace')
        failure_seen=(out/'failure.json').exists() or 'OPENRACKET_QUIT_FAILED' in text or 'OPENRACKET_QUIT_FAILURE_WRITE' in text
        result=C.validate_complete(c,records,p.pid,returncode,elapsed,C.path(c,'fixture_path').read_bytes(),cleanup_used=False,failure_seen=failure_seen,survivors=bundle_processes(c))
        C.need(C.digest(C.path(c,'native_executable_path').read_bytes())==native_before,'Native executable bytes changed')
        handler_after=default_handler(c,args.default_reader);fresh_json(root/'default-after.json',handler_after)
        C.need((handler_before['uti'],handler_before['default_handler'])==(handler_after['uti'],handler_after['default_handler']),'Original default handler changed')
        result['native_sha256']=native_before;result['default_handler_unchanged']=True
        fresh_json(root/'transcript.json',records);fresh_json(root/'acceptance.json',result)
        print('OPENRACKET_QUIT_CASE_RESULT '+json.dumps(result),flush=True)
        return 0
    except BaseException as e:
        failure={'status':'failed','run_id':c['run_id'],'error':str(e),'elapsed_seconds':time.monotonic()-start,'late_success_allowed':False}
        try:fresh_json(root/'supervisor-failure.json',failure)
        except Exception as write_error:
            failure['failure_write_error']=str(write_error)
            print('OPENRACKET_QUIT_DURABLE_REPORT_UNAVAILABLE '+json.dumps(failure),flush=True)
        diagnostic_deadline=time.monotonic()+15
        try:failure['diagnostic_screenshot']=capture(captures/'failure.png',diagnostic_deadline-8)
        except Exception as diagnostic:failure['diagnostic_error']=str(diagnostic)
        if p is not None and p.poll() is None:
            cleanup_used=True
            try:failure['cleanup']=failure_cleanup(p,c)
            except Exception as cleanup_error:failure['cleanup_error']=str(cleanup_error)
        failure['cleanup_used']=cleanup_used
        for destination,value in ((root/'failure-result.json',failure),(root/'transcript.json',records)):
            try:fresh_json(destination,value)
            except Exception as write_error:print('OPENRACKET_QUIT_REPORT_WRITE_FAILED '+str(write_error),flush=True)
        print('OPENRACKET_QUIT_CASE_RESULT '+json.dumps(failure),flush=True)
        return 1
if __name__=='__main__':raise SystemExit(main())
