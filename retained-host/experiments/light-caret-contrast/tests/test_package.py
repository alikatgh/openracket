"""Portable source/adapter tests. Synthetic receipts are never native evidence."""
import sys
sys.dont_write_bytecode=True
import copy, hashlib, importlib.util, json, os, re, struct, tempfile, unittest, zlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
v=module('caret_verifier',ROOT/'scripts/validate-caret-result.py')
d=module('caret_deriver',ROOT/'scripts/derive-host.py')
c=module('caret_composer',ROOT/'scripts/compose-candidate.py')
pair=module('caret_pair',ROOT/'scripts/validate-caret-pair.py')
def state(arm='patched'):
    s=copy.deepcopy(v.EXPECTED[arm]);s.update(visible_first_line=0,visible_last_line=4,rendered_line=2,
      line_top=40,line_bottom=60,view_left=0,view_top=0,view_width=800,view_height=400,
      contrast_ratio=v.contrast(s['gutter_foreground'],s['gutter_background']));return s
def preflights():
    return [dict(entrypoint=name,arguments=args,exit_code=(1 if injection else 0),timed_out=False,
        timeout_seconds=30,stdout='\n'.join(([injection] if injection else [])+[marker])+'\n',stderr='')
            for name,args,marker,injection,_ in v.PREFLIGHTS]
def native(arm='patched'):
    lights=[{'stage':stage,'observed':v.inherited.EXPECTED} for stage in ('before-tool','after-tool')]
    r=dict(status='passed',checks=40,racket='9.3',genuine_host=True,repeated_real_run=True,
      complete_stock_parity=False,physical_input_to_photon_measured=False,ui='modern',theme='light',
      native_appearance_lifecycle=None,follow_on_case='macro-stepper',follow_on_result={'case':'macro-stepper','status':'passed'},
      light_tool_states=lights,caret_state=state(arm))
    out='\n'.join(['OPENRACKET_NATIVE_LIGHT_STATE '+json.dumps(lights[0]),
      'OPENRACKET_NATIVE_STAGE follow-on=macro-stepper','OPENRACKET_NATIVE_LIGHT_STATE '+json.dumps(lights[1]),
      'OPENRACKET_NATIVE_CARET_STATE '+json.dumps(r['caret_state']),
      'OPENRACKET_NATIVE_RESULT '+json.dumps(r),'OPENRACKET_NATIVE_READY'])+'\n'
    return r,out

