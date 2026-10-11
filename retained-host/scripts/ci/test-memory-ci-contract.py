import importlib.util,pathlib,tempfile,unittest
p=pathlib.Path(__file__).with_name('memory-ci-contract.py');s=importlib.util.spec_from_file_location('c',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Contract(unittest.TestCase):
 def test_capacity_precondition(self):
  self.assertEqual(c.require_capacity(4*1024**3),4*1024**3)
  for value in (0,3*1024**3,True,None):
   with self.assertRaises(ValueError):c.require_capacity(value)
 def test_balanced_sequential_order(self):
  self.assertEqual(len(c.ORDER),3)
  for r in c.ORDER:self.assertEqual(set(r),set(c.LIMITS))
  for i in range(3):self.assertEqual({r[i] for r in c.ORDER},set(c.LIMITS))
 def test_fresh_profiles_and_no_experiment_flags(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)/'runtime';base={'OPENRACKET_XREF_REPLY_CELL':'1','OPENRACKET_THEME':'dark','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS':'8','PLTCONFIGDIR':'bad','PLT_COMPILED_FILE_CHECK':'bad','PLTCOLLECTS':'bad','PLTCOMPILEDROOTS':'bad','PATH':'kept'}
   a=c.environment(base,'round-1-128',temp=t,runtime=root);b=c.environment(base,'round-1-256',temp=t,runtime=root)
   self.assertFalse(any(k.startswith('OPENRACKET_') for k in a));self.assertNotIn('PLTCONFIGDIR',a);self.assertNotIn('PLT_COMPILED_FILE_CHECK',a);self.assertNotIn('PLTCOLLECTS',a);self.assertNotIn('PLTCOMPILEDROOTS',a)
   self.assertNotEqual(a['PLTUSERHOME'],b['PLTUSERHOME']);self.assertNotEqual(a['PLTADDONDIR'],b['PLTADDONDIR']);self.assertEqual(a['PATH'],'kept');self.assertEqual(base['OPENRACKET_THEME'],'dark')
 def test_refuse_ambiguous_labels(self):
  for label in ('','../escape','hello world','/absolute'):
   with self.assertRaises(ValueError):c.environment({},label,temp='/tmp/x',runtime='/tmp/x/runtime')
 def test_refuse_non_disposable_runtime(self):
  with self.assertRaises(ValueError):c.environment({},'test',temp='/tmp/x',runtime='/tmp/elsewhere')
if __name__=='__main__':unittest.main()
