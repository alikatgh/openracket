import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import struct
import zlib
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import compare_controls as gate
import run_native as runner

def test_png(width=2,height=2):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+b'\0'*6+b'\0'+b'\0'*6))+chunk(b'IEND',b'')
PNG=test_png()

def fixture(mode):
    stock=mode=='stock';enabled=mode=='candidate-on';root='/runtime/stock' if stock else '/runtime/candidate'
    source={'schema':'openracket-named-style-control-source/v1','mode':mode,'version':'9.3',
            'runtime_root':root,'executable':root+'/bin/racket','flag':None if stock else ('1' if enabled else '0'),
            'activation':'unexported' if stock else enabled,'state_export':'unexported' if stock else 'present',
            'source_first_load':True,'host_sha256':gate.HOST_SHA,
            'sources':{name:{'path':root+'/collects/'+name+'.rkt','sha256':pin['stock' if stock else 'candidate'] if type(pin) is dict else pin}
                       for name,pin in gate.PINS.items()}}
    result={'checks':31,'complete_stock_parity':False,'physical_input_to_photon_measured':False,
            'native_appearance_lifecycle':None,'status':'passed','genuine_host':True,'repeated_real_run':True,'ui':'stock','racket':'9.3',
            'follow_on_case':'check-syntax','follow_on_result':{'case':'check-syntax','status':'passed'}}
    process={'returncode':0,'timed_out':False,'native_executed':True,'timeout_seconds':60,
             'capture_attempted':True,'capture_done_written':True,'capture_returncode':0,
             'screenshot':gate.png_record(PNG),'runtime_root':root,'arm':mode,
             'command':[root+'/bin/racket','/controls/native/bootstrap.rkt',mode,root],
             'named_style_flag':source['flag']}
    return source,copy.deepcopy(gate.EDGES),result,process

def encode(source,graph,result):
    return ('OPENRACKET_NAMED_STYLE_CONTROL_SOURCE '+json.dumps(source)+'\nOPENRACKET_BINDING_GRAPH '+json.dumps(graph)+
            '\nOPENRACKET_NATIVE_RESULT '+json.dumps(result)+'\nOPENRACKET_FOLLOWON_CASE check-syntax completed\nOPENRACKET_NATIVE_READY\n').encode()

def validate(parts,mode):
    source,graph,result,process=parts
    return gate.validate(encode(source,graph,result),json.dumps(result).encode(),process,mode,PNG)

