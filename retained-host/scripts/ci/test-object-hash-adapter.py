#!/usr/bin/env python3
"""Portable refusal/supervisor/transport tests; no Racket execution."""
import base64,contextlib,copy,hashlib,importlib.util,io,json,os,pathlib,shutil,struct,subprocess,sys,tempfile,unittest,zlib
from unittest.mock import patch
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1];EXP=ROOT/'experiments/object-hash'
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
C=load('test_object_contract','object-hash-ci-contract.py');S=load('test_object_supervisor','object-hash-supervisor.py');E=load('test_object_evidence','object-hash-evidence.py');EM=load('test_object_emitter','emit-replay-evidence.py');D=load('test_object_decoder','decode-replay-evidence.py')
class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        # Canonicalize ordinary fixtures centrally. Alias/escape negatives below
        # deliberately create their own links after this physical root is known.
        self.root=pathlib.Path(self.tmp.name).resolve(strict=True)
    def arm(self):
        w=self.root/'arm';w.mkdir();c=w/'runtime';c.mkdir();q=w/'probe';shutil.copytree(EXP,q)
        for p in (c/'collects',c/'etc',c/'bin',w/'compiled',w/'quarantine',w/'ci'):p.mkdir()
        (c/'bin/racket').write_text('fixture')
        return {'purpose':'object-hash-stock','work':str(w),'runtime':str(c),'package':str(q),'compiled':str(w/'compiled'),'quarantine':str(w/'quarantine')}
