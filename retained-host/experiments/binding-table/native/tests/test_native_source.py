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
    def test_fast_hit_and_materialization_cannot_be_vacuous(self):
        s=(ROOT/'tests/binding-postflight.rkt').read_text()
        for required in ["(positive? (hash-ref state 'accepted))","(hash-ref state 'materializations) 1", "(hash-ref state 'unsupported_fallbacks) 0", "'public-exposure",'(witness) witness-before']:
            self.assertIn(required,s)
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
    def test_balanced_source(self):
        for p in (ROOT/'tests').glob('*.rkt'):balanced(p.read_text())
if __name__=='__main__':unittest.main()
