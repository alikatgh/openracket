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
        a=self.arm();c=pathlib.Path(a['runtime']);target=c/'collects/info-cache.rktd';a['metadata_paths']=[str(target)];target.write_bytes(b'old');before=C.tree(c);C.quarantine(a);target.write_bytes(b'new');self.assertTrue(C.source_unchanged(before,C.tree(c),a))
    def test_new_installed_directory_outside_metadata_ancestors_refused(self):
        a=self.arm();c=pathlib.Path(a['runtime']);before=C.tree(c);(c/'bin/unexpected').mkdir()
        with self.assertRaises(ValueError):C.source_unchanged(before,C.tree(c),a)
    def test_original_tree_detects_modes_links_bytes(self):
        (self.root/'f').write_text('x');before=C.tree(self.root);(self.root/'f').chmod(0o600);self.assertNotEqual(before,C.tree(self.root))
class ConfigRepresentationTests(TempCase):
    def fixture(self):
        a=self.arm();c=pathlib.Path(a['runtime']);p=C.profile(a,'profile-inventory');w=pathlib.Path(a['work'])
        target=c/'collects/racket/private/class-internal.rkt';target.parent.mkdir(parents=True);shutil.copyfile(EXP/'vendor/class-internal.rkt',target)
        (c/'share/pkgs/base').mkdir(parents=True);(c/'share/links.rktd').write_text('()')
        raw=str(c/'collects/../share/links.rktd');root=str(c/'share/pkgs/base')
        v={'schema':'object-hash-config/v1','runtime_root':str(c),'probe_root':a['package'],'helper_root':str(w/'ci'),'compiled_root':a['compiled'],'profile_root':str(p),'compiled_roots':[a['compiled']],'compiled_subdirs':[],'unclassified_config':[],
           'resolved_class_source':{'path':str(target),'sha256':C.ORIGINAL_CLASS},'collections':[str(c/'collects')+'/'],
           'paths':[{'label':'find-collects-dir','role':'source','path':str(c/'collects'),'raw_path':str(c/'collects')+'/'},{'label':'links-file','role':'link','path':str(c/'share/links.rktd'),'raw_path':raw}],
           'collection_links':[{'kind':'splice'},{'kind':'file','path':raw}],
           'links':[{'path':raw,'ordinary':[{'name':'base','path':root}],'roots':[root],'all_entries':[{'path':str(c/'collects/../share/pkgs/base')}]},{'path':str(p/'addon/9.3/links.rktd'),'ordinary':[],'roots':[],'all_entries':[]}],
           'config_files':[{'path':str(c/'etc/config.rktd')},{'path':str(p/'addon/etc/config.rktd')}]}
        return a,p,v
    def test_observed_trailing_collects_and_parent_relative_links(self):
        a,p,v=self.fixture();original=copy.deepcopy(v);self.assertEqual(C.validate_config(v,a,p),[str(pathlib.Path(a['runtime'])/'collects')]);self.assertEqual(v,original)
    def test_canonical_config_shape_still_passes(self):
        a,p,v=self.fixture();v['collections'][0]=v['collections'][0].rstrip('/');v['collection_links'][1]['path']=str(pathlib.Path(a['runtime'])/'share/links.rktd');v['links'][0]['path']=v['collection_links'][1]['path'];self.assertTrue(C.validate_config(v,a,p))
    def test_extra_collection_order_preserved(self):
        a,p,v=self.fixture();extra=pathlib.Path(a['runtime'])/'extra';extra.mkdir();v['collections']=[str(extra)+'/',v['collections'][0]];self.assertEqual(C.validate_config(v,a,p),[str(extra),str(pathlib.Path(a['runtime'])/'collects')])
    def test_safe_collection_parent_spelling(self):
        a,p,v=self.fixture();v['collections']=[str(pathlib.Path(a['runtime'])/'share/../collects')+'/'];self.assertTrue(C.validate_config(v,a,p))
    def test_collection_link_table_safe_spelling(self):
        a,p,v=self.fixture();v['collection_links'].append({'kind':'table','entries':[{'paths':[str(pathlib.Path(a['runtime'])/'collects/../share/pkgs/base')]}]});self.assertTrue(C.validate_config(v,a,p))
    def test_collection_escape_then_reentry_refused(self):
        a,p,v=self.fixture();c=pathlib.Path(a['runtime']);v['collections']=[str(c/'../runtime/collects')]
        with self.assertRaises(ValueError):C.validate_config(v,a,p)
    def test_internal_link_parent_cancellation_refused(self):
        a,p,v=self.fixture();c=pathlib.Path(a['runtime']);(c/'alias').symlink_to(c/'share',target_is_directory=True);v['collection_links'][1]['path']=str(c/'alias/../share/links.rktd')
        with self.assertRaises(ValueError):C.validate_config(v,a,p)
    def test_external_alias_into_owned_root_refused(self):
        a,p,v=self.fixture();alias=self.root/'alias-runtime';alias.symlink_to(a['runtime'],target_is_directory=True);v['collections']=[str(alias/'collects')]
        with self.assertRaises(ValueError):C.validate_config(v,a,p)
    def test_dangling_link_destination_refused(self):
        a,p,v=self.fixture();target=p/'addon/9.3';target.symlink_to(p/'missing',target_is_directory=True)
        with self.assertRaises(ValueError):C.validate_config(v,a,p)
    def test_every_raw_link_surface_rejects_outside_root(self):
        a,p,v=self.fixture()
        for surface in ('collection-file','table','link-file','ordinary','root','all-entry','config-file'):
            x=copy.deepcopy(v);outside=str(self.root/'outside')
            if surface=='collection-file':x['collection_links'][1]['path']=outside
            elif surface=='table':x['collection_links']=[{'kind':'table','entries':[{'paths':[outside]}]}]
            elif surface=='link-file':x['links'][0]['path']=outside
            elif surface=='ordinary':x['links'][0]['ordinary'][0]['path']=outside
            elif surface=='root':x['links'][0]['roots']=[outside]
            elif surface=='all-entry':x['links'][0]['all_entries'][0]['path']=outside
            else:x['config_files'][0]['path']=outside
            with self.subTest(surface=surface),self.assertRaises(ValueError):C.validate_config(x,a,p)
    def test_exact_roots_sole_cache_and_class_pin_stay_strict(self):
        a,p,v=self.fixture()
        for key in ('runtime_root','compiled_roots','class-sha'):
            x=copy.deepcopy(v)
            if key=='runtime_root':x[key]+='/'
            elif key=='compiled_roots':x[key].append('same')
            else:x['resolved_class_source']['sha256']='0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):C.validate_config(x,a,p)

