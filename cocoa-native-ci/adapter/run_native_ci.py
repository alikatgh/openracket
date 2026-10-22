#!/usr/bin/env python3
"""Public source input admission, compile-first, then unchanged full gate.

No native action is permitted on Linux. Final witnesses and transport are stdlib
filesystem work and run independently of runtime/helper loading or launch state.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, platform, plistlib, shutil, stat, sys, time, tomllib, types
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SOURCE=BASE/'source'
sys.path.insert(0,str(HERE))
from bootstrap import bootstrap, durable, sha, physical
SUPERVISOR_SHA='d8fe825d66cc2d710f5e6759cec355c941627cd4cb93995ab7a479292e2fbc81'
PUBLIC_INPUT_PINS={'PUBLIC-SOURCE.json': '3504ad66c86bf1bab94b640a71bd6ccf317151eda429007a3042cba788580410', 'SOURCE-BUNDLE.json': 'ae8e10ee61f4a5bdefeef38dd2730fc0cc560ed590c303ca84c4b08cfe05a4ec', 'SOURCE-PARTS.json': '3941d99d0a48cdfceb0de0a99000090b9d4458cce98aea65ea6517b07d028996'}
MANIFEST_SHA=PUBLIC_INPUT_PINS['PUBLIC-SOURCE.json']
SMOKE_MARKER='native shell, real Run/interaction, diagnostic navigation, Racket coloring, language bracket and indentation actions smoke passed (AX/IME/performance/parity pending)'
GATE_MARKER='Mandatory bounded build + engine protocol + native shell smoke passed.'

def load_exact(path,name,digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Pinned module changed: '+path.name)
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__);return module

def load_supervisor():return load_exact(SOURCE/'ci/supervisor/owned_process_supervisor.py','cocoa_owned_supervisor',SUPERVISOR_SHA)

def public_inputs():
    """Admit only pinned distributed inputs; private ancestry is not required."""
    values={}
    for name,digest in PUBLIC_INPUT_PINS.items():
        path=BASE/name
        if path.is_symlink() or not path.is_file() or sha(path)!=digest:
            raise ValueError('Public input manifest hash/type mismatch: '+name)
        values[name]=json.loads(path.read_bytes())
    manifest=values['PUBLIC-SOURCE.json']
    if set(manifest)!={'schema','files'} or manifest['schema']!='openracket-public-source/v1':
        raise ValueError('Public source manifest schema')
    from source_bundle import members
    rows=members(manifest)
    pin=values['SOURCE-BUNDLE.json'];parts=values['SOURCE-PARTS.json']
    if pin['members']!=len(rows) or pin['raw_file_bytes']!=sum(r['bytes'] for r in rows):
        raise ValueError('Public source member accounting')
    if pin['sha256']!=parts['sha256'] or pin['bytes']!=parts['bytes']:
        raise ValueError('Public source envelope binding')
    return manifest,pin,parts

def projection():
    manifest,_,_=public_inputs()
    selected=manifest['files']
    source=SOURCE;actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!={r['path'] for r in selected}:raise ValueError('Extra/missing projection source member')
    verify_sources(source,selected,immutable=True)
    return manifest

def verify_sources(root,records,*,immutable=False):
    for row in records:
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe source member')
        path=root/rel
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise ValueError('Source changed/missing: '+str(rel))
        if immutable and stat.S_IMODE(path.stat().st_mode)!=row['mode']:raise ValueError('Immutable source mode changed: '+str(rel))
    if immutable:
        for path in [root]+[p for p in root.rglob('*') if p.is_dir()]:
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode)!=0o555:raise ValueError('Immutable source directory mode changed')

def workcopy(destination,manifest):
    if destination.exists() or destination.is_symlink():raise ValueError('Fresh projection workcopy required')
    destination.mkdir(mode=0o700)
    for row in manifest['files']:
        path=destination/row['path'];path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        shutil.copyfile(SOURCE/row['path'],path);path.chmod((row['mode']&0o777)|0o600)
    (destination/'evidence').mkdir(mode=0o700)
    verify_sources(destination,manifest['files'])
    return {'schema':'openracket-projection-workcopy/v1','source_manifest_sha256':MANIFEST_SHA,
            'projection_sha256':sha(BASE/'PUBLIC-SOURCE.json'),'verified_members':len(manifest['files']),
            'full_archive_prepare_workcopy_invoked':False,'production_bytes_changed':False,'destination':str(destination)}

def tree(root):
    root=physical(root);root_info=root.stat();entries={'.':['directory',stat.S_IMODE(root.stat().st_mode)]}
    for path in sorted(root.rglob('*')):
        key=path.relative_to(root).as_posix();info=path.lstat()
        if path.is_symlink():entries[key]=['symlink',os.readlink(path)]
        elif path.is_file():entries[key]=['file',stat.S_IMODE(info.st_mode),info.st_size,sha(path)]
        elif path.is_dir():entries[key]=['directory',stat.S_IMODE(info.st_mode)]
        else:raise ValueError('Special runtime filesystem member')
    encoded=json.dumps(entries,sort_keys=True,separators=(',',':')).encode()
    if (root.stat().st_dev,root.stat().st_ino)!=(root_info.st_dev,root_info.st_ino):raise ValueError('Runtime root replaced during scan')
    return {'schema':'openracket-runtime-tree/v1','root':str(root),'root_device':root_info.st_dev,'root_inode':root_info.st_ino,'entries':entries,'tree_sha256':hashlib.sha256(encoded).hexdigest()}

def compare_tree(before,root,*,require_identity=False):
    if require_identity and (root.stat().st_dev,root.stat().st_ino)!=(before['root_device'],before['root_inode']):raise ValueError('Original runtime root replaced')
    after=tree(root);changed=[k for k in set(before['entries'])|set(after['entries']) if before['entries'].get(k)!=after['entries'].get(k)]
    return after,{'unchanged':not changed,'before_tree_sha256':before['tree_sha256'],'after_tree_sha256':after['tree_sha256'],'changed_count':len(changed),'changed_paths':sorted(changed),'changed_entries':[{'path':k,'before':before['entries'].get(k),'after':after['entries'].get(k)} for k in sorted(changed)]}

def profile(root,runtime,helper,digest,sdk,developer,rust):
    root.mkdir(mode=0o700)
    for name in ('home','tmp','addon','cargo'): (root/name).mkdir(mode=0o700)
    # Never forward repository tokens, loader injection variables, or user config.
    env={'PATH':os.environ['PATH'],'HOME':str(root/'home'),'TMPDIR':str(root/'tmp')+'/',
         'PLTADDONDIR':str(root/'addon'),'CARGO_HOME':str(root/'cargo'),'CARGO_NET_OFFLINE':'true',
         'RACKET_BIN':str(runtime/'bin/racket'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONOPTIMIZE':'',
         'LC_ALL':'C','LANG':'C','DEVELOPER_DIR':str(developer),'SDKROOT':str(sdk),
         'OPENRACKET_PROCESS_HELPER':str(helper),'OPENRACKET_PROCESS_HELPER_SHA256':digest,
         'OPENRACKET_TEST_PROCESS_HELPER':str(helper),'OPENRACKET_TEST_PROCESS_HELPER_SHA256':digest}
    env.update(RUSTUP_HOME=str(rust['root']),RUSTC=str(rust['rustc']),RUSTDOC=str(rust['rustdoc']))
    env['PATH']=str(rust['cargo'].parent)+':'+env['PATH']
    return env

def read_log(receipt,suffix):
    record=receipt.get('logs',{}).get(suffix,{})
    if not record.get('sha256') or type(record.get('bytes')) is not int or not 0<=record['bytes']<=64*1024*1024:raise ValueError('Bounded verified log unavailable: '+suffix)
    fd=os.open(receipt['paths'][suffix],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size!=record['bytes']:raise ValueError('Log type/size changed')
        raw=stream.read(record['bytes']+1)
    if len(raw)!=record['bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Log bytes changed')
    return raw

def command(supervisor,root,name,argv,cwd,env,timeout,*,marker=None):
    gate=root/'launch-state.json'
    if gate.exists() and json.loads(gate.read_bytes()).get('safe_to_continue') is not True:raise RuntimeError('Global launch latch blocks '+name)
    durable(gate,{'phase':name,'safe_to_continue':False,'began_ns':time.time_ns()},replace=gate.exists())
    # The latch is set before every launch, including non-engine commands.
    receipt=supervisor.run(argv,cwd=str(cwd),env=env,label=name,timeout=timeout,logs_dir=str(root/'reports'/name))
    passed=receipt.get('outcome')=='success' and receipt.get('safe_to_continue') is True
    replay_error=None
    try:stdout=read_log(receipt,'stdout.log');stderr=read_log(receipt,'stderr.log')
    except (OSError,ValueError) as error:stdout=b'';stderr=('Bounded log replay refused: '+str(error)+'\n').encode();replay_error=str(error);passed=False
    if marker is not None:passed=passed and marker.encode() in stdout
    row={'schema':'openracket-cocoa-phase/v1','phase':name,'passed':passed,'timeout_seconds':timeout,'receipt':receipt,'required_marker':marker,'replay_error':replay_error}
    durable(root/'reports'/(name+'.json'),row)
    # Compiler/error feedback is emitted before later phases, even when failing.
    sys.stdout.buffer.write(stdout);sys.stdout.flush();sys.stderr.buffer.write(stderr);sys.stderr.flush()
    print('OPENRACKET_COCOA_PHASE '+json.dumps({'phase':name,'passed':passed,'outcome':receipt.get('outcome'),'returncode':receipt.get('returncode'),'native_acceptance':'pending'}),flush=True)
    if not passed:raise RuntimeError(name+' failed; later native launches blocked, nested groups are not assumed quiet')
    durable(gate,{'phase':name,'safe_to_continue':True,'receipt_sha256':sha(root/'reports'/(name+'.json'))},replace=True)
    return receipt

def setup(root):
    if sys.platform!='darwin' or sys.version_info<(3,13) or not all(hasattr(os,x) for x in ('waitid','WNOWAIT','WEXITED')):raise ValueError('Native Darwin Python>=3.13 with waitid/WNOWAIT required')
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!='alikatgh/openracket':raise ValueError('Reviewed public GitHub job required')
    if os.environ.get('GITHUB_REF')!='refs/heads/prototype/retained-drracket':raise ValueError('Reviewed branch required')
    temp=Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    if root.exists() or root.is_symlink() or root.parent!=temp:raise ValueError('Fresh direct RUNNER_TEMP child required')
    root.mkdir(mode=0o700);(root/'reports').mkdir(mode=0o700)
    original=Path(os.environ['OPENRACKET_CI_INSTALL']).resolve(strict=True)
    if not original.is_relative_to(temp) or original==temp:raise ValueError('Official disposable runtime must be beneath RUNNER_TEMP')
    baseline=tree(original);durable(root/'reports/original-runtime-before.json',baseline)
    durable(root/'context.json',{'original_runtime':str(original),'source_projection_sha256':sha(BASE/'PUBLIC-SOURCE.json')})
    return original,baseline

def run(root):
    global SOURCE
    original,baseline=setup(root)
    from source_bundle import extract_parts
    SOURCE=root/'immutable-source'
    try:
        manifest,pin,parts=public_inputs()
        materialized=extract_parts(BASE/'source-parts',parts,manifest,pin,SOURCE,root/'source-envelope.xz')
        durable(root/'reports/materialization.json',materialized)
        module=load_supervisor()
    except BaseException:
        witness(root,'materialization-failure');raise
    supervisor=None
    summary={'schema':'openracket-cocoa-native-summary/v1','native_acceptance':'pending','screenshots':'deferred in first compile-first adapter','phases':{}}
    with module.interruption_guard():
        try:
            manifest=projection();durable(root/'reports/projection-verified.json',{'sha256':sha(BASE/'PUBLIC-SOURCE.json'),'members':len(manifest['files'])})
            developer=physical('/Applications/Xcode_16.4.app/Contents/Developer')
            if os.environ.get('DEVELOPER_DIR')!=str(developer):raise ValueError('Exact DEVELOPER_DIR required before bootstrap')
            compiler=(developer/'Toolchains/XcodeDefault.xctoolchain/usr/bin/clang').resolve(strict=True)
            sdk=(developer/'Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk').resolve(strict=True)
            sdk_settings=sdk/'SDKSettings.json'
            metadata=json.loads(sdk_settings.read_bytes()) if sdk_settings.exists() else plistlib.loads((sdk/'SDKSettings.plist').read_bytes())
            version=metadata.get('Version')
            if not isinstance(version,str) or not version:raise ValueError('SDK version missing')
            bootstrap_root=root/'reports/bootstrap';bootstrap_root.mkdir(mode=0o700)
            bootstrap_env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(root),'TMPDIR':str(root)+'/',
                           'DEVELOPER_DIR':str(developer),'SDKROOT':str(sdk),'LC_ALL':'C','LANG':'C'}
            helper,digest,receipt=bootstrap(module,SOURCE/'ci/supervisor/darwin_process_inventory.c',compiler,sdk,None,bootstrap_root,bootstrap_env)
            summary['phases']['helper_bootstrap']='passed'
            supervisor=module.Supervisor(process_helper=str(helper),process_helper_sha256=digest)
            clone=root/'runtime';shutil.copytree(original,clone,symlinks=True)
            clone_after=tree(clone)
            if clone_after['entries']!=baseline['entries']:raise ValueError('Official runtime clone differs')
            durable(root/'reports/runtime-clone.json',{'verified':True,'tree_sha256':clone_after['tree_sha256']})
            rust_root=Path(os.environ.get('RUSTUP_HOME',str(Path.home()/'.rustup'))).resolve(strict=True)
            rust_settings=rust_root/'settings.toml';rust_meta=tomllib.loads(rust_settings.read_text())
            toolchain=os.environ.get('RUSTUP_TOOLCHAIN',rust_meta.get('default_toolchain',''))
            if not toolchain or '/' in toolchain or toolchain in ('.','..'):raise ValueError('Installed Rust toolchain selection missing/unsafe')
            tools=(rust_root/'toolchains'/toolchain/'bin').resolve(strict=True)
            if not tools.is_relative_to(rust_root):raise ValueError('Rust toolchain escapes selected root')
            rust={'root':rust_root,**{name:(tools/name).resolve(strict=True) for name in ('cargo','rustc','rustdoc')}}
            durable(root/'reports/rust-toolchain.json',{'toolchain':toolchain,'rustup_root':str(rust_root),'settings_sha256':sha(rust_settings),'binaries':{name:{'path':str(rust[name]),'sha256':sha(rust[name])} for name in ('cargo','rustc','rustdoc')}})
            diagnostic=root/'diagnostic';durable(root/'reports/diagnostic-workcopy.json',workcopy(diagnostic,manifest))
            env=profile(root/'diagnostic-profile',clone,helper,digest,sdk,developer,rust)
            version_receipt=command(supervisor,root,'compiler-version',[str(compiler),'--version'],root,env,15)
            durable(root/'reports/helper-provenance.json',{'source_sha256':receipt['source_sha256'],'compiler_physical_path':str(compiler),
               'compiler_sha256':sha(compiler),'compiler_version_receipt':version_receipt,'sdk_path':str(sdk),'sdk_version':version,
               'sdk_settings_sha256':sha(sdk_settings if sdk_settings.exists() else sdk/'SDKSettings.plist'),
               'target_architecture':platform.machine(),'argv':receipt['argv'],'supervisor_receipt':receipt,'output_sha256':digest,
               'python_physical_path':str(Path(sys.executable).resolve()),'python_sha256':sha(Path(sys.executable).resolve()),'python_version':sys.version})
            command(supervisor,root,'darwin-supervisor-suite',[sys.executable,'-B',str(HERE/'run_native_suite.py'),str(diagnostic)],diagnostic,env,120)
            summary['phases']['darwin_supervisor_suite']='passed'
            command(supervisor,root,'runtime-version',[str((clone/'bin/racket').resolve()),'-e','(display (version))'],diagnostic,env,15,marker='9.3')
            cargo=str(rust['cargo'])
            if not cargo:raise ValueError('Preinstalled cargo missing')
            # Keep rustup proxy basename intact; realpath would select rustup itself.
            command(supervisor,root,'cargo-release',[cargo,'build','--release','--offline','--locked'],diagnostic/'engine',env,240)
            command(supervisor,root,'cocoa-compile',['/bin/bash',str(diagnostic/'ci/build-native.sh')],diagnostic,env,600)
            summary['phases']['cocoa_compile']='passed'
            app=diagnostic/'build/native/OpenRacket Reconstruction.app';app_manifest=tree(app)
            durable(root/'reports/compiled-app.json',app_manifest)
            command(supervisor,root,'native-smoke',[str(app/'Contents/MacOS/OpenRacket'),'--native-smoke'],diagnostic,env,30,marker=SMOKE_MARKER)
            summary['phases']['limited_native_smoke']='passed'
            verify_sources(diagnostic,manifest['files']);_,clone_witness=compare_tree(baseline,clone)
            durable(root/'reports/runtime-after-diagnostic.json',clone_witness)
            if not clone_witness['unchanged']:raise ValueError('Runtime clone changed during diagnostic')
            # The full native gate remains unchanged and gets its own fresh outputs/profile.
            acceptance=root/'acceptance';durable(root/'reports/acceptance-workcopy.json',workcopy(acceptance,manifest))
            env2=profile(root/'acceptance-profile',clone,helper,digest,sdk,developer,rust)
            command(supervisor,root,'mandatory-native-gate',['/bin/bash',str(acceptance/'ci/verify-native.sh')],acceptance,env2,7200,marker=GATE_MARKER)
            verify_sources(acceptance,manifest['files'])
            summary['phases']['mandatory_native_gate']='passed'
            summary['native_acceptance']='mandatory automated native gate passed; screenshots, VoiceOver, system IME, performance and DrRacket parity pending'
        except BaseException as error:
            summary['error']=type(error).__name__+': '+str(error)
            # No recovery launch after any engine-capable failure, even if the
            # outer group alone is quiet: app helpers intentionally own groups.
            durable(root/'launch-state.json',{'safe_to_continue':False,'phase':'blocked','error':summary['error']},replace=(root/'launch-state.json').exists())
        finally:
            finish_run(supervisor,root,summary)
    return 0 if 'error' not in summary and summary.get('outer_cleanup_verified') else 1

def finish_run(supervisor,root,summary):
    if supervisor is not None:
        try:summary['outer_cleanup_verified']=bool(supervisor.close()) and not supervisor.uncertain
        except BaseException as error:summary['outer_cleanup_error']=str(error)
    # Filesystem-only original runtime/source witnesses; no helper load.
    try:summary['final_witness_passed']=witness(root,'run-final')
    except BaseException as error:summary['final_witness_passed']=False;summary['witness_error']=str(error)
    if not summary['final_witness_passed'] or not summary.get('outer_cleanup_verified'):
        summary['error']=summary.get('error','Final witness or outer cleanup unverified')
        summary['native_acceptance']='final witness or cleanup unverified; native acceptance not established'
        durable(root/'launch-state.json',{'safe_to_continue':False,'phase':'final-witness-failed'},replace=(root/'launch-state.json').exists())
    durable(root/'reports/run-summary.json',summary)

def witness(root,label):
    reports=root/'reports';result={'schema':'openracket-independent-final-witness/v1','label':label,'passed':False,'checks':{}}
    def check(name,fn):
        try:
            value=fn();result['checks'][name]={'passed':True,'result':value}
            if isinstance(value,dict) and value.get('unchanged') is False:result['checks'][name]['passed']=False
        except BaseException as error:result['checks'][name]={'passed':False,'error':type(error).__name__+': '+str(error)}
    def original():
        context=json.loads((root/'context.json').read_bytes());before=json.loads((reports/'original-runtime-before.json').read_bytes())
        return compare_tree(before,Path(context['original_runtime']),require_identity=True)[1]
    check('original_runtime',original)
    check('immutable_projection',lambda: {'members':len(projection()['files'])})
    for name in ('diagnostic','acceptance'):
        if (root/name).is_dir():
            check(name+'_sources',lambda name=name: verify_sources(root/name,public_inputs()[0]['files']))
        else:
            created=(reports/(name+'-workcopy.json')).exists()
            result['checks'][name+'_sources']={'passed':False if created else None,'status':'recorded-workcopy-missing' if created else 'not-created'}
    result['passed']=all(row['passed'] is not False for row in result['checks'].values())
    durable(reports/(label+'.json'),result)
    print('OPENRACKET_COCOA_FINAL_WITNESS '+json.dumps(result),flush=True)
    return result['passed']

def runtime_inventory_summary(path,codec):
    """Keep full baseline locally; export a byte-bound summary, never its rows."""
    result={'schema':'openracket-runtime-inventory-summary/v1',
            'complete':False,'full_inventory_transported':False}
    try:
        stream,info=codec._open_input(codec.physical_root(path.parent),path.name)
        with stream:
            if not 0<info.st_size<=32*1024*1024:
                raise ValueError('Runtime inventory size bound')
            raw=stream.read(info.st_size+1)
            after=os.fstat(stream.fileno())
        if len(raw)!=info.st_size or codec._identity(info)!=codec._identity(after):
            raise ValueError('Runtime inventory changed while reading')
        result.update(raw_bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest())
        value=codec.strict_json(raw)
        if type(value) is not dict or set(value)!={'schema','root','root_device','root_inode','entries','tree_sha256'} or value['schema']!='openracket-runtime-tree/v1':
            raise ValueError('Runtime inventory schema')
        if not isinstance(value['entries'],dict) or not isinstance(value['root'],str) or not value['root'].startswith('/'):
            raise ValueError('Runtime inventory entries/root')
        if any(type(value[k]) is not int or value[k]<0 for k in ('root_device','root_inode')):
            raise ValueError('Runtime inventory root identity')
        encoded=json.dumps(value['entries'],sort_keys=True,separators=(',',':')).encode()
        if hashlib.sha256(encoded).hexdigest()!=value['tree_sha256']:
            raise ValueError('Runtime inventory tree digest')
        result.update(complete=True,root=value['root'],root_device=value['root_device'],
                      root_inode=value['root_inode'],entry_count=len(value['entries']),
                      tree_sha256=value['tree_sha256'])
    except (OSError,ValueError,TypeError) as error:
        result['error']=type(error).__name__+': '+str(error)
    return result

def transport(root):
    pins=json.loads((HERE/'VENDOR-PINS.json').read_bytes())
    def vendor(name):
        row=next(x for x in pins if x['path']==name)
        return load_exact(HERE/'vendor'/name,'cocoa_'+name.replace('-','_').replace('.','_'),row['sha256'])
    codec=vendor('object-hash-transport.py');emitter=vendor('emit-replay-evidence.py')
    reports=root/'reports'
    inventory=reports/'original-runtime-before.json'
    inventory_summary=runtime_inventory_summary(inventory,codec)
    summary_path=reports/'original-runtime-summary.json'
    durable(summary_path,inventory_summary,replace=summary_path.exists())
    # Only generated public receipts/logs: never source archives, native binaries,
    # runtime payloads, profile data or pre-existing historical evidence.
    for name in ('diagnostic','acceptance'):
        evidence=root/name/'evidence'
        if evidence.exists():
            target=reports/(name+'-inner-evidence');target.mkdir(mode=0o700)
            for p in sorted(evidence.rglob('*')):
                if p.is_file() and p.name!='.supervisor.lock':
                    if p.is_symlink():raise ValueError('Evidence symlink refused')
                    q=target/p.relative_to(evidence);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    # Native helper is an executable prerequisite, not public log evidence.
    files=[p.relative_to(reports).as_posix() for p in sorted(reports.rglob('*')) if p.is_file() and p!=inventory and p.name not in {'.supervisor.lock','openracket_process_inventory.dylib'}]
    out=root/'transport';out.mkdir(mode=0o700)
    envelope=codec.build_bundle(files,reports,out/'evidence.xz')
    transport_complete=codec.emit_bundle(envelope,emitter,out)['complete']
    return transport_complete and inventory_summary['complete']

def main():
    global SOURCE
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['run','finalize','validate-projection']);parser.add_argument('--root',type=Path);args=parser.parse_args()
    if args.mode=='validate-projection':m=projection();print(json.dumps({'members':len(m['files']),'public_source_manifest_sha256':MANIFEST_SHA}));return 0
    if args.root is None:parser.error('--root required')
    root=args.root.parent.resolve(strict=True)/args.root.name
    if args.mode=='run':return run(root)
    SOURCE=root/'immutable-source'
    if not (root/'reports').is_dir():print('No initialized native run; bootstrap/native stages pending');return 1
    return finalize(root)

def finalize(root):
    good=False;errors=[]
    try:good=witness(root,'independent-final')
    except BaseException as error:errors.append({'phase':'witness','error':type(error).__name__+': '+str(error)})
    try:good=transport(root) and good
    except BaseException as error:errors.append({'phase':'transport','error':type(error).__name__+': '+str(error)});good=False
    if errors:
        try:print('OPENRACKET_COCOA_EVIDENCE_INCOMPLETE '+json.dumps({'errors':errors,'complete':False}),flush=True)
        except BaseException:pass
    return 0 if good and not errors else 1

if __name__=='__main__':raise SystemExit(main())
