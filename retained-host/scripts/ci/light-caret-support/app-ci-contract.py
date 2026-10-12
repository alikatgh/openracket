"""Pure environment, immutable-tree and source-copy contracts for the Mac app gate."""
import hashlib,json,os,pathlib,shutil,stat
FORBIDDEN={'PYTHONOPTIMIZE','PLTCOLLECTS','PLTCONFIGDIR','PLTLINKS','PLT_COMPILED_FILE_CHECK','PLT_ZO_PATH','PLTDRDEBUG','PLTDRCM','PLTDRPAR','PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}
def environment(parent,racket,home,addon,cache):
    env={k:v for k,v in parent.items() if k not in FORBIDDEN and not k.startswith('OPENRACKET_')}
    env.update(RACKET=str(racket),RACO=str(pathlib.Path(racket).with_name('raco')),PLTUSERHOME=str(home),PLTADDONDIR=str(addon),PLTCOMPILEDROOTS=str(cache)+':',XDG_CACHE_HOME=str(home/'.cache'),PATH='/usr/bin:/bin:/usr/sbin:/sbin')
    return env

def snapshot(root):
    root=pathlib.Path(root)
    def entry(path):
        s=path.lstat();mode=stat.S_IMODE(s.st_mode)
        if path.is_symlink():return ['symlink',mode,s.st_mtime_ns,os.readlink(path)]
        if path.is_dir():return ['directory',mode,s.st_mtime_ns]
        if path.is_file():
            h=hashlib.sha256()
            with path.open('rb') as f:
                for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
            return ['file',mode,s.st_mtime_ns,s.st_size,h.hexdigest()]
        raise ValueError('Unexpected filesystem entry: '+str(path))
    if not root.exists() and not root.is_symlink():return {'.':['absent']}
    result={'.':entry(root)}
    if root.is_dir() and not root.is_symlink():
        for p in sorted(root.rglob('*')):result[str(p.relative_to(root))]=entry(p)
    return result

def source_copy(source,destination,pin,count,manifest_name='CONTENTS-SHA256.json'):
    raw=(source/manifest_name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Source manifest pin mismatch')
    files=json.loads(raw)
    if len(files)!=count or destination.exists():raise ValueError('Source count/destination mismatch')
    for name,digest in files.items():
        path=pathlib.Path(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe manifest path')
        p=source/path
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Member mismatch: '+name)
    destination.mkdir(parents=True)
    for name in files:
        out=destination/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,out)
    shutil.copy2(source/manifest_name,destination/manifest_name)
    return files

def same_snapshot(before,after):
    changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    return {'unchanged':not changed,'changed_count':len(changed),'first_changed_paths':changed[:30],
            'entries':len(after),'tree_sha256':hashlib.sha256(json.dumps(after,sort_keys=True,separators=(',',':')).encode()).hexdigest()}

def validate_ready(report,config,step,prior_pid=None):
    if not isinstance(report,dict):raise ValueError('READY must be an object')
    if type(report.get('schema')) is not int or report['schema']!=1:raise ValueError('READY schema must be exact integer1')
    for key,value in [('schema',1),('run_id',config['run_id']),('step',step),('token',config['step_tokens'][step])]:
        if report.get(key)!=value:raise ValueError('READY envelope mismatch: '+key)
    if report.get('status')!='passed':raise ValueError('Native observer failed: '+str(report.get('error','missing status')))
    for key in ('entrypoint_replaced','fixture_opened_by_observer','handler_replaced','content_or_preferences_changed','complete_app_acceptance'):
        if report.get(key) is not False:raise ValueError('Unexpected observer scope: '+key)
    pid=report.get('pid')
    if isinstance(pid,bool) or not isinstance(pid,int) or pid<=1 or report.get('same_pid') is not True:raise ValueError('Invalid actual native PID')
    if prior_pid is not None and pid!=prior_pid:raise ValueError('Warm dispatch changed process')
    identity=report.get('identity',{})
    if identity.get('same_running_application') is not True or identity.get('same_pid') is not True:raise ValueError('Native application identity changed')
    if identity.get('pid')!=pid or identity.get('running_pid')!=pid:raise ValueError('Native PID sources disagree')
    if pathlib.Path(identity.get('process_image_path','')).resolve()!=pathlib.Path(config['native_executable_path']).resolve():raise ValueError('Actual process image differs')
    for key in ('running_bundle_identifier','main_bundle_identifier'):
        if identity.get(key)!=config['bundle_id']:raise ValueError('Actual bundle ID differs')
    for key in ('running_bundle_path','main_bundle_path'):
        if pathlib.Path(identity.get(key,'')).resolve()!=pathlib.Path(config['app_path']).resolve():raise ValueError('Actual bundle path differs')
    if step=='duplicate' and (report.get('duplicate',{}).get('observed_no_duplicate') is not True or report.get('duplicate',{}).get('handler_receipt_proven') is not False):raise ValueError('Duplicate observation is missing or overclaimed')
    return pid
