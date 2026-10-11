#!/usr/bin/env python3
"""Focused offline adapter tests. Never starts a native application."""
import ast,base64,contextlib,hashlib,importlib.util,io,json,os,pathlib,subprocess,sys,tempfile,types,unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=(ROOT/'run-editor-diagnostic.py').read_text()
BASE=(ROOT/'run-named-style.py').read_text()
WORKFLOW=(ROOT.parents[2]/'.github/workflows/retained-native.yml').read_text()
EXP=ROOT.parents[1]/'experiments/named-style'
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
EMITTER=module('focused_emitter','emit-replay-evidence.py')
DECODER=module('focused_decoder','decode-replay-evidence.py')
EVIDENCE=module('focused_evidence','named-style-evidence.py')
def node(name,source=SOURCE):
 return next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
class AdapterTests(unittest.TestCase):
 def functions(self,folder):
  rows=[];namespace={'pathlib':pathlib,'json':json,'sys':sys,'hashlib':hashlib,'base64':base64,'ROOT':folder,'REPORTS':folder,'CLEANUP_BLOCK':folder/'launch-blocked.json','PHASE':'editor','CLEANUP_UNVERIFIED':False,'env':lambda *args:{},'record':lambda name,ok,detail='':rows.append((name,ok,detail)),'emitter':EMITTER,'evidence':EVIDENCE}
  nodes=[n for n in ast.parse(SOURCE).body if isinstance(n,ast.FunctionDef) and n.name in ('command','collection','emit','transport_bytes','logs_and_reports','verify_frozen')]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'adapter-functions','exec'),namespace)
  return namespace,rows
 def test_only_three_phases_and_no_timing_production_or_control_execution(self):
  ast.parse(SOURCE)
  self.assertIn("('prepare','editor','verify')",SOURCE)
  for value in ("PHASE=='telemetry'","PHASE=='production'","PHASE=='controls'","PHASE=='helpers'","TELEMETRY/'capture.py'","TELEMETRY/'native_preflight.py'","PRODUCTION/'scripts/run_native.py'","CONTROLS/'scripts/run_native.py'","contract.trial_order()","validate-named-style-matrix.py"):
   self.assertNotIn(value,SOURCE)
  self.assertEqual(SOURCE.count("EDITOR/'scripts/run_native.py'"),1)
 def test_original_command_lease_resolution_and_source_checks_preserved_exactly(self):
  for name in ('command','collection','verify_sources','env','runtime'):
   self.assertEqual(ast.dump(node(name)),ast.dump(node(name,BASE)),name)
 def test_original_source_pin_pending_fails_closed_or_exact_frozen(self):
  assignment=next(n for n in ast.parse(SOURCE).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='COMPOSITION_PIN' for t in n.targets))
  pin=ast.literal_eval(assignment.value)
  with tempfile.TemporaryDirectory() as d:
   ns,_=self.functions(pathlib.Path(d));ns.update(COMPOSITION_PIN=pin,EXP=EXP,TELEMETRY=EXP/'performance',PRODUCTION=EXP/'production',TELEMETRY_PIN='840fe01e282b60ee8613a87c63e7e7ed21233741c3fb30eb923dcd3bec75bdc4')
   if pin.startswith('PENDING_'):
    with self.assertRaisesRegex(AssertionError,'pin is pending'):ns['verify_frozen']()
   else:ns['verify_frozen']()
 def test_independent_clones_and_only_named_style_applier(self):
  for purpose in ('named-style-control','named-style-candidate'):
   self.assertIn(purpose,SOURCE);self.assertIn("['"+purpose+"']",(ROOT/'copy-independent-runtime.py').read_text())
  self.assertIn("PRODUCTION/'scripts/overlay.py','apply'",SOURCE)
  self.assertNotIn('binding-table-eager',SOURCE)
 def test_every_editor_module_compiled_and_new_observers_explicit(self):
  self.assertIn("native_modules=sorted((EDITOR/'native').rglob('*.rkt'))",SOURCE)
  for name in ('failure-observation.rkt','reload-diagnostic.rkt'):self.assertIn("EDITOR/'native/"+name+"'",SOURCE)
  self.assertIn("for mode in ('stock','candidate-off','candidate-on'):",SOURCE)
  self.assertIn("*native_modules],mode=mode,purpose='compile',timeout=240)",SOURCE)
 def test_existing_editor_cli_four_arms_deadlines_and_fresh_profiles(self):
  runner=(EXP/'editor/scripts/run_native.py').read_text()
  comparator=(EXP/'editor/scripts/compare.py').read_text()
  self.assertIn('timeout=180',runner);self.assertIn('timeout=760,required=False',SOURCE)
  self.assertIn('for mode in compare.MODES:',runner)
  self.assertIn('MODES = ("stock", "stock-again", "off", "on")',comparator)
  self.assertIn('profile = output / "profile"',runner)
  self.assertIn('env["PLTADDONDIR"] = str(profile / "addon")',runner)
  self.assertIn('if output.exists():',runner)
  for flag in ('--stock-racket','--stock-root','--candidate-racket','--candidate-root','--output','--authorize-native-execution'):self.assertIn(flag,SOURCE)
  self.assertIn('environment=contract.clean_environment(os.environ)',SOURCE)
 def test_unchanged_runner_attempts_all_four_after_capture_failures(self):
  path=EXP/'editor/scripts/run_native.py'
  saved=sys.modules.get('compare');sys.path.insert(0,str(path.parent))
  try:
   compare_spec=importlib.util.spec_from_file_location('compare',path.parent/'compare.py');compare=importlib.util.module_from_spec(compare_spec);compare_spec.loader.exec_module(compare);sys.modules['compare']=compare
   spec=importlib.util.spec_from_file_location('focused_editor_runner',path);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
   with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
    root=pathlib.Path(d);stock=root/'stock';candidate=root/'candidate';arms=[]
    for runtime in (stock,candidate):
     (runtime/'bin').mkdir(parents=True);exe=runtime/'bin/racket';exe.write_text('mock only');exe.chmod(0o700)
    argv=[str(path),'--stock-racket',str(stock/'bin/racket'),'--stock-root',str(stock),'--candidate-racket',str(candidate/'bin/racket'),'--candidate-root',str(candidate),'--output',str(root/'out'),'--authorize-native-execution']
    def fail(exe,runtime,mode,output):
     arms.append((mode,runtime,output));raise RuntimeError('retained original '+mode+' error')
    with patch.object(sys,'argv',argv),patch.object(runner,'capture',side_effect=fail):code=runner.main()
    self.assertEqual(code,1);self.assertEqual([v[0] for v in arms],['stock','stock-again','off','on'])
    self.assertEqual([v[1] for v in arms],[stock,stock,candidate,candidate]);self.assertEqual(len({v[2] for v in arms}),4)
    report=json.loads((root/'out/report.json').read_text());self.assertFalse(report['passed']);self.assertEqual(len(report['failures']),4)
    for item in report['failures']:self.assertIn('retained original '+item['mode']+' error',item['details'])
  finally:
   sys.path.pop(0)
   if saved is None:sys.modules.pop('compare',None)
   else:sys.modules['compare']=saved
 def test_all_portable_source_checks_keep_explicit_official_gui_source(self):
  for value in ("PRODUCTION/'tests/source_test.py'","PRODUCTION/'tests/snapshot_model.py'","for package in (EDITOR,CONTROLS)","GUI_TEST_SOURCE_DIR","collection('stock','drracket/private/module-language').parent","'test_accept_gui','test_accept_named_style','test_capture','test_gui_source','test_prepared_runtime','test_telemetry'"):
   self.assertIn(value,SOURCE)
  self.assertNotIn("'test_gui_native'",SOURCE)
 def test_baseline_before_native_and_unconditional_full_witness(self):
  prepare=SOURCE[SOURCE.index("if PHASE=='prepare':"):SOURCE.index("elif PHASE=='editor':")]
  self.assertLess(prepare.index('Full pristine runtime baseline'),prepare.index('verify_frozen()'))
  self.assertIn("'compare',ORIGINAL,TEMP/'editor-diagnostic-pristine-tree.json'",SOURCE)
  self.assertIn("id: editor_witness\n        if: always() && steps.runtime.outcome == 'success'",WORKFLOW)
 def test_editor_evidence_collected_in_finally_without_native_launch(self):
  self.assertIn('finally:logs_and_reports(destination)',SOURCE)
  for name in ('emit','transport_bytes','logs_and_reports'):
   body=ast.get_source_segment(SOURCE,node(name))
   self.assertNotIn('subprocess',body);self.assertNotIn('command(',body)
  self.assertIn("sys.exit(1 if any(not r['passed'] for r in ROWS[START:]) else 0)",SOURCE)
 def test_lossless_capture_arrays_unicode_long_original_errors_and_binary(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);ns,rows=self.functions(root);case=root/'editor/stock';case.mkdir(parents=True)
   value={'status':'failed','original_error':'reader 🦋 failure '*3000,'wxme_reload_diagnostic':{'full_file_bytes':list(range(256))*90,'position':0,'false_is_false':False}}
   original=json.dumps(value,ensure_ascii=False).encode();(case/'capture.json').write_bytes(original)
   binary=bytes(range(256))*100;(case/'stderr.bin').write_bytes(binary)
   # A blocked native lease must not stop evidence emission.
   ns['CLEANUP_BLOCK'].write_text('uncertain');ns['CLEANUP_UNVERIFIED']=True
   output=io.StringIO()
   with contextlib.redirect_stdout(output):ns['logs_and_reports'](root/'editor')
   decoded=DECODER.decode(output.getvalue(),root/'decoded');self.assertEqual(len(decoded),3)
   values=[json.loads(pathlib.Path(row['path']).read_text()) for row in decoded]
   raw={v['file']:b''.join(base64.b64decode(c) for c in v['chunks']) for v in values if v.get('kind')=='editor-diagnostic-original-bytes'}
   self.assertEqual(raw,{'capture.json':original,'stderr.bin':binary})
   wrapped=next(v for v in values if v.get('kind')=='lossless-native-json-text-wrapper')
   self.assertEqual(EVIDENCE.restore_text(wrapped['document']),value)
   self.assertEqual(wrapped['original_raw_sha256'],hashlib.sha256(original).hexdigest())
   self.assertTrue(ns['CLEANUP_BLOCK'].exists());self.assertFalse(rows)
 def test_two_arm_same_basename_and_malformed_json_keep_exact_source_paths(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);ns,rows=self.functions(root)
   for mode in ('stock','on'):(root/'editor'/mode).mkdir(parents=True)
   (root/'editor/stock/capture.json').write_bytes(b'{invalid original')
   (root/'editor/on/capture.json').write_text('{"status":"failed"}')
   output=io.StringIO()
   with contextlib.redirect_stdout(output):ns['logs_and_reports'](root/'editor')
   decoded=DECODER.decode(output.getvalue(),root/'decoded');self.assertEqual(len(decoded),3)
   raw=[json.loads(pathlib.Path(row['path']).read_text()) for row in decoded]
   raw=[v for v in raw if v.get('kind')=='editor-diagnostic-original-bytes']
   self.assertEqual({v['source_relative_path'] for v in raw},{'editor/stock/capture.json','editor/on/capture.json'})
   self.assertEqual({v['file'] for v in raw},{'capture.json'})
   self.assertTrue(any(not ok for _,ok,_ in rows))
 def test_emit_exception_retained_without_escape(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);ns,rows=self.functions(root);path=root/'capture.json';path.write_text('{}')
   def fail(*args):raise OSError('transport failure')
   ns['emitter']=types.SimpleNamespace(emit=fail)
   self.assertFalse(ns['emit'](path));self.assertTrue(any(not ok for _,ok,_ in rows))
 def test_public_free_pinned_read_only_workflow(self):
  for text in ('runs-on: macos-15','contents: read','github.event.repository.private == false',"github.event.repository.visibility == 'public'",'cancel-in-progress: false','persist-credentials: false','ref: ${{ github.sha }}'):
   self.assertIn(text,WORKFLOW)
  for text in ('upload-artifact','actions/cache','contents: write','self-hosted','workflow_dispatch','continue-on-error'):
   self.assertNotIn(text,WORKFLOW)
 def test_audit_after_editor_witness_and_ordinary_red_not_a_dependency(self):
  self.assertLess(WORKFLOW.index('run-editor-diagnostic.py editor'),WORKFLOW.index('run-editor-diagnostic.py verify'))
  self.assertLess(WORKFLOW.index('run-editor-diagnostic.py verify'),WORKFLOW.index('run-packaging-audit.py run'))
  self.assertIn("if: always() && steps.runtime.outcome == 'success' && steps.editor_witness.outcome == 'success'",WORKFLOW)
  self.assertNotIn("steps.editor_capture.outcome == 'success'",WORKFLOW)
  self.assertEqual(WORKFLOW.count('if test -e retained-host/reports/editor-diagnostic-ci/launch-blocked.json; then'),2)
 def test_workflow_lease_blocks_both_audit_commands_but_not_editor_witness(self):
  blocks=[]
  lines=WORKFLOW.splitlines()
  for i,line in enumerate(lines):
   if line.strip()=='run: |':
    block=[]
    for follow in lines[i+1:]:
     if not follow.startswith('          '):break
     block.append(follow[10:])
    if any('run-packaging-audit.py' in x for x in block):blocks.append('\n'.join(block))
  self.assertEqual(len(blocks),2)
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);lease=root/'retained-host/reports/editor-diagnostic-ci/launch-blocked.json';lease.parent.mkdir(parents=True)
   for blocked in (False,True):
    if blocked:lease.write_text('unresolved')
    for body in blocks:
     # Replace only the intended Python call by a harmless shell sentinel.
     body=body[:body.rindex('python3 ')]+"printf reached"
     p=subprocess.run(['bash','-c',body],cwd=root,capture_output=True,text=True,check=False)
     self.assertEqual(p.returncode,1 if blocked else 0)
     self.assertEqual('reached' in p.stdout,not blocked)
 def test_unverified_timeout_cleanup_blocks_later_phases_and_resolution(self):
   with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
    root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
    class Process:
     pid=123
     def wait(self,timeout):raise subprocess.TimeoutExpired('native',timeout)
    def launch(*args,**kwargs):launches.append(args);return Process()
    def cleanup(p):raise RuntimeError('survivor still alive')
    ns.update(subprocess=types.SimpleNamespace(Popen=launch,TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT),terminate_group=cleanup)
    self.assertFalse(ns['command']('first',['native'],required=False));self.assertTrue(ns['CLEANUP_BLOCK'].is_file());self.assertEqual(len(launches),1)
    self.assertFalse(ns['command']('next',['native'],required=False));self.assertEqual(len(launches),1)
    with self.assertRaisesRegex(RuntimeError,'Collection lookup blocked'):ns['collection']('stock','a/b')
    fresh,_=self.functions(root);fresh.update(subprocess=ns['subprocess'],terminate_group=cleanup)
    self.assertFalse(fresh['command']('later phase',['native'],required=False));self.assertEqual(len(launches),1)
    fresh['PHASE']='verify';fresh['subprocess']=types.SimpleNamespace(Popen=lambda *a,**k:types.SimpleNamespace(wait=lambda timeout:0),TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT)
    self.assertTrue(fresh['command']('original witness',['python']))
    self.assertTrue(any('cleanup' in name and not ok for name,ok,detail in rows))
 def test_cleanup_diagnostic_write_failure_leaves_prelaunch_lease(self):
   with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
    root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
    class FlakyLease:
     def __init__(self):self.path=root/'launch-blocked.json';self.writes=0
     def exists(self):return self.path.exists()
     def write_text(self,text):
      self.writes+=1
      if self.writes>1:raise OSError('disk update failed')
      return self.path.write_text(text)
     def unlink(self,**kwargs):return self.path.unlink(**kwargs)
    class Process:
     pid=456
     def wait(self,timeout):raise subprocess.TimeoutExpired('native',timeout)
    def launch(*a,**k):launches.append(a);return Process()
    def cleanup(p):raise RuntimeError('unknown survivors')
    ns.update(CLEANUP_BLOCK=FlakyLease(),subprocess=types.SimpleNamespace(Popen=launch,TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT),terminate_group=cleanup)
    self.assertFalse(ns['command']('first',['native'],required=False));self.assertTrue(ns['CLEANUP_UNVERIFIED']);self.assertTrue(ns['CLEANUP_BLOCK'].exists())
    self.assertFalse(ns['command']('second',['native'],required=False));self.assertEqual(len(launches),1)
    fresh,_=self.functions(root);fresh.update(subprocess=ns['subprocess'],terminate_group=cleanup)
    self.assertFalse(fresh['command']('later phase',['native'],required=False));self.assertEqual(len(launches),1)
    self.assertTrue(any('persistence_error' in detail for name,ok,detail in rows))
 def test_failed_initial_lease_write_starts_no_process(self):
   with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
    root=pathlib.Path(folder);ns,rows=self.functions(root);launches=[]
    class RefusingLease:
     def exists(self):return False
     def write_text(self,text):raise OSError('cannot persist launch lease')
     def unlink(self,**kwargs):pass
    ns.update(CLEANUP_BLOCK=RefusingLease(),subprocess=types.SimpleNamespace(Popen=lambda *a,**k:launches.append(a),TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT))
    self.assertFalse(ns['command']('first',['native'],required=False));self.assertFalse(launches)
 def test_optimized_launch_refused_before_environment(self):
   p=subprocess.run([sys.executable,'-O',str(ROOT/'run-editor-diagnostic.py'),'prepare'],capture_output=True,text=True,timeout=10);self.assertNotEqual(p.returncode,0);self.assertIn('Optimized Python execution refused',p.stderr)
if __name__=='__main__':unittest.main()