class PathAndCompileTests(TempCase):
    def test_exact_reviewed_helper_manifest(self):self.assertTrue(C.verify_helpers(HERE/'object-hash-native'))
    def test_helper_tampering_refused(self):
        target=self.root/'helpers';shutil.copytree(HERE/'object-hash-native',target);(target/'core-first.rkt').write_text('changed')
        with self.assertRaises(ValueError):C.verify_helpers(target)
    def test_helper_extra_file_refused(self):
        target=self.root/'helpers';shutil.copytree(HERE/'object-hash-native',target);(target/'unknown.rkt').write_text('extra')
        with self.assertRaises(ValueError):C.verify_helpers(target)
    def test_complete_frozen_source(self):self.assertEqual(len(C.verify_frozen(EXP)),58)
    def test_publication_report_redaction_is_explicit(self):
        proof=(EXP/'reports/symlinked-tmpdir-proof.log').read_text()
        self.assertIn('descriptive placeholders',proof)
        self.assertIn('no test was rerun or reclassified by this redaction',proof)
        self.assertIn('Original record SHA-256: bfc74fcf2664667656f310ba897d0a14e1f54bac992a7fbaeb9a2c9568d7102a',proof)
        self.assertIn('TMPDIR=<temporary-root>/alias',proof)
        self.assertIn('SYMLINK=<temporary-root>/physical',proof)
        self.assertIn('Python temporary directory: <temporary-root>/alias/<temporary-child>',proof)
        self.assertIn('Canonical temporary directory: <temporary-root>/physical/<temporary-child>',proof)
        self.assertIn('Explicit symlinked TMPDIR verified: true',proof)
        self.assertNotIn('/tmp/',proof)
    def test_ancestor_alias_supported(self):
        alias=self.root/'alias';real=self.root/'physical';real.mkdir();alias.symlink_to(real,target_is_directory=True)
        self.assertEqual(C.new_directory(alias,'leaf'),real/'leaf')
    def test_internal_leaf_symlink_refused(self):
        (self.root/'f').write_text('x');(self.root/'alias').symlink_to(self.root/'f')
        with self.assertRaises(ValueError):C.inside(self.root/'alias',self.root)
    def test_dangling_new_leaf_refused(self):
        (self.root/'leaf').symlink_to(self.root/'missing')
        with self.assertRaises(ValueError):C.new_directory(self.root,'leaf')
    def test_escape_refused(self):
        sub=self.root/'sub';sub.mkdir();(sub/'outside').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):C.inside(sub/'outside/anything',sub,allow_missing=True)
    def test_overlap_refused(self):
        sub=self.root/'sub';sub.mkdir()
        with self.assertRaises(ValueError):C.independent([self.root,sub])
    def test_shared_inode_refused(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir();(a/'f').write_text('x');os.link(a/'f',b/'f')
        with self.assertRaises(ValueError):C.independent([a,b])
    def test_independent_regular_files(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir();(a/'f').write_text('x');(b/'f').write_text('x');self.assertEqual(C.independent([a,b])['regular_files'],2)
    def test_purpose_refusal(self):
        with self.assertRaises(ValueError):C.copy_arm(self.root,EXP,self.root,'named-style-control')
    def test_exact_compile_split_and_boundary(self):
        a=self.arm();p=C.profile(a,'profile-build');commands=C.compile_commands(a,p,pathlib.Path(a['work'])/'ci')
        self.assertEqual([x[0] for x in commands],['core','setup','native_compile'])
        self.assertEqual(commands[0][1][-5:-2],['setup','--','--boot'])
        self.assertEqual(commands[1][1][-len(C.SETUP_FLAGS):],C.SETUP_FLAGS)
        make=commands[2][1];self.assertIn('--',make);self.assertEqual(sum(x.endswith('.rkt') for x in make),23);self.assertFalse(any(x.endswith('.rktd') for x in make))
        for phase,cmd in commands:self.assertEqual(cmd[cmd.index('-R')+1],a['compiled']);self.assertNotIn('-c',cmd)
    def test_all_runtime_overrides_removed(self):
        a=self.arm();p=C.profile(a,'profile-one');env=C.environment({'PLTFOO':'bad','OPENRACKET_OTHER':'bad','DYLD_INSERT_LIBRARIES':'bad','PYTHONPATH':'bad','HOME':'bad','PATH':'bad','TOKEN':'secret'},a,p,flag='0',collections=[a['runtime']+'/collects'])
        for key in ('PLTFOO','OPENRACKET_OTHER','DYLD_INSERT_LIBRARIES','PYTHONPATH','TOKEN'):self.assertNotIn(key,env)
        self.assertEqual(env['HOME'],str(p));self.assertEqual(env['PLTCOMPILEDROOTS'],a['compiled']);self.assertEqual(env['PLT_ZO_PATH'],'compiled');self.assertEqual(env['OPENRACKET_OBJECT_HASH_PROBE'],'0')
    def test_inventory_does_not_hide_extra_collections(self):
        a=self.arm();p=C.profile(a,'profile-inventory');self.assertNotIn('PLTCOLLECTS',C.environment({},a,p))
    def test_stock_has_no_diagnostic_flag(self):
        a=self.arm();p=C.profile(a,'profile-one');self.assertNotIn('OPENRACKET_OBJECT_HASH_PROBE',C.environment({},a,p))
    def test_fresh_profile_required(self):
        a=self.arm();C.profile(a,'profile-one')
        with self.assertRaises(ValueError):C.profile(a,'profile-one')
    def test_quarantine_all_packages_and_metadata(self):
        a=self.arm();c=pathlib.Path(a['runtime']);d=c/'share/pkgs/some/compiled';d.mkdir(parents=True)
        for name in ('x_rkt.zo','x_rkt.dep','cache.rktd'):(d/name).write_bytes(name.encode())
        info=c/'share/info-cache.rktd';info.write_bytes(b'old');a['metadata_paths']=[str(info)];(c/'lib').mkdir();(c/'lib/ordinary.dylib').write_bytes(b'keep')
        rows=C.quarantine(a);self.assertEqual(len(rows),4);self.assertTrue((c/'lib/ordinary.dylib').exists());self.assertFalse(info.exists())
    def test_compiled_native_extension_requires_review(self):
        a=self.arm();c=pathlib.Path(a['runtime']);d=c/'collects/compiled';d.mkdir();(d/'x.dylib').write_bytes(b'opaque')
        with self.assertRaises(ValueError):C.quarantine(a)
    def test_nonempty_compiled_root_refused(self):
        a=self.arm();(pathlib.Path(a['compiled'])/'old.zo').write_bytes(b'old')
        with self.assertRaises(ValueError):C.quarantine(a)
    def test_source_manifest_rejects_mutation(self):
        a=self.arm();before=C.tree(a['runtime']);(pathlib.Path(a['runtime'])/'bin/racket').write_text('mutated')
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(a['runtime']),a)
    def test_new_bytecode_outside_K_refused(self):
        a=self.arm();before=C.tree(a['runtime']);(pathlib.Path(a['runtime'])/'collects/bad.zo').write_bytes(b'bad')
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(a['runtime']),a)
    def test_safe_parent_relative_config_is_canonicalized(self):
        c=self.root/'runtime';c.mkdir();(c/'collects').mkdir();(c/'lib').mkdir()
        self.assertEqual(C.config_path(c/'collects/../lib',c/'lib',(c,)),c/'lib')
    def test_true_parent_relative_config_escape_refused(self):
        c=self.root/'runtime';c.mkdir();(c/'collects').mkdir()
        with self.assertRaises(ValueError):C.config_path(c/'collects/../../outside',self.root/'outside',(c,))
    def test_raw_config_symlink_cannot_be_hidden_by_canonicalization(self):
        c=self.root/'runtime';c.mkdir();(c/'real').mkdir();(c/'alias').symlink_to(c/'real',target_is_directory=True)
        with self.assertRaises(ValueError):C.config_path(c/'alias/file',c/'real/file',(c,))
    def test_metadata_suffix_does_not_authorize_unknown_destination(self):
        a=self.arm();c=pathlib.Path(a['runtime']);before=C.tree(c);outside=self.root/'outside-data';outside.write_bytes(b'outside');(c/'bin/info-cache.rktd').symlink_to(outside)
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(c),a)
    def test_declared_metadata_must_remain_physical_single_link_file(self):
        a=self.arm();c=pathlib.Path(a['runtime']);target=c/'collects/info-cache.rktd';a['metadata_paths']=[str(target)];before=C.tree(c);outside=self.root/'outside-data';outside.write_bytes(b'outside');target.symlink_to(outside)
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(c),a)
    def test_declared_physical_metadata_update_is_allowed(self):
        a=self.arm();c=pathlib.Path(a['runtime']);target=c/'collects/info-cache.rktd';a['metadata_paths']=[str(target)];target.write_bytes(b'old');before=C.tree(c);target.write_bytes(b'new');self.assertTrue(C.source_unchanged(before,C.tree(c),a))
    def test_new_installed_directory_outside_metadata_ancestors_refused(self):
        a=self.arm();c=pathlib.Path(a['runtime']);before=C.tree(c);(c/'bin/unexpected').mkdir()
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(c),a)
    def test_original_tree_detects_modes_links_bytes(self):
        (self.root/'f').write_text('x');before=C.tree(self.root);(self.root/'f').chmod(0o600);self.assertNotEqual(before,C.tree(self.root))
