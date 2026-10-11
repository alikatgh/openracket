import ast,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parent
class Contract(unittest.TestCase):
 def test_separate_single_trial_processes(self):
  s=(ROOT/'run-phase-control.py').read_text()
  self.assertIn("PHASE in ('off','on')",s);self.assertIn("'--trials','1'",s)
  self.assertIn("if PHASE=='on':args.append('--phase-probe')",s)
  self.assertIn("OFF=REPORTS/'replay-off';ON=REPORTS/'replay-on'",s)
 def test_unchanged_native_envelopes(self):
  s=(ROOT/'run-phase-control.py').read_text();self.assertIn('timeout=110',s);self.assertIn('timeout=235',s)
 def test_same_captured_context(self):
  s=(ROOT/'run-phase-control.py').read_text();self.assertIn("'--capture',CAPTURE/'capture.rktd'",s)
  self.assertIn("'--probe',EXP,'--capture',CAPTURE,'--off',OFF,'--on',ON",s)
 def test_second_arm_and_acceptance_survive_first_failure(self):
  s=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()
  self.assertIn("if: always() && steps.probe_capture.outcome == 'success'",s)
  self.assertIn("if: always() && steps.probe_prepare.outcome == 'success'",s)
if __name__=='__main__':unittest.main()
