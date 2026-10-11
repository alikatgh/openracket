import ast,contextlib,io,json,os,pathlib,signal,subprocess,tempfile,types,unittest
P=pathlib.Path(__file__).with_name('run-native-quit.py');S=P.read_text();A=ast.parse(S)
def fn(name):return ast.get_source_segment(S,next(x for x in A.body if isinstance(x,ast.FunctionDef) and x.name==name))
class Contracts(unittest.TestCase):
 def test_exact_sources(self):
  for x in ('932b9036e3d52d6b6aa723500c18c5c500ba28ae4b29dd3800bdf950b15b64fc','2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552','b4e5638c409b018a8dec030ea7dafb60291bfffc2645a5d087d7e91d4cfd77ee','175e8b8e8d9a74eb275998054764016bc15addc4eeebeb387eb9167bef43d53b'):self.assertIn(x,S)
 def test_no_optimized_assertions(self):self.assertIn("if sys.flags.optimize:raise SystemExit",S)
 def test_private_registration_no_u(self):
  self.assertNotIn("'-U'",fn('raco'));self.assertIn("'--scope','user'",fn('prepare_case'));self.assertIn("'--avoid-main'",fn('prepare_case'));self.assertIn('collection-file-path',fn('prepare_case'))
 def test_all_native_inputs_and_count(self):
  for x in ('tool.rkt','contract.rkt','cocoa-identity.rkt','contract-test.rkt'):self.assertIn(x,fn('prepare_case'))
  self.assertIn("out.splitlines().count('8 tests passed')==1",S)
 def test_profile_and_product_unchanged(self):
  t=fn('prepare_case');self.assertIn('SOURCE_PIN,155',t);self.assertIn("assert not home.exists()",t);self.assertIn("'--theme','dark'",t);self.assertNotIn('memory-profile.rkt',t)
 def test_natural_exit_and_outer_bound(self):
  t=fn('run_case');self.assertIn('home,270,required=False,owned_case=root',t);self.assertIn("d['natural_exit']==0",t);self.assertIn("d['cleanup_used'] is False",t);self.assertIn("d['elapsed_seconds']<150",t)
 def test_strict_outer_cleanup(self):
  t=fn('timeout_cleanup');self.assertIn("matches[0][1]==str(p.pid)",t);self.assertIn("matches[0][2]==str(pid)",t);self.assertIn('code=124',fn('command'));self.assertIn("block('Outer supervisor timeout",t)
 def test_independence_and_matrix(self):
  self.assertIn("for case in ('clean','save','discard')",S);self.assertIn("if stock_ok:run_case(case,'modern-dark')",S);self.assertIn("all(r['passed'] for r in ROWS)",S);self.assertIn("len({c['profile_path'] for c in configs})==6",S)
 def test_witness_and_handler_before_generation(self):
  self.assertIn("default_handler('before-generation',baseline=True)",S);self.assertIn("'official-preferences'",S);self.assertIn("default_handler(label+'-after-generation')",S);self.assertIn("default_handler('after-all')",S)
 def test_evidence_continues(self):
  t=fn('evidence');self.assertGreaterEqual(t.count('except Exception as error:failures.append'),2);self.assertIn("not failures",t);self.assertNotIn('capture.rktd',t)
 def test_selected_clone_explicit_environment(self):self.assertIn("extra={'OPENRACKET_CI_STOCK_RACKET':str(STOCK/'bin/racket')}",S)
 def test_timeout_inspection_failures_reap_supervisor(self):
  code=compile(ast.Module(body=[next(x for x in A.body if isinstance(x,ast.FunctionDef) and x.name=='timeout_cleanup')],type_ignores=[]),str(P),'exec')
  for mode in ('bad-json','ps-error','ownership'):
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);(root/'launch.json').write_text('{' if mode=='bad-json' else json.dumps({'pid':12345}))
    events=[]
    def ps(*a,**k):
     if mode=='ps-error':raise OSError('injected ps failure')
     return '12345 999 12345 '+str(root)+'/native'
    class Child:
     pid=456;returncode=None
     def communicate(self,**kwargs):events.append('reap');self.returncode=-9;return ('saved output',None)
     def poll(self):return self.returncode
    ns=dict(json=json,os=types.SimpleNamespace(getpid=os.getpid,killpg=lambda *a:events.append('native-signal')),signal=signal,subprocess=types.SimpleNamespace(check_output=ps),block=lambda why:events.append('blocked'),terminate_group=lambda p:events.append('terminate'))
    exec(code,ns)
    with contextlib.redirect_stdout(io.StringIO()):out,detail=ns['timeout_cleanup'](Child(),root)
    self.assertEqual(events,['blocked','terminate','reap']);self.assertEqual(detail['exit'],124);self.assertIsNotNone(detail['native_cleanup_error']);self.assertEqual(out,'saved output');self.assertIsNotNone(detail['supervisor_returncode_after_cleanup'])
 def test_block_write_failure_reaps_and_blocks_memory(self):
  functions=[next(x for x in A.body if isinstance(x,ast.FunctionDef) and x.name==n) for n in ('block','timeout_cleanup')]
  code=compile(ast.Module(body=functions,type_ignores=[]),str(P),'exec')
  with tempfile.TemporaryDirectory() as tmp:
   events=[]
   class Child:
    pid=456;returncode=None
    def communicate(self,**kwargs):events.append('reap');self.returncode=-9;return ('',None)
    def poll(self):return self.returncode
   ns=dict(json=json,REPORTS=pathlib.Path(tmp)/'missing-parent',LAUNCH_BLOCKED=False,terminate_group=lambda p:events.append('terminate'))
   exec(code,ns)
   with contextlib.redirect_stdout(io.StringIO()):out,d=ns['timeout_cleanup'](Child(),None)
   self.assertEqual(events,['terminate','reap']);self.assertTrue(ns['LAUNCH_BLOCKED']);self.assertIsNotNone(d['block_write_error']);self.assertEqual(d['exit'],124)
   self.assertIn("if LAUNCH_BLOCKED or (REPORTS/'launch-blocked.json').exists()",fn('run_case'))
if __name__=='__main__':unittest.main(verbosity=2)
