import ast,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parent
class Contract(unittest.TestCase):
 def test_evidence_failure_does_not_hide_other_records(self):
  s=(ROOT/'run-annotation-application.py').read_text()
  self.assertIn('except Exception as error:',s);self.assertIn('Evidence emission failure retained; continuing collection',s)
  self.assertIn("report.get('accepted') is True and report.get('failures')==[]",s)
 def test_actual_gui_only(self):
  s=(ROOT/'run-annotation-application.py').read_text()
  self.assertIn("PHASE in ('control','observed')",s)
  self.assertIn("EXP/'capture.py','--arm',PHASE",s)
  self.assertNotIn("EXP/'supervise.py'",s);self.assertNotIn("'--phase-probe'",s)
 def test_native_gates_and_wrappers(self):
  s=(ROOT/'run-annotation-application.py').read_text()
  self.assertLess(s.index("EXP/'native_preflight.py'"),s.index("EXP/'prepare_gui.py'"))
  self.assertIn('timeout=235',s);self.assertIn('timeout=285',s)
  self.assertIn("'--pristine-source',pristine.parent",s)
 def test_independent_observed_and_acceptance(self):
  s=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()
  self.assertGreaterEqual(s.count("if: always() && steps.annotation_prepare.outcome == 'success'"),2)
 def test_configuration_isolation(self):
  tree=ast.parse((ROOT/'run-annotation-application.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='env')
  fake=type('OS',(),{'environ':{k:'poison' for k in ('PLTCONFIGDIR','PLTCOLLECTS','PLT_COMPILED_FILE_CHECK','OPENRACKET_XREF_REPLY_CELL','OPENRACKET_GUI_PHASE_POINTS','PYTHONOPTIMIZE','PLTLINKS')}})
  ns={'os':fake,'RACKET':pathlib.Path('/runtime/bin/racket'),'CLONE':pathlib.Path('/runtime'),'TEMP':pathlib.Path('/tmp')}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'<environment>','exec'),ns);e=ns['env']()
  for key in fake.environ:self.assertNotIn(key,e)
 def test_explicit_clone_and_evidence_names(self):
  self.assertIn("['annotation-application']",(ROOT/'copy-independent-runtime.py').read_text())
  s=(ROOT/'emit-replay-evidence.py').read_text()
  for name in ('gui-observation.json','worker-phase-1.json','application-profile.json'):self.assertIn(repr(name),s)
if __name__=='__main__':unittest.main()
