#!/usr/bin/env python3
"""Portable source and synthetic receipt tests. Does not execute Racket or GUI."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
def module(path):
    spec=importlib.util.spec_from_file_location(path.stem,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
prepare=module(ROOT/'scripts/prepare-light-tool-host.py')
verify=module(ROOT/'scripts/validate-light-tool-result.py')
stock=module(ROOT/'tests/stock-tool-source-test.py')

def evidence(arm='modern-light',case='debugger'):
    report={'status':'passed','racket':'9.3','ui':'stock' if arm=='stock' else 'modern','theme':'light',
            'genuine_host':True,'repeated_real_run':True,'complete_stock_parity':False,
            'physical_input_to_photon_measured':False,'native_appearance_lifecycle':None,
            'follow_on_case':case,'follow_on_result':{'case':case,'status':'passed'}}
    lines=[]
    if arm=='modern-light':
        states=[{'stage':stage,'observed':copy.deepcopy(verify.EXPECTED)} for stage in ('before-tool','after-tool')]
        report['light_tool_states']=states
        lines.append('OPENRACKET_NATIVE_LIGHT_STATE '+json.dumps(states[0]))
    lines.append('OPENRACKET_NATIVE_STAGE follow-on='+case)
    if arm=='modern-light':lines.append('OPENRACKET_NATIVE_LIGHT_STATE '+json.dumps(states[1]))
    lines.extend(['OPENRACKET_NATIVE_RESULT '+json.dumps(report),'OPENRACKET_NATIVE_READY'])
    return report,'\n'.join(lines)+'\n'

def preflights():
    return [{'entrypoint':name,'arguments':args,'exit_code':1 if injection else 0,
             'timed_out':False,'timeout_seconds':30,'stdout':((''+injection+'\n') if injection else '')+marker+'\n','stderr':''}
            for name,args,marker,injection,forbidden in verify.PREFLIGHTS]

class SourceTests(unittest.TestCase):
    def test_all_accepted_source_bytes_unchanged(self):
        for path,digest in json.loads((ROOT/'BASELINE-1125-SHA256.json').read_text())['files'].items():
            with self.subTest(path=path):self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)
    def test_light_host_is_exact_pinned_derivation(self):
        raw=prepare.BASE_HOST.read_bytes()
        for path,content in prepare.outputs(raw).items():self.assertEqual(path.read_bytes(),content.encode())
        for bad in (raw+b'\n',raw.replace(b'\n',b'\r\n')):
            with self.assertRaises(ValueError):prepare.derive(bad)
    def test_racket_lexical_structure(self):
        for path in (ROOT/'tests').glob('*.rkt'):
            with self.subTest(path=path.name):stock.delimiter_check(path.read_text())
    def test_workflow_body_and_deadlines_byte_identical(self):
        base=prepare.BASE_HOST.read_text();light=(ROOT/'tests/independent-native-light-tools-host.rkt').read_text()
        for start,end in [('(define (wait-for ', '(define before'),('(define (wait-for-capture!)','(define (assert-theme-state!'),('  (when follow-on-case\n    (unless', '  ;; A low-priority')]:
            a=base.split(start,1)[1].split(end,1)[0]
            b=light.split(start,1)[1].split(end,1)[0]
            if start.startswith('  (when follow-on-case'):
                b=b.split('  (set! light-tool-states',1)[0]
                a=a.rstrip();b=b.rstrip()
            self.assertEqual(a,b)
        self.assertEqual(base.count('current-inexact-monotonic-milliseconds'),light.count('current-inexact-monotonic-milliseconds'))
        self.assertEqual(base.count('(yield '),light.count('(yield '))
        self.assertEqual(base.count('(wait-for '),light.count('(wait-for '))
        for marker in ('OPENRACKET_NATIVE_READY','OPENRACKET_NATIVE_FAILURE_READY','OPENRACKET_CAPTURE_DONE'):
            self.assertEqual(base.count(marker),light.count(marker))
    def test_hook_brackets_tools_on_actual_handler(self):
        host=(ROOT/'tests/independent-native-light-tools-host.rkt').read_text()
        self.assertLess(host.index('(observe-light-state! "before-tool")'),host.index('  (when follow-on-case\n    (unless'))
        self.assertLess(host.index('  (when follow-on-case\n    (unless'),host.index('(observe-light-state! "after-tool")'))
        for stage in ('before-tool','after-tool'):
            self.assertIn('(on-gui (lambda () (observe-light-state! "'+stage+'")))',host)
        self.assertIn('(equal? (getenv "OPENRACKET_THEME") "light")',host)
        self.assertIn('(not (getenv "OPENRACKET_NATIVE_APPEARANCE_CHECK"))',host)
    def test_observer_is_read_only_and_uses_actual_getters(self):
        source=(ROOT/'tests/native-light-state-observer.rkt').read_text()
        for banned in ("'preferences:set","'set-modern-host-theme!","'set-modern-chrome-blended!",'native-appearance-set!','native-appearance-restore!','send frame','(yield ', '(sleep ', 'setAppearance:'):
            self.assertNotIn(banned,source)
        for phrase in ("'color-prefs:lookup-in-color-scheme","'framework:basic-canvas-background","'framework:default-text-color","'get-modern-host-theme","'get-modern-chrome-blended?","'modern-ui?","'native-appearance-adapter-inspect",'((inspect adapter))','[painter-parameter painter]','(validate-light-state! observed)'):
            self.assertIn(phrase,source)
        self.assertLess(source.index('OPENRACKET_NATIVE_LIGHT_STATE'),source.index('(validate-light-state! observed)'))
    def test_exact_palette_matches_read_only_production_source(self):
        info=(ROOT/'reference/production/tool/info.rkt').read_text().split('(name . "OpenRacket Dark")')[0]
        for key,target in [('framework:basic-canvas-background','palette_background'),('framework:default-text-color','palette_foreground')]:
            rgb=[int(x) for x in re.search(re.escape(key)+r' #\((\d+ \d+ \d+)\)',info)[1].split()]
            self.assertEqual(verify.EXPECTED[target],rgb)
        painter=(ROOT/'reference/production/overlay/mrlib/private/openracket-paint.rkt').read_text().split("(hash 'light (hash ")[1].split("'dark (hash")[0]
        palette={k:[int(v[i:i+2],16) for i in (0,2,4)] for k,v in re.findall(r"'([\w-]+) \"#([A-F0-9]{6})\"",painter)}
        self.assertEqual(verify.EXPECTED['painter_palette'],palette)
        button=(ROOT/'reference/production/overlay/mrlib/switchable-button.rkt').read_text()
        self.assertIn('(get-modern-host-theme))])',button)
    def test_cocoa_inspection_keys_and_aqua_are_source_supported(self):
        source=(ROOT/'reference/production/tool/native-appearance-cocoa.rkt').read_text()
        for key in verify.EXPECTED['native']:self.assertIn("'"+key,source)
        self.assertIn('"NSAppearanceNameAqua"',source)
        self.assertIn('(tell app effectiveAppearance)',source)
        provenance=json.loads((ROOT/'reports/production-source-evidence.json').read_text())
        manifest=provenance['current_accepted_manifest']
        raw=(ROOT/manifest['portable_copy']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['sha256'])
        accepted=json.loads(raw)
        pins=provenance['files']
        for name,item in pins.items():self.assertEqual(item['sha256'],accepted[name])
        for path,item in pins.items():self.assertEqual(hashlib.sha256((ROOT/'reference/production'/path).read_bytes()).hexdigest(),item['sha256'])
    def test_new_headless_refusals_are_fail_closed(self):
        contract=(ROOT/'tests/native-light-state-contract.rkt').read_text()
        source=(ROOT/'tests/native-light-state-standalone.rkt').read_text()
        self.assertNotIn('racket/gui',contract+source)
        self.assertIn('(parameterize ([current-check-handler raise])',contract)
        self.assertIn('(hash-keys observed)',contract)
        self.assertIn('(canonical (hash-ref observed key))',contract)
        self.assertIn('(hash-remove expected-light-state key)',source)
        self.assertIn('(raise failure)',source)
        self.assertIn('(report-failure!',source)
        self.assertIn('(validate-light-state! ordinary)',source)
        self.assertIn('(validate-light-state! json-roundtrip)',source)
        self.assertIn("(hash-equal? (hash-ref ordinary 'native))",source)
        self.assertIn('(for/hasheq',contract)
        self.assertIn('(pretty-info-value actual) "dark"',source)
        self.assertIn('(pretty-info-value expected) "light"',source)
        self.assertEqual(verify.EXPECTED,json.loads((ROOT/'tests/native-light-state-expected.json').read_text()))
    def test_six_synthetic_success_receipts(self):
        for arm in ('stock','modern-light'):
            for case in verify.CASES:
                report,out=evidence(arm,case)
                self.assertTrue(verify.validate_result(arm,case,report,out,'',0))
    def test_wrong_or_missing_light_state_refused(self):
        report,out=evidence()
        for key in verify.EXPECTED:
            for replacement in (None,'wrong'):
                bad=copy.deepcopy(report)
                for state in bad['light_tool_states']:
                    if replacement is None:state['observed'].pop(key)
                    else:state['observed'][key]=replacement
                with self.subTest(key=key,replacement=replacement),self.assertRaises(ValueError):verify.validate_result('modern-light','debugger',bad,out,'',0)
        self.assertFalse(verify.exact(False,0));self.assertFalse(verify.exact(True,1))
    def test_bad_native_receipts_refused(self):
        report,out=evidence()
        for arm,case,bad,stdout,stderr,code,timeout in [
            ('modern-light','debugger',report,out,'',1,False),
            ('modern-light','debugger',report,out,'',0,True),
            ('modern-light','debugger',report,out,'',False,False),
            ('stock','debugger',report,out,'',0,False),
            ('modern-light','macro-stepper',report,out,'',0,False),
            ('modern-light','debugger',report,out+'OPENRACKET_NATIVE_READY\n','',0,False),
            ('modern-light','debugger',report,out,'OPENRACKET_NATIVE_FAILURE bad',0,False),
            ('modern-light','debugger',report,'OPENRACKET_NATIVE_READY\n','',0,False),
            ('modern-light','debugger',report,out.replace('OPENRACKET_NATIVE_STAGE follow-on=debugger','no workflow'),'',0,False),
        ]:
            with self.assertRaises(ValueError):verify.validate_result(arm,case,bad,stdout,stderr,code,timeout)
        for key,value in [('status','failed'),('racket','9.2'),('genuine_host',False),('theme','dark'),('follow_on_result',{'case':'debugger','status':'failed'}),('light_tool_states',report['light_tool_states'][:1])]:
            bad=copy.deepcopy(report);bad[key]=value
            with self.assertRaises(ValueError):verify.validate_result('modern-light','debugger',bad,out,'',0)
    def test_preflights_and_injected_failures_all_mandatory(self):
        good=preflights();self.assertTrue(verify.validate_preflights(good))
        for i in range(len(good)):
            with self.assertRaises(ValueError):verify.validate_preflights(good[:i]+good[i+1:])
            for key,value in [('exit_code',0 if good[i]['exit_code'] else 1),('timed_out',True),('timeout_seconds',31),('stdout',''),('stderr',None)]:
                bad=copy.deepcopy(good);bad[i][key]=value
                with self.subTest(index=i,key=key),self.assertRaises(ValueError):verify.validate_preflights(bad)
        for i,(_,_,_,injection,forbidden) in enumerate(verify.PREFLIGHTS):
            if injection:
                for code in (-15,-9,124,125,126,127,128,129,137,143,255):
                    bad=copy.deepcopy(good);bad[i]['exit_code']=code
                    with self.subTest(index=i,exit=code),self.assertRaises(ValueError):verify.validate_preflights(bad)
                bad=copy.deepcopy(good);bad[i]['stdout']+=forbidden+'\n'
                with self.assertRaises(ValueError):verify.validate_preflights(bad)
        with self.assertRaises(ValueError):verify.validate_preflights(good[:-1]+[good[0]])

if __name__=='__main__':unittest.main(verbosity=2)
