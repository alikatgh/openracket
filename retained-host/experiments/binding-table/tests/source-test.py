#!/usr/bin/env python3
"""Python/source contracts only. This is not native Racket execution or parity."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location('binding_'+name, ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
prepare=load('prepare'); extract=load('extract'); applier=load('apply')
def brackets(text):
    stack=[]; string=False; escape=False; comment=False
    for ch in text:
        if comment:
            if ch=='\n': comment=False
            continue
        if string:
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch=='"': string=False
            continue
        if ch==';': comment=True
        elif ch=='"': string=True
        elif ch in '([{': stack.append(ch)
        elif ch in ')]}':
            if not stack or '([{'.index(stack.pop())!=')]}'.index(ch):
                raise AssertionError('mismatched lexical delimiter')
    if string or stack: raise AssertionError('unclosed lexical delimiter')
class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock=(ROOT/'vendor/gui.rkt').read_bytes()
        cls.patched=(ROOT/'overlay/gui.rkt').read_bytes()
        cls.manifest=json.loads((ROOT/'manifest.json').read_text())
    def test_exact_original_and_reproduction(self):
        self.assertEqual(prepare.sha(self.stock),prepare.PIN)
        self.assertEqual(prepare.generate(self.stock),self.patched)
        self.assertEqual(prepare.restore(self.patched),self.stock)
        self.assertEqual(prepare.sha(self.patched),self.manifest['patched_sha256'])
    def test_mutated_original_refused(self):
        with self.assertRaises(ValueError): prepare.generate(self.stock+b'\n')
    def test_only_five_source_seams(self):
        self.assertEqual(len(prepare.SEAMS),5)
        for old,new in prepare.SEAMS:
            self.assertEqual(self.stock.decode().count(old),1)
            self.assertEqual(self.patched.decode().count(new),1)
    def test_default_off_read_only_activation(self):
        self.assertIn('(equal? (getenv "OPENRACKET_BINDING_TABLE_INDEX") "1")',prepare.ACTIVATION)
        self.assertNotIn('(set! openracket-binding-table-index-enabled?',self.patched.decode())
        self.assertFalse(self.manifest['default_enabled'])
    def test_original_self_check_is_first_and_byte_identical(self):
        stock=extract.form_at(self.stock.decode(),'(define/private (add-to-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/private (add-to-bindings-table ')
        prefix=stock.split('                [else',1)[0]
        self.assertTrue(patched.startswith(prefix))
        self.assertLess(patched.index('(object=?'),patched.index('[(and binding-index'))
    def test_stock_core_unchanged_after_prelude(self):
        stock=extract.form_at(self.stock.decode(),'(define/private (add-to-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/private (add-to-bindings-table ')
        needle='                 (define key (list start-text start-left start-right))'
        self.assertEqual(stock[stock.index(needle):],patched[patched.index(needle):])
    def test_owner_and_four_exact_integer_guards(self):
        self.assertIn('(eq? start-text this) (eq? end-text this)',prepare.NEW_ADD)
        for p in ['start-left','start-right','end-left','end-right']:
            self.assertIn(f'(exact-integer? {p})',prepare.NEW_ADD)
        self.assertIn('(list start-left start-right end-left end-right)',prepare.NEW_ADD)
        self.assertNotIn('make-hasheq',prepare.STATE)
    def test_replay_uses_original_method_and_order(self):
        self.assertIn('(reverse binding-pending)',prepare.STATE)
        self.assertLess(prepare.STATE.index('(set! binding-index #f)'),prepare.STATE.index('(for ([entry'))
        self.assertIn('(add-to-bindings-table this (list-ref entry 0) (list-ref entry 1)',prepare.STATE)
        self.assertNotIn('hash-set! bindings-table',prepare.STATE)
        self.assertNotIn('mutable-set',prepare.STATE)
    def test_public_identity_and_tooltip_branch(self):
        stock=extract.form_at(self.stock.decode(),'(define/public (syncheck:get-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/public (syncheck:get-bindings-table ')
        self.assertEqual(patched.replace(prepare.NEW_GET,prepare.OLD_GET),stock)
        self.assertEqual(prepare.NEW_GET.count('bindings-table]'),1)
    def test_witness_is_bounded_readonly(self):
        witness=extract.form_at(prepare.STATE,'(define/public (openracket:get-binding-table-index-state)')
        for forbidden in ['set!','binding-pending)','bindings-table','hash-set!','materialize-bindings-table!']:
            self.assertNotIn(forbidden,witness)
        self.assertTrue(witness.split('\n')[1].strip().startswith('(hash '))
    def test_reset_replaces_only_current_state(self):
        self.assertIn('(set! binding-index',prepare.RESET)
        self.assertIn('(set! binding-pending \'())',prepare.RESET)
        self.assertIn('(set! binding-generation (add1 binding-generation))',prepare.RESET)
        self.assertNotIn('hash-clear!',prepare.RESET)
    def test_actual_form_generated_files_match(self):
        for arm,source in [('stock',self.stock),('candidate',self.patched)]:
            generated=extract.extract(source,arm=='candidate')
            self.assertEqual((ROOT/f'tests/generated/{arm}.rkt').read_bytes(),generated)
            for needle in ['(define/private (add-to-bindings-table ',
                           '(define/public (syncheck:get-bindings-table ',
                           '(define/public (syncheck:init-arrows)']:
                self.assertIn(extract.form_at(source.decode(),needle),generated.decode())
            brackets(generated.decode())
    def test_native_test_lexical_integrity(self):
        brackets((ROOT/'tests/bindings-differential.rkt').read_text())
    def test_native_boundary_cases_are_explicit(self):
        source=(ROOT/'tests/bindings-differential.rkt').read_text()
        for required in ['in-range 1200','hash-remove!','hash-clear!','mutable-set',
                         'syncheck:init-arrows','test:tooltip','object/c','inspect #f',
                         'prop:equal+hash','equal<%>','deliberate','CUSTOM_CALLBACK_BOUNDARY',
                         'exact same-process hash/set enumeration order']:
            self.assertIn(required,source)
    def test_stateful_foreign_equality_coverage(self):
        source=(ROOT/'tests/bindings-differential.rkt').read_text()
        self.assertTrue(all(required in source for required in [
            '(set! equivalent? #t)', '(set! equivalent? #f)',
            '(define/public (equal-hash-code-of recur) 31)',
            '(define/public (equal-secondary-hash-code-of recur) 31)',
            'stateful equality begins after permanent fallback',
            'stateful foreign duplicate decisions',
            'candidate used retained equality callback',
            'stateful equality keeps hashes constant']))
    def test_pinned_runtime_reference_blobs(self):
        for f,pin in [('class-internal.rkt','b3134180ee93023bfc2132d67c676b8246574c66'),
                      ('set-types.rkt','13ed507f77382b3f94987399c500174e9d413aa9')]:
            b=(ROOT/'vendor'/f).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),pin)
            self.assertEqual(prepare.sha(b),self.manifest['reference_source_sha256'][f])
class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        # macOS may return /var/... although /var aliases /private/var.
        # Fixture callers must supply canonical paths; the applier must keep
        # rejecting aliases rather than relaxing its production path checks.
        self.root=Path(self.temp.name).resolve()/'runtime'; self.root.mkdir()
        self.target=self.root/'pkgs/drracket-core-lib/drracket/private/syncheck/gui.rkt'
        self.target.parent.mkdir(parents=True)
        for f in ['gui.rkt','intf.rkt','local-member-names.rkt']:
            (self.target.parent/f).write_bytes((ROOT/'vendor'/f).read_bytes())
    def tearDown(self): self.temp.cleanup()
    def apply(self,**kw): return applier.apply(self.root,self.target,disposable=True,**kw)
    def test_apply_idempotence_and_revert(self):
        os.chmod(self.target,0o640)
        self.assertTrue(self.apply()['changed']); self.assertFalse(self.apply()['changed'])
        self.assertEqual(self.target.stat().st_mode&0o777,0o640)
        self.assertTrue(self.apply(revert=True)['changed'])
        self.assertEqual(self.target.read_bytes(),(ROOT/'vendor/gui.rkt').read_bytes())
        self.assertFalse(self.apply(revert=True)['changed'])
    def test_parent_alias_refused_but_resolved_apply_and_revert_succeed(self):
        # Portable reproduction of a /var -> /private/var-style ancestor alias.
        alias=self.root.parent/'temporary-parent-alias'
        alias.symlink_to(self.root.parent, target_is_directory=True)
        alias_root=alias/self.root.name
        alias_target=alias_root/self.target.relative_to(self.root)
        with self.assertRaisesRegex(ValueError, 'Symlinked runtime root refused'):
            applier.apply(alias_root,alias_target,disposable=True)
        with self.assertRaisesRegex(ValueError, 'Symlinked runtime/source path refused'):
            applier.apply(self.root,alias_target,disposable=True)
        canonical_root=alias_root.resolve()
        canonical_target=alias_target.resolve()
        self.assertEqual(canonical_root,self.root)
        self.assertEqual(canonical_target,self.target)
        self.assertTrue(applier.apply(canonical_root,canonical_target,disposable=True)['changed'])
        self.assertFalse(applier.apply(canonical_root,canonical_target,disposable=True)['changed'])
        # Idempotence must not make the noncanonical input acceptable.
        with self.assertRaisesRegex(ValueError, 'Symlinked runtime root refused'):
            applier.apply(alias_root,alias_target,disposable=True)
        self.assertTrue(applier.apply(canonical_root,canonical_target,
                                      disposable=True,revert=True)['changed'])
        self.assertFalse(applier.apply(canonical_root,canonical_target,
                                       disposable=True,revert=True)['changed'])
        self.assertEqual(self.target.read_bytes(),(ROOT/'vendor/gui.rkt').read_bytes())
        # Resolving an alias is not permission to escape the selected runtime.
        outside=self.root.parent/'outside'/self.target.relative_to(self.root)
        outside.parent.mkdir(parents=True)
        outside.write_bytes((ROOT/'vendor/gui.rkt').read_bytes())
        alias_outside=alias/outside.relative_to(self.root.parent)
        with self.assertRaisesRegex(ValueError, 'inside the independent runtime'):
            applier.apply(canonical_root,alias_outside.resolve(),disposable=True)
    def test_ack_required(self):
        with self.assertRaises(ValueError): applier.apply(self.root,self.target)
    def test_wrong_preimage(self):
        self.target.write_text('bad')
        with self.assertRaises(ValueError): self.apply()
    def test_changed_support(self):
        (self.target.parent/'intf.rkt').write_text('bad')
        with self.assertRaises(ValueError): self.apply()
    def test_symlink_target(self):
        backup=self.target.with_suffix('.backup'); self.target.rename(backup); self.target.symlink_to(backup)
        with self.assertRaises(ValueError): self.apply()
    def test_hardlink_target(self):
        os.link(self.target,self.target.with_suffix('.linked'))
        with self.assertRaises(ValueError): self.apply()
    def test_outside_root(self):
        with self.assertRaises(ValueError): applier.apply(self.root,ROOT/'vendor/gui.rkt',disposable=True)
    def test_wrong_collection_suffix(self):
        wrong=self.target.with_name('wrong.rkt'); wrong.write_bytes(self.target.read_bytes())
        with self.assertRaises(ValueError): applier.apply(self.root,wrong,disposable=True)
if __name__=='__main__': unittest.main(verbosity=2)
