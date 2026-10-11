import pathlib,ast,unittest
P=pathlib.Path(__file__).parent;S=(P/'run-stock-tools.py').read_text()
class ToolAdapter(unittest.TestCase):
 def test_exact_source_and_complete_candidate(self):
  for pin in ('a4fe8c99ea951787e4e5e1b3521ef02c12358120e3887a2ae6188ead6e60830d','9902209df604d4b5d8e5b92b77f39df58e81ed7acd918c93c823d3b19d7ffcea','2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'):self.assertIn(pin,S)
  self.assertIn('len(allowed)==11',S);self.assertIn('BASE-0520-CONTENTS.json',S)
 def test_fresh_each_mode_and_original_deadlines(self):
  self.assertIn('assert not home.exists()',S);self.assertIn("if modern:fresh_modern_addon(label,e)",S)
  self.assertIn('deadline=time.monotonic()+60',S);self.assertNotIn('set-mib',S);self.assertNotIn('MEMORY_LIMIT_MIB',S)
 def test_partial_ready_is_parsed_only_after_exit_and_timeout_stays_failed(self):
  self.assertLess(S.index('result=p.wait('),S.index('report=json.loads(raw)'))
  self.assertIn("'status':'malformed-failure'",S);self.assertIn('terminate_group(p);result=124',S)
  self.assertIn('diagnostic_grace_max_seconds=15',S)
 def test_actual_cases_and_corresponding_stock_gate(self):
  self.assertIn("for case in ('debugger','macro-stepper','teaching-tests')",S);self.assertIn('try:stock_passed=native_case(case)',S);self.assertIn('if stock_passed:',S);self.assertIn('try:native_case(case,True)',S)
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
  failure='OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong'
  bad='OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE\n'+failure
  self.assertTrue(valid(0,ok,False));self.assertTrue(valid(1,bad,True))
  for code,text,negative in [(1,ok,False),(0,ok+'\n'+ok,False),(0,bad,True),(124,bad,True),(-9,bad,True),(1,'import failed',True),(1,bad+'\n'+ok,True),(1,bad+'\nOPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE',True),(1,bad+'\n'+failure,True),(1,bad.replace('exn:test:check','exn:fail'),True),(1,bad.replace('actual=actual','actual=wrong'),True),(1,bad.replace('expected=deliberately-wrong','expected=actual'),True),(1,bad.replace(failure,''),True),(1,bad.replace(failure,' '+failure),True),(0,ok+'\n'+failure,False),(0,ok+'\nOPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE malformed',False)]:self.assertFalse(valid(code,text,negative))

 def test_dispatch_strict_positive_and_typed_negative(self):
  node=next(n for n in ast.parse(S).body if isinstance(n,ast.FunctionDef) and n.name=='coordinator_result_valid')
  ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<validator>','exec'),ns);valid=ns['coordinator_result_valid']
  ok='OPENRACKET_NATIVE_TOOL_DISPATCH_OK distinct-thread strict-failures cleanup-complete'
  failure='OPENRACKET_NATIVE_TOOL_DISPATCH_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong'
  bad='OPENRACKET_NATIVE_TOOL_DISPATCH_INJECTING_FAILURE\n'+failure
  self.assertTrue(valid(0,ok,False,'dispatch'));self.assertTrue(valid(1,bad,True,'dispatch'))
  for code,out,negative in [(124,bad,True),(-9,bad,True),(0,bad,True),(1,bad+'\n'+failure,True),(1,bad.replace('exn:test:check','exn:fail'),True),(1,bad.replace('actual=actual','actual=wrong'),True),(1,bad.replace(failure,''),True),(1,bad.replace(failure,' '+failure),True),(0,ok+'\n'+failure,False),(0,ok.replace('distinct-thread ',''),False),(0,ok+'\n'+ok,False)]:self.assertFalse(valid(code,out,negative,'dispatch'))
  self.assertFalse(valid(0,ok,False,'unknown'))
  self.assertIn('coordinator_regression(mode,e,"dispatch")',S)
  for name in ('native-tool-dispatch.rkt','native-tool-dispatch-standalone.rkt'):self.assertIn(repr(name),S)
  self.assertIn("'--inject-wrong-result'",S)
 def test_independent_workflow_and_original_tree_witness(self):
  w=(P.parents[2]/'.github/workflows/retained-native.yml').read_text();self.assertIn("if: always() && steps.tools_prepare.outcome == 'success'",w)
  self.assertIn("tree('baseline',STOCK,'pristine')",S);self.assertIn("tree('baseline',MODERN,'selected-modern')",S)
  self.assertIn('if sys.flags.optimize:raise SystemExit',S)
 def test_source_contract_strict_native_gate(self):
  node=next(n for n in ast.parse(S).body if isinstance(n,ast.FunctionDef) and n.name=='source_contract_result_valid')
  ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<validator>','exec'),ns);valid=ns['source_contract_result_valid']
  marker='OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals'
  self.assertTrue(valid(0,marker))
  for code,out in [(1,marker),(124,marker),(-9,marker),(0,''),(0,' '+marker),(0,marker+'\n'+marker),(0,marker.replace('source-range','source')),(0,marker+'\nOPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_FAILURE')]:self.assertFalse(valid(code,out))
  self.assertIn('source_contract_regression(mode,e)',S)
  for name in ('native-tool-source-contract.rkt','native-tool-source-contract-standalone.rkt'):self.assertIn(repr(name),S)
  self.assertIn("str(PROOF/'tests/native-tool-source-contract-standalone.rkt')",S)
if __name__=='__main__':unittest.main()
