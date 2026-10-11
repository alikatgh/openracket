#!/usr/bin/env python3
"""Pure orchestration fixtures; these are not native acceptance evidence."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

CI = Path(__file__).resolve().parent
ROOT = CI.parents[1]
SPEC = importlib.util.spec_from_file_location('functional_cases', CI / 'run-functional-phase.py')
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
WORKFLOW = (ROOT.parent / '.github/workflows/retained-native.yml').read_text()


class FunctionalCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []

    def put(self, relative, value):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))
        return p

    def run_group(self, group, code=0, action=None, phase="cases"):
        def invoke(argv):
            self.calls.append(argv)
            if action:
                return action()
            return code
        with contextlib.redirect_stdout(io.StringIO()):
            return F.run_phase(self.root, group, phase, invoke)

    def light_receipt(self, **overrides):
        value = dict(cleanup_verified=True, cleanup_error=None, exit_code=0,
                     timed_out=False, forced_cleanup=False, supervisor_error=None)
        value.update(overrides)
        return self.put('reports/light-tools-ci/tools-stock-debugger/supervisor.json', value)

    def state(self, group):
        return json.loads((self.root / ('reports/functional-ci/' + group + '-cases.json')).read_text())

    def test_success_runs_exact_adapters_with_independent_states(self):
        self.assertEqual(self.run_group('light'), 0)
        self.assertEqual(self.run_group('quit'), 0)
        self.assertEqual(self.calls, [[sys.executable, str(self.root / 'scripts/ci' / name), 'cases']
                                     for name in ('run-light-tools.py', 'run-native-quit.py')])
        for group in ('light', 'quit'):
            self.assertIs(self.state(group)['cleanup_safe'], True)
            self.assertEqual(self.state(group)['status'], 'completed')

    def test_cleaned_assertion_failure_stays_red_but_does_not_block_quit(self):
        self.light_receipt()
        self.put('reports/light-tools-ci/results.json', [
            {'name': 'tools-stock-debugger owned-process cleanup', 'passed': True},
            {'name': 'tools-stock-debugger native real-tool gate', 'passed': False}])
        self.assertEqual(self.run_group('light', 7), 7)
        self.assertEqual(self.run_group('quit'), 0)
        self.assertEqual(self.state('light')['adapter_exit_code'], 7)
        self.assertIs(self.state('light')['cleanup_safe'], True)

    def test_failure_only_verified_cleanup_allows_independent_later_group(self):
        self.light_receipt(exit_code=-9, timed_out=True, forced_cleanup=True)
        self.assertEqual(self.run_group('light', 1), 1)
        self.assertEqual(self.run_group('quit'), 0)

    def test_light_cleanup_refusal_blocks_later_gui_even_if_child_returns_zero(self):
        def unsafe():
            self.light_receipt(cleanup_verified=False, cleanup_error='owned survivor', exit_code=None)
            return 0
        self.assertEqual(self.run_group('light', action=unsafe), 1)
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIs(self.state('light')['cleanup_safe'], False)
        self.assertEqual(self.state('quit')['status'], 'blocked')

    def test_missing_native_supervisor_receipt_fails_closed(self):
        p = self.root / 'reports/light-tools-ci/tools-stock-debugger'
        p.mkdir(parents=True)
        (p / 'stdout.txt').write_text('partial native launch')
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(self.calls, [])

    def test_malformed_or_symlink_native_receipt_fails_closed(self):
        p = self.light_receipt()
        p.write_text('{broken')
        self.assertTrue(F.safety_reasons(self.root))
        p.unlink()
        p.symlink_to(self.root / 'missing')
        self.assertTrue(F.safety_reasons(self.root))

    def test_durable_cleanup_row_survives_failed_supervisor_write(self):
        self.put('reports/light-tools-ci/results.json', [
            {'name': 'tools-stock-debugger owned-process cleanup', 'passed': False}])
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(self.calls, [])

    def test_quit_original_block_marker_blocks_light_without_modification(self):
        p = self.put('reports/native-quit-ci/launch-blocked.json', {'reason': 'default handler unknown'})
        before = p.read_bytes()
        self.assertEqual(self.run_group('light'), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(p.read_bytes(), before)

    def test_quit_cleanup_error_row_also_blocks_if_marker_write_failed(self):
        self.put('reports/native-quit-ci/results.json', [
            {'name': 'setup failure-only outer cleanup', 'passed': False}])
        self.assertEqual(self.run_group('light'), 1)
        self.assertEqual(self.calls, [])

    def test_outer_cancellation_running_marker_blocks_later_launch(self):
        def cancel():
            self.assertEqual(self.state('light')['status'], 'running')
            raise KeyboardInterrupt('simulate outer runner termination')
        with self.assertRaises(KeyboardInterrupt):
            self.run_group('light', action=cancel)
        self.assertEqual(self.state('light')['status'], 'running')
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(len(self.calls), 1)

    def test_adapter_exception_remains_unresolved_and_blocks_later_launch(self):
        def failed_spawn():
            raise OSError('cannot start adapter')
        self.assertEqual(self.run_group('light', action=failed_spawn), 1)
        self.assertEqual(self.state('light')['status'], 'unresolved')
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(len(self.calls), 1)

    def test_adapter_signal_is_not_a_cleaned_assertion_failure(self):
        self.assertEqual(self.run_group('light', -15), 1)
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(len(self.calls), 1)

    def test_no_implicit_retry_or_overwrite_of_original_phase_state(self):
        self.assertEqual(self.run_group('light', 1), 1)
        before = self.state('light')
        with self.assertRaisesRegex(RuntimeError, 'already attempted'):
            self.run_group('light')
        self.assertEqual(before, self.state('light'))
        self.assertEqual(len(self.calls), 1)

    def test_atomic_final_write_failure_keeps_running_marker(self):
        calls = []
        original = F.write_state
        def write(path, value):
            calls.append(value['status'])
            if value['status'] == 'completed':
                raise OSError('synthetic final write failure')
            original(path, value)
        with mock.patch.object(F, 'write_state', write), self.assertRaises(OSError):
            self.run_group('light')
        self.assertEqual(self.state('light')['status'], 'running')
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(calls, ['running', 'completed'])

    def test_wrong_typed_cleanup_values_are_not_success(self):
        for bad in (dict(cleanup_verified=1), dict(exit_code=True), dict(exit_code=None),
                    dict(cleanup_error='unknown')):
            with self.subTest(bad=bad):
                self.light_receipt(**bad)
                self.assertTrue(F.safety_reasons(self.root))

    def test_malformed_prior_phase_or_result_rows_fail_closed(self):
        p = self.put('reports/functional-ci/light-cases.json', {'status': 'completed'})
        self.assertTrue(F.safety_reasons(self.root))
        p.unlink()
        self.put('reports/light-tools-ci/results.json', {'passed': True})
        self.assertTrue(F.safety_reasons(self.root))

    def test_phase_schema_is_exact_integer_one(self):
        for schema in (True, 1.0, '1', 2):
            with self.subTest(schema=schema):
                self.put('reports/functional-ci/light-prepare.json',
                         dict(schema=schema, group='light', phase='prepare', status='completed', cleanup_safe=True))
                self.assertTrue(F.safety_reasons(self.root))

    def test_interrupted_preparation_blocks_all_later_native_phases(self):
        def cancel():
            raise KeyboardInterrupt('preparation outer timeout')
        with self.assertRaises(KeyboardInterrupt):
            self.run_group('light', action=cancel, phase='prepare')
        path = self.root / 'reports/functional-ci/light-prepare.json'
        before = path.read_bytes()
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.calls), 1)

    def test_terminal_non_timeout_light_compile_failure_allows_quit(self):
        self.put('reports/light-tools-ci/command-001/supervisor.json',
                 dict(exit_code=1, timed_out=False, name='stock compile'))
        self.assertEqual(self.run_group('light', 1, phase='prepare'), 1)
        self.assertEqual(self.run_group('quit'), 0)
        self.assertEqual(len(self.calls), 2)

    def test_light_command_timeout_receipt_blocks_later_gui(self):
        def timeout():
            self.put('reports/light-tools-ci/command-001/supervisor.json',
                     dict(exit_code=-9, timed_out=True, name='stock compile'))
            return 1
        self.assertEqual(self.run_group('light', action=timeout, phase='prepare'), 1)
        path = self.root / 'reports/functional-ci/light-prepare.json'
        first_cause = path.read_bytes()
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(path.read_bytes(), first_cause)
        self.assertEqual(len(self.calls), 1)

    def test_light_cleanup_exception_without_command_receipt_blocks(self):
        (self.root / 'reports/light-tools-ci/command-001').mkdir(parents=True)
        self.assertEqual(self.run_group('quit'), 1)
        self.assertEqual(self.calls, [])

    def test_missing_partial_or_timed_out_preflights_after_compile_block(self):
        self.put('reports/light-tools-ci/results.json', [
            {'name': 'stock compile all15 and accepted runtime-path dependencies', 'passed': True}])
        self.assertTrue(F.safety_reasons(self.root))
        controls = [dict(exit_code=0, timed_out=False) for _ in range(9)]
        self.put('reports/light-tools-ci/stock-preflights.json', controls[:-1])
        self.assertTrue(F.safety_reasons(self.root))
        controls[1]['timed_out'] = True
        self.put('reports/light-tools-ci/stock-preflights.json', controls)
        self.assertTrue(F.safety_reasons(self.root))
        controls[1]['timed_out'] = False
        self.put('reports/light-tools-ci/stock-preflights.json', controls)
        self.assertEqual(F.safety_reasons(self.root), [])

    def test_complete_non_timeout_negative_controls_do_not_block_independence(self):
        self.put('reports/light-tools-ci/stock-preflights.json',
                 [dict(exit_code=1 if i % 2 else 0, timed_out=False) for i in range(9)])
        self.assertEqual(self.run_group('light', 1, phase='prepare'), 1)
        self.assertEqual(self.run_group('quit'), 0)

    def test_quit_prepare_terminal_compile_failure_does_not_hide_light(self):
        def fail():
            self.put('reports/native-quit-ci/results.json', [
                {'name': 'Explicit generator compile', 'passed': False, 'detail': 'exit=1'},
                {'name': 'prepare orchestration', 'passed': False, 'detail': 'compile failed'}])
            return 1
        self.assertEqual(self.run_group('quit', action=fail, phase='prepare'), 1)
        self.assertEqual(self.run_group('light'), 0)

    def test_quit_prepare_unrecorded_native_query_failure_is_unresolved(self):
        def fail():
            self.put('reports/native-quit-ci/results.json', [
                {'name': 'original runtime baseline', 'passed': True, 'detail': ''},
                {'name': 'prepare orchestration', 'passed': False, 'detail': 'query interrupted'}])
            return 1
        self.assertEqual(self.run_group('quit', action=fail, phase='prepare'), 1)
        self.assertEqual(self.run_group('light'), 1)
        self.assertEqual(len(self.calls), 1)

    def test_subprocess_inherits_streams_environment_and_original_deadlines(self):
        with mock.patch.object(F.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(F.run_phase(self.root, 'light', 'cases'), 0)
        self.assertEqual(run.call_args.kwargs, {})
        source = (CI / 'run-functional-phase.py').read_text()
        self.assertNotIn('killpg', source)
        self.assertNotIn('terminate_group', source)

    def test_cli_exact_dispatch_and_refuses_other_command(self):
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
               'GITHUB_REF': 'refs/heads/prototype/retained-drracket'}
        args = ['wrapper', 'light', 'cases', '--', 'python3', 'retained-host/scripts/ci/run-light-tools.py', 'cases']
        with mock.patch.dict(F.os.environ, env), mock.patch.object(F.platform, 'system', return_value='Darwin'), \
                mock.patch.object(F.platform, 'machine', return_value='arm64'), mock.patch.object(F.sys, 'argv', args), \
                mock.patch.object(F, 'run_phase', return_value=3) as run:
            self.assertEqual(F.main(), 3)
            run.assert_called_once_with(ROOT, 'light', 'cases')
            args[-1] = 'verify'
            with self.assertRaises(SystemExit):
                F.main()

    def test_approved_adapters_are_byte_identical(self):
        pins = {'run-light-tools.py': 'edaa187aa3dbb3ced85f0f4f6ab441c242cd416c15abc60b3ad5d3e255d91f8c',
                'run-native-quit.py': '61e3328bb320a243f0bf47d75069449de6cd85c29b19374c512358914b30c441'}
        for name, expected in pins.items():
            self.assertEqual(hashlib.sha256((CI / name).read_bytes()).hexdigest(), expected)

    def test_workflow_single_public_install_separate_red_phases_and_clocks(self):
        self.assertEqual(WORKFLOW.count('run: bash retained-host/scripts/ci/install-full-racket.sh'), 1)
        for text in ('runs-on: macos-15', 'contents: read', 'persist-credentials: false',
                     "github.event.repository.private == false", "github.event.repository.visibility == 'public'",
                     'cancel-in-progress: false', 'timeout-minutes: 200'):
            self.assertIn(text, WORKFLOW)
        for forbidden in ('continue-on-error', 'upload-artifact', 'actions/cache', 'contents: write', 'workflow_dispatch'):
            self.assertNotIn(forbidden, WORKFLOW)
        names = ['quit_prepare', 'light_prepare', 'light_cases', 'quit_cases', 'light_verify', 'quit_verify']
        positions = [WORKFLOW.index('id: ' + name) for name in names]
        self.assertEqual(positions, sorted(positions))
        steps = WORKFLOW.split('      - name: ')[1:]
        for name, minutes in zip(names, [15, 20, 40, 70, 4, 5]):
            step = next(s for s in steps if 'id: ' + name + '\n' in s)
            self.assertIn('timeout-minutes: ' + str(minutes) + '\n', step)
            self.assertIn("always() && steps.runtime.outcome == 'success'", step)
            if name.endswith('verify'):
                self.assertNotIn('steps.light_', step)
                self.assertNotIn('steps.quit_', step)
                self.assertNotIn('run-functional-phase.py', step)
        self.assertEqual(sum(map(int, re.findall(r'^        timeout-minutes: (\d+)$', WORKFLOW, re.M))), 186)
        quit_step = next(s for s in steps if 'id: quit_cases\n' in s)
        self.assertNotIn('steps.light_', quit_step)
        self.assertIn("steps.quit_prepare.outcome == 'success'", quit_step)


if __name__ == '__main__':
    unittest.main(verbosity=2)