class GraphMutations(unittest.TestCase):
    def test_three_modes_exact_fixture_and_explicit_scope(self):
        rows={mode:validate(fixture(mode),mode) for mode in gate.MODES}
        result=gate.compare(rows)
        self.assertTrue(result['accepted']);self.assertEqual(result['zero_span_edges_per_mode'],4)
        self.assertIn('not proof about filtered entries',result['scope'])
        self.assertNotIn('complete_graph',result)
    def test_every_edge_and_integer_type_is_mandatory_in_every_mode(self):
        for mode in gate.MODES:
            for n in range(8):
                for mutation in ('delete','duplicate','reverse','bool','float','changed'):
                    with self.subTest(mode=mode,edge=n,mutation=mutation):
                        parts=fixture(mode);edges=parts[1]
                        if mutation=='delete':edges.pop(n)
                        elif mutation=='duplicate':edges.append(copy.deepcopy(edges[n]))
                        elif mutation=='reverse':edges[n]=edges[n][2:]+edges[n][:2]
                        else:edges[n][0]={'bool':True,'float':float(edges[n][0]),'changed':99}[mutation]
                        with self.assertRaises(gate.Refused):validate(parts,mode)
    def test_all_four_zero_spans_preserved(self):
        zeros=[i for i,e in enumerate(gate.EDGES) if e[2]==e[3]]
        self.assertEqual(len(zeros),4)
        for i in zeros:
            parts=fixture('candidate-on');parts[1][i][3]+=1
            with self.assertRaises(gate.Refused):validate(parts,'candidate-on')
    def test_stock_and_activation_exports_cannot_be_faked(self):
        for mode in gate.MODES:
            for key,value in [('flag','unexpected'),('flag',True),('activation',0),('activation',1),
                              ('state_export','missing'),('source_first_load',False),('mode','wrong'),
                              ('host_sha256','0'*64),('runtime_root','/runtime/../else'),('executable','/else/racket')]:
                with self.subTest(mode=mode,key=key,value=value):
                    parts=fixture(mode);parts[0][key]=value
                    with self.assertRaises(gate.Refused):validate(parts,mode)
    def test_every_runtime_pin_and_path_are_mandatory(self):
        for mode in gate.MODES:
            for name in gate.PINS:
                for key,value in [('sha256','0'*64),('path','/escape/'+name+'.rkt')]:
                    parts=fixture(mode);parts[0]['sources'][name][key]=value
                    with self.subTest(mode=mode,module=name,key=key),self.assertRaises(gate.Refused):validate(parts,mode)
    def test_source_records_cannot_be_dropped_added_or_relabelled(self):
        for mutation in ('drop','add','field'):
            parts=fixture('stock');sources=parts[0]['sources']
            if mutation=='drop':sources.pop(next(iter(sources)))
            elif mutation=='add':sources['extra']={}
            else:sources[next(iter(sources))]['extra']=True
            with self.assertRaises(gate.Refused):validate(parts,'stock')
    def test_timeout_launch_failure_handshake_and_caller_mismatch_rejected(self):
        for key,value in [('returncode',True),('returncode',1),('timed_out',True),('native_executed',False),
                          ('timeout_seconds',61),('timeout_seconds',60.0),('capture_attempted',False),
                          ('capture_done_written',False),('runtime_root','/other'),('arm','candidate-off'),
                          ('named_style_flag','0'),('command',[])]:
            parts=fixture('stock');parts[3][key]=value
            with self.subTest(key=key),self.assertRaises(gate.Refused):validate(parts,'stock')
    def test_missing_duplicate_and_malformed_markers_rejected(self):
        parts=fixture('stock');source,edges,result,process=parts;raw=encode(source,edges,result)
        for prefix in ['OPENRACKET_NAMED_STYLE_CONTROL_SOURCE','OPENRACKET_BINDING_GRAPH','OPENRACKET_NATIVE_RESULT','OPENRACKET_NATIVE_READY']:
            for changed in [raw.replace(prefix.encode(),b'MISSING'),raw+(prefix+' {}\n').encode(),raw.replace(prefix.encode(),('BAD '+prefix).encode())]:
                with self.subTest(prefix=prefix),self.assertRaises((ValueError,gate.Refused)):
                    gate.validate(changed,json.dumps(result).encode(),process,'stock',PNG)
    def test_failed_host_mismatched_ready_and_workflow_rejected(self):
        parts=fixture('stock');raw=encode(*parts[:3])
        with self.assertRaises(gate.Refused):gate.validate(raw,b'{}',parts[3],'stock',PNG)
        for key,value in [('status','failed'),('genuine_host',1),('repeated_real_run',False),('follow_on_case','stop'),('follow_on_result',{}),('checks',True),('checks',0),('checks',31.0),('complete_stock_parity',True),('physical_input_to_photon_measured',True),('native_appearance_lifecycle',{})]:
            parts=fixture('stock');parts[2][key]=value
            with self.subTest(key=key),self.assertRaises(gate.Refused):validate(parts,'stock')
    def test_nonfinite_and_duplicate_json_rejected(self):
        for raw in ['{"x":1,"x":2}','{"x":NaN}']:
            with self.assertRaises(gate.Refused):gate.decode(raw)
    def test_screenshot_capture_record_and_bytes_fail_closed(self):
        for key,value in [('capture_returncode',1),('capture_returncode',True),('screenshot',{})]:
            parts=fixture('stock');parts[3][key]=value
            with self.subTest(key=key),self.assertRaises(gate.Refused):validate(parts,'stock')
        parts=fixture('stock');raw=encode(*parts[:3])
        for png in [b'',b'bad',PNG[:-1],PNG+b'extra',PNG[:40]+b'bad'+PNG[43:],test_png(0,2)]:
            with self.assertRaises(gate.Refused):gate.validate(raw,json.dumps(parts[2]).encode(),parts[3],'stock',png)
    def test_validation_preserves_inputs_and_original_raw_bytes(self):
        parts=fixture('stock');before=copy.deepcopy(parts);raw=encode(*parts[:3]);result=validate(parts,'stock')
        self.assertEqual(parts,before);self.assertEqual(result['raw_sha256'],hashlib.sha256(raw).hexdigest())
    def test_missing_arm_rejected(self):
        with self.assertRaises(gate.Refused):gate.compare({'stock':validate(fixture('stock'),'stock')})

