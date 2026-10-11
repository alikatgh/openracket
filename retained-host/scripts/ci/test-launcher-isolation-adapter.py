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
                      'macho': [{'path': 'binary'}], 'static_loader_context_pending': [], 'native_sha256': 'b' * 64,
                      'runtime_copy_plan': 'runtime-copy-plan.json',
                      'retained_runtime_digest': c.tree_digest(self.retained)}

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
        for name, value in [('build.json', record), ('original-runtime.json', self.before),
                            ('source-before.json', self.source_before), ('runtime-copy-plan.json', self.plan),
                            ('protected-input-witness.json', self.protected())]:
            runner.write(runner.work / name, value)
        return record

    def summary(self, runner):
        runner.work.mkdir(exist_ok=True)
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
            runner.write(profile / 'result.json', report)
            runner.write(profile / 'post-launch-witness.json', {
                'schema': 1, 'bundle_unchanged': True, 'owned_process_group_cleanup_certain': True,
                'handler_before': self.handler, 'handler_after': self.handler,
                'bundle_before_digest': 'c' * 64, 'bundle_after_digest': 'c' * 64})
            observations.append({'profile': str(profile), 'verdict': {'status': 'path-and-identity-observation-validated',
                                                                     'bundle': str(app), 'profile': str(profile)},
                                 'report': report, 'bundle_inventory_digest': 'c' * 64,
                                 'active_non_system_dylib_closure': {'gui': [], 'child': []}})
        return {'schema': 1, 'status': 'bounded-path-probe-passed', 'observations': observations,
                'original_runtime_present': True, 'recorded_original_runtime_absent': False,
                'clean_destination_tested': False, 'full_distribution_acceptance': False,
                'initially_unset_handler_tested': False, 'unresolved_static_loader_context': []}

    def test_exact27_file_freeze(self):
        self.assertEqual(len(c.frozen_sources(EXP)), 26)
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
