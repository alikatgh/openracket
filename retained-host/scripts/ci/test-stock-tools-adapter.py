import pathlib,ast,unittest
P=pathlib.Path(__file__).parent;S=(P/'run-stock-tools.py').read_text()
class ToolAdapter(unittest.TestCase):
 def test_exact_source_and_complete_candidate(self):
  for pin in ('753839e4a470ebf9fb33a95f4100b3954a6f55718cc14c3310cc7cc46d2bd1bc','f74d22a1b1e15956d8a86b6b884fb3d69655523d79e125c777a16b5758fb961a','2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'):self.assertIn(pin,S)
  self.assertIn('len(allowed)==5',S);self.assertIn('BASE-0520-CONTENTS.json',S)
 def test_fresh_each_mode_and_original_deadlines(self):
  self.assertIn('assert not home.exists()',S);self.assertIn("shutil.copytree(ADDON,pathlib.Path(e['PLTADDONDIR']),symlinks=True)",S)
  self.assertIn('deadline=time.monotonic()+60',S);self.assertNotIn('set-mib',S);self.assertNotIn('MEMORY_LIMIT_MIB',S)
 def test_partial_ready_is_parsed_only_after_exit_and_timeout_stays_failed(self):
  self.assertLess(S.index('result=p.wait('),S.index('report=json.loads(raw)'))
  self.assertIn("'status':'malformed-failure'",S);self.assertIn('terminate_group(p);result=124',S)
  self.assertIn('diagnostic_grace_max_seconds=15',S)
 def test_actual_cases_and_corresponding_stock_gate(self):
  self.assertIn("for case in ('debugger','macro-stepper','teaching-tests')",S);self.assertIn('if native_case(case):native_case(case,True)',S)
  self.assertIn("report.get('follow_on_case')==case",S);self.assertIn("report['follow_on_result'].get('status')=='passed'",S)
 def test_explicit_compile_and_coordinator_execution(self):
  for name in ('native-tool-coordinator.rkt','native-tool-coordinator-test.rkt','independent-native-stock-tools.rkt','independent-native-host.rkt'):self.assertIn(repr(name),S)
  self.assertNotIn("prefix+['test',PROOF/'tests/native-tool-coordinator-test.rkt']",S)
  self.assertIn("coordinator_regression(mode,e)",S);self.assertIn("communicate(timeout=30)",S)
  self.assertIn("'native-tool-coordinator-standalone.rkt'",S)
  self.assertIn("['native-tools']",(P/'copy-independent-runtime.py').read_text())
 def test_standalone_acceptance_and_negative_controls(self):
  node=next(n for n in ast.parse(S).body if isinstance(n,ast.FunctionDef) and n.name=='coordinator_result_valid')
  ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<validator>','exec'),ns);valid=ns['coordinator_result_valid']
  ok='OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete'
  bad='OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE\nactual: actual\nexpected: deliberately-wrong'
  self.assertTrue(valid(0,ok,False));self.assertTrue(valid(1,bad,True))
  for code,text,negative in [(1,ok,False),(0,ok+'\n'+ok,False),(0,bad,True),(124,bad,True),(-9,bad,True),(1,'import failed',True),(1,bad+'\n'+ok,True),(1,bad+'\nOPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE',True)]:self.assertFalse(valid(code,text,negative))
 def test_independent_workflow_and_original_tree_witness(self):
  w=(P.parents[2]/'.github/workflows/retained-native.yml').read_text();self.assertIn("if: always() && steps.tools_prepare.outcome == 'success'",w)
  self.assertIn("tree('baseline',STOCK,'pristine')",S);self.assertIn("tree('baseline',MODERN,'selected-modern')",S)
  self.assertIn('if sys.flags.optimize:raise SystemExit',S)
if __name__=='__main__':unittest.main()
