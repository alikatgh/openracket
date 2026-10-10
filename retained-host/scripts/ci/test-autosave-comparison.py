#!/usr/bin/env python3
"""Synthetic acceptance checks only; these are not native measurements."""
import ast,contextlib,copy,io,json,pathlib,statistics,tempfile,unittest
SOURCE=pathlib.Path(__file__).with_name('run-autosave.py')
FUNCTION=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='compare_completed_trials')

def trial(arm,pair):
    return {'status':'complete','exit_code':0,'timeout':False,'measurement_kind':'settled_editor_autosave',
            'initial_lexer_settle':{'complete':True},'final_lexer_settle':{'complete':True},
            'autosave_recovery':{**{k:True for k in ('recovery_toc_entry_verified','new_artifact_path_verified','exact_recovered_source','original_file_unchanged','filename_restored','format_restored','still_modified')},'artifact_bytes':10,'recovered_characters':11},
            'autosave_preconditions':{'lexer_valid':True,'modified':True,'autosave_enabled':True},
            'ui_environment':{k:'unset' for k in ('OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_THEME','OPENRACKET_ALL_STRING_FAST_PATH','OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS')},
            'selected_language_settings':{'status':'complete','annotations':'lang-default'},
            'preserved_settings':{k:'#t' for k in ('framework:autosaving-on?','framework:autosave-delay','framework:backup-files?','framework:verify-change-format')},'racket_version':'9.3','os':'unix','vm':'chez-scheme',
            'fixture_metadata':{'path':f'/{arm}/{pair}/fixture.rkt','sha256':'synthetic-fixture','characters':10},'loaded_characters':10,
            'scan_activation':{'status':'verified','expected':'stock'},
            'autosave_activation':{'status':'verified','expected':arm},
            'actual_autosave':{'command_ms':100 if arm=='stock' else 90,'command_plus_low_priority_fence_ms':101},'autosave_queued_gui_probe_ms':100,
            'native_max_rss_bytes':100,
            **{snapshot:{k:10 for k in ('racket_managed_bytes','racket_cumulative_allocated_bytes','racket_peak_allocated_bytes','process_cpu_ms','gc_ms')} for snapshot in ('memory_before_autosave','memory_after_autosave_command','memory_after_autosave')}}

class ComparisonTests(unittest.TestCase):
    def compare(self,change=lambda r:None):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);calls=[]
            for arm in ('stock','candidate'):
                for pair in (1,2,3):
                    r=trial(arm,pair)
                    if arm=='candidate' and pair==2:change(r)
                    p=root/f'performance-{arm}'/f'pair-{pair}'/'mixed-1mib-01';p.mkdir(parents=True)
                    (p/'measurements.json').write_text(json.dumps(r))
            env={'REPORTS':root,'json':json,'statistics':statistics,'record':lambda *a:calls.append(a)}
            exec(compile(ast.Module(body=[copy.deepcopy(FUNCTION)],type_ignores=[]),str(SOURCE),'exec'),env)
            with contextlib.redirect_stdout(io.StringIO()):env['compare_completed_trials']()
            self.assertEqual(len(calls),1)
            return json.loads((root/'paired-comparison.json').read_text())
    def test_complete_pair(self):
        r=self.compare();self.assertTrue(r['completed_workload_comparison_available']);self.assertEqual(r['candidate_over_stock_autosave_ratio'],.9)
    def test_partial_failed_or_no_recovery_blocks_ratio(self):
        for key,value in [('status','timeout'),('timeout',True),('exit_code',1),('initial_lexer_settle',{'complete':False}),('final_lexer_settle',{'complete':False}),('autosave_recovery',{}),('autosave_preconditions',{}),('autosave_queued_gui_probe_ms',None)]:
            with self.subTest(key=key):
                r=self.compare(lambda r:r.update({key:value}));self.assertFalse(r['completed_workload_comparison_available']);self.assertNotIn('candidate_over_stock_autosave_ratio',r)
    def test_activation_and_appearance_must_match(self):
        for key,value in [('scan_activation',{'status':'verified','expected':'candidate'}),('autosave_activation',{'status':'verified','expected':'stock'}),('ui_environment',{'OPENRACKET_UI':'modern'})]:
            with self.subTest(key=key):self.assertFalse(self.compare(lambda r:r.update({key:value}))['completed_workload_comparison_available'])
    def test_metadata_must_be_available_and_equal(self):
        for key,value in [('selected_language_settings',{'status':'partial'}),('preserved_settings',{'autosave_enabled':'UNAVAILABLE'}),('preserved_settings',{'autosave_enabled':'#f'}),('fixture_metadata',{'sha256':'changed'}),('racket_version','different')]:
            with self.subTest(key=key):self.assertFalse(self.compare(lambda r:r.update({key:value}))['completed_workload_comparison_available'])
if __name__=='__main__':unittest.main()
