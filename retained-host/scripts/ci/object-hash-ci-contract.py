"""Pure, fail-closed isolation and argv contract for the diagnostic-only rebuild."""
import hashlib, json, os, pathlib, shutil, stat
P=pathlib.Path
PURPOSES=('object-hash-stock','object-hash-diagnostic')
MANIFEST_SHA256='8fafd9824b2cfeffe3759253ad4e2561b937f76685e9f6c41f5d3bc8f8dfe82c'
HELPER_MANIFEST_SHA256='5542cbbb9d6db661db7d10908137fe355974170d0d59011f75ebc0360b5b878b'
ORIGINAL_CLASS='1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f'
DIAGNOSTIC_CLASS='808a728997c4f085a98fe5c30793c821d9a1097373431addd411370ba2d161d6'
BOUNDS={'inventory':90,'core':600,'setup':1800,'native_compile':300,'coverage':180,'scenario':30,'host':60,'cleanup':30}
SETUP_FLAGS=['--no-user','--no-docs','--no-launcher','--no-foreign-libs','--no-install','--no-post-install','--jobs','1','--fail-fast','-v','-r']

def need(ok, why):
    if not ok: raise ValueError(why)

def sha(path):
    h=hashlib.sha256()
    with P(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def existing(path):
    p=P(path);need(p.is_absolute(),'Absolute existing root required')
    r=p.resolve(strict=True);need(r.is_dir() and r!=P(r.anchor),'Existing directory required')
    return r

def inside(path,root,*,allow_missing=False):
    root=existing(root);p=P(path)
    need(p.is_absolute() and '..' not in p.parts,'Absolute non-traversing path required')
    need(p==root or root in p.parents,'Lexical outside-root path')
    current=root
    for part in p.relative_to(root).parts:
        current/=part
        need(not current.is_symlink(),'Internal symlink refused: '+str(current))
    actual=p.resolve(strict=not allow_missing)
    need(actual==p and (actual==root or root in actual.parents),'Physical outside-root path')
    return p

def new_directory(parent,name):
    parent=existing(parent);need(name and P(name).name==name and name not in ('.','..'),'Single leaf name required')
    p=parent/name;need(not p.exists() and not p.is_symlink(),'Fresh directory required: '+str(p))
    p.mkdir();return p

def independent(roots):
    roots=[existing(p) for p in roots]
    for i,a in enumerate(roots):
        for b in roots[i+1:]:need(a!=b and a not in b.parents and b not in a.parents,'Overlapping roots')
    seen={};counts={}
    for root in roots:
        count=0
        for p in sorted(root.rglob('*')):
            s=p.lstat()
            if stat.S_ISLNK(s.st_mode):
                target=p.resolve(strict=True)
                need(root in target.parents or target==root,'Link escapes owned root: '+str(p))
            elif stat.S_ISREG(s.st_mode):
                key=(s.st_dev,s.st_ino)
                need(s.st_nlink==1,'Mutable hardlink refused: '+str(p))
                need(key not in seen,'Shared mutable inode: '+str(p))
                seen[key]=str(p);count+=1
            else:need(stat.S_ISDIR(s.st_mode),'Special filesystem entry refused')
        counts[str(root)]=count
    return {'roots':counts,'regular_files':len(seen),'shared_inodes':False,'single_link_regular_files':True}

def tree(root):
    root=existing(root);rows={'.':['directory',stat.S_IMODE(root.stat().st_mode)]}
    for p in sorted(root.rglob('*')):
        key=str(p.relative_to(root));s=p.lstat()
        if p.is_symlink(): rows[key]=['symlink',os.readlink(p)]
        elif p.is_file():rows[key]=['file',stat.S_IMODE(s.st_mode),s.st_size,sha(p)]
        elif p.is_dir():rows[key]=['directory',stat.S_IMODE(s.st_mode)]
        else:raise ValueError('Unexpected filesystem entry: '+key)
    return {'root':str(root),'entries':rows,'tree_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}

def verify_frozen(root):
    root=existing(root);manifest=inside(root/'CONTENTS-SHA256.json',root)
    need(sha(manifest)==MANIFEST_SHA256,'Frozen composition identity')
    data=json.loads(manifest.read_text());actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    need(len(actual)==59 and actual==set(data)|{'CONTENTS-SHA256.json'},'Exact 59-file closure required')
    for name,pin in data.items():need(sha(inside(root/name,root))==pin,'Frozen file changed: '+name)
    return data


def verify_helpers(root):
    root=existing(root);manifest=inside(root/'CONTENTS-SHA256.json',root)
    need(sha(manifest)==HELPER_MANIFEST_SHA256,'Exact reviewed helper composition required')
    data=json.loads(manifest.read_text());need(data.get('schema')=='object-hash-helper-contents/v1','Helper manifest schema')
    entries=data['files'];actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    need(actual==set(entries)|{'CONTENTS-SHA256.json'},'Exact helper file closure')
    for name,row in entries.items():
        path=inside(root/name,root);need(type(row['bytes']) is int and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'Changed helper source: '+name)
    return entries

def copy_arm(original,package,temp,purpose):
    need(purpose in PURPOSES,'Bounded object-hash clone purpose required')
    original=existing(original);package=existing(package);temp=existing(temp)
    need(temp in original.parents,'Original must be disposable inside runner temp')
    w=new_directory(temp,purpose);c=w/'runtime';q=w/'probe'
    shutil.copytree(original,c,symlinks=True);shutil.copytree(package,q,symlinks=False)
    for name in ('compiled','profile','quarantine','tmp'):new_directory(w,name)
    inside(c/'collects',c);inside(c/'etc',c);inside(c/'bin/racket',c)
    need(':' not in str(w/'compiled'),'Colon compiled-root path list refused')
    verify_frozen(q)
    for p in q.rglob('*'):need(p.suffix not in ('.zo','.dep'),'Copied package bytecode refused')
    return {'purpose':purpose,'work':str(w),'runtime':str(c),'package':str(q),'compiled':str(w/'compiled'),'profile':str(w/'profile'),'quarantine':str(w/'quarantine'),'initial_before':tree(c)}

def profile(arm,label):
    need(label and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label),'Bounded profile label required')
    w=existing(arm['work']);p=new_directory(w,label)
    for part in ('addon','tmp','config','cache','data'):new_directory(p,part)
    return p

def clean_environment(base):
    # Keep only operating-system essentials. No ambient credentials, Racket,
    # Python, injection, loader, user preference or unrelated experiment state.
    allowed={'PATH','LANG','LC_ALL','LC_CTYPE','TZ','SYSTEMROOT','COMSPEC','TERM','DISPLAY','__CF_USER_TEXT_ENCODING'}
    return {k:v for k,v in base.items() if k in allowed}

def environment(base,arm,p,*,flag=None,collections=None):
    c=existing(arm['runtime']);w=existing(arm['work']);k=inside(P(arm['compiled']),w);p=inside(P(p),w)
    need(k.is_dir() and ':' not in str(k),'Sole physical compiled directory required')
    env=clean_environment(base)
    roots=collections or [str(c/'collects')]
    for r in roots:inside(P(r),c);need(':' not in r,'Collection path-list delimiter')
    env.update(HOME=str(p),PLTUSERHOME=str(p),PLTADDONDIR=str(p/'addon'),TMPDIR=str(p/'tmp'),
               XDG_CONFIG_HOME=str(p/'config'),XDG_CACHE_HOME=str(p/'cache'),XDG_DATA_HOME=str(p/'data'),
               PLTCONFIGDIR=str(c/'etc'),PLTCOMPILEDROOTS=str(k),PLT_ZO_PATH='compiled',
               PATH=str(c/'bin')+':/usr/bin:/bin:/usr/sbin:/sbin')
    if collections is not None:env['PLTCOLLECTS']=':'.join(roots)
    if 'receipt_sha256' in arm:
        pin=arm['receipt_sha256'];need(type(pin) is str and len(pin)==64 and all(c in '0123456789abcdef' for c in pin),'Exact prebuild receipt raw SHA required')
        env['OBJECT_HASH_PREBUILD_RECEIPT_SHA256']=pin
    if flag is not None:need(flag in ('0','1'),'Exact diagnostic flag');env['OPENRACKET_OBJECT_HASH_PROBE']=flag
    return env

def prefix(arm,p):
    c=P(arm['runtime']);return [str(c/'bin/racket'),'-X',str(c/'collects'),'-G',str(c/'etc'),'-A',str(P(p)/'addon'),'-U','-R',arm['compiled']]

def compile_commands(arm,p,helpers):
    q=P(arm['package']);native=sorted(q.glob('native/**/*.rkt'));stock=sorted(q.glob('vendor/host/**/*.rkt'))
    need(len(native)==13 and len(stock)==10,'Exact native compile closure changed')
    for x in native+stock:inside(x,q)
    r=prefix(arm,p)
    return [('core',r+['-l','setup','--','--boot',str(P(helpers)/'core-first.rkt'),arm['compiled']]),
            ('setup',r+['-l','setup','--',*SETUP_FLAGS]),
            ('native_compile',r+['-l','raco','--','make','-v',*[str(x) for x in native+stock]])]

def accept_overlay(arm,after):
    before=arm['initial_before'];entries=before['entries'];actual=after['entries']
    need(after['root']==before['root'] and set(actual)==set(entries),'Overlay tree shape changed')
    core='collects/racket/private/class-internal.rkt';need(core in entries,'Required core absent from clone baseline')
    for name,row in entries.items():
        if name==core and arm['purpose']=='object-hash-diagnostic':
            value=actual[name]
            need(row[0]=='file' and row[3]==ORIGINAL_CLASS and value[0]=='file' and value[1]==row[1] and value[3]==DIAGNOSTIC_CLASS,'Exact one-file diagnostic overlay required')
        else:need(actual[name]==row,'Unexpected overlay input change: '+name)
    arm['immutable_before']=after
    return True

def old_product(name,metadata):
    return name.endswith(('.zo','.dep')) or name in metadata or ('compiled' in P(name).parts and name.endswith('.rktd'))

def quarantine(arm,persist=lambda state:None):
    need('quarantine_state' not in arm,'Quarantine may be attempted only once')
    state={'schema':'object-hash-quarantine/v1','phase':'in-progress','moves':[]};arm['quarantine_state']=state
    persist({'event':'phase','phase':state['phase']}) # Durable intent precedes each move.
    c=existing(arm['runtime']);dest=existing(arm['quarantine']);need(not any(dest.iterdir()),'Fresh quarantine required')
    need(not any(P(arm['compiled']).iterdir()),'Rebuilt root was not initially empty')
    metadata={str(P(path).relative_to(c)) for path in arm.get('metadata_paths',[])}
    for p in sorted(c.rglob('*')):
        if p.is_symlink():
            need(c in p.resolve(strict=True).parents,'Old product link outside clone')
            need(not old_product(str(p.relative_to(c)),metadata),'Linked old product refused')
            continue
        if not p.is_file():continue
        relative=str(p.relative_to(c));compiled='compiled' in P(relative).parts
        if old_product(relative,metadata):
            inside(p,c);st=p.stat();need(st.st_nlink==1,'Shared old product refused')
            target=dest/p.relative_to(c);inside(target,dest,allow_missing=True)
            row={'path':str(p),'quarantine':str(target),'bytes':st.st_size,'sha256':sha(p),'device':st.st_dev,'inode':st.st_ino,'before':['file',stat.S_IMODE(st.st_mode),st.st_size,sha(p)],'state':'intent'}
            state['moves'].append(row);persist({'event':'intent','move':dict(row)})
            target.parent.mkdir(parents=True,exist_ok=True);p.rename(target)
            row['state']='moved';persist({'event':'moved','path':row['path']})
        elif compiled and p.suffix in ('.so','.dylib','.dll'):
            raise ValueError('Compiled native-extension product needs explicit source/loader review: '+str(p))
    need(not any(p.suffix in ('.zo','.dep') for p in c.rglob('*') if p.is_file() or p.is_symlink()),'Reachable old bytecode survived')
    state['phase']='complete';persist({'event':'phase','phase':state['phase']})
    return state['moves']

def source_unchanged(before,after,arm):
    c=existing(arm['runtime']);dest=existing(arm['quarantine'])
    need(before['root']==after['root']==str(c),'Clone witness root mismatch')
    state=arm.get('quarantine_state',{'phase':'pre-quarantine','moves':[]})
    phase=state['phase'];need(phase in ('pre-quarantine','in-progress','complete'),'Unknown quarantine witness phase')
    if phase=='pre-quarantine':
        need(before==after,'Pre-quarantine clone differs from its exact baseline')
        need(not state['moves'] and not any(dest.iterdir()),'Unexpected pre-quarantine output')
        need(not any(P(arm['compiled']).iterdir()),'Unexpected pre-build compiled output')
        return True
    if phase=='in-progress':need(not any(P(arm['compiled']).iterdir()),'Unexpected partial-quarantine compiled output')
    metadata={str(inside(P(path),c,allow_missing=True).relative_to(c)) for path in arm.get('metadata_paths',[])}
    moved=set();recorded=set();targets=set()
    for row in state['moves']:
        source=inside(P(row['path']),c,allow_missing=True);target=inside(P(row['quarantine']),dest,allow_missing=True)
        name=str(source.relative_to(c));need(name not in recorded,'Duplicate quarantine move');recorded.add(name)
        need(target==dest/name and old_product(name,metadata),'Unexpected quarantine move destination/type')
        need(row['before']==before['entries'].get(name) and row['before'][0]=='file' and row['bytes']==row['before'][2] and row['sha256']==row['before'][3],'Quarantine move does not match baseline')
        need(row['state'] in ('intent','moved'),'Unknown quarantine move state')
        targets.add(name)
        if target.exists():
            need(target.is_file() and (not source.exists() or (phase=='complete' and name in metadata and row['state']=='moved')),'Quarantine move has conflicting source/target')
            st=target.stat();need(st.st_nlink==1 and [st.st_dev,st.st_ino]==[row['device'],row['inode']],'Quarantined inode identity changed')
            need(['file',stat.S_IMODE(st.st_mode),st.st_size,sha(target)]==row['before'],'Quarantined bytes/mode changed')
            moved.add(name)
        else:need(row['state']=='intent' and after['entries'].get(name)==row['before'],'Recorded quarantine move disappeared')
    quarantine_tree=tree(dest)['entries']
    for name,row in quarantine_tree.items():
        if name=='.':continue
        if row[0]=='directory':need(any(P(name) in P(path).parents for path in targets),'Unrecorded quarantine directory')
        else:need(name in moved and row==before['entries'][name],'Unrecorded quarantine product')
    if phase=='complete':
        required={name for name,row in before['entries'].items() if row[0]=='file' and old_product(name,metadata)}
        need(recorded==moved==required,'Completed quarantine must account for every baseline product')
    def metadata_file(name,row):
        need(row[0]=='file','Metadata destination must remain a regular file: '+name)
        path=inside(c/name,c);need(path.stat().st_nlink==1,'Metadata writable inode sharing refused: '+name)
    for name,row in before['entries'].items():
        if phase=='complete' and name in metadata:
            if name in after['entries']:metadata_file(name,after['entries'][name])
            continue
        if name in moved:need(name not in after['entries'],'Quarantined input reappeared: '+name);continue
        need(after['entries'].get(name)==row,'Installed immutable input changed: '+name)
    for name,row in after['entries'].items():
        if phase=='complete' and name.endswith(('.zo','.dep')) and row[0]!='directory':raise ValueError('Module bytecode outside sole rebuilt root: '+name)
        if name not in before['entries']:
            need(phase=='complete','Unexpected output during partial quarantine: '+name)
            if row[0]=='directory':need(any(P(name) in P(path).parents for path in metadata),'Directory output outside inventory-declared metadata ancestors: '+name)
            else:need(name in metadata,'Output outside inventory-declared metadata path: '+name);metadata_file(name,row)
    return True

def config_path(raw,canonical,roots):
    raw=P(raw);canonical=P(canonical)
    need(raw.is_absolute() and canonical.is_absolute(),'Absolute config path required')
    matches=[root for root in roots if raw==root or root in raw.parents]
    need(len(matches)==1,'Raw config path does not begin in one owned root')
    root=matches[0];current=root
    for part in raw.relative_to(root).parts:
        if part=='..':
            need(current!=root,'Parent-relative config escapes owned root');current=current.parent
        elif part!='.':
            current/=part;need(not current.is_symlink(),'Raw config traverses internal symlink')
    need(current==canonical and current.resolve(strict=False)==canonical,'Canonical/raw config resolution mismatch')
    inside(canonical,root,allow_missing=True)
    return canonical

def config_identity(raw,roots,*,allow_missing=True,directory=False):
    need(type(raw) is str and bool(raw),'Config path string required')
    canonical=P(os.path.normpath(raw))
    result=config_path(raw,canonical,roots)
    owners=[root for root in roots if result==root or root in result.parents]
    need(len(owners)==1,'Config path owner mismatch')
    inside(result,owners[0],allow_missing=allow_missing)
    if directory:need(result.is_dir(),'Required config directory missing')
    return result

def validate_config(value,arm,p):
    need(value.get('schema')=='object-hash-config/v1','Effective config schema')
    c=existing(arm['runtime']);q=existing(arm['package']);w=existing(arm['work']);k=existing(arm['compiled']);h=existing(w/'ci');p=existing(p)
    expected={'runtime_root':c,'probe_root':q,'helper_root':h,'compiled_root':k,'profile_root':p}
    for key,path in expected.items():need(value.get(key)==str(path),'Actual config root mismatch: '+key)
    need(value.get('compiled_roots')==[str(k)] and value.get('compiled_subdirs')==[],'Initial -c sole-root config required')
    need(value.get('unclassified_config')==[],'Unclassified configuration refused')
    resolved=value.get('resolved_class_source',{});target=c/'collects/racket/private/class-internal.rkt'
    expected=ORIGINAL_CLASS if arm['purpose']=='object-hash-stock' else DIAGNOSTIC_CLASS
    need(resolved.get('path')==str(target) and resolved.get('sha256')==expected and sha(target)==expected,'Actual class resolution/pin mismatch')
    roots=value.get('collections');need(type(roots) is list and roots,'Complete main/extra collection paths required')
    roots=[str(config_identity(root,(c,),allow_missing=False,directory=True)) for root in roots]
    need(str(c/'collects') in roots,'Complete main/extra collection paths required')
    def owned(path,allow_missing=True):
        return config_identity(path,(c,p,k),allow_missing=allow_missing)
    need(type(value.get('paths')) is list and value['paths'],'Effective path inventory required')
    for row in value['paths']:
        need(row.get('role') in ('source','config','link','metadata','library','write'),'Path classification')
        config_path(row.get('raw_path',row['path']),row['path'],(c,p,k))
        owned(row['path'])
        if row['role']=='source':need(P(row['path'])==c or c in P(row['path']).parents or p in P(row['path']).parents,'Source destination outside clone/fresh profile')
    for row in value.get('collection_links',[]):
        if row['kind']=='file':owned(row['path'])
        elif row['kind']=='table':
            for entry in row['entries']:
                for path in entry['paths']:config_identity(path,(c,))
        else:need(row['kind']=='splice','Unknown collection link kind')
    for row in value.get('links',[]):
        owned(row['path'])
        for link in row['ordinary']:config_identity(link['path'],(c,))
        for path in row['roots']:config_identity(path,(c,))
        for entry in row.get('all_entries',[]):config_identity(entry['path'],(c,))
    for row in value.get('config_files',[]):owned(row['path'])
    return roots

def validate_receipts(value,arm,mode):
    need(value.get('schema')=='object-hash-rebuild-receipts/v1' and value.get('mode')==mode,'Rebuild receipt mode/schema')
    c=existing(arm['runtime']);q=existing(arm['package']);k=existing(arm['compiled']);h=existing(P(arm['work'])/'ci')
    for name,path in (('runtime_root',c),('probe_root',q),('helper_root',h),('compiled_root',k)):need(value.get(name)==str(path),'Actual receipt root mismatch: '+name)
    need(value.get('registered_and_static_closure_complete') is True,'Required known graph prebuild incomplete')
    need(value.get('arbitrary_dynamic_graph_proven') is False and value.get('child_place_dynamic_audit_complete') is False,'Exact dynamic-coverage limitation required')
    need(value.get('runtime_audit_scope')=='initial-place-and-inheriting-threads','Host-place audit scope')
    modules=value.get('modules');need(type(modules) is list and modules,'Source/zo/dep rows required');source_hashes={};seen=set()
    def record(row,roots):
        need(type(row) is dict and set(row)=={'path','size','sha256'},'File receipt shape')
        p=P(row['path']);owners=[r for r in roots if r in p.parents];need(len(owners)==1,'Receipt file outside exact roots')
        inside(p,owners[0]);need(p.is_file() and p.stat().st_nlink==1,'Nonshared physical receipt file required')
        need(type(row['size']) is int and row['size']>=0 and p.stat().st_size==row['size'] and sha(p)==row['sha256'],'Actual receipt bytes/size/hash mismatch')
        return p
    for row in modules:
        need(row['nominal_path'] not in seen,'Duplicate module receipt');seen.add(row['nominal_path'])
        source=record(row['source'],(c,q,h));zo=record(row['bytecode'],(k,));dep=record(row['dependency'],(k,))
        need(zo.suffix=='.zo' and dep==zo.with_suffix('.dep'),'Exact rebuilt .zo/.dep pair')
        need(source.stat().st_mtime<=zo.stat().st_mtime,'Source newer than rebuilt product')
        source_hashes[str(source)]=row['source']['sha256']
    for row in value.get('external_files',[]):record(row,(c,q,h))
    for row in value.get('primitives',[]):need(row.get('classification')=='predefined-vm-module' and row.get('module_predefined') is True,'Unclassified primitive dependency')
    expected=ORIGINAL_CLASS if arm['purpose']=='object-hash-stock' else DIAGNOSTIC_CLASS
    need(source_hashes.get(str(c/'collects/racket/private/class-internal.rkt'))==expected,'Class source-backed rebuilt receipt missing')
    if mode=='full':
        pins=json.loads((q/'RUNTIME-PINS.json').read_text())
        for module,pin in pins.items():
            expected=ORIGINAL_CLASS if module=='racket/private/class-internal' and arm['purpose']=='object-hash-stock' else pin
            matches=[p for p,digest in source_hashes.items() if p.startswith(str(c)+'/') and p.endswith('/'+module+'.rkt') and digest==expected]
            need(len(matches)==1,'Required pinned runtime source missing/ambiguous: '+module)
        for path in list(q.glob('native/**/*.rkt'))+list(q.glob('vendor/host/**/*.rkt'))+list(h.glob('*.rkt')):need(str(path) in source_hashes,'Required native/helper prebuild missing: '+str(path))
        need(type(value.get('registrations')) is list and value['registrations'],'Actual installed tool registrations required')
        need(value.get('online_handler_registry_complete') is False and value.get('live_registry_observed') is False,'Explicit internal-unit live registry limitation required')
        workers=value.get('worker_roots',[]);need(type(workers) is list and len(workers)==1 and workers[0].get('module')=='drracket/private/expanding-place' and workers[0].get('export')=='start' and workers[0].get('source') in source_hashes,'Pinned known expanding-place/start required')
    return True
