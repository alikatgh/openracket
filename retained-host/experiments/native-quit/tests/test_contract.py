"""Validator unit tests only. Synthetic records below are never native results."""
import copy,importlib.util,json,pathlib,secrets,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));import quit_contract as C
class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);r=pathlib.Path(self.temp.name)
        for p in ('evidence','profile','app/Contents/MacOS','runtime'):(r/p).mkdir(parents=True)
        (r/'app/Contents/MacOS/native').write_bytes(b'fixture-only-not-executable')
        text='#lang racket/base\n(define gate-answer 42)\n';(r/"Quit λ's.rkt").write_bytes(text.encode())
        self.c={'schema':1,'run_id':secrets.token_hex(12),'mode':'stock','case':'save','root_dir':str(r),'output_dir':str(r/'evidence'),'profile_path':str(r/'profile'),'app_path':str(r/'app'),'native_executable_path':str(r/'app/Contents/MacOS/native'),'bundle_id':'org.example.unit-only','fixture_path':str(r/"Quit λ's.rkt"),'original_text':text,'edited_text':text+';; intended edit: café 日本語\n','runtime_root':str(r/'runtime'),'step_tokens':{},'memory_mib':128,'process_timeout_seconds':150}
        self.tokens()
    def tokens(self):self.c['step_tokens']={x:secrets.token_hex(24) for x in C.stages(self.c)}
    def records(self):
        c=self.c;rows=[];frame=10
        for stage in C.stages(c):
            r={**C.envelope(c,stage),'status':'ready','checks':42,'test_actor':True,'handler_replaced':False,'test_exit_used':False,'entrypoint_replaced':False,
               'identity':{'pid':42,'running_pid':42,'same_running_application':True,'process_image_path':c['native_executable_path'],'running_bundle_path':c['app_path'],'main_bundle_path':c['app_path'],'running_bundle_identifier':c['bundle_id'],'main_bundle_identifier':c['bundle_id']},
               'host':{**{k:i+10 for i,k in enumerate(C.ID_KEYS)},'filename':c['fixture_path'],'text':c['original_text'] if stage=='ready' or c['case']=='clean' else c['edited_text'],'modified':stage!='ready' and c['case']!='clean','disk_sha256':C.digest(c['original_text'].encode()),'verify_exit':True,'handler_unchanged':True},
               'mode_evidence':{'mode':c['mode'],'memory_mib':c['memory_mib'],'finder_or_apple_event_route_tested':False,'stock_control':'official-generator native app running unchanged DrRacket','native':False},'sources':[{'module':m,'sha256':v} for m,v in C.SOURCE_PINS.items()],'evidence':{}}
            e=r['evidence']
            if stage=='ready':e.update(fixture_opened_by_driver=False,fixture_mutated=False)
            elif stage.startswith('quit-confirm'):e.update(kind='quit',shown=True,dialog_id=100+len(rows),message='unit-only localized confirmation',labels=['Quit','Do not quit'],checkbox_values=[False],request_attempt=int(stage[-1]),request_frame_id=frame,parent_frame_id=False)
            elif stage.startswith('unsaved'):e.update(kind='unsaved',shown=True,dialog_id=100+len(rows),message='unit-only localized unsaved message',labels=['Save','Cancel','Do not save'],checkbox_values=[],request_attempt=int(stage[-1]),request_frame_id=frame,parent_frame_id=frame)
            elif stage=='cancelled':e.update(exit_state_reset=True,live_identity_preserved=True,responsive_gui_turns=11,stable_ms=1050,focus_restored=True,focus_frame_id=frame,edit_target_frame_id=frame)
            elif stage=='terminal-response':
                prior=rows[-1]['report']['evidence'];r={**C.envelope(c,stage),'status':'response-dispatched','case':c['case'],'pid':42,'test_exit_used':False,'handler_replaced':False,'cleanup_used':False,'response':{'callback_returned':True,'modal_dismissed':True,'event':'button','dialog_id':prior['dialog_id'],'button_id':500,'label':prior['labels'][2 if c['case']=='discard' else 0]}}
            rows.append({'stage':stage,'report':r,'capture_ok':True,'ack_written':True,'screenshot_sha256':'a'*64})
        return rows
    def valid(self,rows=None,**overrides):
        k=dict(cleanup_used=False,failure_seen=False,survivors=[]);k.update(overrides)
        return C.validate_complete(self.c,self.records() if rows is None else rows,42,0,12,self.c['edited_text' if self.c['case']=='save' else 'original_text'].encode(),**k)
    def test_valid_config(self):self.assertEqual(C.validate_config(self.c),self.c)
    def test_exact_schema_keys_types_and_modes(self):
        for key,val in [('schema',True),('schema',2),('case','save-as'),('mode','modern-light'),('memory_mib',256),('process_timeout_seconds',151),('run_id','short')]:
            c=copy.deepcopy(self.c);c[key]=val
            with self.subTest(key=key,value=val),self.assertRaises(ValueError):C.validate_config(c)
        c=copy.deepcopy(self.c);c['extra']=1
        with self.assertRaises(ValueError):C.validate_config(c)
    def test_fixtures_bounded_and_edit_append_only(self):
        for val in ['#lang racket/base\nreplacement\n',self.c['original_text']+'not a comment\n',self.c['original_text']+';; '+('x'*4097)+'\n']:
            c=copy.deepcopy(self.c);c['edited_text']=val
            with self.subTest(val=val[:30]),self.assertRaises(ValueError):C.validate_config(c)
    def test_initial_disk_and_symlink_refusal(self):
        f=pathlib.Path(self.c['fixture_path']);f.write_bytes(b'wrong')
        with self.assertRaises(ValueError):C.validate_config(self.c)
        f.write_bytes(self.c['original_text'].encode());alias=f.with_name('alias');alias.symlink_to(f);self.c['fixture_path']=str(alias)
        with self.assertRaises(ValueError):C.validate_config(self.c)
    def test_tokens_exact_unique_and_stage_bound(self):
        for change in ('missing','duplicate','extra','bad'):
            c=copy.deepcopy(self.c);ts=c['step_tokens']
            if change=='missing':ts.pop('dirty')
            elif change=='duplicate':ts['dirty']=ts['ready']
            elif change=='extra':ts['unknown']=secrets.token_hex(24)
            else:ts['dirty']='short'
            with self.subTest(change=change),self.assertRaises(ValueError):C.validate_config(c)
    def test_all_three_complete_protocols(self):
        for case in ('clean','save','discard'):
            self.c['case']=case;self.tokens();self.assertEqual(self.valid()['status'],'passed')
    def test_each_exit_failure_is_final(self):
        rows=self.records()
        for code in (1,2,124,-9,-15,False):
            with self.subTest(code=code),self.assertRaises(ValueError):C.validate_complete(self.c,rows,42,code,12,self.c['edited_text'].encode(),cleanup_used=False,failure_seen=False,survivors=[])
    def test_cleanup_failure_and_survivor_can_never_pass(self):
        for k in (dict(cleanup_used=True),dict(failure_seen=True),dict(survivors=[{'pid':42}])):
            with self.subTest(k=k),self.assertRaises(ValueError):self.valid(**k)
    def test_timeout_exit_cannot_pass(self):
        for elapsed in (150,151,-1,float('nan'),float('inf'),float('-inf'),10**1000,-(10**1000)):
            with self.subTest(elapsed=elapsed),self.assertRaises(ValueError):C.validate_complete(self.c,self.records(),42,0,elapsed,self.c['edited_text'].encode(),cleanup_used=False,failure_seen=False,survivors=[])
    def test_missing_duplicate_or_reordered_stage_refused(self):
        rows=self.records()
        for rr in (rows[:-1],rows+[rows[-1]],rows[:2]+[rows[3],rows[2]]+rows[4:]):
            with self.assertRaises(ValueError):self.valid(rr)
    def test_bad_envelope_pid_or_image_refused(self):
        for path,val in [(('token',),'wrong'),(('schema',),True),(('identity','pid'),43),(('identity','running_pid'),41),(('identity','same_running_application'),False),(('identity','process_image_path'),self.c['fixture_path']),(('identity','main_bundle_identifier'),'other')]:
            rows=self.records();d=rows[0]['report']
            for p in path[:-1]:d=d[p]
            d[path[-1]]=val
            with self.subTest(path=path),self.assertRaises(ValueError):self.valid(rows)
    def test_cancel_retains_all_objects_and_dirty_text(self):
        for key in C.ID_KEYS+('text','modified','disk_sha256','verify_exit','handler_unchanged'):
            rows=self.records();h=rows[4]['report']['host'];h[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):self.valid(rows)
    def test_cancel_focus_and_liveness_required(self):
        for key,val in [('focus_restored',False),('focus_frame_id',11),('edit_target_frame_id',11),('responsive_gui_turns',2),('stable_ms',999),('exit_state_reset',False),('live_identity_preserved',False)]:
            rows=self.records();rows[4]['report']['evidence'][key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.valid(rows)
    def test_modal_parent_attempt_and_checkbox_refusals(self):
        for index,key,val in [(2,'parent_frame_id',10),(2,'request_attempt',2),(2,'request_frame_id',11),(2,'checkbox_values',[True]),(3,'parent_frame_id',False),(3,'kind','file-picker'),(3,'shown',False),(3,'labels',['Save'])]:
            rows=self.records();rows[index]['report']['evidence'][key]=val
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):self.valid(rows)
    def test_terminal_callback_and_expected_choice_required(self):
        for key,val in [('callback_returned',False),('modal_dismissed',False),('dialog_id',999),('event','fake'),('label','Cancel')]:
            rows=self.records();rows[-1]['report']['response'][key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.valid(rows)
    def test_independent_post_exit_disk_bytes(self):
        with self.assertRaises(ValueError):C.validate_complete(self.c,self.records(),42,0,12,self.c['original_text'].encode(),cleanup_used=False,failure_seen=False,survivors=[])
    def test_nonfinite_stability_and_inexact_count_fields_refused(self):
        for key,value in [('stable_ms',float('nan')),('stable_ms',float('inf')),('stable_ms',float('-inf')),('stable_ms',10**1000),('stable_ms',-(10**1000)),('responsive_gui_turns',True),('responsive_gui_turns',11.0),('focus_frame_id',10.0),('edit_target_frame_id',10.0)]:
            rows=self.records();rows[4]['report']['evidence'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.valid(rows)
        for key,value in [('request_attempt',True),('request_attempt',1.0),('request_frame_id',10.0)]:
            rows=self.records();rows[2]['report']['evidence'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.valid(rows)
    def test_json_loader_rejects_constants_and_duplicate_keys(self):
        spec=importlib.util.spec_from_file_location('quit_runner',ROOT/'scripts/run-case.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        p=pathlib.Path(self.temp.name)/'parser-input.json'
        for text in ['{"value":NaN}','{"value":Infinity}','{"value":-Infinity}','{"value":1e9999}','{"x":1,"x":2}','{} {}']:
            p.write_text(text)
            with self.subTest(text=text),self.assertRaises(ValueError):m.load_json(p)
        p.write_text('{"value":1.25}');self.assertEqual(m.load_json(p),{'value':1.25})
    def test_every_source_pin_and_scope_flag_required(self):
        for key in ('handler_replaced','test_exit_used','entrypoint_replaced'):
            rows=self.records();rows[0]['report'][key]=True
            with self.assertRaises(ValueError):self.valid(rows)
        rows=self.records();rows[0]['report']['sources'][0]['sha256']='f'*64
        with self.assertRaises(ValueError):self.valid(rows)
    def test_every_screenshot_and_ack_required(self):
        for key,val in [('capture_ok',False),('ack_written',False),('screenshot_sha256','')]:
            rows=self.records();rows[3][key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.valid(rows)
if __name__=='__main__':unittest.main(verbosity=2)