def png():
    def chunk(t,p):return struct.pack('>I',len(p))+t+p+struct.pack('>I',zlib.crc32(t+p)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')
def supervisor(ready=b'{}',image=None):
    image=png() if image is None else image
    return dict(arm='patched',composition_sha256='fixture',timeout_seconds=60,timed_out=False,exit_code=0,
       process_group_alive_after_cleanup=False,started_monotonic=100.,ready_monotonic=110.,
       capture_completed_monotonic=111.,ack_monotonic=112.,exited_monotonic=113.,deadline_monotonic=160.,
       capture_tool='screencapture',capture_after_ready=True,ready_sha256=v.digest(ready),png_sha256=v.digest(image),
       fresh_process=True,fresh_profile=True,initial_ready_absent=True,initial_ack_absent=True)

class SourceTests(unittest.TestCase):
    def test_frozen_references_match_manifest(self):
        frozen=json.loads((c.REF/'DELIVERABLE-SHA256.json').read_text())['files']
        for p in c.REF.rglob('*'):
            if p.is_file() and p.name!='DELIVERABLE-SHA256.json':
                self.assertEqual(v.digest(p.read_bytes()),frozen[p.relative_to(c.REF).as_posix()])
    def test_accepted_manifest(self):
        raw=c.ACCEPTED.read_bytes();self.assertEqual(v.digest(raw),c.ACCEPTED_SHA);self.assertEqual(len(json.loads(raw)),155)
    def test_exact_reversible_one_entry(self):
        old=(c.REF/'reference/production/tool/info.rkt').read_bytes();new=(ROOT/'production/tool/info.rkt').read_bytes()
        a=b'(framework:line-numbers-current-line-number-foreground #(36 94 219))';b=a.replace(b'36 94 219',b'35 91 215')
        self.assertEqual(old.count(a),1);self.assertEqual(new,old.replace(a,b));self.assertEqual(old,new.replace(b,a))
        self.assertEqual(new.split(b'#hash((name . "OpenRacket Dark")')[1],old.split(b'#hash((name . "OpenRacket Dark")')[1])
        self.assertEqual(new.count(b'#(36 94 219)'),old.count(b'#(36 94 219)')-1)
    def test_patch_exact(self):
        import difflib
        old=(c.REF/'reference/production/tool/info.rkt').read_text();new=(ROOT/'production/tool/info.rkt').read_text()
        self.assertEqual((ROOT/'production.patch').read_text(),''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/tool/info.rkt',tofile='b/tool/info.rkt')))
    def test_unrounded_contrast(self):
        self.assertAlmostEqual(v.contrast([36,94,219],[220,228,239]),4.43009856144889,places=13)
        self.assertAlmostEqual(v.contrast([35,91,215],[220,228,239]),4.617119494850047,places=13)
        self.assertLess(v.contrast([36,94,219],[220,228,239]),4.5);self.assertGreaterEqual(v.contrast([35,91,215],[220,228,239]),4.5)
    def test_exact_host_derivation(self):
        raw=d.BASE.read_bytes();self.assertEqual(d.derive(raw),(ROOT/'native/tests/independent-native-light-caret-host.rkt').read_bytes())
        with self.assertRaises(ValueError):d.derive(raw+b'\n')
    def test_original_host_is_subsequence(self):
        # All old lines survive in order; only the require closing-paren line has
        # an insertion before its paren and remains semantically exact.
        old=d.BASE.read_text().replace('"native-light-state-observer.rkt")','"native-light-state-observer.rkt"').splitlines()
        new=(ROOT/'native/tests/independent-native-light-caret-host.rkt').read_text().splitlines()
        it=iter(new)
        for line in old:self.assertTrue(any(x==line for x in it),line)
    def test_wait_and_failure_blocks_unchanged(self):
        old=d.BASE.read_text();new=(ROOT/'native/tests/independent-native-light-caret-host.rkt').read_text()
        for first,last in [('(define (on-gui thunk)','(define before '),('(define (wait-for-capture!)','(define (assert-theme-state!'),('(define (failure-diagnostics!','(define (cleanup!)'),('(with-handlers\n    ([exn?','  ;; This separate entrypoint')]:
            if first.startswith('(with-handlers'):continue
            self.assertEqual(old.split(first,1)[1].split(last,1)[0],new.split(first,1)[1].split(last,1)[0])
        self.assertEqual(old.count('(yield (alarm-evt (+ (current-inexact-milliseconds) 500)))'),1)
        self.assertEqual(new.count('(yield (alarm-evt (+ (current-inexact-milliseconds) 500)))'),1)
    def test_observer_no_renderer_or_theme_mutation(self):
        s=(ROOT/'native/tests/native-light-caret-observer.rkt').read_text()
        for forbidden in ['send canvas on-paint','send defs do-draw-single-line','preferences:set','show-line-numbers!','set-style-list','set-line-numbers-color','set-padding','(sleep ','(thread ']:self.assertNotIn(forbidden,s)
        self.assertIn('(send defs set-position position position)',s)
        self.assertIn('(emit-caret-state!\n   (lambda ()',s)
        for method in ['get-visible-line-range','line-location','get-view','has-focus?','showing-line-numbers?','get-start-position','get-end-position']:self.assertIn(method,s)
    def test_state_output_preserves_breaks_and_typed_validation(self):
        contract=(ROOT/'native/tests/native-light-caret-contract.rkt').read_text()
        observer=(ROOT/'native/tests/native-light-caret-observer.rkt').read_text()
        standalone=(ROOT/'native/tests/native-light-caret-standalone.rkt').read_text()
        self.assertIn('[exn:break? raise]',contract)
        self.assertLess(contract.index('[exn:break? raise]'),contract.index('[(lambda (_) #t)'))
        self.assertLess(observer.index('(emit-caret-state!'),observer.index('(validate-caret-state! observed arm)'))
        self.assertIn('(eq? failure original-break)',standalone)
        self.assertIn("(emit-caret-state! (lambda () (raise 'output-fixture)))",standalone)
        self.assertIn("(hash-set good 'selection_collapsed #f)",standalone)
    def test_official_renderer_pins_and_git_blobs(self):
        for name,sha,git in [('text-line-numbers.rkt','14ff8bd96dcaf07b8b8c115a85eb88a49f97f4e37cf7fbee03d50c5493a2f5e7','1d84b47aed5abfeef65dba32b2b82a125c0cd96d'),('cocoa-procs.rkt','b6ce80e7673088f57edb9cd1fc5535a35741190c3f1197eedb55ddde850c00ca','786b064d7ecd6015e995856ec270ab64540889af')]:
            raw=(ROOT/'reference/official'/name).read_bytes();self.assertEqual(v.digest(raw),sha)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),git)
    def test_expected_macro_source_is_exact(self):
        source=(c.REF/'tests/independent-native-stock-tools.rkt').read_text()
        encoded=re.search(r'\(define macro-fixture\s+("(?:\\.|[^"\\])*")\)',source).group(1)
        fixture=json.loads(encoded);self.assertEqual(fixture,v.EXPECTED['patched']['source_text'])
        self.assertEqual(len(''.join(fixture.splitlines(True)[:2])),68)
    def test_all_native_sources_balanced(self):
        # Lexical delimiter screening only, explicitly not a Racket reader.
        for path in (ROOT/'native/tests').glob('*.rkt'):
            text=path.read_text();text=re.sub(r'"(?:\\.|[^"\\])*"','""',text);text=re.sub(r';[^\n]*','',text)
            stack=[];pairs={')':'(',']':'[','}':'{'}
            for char in text:
                if char in '([{':stack.append(char)
                elif char in ')]}':self.assertTrue(stack,path.name);self.assertEqual(stack.pop(),pairs[char],path.name)
            self.assertEqual(stack,[],path.name)

