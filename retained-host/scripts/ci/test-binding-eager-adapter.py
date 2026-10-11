import ast,pathlib,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).parent
SOURCE=(ROOT/'run-binding-eager.py').read_text()
WORKFLOW=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()
class AdapterTests(unittest.TestCase):
 def test_source_and_clone_scopes(self):
  ast.parse(SOURCE)
  for purpose in ('binding-eager-control','binding-eager-candidate'):
   self.assertIn("['"+purpose+"']",(ROOT/'copy-independent-runtime.py').read_text());self.assertIn(purpose,SOURCE)
 def test_all_helpers_and_product_correctness_before_telemetry(self):
  for n in ('--candidate-source','--pristine-source','--profile','bindings-differential.rkt','compare-bindings.py','native-trace.rkt','compare-binding-trace.py'):
   self.assertIn(n,SOURCE[:SOURCE.index(" elif PHASE=='telemetry':")])
  self.assertIn("for mode in ('stock','candidate-off','candidate-on'):",SOURCE)
  self.assertIn("native_modules=sorted((NATIVE/'tests').glob('*.rkt'))+sorted((NATIVE/'tool').glob('*.rkt'))",SOURCE)
  self.assertIn("('stock.rkt','candidate.rkt','stock-fault.rkt','candidate-fault.rkt')",SOURCE)
  self.assertIn('*generated_modules,*native_modules',SOURCE)
  self.assertIn("assert ROWS and all(r['passed'] for r in ROWS)",SOURCE)
  self.assertIn("if: always() && steps.binding_prepare.outcome == 'success'",WORKFLOW)
  self.assertIn("steps.binding_helpers.outcome == 'success'",WORKFLOW)
 def test_flag_modes_and_independent_stock_trace_validation(self):
  self.assertIn("(('unset',None),('zero','0'),('unexpected','unexpected'),('one','1'))",SOURCE)
  self.assertIn("('off','candidate-off','stock'),('on','candidate-on','stock')",SOURCE)
  self.assertIn("NATIVE=EXP/'native';TRACE=EXP/'trace'",SOURCE)
 def test_verified_transform_and_separate_getter_evidence(self):
  self.assertIn("'--arm','stock' if mode=='stock' else 'candidate'",SOURCE)
  self.assertIn("'--manifest',runtime(mode)/'openracket-gui-phase-manifest.json'",SOURCE)
  self.assertIn("'binding-export.json'",SOURCE)
  self.assertNotIn('application-profile.json',SOURCE);self.assertNotIn('queued-samples.json',SOURCE)
  self.assertIn('first and second public getter costs',WORKFLOW)
 def test_six_sequential_complete_pairs_and_independent_fresh_evidence(self):
  self.assertIn('for pair,mode in contract.trial_order():',SOURCE)
  self.assertIn('timeout=235,required=False',SOURCE);self.assertIn('timeout=285',SOURCE)
  self.assertIn('validate-binding-eager-matrix.py',SOURCE)
  self.assertIn("ROOT/'scripts/ci/emit-replay-evidence.py',REPORTS/'matrix.json'",SOURCE)
  self.assertNotIn('ThreadPoolExecutor',SOURCE)
  for n in ('binding-eager-stock-check-syntax','binding-eager-candidate-off-check-syntax','binding-eager-candidate-on-check-syntax'):
   self.assertIn(n,(ROOT/'decode-screenshots.py').read_text())
 def test_small_native_deadline_and_exact_proofs(self):
  self.assertIn('deadline=time.monotonic()+60',SOURCE)
  self.assertNotIn('deadline=time.monotonic()+100',SOURCE)
  self.assertIn('passed=host_proof(code,data,native_text)',SOURCE)
  self.assertIn('differential_proof(ok,proof,expected_mode)',SOURCE)
  selected=[n for n in ast.parse(SOURCE).body if isinstance(n,ast.FunctionDef) and n.name in ('host_proof','differential_proof','within_host_deadline')]
  ns={'re':__import__('re')};exec(compile(ast.Module(body=selected,type_ignores=[]),'<proofs>','exec'),ns)
  good='BINDINGS_EAGER_DIFFERENTIAL passed mode=on checks=42'
  self.assertTrue(ns['differential_proof'](True,good,'on'))
  for text in ('',good+'\n'+good,good.replace('42','0'),good.replace('on','off'),'prefix '+good,good.replace('42','True')):
   self.assertFalse(ns['differential_proof'](True,text,'on'))
  self.assertEqual(ns['within_host_deadline'](0,60,60),0)
  self.assertEqual(ns['within_host_deadline'](0,60.001,60),124)
  self.assertEqual(ns['within_host_deadline'](1,61,60),124)
  self.assertIn('code=within_host_deadline(code,time.monotonic(),deadline)',SOURCE)
  ready={'status':'passed','follow_on_case':'check-syntax'};marker='OPENRACKET_NATIVE_BINDINGS_OK complete-graph real-navigation escaped-table'
  self.assertTrue(ns['host_proof'](0,ready,marker))
  for code,data,text in ((124,ready,marker),(0,[],marker),(0,None,marker),(0,ready,''),(0,ready,marker+'\n'+marker)):
   self.assertFalse(ns['host_proof'](code,data,text))
 def test_public_free_runner_and_witness(self):
  for n in ('runs-on: macos-15','contents: read',"github.event.repository.private == false", "github.event.repository.visibility == 'public'", "github.ref == 'refs/heads/prototype/retained-drracket'", "if: always() && steps.runtime.outcome == 'success'"):
   self.assertIn(n,WORKFLOW)
  for n in ('upload-artifact','actions/cache','workflow_dispatch','contents: write','self-hosted'):
   self.assertNotIn(n,WORKFLOW)
 def test_optimized_entry_refuses_before_access(self):
  p=subprocess.run([sys.executable,'-O',str(ROOT/'run-binding-eager.py'),'prepare'],capture_output=True,text=True,timeout=10)
  self.assertNotEqual(p.returncode,0);self.assertIn('Optimized Python execution',p.stderr)
 def test_typed_native_diagnostic_gate(self):
  node=next(n for n in ast.parse(SOURCE).body if isinstance(n,ast.FunctionDef) and n.name=='diagnostic_proof')
  ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<diagnostic>','exec'),ns);valid=ns['diagnostic_proof']
  prefix='OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS';ok=prefix+'_OK typed-payload-preserved output-failures-contained';injection=prefix+'_INJECTING_FAILURE';failure=prefix+'_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong';bad=injection+'\n'+failure
  self.assertTrue(valid(0,ok,False));self.assertTrue(valid(1,bad,True))
  for code,text,negative in [(124,bad,True),(-9,bad,True),(0,bad,True),(1,bad+'\n'+failure,True),(1,bad.replace('exn:test:check','exn:fail'),True),(1,bad.replace('actual=actual','actual=other'),True),(1,bad.replace(failure,''),True),(1,'prefix '+bad,True),(1,bad+'\n'+ok,True),(0,ok+'\n'+ok,False),(0,ok+'\n'+failure,False)]:self.assertFalse(valid(code,text,negative))
  self.assertIn("communicate(timeout=30)",SOURCE)
  self.assertIn("elif PHASE=='correctness':\n  diagnostic_regression()",SOURCE)
  for n in ('native-tool-failure-diagnostics.rkt','native-tool-failure-diagnostics-standalone.rkt'):self.assertIn(repr(n),SOURCE)
  self.assertIn('assert all(p in native_modules for p in required_diagnostics)',SOURCE)
if __name__=='__main__':unittest.main()
