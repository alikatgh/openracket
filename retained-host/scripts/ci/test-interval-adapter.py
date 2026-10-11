import ast,pathlib,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).parent
SOURCE=(ROOT/'run-interval.py').read_text()
WORKFLOW=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()

class AdapterTests(unittest.TestCase):
 def test_source_parses_and_clones_have_explicit_allowlist(self):
  ast.parse(SOURCE)
  copier=(ROOT/'copy-independent-runtime.py').read_text()
  for purpose in ('interval-control','interval-candidate'):
   self.assertIn("['"+purpose+"']",copier);self.assertIn(purpose,SOURCE)
  self.assertIn('runtime-tree-check.py',SOURCE)
 def test_native_helpers_collect_independently_and_gate_timing(self):
  self.assertIn("['helpers']",SOURCE);self.assertIn("TELEMETRY/'native_preflight.py'",SOURCE)
  self.assertIn("all(r['passed'] for r in ROWS)",SOURCE)
  self.assertLess(SOURCE.index("assert ROWS and all"),SOURCE.index("TELEMETRY/'prepare_gui.py'"))
  self.assertIn("if: always() && steps.interval_prepare.outcome == 'success'",WORKFLOW)
  self.assertIn("steps.interval_helpers.outcome == 'success'",WORKFLOW)
 def test_correctness_precedes_telemetry_and_includes_actual_docs(self):
  for needle in ('interval-map-differential.rkt','native-trace.rkt','compare-trace.py','compare-docs-map.py','host_check(mode)'):
   self.assertIn(needle,SOURCE[:SOURCE.index(" elif PHASE=='telemetry':")])
  wrapper=(ROOT/'interval-native-host.rkt').read_text()
  self.assertIn('experiments/interval-map/tests/independent-native-host.rkt',wrapper)
  self.assertIn('OPENRACKET_INTERVAL_DOCS_OUTPUT',SOURCE)
  self.assertIn("EXP/'tests/interval-docs-postflight.rkt'",SOURCE)
  self.assertIn("EXP/'tests/rackunit-failure-propagation.rkt'",SOURCE)
  self.assertIn("[STOCK/'bin/racket',EXP/'tests/rackunit-failure-propagation-test.rkt']",SOURCE)
  self.assertIn('propagation_text.splitlines().count(marker)==1',SOURCE)
  self.assertIn("purpose='failure-propagation',timeout=30,required=False",SOURCE)
  self.assertIn('if sys.flags.optimize != 0:raise RuntimeError',SOURCE)
 def test_sequential_trial_order_unique_outputs_and_all_pair_acceptance(self):
  self.assertIn('for pair,mode in contract.trial_order():',SOURCE)
  self.assertIn("label=f'pair-{pair}-{arm}'",SOURCE)
  self.assertIn('timeout=235,required=False',SOURCE)
  self.assertIn('for pair in range(1,4):',SOURCE)
  self.assertIn('validate-interval-matrix.py',SOURCE)
  self.assertNotIn('ThreadPoolExecutor',SOURCE)
 def test_all_evidence_kept_bounded(self):
  for name in ('capture-host.json','capture-supervisor.json','memory-profile.json','gui-observation.json','worker-init.json','worker-phase-1.json','activation.json','heartbeat.json'):
   self.assertIn(name,SOURCE)
  self.assertIn('emit-replay-evidence.py',SOURCE)
  self.assertNotIn('capture.rktd',SOURCE)
  decoder=(ROOT/'decode-screenshots.py').read_text()
  self.assertIn('interval-stock-check-syntax',decoder);self.assertIn('interval-candidate-on-check-syntax',decoder)
 def test_free_public_guard_and_final_witness(self):
  for needle in ('runs-on: macos-15','contents: read',"github.event.repository.private == false","github.event.repository.visibility == 'public'","github.ref == 'refs/heads/prototype/retained-drracket'","if: always() && steps.runtime.outcome == 'success'"):
   self.assertIn(needle,WORKFLOW)
  for blocked in ('upload-artifact','actions/cache','workflow_dispatch','contents: write','runs-on: [self-hosted'):
   self.assertNotIn(blocked,WORKFLOW)
 def test_optimized_entry_fails_before_runtime_or_repository_access(self):
  result=subprocess.run([sys.executable,'-O',str(ROOT/'run-interval.py'),'prepare'],capture_output=True,text=True,timeout=10)
  self.assertNotEqual(result.returncode,0);self.assertIn('Optimized Python execution would disable source/CI gates',result.stderr)
if __name__=='__main__':unittest.main()
