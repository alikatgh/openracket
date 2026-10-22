import contextlib,io,copy,hashlib,importlib.util,json,lzma,os,pathlib,signal,struct,sys,tempfile,types,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import source_bundle as bundle
import bootstrap as boot
import run_native_ci as runner
TEST_SOURCE=pathlib.Path(os.environ.get("OPENRACKET_ADAPTER_TEST_SOURCE",str(HERE.parent/"source"))).resolve(strict=True)
runner.SOURCE=TEST_SOURCE

class BundleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name).resolve();self.source=self.root/'source';self.source.mkdir()
  (self.source/'one.py').write_bytes(b'print(1)\n');self.rows=[{'path':'one.py','bytes':9,'sha256':hashlib.sha256(b'print(1)\n').hexdigest(),'mode':0o444}];self.manifest={'files':self.rows}
 def tearDown(self):
  for p in self.root.rglob('*'):
   if p.is_dir():p.chmod(0o700)
  self.temp.cleanup()
 def build(self):
  target=self.root/'source.xz';pin=bundle.build(self.source,self.manifest,target);return target,pin
 def corrupted(self,raw):
  p=self.root/'bad.xz';p.write_bytes(raw);return p,{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
 def test_roundtrip_and_fresh_destination(self):
  p,pin=self.build();dest=self.root/'out';result=bundle.extract(p,self.manifest,pin,dest)
  self.assertEqual((dest/'one.py').read_bytes(),b'print(1)\n');self.assertTrue(result['materialized_readonly']);self.assertEqual((dest/'one.py').stat().st_mode&0o777,0o444)
  with self.assertRaises(ValueError):bundle.extract(p,self.manifest,pin,dest)
 def test_deterministic(self):
  p,pin=self.build();other=self.root/'second.xz';again=bundle.build(self.source,self.manifest,other);self.assertEqual(pin['sha256'],again['sha256'])
 def test_paths_duplicates_casefold_modes_and_size(self):
  for path in ('/absolute','../escape','a/../b','a//b','a\\b','a\x00b','trailing.'):
   m=copy.deepcopy(self.manifest);m['files'][0]['path']=path
   with self.subTest(path=path),self.assertRaises(ValueError):bundle.members(m)
  for change in ({'mode':0o777},{'mode':0o120777},{'bytes':bundle.MAX_FILE+1},{'sha256':'x'*64}):
   m=copy.deepcopy(self.manifest);m['files'][0].update(change)
   with self.assertRaises(ValueError):bundle.members(m)
  for name in ('one.py','ONE.py'):
   m=copy.deepcopy(self.manifest);m['files'].append({**self.rows[0],'path':name})
   with self.assertRaises(ValueError):bundle.members(m)
 def test_stream_trailing_concat_truncate_hash_and_extra_payload(self):
  p,pin=self.build();raw=p.read_bytes();plain=lzma.decompress(raw)
  for bad in (raw+b'trailing',raw+raw,raw[:-1],lzma.compress(plain+b'extra'),lzma.compress(plain[:-1]+b'x')):
   q,qp=self.corrupted(bad)
   with self.assertRaises(ValueError):bundle.extract(q,self.manifest,qp,self.root/'out')
   self.assertFalse((self.root/'out').exists())
 def test_manifest_mode_and_member_changes(self):
  p,pin=self.build();m=copy.deepcopy(self.manifest);m['files'][0]['mode']=0o555
  with self.assertRaises(ValueError):bundle.extract(p,m,pin,self.root/'out')
 def test_symlink_source_bundle_and_destination_parent(self):
  p,pin=self.build();link=self.root/'link';link.symlink_to(p)
  with self.assertRaises(ValueError):bundle.extract(link,self.manifest,pin,self.root/'out')
  parent=self.root/'alias';parent.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ValueError):bundle.extract(p,self.manifest,pin,parent/'out')
 def test_oversize_decode_refused(self):
  q,pin=self.corrupted(lzma.compress(b'x'*(bundle.MAX_TOTAL+bundle.MAX_MANIFEST+100)))
  with self.assertRaises(ValueError):bundle.extract(q,self.manifest,pin,self.root/'out')

