import pathlib,unittest
ROOT=pathlib.Path(__file__).parent
S=(ROOT/'run-mac-app.py').read_text()
class Adapter(unittest.TestCase):
 def test_native_footprint_witness_starts_before_builder_tests(self):
  self.assertLess(S.index("witness('baseline','pristine',STOCK)"),S.index("'Twenty actual native Racket builder contract cases'"))
  self.assertLess(S.index("witness('baseline','selected-runtime',RUNTIME)"),S.index("'Twenty actual native Racket builder contract cases'"))
  self.assertIn("witness('compare','official-user-preferences'",S)
 def test_exact_builder_and_preview_pins(self):
  self.assertIn('db7b3e766da0532630237e8dd3bc42fb6eab9d7130753a69a17e70faf0574f67',S)
  self.assertIn('2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552',S)
  self.assertIn('CONTRACT.source_copy(ROOT,PROOF,SOURCE_PIN,155)',S)
 def test_native_tests_explicit_and_no_false_success(self):
  self.assertIn("'20 tests passed' in out",S);self.assertIn("HEARTBEAT/'test_heartbeat.rkt'",S)
  for f in ('make-app.rkt','test-app.rkt','make-native-launcher.rkt'):self.assertIn("BUILDER/'"+f+"'",S)
 def test_real_entry_and_no_security_bypass(self):
  self.assertIn("['/bin/sh',BUILDER/'build-app.sh'",S)
  self.assertNotIn('launchctl',S);self.assertNotIn('xattr',S);self.assertNotIn('--master-disable',S)
  self.assertIn("'independent_generation_determinism_gate':False",S)
  self.assertLess(S.index("default_handler('before-build')"),S.index("'Generate independent untouched official native launcher reference'"))
 def test_closed_environment_and_python_optimization(self):
  self.assertIn('if sys.flags.optimize:raise SystemExit',S)
  self.assertIn("['mac-app']",(ROOT/'copy-independent-runtime.py').read_text())
  self.assertIn("'mac-app'",S)
if __name__=='__main__':unittest.main()
