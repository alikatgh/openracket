import hashlib,importlib.util,json,re
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'scripts/prepare-host.py';s=importlib.util.spec_from_file_location('prepare',p);prep=importlib.util.module_from_spec(s);s.loader.exec_module(prep)
def balanced(text):
    stack=[];string=escape=comment=False
    for c in text:
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
        elif c in ')]}':
            if not stack or '([{'.index(stack.pop())!=')]}'.index(c):raise AssertionError('Unbalanced delimiter')
    assert not stack and not string
class Tests(unittest.TestCase):
    def test_exact_host_derivation_and_workflow_pin(self):
        p=json.loads((ROOT/'tests/binding-native-pins.json').read_text())
        self.assertEqual(prep.generate(),(ROOT/'tests/independent-native-host.rkt').read_bytes())
        for key,name in [('host','independent-native-host.rkt'),('workflow','independent-native-workflows.rkt')]:
            self.assertEqual(hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest(),p[key])
    def test_actual_keymap_commands_and_exact_positions(self):
        s=(ROOT/'tests/binding-postflight.rkt').read_text()
        for part in ['call-function command defs (new key-event% [key-code #\\x]) #t',
                     'cs-jump-to-binding','cs-jump-to-next-bound-occurrence','cs-jump-to-previous-bound-occurrence',
                     "'(45 45) '(27 31)","'(32 33) '(38 39)"]:
            self.assertIn(part,s)
    def test_no_simulated_or_mutated_binding_graph(self):
        s=(ROOT/'tests/binding-postflight.rkt').read_text()
        for banned in ['syncheck:add-arrow','syncheck:init-arrows','set-syncheck-running-mode','hash-set! table','hash-remove! table','hash-clear! table','set-add!']:
            self.assertNotIn(banned,s)
        for required in ['(send defs syncheck:get-bindings-table)','(hash-strong? table)','(set-equal? value)','(not (set-mutable? value))','(snapshot) graph']:
            self.assertIn(required,s)
    def test_eager_hit_and_publication_cannot_be_vacuous(self):
        s=(ROOT/'tests/binding-postflight.rkt').read_text()
        for required in ["(positive? (hash-ref state 'accepted))","(hash-ref state 'materializations) 0", "(hash-ref state 'unsupported_fallbacks) 0", "'public-exposure",'(witness) witness-before',"(hash-ref state 'eager_writes) 8","(hash-ref state 'public_keys) 3","(hash-ref state 'in_flight)"]:
            self.assertIn(required,s)
    def test_eager_identity_cannot_select_prior_lazy_experiment(self):
        source=(ROOT/'tests/binding-postflight.rkt').read_text()
        for required in ('OPENRACKET_BINDING_TABLE_EAGER','openracket-binding-table-eager-enabled?',
                         'openracket:get-binding-table-eager-state','openracket-native-binding-eager-graph/v1',"'eager_witness"):
            self.assertIn(required,source)
        for forbidden in ('OPENRACKET_BINDING_TABLE_INDEX','binding-table-index','index_witness'):
            self.assertNotIn(forbidden,source)
    def test_fatal_handler_and_post_navigation_preservation(self):
        s=(ROOT/'tests/binding-postflight.rkt').read_text()
        for required in ['(parameterize ([current-check-handler raise])','(assert-rackunit-failure-propagation!)',
                         '(send defs get-text) text-before','(send defs get-filename) filename-before',
                         '(send defs is-modified?) modified-before','(send canvas get-editor) defs',
                         '(send frame get-current-tab) tab',"#:exists 'error"]:
            self.assertIn(required,s)
        self.assertNotIn('(eq? (current-check-handler) raise)',s)
    def test_pinned_runtime_path_appearance_dependencies_exist(self):
        pins=json.loads((ROOT/'tests/baseline-tool-pins.json').read_text())
        self.assertEqual(set(pins),{'native-appearance.rkt','native-appearance-platform.rkt','native-appearance-cocoa.rkt','native-appearance-gtk.rkt','native-appearance-cocoa-policy.rkt','native-appearance-gtk-pair.rkt'})
        for name,sha in pins.items():
            path=ROOT/'tool'/name
            self.assertFalse(path.is_symlink())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),sha)
            for dependency in re.findall(r'"([^"]+\.rkt)"',path.read_text()):
                self.assertTrue((path.parent/dependency).is_file(),dependency)
        source=(ROOT/'tests/independent-native-appearance-workflows.rkt').read_text()
        for name in ('native-appearance.rkt','native-appearance-platform.rkt'):
            self.assertIn('"../tool/'+name+'"',source)
        platform=(ROOT/'tool/native-appearance-platform.rkt').read_text()
        for name in ('native-appearance-cocoa.rkt','native-appearance-gtk.rkt'):
            self.assertIn('"'+name+'"',platform)
    def test_diagnostics_preserve_every_original_postflight_assertion(self):
        seams=json.loads((ROOT/'tests/postflight-diagnostic-seams.json').read_text())
        baseline=(ROOT/'tests/reference-postflight-1102.rkt.txt').read_bytes()
        self.assertEqual(hashlib.sha256(baseline).hexdigest(),seams['baseline_sha256'])
        self.assertEqual(seams['baseline_sha256'],'e885f5e08f37fed6846db28c0616e8c2dba9c11dcc3b146f470b829cb717cee6')
        source=(ROOT/'tests/binding-postflight.rkt').read_text()
        for added,original in [(seams['new_require'],seams['old_require']),
                               (seams['new_wrapper'],seams['old_wrapper']),
                               (seams['witness_insertion'],'')]:
            self.assertEqual(source.count(added),1)
            source=source.replace(added,original)
        self.assertEqual(source.encode(),baseline)
    def test_diagnostics_rethrow_original_and_pin_native_proven_helper(self):
        seams=json.loads((ROOT/'tests/postflight-diagnostic-seams.json').read_text())
        wrapper=seams['new_wrapper']
        self.assertIn('(parameterize ([current-check-handler raise])',wrapper)
        self.assertIn('(report-failure!',wrapper)
        self.assertIn('(raise failure))])\n      (capture! frame)',wrapper)
        self.assertIn('OPENRACKET_BINDING_POSTFLIGHT_FAILURE',wrapper)
        self.assertIn('(report-failure!\n        state\n        (lambda (observed)',seams['witness_insertion'])
        source=(ROOT/'tests/binding-postflight.rkt').read_text()
        self.assertLess(source.index('OPENRACKET_BINDING_POSTFLIGHT_STATE'),
                        source.index('(require! (and (hash? state)'))
        for name,pin in {
            'native-tool-failure-diagnostics.rkt':'3147fad446f383778b1ae2bb3f55a3eea3d71dc38d26b9ab9b107e1deb7be22a',
            'native-tool-failure-diagnostics-standalone.rkt':'aaa23198c848e9f3284a296b1621b283458dc04311424b43821b83a5064e2caa',
        }.items():
            self.assertEqual(hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest(),pin)
    def test_balanced_source(self):
        for p in (ROOT/'tests').glob('*.rkt'):balanced(p.read_text())
if __name__=='__main__':unittest.main()