class PartTests(unittest.TestCase):
 def test_actual_parts_and_tamper_closure(self):
  base=HERE.parent;mapping=json.loads((base/'SOURCE-PARTS.json').read_bytes());raw=bundle.read_parts((base/'source-parts').resolve(),mapping)
  self.assertEqual(len(raw),json.loads((base/'SOURCE-BUNDLE.json').read_bytes())['bytes'])
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();import shutil
   shutil.copytree(base/'source-parts',root/'parts');parts=root/'parts'
   (parts/'extra.bin').write_bytes(b'x')
   with self.assertRaises(ValueError):bundle.read_parts(parts,mapping)
   (parts/'extra.bin').unlink();first=parts/'source-000.bin';saved=first.read_bytes();first.write_bytes(saved[:-1])
   with self.assertRaises(ValueError):bundle.read_parts(parts,mapping)
   first.write_bytes(saved);m=copy.deepcopy(mapping);m['parts'].reverse()
   with self.assertRaises(ValueError):bundle.read_parts(parts,m)
class WitnessTests(unittest.TestCase):
 def test_false_witness_revokes_acceptance_and_sets_block(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();(root/'reports').mkdir();summary={'native_acceptance':'passed'}
   with patch.object(runner,'witness',return_value=False):runner.finish_run(types.SimpleNamespace(close=lambda:True,uncertain=False),root,summary)
   self.assertFalse(summary['final_witness_passed']);self.assertIn('error',summary);self.assertFalse(json.loads((root/'launch-state.json').read_bytes())['safe_to_continue'])
 def test_close_failure_blocks_even_with_good_filesystem_witness(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();(root/'reports').mkdir();summary={'native_acceptance':'passed'}
   with patch.object(runner,'witness',return_value=True):runner.finish_run(types.SimpleNamespace(close=lambda:False,uncertain=False),root,summary)
   self.assertIn('error',summary);self.assertFalse(json.loads((root/'launch-state.json').read_bytes())['safe_to_continue'])
 def test_final_witness_write_or_print_error_still_transports(self):
  for error in (OSError('write failed'),BrokenPipeError('print failed')):
   with patch.object(runner,'witness',side_effect=error),patch.object(runner,'transport',return_value=True) as transport:
    self.assertEqual(runner.finalize(pathlib.Path('/unread-placeholder')),1);transport.assert_called_once()
 def test_one_failed_domain_does_not_suppress_others(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();(root/'reports').mkdir();(root/'diagnostic').mkdir();(root/'acceptance').mkdir()
   calls=[]
   with patch.object(runner,'projection',side_effect=lambda:calls.append('projection') or {'files':[]}),patch.object(runner,'verify_sources',side_effect=lambda *x:calls.append(x[0].name)):
    self.assertFalse(runner.witness(root,'test'))
   self.assertEqual(calls,['projection','diagnostic','acceptance'])

class InventoryTransportTests(unittest.TestCase):
 def setUp(self):
  self.codec=runner.load_exact(HERE/'vendor/object-hash-transport.py','inventory_summary_codec','60bdeb6da27b752f663215f97080cb3bba8cee64f60a841636312c26223a2f53')
 def test_summary_keeps_exact_raw_digest_without_inventory_rows(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();runtime=root/'runtime';runtime.mkdir();(runtime/'public-input').write_text('known')
   original=runner.tree(runtime);p=root/'baseline.json';boot.durable(p,original);raw=p.read_bytes()
   summary=runner.runtime_inventory_summary(p,self.codec)
   self.assertTrue(summary['complete']);self.assertFalse(summary['full_inventory_transported'])
   self.assertEqual(summary['raw_bytes'],len(raw));self.assertEqual(summary['raw_sha256'],hashlib.sha256(raw).hexdigest())
   self.assertEqual(summary['entry_count'],len(original['entries']));self.assertEqual(summary['tree_sha256'],original['tree_sha256'])
   self.assertNotIn('entries',summary);self.assertEqual(p.read_bytes(),raw)
 def test_invalid_missing_and_linked_baseline_stay_incomplete(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();p=root/'baseline.json'
   self.assertFalse(runner.runtime_inventory_summary(p,self.codec)['complete'])
   p.write_bytes(b'{broken');r=runner.runtime_inventory_summary(p,self.codec)
   self.assertFalse(r['complete']);self.assertEqual(r['raw_sha256'],boot.sha(p))
   p.unlink();p.symlink_to(root/'outside');self.assertFalse(runner.runtime_inventory_summary(p,self.codec)['complete'])
   p.unlink();p.write_text('{}');os.link(p,root/'hardlink');self.assertFalse(runner.runtime_inventory_summary(p,self.codec)['complete'])
   (root/'hardlink').unlink();p.write_text('{"schema":1,"schema":2}');self.assertFalse(runner.runtime_inventory_summary(p,self.codec)['complete'])
 def test_real_transport_omits_only_baseline_and_retains_all_changes_and_failure_bytes(self):
  codec=runner.load_exact(HERE/'vendor/object-hash-transport.py','inventory_test_codec','60bdeb6da27b752f663215f97080cb3bba8cee64f60a841636312c26223a2f53')
  for malformed in (False,True):
   with tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d).resolve();reports=root/'reports';reports.mkdir();runtime=root/'runtime';runtime.mkdir()
    for i in range(50):(runtime/('file-%d'%i)).write_text('before')
    before=runner.tree(runtime);baseline=reports/'original-runtime-before.json';boot.durable(baseline,before)
    for i in range(50):(runtime/('file-%d'%i)).write_text('after')
    _,comparison=runner.compare_tree(before,runtime);boot.durable(reports/'final-comparison.json',comparison)
    raw=b'compiler failure\x00\xff\n';(reports/'failure.stderr').write_bytes(raw)
    cleanup=b'{"safe_to_continue":false,"cleanup":{"group_quiescent":false}}\n';(reports/'cleanup.json').write_bytes(cleanup)
    if malformed:baseline.write_bytes(b'{broken')
    saved=baseline.read_bytes();output=io.StringIO()
    with contextlib.redirect_stdout(output):complete=runner.transport(root)
    self.assertEqual(complete,not malformed);self.assertEqual(baseline.read_bytes(),saved)
    envelope=codec.envelope_from_log(output.getvalue());restored=root/'restored';codec.decode_verified(envelope,restored)
    self.assertFalse((restored/'original-runtime-before.json').exists())
    self.assertEqual((restored/'failure.stderr').read_bytes(),raw)
    self.assertEqual((restored/'cleanup.json').read_bytes(),cleanup)
    self.assertEqual(json.loads((restored/'final-comparison.json').read_bytes()),comparison)
    self.assertEqual(len(comparison['changed_entries']),50)
    summary=json.loads((restored/'original-runtime-summary.json').read_bytes())
    self.assertEqual(summary['complete'],not malformed);self.assertEqual(summary['raw_sha256'],hashlib.sha256(saved).hexdigest())

class BootstrapTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name).resolve();self.source=TEST_SOURCE/'ci/supervisor/darwin_process_inventory.c';self.compiler=pathlib.Path(sys.executable).resolve();self.sdk=self.root/'sdk';self.sdk.mkdir();self.report=self.root/'report';self.report.mkdir();self.started=False;self.kills=[];self.reaped=False
 def tearDown(self):self.temp.cleanup()
 def run_fake(self,code=0,bad_inventory=False,timeout=5,fail_owned=False):
  identity=types.SimpleNamespace(pgid=42424,dead=True,start='fake-birth')
  inventory=types.SimpleNamespace(pids=lambda:{42424},identity=lambda pid:identity)
  def loader(path,digest):
   if bad_inventory:raise RuntimeError('injected helper load refusal')
   return inventory
  module=types.SimpleNamespace(_DarwinSDKInventory=loader)
  real_durable=boot.durable
  def write_receipt(path,value,**kwargs):
   if fail_owned and value.get('phase')=='owned':raise OSError('injected owned lease persistence failure')
   return real_durable(path,value,**kwargs)
  def write(fd,raw):
   self.started=True;(self.report/'openracket_process_inventory.dylib').write_bytes(b'fake-test-only');return len(raw)
  def observe(pid):return types.SimpleNamespace(si_code=os.CLD_EXITED,si_status=code) if self.started or self.kills else None
  def reap(pid,opt):self.reaped=True;return pid,code<<8
  def kill(pid,sig):
   if self.reaped:raise AssertionError('signal after reap')
   self.kills.append((pid,sig))
  with patch.object(boot.sys,'platform','darwin'),patch.object(boot.sys,'version_info',(3,13)),patch.object(boot.os,'fork',return_value=42424),patch.object(boot.os,'getpgid',return_value=42424),patch.object(boot.os,'getsid',return_value=42424),patch.object(boot.os,'waitid',side_effect=lambda *a:observe(a[1])),patch.object(boot.os,'waitpid',side_effect=reap),patch.object(boot.os,'killpg',side_effect=kill),patch.object(boot.os,'kill',side_effect=kill),patch.object(boot.os,'read',return_value=b'R'),patch.object(boot.os,'write',side_effect=write),patch.object(boot.select,'select',side_effect=lambda r,w,e,t:(r,[],[])),patch.object(boot.time,'sleep'),patch.object(boot,'durable',side_effect=write_receipt):
   return boot.bootstrap(module,self.source,self.compiler,self.sdk,None,self.report,{},timeout=timeout)
 def test_success_handoff_keeps_anchor_until_inventory(self):
  path,digest,row=self.run_fake();self.assertTrue(row['safe_to_continue']);self.assertTrue(row['leader_reaped']);self.assertTrue(row['group_quiescent']);self.assertEqual(self.kills,[]);self.assertTrue(json.loads((self.report/'launch-blocked.json').read_bytes())['safe_to_continue'])
 def test_nonzero_is_permanent_block_even_after_reap(self):
  with self.assertRaises(RuntimeError):self.run_fake(code=1)
  row=json.loads((self.report/'bootstrap-receipt.json').read_bytes());self.assertFalse(row['safe_to_continue']);self.assertFalse(row['group_quiescent']);self.assertTrue(row['leader_reaped']);self.assertEqual([s for _,s in self.kills],[signal.SIGTERM,signal.SIGKILL])
 def test_loader_failure_blocks_and_preserves_output(self):
  with self.assertRaises(RuntimeError):self.run_fake(bad_inventory=True)
  row=json.loads((self.report/'launch-blocked.json').read_bytes());self.assertFalse(row['safe_to_continue']);self.assertTrue((self.report/'openracket_process_inventory.dylib').is_file())
 def test_timeout_before_readiness_never_releases_gate(self):
  with self.assertRaises(TimeoutError):self.run_fake(timeout=0)
  self.assertFalse(self.started);row=json.loads((self.report/'launch-blocked.json').read_bytes());self.assertFalse(row['safe_to_continue']);self.assertTrue(row['leader_reaped'])
 def test_owned_receipt_failure_never_releases_gate(self):
  with self.assertRaises(OSError):self.run_fake(fail_owned=True)
  self.assertFalse(self.started);self.assertFalse(json.loads((self.report/'launch-blocked.json').read_bytes())['safe_to_continue'])
 def test_stale_lease_refuses_before_fork(self):
  (self.report/'launch-blocked.json').write_text('{"safe_to_continue":false}')
  with patch.object(boot.sys,'platform','darwin'),patch.object(boot.sys,'version_info',(3,13)),patch.object(boot.os,'fork') as fork,self.assertRaises(FileExistsError):boot.bootstrap(None,self.source,self.compiler,self.sdk,None,self.report,{})
  fork.assert_not_called()
 def test_native_preflight_refuses_linux_before_lease(self):
  with patch.object(boot.sys,'platform','linux'),self.assertRaises(ValueError):boot.bootstrap(None,self.source,self.compiler,self.sdk,None,self.report,{})
  self.assertEqual(list(self.report.iterdir()),[])

class PublicInputTests(unittest.TestCase):
 def test_public_map_contains_only_distributed_files(self):
  manifest,pin,parts=runner.public_inputs()
  self.assertEqual(set(manifest),{'schema','files'})
  self.assertEqual(manifest['schema'],'openracket-public-source/v1')
  self.assertEqual(pin['members'],len(manifest['files']))
  self.assertEqual(pin['sha256'],parts['sha256'])
  self.assertEqual(pin['bytes'],parts['bytes'])
 def test_metadata_tampering_and_symlinks_fail_before_source_read(self):
  import shutil
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve()
   for name in runner.PUBLIC_INPUT_PINS:shutil.copyfile(HERE.parent/name,root/name)
   with patch.object(runner,'BASE',root):
    runner.public_inputs()
    for name in runner.PUBLIC_INPUT_PINS:
     p=root/name;saved=p.read_bytes();p.write_bytes(saved+b' ')
     with self.subTest(name=name),self.assertRaises(ValueError):runner.public_inputs()
     p.write_bytes(saved);p.rename(root/'saved');p.symlink_to(root/'saved')
     with self.assertRaises(ValueError):runner.public_inputs()
     p.unlink();(root/'saved').rename(p)
 def test_extra_metadata_fields_refused_even_in_rebound_fixture(self):
  import shutil
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve()
   for name in runner.PUBLIC_INPUT_PINS:shutil.copyfile(HERE.parent/name,root/name)
   manifest=json.loads((root/'PUBLIC-SOURCE.json').read_bytes());manifest['extra']={}
   p=root/'PUBLIC-SOURCE.json';p.write_text(json.dumps(manifest))
   pins={**runner.PUBLIC_INPUT_PINS,'PUBLIC-SOURCE.json':boot.sha(p)}
   with patch.object(runner,'BASE',root),patch.object(runner,'PUBLIC_INPUT_PINS',pins),self.assertRaisesRegex(ValueError,'schema'):runner.public_inputs()
 def test_projection_closure_bytes_and_mode_still_required(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve();source=root/'source';source.mkdir();p=source/'one.py';p.write_bytes(b'x');p.chmod(0o444);source.chmod(0o555)
   manifest={'files':[{'path':'one.py','bytes':1,'sha256':hashlib.sha256(b'x').hexdigest(),'mode':0o444}]}
   try:
    with patch.object(runner,'SOURCE',source),patch.object(runner,'public_inputs',return_value=(manifest,{},{})):
     self.assertEqual(runner.projection(),manifest)
     source.chmod(0o755);extra=source/'unlisted';extra.write_bytes(b'y');source.chmod(0o555)
     with self.assertRaisesRegex(ValueError,'Extra/missing'):runner.projection()
     source.chmod(0o755);extra.unlink();source.chmod(0o555);p.chmod(0o644)
     with self.assertRaisesRegex(ValueError,'mode'):runner.projection()
     p.write_bytes(b'y');p.chmod(0o444)
     with self.assertRaisesRegex(ValueError,'changed/missing'):runner.projection()
     source.chmod(0o755);p.unlink();source.chmod(0o555)
     with self.assertRaisesRegex(ValueError,'Extra/missing'):runner.projection()
   finally:source.chmod(0o755)

class ContractTests(unittest.TestCase):
 def test_source_projection_exact(self):self.assertEqual(len(runner.projection()['files']),1159)
 def test_inner_gate_and_bounds_remain_exact(self):
  source=TEST_SOURCE;mapping={x['path']:x for x in runner.public_inputs()[0]['files']}
  for name in ('ci/verify-native.sh','ci/build-native.sh','ci/bounded.py','ci/prepare-workcopy.py','cocoa/Main.mm'):
   self.assertEqual(boot.sha(source/name),mapping[name]['sha256'])
 def test_unverified_or_oversized_log_refuses_before_read(self):
  for record in ({'bytes':1,'sha256':None},{'bytes':64*1024*1024+1,'sha256':'0'*64}):
   with self.assertRaises(ValueError):runner.read_log({'logs':{'stdout.log':record}},'stdout.log')
 def test_runtime_same_path_replacement_refused(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d).resolve()/'runtime';root.mkdir();(root/'x').write_text('same');before=runner.tree(root);root.rename(root.with_name('old'));root.mkdir();(root/'x').write_text('same')
   with self.assertRaises(ValueError):runner.compare_tree(before,root,require_identity=True)
 def test_no_live_screenshot_launch_in_first_draft(self):
  text=(HERE/'run_native_ci.py').read_text();self.assertNotIn('capture_smoke.m',text);self.assertIn("'screenshots':'deferred",text)
 def test_existing_global_failure_blocks_before_launch(self):
  root=pathlib.Path(tempfile.mkdtemp()).resolve();(root/'launch-state.json').write_text('{"safe_to_continue":false}')
  fake=types.SimpleNamespace(run=lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not run')))
  try:
   with self.assertRaises(RuntimeError):runner.command(fake,root,'blocked',['/bin/true'],root,{},1)
  finally:
   import shutil;shutil.rmtree(root)
if __name__=='__main__':unittest.main(verbosity=2)
