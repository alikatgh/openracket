#!/usr/bin/env python3
"""Synthetic acceptance-logic checks only; no native timing is generated."""
import ast, contextlib, copy, io, json, pathlib, statistics, tempfile, unittest

SOURCE=pathlib.Path(__file__).with_name('run-budget.py')
FUNCTION=next(n for n in ast.parse(SOURCE.read_text()).body
              if isinstance(n,ast.FunctionDef) and n.name=='compare_completed_trials')

def trial(arm,pair):
    return {'status':'complete','exit_code':0,'timeout':False,
            'measurement_kind':'initial_coloring_typing',
            'post_typing_lexer_settle':{'complete':True},
            'exact_resulting_source_verified':True,'keys_starting_with_lexer_invalid':1,
            'initial_coloring_key_samples':[{} for _ in range(80)],
            'selected_language_settings':{'status':'complete','annotations':'lang-default'},
            'preserved_settings':{'coloring':True},'racket_version':'9.3','os':'unix','vm':'chez-scheme',
            'fixture_metadata':{'path':f'/{arm}/{pair}/fixture.rkt','sha256':'synthetic-fixture'},
            'scan_activation':{'status':'verified','expected':'stock'},
            'budget_activation':{'status':'verified','expected':'stock' if arm=='stock' else '8'},
            'ui_environment':{**{k:'unset' for k in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_ALL_STRING_FAST_PATH')},'OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS':'unset' if arm=='stock' else '8'},
            'open_to_completed_workload_ms':100 if arm=='stock' else 90}

class ComparisonTests(unittest.TestCase):
    def compare(self,change=lambda r:None):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);calls=[]
            for arm in ('stock','budget8'):
                for pair in (1,2,3):
                    r=trial(arm,pair)
                    if arm=='budget8' and pair==2:change(r)
                    p=root/f'performance-{arm}'/f'pair-{pair}'/'mixed-1mib-01'
                    p.mkdir(parents=True);(p/'measurements.json').write_text(json.dumps(r))
            env={'REPORTS':root,'json':json,'statistics':statistics,'record':lambda *a:calls.append(a)}
            exec(compile(ast.Module(body=[copy.deepcopy(FUNCTION)],type_ignores=[]),str(SOURCE),'exec'),env)
            with contextlib.redirect_stdout(io.StringIO()):env['compare_completed_trials']()
            self.assertEqual(len(calls),1)
            return json.loads((root/'paired-comparison.json').read_text())

    def test_all_complete_and_paths_may_differ(self):
        result=self.compare();self.assertTrue(result['completed_workload_comparison_available'])
        self.assertEqual(result['budget8_over_stock_readiness_ratio'],.9)

    def test_incomplete_trial_never_produces_ratio(self):
        for key,value in [('status','timeout'),('timeout',True),('exit_code',1),
                          ('keys_starting_with_lexer_invalid',0),('exact_resulting_source_verified',False),
                          ('post_typing_lexer_settle',{'complete':False}),('initial_coloring_key_samples',[{}]*79)]:
            with self.subTest(key=key):
                result=self.compare(lambda r:r.update({key:value}))
                self.assertFalse(result['completed_workload_comparison_available'])
                self.assertNotIn('budget8_over_stock_readiness_ratio',result)

    def test_activation_and_appearance_fail_closed(self):
        for key,value in [('scan_activation',{'status':'verified','expected':'candidate'}),
                          ('budget_activation',{'status':'verified','expected':'20'}),
                          ('ui_environment',{'OPENRACKET_UI':'modern'})]:
            with self.subTest(key=key):
                self.assertFalse(self.compare(lambda r:r.update({key:value}))['completed_workload_comparison_available'])

    def test_settings_runtime_and_fixture_must_match(self):
        for key,value in [('selected_language_settings',{'status':'complete','annotations':'debug'}),
                          ('preserved_settings',{'coloring':False}),('racket_version','different'),
                          ('fixture_metadata',{'sha256':'different'})]:
            with self.subTest(key=key):
                self.assertFalse(self.compare(lambda r:r.update({key:value}))['completed_workload_comparison_available'])

if __name__=='__main__':unittest.main()
