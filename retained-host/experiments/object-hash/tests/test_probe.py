import copy,hashlib,importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from generate import *
import generate_host as gh
import generate_native_forms as gn
import overlay
import compare_observation as co


def balanced(data):
    """Lexical bracket smoke check, not a Racket parser/compiler."""
    s=data.decode();stack=[];i=0
    pairs={')':'(',']':'[','}':'{'}
    while i<len(s):
        if s[i]==';':
            j=s.find('\n',i);i=len(s) if j<0 else j+1;continue
        if s.startswith('#\\',i):
            i+=2
            if i<len(s):i+=1
            while i<len(s) and not s[i].isspace() and s[i] not in '()[]{}':i+=1
            continue
        if s[i]=='"':
            i+=1
            while i<len(s):
                if s[i]=='\\':i+=2;continue
                if s[i]=='"':i+=1;break
                i+=1
            else:raise ValueError('unterminated string')
            continue
        if s[i] in '([{':stack.append((s[i],i))
        elif s[i] in ')]}':
            if not stack or stack[-1][0]!=pairs[s[i]]:raise ValueError(f'bracket mismatch at line {s.count(chr(10),0,i)+1}')
            stack.pop()
        i+=1
    if stack:raise ValueError(f'unclosed bracket {stack[-1]}')

class TransformTests(unittest.TestCase):
    def setUp(self):self.original=(ROOT/'vendor/class-internal.rkt').read_bytes()
    def test_exact_pins(self):
        self.assertEqual(sha(self.original),CLASS_PIN)
        self.assertEqual(sha((ROOT/'vendor/REVIEW.md').read_bytes()),REVIEW_PIN)
    def test_round_trip(self):self.assertEqual(restore(transform(self.original)),self.original)
    def test_drift_refused(self):
        for data in (self.original+b'\n', self.original.replace(b'#lang',b'# lang',1),b''):
            with self.assertRaises(ValueError):transform(data)
    def test_duplicate_anchor_refused(self):
        with self.assertRaises(ValueError):once(b'aa',b'a',b'b')
    def test_repeated_transform_refused(self):
        with self.assertRaises(ValueError):transform(transform(self.original))
    def test_restore_drift_refused(self):
        with self.assertRaises(ValueError):restore(transform(self.original)+b'\n')
    def test_original_body_verbatim_once(self):
        body=ORIGINAL_HASH.split(b'\n',1)[1][:-1]
        self.assertEqual(instrumented_hash().count(body),1)
        self.assertNotIn(b'(eq-hash-code ',support())
    def test_helper_exact_single_conversion(self):
        h=observed_helper().replace(b'(probe-inspectable-struct->vector v category)',b'(inspectable-struct->vector v)')
        h=h.replace(b'\n  (probe-note-vector! category (vector-length vec))',b'')
        self.assertEqual(h,ORIGINAL_HELPER)
        self.assertEqual(observed_helper().count(b'(struct->vector '),1)
    def test_custom_dispatch_unchanged(self):
        anchor=b'(define equal<%>'
        self.assertEqual(self.original.split(anchor)[1],transform(self.original).split(anchor)[1])
    def test_no_global_memory_or_extra_conversion(self):
        s=support()
        self.assertNotIn(b'current-memory-use',s);self.assertNotIn(b'struct->vector',s)
        self.assertNotIn(b'collect-garbage',s)
    def test_weak_registry(self):
        s=support();self.assertEqual(s.count(b'(make-weak-box '),3)
        self.assertNotIn(b'(set! probe-definitions definitions)',s)
    def test_break_predicate_and_categories(self):
        s=support()
        self.assertIn(b'(define (probe-diagnostic-failure? v) (not (exn:break? v)))',s)
        self.assertNotIn('definitions-visible',CATEGORIES)
        self.assertIn('definitions-not-skipped',CATEGORIES)
    def test_generated_sources_fresh(self):generate(True);gh.generate(True);gn.generate(True)
    def test_host_restoration(self):
        for name,data in gh.derivatives().items():self.assertEqual(gh.restore_host(name,data),(ROOT/'vendor/host'/name).read_bytes())
    def test_small_tight_window(self):
        data=gh.derivatives()[gh.WORKFLOW]
        self.assertLess(data.index(b'(probe-begin! frame defs ints)'),data.index(b'(send button command)'))
        self.assertLess(data.index(b'(probe-end!)'),data.index(b'(define arrows (hash-copy'))
        self.assertIn(b'(parameterize ([current-check-handler raise])',data)
    def test_native_assertions_fatal(self):
        data=(ROOT/'native/test-actual-forms.rkt').read_bytes()
        self.assertIn(b'(parameterize ([current-check-handler raise])',data)
        for scenario in ('observer-break','observer-fault','conversion-fault','custom-dispatch','caps-match','caps-attempt','weak-registry','public-dispatch'):
            self.assertIn(scenario.encode(),data)
    def test_native_mutation_actual_module_and_readback(self):
        data=(ROOT/'native/test-actual-forms.rkt').read_bytes()
        self.assertNotIn(b'namespace-set-variable-value!',data)
        self.assertIn(b'(lambda (value) (set! probe-definitions-not-skipped-vectors value))',data)
        self.assertIn(b'(check-false (variable-reference-constant? fault-counter-reference))',data)
        self.assertIn(b"(check-eq? (private 'probe-definitions-not-skipped-vectors) value)",data)
        self.assertIn(b"(check-eq? (hash-ref (state) 'definitions_not_skipped_vectors) value)",data)
        self.assertLess(data.index(b"(set-fault-counter! 'fault)"),data.index(b'(set-fault-counter! 0)'))
        self.assertLess(data.index(b'(set-fault-counter! 0)'),data.index(b'(write-json'))
    def test_new_racket_lexical_smoke(self):
        for name in ['native/bootstrap.rkt','native/host-probe.rkt','native/test-actual-forms.rkt']:
            with self.subTest(name=name):balanced((ROOT/name).read_bytes())
        balanced(support());balanced(instrumented_hash());balanced(observed_helper())
        for data in gn.forms().values():balanced(data)

