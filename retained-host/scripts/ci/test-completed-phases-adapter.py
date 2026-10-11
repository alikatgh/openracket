import ast,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parent
class Contract(unittest.TestCase):
 def test_native_preflight_precedes_patch(self):
  source=(ROOT/'run-completed-phases.py').read_text()
  self.assertLess(source.index("EXP/'native_preflight.py'"),source.index("EXP/'prepare_phase.py'"))
  self.assertIn("'--pristine-source',pristine.parent",source)
 def test_strict_separate_acceptance_and_existing_bounds(self):
  source=(ROOT/'run-completed-phases.py').read_text()
  self.assertIn("elif PHASE=='accept'",source);self.assertIn("EXP/'accept_completed.py'",source)
  self.assertIn('timeout=235',source);self.assertIn('timeout=170',source)
  self.assertIn("'--trials','2','--phase-probe'",source)
 def test_all_config_overrides_cleared(self):
  tree=ast.parse((ROOT/'run-completed-phases.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='env')
  import os
  fake=type('OS',(),{'environ':{'PLTCONFIGDIR':'poison','PLT_COMPILED_FILE_CHECK':'poison','PLTCOLLECTS':'poison','OPENRACKET_XREF_REPLY_CELL':'1'}})
  ns={'os':fake,'RACKET':pathlib.Path('/runtime/bin/racket'),'CLONE':pathlib.Path('/runtime'),'TEMP':pathlib.Path('/tmp')}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'<environment>','exec'),ns);e=ns['env']()
  for key in fake.environ:self.assertNotIn(key,e)
 def test_clone_allowlist_explicit(self):
  self.assertIn("['phase256']",(ROOT/'copy-independent-runtime.py').read_text())
 def test_evidence_acceptance_transport(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('emitter',ROOT/'emit-replay-evidence.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  self.assertIn('acceptance.json',mod.ALLOWED)
if __name__=='__main__':unittest.main()
