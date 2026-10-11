import pathlib,ast,unittest,subprocess,types
ROOT=pathlib.Path(__file__).parent
S=(ROOT/'run-mac-app.py').read_text()
class Adapter(unittest.TestCase):
 def test_installed_profile_prefix_retains_links_but_builder_prefix_stays_clean(self):
  nodes=[n for n in ast.parse(S).body if isinstance(n,ast.FunctionDef) and n.name in ('raco_prefix','installed_raco_prefix')]
  namespace={'RUNTIME':pathlib.Path('/runtime'),'ADDON':pathlib.Path('/private/addon'),'CACHE':pathlib.Path('/private/cache')}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'<prefixes>','exec'),namespace)
  stock=namespace['raco_prefix']();installed=namespace['installed_raco_prefix']()
  self.assertIn('-U',stock);self.assertNotIn('-U',installed)
  self.assertEqual([x for x in stock if x!='-U'],installed)
  self.assertIn("'Register separate CI-only read-only native app observer',installed_raco_prefix()",S)
  self.assertIn("'Compile observer package registration without main runtime writes',installed_raco_prefix()",S)
  self.assertIn('resolved==expected.resolve()',S);self.assertIn('actual_sha==expected_sha',S)
 def test_launch_refusal_captures_and_blocks_alternate_attempts(self):
  self.assertIn("atomic_json(REPORTS/'launch-blocked.json'",S)
  self.assertIn('App relocation launch withheld after prior unresolved launch refusal/startup',S)
  self.assertIn("if not (REPORTS/'launch-blocked.json').exists():launch_sequence",S)
  self.assertIn('further launch/relocation attempts blocked pending diagnosis',S)
 def test_open_timeout_is_blocked_before_exception_returns(self):
  nodes=[n for n in ast.parse(S).body if isinstance(n,ast.FunctionDef) and n.name=='dispatch_open']
  seen=[]
  def timeout(*args,**kwargs):raise subprocess.TimeoutExpired(args[0],kwargs['timeout'])
  namespace={'subprocess':types.SimpleNamespace(run=timeout,TimeoutExpired=subprocess.TimeoutExpired),'REPORTS':pathlib.Path('/reports'),'atomic_json':lambda p,v:seen.append((p,v))}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'<dispatch>','exec'),namespace)
  with self.assertRaises(subprocess.TimeoutExpired):namespace['dispatch_open'](['/usr/bin/open','-a','app'],30,'cold','initial')
  self.assertEqual(len(seen),1);self.assertEqual(seen[0][0],pathlib.Path('/reports/launch-blocked.json'))
  self.assertIn('timed out',seen[0][1]['reason'])
 def test_initial_readiness_block_precedes_fallible_diagnostics(self):
  block=S[S.index('   if not ready.exists():'):S.index("   assert ready.stat()")]
  self.assertLess(block.index('atomic_json('),block.index('path=capture('))
  self.assertIn("if first_pid is None and not (REPORTS/'launch-blocked.json').exists():",S)
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
