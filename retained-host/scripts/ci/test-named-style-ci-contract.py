import importlib.util,pathlib,tempfile,unittest
spec=importlib.util.spec_from_file_location('contract',pathlib.Path(__file__).with_name('named-style-ci-contract.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.temp=pathlib.Path(self.t.name).resolve();self.stock=self.temp/'stock';self.candidate=self.temp/'candidate'
 def env(self,mode='stock',purpose='check',**extra):
  base={'PYTHONOPTIMIZE':'2','PATH':'/known/path','OPENRACKET_NAMED_STYLE_INDEX':'1','OPENRACKET_HOST_THEME':'1','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS':'8','OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD':'1','PLTCONFIGDIR':'foreign','PLT_COMPILED_FILE_CHECK':'foreign','OPENRACKET_XREF_REPLY_CELL':'1','PLTCOLLECTS':'foreign','PLTCOMPILEDROOTS':'foreign','PLTUSERHOME':'foreign','PLTADDONDIR':'foreign'};base.update(extra)
  return c.environment(base,mode,purpose,temp=self.temp,stock=self.stock,candidate=self.candidate)
 def test_stock_clears_all_experiments_and_foreign_collections(self):
  e=self.env();self.assertFalse(any(k.startswith('OPENRACKET_') for k in e));self.assertNotIn('PYTHONOPTIMIZE',e);self.assertNotIn('PLTCONFIGDIR',e);self.assertNotIn('PLT_COMPILED_FILE_CHECK',e);self.assertNotIn('PLTCOLLECTS',e);self.assertNotIn('PLTCOMPILEDROOTS',e);self.assertEqual(e['PATH'],'/known/path');self.assertEqual(e['RACKET'],str(self.stock/'bin/racket'))
 def test_explicit_off_and_on_candidate_flags(self):
  for mode in c.MODES:
   e=self.env(mode);self.assertEqual({k:v for k,v in e.items() if k.startswith('OPENRACKET_')},{} if mode=='stock' else {'OPENRACKET_NAMED_STYLE_INDEX':'1' if mode=='candidate-on' else '0'})
 def test_fresh_preferences_and_separate_addons(self):
  homes=set();addons=set()
  for mode in c.MODES:
   for purpose in ('correctness','pair-1','pair-2'):
    e=self.env(mode,purpose);homes.add(e['PLTUSERHOME']);addons.add(e['PLTADDONDIR'])
  self.assertEqual(len(homes),9);self.assertEqual(len(addons),9)
 def test_arbitrary_arm_and_profile_paths_refused(self):
  for mode,purpose in (('other','check'),('stock','../escape'),('stock','')):
   with self.assertRaises(ValueError):self.env(mode,purpose)
 def test_runtime_outside_runner_temp_refused(self):
  with self.assertRaises(ValueError):c.environment({},'stock','check',temp=self.temp,stock=self.temp.parent/'outside',candidate=self.candidate)
 def test_balanced_sequential_order(self):
  self.assertEqual(c.trial_order(),[(1,'stock'),(1,'candidate-on'),(2,'candidate-on'),(2,'stock'),(3,'stock'),(3,'candidate-on')])
 def test_independent_runtime_roots_required(self):
  for candidate in (self.stock,self.stock/'nested',self.stock.parent):
   with self.assertRaises(ValueError):c.environment({},'stock','check',temp=self.temp,stock=self.stock,candidate=candidate)
if __name__=='__main__':unittest.main()