class SupervisorTests(TempCase):
    def test_uncertain_spawn_retains_durable_lease(self):
        s=S.Supervisor(self.root/'reports')
        def fail(*args,**kwargs):raise OSError('uncertain spawn')
        row,out=s.run('uncertain',['fixture'],{},self.root,30,popen=fail)
        self.assertFalse(row['passed']);self.assertTrue(s.blocked);self.assertTrue(s.lease.exists())
        with self.assertRaises(RuntimeError):s.run('later',['fixture'],{},self.root,30,popen=fail)
    def test_late_exit_rejected_spawn_counts_toward_deadline(self):
        s=S.Supervisor(self.root/'reports');t=[0]
        class Proc:
            pid=912345
            def poll(self):return 0
            def wait(self,**kwargs):return 0
        def launch(*a,**k):t[0]=61;return Proc()
        with patch.object(S,'terminate_group',lambda p:None),patch.object(S,'live_group_members',lambda pid:[]):row,_=s.run('late',['fixture'],{},self.root,60,popen=launch,clock=lambda:t[0])
        self.assertFalse(row['passed']);self.assertTrue(row['timed_out']);self.assertFalse(s.lease.exists())
    def test_normal_exit_checks_descendants(self):
        s=S.Supervisor(self.root/'reports');calls=[]
        class Proc:
            pid=912345
            def poll(self):return 0
            def wait(self,**kwargs):return 0
        with patch.object(S,'live_group_members',lambda pid:calls.append(pid) or []):row,_=s.run('normal',['fixture'],{},self.root,30,popen=lambda *a,**k:Proc(),clock=lambda:0)
        self.assertTrue(row['passed']);self.assertEqual(calls,[912345]);self.assertFalse(s.lease.exists())
    def test_cleanup_failure_blocks_following_process(self):
        s=S.Supervisor(self.root/'reports')
        class Proc:
            pid=912345
            def poll(self):return 0
            def wait(self,**kwargs):return 0
        with patch.object(S,'live_group_members',side_effect=OSError('cannot observe')),patch.object(S,'terminate_group',side_effect=OSError('cannot clean')):row,_=s.run('blocked',['fixture'],{},self.root,30,popen=lambda *a,**k:Proc(),clock=lambda:0)
        self.assertFalse(row['passed']);self.assertTrue(s.lease.exists());self.assertTrue(s.blocked)
    def test_lease_unlink_failure_cannot_mark_command_passed(self):
        s=S.Supervisor(self.root/'reports');original_unlink=pathlib.Path.unlink
        class Proc:
            pid=912345
            def poll(self):return 0
            def wait(self,**kwargs):return 0
        def unlink(path,*args,**kwargs):
            if path==s.lease:raise OSError('durable lease cannot be removed')
            return original_unlink(path,*args,**kwargs)
        with patch.object(S,'live_group_members',lambda pid:[]),patch.object(pathlib.Path,'unlink',unlink):row,_=s.run('unlink',['fixture'],{},self.root,30,popen=lambda *a,**k:Proc(),clock=lambda:0)
        self.assertFalse(row['passed']);self.assertFalse(row['cleanup_verified']);self.assertTrue(s.blocked);self.assertTrue(s.lease.exists())
    def test_fast_exit_over_output_bound_is_rejected(self):
        s=S.Supervisor(self.root/'reports')
        class Proc:
            pid=912345
            def poll(self):return 0
            def wait(self,**kwargs):return 0
        def launch(*args,**kwargs):kwargs['stdout'].write(b'x'*11);return Proc()
        with patch.object(S,'RAW_LIMIT',10),patch.object(S,'live_group_members',lambda pid:[]):row,_=s.run('too-large',['fixture'],{},self.root,30,popen=launch,clock=lambda:0)
        self.assertFalse(row['passed']);self.assertTrue(row['output_bound_exceeded']);self.assertEqual(row['files']['stdout.bin']['bytes'],11)
    def test_lease_written_before_spawn(self):
        s=S.Supervisor(self.root/'reports');seen=[]
        def launch(*a,**k):seen.append(s.lease.exists());raise OSError('fixture')
        s.run('lease',['fixture'],{},self.root,30,popen=launch);self.assertEqual(seen,[True])