class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.source=self.base/'source';p=self.source/overlay.RELATIVE_CLASS;p.parent.mkdir(parents=True)
        p.write_bytes((ROOT/'vendor/class-internal.rkt').read_bytes())
        self.out=self.base/'out'
    def tearDown(self):self.tmp.cleanup()
    def stage(self):return overlay.stage(self.source,self.out)
    def test_new_overlay_verified(self):self.assertEqual(self.stage(),overlay.verify(self.out))
    def test_original_unchanged(self):self.stage();self.assertEqual(sha((self.source/overlay.RELATIVE_CLASS).read_bytes()),CLASS_PIN)
    def test_repeat_refused(self):
        self.stage()
        with self.assertRaises(ValueError):self.stage()
    def test_relative_root_refused(self):
        with self.assertRaises(ValueError):overlay.stage(Path('source'),self.out)
    def test_source_leaf_symlink_refused(self):
        p=self.source/overlay.RELATIVE_CLASS;data=p.read_bytes();p.unlink();q=self.base/'other';q.write_bytes(data);p.symlink_to(q)
        with self.assertRaises(ValueError):self.stage()
    def test_destination_symlink_refused(self):
        self.out.symlink_to(self.base/'absent')
        with self.assertRaises(ValueError):self.stage()
    def test_overlap_refused(self):
        with self.assertRaises(ValueError):overlay.stage(self.source,self.source/'out')
    def test_symlinked_temp_ancestor_supported(self):
        alias=self.base/'alias';alias.symlink_to(self.base,target_is_directory=True)
        result=overlay.stage(alias/'source',alias/'out')
        self.assertEqual(result,overlay.verify(self.out))
    def test_alias_overlap_refused(self):
        alias=self.base/'alias';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(ValueError):overlay.stage(self.source,alias/'out')
    def test_bad_source_refused_before_output(self):
        (self.source/overlay.RELATIVE_CLASS).write_bytes(b'bad')
        with self.assertRaises(ValueError):self.stage()
        self.assertFalse(self.out.exists())
    def test_manifest_mutations(self):
        self.stage();path=self.out/'MANIFEST.json';original=path.read_bytes();data=json.loads(original)
        mutations=[]
        for key,value in [('native_execution',True),('original_sha256','0'*64),('schema','unknown')]:
            m=copy.deepcopy(data);m[key]=value;mutations.append(m)
        m=copy.deepcopy(data);m['files']['../outside']='0'*64;mutations.append(m)
        m=copy.deepcopy(data);m['files'].pop('original/class-internal.rkt');mutations.append(m)
        for m in mutations:
            path.write_text(json.dumps(m))
            with self.assertRaises(ValueError):overlay.verify(self.out)
        path.write_bytes(original)
    def test_duplicate_manifest_key_refused(self):
        self.stage();p=self.out/'MANIFEST.json';p.write_text('{"schema":1,"schema":2}')
        with self.assertRaises(ValueError):overlay.verify(self.out)
    def test_content_mutation_refused(self):
        self.stage();(self.out/'overlay/collects/racket/private/class-internal.rkt').write_bytes(b'bad')
        with self.assertRaises(ValueError):overlay.verify(self.out)
    def test_unlisted_file_refused(self):
        self.stage();(self.out/'extra').write_text('x')
        with self.assertRaises(ValueError):overlay.verify(self.out)
    def test_output_symlink_refused(self):
        self.stage();(self.out/'escape').symlink_to(self.source)
        with self.assertRaises(ValueError):overlay.verify(self.out)


