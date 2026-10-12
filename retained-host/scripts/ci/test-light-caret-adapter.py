#!/usr/bin/env python3
"""Portable synthetic adapter tests. No native/reader/compiler evidence is created."""
import ast
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import importlib.util

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

CI = Path(__file__).resolve().parent
ROOT = CI.parents[1]
EXP = ROOT / 'experiments/light-caret-contrast'
ACCEPTED = ROOT / 'experiments/light-caret-accepted-source'
C = module('caret_test_contract', CI / 'caret-ci-contract.py')
A = module('caret_test_adapter', CI / 'run-light-caret.py')
D = module('caret_test_decoder', CI / 'decode-light-caret-evidence.py')
V = module('caret_test_verifier', EXP / 'scripts/validate-caret-result.py')
T = module('caret_test_fixtures', EXP / 'tests/test_package.py')
APP = module('caret_test_app', CI / 'light-caret-support/app-ci-contract.py')
LIGHT = module('caret_test_light', CI / 'light-caret-support/light-ci-contract.py')
EMIT = module('caret_test_emitter', CI / 'light-caret-support/emit-replay-evidence.py')
SOURCE = (CI / 'run-light-caret.py').read_text()

class ContractTests(unittest.TestCase):
    def test_all_exact_inputs_and_manifest_members(self):
        self.assertEqual(len(C.verify_inputs(EXP, ACCEPTED, CI / 'light-caret-support')), 155)
        self.assertEqual(C.sha(EXP / 'MANIFEST.json'), C.FREEZE_PIN)
        self.assertEqual(len(V.required_racket_modules()), 22)
        self.assertEqual(len(V.PREFLIGHTS), 12)

    def test_real_compositions_are_175_and_differ_only_info(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = C.inventory(ACCEPTED)
            rows = [T.c.compose(ACCEPTED, root / arm, arm) for arm in C.ARMS]
            C.validate_compositions(*rows, V)
            self.assertEqual(C.inventory(ACCEPTED), before)
            for arm, row in zip(C.ARMS, rows):
                C.check_members(root / arm, row['files'])
                self.assertEqual(len(T.c.members(root / arm)), 175)
                self.assertFalse((root / arm / 'reference').exists())
            rows[1]['files']['tool/tool.rkt'] = 'bad'
            with self.assertRaises(ValueError):
                C.validate_compositions(*rows, V)

    def test_member_paths_casefold_and_alias_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'member').write_bytes(b'exact')
            pin = C.sha(source / 'member')
            alias = root / 'alias'
            alias.symlink_to(source, target_is_directory=True)
            C.check_members(alias, {'member': pin})
            for names in ({'member': pin, 'MEMBER': pin}, {'../member': pin}, {'/member': pin}, {'./member': pin}, {'member': 'bad'}):
                with self.assertRaises(ValueError):
                    C.check_members(source, names)
            (source / 'inside').symlink_to(source, target_is_directory=True)
            with self.assertRaises(ValueError):
                C.check_members(source, {'inside/member': pin})

    def test_runtime_clone_is_byte_equal_without_mutable_hardlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            (source / 'bin').mkdir(parents=True)
            (source / 'bin/racket').write_bytes(b'fixture')
            C.independent_copy(source, root / 'clone')
            self.assertEqual(C.inventory(source), C.inventory(root / 'clone'))
            self.assertNotEqual((source / 'bin/racket').stat().st_ino, (root / 'clone/bin/racket').stat().st_ino)
            with self.assertRaises(ValueError):
                C.independent_copy(source, root / 'clone')
            (source / 'alias').symlink_to(source / 'bin/racket')
            with self.assertRaises(ValueError):
                C.independent_copy(source, root / 'bad-clone')

    def test_durable_prelaunch_and_cleanup_uncertainty_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'safety.json'
            s = C.Safety(path)
            with self.assertRaises(ValueError):
                s.safe()
            s.initialize()
            s.safe()
            s.begin('first', 'command')
            with self.assertRaises(ValueError):
                C.Safety(path).safe()
            with self.assertRaises(ValueError):
                C.Safety(path).begin('second', 'command')
            s.spawned('first', 123)
            s.finish('first', False)
            with self.assertRaises(ValueError):
                C.Safety(path).safe()
            self.assertTrue(C.Safety(path).read()['blocked'])

    def test_only_owned_bounded_capture_can_overlap_gui(self):
        with tempfile.TemporaryDirectory() as temp:
            s = C.Safety(Path(temp) / 'safety.json')
            s.initialize()
            s.begin('gui', 'gui')
            s.spawned('gui', 100)
            for kind, owner in [('command', 'gui'), ('capture', 'wrong')]:
                with self.assertRaises(ValueError):
                    s.begin('bad', kind, owner)
            s.begin('capture', 'capture', 'gui')
            s.spawned('capture', 101)
            s.finish('capture', True)
            s.finish('gui', True)
            C.Safety(s.path).safe()
            with self.assertRaises(ValueError):
                s.begin('gui', 'gui')

    def test_interrupted_atomic_write_blocks_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'safety.json'
            path.with_name('safety.json.pending').write_text('{partial')
            with self.assertRaises(ValueError):
                C.Safety(path).safe()
            with self.assertRaises(ValueError):
                C.Safety(path).begin('launch', 'command')

    def test_all_12_strict_receipts_and_marker_refusals(self):
        good = T.preflights()
        C.validate_preflights(good, V)
        for index, spec in enumerate(V.PREFLIGHTS):
            for key, value in [('timed_out', True), ('exit_code', True), ('exit_code', -9), ('exit_code', 124), ('timeout_seconds', 31), ('stdout', ''), ('stderr', spec[2] + '\n')]:
                bad = copy.deepcopy(good)
                bad[index][key] = value
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    C.validate_preflights(bad, V)
        for index, spec in enumerate(V.PREFLIGHTS):
            if spec[3]:
                for code in (0, 125, 127, 255):
                    bad = copy.deepcopy(good)
                    bad[index]['exit_code'] = code
                    with self.assertRaises(ValueError):
                        C.validate_preflights(bad, V)

    def test_clean_environment_leaves_measured_settings_unmodified(self):
        e = APP.environment({'PLTCOLLECTS': '/shared', 'OPENRACKET_MEMORY_LIMIT_MIB': '256', 'OPENRACKET_NATIVE_APPEARANCE_CHECK': '1', 'OPENRACKET_EXPERIMENTAL_BAD': '1', 'PYTHONOPTIMIZE': '1'}, Path('/runtime/bin/racket'), Path('/fresh'), Path('/fresh/addon'), Path('/fresh/cache'))
        self.assertFalse(any(k.startswith('OPENRACKET_') for k in e))
        self.assertNotIn('PLTCOLLECTS', e)
        self.assertNotIn('PYTHONOPTIMIZE', e)
        self.assertEqual(e['PLTCOMPILEDROOTS'], '/fresh/cache:')

    def test_actual_tmpdir_alias_requested_is_used(self):
        if os.environ.get('REQUIRE_ALIASED_TMPDIR') == '1':
            alias = Path(os.environ['TMPDIR'])
            self.assertTrue(alias.is_symlink())
            with tempfile.TemporaryDirectory() as temp:
                self.assertTrue(Path(temp).resolve().is_relative_to(alias.resolve()))

    def test_workflow_only_public_standard_readonly_focused_batch(self):
        workflow = (ROOT.parent / '.github/workflows/retained-native.yml').read_text()
        for required in ('runs-on: macos-15', 'contents: read', 'persist-credentials: false', "github.event.repository.private == false", "github.event.repository.visibility == 'public'", 'group: retained-drracket-native', 'run-light-caret.py prepare', 'run-light-caret.py cases', 'run-light-caret.py verify'):
            self.assertIn(required, workflow)
        for refused in ('contents: write', 'upload-artifact', 'actions/cache', 'continue-on-error', 'run-light-tools.py', 'run-launcher-isolation.py', 'self-hosted', 'macos-15-large'):
            self.assertNotIn(refused, workflow)
        self.assertEqual(workflow.count("if: always() && steps.runtime.outcome == 'success'"), 2)
        self.assertNotIn('workflow_dispatch', workflow)

    def test_source_contract_registration_setup_and_native_scope(self):
        node = next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.ClassDef))
        methods = {n.name: ast.get_source_segment(SOURCE, n) for n in node.body if isinstance(n, ast.FunctionDef)}
        for flag in ('--no-setup', '--deps', '--copy', '--link', '--avoid-main', '--no-docs', '--no-launcher', '--no-foreign-libs', '--no-install', '--no-post-install'):
            self.assertIn(repr(flag), methods['fresh_addon'])
        self.assertNotIn("'--auto'", methods['fresh_addon'])
        self.assertNotIn("'-U'", methods['fresh_addon'])
        self.assertIn('verify-modern-tool-registration.rkt', methods['fresh_addon'])
        self.assertIn("self.env(arm, 'setup')", methods['prepare_arm'])
        self.assertIn("self.env(arm, 'compile')", methods['prepare_arm'])
        self.assertIn("self.env(arm, 'native')", methods['native_arm'])
        self.assertIn('len(modules) == 22', methods['prepare_arm'])
        self.assertIn("('reader', 30", methods['prepare_arm'])
        self.assertIn("('compile', 180", methods['prepare_arm'])
        self.assertIn('self.v.PREFLIGHTS', methods['prepare_arm'])
        self.assertIn("OPENRACKET_NATIVE_CASE='macro-stepper'", methods['native_arm'])
        self.assertIn("s['started_monotonic'] + 60", methods['native_arm'])
        self.assertNotIn('memory-profile.rkt', methods['native_arm'])
        self.assertNotIn('preferences:set', SOURCE)
        self.assertLess(methods['verify'].index('self.witness('), methods['verify'].index('self.safety.safe()'))