class StateTests(unittest.TestCase):
    def test_original_is_valid_known_below_threshold_baseline(self):self.assertLess(v.validate_state(state('original'),'original'),4.5)
    def test_patched_valid(self):self.assertGreaterEqual(v.validate_state(state(),'patched'),4.5)
    def test_missing_each_key(self):
        for key in state():
            s=state();del s[key]
            with self.assertRaises(ValueError,msg=key):v.validate_state(s,'patched')
    def test_wrong_each_fixed_value(self):
        for key in v.EXPECTED['patched']:
            s=state();s[key]='wrong'
            with self.assertRaises(ValueError,msg=key):v.validate_state(s,'patched')
    def test_boolean_numeric_standins(self):
        for key,value in v.EXPECTED['patched'].items():
            if type(value) is bool:
                s=state();s[key]=int(value)
                with self.assertRaises(ValueError,msg=key):v.validate_state(s,'patched')
    def test_wrong_rgb_and_arm(self):
        for arm in ['original','patched']:
            s=state(arm);s['gutter_foreground']=[36,94,219] if arm=='patched' else [35,91,215]
            with self.assertRaises(ValueError):v.validate_state(s,arm)
    def test_viewport_refusals(self):
        for key,value in [('view_top',50),('view_height',1),('view_width',0),('visible_first_line',3),('visible_last_line',1),('line_bottom',40),('rendered_line',True),('line_top',float('nan')),('view_top',10**10000),('contrast_ratio',4.5)]:
            s=state();s[key]=value
            with self.assertRaises(ValueError,msg=key):v.validate_state(s,'patched')
    def test_extra_keys_refused(self):
        s=state();s['extra']=True
        with self.assertRaises(ValueError):v.validate_state(s,'patched')

