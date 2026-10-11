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
        self.assertIn('(equal? (getenv "OPENRACKET_BINDING_TABLE_EAGER") "1")',prepare.ACTIVATION)
        self.assertNotIn('(set! openracket-binding-table-eager-enabled?',self.patched.decode())
        self.assertFalse(self.manifest['default_enabled'])
    def test_original_self_check_is_first_and_byte_identical(self):
        stock=extract.form_at(self.stock.decode(),'(define/private (add-to-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/private (add-to-bindings-table ')
        prefix=stock.split('                [else',1)[0]
        self.assertTrue(patched.startswith(prefix))
        self.assertLess(patched.index('(object=?'),patched.index('[(and binding-eager-state'))
    def test_stock_core_unchanged_after_prelude(self):
        stock=extract.form_at(self.stock.decode(),'(define/private (add-to-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/private (add-to-bindings-table ')
        needle='                 (define key (list start-text start-left start-right))'
        self.assertEqual(stock[stock.index(needle):],patched[patched.rindex(needle):])
    def test_owner_and_four_exact_integer_guards(self):
        self.assertIn('(eq? start-text this) (eq? end-text this)',prepare.NEW_ADD)
        for p in ['start-left','start-right','end-left','end-right']:
            self.assertIn(f'(exact-integer? {p})',prepare.NEW_ADD)
        self.assertIn('(list start-left start-right end-left end-right)',prepare.NEW_ADD)
        self.assertNotIn('make-hasheq',prepare.STATE)
    def test_eager_public_write_precedes_both_cache_commits(self):
        source=prepare.NEW_ADD
        write=source.index('(hash-set! bindings-table key')
        start_cache=source.index('(hash-set! (cdr state) start-key next-priors)')
        edge_cache=source.index('(hash-set! (car state) edge #t)')
        self.assertLess(write,start_cache); self.assertLess(start_cache,edge_cache)
        self.assertIn('(let ([updated (set-add priors new)])',source[write:start_cache])
        self.assertIn('(set! next-priors updated)',source[write:start_cache])
        self.assertIn('(eq? state binding-eager-state)',source[write:start_cache])
        self.assertIn('(eq? target bindings-table)',source[write:start_cache])
        self.assertNotIn('materialize-bindings-table!',self.patched.decode())
        self.assertNotIn('binding-pending',self.patched.decode())
        self.assertNotIn('(mutable-set',prepare.STATE)
    def test_escape_cleanup_and_continuation_reentry_fail_closed(self):
        source=prepare.NEW_ADD
        self.assertIn('(dynamic-wind',source)
        self.assertIn("(unless completed? (disable-binding-eager! state 'interrupted))",source)
        self.assertIn("(when entered? (disable-binding-eager! state 'interrupted))",source)
        self.assertIn('(set! completed? #f)',source)
        self.assertIn('(eq? binding-eager-in-flight state)',source)
        self.assertIn('(= generation binding-eager-generation)',source)
        self.assertNotIn('with-handlers',source)
        self.assertEqual(source.count('(parameterize-break #f'),2)
        body=source[source.index('(define edge '):source.index('(set! completed? #t)')]
        self.assertNotIn('parameterize-break',body)
        disable=extract.form_at(prepare.STATE,'(define/private (disable-binding-eager! ')
        self.assertLess(disable.index('(set! binding-eager-state #f)'),
                        disable.index('(set! binding-eager-fallback-reason'))
        self.assertNotIn('hash-clear!',disable)
    def test_public_identity_and_tooltip_branch(self):
        stock=extract.form_at(self.stock.decode(),'(define/public (syncheck:get-bindings-table ')
        patched=extract.form_at(self.patched.decode(),'(define/public (syncheck:get-bindings-table ')
        self.assertEqual(patched.replace(prepare.NEW_GET,prepare.OLD_GET),stock)
        self.assertEqual(prepare.NEW_GET.count('bindings-table]'),1)
    def test_witness_is_bounded_readonly(self):
        witness=extract.form_at(prepare.STATE,'(define/public (openracket:get-binding-table-eager-state)')
        for forbidden in ['set!','binding-pending)','hash-set!','in-hash','for/', 'materialize-bindings-table!']:
            self.assertNotIn(forbidden,witness)
        self.assertTrue(witness.split('\n')[1].strip().startswith('(hash '))
        self.assertIn("'public_keys (hash-count bindings-table)",witness)
        self.assertIn("'pending 0",witness)
        self.assertIn("'materializations 0",witness)
    def test_reset_replaces_only_current_state(self):
        self.assertIn('(set! binding-eager-state',prepare.RESET)
        self.assertIn('(set! binding-eager-in-flight #f)',prepare.RESET)
        self.assertIn('(set! binding-eager-generation (add1 binding-eager-generation))',prepare.RESET)
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
    def test_fault_modules_have_only_explicit_test_hook_substitutions(self):
        for arm,source in [('stock',self.stock),('candidate',self.patched)]:
            generated=extract.extract(source,arm=='candidate',fault=True)
            self.assertEqual((ROOT/f'tests/generated/{arm}-fault.rkt').read_bytes(),generated)
            original=extract.form_at(source.decode(),'(define/private (add-to-bindings-table ')
            fault=extract.form_at(generated.decode(),'(define/private (add-to-bindings-table ')
            for anchor,hook in extract.FAULT_HOOKS: fault=fault.replace(hook,'')
            fault=fault.replace('(let ([result (set-add priors new)]) (test-after-set-add) result)',
                                '(set-add priors new)')
            self.assertEqual(fault,original)
            brackets(generated.decode())
        for forbidden in ['test-after-public-write','test-after-first-cache','test-after-set-add','test:arm-']:
            self.assertNotIn(forbidden,self.patched.decode())
    def test_fault_and_resumption_native_cases_are_required(self):
        source=(ROOT/'tests/bindings-differential.rkt').read_text()
        for required in ['before-public after-public after-first-cache',
                         'exception arbitrary break escape', 'call-with-continuation-prompt',
                         'saved-s', 'saved-c', 'write exposure reset',
                         'retry consults authoritative public table',
                         'later insertion never loses published edge after cache failure',
                         'original hash-set! argument order preserves old target',
                         'resumed public write exactly matches stock',
                         'next insertion reads authoritative table after resumption',
                         '(break-thread (current-thread))',
                         'requested break leaves no stranded in-flight marker']:
            self.assertIn(required,source)
    def test_native_test_lexical_integrity(self):
        brackets((ROOT/'tests/bindings-differential.rkt').read_text())
    def test_throwing_hash_lock_observation_is_owned_bounded_and_typed(self):
        source=(ROOT/'tests/bindings-differential.rkt').read_text()
        observer=extract.form_at(source,'(define (observe-poisoned-count ')
        for required in ['(make-custodian)', '(make-channel)', '(make-semaphore 0)',
                         '(parameterize ([current-custodian owner])',
                         '(semaphore-post entered)', '(sync/timeout 5 entered)',
                         '(sync/timeout 1 result)', '(thread-dead? worker)',
                         '(custodian-shutdown-all owner)', '(thread-dead-evt worker)',
                         "(list 'raised", "(list 'returned", "(list 'non-exception",
                         'CUSTOM_HASH_LOCK_BOUNDARY', '(flush-output)']:
            self.assertIn(required,observer)
        self.assertLess(observer.index('(semaphore-post entered)'),observer.index('(hash-count table)'))
        case=source[source.index("(stage! 'throwing-owner)"):source.index(';; Deterministic fault modules')]
        self.assertIn('owner-hash error still occurs during insertion',case)
        self.assertIn("(observe-poisoned-count initial-stock 'stock)",case)
        self.assertIn("(observe-poisoned-count initial-candidate 'candidate-off)",case)
        off=case[case.index('    [else'):case.index('  ;; Only after recording')]
        self.assertNotIn('(state ',off)
        self.assertNotIn('(hash-count ',off)
        self.assertNotIn('(compare ',off)
        self.assertLess(case.index("(observe-poisoned-count initial-candidate 'candidate-off)"),
                        case.index('(send s syncheck:init-arrows)'))
        self.assertIn('failed eager insertion permanently discards caches',case)
        self.assertIn('getter has no deferred error',case)
        self.assertIn('fresh tables agree after callback escape',case)
    def test_native_stage_markers_are_flushed(self):
        source=(ROOT/'tests/bindings-differential.rkt').read_text()
        marker=extract.form_at(source,'(define (stage! ')
        self.assertIn('BINDINGS_EAGER_STAGE',marker)
        self.assertIn('(flush-output)',marker)
        for required in ['throwing-owner-error-parity', 'throwing-owner-reset-after-observation',
                         'fault stage=~a kind=~a', 'requested-break stage=~a',
                         'exposure stage=~a', 'resumed-continuation transition=~a']:
            self.assertIn(required,source)
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