def state():
    d={'schema':'openracket-object-hash-probe/v1','enabled':True,'instance':'object-hash-probe-v1123',
       'started':True,'active':False,'stop_reason':'host-complete','attempt_cap':20000,'match_cap':128,
       'attempts':1,'matches':0,'diagnostic_faults':0,'scope':'registered-handler-default-hash-entries',
       'allocation_unit':'original-struct-vector-slots','eligibility':'unresolved-no-matching-calls'}
    d.update({f"{c.replace('-','_')}_{s}":0 for c in CATEGORIES for s in co.STATS});return d

def matched(kind='skipped'):
    d=state();d['matches']=1
    for stat,value in [('matches',1),('vectors',1),('slots',17),('max_slots',17),('returns',1),('fallbacks',1)]:d[f'definitions_{kind}_{stat}']=value
    d['eligibility']='plain-skipped-original-fallback-observed' if kind=='skipped' else 'no-plain-skipped-fallback-observed-in-bounded-sample'
    return d

class ObservationTests(unittest.TestCase):
    def test_started_not_armed_refused(self):
        d=matched();d['stop_reason']='not-armed'
        with self.assertRaises(ValueError):co.validate(d)
    def test_never_started_activity_refused(self):
        d=state();d['started']=False;d['stop_reason']='not-armed'
        with self.assertRaises(ValueError):co.validate(d)
    def test_never_started_wrong_reason_refused(self):
        d=state();d['started']=False;d['attempts']=0
        with self.assertRaises(ValueError):co.validate(d)
    def test_never_started_zero_unresolved(self):
        d=state();d['started']=False;d['attempts']=0;d['stop_reason']='not-armed'
        self.assertFalse(co.validate(d)['actionable'])
    def test_false_fault_reason_refused(self):
        d=matched();d['stop_reason']='diagnostic-fault'
        with self.assertRaises(ValueError):co.validate(d)
    def test_zero_matches_unresolved(self):self.assertEqual(co.validate(state())['conclusion'],'unresolved')
    def test_valid_witness(self):self.assertEqual(co.validate(matched())['conclusion'],'eligible-original-fallback-observed')
    def test_not_skipped_fallback_not_eligible(self):self.assertEqual(co.validate(matched('not_skipped'))['conclusion'],'no-eligible-call-observed-in-bounded-sample')
    def test_impersonator_not_eligible(self):self.assertEqual(co.validate(matched('impersonator'))['conclusion'],'no-eligible-call-observed-in-bounded-sample')
    def test_inspection_failure_unresolved(self):
        d=matched('inspection_failed');d['eligibility']='unresolved-inspection-failure'
        self.assertFalse(co.validate(d)['actionable'])
    def test_incomplete_unresolved(self):
        d=matched();d['definitions_skipped_returns']=d['definitions_skipped_fallbacks']=0;d['eligibility']='no-plain-skipped-fallback-observed-in-bounded-sample'
        self.assertEqual(co.validate(d)['conclusion'],'unresolved')
    def test_fault_unresolved(self):
        d=matched();d['diagnostic_faults']=1;d['eligibility']='unresolved-diagnostic-fault';self.assertFalse(co.validate(d)['actionable'])
    def test_aborted_unresolved(self):
        d=matched();d['stop_reason']='host-aborted';self.assertFalse(co.validate(d)['actionable'])
    def test_bad_numeric_boolean(self):
        d=matched();d['definitions_skipped_vectors']=True
        with self.assertRaises(ValueError):co.validate(d)
    def test_count_order_refused(self):
        d=matched();d['definitions_skipped_returns']=2
        with self.assertRaises(ValueError):co.validate(d)
    def test_false_cap_refused(self):
        d=matched();d['stop_reason']='match-cap'
        with self.assertRaises(ValueError):co.validate(d)
    def test_cap_excess_refused(self):
        d=matched();d['attempts']=20001
        with self.assertRaises(ValueError):co.validate(d)
    def test_false_claim_refused(self):
        d=state();d['eligibility']='plain-skipped-original-fallback-observed'
        with self.assertRaises(ValueError):co.validate(d)
    def test_non_scalar_refused(self):
        d=matched();d['definitions_skipped_slots']=[17]
        with self.assertRaises(ValueError):co.validate(d)
    def test_missing_field_refused(self):
        d=matched();del d['match_cap']
        with self.assertRaises(ValueError):co.validate(d)
    def test_disabled_activity_refused(self):
        d=matched();d['enabled']=False
        with self.assertRaises(ValueError):co.validate(d)
    def test_live_window_refused(self):
        d=matched();d['active']=True
        with self.assertRaises(ValueError):co.validate(d)


class SourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        pins=json.loads((ROOT/'SOURCE-PINS.json').read_text());runtime=json.loads((ROOT/'RUNTIME-PINS.json').read_text())
        self.observation=matched()
        self.source={'schema':'openracket-object-hash-source/v1','runtime_root':'/isolated/probe',
          'executable':'/isolated/probe/bin/racket','flag':'1','enabled':True,'build_id':pins['build_id'],
          'instance':self.observation['instance'],'host_sha256':sha((ROOT/'native/tests/reference-host-0520.rkt').read_bytes()),
          'workflow_window':'check-syntax-command-through-binding-completion','dependency_recompile':'separate-required-preflight',
          'sources':{k:{'path':'/isolated/probe/collects/'+k+'.rkt','sha256':v} for k,v in runtime.items()}}
        self.result={'status':'passed','genuine_host':True,'repeated_real_run':True,'racket':'9.3','ui':'stock',
          'follow_on_case':'check-syntax','follow_on_result':{'status':'passed','case':'check-syntax'}}
        self.graph=copy.deepcopy(co.EDGES)
    def validate(self):return co.validate_run(self.source,self.observation,self.result,self.graph)
    def test_full_synthetic_evidence(self):self.assertTrue(self.validate()['source_instance_proved'])
    def test_instance_mismatch_refused(self):
        self.source['instance']='other'
        with self.assertRaises(ValueError):self.validate()
    def test_flag_mismatch_refused(self):
        self.source['flag']='0'
        with self.assertRaises(ValueError):self.validate()
    def test_build_mismatch_refused(self):
        self.source['build_id']='0'*64
        with self.assertRaises(ValueError):self.validate()
    def test_source_mismatch_refused(self):
        self.source['sources']['racket/private/class-internal']['sha256']='0'*64
        with self.assertRaises(ValueError):self.validate()
    def test_source_escape_refused(self):
        self.source['sources']['racket/private/class-internal']['path']='/other/racket/private/class-internal.rkt'
        with self.assertRaises(ValueError):self.validate()
    def test_workflow_failure_refused(self):
        self.result['follow_on_result']['status']='failed'
        with self.assertRaises(ValueError):self.validate()
    def test_graph_mutation_refused(self):
        self.graph[1][2]=34
        with self.assertRaises(ValueError):self.validate()
    def test_graph_boolean_refused(self):
        self.graph[0][0]=True
        with self.assertRaises(ValueError):self.validate()
    def test_raw_records_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'raw.log'
            rows=[('OPENRACKET_OBJECT_HASH_SOURCE',self.source),('OPENRACKET_OBJECT_HASH_OBSERVATION',self.observation),
                  ('OPENRACKET_NATIVE_RESULT',self.result),('OPENRACKET_BINDING_GRAPH',self.graph)]
            data=('\n'.join(k+' '+json.dumps(v) for k,v in rows)+'\n').encode();p.write_bytes(data)
            self.assertTrue(co.read_log(p)['actionable']);self.assertEqual(p.read_bytes(),data)
            p.write_bytes(data+data)
            with self.assertRaises(ValueError):co.read_log(p)

if __name__=='__main__':unittest.main()