class CallerAndSourceTests(unittest.TestCase):
    def test_exact_accepted_sources_and_all_tool_dependencies(self):
        runner.check_package()
        pins=json.loads((ROOT/'PROVENANCE.json').read_text())['unchanged_copies']
        tools=[key for key in pins if key.startswith('native/tool/')]
        self.assertEqual(len(tools),6)
        for path in (ROOT/'native').rglob('*.rkt'):
            for dep in re.findall(r'"((?:\.\./)?(?:tool/|tests/)?(?:native-|independent-|reference-)[-a-z0-9/]*\.rkt)"',path.read_text()):
                self.assertTrue((path.parent/dep).is_file(),str(path)+': '+dep)
        self.assertEqual(hashlib.sha256((ROOT/'native/tests/reference-host-0520.rkt').read_bytes()).hexdigest(),gate.HOST_SHA)
    def test_no_eager_postflight_or_candidate_binding_source(self):
        native='\n'.join(p.read_text() for p in (ROOT/'native').rglob('*.rkt'))
        self.assertNotIn('binding-postflight',native);self.assertNotIn('BINDING_TABLE',native)
        self.assertNotIn('OPENRACKET_NATIVE_BINDINGS_OK',native)
    def test_wrapper_only_reads_state_export_and_invokes_unchanged_host(self):
        s=(ROOT/'native/bootstrap.rkt').read_text()
        for value in ["[use-compiled-file-paths '()]",'module->namespace',"(lambda () missing)",'(dynamic-require host #f)',
                      "'openracket-named-style-index-enabled?","'openracket-named-style-index-state"]:self.assertIn(value,s)
        self.assertNotIn('(state ',s);self.assertNotIn('find-named-style',s);self.assertNotIn('new style',s)
    def test_exact_flag_and_fresh_profiles_for_all_seven_callers(self):
        profiles=[]
        for host,arms in [(True,runner.HOST_ARMS),(False,runner.TRACE_ARMS)]:
            for arm in arms:
                profile=Path('/evidence')/('host-' if host else 'trace-')/arm
                profiles.append(profile);env=runner.environment({'PATH':'/usr/bin'},arm,profile,host)
                expected=None if arm.startswith('stock') else ('1' if arm.endswith('-on') else '0')
                self.assertEqual(env.get('OPENRACKET_NAMED_STYLE_INDEX'),expected)
                self.assertEqual(env['PLTUSERHOME'],str(profile));self.assertNotIn('OPENRACKET_XREF_REPLY_CELL',env)
                if host:self.assertEqual(env['OPENRACKET_NATIVE_CASE'],'check-syntax')
        self.assertEqual(len(set(profiles)),7)
    def test_every_trace_caller_is_stock_and_outputs_distinct_raw_capture(self):
        commands=[runner.command(Path('/runtime'),arm,Path('/output')/arm,False) for arm in runner.TRACE_ARMS]
        for command in commands:self.assertEqual(command[command.index('--mode')+1],'stock')
        self.assertEqual(len({command[-1] for command in commands}),4)
        self.assertEqual([c[-3] for c in commands],['30']*4)
    def test_contaminated_environment_always_refused(self):
        for key in runner.BANNED|{'OPENRACKET_BINDING_TABLE_EAGER','OPENRACKET_XREF_REPLY_CELL','OPENRACKET_NAMED_STYLE_INDEX','OPENRACKET_UI'}:
            with self.subTest(key=key),self.assertRaises(ValueError):runner.environment({key:'1'},'stock',Path('/profile'))
    def test_all_seven_arms_attempted_after_independent_failures(self):
        attempted=[]
        def fail(runtime,arm,out,host):attempted.append((arm,host));raise ValueError('synthetic failure')
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'capture',side_effect=fail):
            result=runner.run_matrix(Path('/stock'),Path('/candidate'),Path(tmp))
        self.assertEqual(len(attempted),7);self.assertEqual(len(result['failures']),7);self.assertFalse(result['passed'])
    def test_bound_and_ready_capture_preserved_in_exact_host(self):
        host=(ROOT/'native/tests/reference-host-0520.rkt').read_text()
        for value in ['OPENRACKET_READY_FILE','OPENRACKET_CAPTURE_DONE','20000','OPENRACKET_NATIVE_READY','(wait-for-capture!)']:
            self.assertIn(value,host)
        runner_source=(ROOT/'scripts/run_native.py').read_text()
        self.assertIn('timeout=60 if host else 200',runner_source)
        self.assertIn('clock()>=deadline',runner_source)
        self.assertIn("'/usr/sbin/screencapture','-x'",runner_source)
    def test_named_comparator_is_external_label_only_derivative(self):
        p=ROOT/'trace/generate-named-style-comparator.py'
        spec=importlib.util.spec_from_file_location('labels',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.generated_source(),(ROOT/'trace/compare-named-style-trace.py').read_text())
        original=(ROOT/'trace/compare-binding-trace.py').read_text()
        transformed=(ROOT/'trace/compare-named-style-trace.py').read_text()
        for old,new in reversed(module.REPLACEMENTS):transformed=transformed.replace(new,old)
        self.assertEqual(original,transformed)
    def test_racket_wrapper_delimiters_balanced(self):
        source=(ROOT/'native/bootstrap.rkt').read_text();stack=[];string=escape=comment=False
        for c in source:
            if comment:
                if c=='\n':comment=False
                continue
            if string:
                if escape:escape=False
                elif c=='\\':escape=True
                elif c=='"':string=False
                continue
            if c==';':comment=True
            elif c=='"':string=True
            elif c in '([{':stack.append(c)
            elif c in ')]}':self.assertTrue(stack);self.assertEqual('([{'.index(stack.pop()),')]}'.index(c))
        self.assertFalse(stack);self.assertFalse(string)