class QuarantinePhaseTests(TempCase):
    def fixture(self):
        a=self.arm();c=pathlib.Path(a['runtime']);d=c/'collects/acks/compiled';d.mkdir(parents=True)
        for name in ('acks_rkt.dep','acks_rkt.zo'):(d/name).write_bytes(name.encode())
        a['initial_before']=C.tree(c);return a,c,a['initial_before']
    def test_unprocessed_clone_and_failed_config_keep_exact_old_products(self):
        a,c,b=self.fixture();self.assertTrue(C.source_unchanged(b,C.tree(c),a));self.assertTrue((c/'collects/acks/compiled/acks_rkt.dep').exists())
    def test_unprocessed_clone_mutation_is_not_skipped(self):
        a,c,b=self.fixture();(c/'bin/racket').write_text('changed')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_pre_quarantine_metadata_change_is_refused(self):
        a,c,b=self.fixture();p=c/'collects/cache.rktd';a['metadata_paths']=[str(p)];p.write_text('new')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_pre_quarantine_removed_bytecode_is_refused(self):
        a,c,b=self.fixture();(c/'collects/acks/compiled/acks_rkt.dep').unlink()
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_phase_record_failure_before_first_move_retains_baseline(self):
        a,c,b=self.fixture()
        with self.assertRaises(OSError):C.quarantine(a,lambda event:(_ for _ in ()).throw(OSError('journal failed')))
        self.assertEqual(a['quarantine_state']['phase'],'in-progress');self.assertTrue(C.source_unchanged(b,C.tree(c),a))
    def test_intent_record_failure_does_not_move_source(self):
        a,c,b=self.fixture()
        def persist(event):
            if event['event']=='intent':raise OSError('intent persistence failed')
        with self.assertRaises(OSError):C.quarantine(a,persist)
        self.assertEqual(len(a['quarantine_state']['moves']),1);self.assertTrue(C.source_unchanged(b,C.tree(c),a));self.assertEqual(C.tree(c),b)
    def test_rename_failure_retains_recorded_intent(self):
        a,c,b=self.fixture()
        with patch.object(pathlib.Path,'rename',side_effect=OSError('rename failed')),self.assertRaises(OSError):C.quarantine(a)
        self.assertEqual(a['quarantine_state']['moves'][0]['state'],'intent');self.assertTrue(C.source_unchanged(b,C.tree(c),a))
    def test_partial_move_then_failure_preserves_remaining_products(self):
        a,c,b=self.fixture()
        def persist(event):
            if event['event']=='moved':raise OSError('completion record failed')
        with self.assertRaises(OSError):C.quarantine(a,persist)
        self.assertEqual(a['quarantine_state']['phase'],'in-progress');self.assertTrue(C.source_unchanged(b,C.tree(c),a));self.assertEqual(len(a['quarantine_state']['moves']),1)
    def test_rename_completed_before_exception_is_reconciled_from_intent(self):
        a,c,b=self.fixture();rename=pathlib.Path.rename
        def uncertain(path,target):rename(path,target);raise OSError('rename result uncertain')
        with patch.object(pathlib.Path,'rename',uncertain),self.assertRaises(OSError):C.quarantine(a)
        self.assertEqual(a['quarantine_state']['moves'][0]['state'],'intent');self.assertTrue(C.source_unchanged(b,C.tree(c),a))
    def test_partial_unrecorded_deletion_refused(self):
        a,c,b=self.fixture()
        with patch.object(pathlib.Path,'rename',side_effect=OSError('rename failed')),self.assertRaises(OSError):C.quarantine(a)
        (c/'collects/acks/compiled/acks_rkt.zo').unlink()
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_quarantined_bytes_changed_refused(self):
        a,c,b=self.fixture();C.quarantine(a);pathlib.Path(a['quarantine_state']['moves'][0]['quarantine']).write_bytes(b'changed')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_unrecorded_quarantine_product_refused(self):
        a,c,b=self.fixture();C.quarantine(a);(pathlib.Path(a['quarantine'])/'unexpected').write_bytes(b'new')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_partial_unmoved_metadata_mutation_refused(self):
        a,c,b=self.fixture();target=c/'collects/z-info-cache.rktd';target.write_bytes(b'old');a['metadata_paths']=[str(target)];b=C.tree(c)
        def persist(event):
            if event['event']=='moved':raise OSError('stop after first move')
        with self.assertRaises(OSError):C.quarantine(a,persist)
        target.write_bytes(b'changed')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_partial_moved_metadata_reappearance_refused(self):
        a,c,b=self.fixture();target=c/'collects/a-info-cache.rktd';target.write_bytes(b'old');a['metadata_paths']=[str(target)];b=C.tree(c)
        def persist(event):
            if event['event']=='moved':raise OSError('stop after first move')
        with self.assertRaises(OSError):C.quarantine(a,persist)
        target.write_bytes(b'regenerated')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_partial_new_declared_metadata_refused(self):
        a,c,b=self.fixture();target=c/'collects/new-cache.rktd';a['metadata_paths']=[str(target)]
        with patch.object(pathlib.Path,'rename',side_effect=OSError('rename failed')),self.assertRaises(OSError):C.quarantine(a)
        target.write_bytes(b'new')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_complete_quarantine_and_build_failure_use_post_rule(self):
        a,c,b=self.fixture();events=[];C.quarantine(a,lambda event:events.append(copy.deepcopy(event)));self.assertTrue(C.source_unchanged(b,C.tree(c),a));self.assertEqual([e['event'] for e in events],['phase','intent','moved','intent','moved','phase']);self.assertEqual(a['quarantine_state']['phase'],'complete')
        (c/'collects/acks/compiled/acks_rkt.zo').write_bytes(b'reappeared')
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_baseline_metadata_disappearance_before_quarantine_cannot_hide(self):
        a,c,b=self.fixture();target=c/'collects/info-cache.rktd';target.write_bytes(b'old');a['metadata_paths']=[str(target)];b=C.tree(c);target.unlink();C.quarantine(a)
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_complete_missing_quarantine_product_refused(self):
        a,c,b=self.fixture();C.quarantine(a);pathlib.Path(a['quarantine_state']['moves'][0]['quarantine']).unlink()
        with self.assertRaises(ValueError):C.source_unchanged(b,C.tree(c),a)
    def test_final_phase_persistence_failure_keeps_complete_move_proof(self):
        a,c,b=self.fixture()
        def persist(event):
            if event.get('phase')=='complete':raise OSError('final phase persistence failed')
        with self.assertRaises(OSError):C.quarantine(a,persist)
        self.assertEqual(a['quarantine_state']['phase'],'complete');self.assertTrue(C.source_unchanged(b,C.tree(c),a))
    def test_exact_overlay_checked_before_new_baseline(self):
        a,c,b=self.fixture();target=c/'collects/racket/private/class-internal.rkt';target.parent.mkdir(parents=True);shutil.copyfile(EXP/'vendor/class-internal.rkt',target);a['initial_before']=C.tree(c);a['purpose']='object-hash-diagnostic';target.write_bytes((EXP/'generated/class-internal.rkt').read_bytes());self.assertTrue(C.accept_overlay(a,C.tree(c)));self.assertTrue(C.source_unchanged(a['immutable_before'],C.tree(c),a))
    def test_overlay_additional_mutation_refused(self):
        a,c,b=self.fixture();(c/'bin/racket').write_text('changed')
        with self.assertRaises(ValueError):C.accept_overlay(a,C.tree(c))
        self.assertNotIn('immutable_before',a)

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
class RunFailureStageTests(TempCase):
    def run_failure(self,stage,mutate_unprocessed=False,transport_failure=False):
        r=load('object_hash_failure_runner','run-object-hash.py');r.ROOT=self.root/'checkout';r.ROOT.mkdir()
        runtime=self.root/'install/racket';(runtime/'bin').mkdir(parents=True);(runtime/'etc').mkdir();(runtime/'bin/racket').write_text('fixture')
        target=runtime/'collects/racket/private/class-internal.rkt';target.parent.mkdir(parents=True);shutil.copyfile(EXP/'vendor/class-internal.rkt',target)
        compiled=runtime/'collects/acks/compiled';compiled.mkdir(parents=True)
        for name in ('acks_rkt.dep','acks_rkt.zo'):(compiled/name).write_bytes(name.encode())
        original=C.tree(runtime);calls=[]
        def command(sup,name,argv,env,cwd,timeout,host=False):
            calls.append(name);out=sup.reports/name;out.mkdir();passed=not(stage=='build' and name=='stock-core')
            row={'passed':passed,'returncode':0 if passed else 1,'cleanup_verified':True};(out/'stdout.bin').write_text(json.dumps({'paths':[]}));(out/'stderr.bin').write_bytes(b'');(out/'process.json').write_text(json.dumps(row))
            if mutate_unprocessed and name=='stock-config':(self.root/'object-hash-diagnostic/runtime/bin/racket').write_text('unprocessed mutation')
            return row,out
        def config(v,a,p):
            if stage=='config':raise ValueError('simulated config rejection')
            return [str(pathlib.Path(a['runtime'])/'collects')]
        quarantine=r.contract.quarantine
        def partial(arm,persist):
            def event(row):
                persist(row)
                if row['event']=='moved':raise OSError('simulated interrupted quarantine')
            return quarantine(arm,event)
        env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'alikatgh/openracket','GITHUB_REF':'refs/heads/prototype/retained-drracket','RUNNER_TEMP':str(self.root),'OPENRACKET_CI_STOCK_RACKET':str(runtime/'bin/racket')}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,env,clear=True));stack.enter_context(patch.object(sys,'argv',['run-object-hash.py','run']));stack.enter_context(patch.object(r.platform,'system',lambda:'Darwin'));stack.enter_context(patch.object(r.supervisor.Supervisor,'run',command));stack.enter_context(patch.object(r.contract,'validate_config',config));stack.enter_context(patch.object(r.transport_module,'emit_bundle',return_value={'complete':True}));stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if stage=='partial':stack.enter_context(patch.object(r.contract,'quarantine',partial))
            if transport_failure:stack.enter_context(patch.object(r.transport_module,'build_bundle',side_effect=ValueError('Compressed evidence exceeds unchanged cap')))
            code=r.main()
        self.assertEqual(code,1);self.assertEqual(C.tree(runtime),original)
        reports=r.ROOT/'reports/object-hash-ci';results=json.loads((reports/'results.json').read_text());self.assertFalse(results['passed']);self.assertTrue(next(x for x in results['checks'] if x['name']=='Full original runtime witness')['passed'])
        self.assertEqual(calls,['portable-source-adapter-transport','stock-config']+(['stock-core'] if stage=='build' else []))
        for arm in ('stock','diagnostic'):
            self.assertTrue((reports/(arm+'-after-execution-witness.json')).exists());self.assertTrue((reports/(arm+'-compiled-after-execution-witness.json')).exists())
        return reports,results
    def test_config_failure_checks_both_exact_pre_quarantine_baselines(self):
        reports,results=self.run_failure('config');checks={x['name']:x for x in results['checks']}
        self.assertTrue(checks['stock immutable source/config/link witness']['passed']);self.assertTrue(checks['diagnostic immutable source/config/link witness']['passed']);self.assertEqual(checks['diagnostic immutable source/config/link witness']['details']['baseline'],'initial-clone')
        self.assertEqual(json.loads((reports/'stock-quarantine-final.json').read_text())['phase'],'pre-quarantine')
    def test_unprocessed_arm_mutation_marks_final_gate_red(self):
        reports,results=self.run_failure('config',True);self.assertTrue(any(x['name']=='Clone/source witness' and not x['passed'] for x in results['checks']));self.assertFalse(any(x['name']=='diagnostic immutable source/config/link witness' and x['passed'] for x in results['checks']))
    def test_partial_quarantine_failure_keeps_raw_journal_and_moves(self):
        reports,results=self.run_failure('partial');state=json.loads((reports/'stock-quarantine-final.json').read_text());self.assertEqual(state['phase'],'in-progress');self.assertEqual(len(state['moves']),1);events=[json.loads(line) for line in (reports/'stock-quarantine-events.jsonl').read_text().splitlines()];self.assertEqual([e['event'] for e in events],['phase','intent','moved']);self.assertTrue(next(x for x in results['checks'] if x['name']=='stock immutable source/config/link witness')['passed'])
    def test_journal_transport_refusal_preserves_evidence_and_incomplete_status(self):
        reports,results=self.run_failure('partial',transport_failure=True)
        failure=json.loads((reports/'transport-failure.json').read_text());self.assertTrue(failure['all_original_evidence_retained_locally']);self.assertTrue(failure['interpretation_blocked']);self.assertFalse(json.loads((reports/'final-status.json').read_text())['transport_complete']);self.assertTrue((reports/'stock-quarantine-events.jsonl').is_file());self.assertTrue((reports/'stock-quarantine-final.json').is_file())
    def test_core_failure_uses_completed_quarantine_witness(self):
        reports,results=self.run_failure('build');state=json.loads((reports/'stock-quarantine-final.json').read_text());self.assertEqual(state['phase'],'complete');self.assertEqual(len(state['moves']),2);self.assertTrue(next(x for x in results['checks'] if x['name']=='stock immutable source/config/link witness')['passed'])

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