class SupervisorTests(unittest.TestCase):
    def runner(self, root):
        r = A.Runner.__new__(A.Runner)
        r.ci, r.root, r.support, r.exp, r.source = CI, ROOT, CI / 'light-caret-support', EXP, ACCEPTED
        r.temp, r.work, r.reports = root, root / 'work', root / 'reports'
        r.work.mkdir(); r.reports.mkdir()
        r.safety = C.Safety(r.reports / 'safety.json')
        r.safety.initialize()
        r.state = {'prepared': {'original': True, 'patched': True}, 'official_runtime_sha256': 'a' * 64, 'rows': [], 'matrix': [], 'witnesses': {}}
        r.state_file = r.reports / 'state.json'
        r.app, r.light, r.v = APP, LIGHT, V
        r.command_index = 0
        r.terminate_group = lambda p: setattr(p, 'returncode', -15)
        r.live_group_members = lambda pid: []
        return r

    def test_real_execute_python_is_bounded_and_durable(self):
        # This starts Python only, never Racket or a native GUI.
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            row = r.execute('portable command', [sys.executable, '-c', 'print("portable-only")'], os.environ.copy(), 5)
            self.assertEqual(row['exit_code'], 0)
            self.assertEqual(row['stdout'], 'portable-only\n')
            self.assertFalse(row['forced_cleanup'])
            self.assertTrue(row['cleanup_verified'])
            C.Safety(r.safety.path).safe()

    def test_spawn_error_is_durable_prelaunch_block(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            row = r.execute('missing fixture', ['/does-not-exist-caret-fixture'], {}, 1, required=False)
            self.assertIn('error', row)
            with self.assertRaises(ValueError):
                C.Safety(r.safety.path).safe()
            with mock.patch.object(A.subprocess, 'Popen') as popen:
                r.execute('later blocked', [sys.executable], {}, 1, required=False)
                popen.assert_not_called()

    def test_state_write_failures_cleanup_owned_process_then_block_restart(self):
        for stage in ('spawned', 'finish'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                r = self.runner(Path(temp))
                owned = []
                cleanup_calls = []
                actual_cleanup = r.cleanup
                def cleanup(p):
                    cleanup_calls.append(p.pid)
                    return actual_cleanup(p)
                r.cleanup = cleanup
                class Process:
                    def __init__(self, *args, **kwargs):
                        self.pid, self.returncode = 55667, None
                        owned.append(self)
                    def wait(self, timeout):
                        self.returncode = 0
                        return 0
                    def poll(self):
                        return self.returncode
                def fail(*args):
                    r.safety.path.with_name('safety.json.pending').write_text('{partial')
                    raise OSError('synthetic durable state write failure')
                with mock.patch.object(A.subprocess, 'Popen', Process), mock.patch.object(r.safety, stage, fail):
                    row = r.execute('state write fixture', ['fixture'], {}, 1, required=False)
                self.assertTrue(cleanup_calls)
                self.assertIsNotNone(owned[0].returncode)
                self.assertTrue(row['cleanup_verified'])
                self.assertIn('error', row)
                with self.assertRaises(ValueError):
                    C.Safety(r.safety.path).safe()
                with mock.patch.object(A.subprocess, 'Popen') as launch:
                    r.execute('later must not spawn', ['fixture'], {}, 1, required=False)
                    launch.assert_not_called()

    def test_invalid_utf8_raw_bytes_are_retained_and_fail_decoding_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            row = r.execute('binary fixture', [sys.executable, '-c', 'import os; os.write(1, bytes([255,13,10,0])); os.write(2,b"stderr\\r\\n")'], os.environ.copy(), 5, required=False)
            command = r.reports / 'commands/command-0001'
            self.assertEqual((command / 'stdout.txt').read_bytes(), bytes([255,13,10,0]))
            self.assertEqual((command / 'stderr.txt').read_bytes(), b'stderr\r\n')
            self.assertIn('not UTF-8', row['error'])
            self.assertEqual(row['stdout_sha256'], C.sha(command / 'stdout.txt'))

    def test_failed_setup_partial_command_transport_keeps_later_streams(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            first = r.reports / 'commands/command-0001'; first.mkdir(parents=True)
            (first / 'stdout.txt').write_bytes(b'partial failed setup')
            (first / 'stderr.txt').write_bytes(b'actual setup failure')
            second = r.reports / 'commands/command-0002'; second.mkdir()
            for name in ('supervisor.json', 'stdout.txt', 'stderr.txt'):
                (second / name).write_bytes(b'independent later command')
            emitted = []
            def emit(path, label):
                emitted.append(label)
                if label == 'command-0001-stdout-txt':
                    raise ValueError('synthetic transport failure')
            r.emit_file = emit
            with self.assertRaises(ValueError):
                r.verify()
            self.assertIn('command-0001-stderr-txt', emitted)
            self.assertIn('command-0002-supervisor-json', emitted)
            self.assertIn('command-0002-stdout-txt', emitted)
            self.assertIn('command-0002-stderr-txt', emitted)
            row = next(v for v in r.state['rows'] if v['name'] == 'Complete independent evidence transport')
            self.assertFalse(row['passed'])
            self.assertIn('command-0001-supervisor-json: missing/incomplete', row['detail'])

    def test_prepare_runs_all12_direct_controls_and_preserves_failed_first(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            r.stock = Path(temp) / 'stock'
            proof, runtime, folder = r.arm_paths('original')
            proof.mkdir(); folder.mkdir()
            C.write(folder / 'composition.json', {'files': V.expected_composition('original')})
            r.witness = lambda *args: 'a' * 64
            r.fresh_addon = lambda *args: None
            direct = []
            def execute(name, argv, e, timeout, required=True, **kwargs):
                base = {'exit_code': 0, 'timed_out': False, 'timeout_seconds': timeout, 'stdout': '', 'stderr': '', 'cleanup_verified': True, 'forced_cleanup': False}
                if len(argv) > 5 and Path(str(argv[5])).name in {s[0] for s in V.PREFLIGHTS}:
                    index = len(direct)
                    direct.append((argv, timeout))
                    base.update(T.preflights()[index])
                    if index == 0:
                        base['stdout'] = 'synthetic failed first control\n'
                return base
            r.execute = execute
            with mock.patch.object(A.C, 'independent_copy'), mock.patch.object(A.C, 'check_members'), self.assertRaises(ValueError):
                r.prepare_arm('original')
            self.assertEqual(len(direct), 12)
            for (argv, timeout), spec in zip(direct, V.PREFLIGHTS):
                self.assertEqual(Path(str(argv[5])).name, spec[0])
                self.assertEqual(argv[6:], spec[1])
                self.assertEqual(timeout, 30)
                self.assertNotIn('raco', argv)
            self.assertEqual(len(json.loads((folder / 'preflights.json').read_text())), 12)

    def native_scenario(self, kind):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        r = self.runner(Path(temp.name))
        proof, runtime, folder = r.arm_paths('original')
        folder.mkdir(); proof.mkdir()
        comp = {'arm': 'original', 'accepted_input_members': 155, 'accepted_manifest_sha256': C.ACCEPTED_PIN, 'native_overlay_manifest_sha256': T.c.OVERLAY_SHA, 'product_changes': [], 'files': V.expected_composition('original')}
        C.write(folder / 'composition.json', comp)
        sha = C.sha(folder / 'composition.json')
        C.write(folder / 'build.json', [{'stage': stage, 'exit_code': 0, 'timed_out': False, 'timeout_seconds': bound, 'modules': V.required_racket_modules(), 'composition_sha256': sha} for stage, bound in [('reader', 30), ('compile', 180)]])
        C.write(folder / 'preflights.json', T.preflights())
        r.fresh_addon = lambda arm, label, e: Path(e['PLTUSERHOME']).mkdir()
        clock = [100.]
        def capture(path, deadline, token, e):
            if kind == 'capture-error':
                raise OSError('synthetic capture failure')
            path.write_bytes(T.png())
            clock[0] = 161. if kind == 'capture-late' else 111.
            return clock[0]
        r.capture = capture
        if kind == 'cleanup-error':
            r.live_group_members = lambda pid: [{'pid': pid}]
            r.terminate_group = lambda p: (_ for _ in ()).throw(RuntimeError('synthetic cleanup uncertainty'))
        class Process:
            def __init__(self, argv, env, stdout, stderr, **kwargs):
                if kind == 'spawn-error':
                    raise OSError('synthetic spawn uncertainty')
                self.pid = 98765
                self.returncode = None
                self.env = env
                report, output = T.native('original')
                Path(env['OPENRACKET_READY_FILE']).write_text('{partial' if kind == 'malformed' else json.dumps(report))
                stdout.write(output); stdout.flush()
            def poll(self):
                return self.returncode
            def wait(self, timeout):
                if kind in ('timeout', 'cleanup-error'):
                    clock[0] = 161.
                    raise subprocess.TimeoutExpired('synthetic', timeout)
                self.returncode = 0
                clock[0] = 161. if kind == 'late-exit' else 113.
                return 0
        original_write = Path.open
        def path_open(path, mode='r', *args, **kwargs):
            if kind == 'ack-error' and path.name == 'capture-ack':
                raise OSError('synthetic ACK failure')
            return original_write(path, mode, *args, **kwargs)
        with mock.patch.object(A.subprocess, 'Popen', Process), mock.patch.object(A.time, 'monotonic', lambda: clock[0]), mock.patch.object(A.C, 'check_members'), mock.patch.object(Path, 'open', path_open):
            try:
                ok = r.native_arm('original')
            except (ValueError, OSError, json.JSONDecodeError):
                ok = False
        return ok, json.loads((folder / 'supervisor.json').read_text()), r, folder

    def test_native_actual_supervisor_complete_timestamps_and_binding(self):
        ok, s, r, folder = self.native_scenario('success')
        self.assertTrue(ok)
        self.assertEqual(s['started_monotonic'], 100.)
        self.assertEqual(s['deadline_monotonic'], 160.)
        self.assertEqual(s['capture_completed_monotonic'], 111.)
        self.assertEqual(s['ack_monotonic'], 111.)
        self.assertEqual(s['exited_monotonic'], 113.)
        self.assertEqual(s['private_launch_context_sha256'], C.sha(folder / 'launch-context.json'))
        self.assertEqual(s['process_id'], 98765)
        C.Safety(r.safety.path).safe()

    def test_native_refuses_timeout_late_capture_ack_malformed_or_uncertain_cleanup(self):
        for kind in ('timeout', 'late-exit', 'capture-late', 'capture-error', 'ack-error', 'malformed', 'cleanup-error', 'spawn-error'):
            with self.subTest(kind=kind):
                ok, s, r, folder = self.native_scenario(kind)
                self.assertFalse(ok)
                self.assertEqual(s['timeout_seconds'], 60)
                self.assertEqual(s['deadline_monotonic'], 160.)
                self.assertTrue((folder / 'stdout.txt').exists())
                self.assertTrue((folder / 'stderr.txt').exists())
                if kind in ('cleanup-error', 'spawn-error'):
                    with self.assertRaises(ValueError):
                        C.Safety(r.safety.path).safe()
                if kind in ('capture-late', 'capture-error', 'malformed'):
                    self.assertFalse((folder / 'capture-ack').exists())

    def test_independent_second_arm_runs_after_first_isolated_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            calls = []
            def arm(name):
                calls.append(name)
                if name == 'original':
                    raise ValueError('synthetic isolated failure')
                return True
            r.native_arm = arm
            with self.assertRaises(ValueError):
                r.cases()
            self.assertEqual(calls, ['original', 'patched'])
            self.assertFalse(r.state['matrix'][0]['passed'])
            self.assertTrue(r.state['matrix'][1]['passed'])

    def test_unconditional_witnesses_continue_despite_failure_and_block(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            r.state['witnesses'] = {'first': '/fixture1', 'second': '/fixture2'}
            calls = []
            def witness(name, path, final=False):
                calls.append(name)
                if name == 'first':
                    raise ValueError('synthetic failed witness')
                return True
            r.witness = witness
            r.emit_file = lambda *args: None
            r.safety.begin('unresolved', 'command')
            with self.assertRaises(ValueError):
                r.verify()
            self.assertEqual(calls, ['first', 'second'])
            self.assertTrue((r.reports / 'summary.md').exists())

    def test_final_source_and_runtime_mutations_are_observable(self):
        with tempfile.TemporaryDirectory() as temp:
            r = self.runner(Path(temp))
            source = Path(temp) / 'immutable'; source.mkdir()
            (source / 'file').write_bytes(b'before')
            before = r.witness('fixture', source)
            (source / 'file').write_bytes(b'after')
            self.assertFalse(r.witness('fixture', source, final=True))
            summary = json.loads((r.reports / 'fixture-witness.json').read_text())
            self.assertEqual(len(summary['changes']), 1)
            self.assertEqual(summary['before_tree_sha256'], before)
            self.assertNotIn(str(source), json.dumps(summary))

class TransportTests(unittest.TestCase):
    def log(self, root, arm, name, data):
        source = root / name; source.write_bytes(data)
        wrapper = root / ('evidence-caret-' + arm + '-' + name.replace('.', '-')) / 'supervisor.json'
        wrapper.parent.mkdir()
        wrapper.write_text(json.dumps(LIGHT.wrap_bytes(source)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            EMIT.emit(wrapper)
        return out.getvalue()

    def test_lossless_png_raw_stream_and_partial_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logs = self.log(root, 'original', 'capture.png', T.png()) + self.log(root, 'patched', 'stderr.txt', bytes(range(256)) * 500)
            result = D.decode(logs, root / 'decoded')
            self.assertEqual((root / 'decoded/original/capture.png').read_bytes(), T.png())
            self.assertEqual((root / 'decoded/patched/stderr.txt').read_bytes(), bytes(range(256)) * 500)
            self.assertEqual(result['programmatic_validation'], 'not run')
            self.assertEqual(result['visual_review'], 'pending')
            self.assertIn('ready.json', result['missing']['original'])
            with self.assertRaises(ValueError):
                D.decode(logs, root / 'decoded')

    def test_repeated_truncated_corrupt_transport_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = self.log(root, 'original', 'capture.png', T.png())
            for index, bad in enumerate((log + log, log.rsplit('OPENRACKET_REPLAY_DOCUMENT_END', 1)[0], log.replace('"bytes":69', '"bytes":70'))):
                # Explicit corruption independent of encoded PNG fixture length.
                if index == 2:
                    bad = log.replace('"sha256":"', '"sha256":"bad', 1)
                with self.assertRaises((ValueError, AssertionError, KeyError)):
                    D.decode(bad, root / ('bad-' + str(index)))

    def test_complete_pair_decoder_does_not_claim_pixel_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logs = ''
            writer = T.PairTests()
            for arm in C.ARMS:
                source = root / ('source-' + arm)
                writer.write_synthetic_arm(source, arm)
                for name in C.FILES:
                    transport = root / ('transport-' + arm + '-' + name.replace('.', '-')); transport.mkdir()
                    logs += self.log(transport, arm, name, (source / name).read_bytes())
            D.decode(logs, root / 'decoded')
            result = D.validate(root / 'decoded', EXP)
            self.assertEqual(result['status'], 'accepted')
            self.assertEqual(result['visual_review'], 'pending')
            self.assertEqual(result['rendered_state_acceptance'], 'pending-independent-visual-review')

if __name__ == '__main__':
    unittest.main(verbosity=2)
