import ast,contextlib,io,json,pathlib,subprocess,sys,tempfile,types,unittest
ROOT=pathlib.Path(__file__).parent;SOURCE=(ROOT/'run-named-style.py').read_text();WORKFLOW=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()
class AdapterTests(unittest.TestCase):
 def test_syntax_and_exact_frozen_pins(self):
  ast.parse(SOURCE)
  for pin in ('15ff0feeb23952ebe826da0472d35bc6a2e150b4256dcb6271c7be5ce5d7cbe1','840fe01e282b60ee8613a87c63e7e7ed21233741c3fb30eb923dcd3bec75bdc4'):self.assertIn(pin,SOURCE)
 def test_independent_clone_purposes_and_no_other_overlay(self):
  for purpose in ('named-style-control','named-style-candidate'):self.assertIn(purpose,SOURCE);self.assertIn("['"+purpose+"']",(ROOT/'copy-independent-runtime.py').read_text())
  self.assertIn("PRODUCTION/'scripts/overlay.py','apply'",SOURCE)
  self.assertNotIn("binding-table-eager",SOURCE)
 def test_all_independent_correctness_gates_and_native_compile(self):
  for phase in ('helpers','production','editor','controls'):
   self.assertIn("elif PHASE=='"+phase+"':",SOURCE);self.assertIn("steps.style_"+phase+".outcome == 'success'",WORKFLOW)
  for part in ("(CONTROLS/'native').rglob('*.rkt')","(EDITOR/'native').glob('*.rkt')","(PRODUCTION/'tests/native').glob('*.rkt')","staged.rglob('*.rkt')"):
   self.assertIn(part,SOURCE)
  self.assertIn("assert ROWS and all(r['passed'] for r in ROWS)",SOURCE)
 def test_inner_deadlines_and_original_workload_preserved(self):
  for fragment in ('timeout=285','timeout=235,required=False','timeout=700,required=False','timeout=760,required=False','timeout=1040,required=False'):
   self.assertIn(fragment,SOURCE)
  self.assertIn('for pair,mode in contract.trial_order():',SOURCE)
  self.assertNotIn('ThreadPoolExecutor',SOURCE)
 def test_clean_nested_runner_environments_and_actual_source_verification(self):
  self.assertEqual(SOURCE.count('environment=contract.clean_environment(os.environ)'),2)
  self.assertIn("name.removesuffix('.rkt')",SOURCE)
  self.assertIn("verify_sources(mode,mode!='stock',observed=True)",SOURCE)
 def test_ten_inputs_and_maps_with_full_matrix(self):
  node=next(n for n in ast.parse(SOURCE).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FILES' for t in n.targets))
  files=ast.literal_eval(node.value);self.assertEqual(len(files),10);self.assertIn('style-witness.json',files)
  self.assertIn("evidence.create_map(inputs,acceptances,REPORTS/'input-digests.json')",SOURCE)
  self.assertIn("'input_digests':digest_map",SOURCE);self.assertIn('prepared-manifest.json',SOURCE)
 def test_no_paid_or_artifact_or_write_scope(self):
  for text in ('runs-on: macos-15','contents: read','github.event.repository.private == false','github.event.repository.visibility == \'public\'','cancel-in-progress: false'):self.assertIn(text,WORKFLOW)
  for text in ('upload-artifact','actions/cache','contents: write','self-hosted','workflow_dispatch'):self.assertNotIn(text,WORKFLOW)
 def test_pristine_witness_even_failed_prior_stage(self):
  self.assertIn("elif PHASE=='verify':",SOURCE);self.assertIn("if: always() && steps.runtime.outcome == 'success'",WORKFLOW)
 def functions(self,folder):
  rows=[];namespace={'pathlib':pathlib,'json':json,'sys':sys,'ROOT':folder,'REPORTS':folder,'CLEANUP_BLOCK':folder/'launch-blocked.json','PHASE':'helpers','CLEANUP_UNVERIFIED':False,'env':lambda *args:{},'record':lambda name,ok,detail='':rows.append((name,ok,detail))}
  nodes=[node for node in ast.parse(SOURCE).body if isinstance(node,ast.FunctionDef) and node.name in ('command','collection','emit','logs_and_reports')]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'adapter-functions','exec'),namespace)
  return namespace,rows
 def test_unverified_timeout_cleanup_blocks_later_phases_and_resolution(self):
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
   root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
   class Process:
    pid=123
    def wait(self,timeout):raise subprocess.TimeoutExpired('native',timeout)
   def launch(*args,**kwargs):launches.append(args);return Process()
   def cleanup(p):raise RuntimeError('survivor still alive')
   ns.update(subprocess=types.SimpleNamespace(Popen=launch,TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT),terminate_group=cleanup)
   self.assertFalse(ns['command']('first',['native'],required=False));self.assertTrue(ns['CLEANUP_BLOCK'].is_file());self.assertEqual(len(launches),1)
   self.assertFalse(ns['command']('next',['native'],required=False));self.assertEqual(len(launches),1)
   with self.assertRaisesRegex(RuntimeError,'Collection lookup blocked'):ns['collection']('stock','a/b')
   fresh,_=self.functions(root);fresh.update(subprocess=ns['subprocess'],terminate_group=cleanup)
   self.assertFalse(fresh['command']('later phase',['native'],required=False));self.assertEqual(len(launches),1)
   fresh['PHASE']='verify';fresh['subprocess']=types.SimpleNamespace(Popen=lambda *a,**k:types.SimpleNamespace(wait=lambda timeout:0),TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT)
   self.assertTrue(fresh['command']('original witness',['python']))
   self.assertTrue(any('cleanup' in name and not ok for name,ok,detail in rows))
 def test_cleanup_diagnostic_write_failure_leaves_prelaunch_lease(self):
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
   root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
   class FlakyLease:
    def __init__(self):self.path=root/'launch-blocked.json';self.writes=0
    def exists(self):return self.path.exists()
    def write_text(self,text):
     self.writes+=1
     if self.writes>1:raise OSError('disk update failed')
     return self.path.write_text(text)
    def unlink(self,**kwargs):return self.path.unlink(**kwargs)
   class Process:
    pid=456
    def wait(self,timeout):raise subprocess.TimeoutExpired('native',timeout)
   def launch(*a,**k):launches.append(a);return Process()
   def cleanup(p):raise RuntimeError('unknown survivors')
   ns.update(CLEANUP_BLOCK=FlakyLease(),subprocess=types.SimpleNamespace(Popen=launch,TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT),terminate_group=cleanup)
   self.assertFalse(ns['command']('first',['native'],required=False));self.assertTrue(ns['CLEANUP_UNVERIFIED']);self.assertTrue(ns['CLEANUP_BLOCK'].exists())
   self.assertFalse(ns['command']('second',['native'],required=False));self.assertEqual(len(launches),1)
   fresh,_=self.functions(root);fresh.update(subprocess=ns['subprocess'],terminate_group=cleanup)
   self.assertFalse(fresh['command']('later phase',['native'],required=False));self.assertEqual(len(launches),1)
   self.assertTrue(any('persistence_error' in detail for name,ok,detail in rows))
 def test_failed_initial_lease_write_starts_no_process(self):
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
   root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
   class RefusingLease:
    def exists(self):return False
    def write_text(self,text):raise OSError('cannot persist launch lease')
    def unlink(self,**kwargs):pass
   ns.update(CLEANUP_BLOCK=RefusingLease(),subprocess=types.SimpleNamespace(Popen=lambda *a,**k:launches.append(a),TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT))
   self.assertFalse(ns['command']('first',['native'],required=False));self.assertFalse(launches)
 def test_per_file_error_preserves_later_evidence(self):
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
   root=pathlib.Path(folder);ns,rows=self.functions(root);(root/'native.json').write_text('{}');(root/'report.json').write_text('{}');emitted=[]
   def broken(*args):raise ValueError('malformed long string document')
   ns.update(evidence=types.SimpleNamespace(transport_json_copy=broken),emit=lambda p:emitted.append(pathlib.Path(p).name))
   ns['logs_and_reports'](root);self.assertEqual(emitted,['report.json']);self.assertTrue(any(not ok for name,ok,detail in rows))
 def test_emit_exception_retained_and_does_not_escape(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);ns,rows=self.functions(root);source=root/'report.json';source.write_text('{}')
   def broken(*args,**kwargs):raise OSError('transport failed')
   ns['command']=broken;self.assertFalse(ns['emit'](source));self.assertTrue(any(not ok for name,ok,detail in rows))
 def test_optimized_launch_refused_before_environment(self):
  p=subprocess.run([sys.executable,'-O',str(ROOT/'run-named-style.py'),'prepare'],capture_output=True,text=True,timeout=10);self.assertNotEqual(p.returncode,0);self.assertIn('Optimized Python execution refused',p.stderr)
if __name__=='__main__':unittest.main()