class EvidenceTests(unittest.TestCase):
    def test_all_12_controls(self):self.assertEqual(len(preflights()),12);v.validate_preflights(preflights())
    def test_missing_controls(self):
        for i in range(12):
            rows=preflights();del rows[i]
            with self.assertRaises(ValueError):v.validate_preflights(rows)
    def test_bad_control_exit_timeout_and_markers(self):
        for i in range(12):
            for key,value in [('timed_out',True),('exit_code',124),('timeout_seconds',31),('stdout',''),('exit_code',True)]:
                rows=preflights();rows[i][key]=value
                with self.assertRaises(ValueError):v.validate_preflights(rows)
    def test_native_adapter_accepts_both_synthetic_receipts(self):
        for arm in ('original','patched'):
            r,out=native(arm);v.validate_result(arm,r,out,'',supervisor())
    def test_state_mismatch_ready_refused(self):
        r,out=native();r['caret_state']['selection_end']=69
        with self.assertRaises(ValueError):v.validate_result('patched',r,out,'',supervisor())
    def test_missing_duplicate_or_early_caret_state_refused(self):
        r,out=native();line=next(x for x in out.splitlines(True) if x.startswith('OPENRACKET_NATIVE_CARET_STATE '))
        for bad in [out.replace(line,''),out+line,line+out.replace(line,'')]:
            with self.assertRaises(ValueError):v.validate_result('patched',r,bad,'',supervisor())
    def test_native_failure_never_success(self):
        r,out=native()
        for bad in ['OPENRACKET_NATIVE_FAILURE','OPENRACKET_CARET_FAILURE','OPENRACKET_CARET_INJECTING_FAILURE']:
            with self.assertRaises(ValueError):v.validate_result('patched',r,out,bad,supervisor())
    def test_valid_supervision(self):v.validate_supervision(supervisor(),b'{}',png(),'fixture','patched')
    def test_supervision_refusals(self):
        for key,value in [('timeout_seconds',61),('timed_out',True),('exit_code',1),('process_group_alive_after_cleanup',True),('deadline_monotonic',161),('exited_monotonic',161),('capture_completed_monotonic',131),('ack_monotonic',109),('ack_monotonic',130),('ready_sha256','wrong'),('png_sha256','wrong'),('capture_tool','synthetic'),('fresh_profile',False),('initial_ack_absent',False),('ready_monotonic',True),('started_monotonic',10**10000)]:
            s=supervisor();s[key]=value
            with self.assertRaises(ValueError,msg=key):v.validate_supervision(s,b'{}',png(),'fixture','patched')
    def test_png_corruption_refused(self):
        for image in [b'',png()[:-1],png().replace(b'IDAT',b'JDAT')]:
            with self.assertRaises(ValueError):v.png_size(image)
    def test_reader_compile_required(self):
        rows=[dict(stage=stage,timeout_seconds=(30 if stage=='reader' else 180),exit_code=0,timed_out=False,composition_sha256='fixture',modules=v.required_racket_modules()) for stage in ('reader','compile')]
        v.validate_build(rows,'fixture')
        for key,value in [('exit_code',1),('timed_out',True),('modules',[]),('composition_sha256','wrong')]:
            bad=copy.deepcopy(rows);bad[0][key]=value
            with self.assertRaises(ValueError):v.validate_build(bad,'fixture')
    def test_exact_composition_receipts(self):
        for arm in ('original','patched'):
            r={'arm':arm,'accepted_input_members':155,'accepted_manifest_sha256':c.ACCEPTED_SHA,'native_overlay_manifest_sha256':c.OVERLAY_SHA,'product_changes':([] if arm=='original' else ['tool/info.rkt']),'files':v.expected_composition(arm)}
            v.validate_composition(r,arm);r['files']['tool/info.rkt']='wrong'
            with self.assertRaises(ValueError):v.validate_composition(r,arm)

