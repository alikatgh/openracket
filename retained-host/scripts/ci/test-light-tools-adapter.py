#!/usr/bin/env python3
"""Portable synthetic adapter tests. Never native acceptance evidence."""
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

CI = Path(__file__).resolve().parent
ROOT = CI.parents[1]
EXP = ROOT / 'experiments/native-light-tool-gates'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


C = load('light_contract_tests', CI / 'light-ci-contract.py')
V = load('frozen_light_validator_tests', EXP / 'scripts/validate-light-tool-result.py')
A = load('light_adapter_tests', CI / 'run-light-tools.py')
APP = load('light_app_tests', CI / 'app-ci-contract.py')
SOURCE = (CI / 'run-light-tools.py').read_text()


def good_records():
    return [{'entrypoint': name, 'arguments': args, 'exit_code': 1 if injection else 0,
             'timed_out': False, 'timeout_seconds': 30,
             'stdout': (injection + '\n' if injection else '') + marker + '\n', 'stderr': ''}
            for name, args, marker, injection, forbidden in V.PREFLIGHTS]


class LightAdapter(unittest.TestCase):
    def test_pinned_frozen45_plus_manifest_native16_racket15(self):
        files = C.frozen_sources(EXP)
        self.assertEqual(len(files), 16)
        self.assertEqual(sum(n.endswith('.rkt') for n in files), 15)
        self.assertEqual(len(json.loads((EXP / 'DELIVERABLE-SHA256.json').read_text())['files']), 45)
        self.assertEqual(C.sha(EXP / 'DELIVERABLE-SHA256.json'), C.FREEZE_PIN)

    def test_full_manifest_members_refuse_corruption_symlinks_and_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'file').write_text('native')
            digest = C.sha(root / 'file')
            C.check_members(root, {'file': digest})
            for members in ({'file': 'bad'}, {'../file': digest}, {'/file': digest}, {'a/../file': digest}):
                with self.assertRaises(ValueError):
                    C.check_members(root, members)
            (root / 'link').symlink_to(root / 'file')
            with self.assertRaises(ValueError):
                C.check_members(root, {'link': digest})

    def test_assemble_overlays_only_native_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            proof = root / 'proof'
            calls = []
            class FakeApp:
                @staticmethod
                def source_copy(source, target, pin, count):
                    calls.append((pin, count))
                    target.mkdir()
                    (target / 'tool').mkdir()
                    (target / 'tool/tool.rkt').write_text('accepted-production')
                    baseline = {'tool/tool.rkt': C.sha(target / 'tool/tool.rkt')}
                    (target / 'CONTENTS-SHA256.json').write_text(json.dumps(baseline))
                    return baseline
            native = C.assemble_proof(root, proof, EXP, FakeApp)
            self.assertEqual(calls, [(C.ACCEPTED_PIN, 155)])
            self.assertEqual((proof / 'tool/tool.rkt').read_text(), 'accepted-production')
            self.assertFalse((proof / 'reference').exists())
            self.assertFalse((proof / 'scripts').exists())
            self.assertEqual(len(json.loads((proof / 'CONTENTS-SHA256.json').read_text())), 17)
            C.check_members(proof, native)
            self.assertTrue((proof / 'BASE-0520-CONTENTS.json').is_file())

    def test_all_nine_exact_positive_negative_pairs(self):
        records = good_records()
        self.assertTrue(C.validate_preflights(records, V))
        for i in range(9):
            with self.assertRaises(ValueError):
                C.validate_preflights(records[:i] + records[i+1:], V)
            for key, value in [('timed_out', True), ('timeout_seconds', True), ('timeout_seconds', 31),
                               ('exit_code', True), ('stdout', ''), ('stderr', None)]:
                bad = copy.deepcopy(records)
                bad[i][key] = value
                with self.subTest(index=i, key=key), self.assertRaises(ValueError):
                    C.validate_preflights(bad, V)

    def test_negatives_reject_signals_timeouts_shell_errors_success(self):
        for i, spec in enumerate(V.PREFLIGHTS):
            if not spec[3]:
                continue
            for code in (-15, -9, 0, 124, 125, 126, 127, 128, 137, 255):
                bad = good_records()
                bad[i]['exit_code'] = code
                with self.subTest(index=i, code=code), self.assertRaises(ValueError):
                    C.validate_preflights(bad, V)
            for code in (1, 123):
                good = good_records()
                good[i]['exit_code'] = code
                self.assertTrue(C.validate_preflights(good, V))

    def test_extra_malformed_typed_markers_rejected(self):
        for i, spec in enumerate(V.PREFLIGHTS):
            marker = spec[2]
            for malformed in (marker, ' ' + marker, marker + ' trailing', marker.replace('actual=dark', 'actual=light')):
                bad = good_records()
                bad[i]['stderr'] += malformed + '\n'
                with self.subTest(index=i, malformed=malformed), self.assertRaises(ValueError):
                    C.validate_preflights(bad, V)
        bad = good_records()
        bad[8]['stdout'] = bad[8]['stdout'].replace('exn:test:check', 'exn:fail')
        with self.assertRaises(ValueError):
            C.validate_preflights(bad, V)

    def test_standalones_are_nine_direct_supervised_invocations_and_continue(self):
        with tempfile.TemporaryDirectory() as folder:
            r = A.Runner.__new__(A.Runner)
            r.proof = Path(folder)
            r.reports = Path(folder)
            r.verifier, r.contract = V, C
            r.record = lambda *args: None
            r.emit_file = lambda *args: None
            calls = []
            class Process:
                def __init__(self, argv, **kwargs):
                    i = len(calls)
                    calls.append((argv, kwargs))
                    self.evidence = good_records()[i]
                    self.returncode = self.evidence['exit_code']
                    if i == 0:
                        self.evidence['stdout'] = 'synthetic first-control failure\n'
                def communicate(self, timeout):
                    self.assert_timeout = timeout
                    if timeout != 30:
                        raise AssertionError('Changed headless bound')
                    return self.evidence['stdout'], self.evidence['stderr']
            e = dict(RACKET='/official/bin/racket', PLTADDONDIR='/fresh/addon', PLTCOMPILEDROOTS='/fresh/compiled:')
            with mock.patch.object(A.subprocess, 'Popen', Process), self.assertRaises(ValueError):
                r.preflights('stock', e)
            self.assertEqual(len(calls), 9)
            for (argv, kwargs), spec in zip(calls, V.PREFLIGHTS):
                self.assertEqual(Path(argv[5]).name, spec[0])
                self.assertEqual(argv[6:], spec[1])
                self.assertNotIn('raco', argv)
                self.assertEqual(kwargs['stderr'], subprocess.PIPE)
                self.assertEqual(kwargs['stdout'], subprocess.PIPE)
            self.assertEqual(len(json.loads((Path(folder) / 'stock-preflights.json').read_text())), 9)

    def test_case_failures_preserve_later_independent_stock_prerequisites(self):
        for failing in [('debugger', False), ('debugger', True), ('macro-stepper', False)]:
            calls = []
            def case(name, modern):
                calls.append((name, modern))
                if (name, modern) == failing:
                    raise RuntimeError('synthetic isolated failure')
                return True
            rows = C.run_case_matrix(case, lambda *args: None, {a: True for a in C.ARMS})
            self.assertEqual(len(rows), 6)
            self.assertIn(('teaching-tests', False), calls)
            self.assertIn(('teaching-tests', True), calls)
            if not failing[1]:
                self.assertNotIn((failing[0], True), calls)
            with self.assertRaises(ValueError):
                C.validate_matrix(rows)

    def test_unavailable_modern_preparation_does_not_hide_stock(self):
        calls = []
        rows = C.run_case_matrix(lambda c, m: calls.append((c, m)) or True, lambda *args: None,
                                 {'stock': True, 'modern-light': False})
        self.assertEqual(calls, [(c, False) for c in C.CASES])
        self.assertEqual(sum(r['passed'] for r in rows), 3)
        with self.assertRaises(ValueError):
            C.validate_matrix(rows)

    def test_six_unique_completed_pairs_required(self):
        good = C.run_case_matrix(lambda *args: True, lambda *args: None, {a: True for a in C.ARMS})
        self.assertTrue(C.validate_matrix(good))
        for bad in (good[:-1], good[:-1] + [good[0]], list(reversed(good))):
            with self.assertRaises(ValueError):
                C.validate_matrix(bad)
        bad = copy.deepcopy(good)
        bad[0]['passed'] = 1
        with self.assertRaises(ValueError):
            C.validate_matrix(bad)

    def test_environment_removes_all_experiments_and_appearance_check(self):
        parent = {'PATH': '/bad', 'PLTCOLLECTS': '/bad', 'PYTHONOPTIMIZE': '1',
                  'OPENRACKET_NATIVE_APPEARANCE_CHECK': '1', 'OPENRACKET_MEMORY_LIMIT_MIB': '256',
                  'OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD': '1', 'XDG_CACHE_HOME': '/shared'}
        e = APP.environment(parent, Path('/runtime/bin/racket'), Path('/fresh'), Path('/fresh/addon'), Path('/fresh/compiled'))
        self.assertFalse(any(k.startswith('OPENRACKET_') for k in e))
        self.assertNotIn('PLTCOLLECTS', e)
        self.assertNotIn('PYTHONOPTIMIZE', e)
        self.assertEqual(e['XDG_CACHE_HOME'], '/fresh/.cache')
        self.assertEqual(e['PLTCOMPILEDROOTS'], '/fresh/compiled:')

    def test_source_preserves_registration_reader_compile_and_deadlines(self):
        ast.parse(SOURCE)
        node = next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.ClassDef) and n.name == 'Runner')
        methods = {m.name: ast.get_source_segment(SOURCE, m) for m in node.body if isinstance(m, ast.FunctionDef)}
        registration = methods['fresh_modern_addon']
        for flag in ('--scope', '--deps', '--copy', '--link', '--no-setup', '--avoid-main', '--no-docs', '--no-launcher', '--no-foreign-libs', '--no-install', '--no-post-install'):
            self.assertIn(repr(flag), registration)
        self.assertNotIn("'--auto'", registration)
        self.assertNotIn("'-U'", registration)
        self.assertNotIn('shutil.copytree', registration)
        self.assertIn('verify-modern-tool-registration.rkt', registration)
        self.assertIn('source.is_relative_to(self.addon.resolve())', registration)
        self.assertIn("'native-light-tools'", methods['prepare_runtime'])
        self.assertIn('assert len(modules) == 15', methods['prepare_runtime'])
        self.assertLess(methods['prepare_runtime'].index("reader all15"), methods['prepare_runtime'].index("compile all15"))
        native = methods['native_case']
        self.assertLess(native.index('fresh_modern_addon'), native.index('deadline = started + 60'))
        self.assertIn('independent-native-light-tools-host.rkt', native)
        self.assertIn("OPENRACKET_THEME='light'", native)
        self.assertNotIn("OPENRACKET_THEME='dark'", native)
        self.assertNotIn('MEMORY_LIMIT', native)
        self.assertIn('timed_out = time.monotonic() > deadline', native)
        self.assertLess(native.index('result = p.wait('), native.index('report = json.loads(raw)'))
        self.assertIn('if captured and time.monotonic() < deadline:', native)
        self.assertIn("args.append('--timed-out')", native)
        self.assertIn("'--stdout', stdout_file, '--stderr', stderr_file", native)
        self.assertIn('all(r', (CI / 'light-ci-contract.py').read_text())

    def test_transport_is_lossless_for_full_binary_streams_and_trees(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tree.json'
            raw = bytes(range(256)) * 300
            path.write_bytes(raw)
            wrapped = C.wrap_bytes(path)
            decoded = b''.join(base64.b64decode(chunk) for chunk in wrapped['chunks'])
            self.assertEqual(decoded, raw)
            self.assertEqual(wrapped['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(wrapped['bytes'], len(raw))

    def native_scenario(self, kind):
        """Synthetic process/clock behavior; never launches a GUI or Racket."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        runner = A.Runner.__new__(A.Runner)
        runner.proof, runner.reports = root / 'proof', root / 'reports'
        runner.proof.mkdir()
        runner.reports.mkdir()
        runner.exp = EXP
        runner.contract, runner.verifier = C, V
        runner.recorded = []
        runner.record = lambda *args: runner.recorded.append(args)
        runner.emitted = []
        def emit_file(path, label):
            runner.emitted.append((label, path.read_bytes()))
            if kind == 'emit-error' and len(runner.emitted) == 1:
                raise RuntimeError('synthetic stream transport failure')
        runner.emit_file = emit_file
        runner.images = []
        runner.emit_image = lambda *args: runner.images.append(args)
        runner.env = lambda label, modern: APP.environment({}, Path('/official/bin/racket'), root / label,
                                                          root / label / 'addon', root / label / 'compiled')
        runner.fresh_modern_addon = lambda *args: None
        runner.terminate_group = lambda p: setattr(p, 'returncode', -15)
        runner.live_group_members = lambda pid: []
        runner.launches_blocked = False
        if kind == 'cleanup-failure':
            def fail_cleanup(p):
                raise RuntimeError('synthetic cleanup refusal')
            runner.terminate_group = fail_cleanup
        clock = [10.0]
        acknowledged = []
        def screenshot(path, deadline):
            if kind == 'capture-failure':
                return False, 'synthetic capture failure'
            path.write_bytes(b'synthetic image')
            if kind == 'capture-late':
                clock[0] = 71.0
            return True, 'synthetic capture'
        runner.screenshot = screenshot
        for arm in C.ARMS:
            (runner.reports / (arm + '-preflights.json')).write_text(json.dumps(good_records()))
        def command(name, argv, **kwargs):
            args = [str(a) for a in argv]
            report = json.loads(Path(args[args.index('--report') + 1]).read_text())
            stdout = Path(args[args.index('--stdout') + 1]).read_text()
            stderr = Path(args[args.index('--stderr') + 1]).read_text()
            exit_code = int(args[args.index('--exit-code') + 1])
            try:
                V.validate_result('stock', 'debugger', report, stdout, stderr, exit_code, '--timed-out' in args)
                code = 0
            except ValueError:
                code = 1
            return {'exit_code': code, 'timed_out': False}
        runner.command = command
        class Process:
            def __init__(self, argv, env, stdout, stderr, **kwargs):
                self.env = env
                self.returncode = None
                self.pid = 777777
                report = {'status': 'passed', 'racket': '9.3', 'genuine_host': True,
                          'repeated_real_run': True, 'complete_stock_parity': False,
                          'physical_input_to_photon_measured': False, 'ui': 'stock', 'theme': 'light',
                          'follow_on_case': 'debugger', 'follow_on_result': {'case': 'debugger', 'status': 'passed'},
                          'native_appearance_lifecycle': None}
                Path(env['OPENRACKET_READY_FILE']).write_text('{partial' if kind == 'malformed' else json.dumps(report))
                stdout.write('OPENRACKET_NATIVE_RESULT ' + json.dumps(report) + '\nOPENRACKET_NATIVE_READY\n')
                stdout.flush()
            def poll(self):
                return self.returncode
            def wait(self, timeout):
                acknowledged.append(Path(self.env['OPENRACKET_CAPTURE_DONE']).exists())
                if kind in ('hang', 'cleanup-failure') and self.returncode is None:
                    clock[0] = 70.1
                    raise subprocess.TimeoutExpired('synthetic native', timeout)
                if kind == 'late-exit':
                    clock[0] = 70.1
                if self.returncode is None:
                    self.returncode = 0
                return self.returncode
        original_write_text = Path.write_text
        def write_text(path, content, *args, **kwargs):
            if kind == 'ack-error' and path.name == 'capture-done':
                raise OSError('synthetic ACK write failure')
            return original_write_text(path, content, *args, **kwargs)
        with mock.patch.object(A.subprocess, 'Popen', Process), mock.patch.object(A.time, 'monotonic', lambda: clock[0]), mock.patch.object(Path, 'write_text', write_text):
            passed = runner.native_case('debugger')
        supervisor = json.loads((runner.reports / 'tools-stock-debugger/supervisor.json').read_text())
        return passed, supervisor, acknowledged, runner

    def test_actual_supervisor_requires_capture_then_ack_and_terminal_success(self):
        passed, supervisor, acknowledgments, runner = self.native_scenario('success')
        self.assertTrue(passed)
        self.assertTrue(acknowledgments[0])
        self.assertEqual(supervisor['exit_code'], 0)
        self.assertFalse(supervisor['timed_out'])
        self.assertTrue(supervisor['capture_acknowledged_within_deadline'])
        self.assertEqual(len(runner.emitted), 4)

    def test_actual_supervisor_refuses_late_exit_timeout_bad_capture_and_malformed_ready(self):
        for kind in ('late-exit', 'hang', 'capture-late', 'capture-failure', 'malformed', 'ack-error', 'cleanup-failure'):
            with self.subTest(kind=kind):
                passed, supervisor, acknowledgments, runner = self.native_scenario(kind)
                self.assertFalse(passed)
                self.assertEqual(supervisor['timeout_seconds'], 60)
                self.assertEqual(len(runner.emitted), 4)
                if kind in ('late-exit', 'hang', 'capture-late', 'cleanup-failure'):
                    self.assertTrue(supervisor['timed_out'])
                if kind in ('capture-late', 'capture-failure'):
                    self.assertFalse(acknowledgments[0])
                    self.assertFalse(supervisor['capture_acknowledged_within_deadline'])
                if kind == 'ack-error':
                    self.assertTrue(supervisor['cleanup_verified'])
                    self.assertTrue(supervisor['forced_cleanup'])
                    self.assertIn('ACK write failure', supervisor['supervisor_error'])
                if kind == 'cleanup-failure':
                    self.assertFalse(supervisor['cleanup_verified'])
                    self.assertTrue(runner.launches_blocked)
                    with self.assertRaisesRegex(RuntimeError, 'No later GUI launch'):
                        runner.native_case('macro-stepper')
                if kind == 'malformed':
                    self.assertTrue(any(b'{partial' == raw for label, raw in runner.emitted))

    def test_one_transport_failure_preserves_later_raw_ready_and_image_evidence(self):
        passed, supervisor, acknowledgments, runner = self.native_scenario('emit-error')
        self.assertFalse(passed)
        self.assertTrue(supervisor['cleanup_verified'])
        self.assertEqual(len(runner.emitted), 4)
        self.assertEqual(len(runner.images), 1)
        self.assertTrue(any('complete raw evidence transport' in name and not ok for name, ok, detail in runner.recorded))

    def test_byte_wrapper_round_trip_through_existing_log_codec(self):
        import contextlib
        import io
        emitter = load('light_emitter_tests', CI / 'emit-replay-evidence.py')
        decoder = load('light_decoder_tests', CI / 'decode-light-tools-evidence.py')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'full-tree.json'
            raw = json.dumps({'entries': [[str(i), 'a' * 150] for i in range(1000)]}).encode()
            source.write_bytes(raw)
            label = root / 'evidence-pristine-baseline-tree'
            label.mkdir()
            wrapped = label / 'supervisor.json'
            value = C.wrap_bytes(source)
            wrapped.write_text(json.dumps(value))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                emitter.emit(wrapped)
            index = decoder.decode(output.getvalue(), root / 'decoded')
            self.assertEqual(Path(index[0]['path']).read_bytes(), raw)
            for key, bad in [('filename', '../escape'), ('bytes', True), ('sha256', 'bad'), ('chunks', ['bad!'])]:
                rejected = copy.deepcopy(value)
                rejected[key] = bad
                with self.assertRaises((ValueError, TypeError)):
                    decoder.unwrap(rejected)
            with self.assertRaises(ValueError):
                decoder.decode(output.getvalue(), root / 'decoded')

    def test_full_runtime_witness_refuses_any_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            runtime = temp / 'runtime'
            runtime.mkdir()
            (runtime / 'compiled').mkdir()
            (runtime / 'compiled/module.zo').write_bytes(b'original compiled bytes')
            witness = temp / 'tree.json'
            e = {**os.environ, 'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
                 'GITHUB_REF': 'refs/heads/prototype/retained-drracket', 'RUNNER_TEMP': str(temp)}
            import sys
            def run(operation):
                return subprocess.run([sys.executable, str(CI / 'runtime-tree-check.py'), operation, str(runtime), str(witness)], env=e, capture_output=True, text=True)
            self.assertEqual(run('baseline').returncode, 0)
            self.assertEqual(run('compare').returncode, 0)
            before = witness.read_bytes()
            (runtime / 'compiled/module.zo').write_bytes(b'mutated compiled bytes')
            self.assertNotEqual(run('compare').returncode, 0)
            self.assertEqual(witness.read_bytes(), before)
            self.assertEqual(C.sha(CI / 'runtime-tree-check.py'), 'a02dc5d58859e821d26ae290a5c690b90ceb2e12e06b548e044185a7acc11031')

    def test_independent_runtime_copy_preserves_no_hardlinks_or_original_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            original = temp / 'runtime'
            (original / 'bin').mkdir(parents=True)
            (original / 'bin/racket').write_text('synthetic runtime fixture')
            e = {**os.environ, 'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
                 'GITHUB_REF': 'refs/heads/prototype/retained-drracket', 'RUNNER_TEMP': str(temp),
                 'OPENRACKET_CI_STOCK_RACKET': str(original / 'bin/racket')}
            import sys
            result = subprocess.run([sys.executable, str(CI / 'copy-independent-runtime.py'), 'native-light-tools'], env=e, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            copied = temp / 'runtime-native-light-tools/bin/racket'
            self.assertEqual(copied.read_bytes(), (original / 'bin/racket').read_bytes())
            self.assertNotEqual(copied.stat().st_ino, (original / 'bin/racket').stat().st_ino)
            copied.write_text('changed only selected copy')
            self.assertEqual((original / 'bin/racket').read_text(), 'synthetic runtime fixture')

    def test_final_runtime_checks_continue_after_one_witness_transport_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runner = A.Runner.__new__(A.Runner)
            runner.temp, runner.reports, runner.stock, runner.modern = root, root, root / 'stock', root / 'modern'
            runner.contract = C
            runner.state = root / 'results.json'
            runner.state.write_text('[]')
            runner.rows = []
            def record(name, passed, detail=''):
                runner.rows.append({'name': name, 'passed': passed, 'detail': detail})
            runner.record = record
            calls = []
            def tree(operation, path, label, required):
                calls.append(label)
                if label == 'pristine':
                    raise RuntimeError('synthetic first witness transport failure')
                return True
            runner.tree = tree
            runner.emit_file = lambda *args: None
            for label in ('pristine', 'selected-modern'):
                (root / ('light-tools-' + label + '-tree.json')).write_text('{}')
            matrix = C.run_case_matrix(lambda *args: True, lambda *args: None, {a: True for a in C.ARMS})
            (root / 'matrix.json').write_text(json.dumps(matrix))
            with self.assertRaisesRegex(RuntimeError, 'mandatory gates failed'):
                runner.verify()
            self.assertEqual(calls, ['pristine', 'selected-modern'])

    def test_runtime_transport_keeps_full_local_trees_but_only_logs_summaries(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            root = temp / 'runtime'
            root.mkdir()
            for i in range(50):
                (root / str(i)).write_text('original')
            runner = A.Runner.__new__(A.Runner)
            runner.temp, runner.ci, runner.reports = temp, CI, temp / 'reports'
            runner.reports.mkdir()
            emitted = []
            runner.emit_file = lambda path, label: emitted.append((label, json.loads(path.read_text())))
            env = {**os.environ, 'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
                   'GITHUB_REF': 'refs/heads/prototype/retained-drracket', 'RUNNER_TEMP': str(temp)}
            def command(name, argv, **kwargs):
                result = subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True)
                return {'exit_code': result.returncode, 'timed_out': False}
            runner.command = command
            self.assertTrue(runner.tree('baseline', root, 'pristine'))
            full = runner.reports / 'pristine-baseline-tree.json'
            self.assertTrue(full.is_file())
            self.assertEqual(emitted[0][1]['sha256'], C.sha(full))
            self.assertEqual(emitted[0][1]['bytes'], len(full.read_bytes()))
            self.assertEqual(emitted[0][1]['entries'], 51)
            self.assertIs(type(emitted[0][1]['entries']), int)
            self.assertEqual([label for label, data in emitted], ['pristine-baseline-tree-summary'])
            for i in range(50):
                (root / str(i)).write_text('changed')
            self.assertFalse(runner.tree('compare', root, 'pristine', False))
            self.assertTrue((runner.reports / 'pristine-final-tree.json').is_file())
            changed = next(data for label, data in emitted if label == 'pristine-all-runtime-changes')
            self.assertEqual(changed['changed_count'], 50)
            self.assertEqual(len(changed['changes']), 50)
            self.assertNotIn('pristine-baseline-tree', [label for label, data in emitted])
            self.assertNotIn('pristine-final-tree', [label for label, data in emitted])

    def test_workflow_keeps_only_standard_public_readonly_runner(self):
        workflow = (ROOT.parent / '.github/workflows/retained-native.yml').read_text()
        for text in ('runs-on: macos-15', 'contents: read', 'persist-credentials: false',
                     "github.event.repository.private == false", "github.event.repository.visibility == 'public'",
                     'run-light-tools.py prepare', 'run-light-tools.py cases', 'run-light-tools.py verify'):
            self.assertIn(text, workflow)
        self.assertEqual(workflow.count("if: always() && steps.runtime.outcome == 'success'"), 3)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('upload-artifact', workflow)


if __name__ == '__main__':
    unittest.main(verbosity=2)
