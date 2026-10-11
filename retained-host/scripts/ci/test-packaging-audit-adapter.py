#!/usr/bin/env python3
"""Pure local orchestration/negative checks. No native runtime is executed."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


c = module('audit_contract_test', HERE / 'packaging-audit-contract.py')
a = module('audit_adapter_test', HERE / 'run-packaging-audit.py')
emitter = module('audit_emitter_test', HERE / 'emit-replay-evidence.py')
decoder = module('audit_decoder_test', HERE / 'decode-light-tools-evidence.py')


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.runtime = self.path / 'runtime'
        self.runtime.mkdir()
        (self.runtime / 'binary').write_bytes(b'fixture bytes only')
        self.handler = {'schema': 1, 'status': 'observed', 'extension': 'rkt', 'defaults_changed': False}
        self.claims = [{'plist': 'Racket.app/Contents/Info.plist', 'sha256': 'a' * 64,
                        'bundle_identifier': 'org.racket', 'declarations': {'CFBundleDocumentTypes': []}}]
        self.before = c.inventory(self.runtime)
        self.digest = c.tree_digest(self.before)
        self.audit = {'schema': 1, 'inventory': self.before, 'inventory_digest': self.digest,
                      'nested_apps': self.claims, 'macho': [{'path': 'binary'}], 'static_loader_context_pending': []}
        self.build = {'schema': 1, 'status': 'assembled-not-launched', 'original_runtime': str(self.runtime),
                      'original_runtime_digest': self.digest, 'handler_baseline': self.handler,
                      'nested_apps': self.claims, 'native_launch_blocked_by_declarations': True,
                      'manual_signing_or_security_changes': False, 'intrinsic_generator_ad_hoc_signing': True,
                      'macho': [{'path': 'binary'}], 'static_loader_context_pending': [], 'native_sha256': 'b' * 64}

    def test_exact_frozen_inventory(self):
        self.assertEqual(len(c.frozen_sources(ROOT / 'experiments/relative-launcher-probe')), 22)

    def test_manifest_tamper_refused(self):
        source = self.path / 'source'
        shutil.copytree(ROOT / 'experiments/relative-launcher-probe', source)
        path = source / 'README.md'
        path.chmod(0o600)
        path.write_text(path.read_text() + '\nmutation')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            c.frozen_sources(source)

    def test_extra_source_refused(self):
        source = self.path / 'source'
        shutil.copytree(ROOT / 'experiments/relative-launcher-probe', source)
        source.chmod(0o700)
        (source / 'extra').write_text('not in freeze')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.frozen_sources(source)

    def test_inventory_mtime_mode_bytes_and_symlink(self):
        file = self.runtime / 'binary'
        os.utime(file, ns=(file.stat().st_atime_ns, file.stat().st_mtime_ns + 1234))
        self.assertEqual([r['path'] for r in c.changes(self.before, c.inventory(self.runtime))], ['binary'])
        file.chmod(0o700)
        file.write_bytes(b'changed bytes')
        (self.runtime / 'alias').symlink_to('binary')
        after = c.inventory(self.runtime)
        self.assertEqual(after['alias']['kind'], 'link')
        self.assertEqual(after['alias']['target'], 'binary')
        self.assertEqual(after['binary']['mode'], 0o700)
        self.assertNotEqual(c.tree_digest(after), self.digest)
        self.assertEqual(set(r['path'] for r in c.changes(self.before, after)), {'.', 'alias', 'binary'})

    def test_whole_inventory_all_changes_not_first30(self):
        before = {str(i): {'value': i} for i in range(100)}
        self.assertEqual(len(c.changes(before, {})), 100)

    def test_empty_declaration_key_still_blocks(self):
        self.assertTrue(c.claims_present(self.claims))
        self.assertTrue(c.validate_build(self.build, self.runtime, self.digest, self.handler))

    def test_missing_or_inconsistent_declaration_flag(self):
        for value in (False, 1, 'true', None):
            bad = copy.deepcopy(self.build)
            bad['native_launch_blocked_by_declarations'] = value
            with self.assertRaises(ValueError):
                c.validate_build(bad, self.runtime, self.digest, self.handler)

    def test_unexpected_status_never_accepted(self):
        for status in ('bounded-path-probe-passed', 'success', 'refused', None):
            bad = copy.deepcopy(self.build)
            bad['status'] = status
            with self.assertRaises(ValueError):
                c.validate_build(bad, self.runtime, self.digest, self.handler)

    def test_exact_schema_and_original_digest(self):
        for field, value in (('schema', True), ('original_runtime_digest', '0' * 64),
                             ('manual_signing_or_security_changes', True), ('handler_baseline', {}), ('macho', None)):
            bad = copy.deepcopy(self.build)
            bad[field] = value
            with self.assertRaises(ValueError):
                c.validate_build(bad, self.runtime, self.digest, self.handler)

    def test_audit_requires_same_preimport_bytes_metadata(self):
        self.assertEqual(c.validate_audit(self.audit, self.before), self.digest)
        for field, value in (('inventory_digest', '0' * 64), ('schema', True), ('inventory', {}), ('macho', [])):
            bad = copy.deepcopy(self.audit)
            bad[field] = value
            with self.assertRaises(ValueError):
                c.validate_audit(bad, self.before)

    def test_no_claims_never_authorizes_launch(self):
        value = c.verdict(True, False, True, True, True)
        self.assertEqual(value['status'], 'audit-complete-no-launch-authorized')
        self.assertEqual(value['native_app_launches'], 0)
        self.assertFalse(value['native_app_acceptance'])
        self.assertFalse(value['full_distribution_acceptance'])

    def test_declared_claims_visible_as_actual_diagnostic(self):
        value = c.verdict(True, True, True, True, True)
        self.assertEqual(value['status'], 'audit-complete-launch-blocked-by-declarations')
        self.assertTrue(value['declarations_block_launch'])
        self.assertTrue(value['mandatory_no_launch'])

    def test_incomplete_evidence_cannot_pass(self):
        for index in (0, 2, 3, 4):
            args = [True, True, True, True, True]
            for bad in (False, None, 1, 'true'):
                args[index] = bad
                self.assertFalse(c.verdict(*args)['audit_complete'])

    def test_environment_guards(self):
        event = self.path / 'event.json'
        event.write_text(json.dumps({'repository': {'full_name': 'alikatgh/openracket', 'private': False, 'visibility': 'public'}}))
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
               'GITHUB_REF': 'refs/heads/prototype/retained-drracket', 'GITHUB_EVENT_NAME': 'push', 'GITHUB_EVENT_PATH': str(event)}
        c.guard(env, 'Darwin', 'arm64')
        for key in ('GITHUB_ACTIONS', 'GITHUB_REPOSITORY', 'GITHUB_REF', 'GITHUB_EVENT_NAME'):
            with self.assertRaises(ValueError):
                c.guard({**env, key: 'wrong'}, 'Darwin', 'arm64')
        with self.assertRaises(ValueError):
            c.guard(env, 'Linux', 'x86_64')
        event.write_text(json.dumps({'repository': {'full_name': 'alikatgh/openracket', 'private': True, 'visibility': 'private'}}))
        with self.assertRaises(ValueError):
            c.guard(env, 'Darwin', 'arm64')

    def runner(self):
        runner = a.Runner.__new__(a.Runner)
        runner.c = c
        runner.ci = HERE
        runner.root = ROOT
        runner.exp = ROOT / 'experiments/relative-launcher-probe'
        runner.proof = self.path / 'proof'
        runner.proof.mkdir()
        runner.reports = self.path / 'reports'
        runner.reports.mkdir()
        runner.runtime = self.runtime
        runner.state_file = runner.reports / 'state.json'
        runner.state = {'assembled': False, 'errors': [], 'declarations_block_launch': None, 'native_state': 'safe'}
        runner.source = None
        runner.save()
        return runner

    def test_orchestration_exact_order_and_cli(self):
        runner = self.runner()
        calls = []
        def handler(label):
            self.assertTrue((runner.proof / 'original-before.json').is_file())
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
                work = runner.proof / 'build-work'
                self.assertEqual(argv[2:], ['build', '--runtime', self.runtime, '--work', work,
                                          '--expected-runtime-digest', self.digest])
                self.assertTrue(native)
                work.mkdir()
                runner.write(work / 'build.json', self.build)
                runner.write(work / 'protected-input-witness.json', {'original_runtime_unchanged': True, 'source_unchanged': True})
            else:
                self.fail('Unexpected command: ' + label)
        with mock.patch.object(runner, 'handler', side_effect=handler), mock.patch.object(runner, 'command', side_effect=command):
            runner.run()
        self.assertEqual(calls, ['handler-before-probe', 'portable-source-tests', 'audit-runtime', 'build'])
        self.assertTrue(runner.state['assembled'])
        self.assertEqual(runner.state['native_state'], 'safe')

    def test_failed_build_stays_native_blocked_with_partial_outputs(self):
        runner = self.runner()
        with mock.patch.object(a.subprocess, 'run', return_value=mock.Mock(returncode=1)):
            with self.assertRaises(ValueError):
                runner.command('build', ['never-executed-mock'], native=True)
        self.assertEqual(runner.state['native_state'], 'unresolved-build')
        self.assertTrue((runner.proof / 'build/command.json').is_file())
        self.assertTrue((runner.proof / 'build/stdout.txt').is_file())
        with mock.patch.object(a.subprocess, 'run') as process:
            with self.assertRaises(ValueError):
                runner.command('later', ['never-executed-mock'], native=True)
            process.assert_not_called()
        with mock.patch.object(runner, 'source_module') as source:
            with self.assertRaises(ValueError):
                runner.handler('later')
            source.assert_not_called()

    def test_verify_runs_filesystem_after_uncertainty_skips_handler(self):
        runner = self.runner()
        runner.state['native_state'] = 'pending-build'
        with mock.patch.object(runner, 'handler') as handler, \
                mock.patch.object(runner, 'filesystem_witness', return_value=True) as filesystem, \
                mock.patch.object(runner, 'collect_evidence', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                runner.verify()
        filesystem.assert_called_once()
        handler.assert_not_called()
        result = json.loads((runner.reports / 'result.json').read_text())
        self.assertFalse(result['audit_complete'])
        self.assertIsNone(result['default_handler_unchanged'])

    def test_partial_malformed_documents_preserved_losslessly(self):
        runner = self.runner()
        raw = b'{"partial":"\\u1234",broken\xff'
        (runner.proof / 'runtime-audit.json').write_bytes(raw)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(runner.collect_evidence())
        self.assertTrue(runner.state['errors'])
        index = decoder.decode(output.getvalue(), self.path / 'decoded')
        recovered = [Path(row['path']).read_bytes() for row in index if Path(row['path']).name == 'runtime-audit.json']
        self.assertEqual(recovered, [raw])

    def test_metadata_transport_keeps_all_rows_and_hashes_full_inventory(self):
        runner = self.runner()
        runner.write(runner.proof / 'runtime-audit.json', self.audit)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.collect_evidence()
        index = decoder.decode(output.getvalue(), self.path / 'decoded')
        path = next(Path(row['path']) for row in index if Path(row['path']).name == 'runtime-audit-metadata.json')
        value = json.loads(path.read_text())
        self.assertEqual(value['nested_apps'], self.claims)
        self.assertEqual(value['macho'], self.audit['macho'])
        self.assertNotIn('inventory', value)
        self.assertEqual(value['raw_full_report']['sha256'], c.sha(runner.proof / 'runtime-audit.json'))
        self.assertEqual(value['raw_full_report']['entry_count'], len(self.before))

    def test_large_strings_arrays_and_non_utf8_roundtrip(self):
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
        index = decoder.decode(output.getvalue(), self.path / 'decoded')
        self.assertEqual(Path(index[0]['path']).read_bytes(), raw)
        with self.assertRaises(AssertionError):
            decoder.decode('\n'.join(output.getvalue().splitlines()[:-1]), self.path / 'truncated')

    def test_missing_success_diagnostics_fail_transport(self):
        runner = self.runner()
        runner.state['assembled'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(runner.collect_evidence())

    def test_native_contract_remains_pinned_and_audit_only(self):
        source = (ROOT / 'experiments/relative-launcher-probe/supervise.py').read_text()
        self.assertIn('TIMEOUT = 120', source)
        self.assertIn('STOP_TIMEOUT = 5', source)
        self.assertIn('MAX_OUTPUT = 1024 * 1024', source)
        adapter = (HERE / 'run-packaging-audit.py').read_text()
        self.assertNotIn("'supervise.py', 'run'", adapter)
        self.assertNotIn('source.build(', adapter)
        self.assertIn("'--expected-runtime-digest', exact_digest", adapter)
        self.assertIn("result['audit_complete']", adapter)
        workflow = (ROOT.parent / '.github/workflows/retained-native.yml').read_text()
        for item in ('runs-on: macos-15', 'contents: read', 'persist-credentials: false',
                     "github.event.repository.private == false", "github.event.repository.visibility == 'public'",
                     'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',
                     'actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3'):
            self.assertIn(item, workflow)
        for item in ('upload-artifact', 'actions/cache', 'self-hosted', 'macos-15-large', 'write-all', 'pull_request_target'):
            self.assertNotIn(item, workflow)
        self.assertNotIn('supervise.py run', workflow)


if __name__ == '__main__':
    unittest.main(verbosity=2)
