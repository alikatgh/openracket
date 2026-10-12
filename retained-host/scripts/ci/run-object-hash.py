#!/usr/bin/env python3
"""CI-only physical-editor object-hash eligibility diagnostic; no optimization."""
import hashlib,importlib.util,json,os,pathlib,platform,shutil,sys,traceback
if sys.flags.optimize:raise RuntimeError('Optimized Python refused')
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[2]
CI=ROOT/'scripts/ci';EXP=ROOT/'experiments/object-hash'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
contract=module('object_hash_contract',CI/'object-hash-ci-contract.py')
supervisor=module('object_hash_supervisor',CI/'object-hash-supervisor.py')
evidence=module('object_hash_evidence',CI/'object-hash-evidence.py')
emitter=module('object_hash_emitter',CI/'emit-replay-evidence.py')
transport_module=module('object_hash_transport',CI/'object-hash-transport.py')

def write(path,data):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    supervisor.durable_json(path,data)

def output_json(out):
    raw=(out/'stdout.bin').read_bytes();return evidence.decode(raw)

def main():
    contract.need(sys.argv[1:] in (['run'],['verify']),'Explicit run/verify required')
    contract.need(os.environ.get('GITHUB_ACTIONS')=='true' and platform.system()=='Darwin','CI-only macOS execution')
    contract.need(os.environ.get('GITHUB_REPOSITORY')=='alikatgh/openracket' and os.environ.get('GITHUB_REF')=='refs/heads/prototype/retained-drracket','Exact public prototype CI scope')
    reports=ROOT/'reports/object-hash-ci';reports.mkdir(parents=True,exist_ok=True)
    temp=contract.existing(os.environ['RUNNER_TEMP']);selected=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET'])
    contract.need(selected.is_absolute(),'Absolute original executable selection required')
    selected_root=selected.parents[1]
    # Preserve the original leaf, even if it was removed/replaced. Resolve only
    # its ancestor so verify can emit a failed witness without following a new
    # root symlink or failing before report initialization.
    original=selected_root.parent.resolve(strict=False)/selected_root.name
    contract.need(temp in original.parents,'Disposable full official runtime required')
    baseline=reports/'original-before.json';rows=[];arms=[];inventory_paths=[]
    def write_inventory(path,data,prior=None):
        write(path,data);inventory_paths.append(path)
        previous={} if prior is None else prior['entries'];current=data['entries']
        changed=[] if prior is None else [{'path':key,'before':previous.get(key),'after':current.get(key)} for key in sorted(set(previous)|set(current)) if previous.get(key)!=current.get(key)]
        write(path.with_name(path.stem+'-witness.json'),{'schema':'object-hash-tree-witness/v1','inventory_relative_path':str(path.relative_to(reports)),'raw_bytes':path.stat().st_size,'raw_sha256':contract.sha(path),'root':data['root'],'entries':len(current),'tree_sha256':data['tree_sha256'],'comparison_tree_sha256':None if prior is None else prior['tree_sha256'],'changed_entries':changed,'changed_count':len(changed),'full_inventory_retained_locally':True})
    def result(name,passed,details):
        value={'name':name,'passed':bool(passed),'details':details};rows.append(value)
        print('OPENRACKET_OBJECT_HASH_CI_RESULT '+json.dumps(value,sort_keys=True),flush=True)
    def witness(label):
        contract.need(not original.is_symlink(),'Original runtime root became a symlink')
        after=contract.tree(original);before=evidence.decode(baseline.read_bytes());write_inventory(reports/label,after,before)
        contract.need(after==before,'Full original runtime changed')
        result('Full original runtime witness',True,{'tree_sha256':after['tree_sha256'],'entries':len(after['entries'])})
    if sys.argv[1]=='verify':
        try:witness('original-workflow-final.json')
        except BaseException:result('Final original witness',False,traceback.format_exc())
        write(reports/'workflow-final.json',{'passed':bool(rows) and all(r['passed'] for r in rows),'checks':rows})
        transport=reports/'workflow-final-transport';transport.mkdir(exist_ok=True);transport_errors=[]
        # Collect all independent final receipts before one bounded emission.
        # A partial envelope is never retried; the independent status remains.
        final_paths=[path for path in (reports/'original-workflow-final-witness.json',reports/'workflow-final.json') if path.is_file()]
        try:
            envelope=transport_module.build_bundle(final_paths,reports,transport/'final-evidence.xz')
            contract.need(envelope['compressed_bytes']<=512*1024,'Final witness transport exceeds separate 512 KiB reserve')
            emitted=transport_module.emit_bundle(envelope,emitter,transport)
            if not emitted.get('complete'):transport_errors.append({'path':'final-evidence.xz','error':'Final witness envelope emission incomplete'})
        except Exception as error:transport_errors.append({'path':'final-evidence.xz','error':str(error)})
        final={'schema':'object-hash-final-witness/v1','passed':bool(rows) and all(r['passed'] for r in rows) and not transport_errors,'checks':rows,'transport_errors':transport_errors}
        target=transport/'summary.json';write(target,final)
        try:emitter.emit(target)
        except Exception:final['passed']=False;print('OPENRACKET_OBJECT_HASH_FINAL_TRANSPORT_FAILURE '+json.dumps({'error':traceback.format_exc()}),flush=True)
        return 0 if final['passed'] else 1
    sup=supervisor.Supervisor(reports/'commands')
    def command(name,argv,env,cwd,timeout,host=False):
        print('OPENRACKET_OBJECT_HASH_CI_START '+json.dumps({'name':name,'command':[str(x) for x in argv],'timeout_seconds':timeout,'state':'starting'}),flush=True)
        row,out=sup.run(name,argv,env,cwd,timeout,host=host)
        result(name,row['passed'],{'process':str(out/'process.json'),'returncode':row['returncode'],'cleanup_verified':row['cleanup_verified']})
        contract.need(row['passed'],'Command failed; later native launches blocked: '+name)
        return row,out
    try:
        contract.need(not original.is_symlink(),'Original runtime root symlink refused')
        write_inventory(baseline,contract.tree(original))
        contract.verify_frozen(EXP)
        contract.verify_helpers(CI/'object-hash-native')
        review_gate=evidence.decode((CI/'OBJECT-HASH-REVIEW-GATE.json').read_bytes())
        contract.need(review_gate.get('native_dispatch_ready') is True,review_gate.get('blocker','Native review gate incomplete'))
        # All source-only checks execute in fresh processes under an explicitly
        # symlinked TMPDIR. This does not execute the Racket binary.
        fixture=contract.new_directory(temp,'object-hash-portable-tmp');alias=fixture.with_name(fixture.name+'-alias')
        contract.need(not alias.exists() and not alias.is_symlink(),'Fresh fixture alias');alias.symlink_to(fixture,target_is_directory=True)
        testenv=contract.clean_environment(os.environ);testenv.update(TMPDIR=str(alias),PYTHONDONTWRITEBYTECODE='1')
        command('portable-source-adapter-transport',[sys.executable,CI/'test-object-hash-adapter.py','--all'],testenv,ROOT,120)
        for purpose in contract.PURPOSES:
            arm=contract.copy_arm(original,EXP,temp,purpose);arms.append(arm)
            shutil.copytree(CI/'object-hash-native',pathlib.Path(arm['work'])/'ci');contract.verify_helpers(pathlib.Path(arm['work'])/'ci')
        roots=[original]
        for arm in arms:roots.extend(pathlib.Path(arm[key]) for key in ('runtime','package','compiled','profile')) ; roots.append(pathlib.Path(arm['work'])/'ci')
        write(reports/'independent-before.json',contract.independent(roots))
        for arm in arms:
            stock=arm['purpose']=='object-hash-stock';name='stock' if stock else 'diagnostic';c=pathlib.Path(arm['runtime']);q=pathlib.Path(arm['package']);h=pathlib.Path(arm['work'])/'ci';flag=None if stock else '0'
            before_overlay=contract.tree(c);write_inventory(reports/(name+'-before-overlay.json'),before_overlay,evidence.decode(baseline.read_bytes()))
            if not stock:
                # Source-only stage/verify preserves the original and permits
                # precisely one copied core file in this disposable clone.
                sys.path.insert(0,str(q/'scripts'))
                for imported in ('generate','overlay'):
                    if imported in sys.modules:del sys.modules[imported]
                overlay=module('object_hash_overlay',q/'scripts/overlay.py')
                stage=pathlib.Path(arm['work'])/'overlay';overlay.stage(c,stage);overlay.verify(stage)
                target=contract.inside(c/'collects/racket/private/class-internal.rkt',c)
                contract.need(contract.sha(target)==contract.ORIGINAL_CLASS and target.stat().st_nlink==1,'Pristine owned class before overlay')
                target.write_bytes((stage/'overlay/collects/racket/private/class-internal.rkt').read_bytes())
                contract.need(contract.sha(target)==contract.DIAGNOSTIC_CLASS,'Exact staged diagnostic core')
                write(reports/'diagnostic-overlay.json',{'manifest':json.loads((stage/'MANIFEST.json').read_text()),'reversal_sha256':contract.sha(stage/'original/class-internal.rkt')})
            else:contract.need(contract.sha(c/'collects/racket/private/class-internal.rkt')==contract.ORIGINAL_CLASS,'Unmodified stock class')
            arm['immutable_before']=contract.tree(c);write_inventory(reports/(name+'-after-overlay.json'),arm['immutable_before'],before_overlay)
            arm['helper_before']=contract.tree(h)
            p=contract.profile(arm,'profile-inventory');env=contract.environment(os.environ,arm,p,flag=flag)
            row,out=command(name+'-config',contract.prefix(arm,p)+['-c','-I','racket/base','-t',str(h/'config-inventory.rkt')],env,q,90)
            value=output_json(out);collections=contract.validate_config(value,arm,p);arm['collections']=collections
            arm['metadata_paths']=[row['path'] for row in value['paths'] if row['label'] in ('collection-info-domain-cache','share-info-cache')]
            write(reports/(name+'-validated-config.json'),value)
            write(reports/(name+'-quarantine.json'),contract.quarantine(arm))
            p=contract.profile(arm,'profile-build');arm['build_profile']=str(p)
            env=contract.environment(os.environ,arm,p,flag=flag,collections=collections)
            commands=contract.compile_commands(arm,p,h)
            for phase,argv in commands:
                command(name+'-'+phase,argv,env,q,contract.BOUNDS[phase])
                if phase=='core':
                    row,out=command(name+'-core-receipts',contract.prefix(arm,p)+['-c','-I','racket/base','-t',str(h/'rebuilt-receipts.rkt'),'--','core'],env,q,90)
                    receipt=output_json(out);contract.validate_receipts(receipt,arm,'core');write(reports/(name+'-core-receipts.json'),receipt)
            helper_modules=sorted(h.glob('*.rkt'));contract.need(helper_modules,'Exact independent helper compile closure')
            command(name+'-helper-compile',contract.prefix(arm,p)+['-l','raco','--','make','-v',*[str(x) for x in helper_modules]],env,q,180)
            row,out=command(name+'-full-receipts',contract.prefix(arm,p)+['-t',str(h/'rebuilt-receipts.rkt'),'--','full'],env,q,180)
            receipt=output_json(out);contract.validate_receipts(receipt,arm,'full');write(reports/(name+'-full-receipts.json'),receipt)
            receipt_path=pathlib.Path(arm['work'])/'prebuild-receipts.json';write(receipt_path,receipt);arm['receipt_sha256']=contract.sha(receipt_path)
            arm['receipt_modules']={row['nominal_path']:{key:row[key] for key in ('nominal_path','source','bytecode','dependency')} for row in receipt['modules']}
            contract.need(arm['receipt_sha256']==contract.sha(reports/(name+'-full-receipts.json')),'Exact raw prebuild evidence copy mismatch')
            write(reports/(name+'-prebuild-input.json'),{'path':str(receipt_path),'raw_sha256':arm['receipt_sha256'],'bytes':receipt_path.stat().st_size})
            after=contract.tree(c);contract.source_unchanged(arm['immutable_before'],after,arm);write_inventory(reports/(name+'-after-build.json'),after,arm['immutable_before']);arm['after_build']=after
            contract.verify_frozen(q);contract.need(contract.tree(h)==arm['helper_before'],'CI helper sources changed during compilation')
            arm['compiled_after_build']=contract.tree(arm['compiled']);write_inventory(reports/(name+'-compiled-after-build.json'),arm['compiled_after_build'])
        # Both independent rebuilds must pass before any semantic or host run.
        diagnostic=arms[1];q=pathlib.Path(diagnostic['package']);h=pathlib.Path(diagnostic['work'])/'ci'
        sys.path.insert(0,str(q/'scripts'));sys.modules.pop('generate',None)
        observation=module('object_hash_observation',q/'scripts/compare_observation.py')
        scenarios=json.loads((q/'native/SCENARIOS.json').read_text());cases=[];hosts={}
        contract.need(scenarios['off']==['off'] and len(scenarios['on'])==15,'Exact sixteen-case scenario contract')
        for scenario in scenarios['off']+scenarios['on']:
            flag='0' if scenario=='off' else '1';p=contract.profile(diagnostic,'profile-case-'+scenario);env=contract.environment(os.environ,diagnostic,p,flag=flag,collections=diagnostic['collections'])
            argv=contract.prefix(diagnostic,p)+['-t',str(h/'audit-loads.rkt'),'-t',str(q/'native/test-actual-forms.rkt'),'--',scenario]
            row,out=command('semantics-'+scenario,argv,env,q,30)
            raw=(out/'stdout.bin').read_bytes();audit=evidence.load_audit(raw,diagnostic,[scenario])
            accepted=evidence.semantics(raw,row,scenario,flag,observation);accepted['load_audit']=audit;cases.append(accepted)
        write(reports/'semantics.json',cases)
        for mode in ('stock','off','on'):
            arm=arms[0] if mode=='stock' else diagnostic;q=pathlib.Path(arm['package']);h=pathlib.Path(arm['work'])/'ci';p=contract.profile(arm,'profile-host-'+mode)
            flag=None if mode=='stock' else ('0' if mode=='off' else '1');env=contract.environment(os.environ,arm,p,flag=flag,collections=arm['collections']);env.update(OPENRACKET_NATIVE_CASE='check-syntax',OPENRACKET_UI='stock')
            target=q/'vendor/host/tests/reference-host-0520.rkt' if mode=='stock' else q/'native/bootstrap.rkt'
            argv=contract.prefix(arm,p)+['-t',str(h/'audit-loads.rkt'),'-t',str(target)]+([] if mode=='stock' else ['--',mode,arm['runtime']])
            row,out=command('host-'+mode,argv,env,q,60,host=True)
            raw=(out/'stdout.bin').read_bytes();audit=evidence.load_audit(raw,arm,[] if mode=='stock' else [mode,arm['runtime']])
            hosts[mode]=evidence.host(raw,(out/'ready.json').read_bytes(),(out/'screenshot.png').read_bytes(),row,mode,arm,observation,supervisor.png_record);hosts[mode]['load_audit']=audit
        write(reports/'matrix.json',evidence.matrix(cases,hosts));result('Complete diagnostic matrix',True,hosts['on']['assessment'])
    except BaseException:result('Diagnostic orchestration',False,traceback.format_exc())
    finally:
        # Pure read-only Python witnesses and transport always remain possible;
        # they do not start native processes or clear an uncertain launch lease.
        for arm in arms:
            try:
                name='stock' if arm['purpose']=='object-hash-stock' else 'diagnostic';after=contract.tree(arm['runtime']);write_inventory(reports/(name+'-after-execution.json'),after,arm.get('after_build',arm.get('immutable_before')))
                if 'immutable_before' in arm:contract.source_unchanged(arm['immutable_before'],after,arm)
                contract.verify_frozen(arm['package'])
                compiled_after=contract.tree(arm['compiled']);write_inventory(reports/(name+'-compiled-after-execution.json'),compiled_after,arm.get('compiled_after_build'))
                for product in pathlib.Path(arm['compiled']).rglob('*'):
                    contract.inside(product,pathlib.Path(arm['compiled']))
                    if product.is_file():contract.need(product.stat().st_nlink==1,'Shared compiled output inode refused')
                if 'helper_before' in arm:contract.need(contract.tree(pathlib.Path(arm['work'])/'ci')==arm['helper_before'],'Helper source mutation')
                if 'receipt_sha256' in arm:
                    rp=pathlib.Path(arm['work'])/'prebuild-receipts.json';contract.inside(rp,pathlib.Path(arm['work']));contract.need(rp.stat().st_nlink==1 and contract.sha(rp)==arm['receipt_sha256'],'Prebuild receipt input changed')
                    contract.validate_receipts(evidence.decode(rp.read_bytes()),arm,'full')
                    write(reports/(name+'-prebuild-after.json'),{'path':str(rp),'raw_sha256':contract.sha(rp),'unchanged':True})
                result(name+' immutable source/config/link witness',True,'Only staged diagnostic class and predeclared compiled/metadata locations may differ')
            except BaseException:result('Clone/source witness',False,traceback.format_exc())
        try:
            final_roots=[original]
            for arm in arms:
                w=pathlib.Path(arm['work'])
                final_roots.extend(pathlib.Path(arm[key]) for key in ('runtime','package','compiled','profile','quarantine'))
                final_roots.append(w/'ci')
                final_roots.extend(sorted(p for p in w.glob('profile-*') if p.is_dir()))
                if (w/'overlay').is_dir():final_roots.append(w/'overlay')
            write(reports/'independent-after.json',contract.independent(final_roots))
            result('Final independent roots/profiles/caches',True,'No shared mutable device/inode pairs or external links')
        except BaseException:result('Final clone independence',False,traceback.format_exc())
        try:witness('original-after.json')
        except BaseException:result('Full original runtime witness',False,traceback.format_exc())
        if sup.blocked or sup.lease.exists():result('Verified cleanup',False,'Durable launch block retained; no later native process permitted')
        report={'schema':'object-hash-ci/v1','passed':bool(rows) and all(r['passed'] for r in rows),'checks':rows,'optimization_implemented':False,'timing_experiment':False,'candidate_adopted':False}
        write(reports/'results.json',report)
        (reports/'summary.md').write_text('# Physical editor object-hash eligibility diagnostic\n\n'+('PASS' if report['passed'] else 'FAIL / incomplete')+'\n\nNo optimization, timing experiment, speed or allocation-byte claim.\n\n'+'\n'.join('- '+r['name']+': '+('PASS' if r['passed'] else 'FAIL / incomplete') for r in rows)+'\n')
        transport={'complete':False}
        try:
            transport_dir=reports/'bounded-transport';transport_dir.mkdir()
            excluded=set(inventory_paths)
            paths=[p for p in sorted(reports.rglob('*')) if p.is_file() and p not in excluded and not p.is_relative_to(transport_dir)]
            envelope=transport_module.build_bundle(paths,reports,transport_dir/'evidence.xz')
            transport=transport_module.emit_bundle(envelope,emitter,transport_dir)
        except BaseException:
            failure={'schema':'object-hash-transport-failure/v1','complete':False,'error':traceback.format_exc(),'all_original_evidence_retained_locally':True,'interpretation_blocked':True}
            write(reports/'transport-failure.json',failure)
            print('OPENRACKET_OBJECT_HASH_TRANSPORT_FAILURE '+json.dumps(failure,sort_keys=True),flush=True)
        if not transport.get('complete'):report['passed']=False
        write(reports/'final-status.json',{'schema':'object-hash-final-status/v1','passed':report['passed'],'transport_complete':bool(transport.get('complete')),'optimization_implemented':False,'timing_experiment':False})
        print('OPENRACKET_OBJECT_HASH_CI_FINAL '+json.dumps({'passed':report['passed'],'transport_complete':bool(transport.get('complete')),'optimization_implemented':False,'timing_experiment':False}),flush=True)
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