def estimate_quarantine_transport():
    # Extend the existing synthetic model without changing the runtime codec.
    # Counts/hashes are synthetic; 8,192 moves per arm are not native observations.
    t=load('object_hash_transport_estimate','test-object-hash-transport.py');build=t.T.build_bundle
    def with_journals(paths,reports,output):
        def put(name,data):
            path=reports/name;path.write_bytes(data);paths.append(path)
        for arm in ('stock','diagnostic'):
            base='/synthetic/object-hash-'+arm;rows=[];events=[{'event':'phase','phase':'in-progress'}];changed=[]
            for index in range(8192):
                relative='share/pkgs/synthetic-'+str(index//2)+'/compiled/module_rkt'+('.zo' if index%2 else '.dep')
                digest=hashlib.sha256((arm+str(index)).encode()).hexdigest();before=['file',420,1024+index,digest]
                row={'path':base+'/runtime/'+relative,'quarantine':base+'/quarantine/'+relative,'bytes':before[2],'sha256':digest,'device':1,'inode':index+1,'before':before,'state':'intent'}
                events.extend([{'event':'intent','move':copy.deepcopy(row)},{'event':'moved','path':row['path']}]);row['state']='moved';rows.append(row);changed.append({'path':relative,'before':before,'after':None})
            events.append({'event':'phase','phase':'complete'})
            state={'schema':'object-hash-quarantine/v1','phase':'complete','moves':rows}
            put(arm+'-quarantine-events.jsonl',b''.join(json.dumps(event,sort_keys=True,separators=(',',':')).encode()+b'\n' for event in events))
            for ending in ('-quarantine.json','-quarantine-final.json'):put(arm+ending,json.dumps(state,sort_keys=True).encode()+b'\n')
            put(arm+'-after-build-witness.json',json.dumps({'schema':'object-hash-tree-witness/v1','synthetic_only':True,'changed_count':len(changed),'changed_entries':changed},sort_keys=True).encode()+b'\n')
        return build(paths,reports,output)
    captured=io.StringIO()
    with patch.object(t.T,'build_bundle',with_journals),contextlib.redirect_stdout(captured):t.estimate()
    result=json.loads(captured.getvalue());result['quarantine_moves_per_arm']=8192;result['includes_complete_intent_completion_journals_and_final_states']=True;result['includes_all_synthetic_removed_product_witness_entries']=True
    print(json.dumps(result,sort_keys=True))

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
    if sys.argv[1:]==['--estimate-quarantine']:estimate_quarantine_transport();raise SystemExit(0)
    unittest.main()