class TransportTests(TempCase):
    def documents(self,data):
        path=self.root/'raw.bin';path.write_bytes(data);return list(S.raw_documents(path,'commands/case/stdout.bin'))
    def test_empty_and_binary_round_trip(self):
        for data in (b'',b'\xff\x00bad json\n',bytes(range(256))*9000):self.assertEqual(S.restore_documents(self.documents(data)),data)
    def test_raw_hash_distinct_from_canonical_json_hash(self):
        raw=b'{ "a" : 1 }\n';docs=self.documents(raw);self.assertEqual(docs[0]['raw_sha256'],hashlib.sha256(raw).hexdigest());self.assertNotEqual(docs[0]['raw_sha256'],EM.digest({'a':1}))
    def test_transport_engine_losslessly_reconstructs_raw_wrapper(self):
        data=bytes(range(256))*600;docs=self.documents(data);p=self.root/'supervisor.json';p.write_text(json.dumps(docs[0]));stream=io.StringIO()
        with contextlib.redirect_stdout(stream):EM.emit(p)
        decoded=D.decode(stream.getvalue(),self.root/'decoded');restored=json.loads(pathlib.Path(decoded[0]['path']).read_text());self.assertEqual(S.restore_documents([restored]),data)
        self.assertTrue(all(len(line.encode())<EM.LINE_LIMIT for line in stream.getvalue().splitlines()))
    def test_missing_reordered_mutated_parts_refused(self):
        docs=self.documents(b'z'*(S.PART_LIMIT+5))
        for bad in (docs[:-1],docs[::-1]):
            with self.assertRaises(ValueError):S.restore_documents(bad)
        bad=copy.deepcopy(docs);bad[0]['chunks'][0]=base64.b64encode(b'changed').decode()
        with self.assertRaises(ValueError):S.restore_documents(bad)
    def test_bool_integer_negative_escape_and_oversize_refused(self):
        for key,value in [('part',False),('parts',True),('raw_bytes',-1),('source_relative_path','../escape'),('source_relative_path','/absolute'),('part_bytes',S.PART_LIMIT+1)]:
            docs=self.documents(b'x');docs[0][key]=value
            with self.assertRaises(ValueError):S.restore_documents(docs)
    def test_emission_failure_does_not_suppress_later_files(self):
        reports=self.root/'reports';reports.mkdir();(reports/'a.bin').write_bytes(b'a');(reports/'b.bin').write_bytes(b'b');calls=[]
        class Emitter:
            def emit(self,p):
                calls.append(str(p))
                if len(calls)==1:raise ValueError('first emission failed')
        result=S.emit_all(reports,Emitter());self.assertFalse(result['complete']);self.assertEqual(len(calls),3);self.assertEqual(len(result['files']),2);self.assertEqual(len(result['errors']),1)
