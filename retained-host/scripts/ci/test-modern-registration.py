import ast,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
SOURCE=(ROOT/'run-stock-tools.py').read_text();PROBE=(ROOT/'verify-modern-tool-registration.rkt').read_text()
class RegistrationTests(unittest.TestCase):
 def test_source_parses(self):ast.parse(SOURCE)
 def test_diagnostic_driver_typed_marker_contract(self):
  node=next(n for n in ast.parse(SOURCE).body if isinstance(n,ast.FunctionDef) and n.name=='coordinator_result_valid');ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<validator>','exec'),ns)
  good='OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained'
  bad='OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE\nOPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong'
  v=ns['coordinator_result_valid'];self.assertTrue(v(0,good,False,'failure-diagnostics'));self.assertTrue(v(1,bad,True,'failure-diagnostics'))
  for code,text in ((0,bad),(124,bad),(-9,bad),(1,bad+good),(1,bad+bad),(1,bad.replace('actual=actual','actual=other'))):self.assertFalse(v(code,text,True,'failure-diagnostics'))
 def test_no_raw_addon_relocation(self):
  self.assertNotIn('shutil.copytree(ADDON',SOURCE)
  self.assertIn("fresh_modern_addon('compile-modern',e)",SOURCE)
  self.assertIn('if modern:fresh_modern_addon(label,e)',SOURCE)
 def test_official_isolated_no_network_registration(self):
  body=SOURCE.split('def fresh_modern_addon',1)[1].split('def native_case',1)[0]
  for token in ("'--scope','user'","'--deps','fail'","'--copy'","'--link'","'--no-setup'","'--avoid-main'","'--no-docs'","'--no-launcher'","'--no-foreign-libs'","'--no-install'","'--no-post-install'"):
   self.assertIn(token,body)
  self.assertNotIn("'-U'",body);self.assertNotIn("'--auto'",body)
  self.assertIn('not addon.exists()',body);self.assertIn('source.is_relative_to(ADDON.resolve())',body)
  self.assertIn("e['PLTCOMPILEDROOTS']",body)
 def test_actual_discovery_and_collection_hashes_required(self):
  for token in ('find-relevant-directory-records','get-info/full','directory-record-path','drracket-tools','drracket-tool-names','collection-file-path','pkg-directory','use-user-specific-search-paths','sha256-bytes',"'tool/tool.rkt","'tool/info.rkt"):
   self.assertIn(token,PROBE)
  self.assertNotIn('(dynamic-require',PROBE)
  self.assertNotIn('(preferences:set',PROBE)
  self.assertIn('(when (gui-available?)',PROBE)
  self.assertIn("(equal? (path->directory-path addon) (path->directory-path (canonical (find-system-path 'addon-dir))))",PROBE)
 def test_prepared_patched_sources_are_pinned(self):
  for token in ('patched_sha256','painter_sha256','00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d'):
   self.assertIn(token,SOURCE);self.assertIn(token,PROBE)
 def test_registration_is_outside_original_gui_bound_and_failures_are_independent(self):
  case=SOURCE.split('def native_case',1)[1]
  self.assertLess(case.index('fresh_modern_addon'),case.index('deadline=time.monotonic()+60'))
  self.assertIn('if time.monotonic()>deadline:result=124',SOURCE)
  self.assertIn("registration or supervisor',False,str(error)",SOURCE)
if __name__=='__main__':unittest.main()
