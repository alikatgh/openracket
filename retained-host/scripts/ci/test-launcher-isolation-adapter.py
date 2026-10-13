#!/usr/bin/env python3
"""Portable positive/negative CI contract tests; never launch native Racket."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / 'experiments/relative-launcher-isolation-probe'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


c = module('isolation_contract_test', HERE / 'launcher-isolation-contract.py')
a = module('isolation_adapter_test', HERE / 'run-launcher-isolation.py')
s = module('isolation_source_test', EXP / 'supervise.py')
emitter = module('isolation_emitter_test', HERE / 'emit-replay-evidence.py')
decoder = module('isolation_decoder_test', HERE / 'decode-launcher-isolation-evidence.py')


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="Adapter λ's ")
        self.addCleanup(self.tmp.cleanup)
        # Every expected source/supervisor path is canonical even under TMPDIR aliases.
        self.path = Path(self.tmp.name).resolve()
        self.runtime = self.path / 'runtime'
        self.runtime.mkdir()
        (self.runtime / 'binary').write_bytes(b'fixture bytes only')
        (self.runtime / 'DrRacket.app').mkdir()
        (self.runtime / 'DrRacket.app/claim').write_bytes(b'original claim')
        self.before = c.inventory(self.runtime)
        self.source_before = c.inventory(EXP)
        self.digest = c.tree_digest(self.before)
        self.handler = {'schema': 1, 'status': 'observed', 'extension': 'rkt', 'defaults_changed': False,
                        'default_handler': 'fixture.original'}
        self.claims = [{'plist': 'DrRacket.app/Contents/Info.plist', 'sha256': 'a' * 64,
                        'bundle_identifier': 'org.racket', 'declarations': {'CFBundleDocumentTypes': []}}]
        self.audit = {'schema': 1, 'inventory': self.before, 'inventory_digest': self.digest,
                      'nested_apps': self.claims, 'macho': [{'path': 'binary'}], 'static_loader_context_pending': []}
        self.plan, self.retained = s.runtime_copy_plan(self.before)
        self.build = {'schema': 1, 'status': 'assembled-not-launched', 'original_runtime': str(self.runtime),
                      'original_runtime_digest': self.digest, 'handler_baseline': self.handler,
                      'nested_apps': [], 'native_launch_blocked_by_declarations': False,
                      'native_launch_blocked_by_loader_context': False,
                      'manual_signing_or_security_changes': False, 'intrinsic_generator_ad_hoc_signing': True,
                      'macho': self.macho_rows(), 'static_loader_context_pending': [], 'native_sha256': 'b' * 64,
                      'runtime_copy_plan': 'runtime-copy-plan.json',
                      'retained_runtime_digest': c.tree_digest(self.retained)}

    def macho_rows(self):
        return [{'path': name, 'sha256': digest * 64, 'slices': [{'cpu_type': 0x0100000C,
                    'dependencies': deps, 'rpaths': []}]} for name, digest, deps in (
                    ('Contents/MacOS/ProbeNative', 'b', ['@executable_path/../Resources/runtime/lib/helper.dylib', '/usr/lib/libSystem.B.dylib']),
                    ('Contents/Resources/runtime/bin/racket', 'd', ['/usr/lib/libSystem.B.dylib']),
                    ('Contents/Resources/runtime/lib/helper.dylib', 'e', ['/usr/lib/libSystem.B.dylib']))]

    def image_proof(self, app, arm):
        executable = app / ('Contents/MacOS/ProbeNative' if arm == 'gui' else 'Contents/Resources/runtime/bin/racket')
        helper = app / 'Contents/Resources/runtime/lib/helper.dylib'
        images = [str(executable)] + ([str(helper)] if arm == 'gui' else []) + ['/usr/lib/libSystem.B.dylib', '/usr/lib/libfixture.dylib']
        records, classifications = [], []
        for index, raw in enumerate(images):
            cache = raw == '/usr/lib/libSystem.B.dylib'
            records.append({'index': index, 'raw': raw, 'header_address': format(0x1000 + index * 4096, 'x'),
                            'magic': 0xFEEDFACF, 'cpu_type': 0x0100000C, 'file_type': 2 if index == 0 else 6,
                            'flags': 0x80000000 if cache else 0, 'shared_cache_contains_path': cache})
            kind = 'os-shared-cache' if cache else ('os-file' if raw.startswith('/usr/lib/') else 'bundle-file')
            row = {'raw': raw, 'kind': kind, 'witness_index': index}
            if not cache:
                row['resolved'] = raw
            classifications.append(row)
        snapshot = {'schema': 1, 'method': 'public-dyld-name-header-cache-v1', 'count': len(images), 'stable': True, 'records': records}
        closure = ([{'image': str(executable), 'dependency': '@executable_path/../Resources/runtime/lib/helper.dylib',
                     'resolved_candidates': [str(helper)]}] if arm == 'gui' else [])
        closure.append({'image': str(executable), 'dependency': '/usr/lib/libSystem.B.dylib', 'system': True})
        if arm == 'gui':
            closure.append({'image': str(helper), 'dependency': '/usr/lib/libSystem.B.dylib', 'system': True})
        return images, snapshot, classifications, closure

    def runner(self):
        runner = a.Runner.__new__(a.Runner)
        runner.c, runner.ci, runner.root, runner.exp = c, HERE, ROOT, EXP
        runner.proof = self.path / "Proof λ's"
        runner.proof.mkdir()
        runner.work = runner.proof / "Build Unicode λ's Probe"
        runner.original_app = runner.work / 'Path Probe.app'
        runner.relocated_app = runner.proof / "Relocated Unicode λ's Path Probe.app"
        runner.reports = self.path / 'reports'
        runner.reports.mkdir()
        runner.runtime = self.runtime
        runner.state_file = runner.reports / 'state.json'
        runner.state = {'assembled': False, 'observed': False, 'run_attempted': False, 'errors': [],
                        'declarations_block_launch': None, 'loader_context_blocks_launch': None, 'native_state': 'safe'}
        runner.source = None
        runner.save()
        return runner

    def protected(self):
        return {'schema': 1, 'original_runtime_unchanged': True, 'source_unchanged': True,
                'original_runtime_before': self.digest, 'original_runtime_after': self.digest,
                'source_before': c.tree_digest(self.source_before), 'source_after': c.tree_digest(self.source_before)}

    def build_files(self, runner, build=None):
        runtime = runner.original_app / 'Contents/Resources/runtime'
        runtime.parent.mkdir(parents=True)
        shutil.copytree(self.runtime, runtime, ignore=lambda directory, names: ['DrRacket.app'] if Path(directory) == self.runtime else [])
        native = runner.original_app / 'Contents/MacOS/ProbeNative'
        native.parent.mkdir()
        native.write_bytes(b'unchanged generated image')
        record = copy.deepcopy(build or self.build)
        record.update(bundle=str(runner.original_app), native_sha256=c.sha(native))
        record['macho'][0]['sha256'] = record['native_sha256']
        for name, value in [('build.json', record), ('original-runtime.json', self.before),
                            ('source-before.json', self.source_before), ('runtime-copy-plan.json', self.plan),
                            ('protected-input-witness.json', self.protected())]:
            runner.write(runner.work / name, value)
        return record

    def summary(self, runner):
        runner.work.mkdir(exist_ok=True)
        if not (runner.work / 'build.json').exists():
            runner.write(runner.work / 'build.json', {**self.build, 'bundle': str(runner.original_app)})
        observations = []
        for index, app in enumerate((runner.original_app, runner.relocated_app)):
            profile = runner.work / ('run-profile-%d' % index)
            profile.mkdir()
            report = {'schema': 1, 'status': 'observed', 'version': '9.3', 'os': 'macosx', 'gc': 'cs',
                      'identity': {'pid': 101 + index, 'running_pid': 101 + index, 'same_running_application': True,
                                   'process_image_path': str(app / 'Contents/MacOS/ProbeNative'),
                                   'main_bundle_path': str(app), 'running_bundle_path': str(app),
                                   'main_bundle_identifier': s.BUNDLE_ID, 'running_bundle_identifier': s.BUNDLE_ID},
                      'child': {'schema': 1, 'status': 'observed', 'version': '9.3', 'gc': 'cs', 'pid': 201 + index}}
            classifications, closure = {}, {}
            for arm, observed in (('gui', report), ('child', report['child'])):
                images, snapshot, classifications[arm], closure[arm] = self.image_proof(app, arm)
                executable = images[0]
                console = str(app / 'Contents/Resources/runtime/bin/racket')
                def rec(path):
                    return {'absolute': path, 'raw': path, 'resolved': path, 'exists': True}
                observed.update(loaded_images=images, loaded_image_snapshot=snapshot,
                                paths={'system': {'run-file': rec(executable), 'exec-file': rec(console)}})
            runner.write(profile / 'result.json', report)
            runner.write(profile / 'post-launch-witness.json', {
                'schema': 1, 'bundle_unchanged': True, 'owned_process_group_cleanup_certain': True,
                'handler_before': self.handler, 'handler_after': self.handler,
                'bundle_before_digest': 'c' * 64, 'bundle_after_digest': 'c' * 64})
            observations.append({'profile': str(profile), 'verdict': {'status': 'path-and-identity-observation-validated',
                                                                     'bundle': str(app), 'profile': str(profile),
                                                                     'loaded_image_classifications': classifications},
                                 'report': report, 'bundle_inventory_digest': 'c' * 64,
                                 'active_non_system_dylib_closure': closure})
        return {'schema': 1, 'status': 'bounded-path-probe-passed', 'observations': observations,
                'original_runtime_present': True, 'recorded_original_runtime_absent': False,
                'clean_destination_tested': False, 'full_distribution_acceptance': False,
                'initially_unset_handler_tested': False, 'unresolved_static_loader_context': []}

    def test_exact37_file_freeze(self):
        self.assertEqual(len(c.frozen_sources(EXP)), 36)
        self.assertEqual(c.sha(EXP / 'MANIFEST.json'), c.FREEZE_PIN)

    def test_manifest_tamper_refused(self):
        source = self.path / 'source'
        shutil.copytree(EXP, source)
        path = source / 'README.md'
        path.chmod(0o600)
        path.write_text(path.read_text() + '\nmutation')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            c.frozen_sources(source)

    def test_extra_file_and_source_symlink_refused(self):
        source = self.path / 'source'
        shutil.copytree(EXP, source)
        source.chmod(0o700)
        extra = source / 'extra'
        extra.write_text('not in freeze')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.frozen_sources(source)
        extra.unlink()
        extra.symlink_to('README.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            c.frozen_sources(source)

    def test_inventory_detects_mtime_mode_bytes_and_symlink(self):
        file = self.runtime / 'binary'
        os.utime(file, ns=(file.stat().st_atime_ns, file.stat().st_mtime_ns + 1234))
        self.assertEqual([r['path'] for r in c.changes(self.before, c.inventory(self.runtime))], ['binary'])
        file.chmod(0o700)
        file.write_bytes(b'changed bytes')
        (self.runtime / 'alias').symlink_to('binary')
        after = c.inventory(self.runtime)
        self.assertEqual(after['alias']['target'], 'binary')
        self.assertEqual(after['binary']['mode'], 0o700)
        self.assertEqual(set(r['path'] for r in c.changes(self.before, after)), {'.', 'alias', 'binary'})

    def test_all_changed_rows_kept(self):
        self.assertEqual(len(c.changes({str(i): {'v': i} for i in range(500)}, {})), 500)

    def test_audit_matches_independent_original(self):
        self.assertEqual(c.validate_audit(self.audit, self.before), self.digest)
        for field, value in [('schema', True), ('inventory_digest', '0' * 64), ('inventory', {}), ('macho', [])]:
            bad = copy.deepcopy(self.audit)
            bad[field] = value
            with self.assertRaises(ValueError):
                c.validate_audit(bad, self.before)

    def test_build_schema_signature_original_and_baseline(self):
        self.assertFalse(c.validate_build(self.build, self.runtime, self.digest, self.handler))
        for field, value in [('schema', True), ('status', 'bounded-path-probe-passed'),
                             ('manual_signing_or_security_changes', True), ('intrinsic_generator_ad_hoc_signing', False),
                             ('original_runtime_digest', '0' * 64), ('handler_baseline', {}), ('macho', [])]:
            bad = copy.deepcopy(self.build)
            bad[field] = value
            with self.assertRaises(ValueError):
                c.validate_build(bad, self.runtime, self.digest, self.handler)

    def test_fixed_exclusion_full_manifest(self):
        self.assertEqual(c.validate_copy_plan(self.plan, self.before, self.build), self.retained)
        self.assertEqual(set(self.plan['excluded_entries']), {'DrRacket.app', 'DrRacket.app/claim'})
        self.assertEqual(set(self.retained), {'.', 'binary'})

    def test_no_other_exclusion_or_missing_rows_allowed(self):
        for key, value in [('excluded_path', 'Other.app'), ('excluded_entries', {}), ('excluded_entry_count', 1),
                           ('retained_inventory_digest', '0' * 64), ('original_inventory_digest', '0' * 64), ('schema', True)]:
            bad = copy.deepcopy(self.plan)
            bad[key] = value
            with self.assertRaises(ValueError):
                c.validate_copy_plan(bad, self.before, self.build)

    def test_exclusion_alias_or_case_conflict_refused(self):
        for extra in ({'drracket.APP': {'kind': 'directory'}}, {'DrRacket.app': {'kind': 'link', 'target': 'other'}}):
            with self.assertRaises(ValueError):
                c.validate_copy_plan(self.plan, {**self.before, **extra}, self.build)

    def test_empty_document_or_uti_declaration_blocks(self):
        for key in c.CLAIMS:
            bad = copy.deepcopy(self.build)
            bad.update(nested_apps=[{**self.claims[0], 'declarations': {key: []}}], native_launch_blocked_by_declarations=True)
            with self.assertRaisesRegex(ValueError, 'block all'):
                c.launch_gate(bad)

    def test_pending_loader_context_blocks(self):
        bad = {**self.build, 'static_loader_context_pending': [{'dependency': '@rpath/missing'}],
               'native_launch_blocked_by_loader_context': True}
        with self.assertRaisesRegex(ValueError, 'block all'):
            c.launch_gate(bad)

    def test_inconsistent_or_nonboolean_block_flags_refused(self):
        for field in ('native_launch_blocked_by_declarations', 'native_launch_blocked_by_loader_context'):
            for value in (True, 0, None, 'false'):
                with self.assertRaises(ValueError):
                    c.launch_gate({**self.build, field: value})

    def test_protected_witness_exact_boolean_and_digests(self):
        c.protected_witness(self.protected(), self.before, self.source_before)
        for field, value in [('schema', True), ('original_runtime_unchanged', 1), ('source_unchanged', False),
                             ('source_after', '0' * 64), ('original_runtime_before', '0' * 64)]:
            with self.assertRaises(ValueError):
                c.protected_witness({**self.protected(), field: value}, self.before, self.source_before)

    def test_summary_two_actual_locations(self):
        runner = self.runner()
        summary = self.summary(runner)
        c.validate_summary(summary, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_summary_missing_false_or_extra_observations_refused(self):
        runner = self.runner()
        summary = self.summary(runner)
        for field, value in [('schema', True), ('status', 'assembled-not-launched'), ('clean_destination_tested', True),
                             ('original_runtime_present', False), ('full_distribution_acceptance', True),
                             ('recorded_original_runtime_absent', True), ('initially_unset_handler_tested', True),
                             ('unresolved_static_loader_context', ['missing']), ('observations', summary['observations'][:1])]:
            with self.assertRaises(ValueError):
                c.validate_summary({**summary, field: value}, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_summary_wrong_identity_or_console_child_refused(self):
        runner = self.runner()
        summary = self.summary(runner)
        for group, field, value in [('identity', 'pid', True), ('identity', 'running_pid', 999),
                                     ('identity', 'process_image_path', '/wrong'), ('identity', 'main_bundle_path', '/wrong'),
                                     ('identity', 'main_bundle_identifier', 'org.racket'), ('identity', 'same_running_application', False),
                                     ('child', 'pid', 101), ('child', 'version', '9.2')]:
            bad = copy.deepcopy(summary)
            bad['observations'][0]['report'][group][field] = value
            with self.assertRaises(ValueError):
                c.validate_summary(bad, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_summary_raw_report_disagreement_refused(self):
        runner = self.runner()
        summary = self.summary(runner)
        (runner.work / 'run-profile-0/result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'differs from summary'):
            c.validate_summary(summary, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_summary_unknown_cleanup_or_changed_handler_refused(self):
        runner = self.runner()
        summary = self.summary(runner)
        path = runner.work / 'run-profile-0/post-launch-witness.json'
        original = json.loads(path.read_text())
        for field, value in [('owned_process_group_cleanup_certain', False), ('bundle_unchanged', False),
                             ('handler_after', {}), ('bundle_after_digest', '0' * 64)]:
            path.write_text(json.dumps({**original, field: value}))
            with self.assertRaises(ValueError):
                c.validate_summary(summary, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_missing_or_linked_original_leaf_preserves_final_evidence_path(self):
        stock = self.runtime / 'bin/racket'
        self.assertEqual(c.selected_runtime(stock, self.path, True), self.runtime)
        shutil.rmtree(self.runtime)
        self.assertEqual(c.selected_runtime(stock, self.path, False), self.runtime)
        with self.assertRaises(ValueError):
            c.selected_runtime(stock, self.path, True)
        self.runtime.symlink_to(EXP, target_is_directory=True)
        self.assertEqual(c.selected_runtime(stock, self.path, False), self.runtime)
        with self.assertRaises(ValueError):
            c.inventory(self.runtime)
        with self.assertRaises(ValueError):
            c.selected_runtime(stock, self.path, True)

    def test_changed_original_blocks_handler_before_any_source_import(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        (self.runtime / 'binary').write_bytes(b'changed original')
        with mock.patch.object(runner, 'source_module') as source:
            with self.assertRaisesRegex(ValueError, 'Changed original inputs'):
                runner.handler('handler-after-probe')
        source.assert_not_called()
        self.assertEqual(runner.state['native_state'], 'unresolved-handler-after-probe')

    def test_missing_original_still_collects_source_witness(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        shutil.rmtree(self.runtime)
        self.assertFalse(runner.filesystem_witness())
        self.assertIn('error', runner.read(runner.reports / 'original-witness.json'))
        self.assertTrue(runner.read(runner.reports / 'source-witness.json')['unchanged'])

    def test_foreign_runtime_symlink_is_never_traversed_or_executed(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        foreign = self.path / 'foreign-unrelated-root'
        foreign.mkdir()
        (foreign / 'secret').write_bytes(b'never read')
        shutil.rmtree(self.runtime)
        self.runtime.symlink_to(foreign, target_is_directory=True)
        original_sha = c.sha
        def sha(path):
            self.assertFalse(Path(path).is_relative_to(foreign), 'Foreign root traversal')
            self.assertFalse(Path(path).is_relative_to(self.runtime), 'Changed original root traversal')
            return original_sha(path)
        with mock.patch.object(c, 'sha', side_effect=sha), mock.patch.object(runner, 'source_module') as source:
            with self.assertRaises(ValueError):
                runner.handler('handler-after-probe')
            self.assertFalse(runner.filesystem_witness())
        source.assert_not_called()
        self.assertTrue(runner.read(runner.reports / 'source-witness.json')['unchanged'])
        self.assertIn('error', runner.read(runner.reports / 'original-witness.json'))

    def test_linked_source_blocks_handler_but_preserves_original_witness(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        runner.exp = self.path / 'changed-source'
        runner.exp.symlink_to(EXP, target_is_directory=True)
        with mock.patch.object(runner, 'source_module') as source:
            with self.assertRaises(ValueError):
                runner.handler('handler-after-probe')
            self.assertFalse(runner.filesystem_witness())
        source.assert_not_called()
        self.assertTrue(runner.read(runner.reports / 'original-witness.json')['unchanged'])
        self.assertIn('error', runner.read(runner.reports / 'source-witness.json'))

    def test_canonical_alias_path_comparison(self):
        alias = self.path / "Alias λ's"
        alias.symlink_to(self.runtime, target_is_directory=True)
        self.assertTrue(c.same_path(str(alias / 'binary'), self.runtime / 'binary'))
        self.assertFalse(c.same_path('relative/binary', self.runtime / 'binary'))
        self.assertFalse(c.same_path(None, self.runtime))

    def test_orchestration_exact_order_and_cli(self):
        runner = self.runner()
        calls = []
        def handler(label):
            self.assertEqual(runner.read(runner.proof / 'original-before.json'), self.before)
            self.assertEqual(runner.read(runner.proof / 'source-before.json'), self.source_before)
            calls.append(label)
            return self.handler
        def command(label, argv, native=False):
            calls.append(label)
            if label == 'portable-source-tests':
                self.assertEqual(argv[1:], ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
                self.assertFalse(native)
            elif label == 'audit-runtime':
                self.assertEqual(argv[2:], ['audit-runtime', self.runtime, '--output', runner.proof / 'runtime-audit.json'])
                runner.write(runner.proof / 'runtime-audit.json', self.audit)
            elif label == 'build':
                self.assertEqual(argv[2:], ['build', '--runtime', self.runtime, '--work', runner.work,
                                          '--expected-runtime-digest', self.digest])
                self.assertTrue(native)
                self.build_files(runner)
            elif label == 'native-probe':
                self.assertEqual(argv[2:], ['run', '--build-record', runner.work / 'build.json', '--renamed', runner.relocated_app])
                self.assertTrue(native)
                self.assertEqual(runner.state['native_state'], 'safe')
                self.assertTrue(runner.state['run_attempted'])
                runner.original_app.rename(runner.relocated_app)
                runner.write(runner.work / 'native-summary.json', self.summary(runner))
                runner.write(runner.work / 'launch-protected-input-witness.json', self.protected())
            else:
                self.fail('Unexpected command ' + label)
        source = mock.Mock()
        source.check_dependency_paths.return_value = []
        with mock.patch.object(runner, 'handler', side_effect=handler), mock.patch.object(runner, 'command', side_effect=command), \
                mock.patch.object(runner, 'source_module', return_value=source):
            runner.run()
        self.assertEqual(calls, ['handler-before-probe', 'portable-source-tests', 'audit-runtime', 'build', 'native-probe'])
        self.assertTrue(runner.state['observed'])
        self.assertEqual(runner.state['native_state'], 'safe')

    def run_until_build(self, runner, build):
        def command(label, argv, native=False):
            if label == 'audit-runtime':
                runner.write(runner.proof / 'runtime-audit.json', self.audit)
            elif label == 'build':
                self.build_files(runner, build)
            elif label == 'native-probe':
                self.fail('Rejected app must never launch')
        return command

    def test_rejected_claims_never_invoke_run(self):
        runner = self.runner()
        build = {**self.build, 'nested_apps': self.claims, 'native_launch_blocked_by_declarations': True}
        with mock.patch.object(runner, 'handler', return_value=self.handler), \
                mock.patch.object(runner, 'command', side_effect=self.run_until_build(runner, build)), \
                mock.patch.object(runner, 'source_module') as source:
            with self.assertRaisesRegex(ValueError, 'block all'):
                runner.run()
            source.assert_not_called()
        self.assertFalse(runner.state['run_attempted'])

    def test_rejected_loader_contexts_never_invoke_run(self):
        runner = self.runner()
        build = {**self.build, 'static_loader_context_pending': ['unresolved'], 'native_launch_blocked_by_loader_context': True}
        with mock.patch.object(runner, 'handler', return_value=self.handler), \
                mock.patch.object(runner, 'command', side_effect=self.run_until_build(runner, build)):
            with self.assertRaisesRegex(ValueError, 'block all'):
                runner.run()
        self.assertFalse(runner.state['run_attempted'])

    def test_pending_lease_durable_before_subprocess(self):
        runner = self.runner()
        def execute(*args, **kwargs):
            self.assertEqual(json.loads(runner.state_file.read_text())['native_state'], 'pending-build')
            self.assertFalse(runner.state_file.with_suffix('.pending').exists())
            self.assertIs(kwargs['stdin'], subprocess.DEVNULL)
            return mock.Mock(returncode=0)
        with mock.patch.object(a.subprocess, 'run', side_effect=execute):
            runner.command('build', ['mock-only'], native=True)
        self.assertEqual(runner.state['native_state'], 'unresolved-build')

    def test_pending_lease_saved_before_handler_source_loading(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        def loading():
            self.assertEqual(json.loads(runner.state_file.read_text())['native_state'], 'pending-handler-test')
            raise RuntimeError('source load failed')
        with mock.patch.object(runner, 'source_module', side_effect=loading):
            with self.assertRaises(RuntimeError):
                runner.handler('handler-test')
        self.assertEqual(runner.state['native_state'], 'unresolved-handler-test')

    def test_failed_durable_save_prevents_spawn(self):
        runner = self.runner()
        with mock.patch.object(runner, 'save', side_effect=OSError('durability failed')), mock.patch.object(a.subprocess, 'run') as run:
            with self.assertRaises(OSError):
                runner.command('build', ['mock-only'], native=True)
        run.assert_not_called()

    def test_interrupted_state_write_blocks_new_native_work(self):
        runner = self.runner()
        runner.state_file.with_suffix('.pending').write_text('interrupted')
        with mock.patch.object(a.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Unresolved state write'):
                runner.command('build', ['mock-only'], native=True)
        run.assert_not_called()

    def test_failed_build_blocks_every_later_native_call(self):
        runner = self.runner()
        with mock.patch.object(a.subprocess, 'run', return_value=mock.Mock(returncode=1)):
            with self.assertRaises(ValueError):
                runner.command('build', ['mock-only'], native=True)
        self.assertEqual(runner.state['native_state'], 'unresolved-build')
        self.assertTrue((runner.proof / 'build/command.json').is_file())
        with mock.patch.object(a.subprocess, 'run') as run, mock.patch.object(runner, 'source_module') as source:
            with self.assertRaises(ValueError):
                runner.command('native-probe', ['mock-only'], native=True)
            with self.assertRaises(ValueError):
                runner.handler('handler-after-probe')
        run.assert_not_called()
        source.assert_not_called()

    def test_spawn_exception_blocks_later_queries(self):
        runner = self.runner()
        with mock.patch.object(a.subprocess, 'run', side_effect=OSError('spawn uncertainty')):
            with self.assertRaises(OSError):
                runner.command('native-probe', ['mock-only'], native=True)
        self.assertEqual(runner.state['native_state'], 'unresolved-native-probe')
        self.assertIsNone(runner.read(runner.proof / 'native-probe/command.json')['exit_code'])

    def test_interruption_preserves_unresolved_receipt(self):
        runner = self.runner()
        with mock.patch.object(a.subprocess, 'run', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                runner.command('native-probe', ['mock-only'], native=True)
        self.assertEqual(json.loads(runner.state_file.read_text())['native_state'], 'unresolved-native-probe')

    def test_verify_uncertain_state_collects_filesystem_without_handler(self):
        runner = self.runner()
        runner.state['native_state'] = 'pending-native-probe'
        with mock.patch.object(runner, 'handler') as handler, mock.patch.object(runner, 'filesystem_witness', return_value=True) as fs, \
                mock.patch.object(runner, 'collect_evidence', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                runner.verify()
        handler.assert_not_called()
        fs.assert_called_once()
        self.assertFalse(runner.read(runner.reports / 'result.json')['probe_complete'])

    def test_filesystem_source_failure_does_not_skip_runtime(self):
        runner = self.runner()
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.exp = self.path / 'nonexistent-source'
        self.assertFalse(runner.filesystem_witness())
        self.assertTrue(runner.read(runner.reports / 'original-witness.json')['unchanged'])
        self.assertIn('error', runner.read(runner.reports / 'source-witness.json'))

    def test_source_and_retained_mutations_report_all_changes(self):
        runner = self.runner()
        self.build_files(runner)
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        runner.write(runner.proof / 'retained-before.json', self.retained)
        target = runner.original_app / 'Contents/Resources/runtime/binary'
        target.write_bytes(b'changed retained')
        self.assertFalse(runner.filesystem_witness())
        report = runner.read(runner.reports / 'retained-witness.json')
        self.assertEqual([r['path'] for r in report['all_changed_entries']], ['binary'])
        self.assertTrue(runner.read(runner.reports / 'source-witness.json')['unchanged'])

    def test_partial_invalid_json_and_utf8_transport_losslessly(self):
        runner = self.runner()
        raw = b'{"partial":"\\u1234",broken\xff'
        (runner.proof / 'runtime-audit.json').write_bytes(raw)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.collect_evidence()
        self.assertTrue(runner.state['errors'])
        rows = decoder.decode(output.getvalue(), self.path / 'decoded')
        recovered = [Path(row['path']).read_bytes() for row in rows if Path(row['path']).name == 'runtime-audit.json']
        self.assertEqual(recovered, [raw])

    def test_full_exclusion_and_native_failure_witness_transport(self):
        runner = self.runner()
        runner.work.mkdir()
        runner.write(runner.work / 'runtime-copy-plan.json', self.plan)
        profile = runner.work / 'run-profile-0'
        profile.mkdir()
        raw = b'(-X did not restore links)\n\xff'
        (profile / 'startup-minimal.rktd').write_bytes(raw)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.collect_evidence()
        rows = decoder.decode(output.getvalue(), self.path / 'decoded')
        paths = {Path(row['path']).name: Path(row['path']) for row in rows}
        self.assertEqual(paths['startup-minimal.rktd'].read_bytes(), raw)
        self.assertEqual(json.loads(paths['runtime-copy-plan.json'].read_text()), self.plan)

    def test_metadata_retains_every_audit_row_and_full_report_digest(self):
        runner = self.runner()
        runner.write(runner.proof / 'runtime-audit.json', self.audit)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.collect_evidence()
        rows = decoder.decode(output.getvalue(), self.path / 'decoded')
        path = next(Path(row['path']) for row in rows if Path(row['path']).name == 'runtime-audit-metadata.json')
        value = json.loads(path.read_text())
        self.assertEqual(value['nested_apps'], self.claims)
        self.assertEqual(value['macho'], self.audit['macho'])
        self.assertNotIn('inventory', value)
        self.assertEqual(value['raw_full_report']['sha256'], c.sha(runner.proof / 'runtime-audit.json'))
        self.assertEqual(value['raw_full_report']['entry_count'], len(self.before))

    def test_large_unicode_binary_roundtrip_and_truncation_refusal(self):
        path = self.path / 'stdout.txt'
        raw = json.dumps({'scalar': 'λ' * 100000, 'rows': list(range(10000))}).encode() + b'\xff'
        path.write_bytes(raw)
        folder = self.path / 'evidence-large'
        folder.mkdir()
        wrapped = folder / 'supervisor.json'
        wrapped.write_text(json.dumps(c.wrap_bytes(path)))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            emitter.emit(wrapped)
        self.assertTrue(all(len(line.encode()) < 60000 for line in output.getvalue().splitlines()))
        rows = decoder.decode(output.getvalue(), self.path / 'decoded')
        self.assertEqual(Path(rows[0]['path']).read_bytes(), raw)
        with self.assertRaises(AssertionError):
            decoder.decode('\n'.join(output.getvalue().splitlines()[:-1]), self.path / 'truncated')

    def test_missing_success_evidence_or_unsafe_file_fails_transport(self):
        runner = self.runner()
        runner.state['observed'] = True
        (runner.proof / 'source-before.json').symlink_to(self.runtime / 'binary')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(runner.collect_evidence())
        errors = runner.read(runner.reports / 'evidence-errors.json')
        self.assertTrue(any('Unsafe diagnostic file' in line for line in errors))
        self.assertTrue(any('Mandatory diagnostic missing' in line for line in errors))

    def test_oversized_diagnostic_fails_instead_of_truncating(self):
        path = self.path / 'too-large.txt'
        with path.open('wb') as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, 'fail rather than truncate'):
            c.wrap_bytes(path)

    def test_verdict_requires_exact_true_for_every_gate(self):
        self.assertTrue(c.verdict(True, True, True, True, True, [])['probe_complete'])
        for index in range(5):
            for value in (False, None, 1, 'true'):
                args = [True] * 5 + [[]]
                args[index] = value
                self.assertFalse(c.verdict(*args)['probe_complete'])
        self.assertFalse(c.verdict(True, True, True, True, True, ['failure'])['probe_complete'])
        result = c.verdict(True, True, True, True, True, [])
        self.assertFalse(result['clean_destination_tested'])
        self.assertFalse(result['full_distribution_acceptance'])
        self.assertFalse(result['original_preferences_file_separately_observed'])

    def test_public_arch_event_branch_guards(self):
        event = self.path / 'event.json'
        event.write_text(json.dumps({'repository': {'full_name': 'alikatgh/openracket', 'private': False, 'visibility': 'public'}}))
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
               'GITHUB_REF': 'refs/heads/prototype/retained-drracket', 'GITHUB_EVENT_NAME': 'push', 'GITHUB_EVENT_PATH': str(event)}
        c.guard(env, 'Darwin', 'arm64')
        for key in ('GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_REF', 'GITHUB_EVENT_NAME'):
            with self.assertRaises(ValueError):
                c.guard({**env, key: 'wrong'}, 'Darwin', 'arm64')
        for system, machine in [('Linux', 'x86_64'), ('Darwin', 'x86_64')]:
            with self.assertRaises(ValueError):
                c.guard(env, system, machine)
        event.write_text(json.dumps({'repository': {'full_name': 'alikatgh/openracket', 'private': True, 'visibility': 'private'}}))
        with self.assertRaises(ValueError):
            c.guard(env, 'Darwin', 'arm64')

    def test_index_emitter_failure_preserves_self_identifying_raw_and_error_tail(self):
        runner = self.runner()
        runner.work.mkdir()
        for index in range(2):
            profile = runner.work / ('run-profile-%d' % index)
            profile.mkdir()
            runner.write(profile / 'result.json', {'location': index})
        actual_module = a.module
        attempted = []
        def load(name, path):
            if name != 'isolation_existing_emitter':
                return actual_module(name, path)
            def emit(path):
                attempted.append(path.parent.name)
                if path.parent.name == 'evidence-index':
                    raise OSError('synthetic index failure')
                emitter.emit(path)
            return mock.Mock(emit=emit)
        output = io.StringIO()
        with mock.patch.object(a, 'module', side_effect=load), contextlib.redirect_stdout(output):
            self.assertFalse(runner.collect_evidence())
        self.assertIn('evidence-index', attempted)
        self.assertIn('evidence-errors', attempted)
        rows = decoder.decode(output.getvalue(), self.path / 'decoded')
        reports = [row for row in rows if Path(row['path']).name == 'result.json']
        self.assertEqual({row['source_relative_path'] for row in reports},
                         {"proof/Build Unicode λ's Probe/run-profile-0/result.json",
                          "proof/Build Unicode λ's Probe/run-profile-1/result.json"})
        errors = next(Path(row['path']) for row in rows if Path(row['path']).name == 'evidence-errors.json')
        self.assertIn('synthetic index failure', errors.read_text())

    def test_every_tail_failure_still_attempts_final_result(self):
        runner = self.runner()
        runner.state['native_state'] = 'unresolved-build'
        actual_module = a.module
        attempted = []
        def load(name, path):
            if name not in ('isolation_existing_emitter', 'isolation_result_emitter'):
                return actual_module(name, path)
            def emit(path):
                attempted.append(path.parent.name)
                if path.parent.name in ('evidence-index', 'evidence-errors'):
                    raise OSError('synthetic tail failure')
                emitter.emit(path)
            return mock.Mock(emit=emit)
        with mock.patch.object(a, 'module', side_effect=load), mock.patch.object(runner, 'filesystem_witness', return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                runner.verify()
        self.assertIn('evidence-index', attempted)
        self.assertIn('evidence-errors', attempted)
        self.assertIn('evidence-result', attempted)
        self.assertFalse(runner.read(runner.reports / 'result.json')['probe_complete'])

    def test_final_result_emitter_failure_keeps_durable_result_red(self):
        runner = self.runner()
        runner.state['assembled'] = runner.state['observed'] = True
        runner.write(runner.proof / 'handler-before-probe.json', self.handler)
        actual_module = a.module
        def load(name, path):
            if name == 'isolation_result_emitter':
                return mock.Mock(emit=mock.Mock(side_effect=OSError('synthetic final failure')))
            return actual_module(name, path)
        with mock.patch.object(a, 'module', side_effect=load), mock.patch.object(runner, 'handler', return_value=self.handler), \
                mock.patch.object(runner, 'filesystem_witness', return_value=True), \
                mock.patch.object(runner, 'collect_evidence', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                runner.verify()
        result = runner.read(runner.reports / 'result.json')
        self.assertFalse(result['probe_complete'])
        self.assertFalse(result['complete_evidence_transport'])
        self.assertIn('synthetic final failure', result['errors'][-1])

    def test_interrupted_write_verify_collects_filesystem_and_evidence_without_native(self):
        runner = self.runner()
        runner.state_file.with_suffix('.pending').write_text('partial durable lease')
        runner.write(runner.proof / 'original-before.json', self.before)
        runner.write(runner.proof / 'source-before.json', self.source_before)
        with mock.patch.object(runner, 'handler') as handler, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                runner.verify()
        handler.assert_not_called()
        self.assertTrue(runner.read(runner.reports / 'original-witness.json')['unchanged'])
        self.assertTrue(runner.read(runner.reports / 'source-witness.json')['unchanged'])
        self.assertTrue((runner.reports / 'evidence-result/supervisor.json').is_file())
        self.assertEqual(runner.read(runner.reports / 'result.json')['native_state'], 'unresolved-state-write')

    def test_decoder_rejects_untrusted_source_relative_paths(self):
        path = self.path / 'fixture.txt'
        path.write_bytes(b'fixture')
        for unsafe in ('/absolute/file', '../escape', 'a/../escape', '', './relative'):
            wrapped = c.wrap_bytes(path)
            wrapped['source_relative_path'] = unsafe
            with self.assertRaises(ValueError):
                decoder.unwrap(wrapped)

    def test_release_checks_frozen_inputs_before_any_subprocess(self):
        release = module('isolation_release_gate_test', HERE / 'check-launcher-isolation-release.py')
        with mock.patch.object(release, 'verify_inputs', side_effect=ValueError('frozen input mismatch')), \
                mock.patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'frozen input mismatch'):
                release.main()
        run.assert_not_called()

    def recorded_fixture(self):
        runner = self.runner()
        summary = self.summary(runner)
        build = runner.read(runner.work / 'build.json')
        posts = [runner.read(runner.work / ('run-profile-%d' % i) / 'post-launch-witness.json') for i in range(2)]
        def validate(value=None, build_record=None, post_records=None):
            value = summary if value is None else value
            reports = [copy.deepcopy(row['report']) for row in value['observations']]
            return c.validate_summary_recorded(value, runner.original_app, runner.relocated_app, runner.work, self.handler,
                                               build if build_record is None else build_record, reports,
                                               posts if post_records is None else post_records)
        return runner, summary, build, posts, validate

    def test_recorded_validator_never_touches_historical_filesystem(self):
        runner, summary, build, posts, validate = self.recorded_fixture()
        self.assertFalse(runner.original_app.exists())
        self.assertFalse(runner.relocated_app.exists())
        with mock.patch.object(Path, 'resolve', side_effect=AssertionError('historical resolution')), \
                mock.patch.object(Path, 'stat', side_effect=AssertionError('historical stat')), \
                mock.patch.object(Path, 'open', side_effect=AssertionError('historical read')):
            validate()

    def test_frozen_classifier_producer_consumed_after_real_bundle_rename(self):
        runner, value, build, posts, validate = self.recorded_fixture()
        for row in build['macho']:
            file = runner.original_app / row['path']
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'synthetic file for frozen classifier only')
        for index, app in enumerate((runner.original_app, runner.relocated_app)):
            if index:
                runner.original_app.rename(runner.relocated_app)
            row = value['observations'][index]
            for arm, observed in (('gui', row['report']), ('child', row['report']['child'])):
                # Remove the synthetic OS-file row; cache membership is typed
                # fixture evidence, and all non-cache bundle files genuinely exist.
                observed['loaded_images'].pop()
                observed['loaded_image_snapshot']['records'].pop()
                observed['loaded_image_snapshot']['count'] -= 1
                produced = s.classify_loaded_images(observed['loaded_images'], observed['loaded_image_snapshot'], app)
                row['verdict']['loaded_image_classifications'][arm] = produced
            profile = runner.work / ('run-profile-%d' % index)
            (profile / 'result.json').write_text(json.dumps(row['report']))
        self.assertFalse(runner.original_app.exists())
        self.assertTrue(runner.relocated_app.is_dir())
        with mock.patch.object(Path, 'resolve', side_effect=AssertionError('historical resolution')), \
                mock.patch.object(Path, 'stat', side_effect=AssertionError('historical stat')), \
                mock.patch.object(s, 'classify_loaded_images', side_effect=AssertionError('launch-time classifier rerun')):
            c.validate_summary(value, runner.original_app, runner.relocated_app, runner.work, self.handler)

    def test_new_verdict_field_is_required_and_unknown_fields_refused(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('missing', 'extra', 'wrong-arm', 'extra-arm'):
            bad = copy.deepcopy(value); verdict = bad['observations'][0]['verdict']
            if mutation == 'missing': del verdict['loaded_image_classifications']
            elif mutation == 'extra': verdict['unknown'] = True
            elif mutation == 'wrong-arm': verdict['loaded_image_classifications'].pop('child')
            else: verdict['loaded_image_classifications']['other'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_classification_unknown_missing_duplicate_and_reordered_rows_refused(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('unknown', 'missing-key', 'extra-key', 'missing-row', 'duplicate-row', 'reorder'):
            bad = copy.deepcopy(value); rows = bad['observations'][0]['verdict']['loaded_image_classifications']['gui']
            if mutation == 'unknown': rows[0]['kind'] = 'trusted-file'
            elif mutation == 'missing-key': del rows[0]['raw']
            elif mutation == 'extra-key': rows[0]['trusted'] = True
            elif mutation == 'missing-row': rows.pop()
            elif mutation == 'duplicate-row': rows[1] = copy.deepcopy(rows[0])
            else: rows[0], rows[1] = rows[1], rows[0]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_classification_swapped_processes_and_locations_refused(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('processes', 'locations'):
            bad = copy.deepcopy(value)
            if mutation == 'processes':
                rows = bad['observations'][0]['verdict']['loaded_image_classifications']
                rows['gui'], rows['child'] = rows['child'], rows['gui']
            else:
                first, second = bad['observations']
                first['verdict']['loaded_image_classifications'], second['verdict']['loaded_image_classifications'] = \
                    second['verdict']['loaded_image_classifications'], first['verdict']['loaded_image_classifications']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_classification_index_bool_integer_and_raw_binding(self):
        _, value, _, _, validate = self.recorded_fixture()
        for key, replacement in (('witness_index', True), ('witness_index', 0.0), ('witness_index', 999), ('raw', '/usr/lib/other')):
            bad = copy.deepcopy(value)
            bad['observations'][0]['verdict']['loaded_image_classifications']['gui'][0][key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(ValueError): validate(bad)

    def test_recorded_snapshot_shape_count_and_stability_are_exact(self):
        _, value, _, _, validate = self.recorded_fixture()
        for key, replacement in (('schema', True), ('count', True), ('count', 999), ('stable', 1), ('stable', False),
                                 ('method', 'guessed'), ('records', []), ('unknown', True)):
            bad = copy.deepcopy(value)
            bad['observations'][0]['report']['loaded_image_snapshot'][key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(ValueError): validate(bad)

    def test_recorded_header_missing_extra_duplicate_and_invalid_addresses(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('missing', 'extra', 'duplicate-address', 'zero-address', 'bad-address'):
            bad = copy.deepcopy(value); rows = bad['observations'][0]['report']['loaded_image_snapshot']['records']
            if mutation == 'missing': del rows[0]['header_address']
            elif mutation == 'extra': rows[0]['trusted'] = True
            elif mutation == 'duplicate-address': rows[1]['header_address'] = rows[0]['header_address']
            elif mutation == 'zero-address': rows[0]['header_address'] = '0'
            else: rows[0]['header_address'] = '0x1234'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_recorded_header_index_name_uint_and_arm_architecture(self):
        _, value, _, _, validate = self.recorded_fixture()
        for key, replacement in (('index', True), ('index', 99), ('raw', '/wrong'), ('magic', 0xFEEDFACE),
                                 ('cpu_type', 0x01000007), ('cpu_type', True), ('flags', -1), ('flags', 2**32),
                                 ('file_type', 2.0), ('shared_cache_contains_path', 1)):
            bad = copy.deepcopy(value)
            bad['observations'][0]['report']['loaded_image_snapshot']['records'][0][key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(ValueError): validate(bad)

    def test_shared_cache_requires_header_flag_dylib_query_and_normalized_os_name(self):
        _, value, _, _, validate = self.recorded_fixture()
        for key, replacement in (('flags', 0), ('file_type', 2), ('shared_cache_contains_path', False)):
            bad = copy.deepcopy(value)
            bad['observations'][0]['report']['loaded_image_snapshot']['records'][2][key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'shared-cache'): validate(bad)
        for raw in ('/usr/library/forged', '/System/LibraryExtra/forged', '/System/Library/../Library/forged',
                    '/System/Volumes/Preboot/Cryptexes/OS/System/Library/forged', '/tmp/forged', '/usr/lib//forged'):
            bad = copy.deepcopy(value); row = bad['observations'][0]
            row['report']['loaded_images'][2] = raw
            row['report']['loaded_image_snapshot']['records'][2]['raw'] = raw
            row['verdict']['loaded_image_classifications']['gui'][2]['raw'] = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError): validate(bad)

    def test_cache_file_kind_switch_and_fabricated_resolution_refused(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('cache-resolved', 'cache-as-file', 'file-as-cache'):
            bad = copy.deepcopy(value); rows = bad['observations'][0]['verdict']['loaded_image_classifications']['gui']
            if mutation == 'cache-resolved': rows[2]['resolved'] = rows[2]['raw']
            elif mutation == 'cache-as-file': rows[2].update(kind='os-file', resolved=rows[2]['raw'])
            else: rows[0].pop('resolved'); rows[0]['kind'] = 'os-shared-cache'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_recorded_file_path_escapes_case_alias_and_inventory_rebinding_refused(self):
        runner, value, _, _, validate = self.recorded_fixture()
        for raw in ('/tmp/outside', str(runner.relocated_app / 'Contents/MacOS/ProbeNative'),
                    str(runner.original_app / 'Contents/MacOS/probenative'),
                    str(runner.original_app / 'Contents/MacOS/../MacOS/ProbeNative')):
            bad = copy.deepcopy(value); row = bad['observations'][0]
            row['report']['loaded_images'][0] = raw
            row['report']['loaded_image_snapshot']['records'][0]['raw'] = raw
            row['verdict']['loaded_image_classifications']['gui'][0]['raw'] = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError): validate(bad)
        bad = copy.deepcopy(value)
        bad['observations'][0]['verdict']['loaded_image_classifications']['gui'][0]['resolved'] = str(runner.original_app / 'Contents/Resources/runtime/bin/racket')
        with self.assertRaisesRegex(ValueError, 'inventory identity'): validate(bad)

    def test_own_process_executable_must_exist_in_its_own_recorded_arm(self):
        _, value, _, _, validate = self.recorded_fixture()
        bad = copy.deepcopy(value); row = bad['observations'][0]
        for key in ('loaded_images',): row['report'][key].pop(0)
        row['report']['loaded_image_snapshot']['records'].pop(0)
        row['report']['loaded_image_snapshot']['count'] -= 1
        row['verdict']['loaded_image_classifications']['gui'].pop(0)
        for i, record in enumerate(row['report']['loaded_image_snapshot']['records']): record['index'] = i
        for i, record in enumerate(row['verdict']['loaded_image_classifications']['gui']): record['witness_index'] = i
        with self.assertRaisesRegex(ValueError, 'executable absent'): validate(bad)

    def test_recorded_executable_path_metadata_cannot_cross_process_or_location(self):
        _, value, _, _, validate = self.recorded_fixture()
        for arm, key in (('gui', 'run-file'), ('child', 'run-file'), ('gui', 'exec-file')):
            bad = copy.deepcopy(value); report = bad['observations'][0]['report']
            if arm == 'child': report = report['child']
            report['paths']['system'][key]['resolved'] = '/wrong/location'
            with self.subTest(arm=arm, key=key), self.assertRaisesRegex(ValueError, 'another process/location'): validate(bad)

    def test_recorded_macho_hash_missing_duplicate_cpu_and_unknown_fields(self):
        _, _, build, _, validate = self.recorded_fixture()
        for mutation in ('native-hash', 'missing-console', 'duplicate-path', 'extra-row-key', 'missing-arm', 'bool-arm'):
            bad = copy.deepcopy(build)
            if mutation == 'native-hash': bad['native_sha256'] = 'f' * 64
            elif mutation == 'missing-console': bad['macho'].pop(1)
            elif mutation == 'duplicate-path': bad['macho'].append(copy.deepcopy(bad['macho'][0]))
            elif mutation == 'extra-row-key': bad['macho'][0]['optional'] = True
            elif mutation == 'missing-arm': bad['macho'][0]['slices'][0]['cpu_type'] = 0x01000007
            else: bad['macho'][0]['slices'][0]['cpu_type'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(build_record=bad)

    def test_recorded_closure_requires_complete_inventory_bound_rows(self):
        _, value, _, _, validate = self.recorded_fixture()
        for mutation in ('missing', 'duplicate', 'reordered', 'wrong-image', 'wrong-dependency', 'system-bool', 'extra-key', 'escape', 'unmeasured'):
            bad = copy.deepcopy(value); rows = bad['observations'][0]['active_non_system_dylib_closure']['gui']
            if mutation == 'missing': rows.pop()
            elif mutation == 'duplicate': rows[1] = copy.deepcopy(rows[0])
            elif mutation == 'reordered': rows[0], rows[1] = rows[1], rows[0]
            elif mutation == 'wrong-image': rows[0]['image'] = '/wrong'
            elif mutation == 'wrong-dependency': rows[0]['dependency'] = '/usr/lib/guessed'
            elif mutation == 'system-bool': rows[1]['system'] = 1
            elif mutation == 'extra-key': rows[0]['trusted'] = True
            elif mutation == 'escape': rows[0]['resolved_candidates'] = ['/tmp/outside']
            else: rows[0]['resolved_candidates'] = ['/usr/lib/unmeasured']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(bad)

    def test_independent_raw_report_json_types_cannot_drift(self):
        runner, value, build, posts, validate = self.recorded_fixture()
        for replacement in (False, 0.0):
            reports = [copy.deepcopy(row['report']) for row in value['observations']]
            reports[0]['loaded_image_snapshot']['records'][0]['index'] = replacement
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, 'differs from summary'):
                c.validate_summary_recorded(value, runner.original_app, runner.relocated_app, runner.work,
                                            self.handler, build, reports, posts)
        bad = copy.deepcopy(build); bad['handler_baseline']['schema'] = True
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'): validate(build_record=bad)
        bad_posts = copy.deepcopy(posts); bad_posts[0]['handler_after']['schema'] = 1.0
        with self.assertRaises(ValueError): validate(post_records=bad_posts)

    def test_relative_dot_cannot_identify_inventory_image(self):
        _, _, build, _, validate = self.recorded_fixture()
        bad = copy.deepcopy(build); extra = copy.deepcopy(bad['macho'][0]); extra['path'] = '.'; bad['macho'].append(extra)
        with self.assertRaisesRegex(ValueError, 'Mach-O identity'): validate(build_record=bad)

    def test_closure_cannot_drop_one_of_two_valid_rpath_candidates(self):
        runner, value, build, posts, validate = self.recorded_fixture()
        build['macho'][0]['slices'][0]['dependencies'][0] = '@rpath/helper.dylib'
        build['macho'][0]['slices'][0]['rpaths'] = ['@executable_path/../Resources/runtime/lib', '@executable_path/../Resources/runtime/alternate']
        second_rel = 'Contents/Resources/runtime/alternate/helper.dylib'
        build['macho'].append({'path': second_rel, 'sha256': 'f' * 64,
                               'slices': [{'cpu_type': 0x0100000C, 'dependencies': [], 'rpaths': []}]})
        for row in value['observations']:
            app = Path(row['verdict']['bundle']); observed = row['report']; raw = str(app / second_rel)
            index = len(observed['loaded_images']); observed['loaded_images'].append(raw)
            observed['loaded_image_snapshot']['count'] += 1
            observed['loaded_image_snapshot']['records'].append({'index': index, 'raw': raw, 'header_address': 'f000',
                        'magic': 0xFEEDFACF, 'cpu_type': 0x0100000C, 'file_type': 6, 'flags': 0, 'shared_cache_contains_path': False})
            row['verdict']['loaded_image_classifications']['gui'].append({'raw': raw, 'kind': 'bundle-file', 'resolved': raw, 'witness_index': index})
            closure = row['active_non_system_dylib_closure']['gui'][0]
            closure['dependency'] = '@rpath/helper.dylib'
            closure['resolved_candidates'] = sorted([raw, str(app / 'Contents/Resources/runtime/lib/helper.dylib')])
        validate(value, build_record=build)
        value['observations'][0]['active_non_system_dylib_closure']['gui'][0]['resolved_candidates'].pop()
        with self.assertRaisesRegex(ValueError, 'complete bound candidate set'): validate(value, build_record=build)

    def test_recorded_bundle_digest_must_match_both_post_witnesses(self):
        _, value, _, posts, validate = self.recorded_fixture()
        for index in range(2):
            bad = copy.deepcopy(value); bad['observations'][index]['bundle_inventory_digest'] = 'f' * 64
            with self.assertRaises(ValueError): validate(bad)
        bad = copy.deepcopy(posts); bad[0]['owned_process_group_cleanup_certain'] = 1
        with self.assertRaises(ValueError): validate(post_records=bad)

    def test_workflow_and_native_limits_remain_bounded_public_read_only(self):
        workflow = (ROOT.parent / '.github/workflows/retained-native.yml').read_text()
        for item in ('runs-on: macos-15', 'contents: read', 'persist-credentials: false',
                     "github.event.repository.private == false", "github.event.repository.visibility == 'public'",
                     'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',
                     'actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3',
                     'timeout-minutes: 70', 'timeout-minutes: 35', 'timeout-minutes: 10',
                     'check-launcher-isolation-release.py', 'run-launcher-isolation.py verify'):
            self.assertIn(item, workflow)
        for item in ('upload-artifact', 'actions/cache', 'self-hosted', 'macos-15-large', 'write-all', 'pull_request_target'):
            self.assertNotIn(item, workflow)
        self.assertEqual((s.TIMEOUT, s.STOP_TIMEOUT, s.MAX_OUTPUT), (120, 5, 1048576))
        adapter = (HERE / 'run-launcher-isolation.py').read_text()
        self.assertNotIn('source.build(', adapter)
        self.assertNotIn('source.run_probe(', adapter)
        self.assertIn("'supervise.py', 'run'", adapter)
        self.assertNotIn('shell=True', adapter)


if __name__ == '__main__':
    unittest.main(verbosity=2)