class PngPixelTests(unittest.TestCase):
    def png(self,payload,depth=8,color=2):
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
        return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,depth,color,0,0,0))+chunk(b'IDAT',payload)+chunk(b'IEND',b'')
    def test_valid_pixel_stream(self):self.assertEqual(S.png_record(self.png(zlib.compress(b'\x00\x10\x20\x30')))['width'],1)
    def test_crc_valid_invalid_compression_refused(self):
        with self.assertRaises(ValueError):S.png_record(self.png(b'not compressed image data'))
    def test_wrong_pixel_length_filter_and_trailing_data_refused(self):
        for data in (b'\x00\x10',b'\x05\x10\x20\x30',b'\x00\x10\x20\x30extra'):
            with self.assertRaises(ValueError):S.png_record(self.png(zlib.compress(data)))
        with self.assertRaises(ValueError):S.png_record(self.png(zlib.compress(b'\x00\x10\x20\x30')+b'extra'))
    def test_illegal_depth_color_combination_refused(self):
        with self.assertRaises(ValueError):S.png_record(self.png(zlib.compress(b'\x00\x00'),depth=1,color=2))
class EvidenceTests(unittest.TestCase):
    def test_duplicate_nonfinite_and_missing_marker_refused(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):E.decode(raw)
        with self.assertRaises(ValueError):E.record(b'','REQUIRED')
    def test_boolean_process_status_rejected(self):
        with self.assertRaises(ValueError):E.process({'native_executed':True,'returncode':False},30)
    def test_partial_matrix_refused(self):
        with self.assertRaises(ValueError):E.matrix([], {})


class FinalWitnessTests(TempCase):
    def run_verify(self,*,missing=False,root_link=False,emission_error=False):
        r=load('test_object_runner','run-object-hash.py');r.ROOT=self.root
        runtime=self.root/'install/racket';runtime.mkdir(parents=True);(runtime/'bin').mkdir();(runtime/'bin/racket').write_text('fixture only')
        reports=self.root/'reports/object-hash-ci';reports.mkdir(parents=True);(reports/'original-before.json').write_text(json.dumps(C.tree(runtime)))
        if missing:shutil.rmtree(runtime)
        if root_link:
            shutil.rmtree(runtime);outside=self.root/'outside';outside.mkdir();runtime.symlink_to(outside,target_is_directory=True)
        env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'alikatgh/openracket','GITHUB_REF':'refs/heads/prototype/retained-drracket','RUNNER_TEMP':str(self.root),'OPENRACKET_CI_STOCK_RACKET':str(runtime/'bin/racket')}
        calls=[]
        def emit(path):
            calls.append(path)
            if emission_error and len(calls)==1:raise OSError('first final evidence failed')
        with patch.dict(os.environ,env,clear=True),patch.object(sys,'argv',['run-object-hash.py','verify']),patch.object(r.platform,'system',lambda:'Darwin'),patch.object(r.emitter,'emit',emit),patch.object(r.supervisor.Supervisor,'run',side_effect=AssertionError('verify must never launch')),contextlib.redirect_stdout(io.StringIO()):code=r.main()
        return code,reports,calls
    def test_removed_original_emits_failed_witness(self):
        code,reports,calls=self.run_verify(missing=True);self.assertEqual(code,1);self.assertFalse(json.loads((reports/'workflow-final.json').read_text())['passed']);self.assertGreaterEqual(len(calls),2)
    def test_replaced_original_symlink_is_not_followed(self):
        code,reports,calls=self.run_verify(root_link=True);self.assertEqual(code,1);self.assertIn('became a symlink',(reports/'workflow-final.json').read_text())
    def test_final_transport_continues_after_first_failure(self):
        code,reports,calls=self.run_verify(emission_error=True);self.assertEqual(code,1);self.assertGreaterEqual(len(calls),2);self.assertTrue(json.loads((reports/'workflow-final-transport/summary.json').read_text())['transport_errors'])
    def test_successful_final_witness_has_no_native_launch(self):
        code,reports,calls=self.run_verify();self.assertEqual(code,0);self.assertTrue(json.loads((reports/'workflow-final.json').read_text())['passed'])