class BoundedCaptureTests(unittest.TestCase):
    def simulate(self,shot_seconds=0,launch_error=False,shot_error=False,shot_code=0,malformed_png=False,never_finishes=False,ready_after=0):
        ticks=[0.0];calls=[]
        class Process:
            pid=987654321
            def __init__(self,cmd,**kw):
                if launch_error:raise OSError('synthetic launch failure')
                self.done=Path(kw['env']['OPENRACKET_CAPTURE_DONE']);self.killed=False
                self.ready=Path(kw['env']['OPENRACKET_READY_FILE'])
                kw['stdout'].write(b'raw stdout\x00\xff');kw['stderr'].write(b'raw stderr\x00\xff')
            def poll(self):
                if ticks[0]>=ready_after and not self.ready.exists():self.ready.write_text('{}')
                return -9 if self.killed else (None if never_finishes or not self.done.exists() else 0)
            def wait(self,timeout):return self.poll()
        def shot(cmd,**kw):
            calls.append((cmd,kw['timeout']));ticks[0]+=shot_seconds
            if shot_error:raise OSError('synthetic capture failure')
            Path(cmd[-1]).write_bytes(b'PNG malformed fixture' if malformed_png else PNG)
            return type('Result',(),{'returncode':shot_code})()
        def terminate(proc):proc.killed=True
        def sleep(seconds):ticks[0]+=seconds
        with tempfile.TemporaryDirectory() as tmp,patch.dict(runner.os.environ,{'PATH':'/usr/bin'},clear=True),patch.object(runner,'terminate',side_effect=terminate):
            output=Path(tmp)/'host'
            result=runner.capture(Path('/runtime'),'stock',output,True,popen=Process,
                                  clock=lambda:ticks[0],sleep=sleep,screen=shot)
            files={p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}
        return result,files,calls
    def test_success_preserves_raw_bytes_and_capture_handshake(self):
        result,files,calls=self.simulate()
        self.assertEqual(result['returncode'],0);self.assertFalse(result['timed_out'])
        self.assertTrue(result['capture_attempted']);self.assertTrue(result['capture_done_written'])
        self.assertEqual(len(calls),1);self.assertEqual(files['stdout.bin'],b'raw stdout\x00\xff')
        self.assertEqual(files['stderr.bin'],b'raw stderr\x00\xff')
        self.assertEqual(result['files']['stdout.bin']['sha256'],hashlib.sha256(files['stdout.bin']).hexdigest())
    def test_successful_exit_after_outer_deadline_still_fails(self):
        result,files,calls=self.simulate(shot_seconds=61)
        self.assertTrue(result['timed_out']);self.assertEqual(result['timeout_seconds'],60)
        self.assertTrue(result['capture_attempted'])
    def test_exact_deadline_is_also_timeout(self):
        result,files,calls=self.simulate(shot_seconds=59.8)
        self.assertTrue(result['timed_out'])
    def test_screenshot_wait_is_bounded(self):
        result,files,calls=self.simulate()
        self.assertEqual(calls[0][1],15)
        result,files,calls=self.simulate(ready_after=54)
        self.assertGreater(calls[0][1],0);self.assertLessEqual(calls[0][1],6)
    def test_nonzero_screenshot_and_malformed_png_never_supply_valid_evidence(self):
        for kw in ({'shot_code':1},{'malformed_png':True}):
            result,files,calls=self.simulate(**kw)
            self.assertNotIn('screenshot',result)
    def test_hanging_host_is_terminated(self):
        result,files,calls=self.simulate(never_finishes=True)
        self.assertTrue(result['timed_out']);self.assertEqual(result['returncode'],-9)
    def test_capture_failure_is_retained_without_fabricating_screenshot(self):
        result,files,calls=self.simulate(shot_error=True)
        self.assertTrue(result['capture_done_written']);self.assertIn('capture_error',result)
        self.assertNotIn('screenshot.png',files)
    def test_launch_error_never_counts_as_native_execution(self):
        result,files,calls=self.simulate(launch_error=True)
        self.assertFalse(result['native_executed']);self.assertIsNone(result['returncode'])
        self.assertFalse(result['timed_out']);self.assertFalse(result['capture_attempted']);self.assertFalse(calls)

if __name__=='__main__':unittest.main()
