import importlib.util,json,hashlib,os,pathlib,tempfile,unittest
p=pathlib.Path(__file__).with_name('app-ci-contract.py');s=importlib.util.spec_from_file_location('contract',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contracts(unittest.TestCase):
 def test_environment_clears_poison_and_experiments(self):
  parent={k:'poison' for k in c.FORBIDDEN};parent.update(OPENRACKET_INTERVAL_MAP_FAST_SET='1',OPENRACKET_UI='modern',HOME='/user',GITHUB_ACTIONS='true')
  e=c.environment(parent,pathlib.Path('/runtime/bin/racket'),pathlib.Path('/fresh'),pathlib.Path('/addon'),pathlib.Path('/cache'))
  self.assertEqual(e['HOME'],'/user');self.assertEqual(e['PLTUSERHOME'],'/fresh');self.assertEqual(e['PLTCOMPILEDROOTS'],'/cache:');self.assertFalse(any(k.startswith('OPENRACKET_') for k in e))
  for key in c.FORBIDDEN-{'PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','XDG_CACHE_HOME'}:self.assertNotIn(key,e)
 def test_snapshot_detects_same_bytes_mtime_and_directory_change(self):
  with tempfile.TemporaryDirectory() as t:
   r=pathlib.Path(t);f=r/'a';f.write_bytes(b'abc');a=c.snapshot(r);os.utime(f,ns=(f.stat().st_atime_ns,f.stat().st_mtime_ns+1000000));self.assertFalse(c.same_snapshot(a,c.snapshot(r))['unchanged'])
   a=c.snapshot(r);os.utime(r,ns=(r.stat().st_atime_ns,r.stat().st_mtime_ns+1000000));self.assertFalse(c.same_snapshot(a,c.snapshot(r))['unchanged'])
 def test_absent_symlink_mode_bytecode_and_unchanged(self):
  with tempfile.TemporaryDirectory() as t:
   r=pathlib.Path(t);self.assertEqual(c.snapshot(r/'missing'),{'.':['absent']});(r/'a.zo').write_bytes(b'compiled');(r/'link').symlink_to('a.zo');a=c.snapshot(r)
   self.assertTrue(c.same_snapshot(a,c.snapshot(r))['unchanged']);(r/'a.zo').chmod(0o700);self.assertFalse(c.same_snapshot(a,c.snapshot(r))['unchanged'])
   a=c.snapshot(r);(r/'link').unlink();(r/'link').symlink_to('missing');self.assertFalse(c.same_snapshot(a,c.snapshot(r))['unchanged'])
 def test_manifest_copy_verified_and_unlisted_excluded(self):
  with tempfile.TemporaryDirectory() as t:
   r=pathlib.Path(t);s=r/'s';s.mkdir();(s/'a').write_text('a');(s/'cache').write_text('do not copy');raw=json.dumps({'a':hashlib.sha256(b'a').hexdigest()}).encode();(s/'CONTENTS-SHA256.json').write_bytes(raw);pin=hashlib.sha256(raw).hexdigest()
   c.source_copy(s,r/'d',pin,1);self.assertFalse((r/'d/cache').exists())
   with self.assertRaises(ValueError):c.source_copy(s,r/'d',pin,1)
   (s/'a').write_text('bad')
   with self.assertRaises(ValueError):c.source_copy(s,r/'e',pin,1)
 def test_ready_exact_identity_and_failure_preservation(self):
  config={'run_id':'app-test','step_tokens':{'coldempty':'tok_12345678','duplicate':'tok_87654321'},'native_executable_path':'/a.app/Contents/MacOS/native','bundle_id':'org.example.app','app_path':'/a.app'}
  identity={'pid':42,'running_pid':42,'same_running_application':True,'same_pid':True,'process_image_path':config['native_executable_path'],'running_bundle_identifier':config['bundle_id'],'main_bundle_identifier':config['bundle_id'],'running_bundle_path':config['app_path'],'main_bundle_path':config['app_path']}
  report={'schema':1,'run_id':'app-test','step':'coldempty','token':'tok_12345678','status':'passed','pid':42,'same_pid':True,'identity':identity,**{k:False for k in ('entrypoint_replaced','fixture_opened_by_observer','handler_replaced','content_or_preferences_changed','complete_app_acceptance')}}
  self.assertEqual(c.validate_ready(report,config,'coldempty'),42)
  for key,value in [('schema',True),('schema',1.0),('status','failed'),('token','wrong'),('pid',True),('fixture_opened_by_observer',True)]:
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate_ready({**report,key:value},config,'coldempty')
  with self.assertRaises(ValueError):c.validate_ready(report,config,'coldempty',43)
  with self.assertRaises(ValueError):c.validate_ready({**report,'identity':{**identity,'main_bundle_path':'/stock.app'}},config,'coldempty')
  duplicate={**report,'step':'duplicate','token':'tok_87654321','duplicate':{'observed_no_duplicate':True,'handler_receipt_proven':False}}
  self.assertEqual(c.validate_ready(duplicate,config,'duplicate',42),42)
  duplicate['duplicate']['handler_receipt_proven']=True
  with self.assertRaises(ValueError):c.validate_ready(duplicate,config,'duplicate',42)
if __name__=='__main__':unittest.main()