class AuditAndBudgetTests(unittest.TestCase):
    def test_audit_rejection_cannot_be_swallowed(self):
        raw=b'OBJECT_HASH_LOAD_AUDIT '+json.dumps({'schema':'object-hash-load-audit/v1','event':'rejected','data':{}}).encode()+b'\n'
        with self.assertRaises(ValueError):E.load_audit(raw,{'compiled':'/fixture'},[])
    def test_null_audit_module_data_refused(self):
        raw=b'OBJECT_HASH_LOAD_AUDIT '+json.dumps({'schema':'object-hash-load-audit/v1','event':'modules','data':None}).encode()+b'\n'
        with self.assertRaises(ValueError):E.load_audit(raw,{'compiled':'/fixture'},[])
    def test_contradictory_native_scope_cannot_be_overwritten(self):
        row={'schema':'object-hash-load-audit/v1','event':'installed','data':{'compiled_root':'/fixture','scope':'initial-place-and-inheriting-threads','child_place_dynamic_audit_complete':False,'live_registry_observed':True,'arbitrary_dynamic_graph_proven':True,'arguments_unchanged':[]}}
        raw=b'OBJECT_HASH_LOAD_AUDIT '+json.dumps(row).encode()+b'\n'
        with self.assertRaises(ValueError):E.load_audit(raw,{'compiled':'/fixture'},[])
    def test_missing_runtime_audit_refused(self):
        with self.assertRaises(ValueError):E.load_audit(b'',{'compiled':'/fixture'},[])
    def test_budget_covers_every_sequential_bound(self):
        rebuild=90+600+90+1800+300+180+180
        self.assertEqual(rebuild,3240)
        native=2*rebuild+16*30+3*60;self.assertEqual(native,7140)
        total=native+33*30+3*30+120+900+600;self.assertEqual(total,9840);self.assertLessEqual(total,165*60)
        self.assertLessEqual(2+3+20+165+5+1,200)
    def test_casefold_siblings_unique(self):
        for directory in [ROOT.parent,HERE,*[p for p in ROOT.rglob('*') if p.is_dir()]]:
            names=[p.name.casefold() for p in directory.iterdir()];self.assertEqual(len(names),len(set(names)),str(directory))

def run_all():
    commands=[[sys.executable,str(__file__),'-v'],[sys.executable,str(HERE/'test-replay-evidence.py')],[sys.executable,str(HERE/'test-object-hash-transport.py'),'-v']]
    commands += [[sys.executable,str(EXP/'scripts'/name),'--check'] for name in ('generate.py','generate_host.py','generate_native_forms.py','pins.py')]
    commands += [[sys.executable,'-m','unittest','discover','-s',str(EXP/'tests'),'-v'],[sys.executable,str(EXP/'tests/test_probe.py'),'-v']]
    helper_tests=HERE/'object-hash-native/test_helpers.py'
    if helper_tests.exists():commands.append([sys.executable,str(helper_tests),'-v'])
    for command in commands:
        print('PORTABLE_COMMAND '+json.dumps(command),flush=True)
        subprocess.run(command,cwd=EXP,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},check=True,timeout=90)
    return 0
if __name__=='__main__':
    if sys.argv[1:]==['--all']:raise SystemExit(run_all())
    unittest.main()