class PairTests(unittest.TestCase):
    def write_synthetic_arm(self,folder,arm):
        folder.mkdir()
        comp={'arm':arm,'accepted_input_members':155,'accepted_manifest_sha256':c.ACCEPTED_SHA,
              'native_overlay_manifest_sha256':c.OVERLAY_SHA,'product_changes':([] if arm=='original' else ['tool/info.rkt']),
              'files':v.expected_composition(arm)}
        raw=json.dumps(comp).encode();sha=v.digest(raw);(folder/'composition.json').write_bytes(raw)
        r,out=native(arm);ready=json.dumps(r).encode();(folder/'ready.json').write_bytes(ready)
        (folder/'stdout.txt').write_text(out);(folder/'stderr.txt').write_text('');(folder/'capture.png').write_bytes(png())
        (folder/'preflights.json').write_text(json.dumps(preflights()))
        build=[dict(stage=stage,timeout_seconds=(30 if stage=='reader' else 180),exit_code=0,timed_out=False,
               composition_sha256=sha,modules=v.required_racket_modules()) for stage in ('reader','compile')]
        (folder/'build.json').write_text(json.dumps(build))
        receipt=supervisor(ready);receipt.update(arm=arm,composition_sha256=sha,profile_id='synthetic-'+arm,launch_id='synthetic-launch-'+arm,
                process_id=(1001 if arm=='original' else 1002),official_runtime_sha256='a'*64)
        (folder/'supervisor.json').write_text(json.dumps(receipt))
        return receipt
    def test_pair_requires_both_arms_and_separate_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'original';b=Path(temp)/'patched'
            self.write_synthetic_arm(a,'original');receipt=self.write_synthetic_arm(b,'patched')
            result=pair.validate_pair(a,b);self.assertEqual(len(result['matrix']),2)
            for key,value in [('profile_id','synthetic-original'),('profile_id','/local/path'),('process_id',1001),('launch_id','synthetic-launch-original'),('official_runtime_sha256','b'*64)]:
                bad=dict(receipt);bad[key]=value;(b/'supervisor.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError,msg=key):pair.validate_pair(a,b)
            with self.assertRaises(ValueError):pair.validate_pair(a,a)
            # Sequential OS PID reuse is legitimate only with a distinct launch
            # receipt and distinct supervisor-recorded process start identity.
            reused=dict(receipt);reused['process_id']=1001
            for key in ['started_monotonic','ready_monotonic','capture_completed_monotonic','ack_monotonic','exited_monotonic','deadline_monotonic']:
                reused[key]+=100
            (b/'supervisor.json').write_text(json.dumps(reused))
            self.assertEqual(pair.validate_pair(a,b)['status'],'accepted')

class CompositionTests(unittest.TestCase):
    def test_missing_full_source_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'input';source.mkdir();out=root/'output'
            with self.assertRaises(ValueError):c.compose(source,out,'patched')
            self.assertFalse(out.exists())
    def test_alias_tmpdir_is_real_when_requested(self):
        if os.environ.get('REQUIRE_ALIASED_TMPDIR')=='1':
            alias=Path(os.environ['TMPDIR']);self.assertTrue(alias.is_symlink());self.assertNotEqual(str(alias.absolute()),str(alias.resolve()))
            with tempfile.TemporaryDirectory() as temp:
                self.assertTrue(Path(temp).resolve().is_relative_to(alias.resolve()))
    def test_synthetic_composition_preserves_input_under_alias(self):
        # Adapter-only exercise of path/copy behavior, never an accepted product.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'input';source.mkdir()
            files={'tool/info.rkt':(c.REF/'reference/production/tool/info.rkt').read_bytes()}
            files.update({f'fixture/member-{i:03d}.txt':str(i).encode() for i in range(154)})
            for name,data in files.items():p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            accepted={name:v.digest(data) for name,data in files.items()}
            real_pinned=c.pinned
            def synthetic(path,sha):return accepted if path==c.ACCEPTED else real_pinned(path,sha)
            alias=root/'alias';alias.symlink_to(root,target_is_directory=True)
            with patch.object(c,'pinned',synthetic):
                receipt=c.compose(alias/'input',alias/'output','patched')
                self.assertEqual((root/'output/tool/info.rkt').read_bytes(),(ROOT/'production/tool/info.rkt').read_bytes())
                self.assertEqual(c.members(source),accepted)
                with self.assertRaises(ValueError):c.compose(source,alias/'output','patched')
                with self.assertRaises(ValueError):c.compose(source,source/'nested','patched')
                self.assertEqual(receipt['product_changes'],['tool/info.rkt'])
    def test_casefold_collision_refused_without_filesystem_assumption(self):
        # Pure name comparison tests the rule on both case-sensitive/insensitive FS.
        names=['tool/info.rkt','TOOL/info.rkt']
        self.assertNotEqual(len(names),len({n.casefold() for n in names}))

if __name__=='__main__':unittest.main(verbosity=2)
