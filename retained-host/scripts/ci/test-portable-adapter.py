#!/usr/bin/env python3
"""Headless checks for portable CI isolation and witness plumbing."""
import ast,os,pathlib,tempfile,unittest
from unittest.mock import patch
SOURCE=pathlib.Path(__file__).with_name('run-portable.py')

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='openracket-portable-adapter-')
        p=pathlib.Path(self.temp.name)
        self.ns={'os':os,'pathlib':pathlib,'TEMP':p,'STOCK':p/'stock','RUNTIME':p/'portable',
                 'PROFILE':p/'proof with spaces/profile','ADDON':p/'proof with spaces/profile/.local/share/racket','CACHE':p/'proof with spaces/profile/compiled-cache'}
        module=ast.parse(SOURCE.read_text())
        selected=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='environment']
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),self.ns)
    def tearDown(self):self.temp.cleanup()
    def test_ambient_experiments_and_profile_roots_do_not_leak(self):
        with patch.dict(os.environ,{'OPENRACKET_ALL_STRING_FAST_PATH':'1','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS':'8',
                                  'OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD':'1','OPENRACKET_NATIVE_APPEARANCE':'1',
                                  'PLTCONFIGDIR':'/unrelated-config','PLTCOLLECTS':'/unrelated-collections','PLT_COMPILED_FILE_CHECK':'exists','PLTADDONDIR':'/unrelated','PLTCOMPILEDROOTS':'/unrelated-cache','PLTUSERHOME':'/unrelated-home'}):
            env=self.ns['environment']('probe',True)
        self.assertFalse(any(k.startswith('OPENRACKET_') for k in env))
        for key in ('PLTCONFIGDIR','PLTCOLLECTS','PLT_COMPILED_FILE_CHECK'):self.assertNotIn(key,env)
        self.assertEqual(env['PLTADDONDIR'],str(self.ns['ADDON']))
        self.assertEqual(env['PLTCOMPILEDROOTS'],str(self.ns['CACHE'])+':')
        self.assertEqual(env['RACKET'],str(self.ns['RUNTIME']/'bin/racket'))
    def test_pristine_checks_have_separate_first_compilation_root(self):
        env=self.ns['environment']('headless')
        self.assertEqual(env['RACKET'],str(self.ns['STOCK']/'bin/racket'))
        self.assertNotEqual(env['PLTADDONDIR'],str(self.ns['ADDON']))
        self.assertTrue(env['PLTCOMPILEDROOTS'].endswith('portable-ci-checks-compiled:'))
    def test_combined_save_preferences_are_distinct(self):
        a=self.ns['environment']('combined-save-candidate-on',True)
        b=self.ns['environment']('combined-save-candidate-off',True)
        self.assertNotEqual(a['PLTUSERHOME'],b['PLTUSERHOME'])
        self.assertEqual(a['PLTADDONDIR'],b['PLTADDONDIR'])
        self.assertNotEqual(a['PLTUSERHOME'],str(self.ns['PROFILE']))
    def test_actual_launcher_and_readonly_observer_contract_is_present(self):
        source=SOURCE.read_text()
        self.assertIn("'launch-stock.sh' if stock else 'launch-openracket.sh'",source)
        self.assertIn("OPENRACKET_NATIVE_READY_FILE=str(ready)",source)
        self.assertIn("OPENRACKET_NATIVE_CAPTURE_DONE=str(done)",source)
        self.assertIn("env['OPENRACKET_AUTOSAVE_GUARD']='0'",source)
        self.assertIn("report.get('genuine_host') is True",source)
        self.assertIn('OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB=str(expected_memory_mib)',source)
        self.assertIn("tree_check('compare',STOCK,False)",source)
        self.assertIn("tree_check('compare',RUNTIME,False)",source)
if __name__=='__main__':unittest.main()
