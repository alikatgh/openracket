import pathlib,ast,unittest
P=pathlib.Path(__file__).parent;S=(P/'run-stock-tools.py').read_text()
class ToolAdapter(unittest.TestCase):
 def test_exact_source_and_complete_candidate(self):
  for pin in ('e588a7b4e383a30e30bc418874102589234dcf4143c93f7cb1c5785680bbb521','226ec3054710a95b45e15c2211090000a94f75123515305a1f4a8a27fd156ea7','2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'):self.assertIn(pin,S)
  self.assertIn('len(allowed)==4',S);self.assertIn('BASE-0520-CONTENTS.json',S)
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
  self.assertIn("prefix+['test',PROOF/'tests/native-tool-coordinator-test.rkt']",S)
  self.assertIn("['native-tools']",(P/'copy-independent-runtime.py').read_text())
 def test_independent_workflow_and_original_tree_witness(self):
  w=(P.parents[2]/'.github/workflows/retained-native.yml').read_text();self.assertIn("if: always() && steps.tools_prepare.outcome == 'success'",w)
  self.assertIn("tree('baseline',STOCK,'pristine')",S);self.assertIn("tree('baseline',MODERN,'selected-modern')",S)
  self.assertIn('if sys.flags.optimize:raise SystemExit',S)
if __name__=='__main__':unittest.main()
