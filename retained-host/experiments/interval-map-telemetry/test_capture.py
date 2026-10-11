"""Portable launcher and host-source contracts; never starts Racket or a GUI."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

import capture

HERE = Path(__file__).resolve().parent
SOURCE_PINS = {'stock_sha256': 'a' * 64, 'candidate_sha256': 'b' * 64}
APPROVED_PINS = {
    'memory-profile.rkt': '9b761799e61b45388ae21461d358a819274ae1923e88959351a9f9b46337abc0',
    'profile_setup.py': '9bb3dc30255a4effca1a91f2f407e0af3ae0fce298f2fc20ed823544176daddb',
    'supervise.py': '0505de6044b8e9c389088bf3714cd95a9c0bef501dadddf08d3617fbb5437b58',
}


def fixture_bytes():
    """The pinned ASCII fixture generator, used as data in Python-only tests."""
    size = 1048576
    header = '#lang racket/base\n; OpenRacket deterministic performance fixture v1\n'
    blocks, length, i, anchors = [header], len(header), 0, []
    while True:
        block = (f'; warm-input-target-{i:06d}: comments stay comments during synthetic typing\n'
                 f'(define (sample-{i:06d} x)\n'
                 '  (define message "a string with \\"escapes\\" and (parentheses)")\n'
                 '  (define pattern #rx"[a-z]+")\n'
                 '  (define data `((alpha ,x) (beta . 42) #(1 2 3)))\n'
                 '  (for/list ([n (in-range 12)] #:when (even? n))\n'
                 '    (list (+ x n) message pattern data #t #\\space)))\n\n')
        if length + len(block) + 7 > size:
            break
        anchors.append(length + len(f'; warm-input-target-{i:06d}: '))
        blocks.append(block)
        length += len(block)
        i += 1
    remaining = size - length
    blocks.append('#|' + ('x' * (remaining - 5)) + '|#\n')
    return ''.join(blocks).encode('ascii'), anchors[len(anchors) // 2]


def complete_evidence(arm):
    host = dict(status='gui_application_complete', arm=arm,
                edited_snapshot_sha256=capture.EDITED_SHA256,
                final_snapshot_sha256=capture.EDITED_SHA256,
                final_snapshot_characters=capture.EXPECTED_CHARACTERS,
                source_unchanged=True, lexer_valid_at_completion=True)
    worker = dict(child_limit_bytes=268435456, memory_accounting_available=True)
    summary = dict(records=[dict(request_id=1, snapshot_sha256=capture.EDITED_SHA256,
                                 snapshot_characters=capture.EXPECTED_CHARACTERS)],
                   matching_request_ids=[1], error_count=0, dropped_records=0)
    return {'capture-host.json': host, 'worker-init.json': worker,
            'gui-observation.json': summary,
            'worker-phase-1.json': {'job_id': 1, 'phase_points_enabled': False},
            'activation.json': dict(verified=True, arm=arm,
                source_sha256=SOURCE_PINS[arm + '_sha256'],
                expected_source_sha256=SOURCE_PINS[arm + '_sha256'],
                gui_module_already_instantiated=True, gui_phase0_import_verified=True,
                interval_map_already_instantiated=True, gui_handler_thread=True,
                phase_points_enabled=False, flag_value='1' if arm == 'candidate' else None,
                export_status='boolean' if arm == 'candidate' else 'missing',
                fast_set_enabled=True if arm == 'candidate' else None),
            'heartbeat.json': dict(joined=True, producer_exited=True, join_timed_out=False,
                outstanding_callbacks=0, dropped_records=0, error_count=0,
                period_ms=50.0, max_records=4096, records=[{}], handled_count=1, submitted_count=1)}


def write_evidence(output, rows):
    for filename, content in rows.items():
        (output / filename).write_text(json.dumps(content))


class LauncherContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_data, cls.anchor = fixture_bytes()

    def test_exact_approved_fixture_and_middle_comment_edit(self):
        self.assertEqual(len(self.fixture_data), 1048576)
        self.assertEqual(hashlib.sha256(self.fixture_data).hexdigest(), capture.BASE_SHA256)
        self.assertEqual(self.anchor, capture.EDIT_POSITION)
        self.assertEqual(self.fixture_data[self.anchor:self.anchor + 8], b'comments')
        edited = self.fixture_data[:self.anchor] + b'x' + self.fixture_data[self.anchor:]
        self.assertEqual(len(edited.decode('ascii')), 1048577)
        self.assertEqual(hashlib.sha256(edited).hexdigest(), capture.EDITED_SHA256)

    def test_approved_helpers_and_cleanup_are_byte_identical(self):
        for filename, pin in APPROVED_PINS.items():
            with self.subTest(filename=filename):
                self.assertEqual(hashlib.sha256((HERE / filename).read_bytes()).hexdigest(), pin)

    def launch(self, root, arm='stock', *, setup_verified=True, timeout=False,
               cleanup_complete=True, evidence=True, exit_code=0, launch_error=False):
        fixture = root / 'mixed-1mib.rkt'
        fixture.write_bytes(self.fixture_data)
        output = root / arm
        racket = root / 'runtime/bin/racket'
        setup_calls, launches, cleanup_calls = [], [], []

        def setup(args, env, directory, terminate):
            setup_calls.append((args, env.copy(), directory))
            self.assertEqual(args.racket, racket)
            self.assertEqual(args.memory_limit_mib, 256)
            self.assertEqual(args.profile_helper, HERE / 'memory-profile.rkt')
            self.assertEqual(list((output / 'profile').iterdir()), [])
            self.assertEqual(env['PLTUSERHOME'], str(output / 'profile'))
            self.assertEqual(env['PLTADDONDIR'], str(output / 'addon'))
            return {'verified': setup_verified, 'errors': [] if setup_verified else ['mock setup failure']}

        class Process:
            returncode = exit_code

            def wait(self, timeout):
                if timeout != 190:
                    raise AssertionError('GUI process budget changed')
                if launches[-1]['timeout']:
                    raise subprocess.TimeoutExpired('mocked GUI', timeout)
                return self.returncode

        def popen(command, **kwargs):
            self.assertTrue(setup_calls)
            self.assertTrue((output / 'profile/openracket-diagnostic-profile').is_file())
            self.assertEqual(command, [str(racket), str(HERE / 'capture-host.rkt')])
            self.assertIs(kwargs['stdin'], subprocess.DEVNULL)
            self.assertIs(kwargs['start_new_session'], True)
            launches.append(dict(command=command, timeout=timeout, **kwargs))
            if launch_error:
                raise OSError('mocked process launch error')
            if evidence:
                write_evidence(output, complete_evidence(arm))
            return Process()

        def cleanup(process, deadline):
            cleanup_calls.append(deadline)
            self.assertEqual(deadline, 105)
            return {'complete': cleanup_complete}

        inherited = {'OPENRACKET_EXPANSION_REPLAY': '1', 'OPENRACKET_EXPANSION_CAPTURE': '1',
                     'OPENRACKET_GUI_PHASE_POINTS': 'bad inherited flag',
                     'OPENRACKET_INTERVAL_MAP_FAST_SET': 'bad inherited candidate flag',
                     'OPENRACKET_UNKNOWN': 'unapproved inherited value', 'TEST_KEEP': 'yes'}
        with mock.patch.dict(os.environ, inherited, clear=True), \
             mock.patch.object(capture, 'read_source_pins', return_value=SOURCE_PINS), \
             mock.patch.object(capture, 'prepare_memory_profile', side_effect=setup), \
             mock.patch.object(capture.subprocess, 'Popen', side_effect=popen), \
             mock.patch.object(capture, 'cleanup_group', side_effect=cleanup), \
             mock.patch.object(capture.time, 'monotonic', return_value=100), \
             contextlib.redirect_stdout(io.StringIO()):
            status = capture.main(['--arm', arm, '--racket', str(racket), '--fixture', str(fixture),
                                   '--output', str(output)])
        self.assertEqual(fixture.read_bytes(), self.fixture_data)
        return status, json.loads((output / 'capture-supervisor.json').read_text()), setup_calls, launches, cleanup_calls

    def test_both_arms_clear_inherited_flags_and_use_same_gui_host(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for arm in ('stock', 'candidate'):
                with self.subTest(arm=arm):
                    status, report, setups, launches, cleanups = self.launch(root, arm)
                    self.assertEqual(status, 0)
                    self.assertEqual(report['status'], 'gui_application_complete')
                    self.assertEqual(len(setups), 1)
                    self.assertEqual(len(launches), 1)
                    self.assertEqual(len(cleanups), 1)
                    self.assertEqual(report['expected_memory_limit_bytes'], 268435456)
                    env = launches[0]['env']
                    expected = {
                        'OPENRACKET_GUI_OBSERVER': '1',
                        'OPENRACKET_GUI_OBSERVER_SUPPORT': str(HERE / 'gui-observer.rkt'),
                        'OPENRACKET_GUI_PHASE_SUPPORT': str(HERE / 'gui-phase.rkt'),
                        'OPENRACKET_GUI_OBSERVER_OUTPUT': str(root / arm),
                        'OPENRACKET_GUI_EXPECTED_SHA256': capture.EDITED_SHA256,
                        'OPENRACKET_GUI_EXPECTED_SOURCE': str(root / 'mixed-1mib.rkt'),
                        'OPENRACKET_GUI_EXPECTED_CHARACTERS': '1048577',
                        'OPENRACKET_CAPTURE_CONFIG': env['OPENRACKET_CAPTURE_CONFIG'],
                    }
                    if arm == 'candidate':
                        expected['OPENRACKET_INTERVAL_MAP_FAST_SET'] = '1'
                    self.assertEqual({k: v for k, v in env.items() if k.startswith('OPENRACKET_')}, expected)
                    self.assertEqual(env['TEST_KEEP'], 'yes')
                    self.assertEqual(setups[0][1], env)
                    self.assertEqual(json.loads(env['OPENRACKET_CAPTURE_CONFIG']), {
                        'fixture': str(root / 'mixed-1mib.rkt'), 'output': str(root / arm),
                        'edit_position': 524139, 'arm': arm,
                        'expected_interval_map_source_sha256': SOURCE_PINS[arm + '_sha256']})
                    self.assertEqual(set(report['cleared_inherited_openracket_keys']), {
                        'OPENRACKET_EXPANSION_REPLAY', 'OPENRACKET_EXPANSION_CAPTURE',
                        'OPENRACKET_GUI_PHASE_POINTS', 'OPENRACKET_INTERVAL_MAP_FAST_SET', 'OPENRACKET_UNKNOWN'})
                    self.assertFalse((root / arm / 'capture.rktd').exists())

    def test_failed_setup_never_starts_gui_or_creates_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            status, report, setups, launches, cleanups = self.launch(root, setup_verified=False)
            self.assertEqual(status, 1)
            self.assertEqual(report['status'], 'setup_failed')
            self.assertFalse(report['gui_started'])
            self.assertEqual(launches, [])
            self.assertEqual(cleanups, [])
            self.assertFalse((root / 'stock/profile/openracket-diagnostic-profile').exists())

    def test_timeout_bad_exit_missing_evidence_and_cleanup_all_fail(self):
        for options in ({'timeout': True}, {'exit_code': 1}, {'evidence': False},
                        {'cleanup_complete': False}, {'launch_error': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                status, report, _, launches, cleanups = self.launch(Path(directory).resolve(), **options)
                self.assertEqual(status, 1)
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(len(launches), 1)
                self.assertEqual(len(cleanups), 0 if options.get('launch_error') else 1)

    def test_arm_is_required_and_only_two_choices(self):
        for args in ([], ['--arm', 'replay'], ['--arm', 'normal']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as caught:
                capture.main(args)
            self.assertEqual(caught.exception.code, 2)

    def test_bad_fixture_and_existing_output_fail_before_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fixture = root / 'fixture.rkt'
            output = root / 'output'
            for data, existing_output in ((b'wrong fixture', False), (self.fixture_data, True)):
                fixture.write_bytes(data)
                if existing_output:
                    output.mkdir()
                with mock.patch.object(capture, 'prepare_memory_profile') as setup, \
                     contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    capture.main(['--arm', 'stock', '--racket', str(root / 'racket'),
                                  '--fixture', str(fixture), '--output', str(output)])
                setup.assert_not_called()

    def test_bounded_json_rejects_large_symlink_nonfinite_and_nonobject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'evidence.json'
            for text, size in ((' ' * 11, 10), ('{"x": NaN}', 100), ('{"x": 1e309}', 100),
                               ('[]', 100), ('', 100)):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        capture.read_bounded_json(path, size)
            path.write_text('{}')
            link = root / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                capture.read_bounded_json(link, 100)

    def test_both_arms_need_postterminal_worker_identity_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('stock', 'candidate'):
                rows = complete_evidence(arm)
                rows.pop('worker-phase-1.json', None)
                write_evidence(root, rows)
                errors = capture.check_host_evidence(root, arm)
                self.assertTrue(errors)

    def test_worker_report_must_use_selected_phase_points_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('stock', 'candidate'):
                rows = complete_evidence(arm)
                rows['worker-phase-1.json']['phase_points_enabled'] = True
                write_evidence(root, rows)
                self.assertTrue(capture.check_host_evidence(root, arm))

    def test_host_completion_memory_and_unique_request_proof_fail_closed(self):
        mutations = [
            lambda r: r['capture-host.json'].update(status='terminal_captured'),
            lambda r: r['capture-host.json'].update(arm='candidate'),
            lambda r: r['capture-host.json'].update(source_unchanged=False),
            lambda r: r['capture-host.json'].update(lexer_valid_at_completion=False),
            lambda r: r['capture-host.json'].update(final_snapshot_sha256='wrong'),
            lambda r: r['worker-init.json'].update(child_limit_bytes=134217728),
            lambda r: r['worker-init.json'].update(memory_accounting_available=False),
            lambda r: r['gui-observation.json'].update(matching_request_ids=[]),
            lambda r: r['gui-observation.json'].update(matching_request_ids=[1, 2]),
            lambda r: r['gui-observation.json']['records'].append(copy.deepcopy(r['gui-observation.json']['records'][0])),
            lambda r: r['gui-observation.json'].update(error_count=1),
            lambda r: r['gui-observation.json'].update(dropped_records=1),
            lambda r: r['gui-observation.json'].update(error_count=False),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    rows = complete_evidence('stock')
                    mutation(rows)
                    write_evidence(root, rows)
                    self.assertTrue(capture.check_host_evidence(root, 'stock'))


class HostStaticContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (HERE / 'capture-host.rkt').read_text()

    def test_scalar_accessor_import_no_serialized_capture_or_replay_execution(self):
        self.assertIn('(only-in "gui-observer.rkt" digest observer-summary)', self.source)
        for forbidden in ('"support.rkt"', '"replay.rkt"', 'capture.rktd', 'capture-summary.json',
                          '(place-channel-put', '(collect-garbage', '(thread ', '(sleep ',
                          'preferences:set'):
            self.assertNotIn(forbidden, self.source)

    def test_original_gui_behavior_and_pending_settings_are_preserved(self):
        snippets = ['(dynamic-require \'drracket/drracket #f)', '(send frame resize 1200 820)',
                    '(send canvas focus)', '(send frame change-to-file fixture)',
                    '(send editor set-position pos)', '(send editor scroll-to-position pos)',
                    '(send editor on-char (new key-event% [key-code #\\x]))',
                    '(define next-settings (send editor get-next-settings))',
                    '(get-lang next-settings) marshall-settings (get-settings next-settings)']
        offsets = [self.source.index(s) for s in snippets]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("(prefs-get 'drracket:child-only-memory-limit)", self.source)
        self.assertIn("(prefs-get 'drracket:online-compilation-default-on)", self.source)
        self.assertIn("(prefs-get 'framework:coloring-active)", self.source)

    def test_one_original_absolute_deadline_includes_every_postedit_gate(self):
        self.assertEqual(self.source.count('90000'), 2)  # Frame gate plus post-edit gate.
        self.assertEqual(self.source.count('(define deadline '), 1)
        self.assertNotIn('(set! deadline', self.source)
        deadline = self.source.index('(define deadline ')
        wait = self.source.index('(define completed-record', deadline)
        final = self.source.index("(hash-set! report 'status \"gui_application_complete\")", wait)
        for snippet in ['(complete-observation)', '(actual-worker-ready?)', '(worker-report-ready?)',
                        '(send editor is-lexer-valid?)', '(pause .02)',
                        '(>= (current-inexact-monotonic-milliseconds) deadline)']:
            self.assertIn(snippet, self.source[wait:final])
        self.assertIn('(< (current-inexact-monotonic-milliseconds) deadline)', self.source[wait:final])
        self.assertIn('(gui-yield (alarm-evt', self.source)

    def test_distinct_endpoint_timestamps_and_strict_currentness(self):
        for name in ('terminal_received_monotonic_ms', 'terminal_callback_enter_monotonic_ms',
                     'terminal_callback_return_monotonic_ms', 'application_complete_monotonic_ms',
                     'first_final_lexer_valid_observed_monotonic_ms'):
            self.assertIn(name, self.source)
        for expr in ["(eq? (hash-ref record 'terminal_callback_current #f) #t)",
                     "(eq? (hash-ref record 'application_current #f) #t)",
                     "(eq? (hash-ref record 'application_cancelled 'missing) #f)",
                     "(zero-count? (hash-ref record 'stale_application_events #f))",
                     "(zero-count? (hash-ref record 'point_duplicates #f))",
                     "(positive-count? (hash-ref monitor 'trace_entries #f))",
                     "(positive-count? (hash-ref monitor 'rename_capability_rows #f))",
                     "(zero-count? (hash-ref monitor 'error_messages #f))",
                     "(zero-count? (hash-ref monitor 'invalid_payloads #f))",
                     "(zero-count? (hash-ref summary 'error_count #f))",
                     "(zero-count? (hash-ref summary 'dropped_records #f))",
                     '(equal? (hash-ref terminal \'tag #f) "handler-results")',
                     '(= (length ids) 1)', '(= (length matching) 1)',
                     '(finite-nonnegative? (hash-ref value \'monotonic_ms #f))',
                     '(list? registry) (pair? registry)',
                     '(timeline-ordered? points terminal-timeline)',
                     '(timeline-ordered? points application-timeline)']:
            self.assertIn(expr, self.source)

    def test_evidence_reads_have_fixed_bounds(self):
        for expr in ['(bounded-object "worker-init.json" (* 16 1024))',
                     '(bounded-object "worker-phase-1.json" (* 64 1024))',
                     '(read-bytes (add1 maximum-bytes) in)', '(link-exists? path)']:
            self.assertIn(expr, self.source)

    def test_only_host_writes_gui_summary_at_final_or_exception_endpoint(self):
        self.assertNotIn('(bounded-object "gui-observation.json"', self.source)
        self.assertIn('(define summary (observer-summary))', self.source)
        self.assertIn('(set! last-observation summary)', self.source)
        self.assertEqual(self.source.count('(persist-observation!'), 3)  # Definition, exception, final.
        self.assertIn('(persist-observation! (observer-summary))', self.source)
        self.assertIn('(persist-observation! last-observation)', self.source)
        self.assertIn('(rename-file-or-directory temporary (build-path output "gui-observation.json") #t)', self.source)
        self.assertIn('(when (> (add1 (bytes-length data)) (* 1024 1024))', self.source)
        wait_start = self.source.index('(define completed-record')
        wait_end = self.source.index('(define points (hash-ref completed-record', wait_start)
        polling = self.source[wait_start:wait_end]
        for forbidden in ('persist!', 'persist-observation!', 'write-json', 'jsexpr->string', 'call-with-output-file'):
            self.assertNotIn(forbidden, polling)

    def test_worker_files_are_cached_after_first_successful_read(self):
        self.assertIn('(define worker-init-cache #f)', self.source)
        self.assertIn('(define worker-phase-cache #f)', self.source)
        self.assertIn('(or worker-init-cache (bounded-object "worker-init.json"', self.source)
        self.assertIn('(set! worker-init-cache worker)', self.source)
        self.assertIn('(or worker-phase-cache', self.source)
        self.assertIn('(set! worker-phase-cache value)', self.source)
        check = self.source[self.source.index('(define (worker-report-ready?)'):self.source.index('(define (on-gui thunk)')]
        self.assertNotIn('(equal? arm "control")', check)
        self.assertIn("(hash-ref value 'phase_points_enabled 'missing)", check)

    def test_timeline_contract_allows_application_before_terminal(self):
        # Interpret only the two literal timeline lists in the host source. This
        # tests its dependency ordering without invoking any Racket evaluator.
        groups = [re.search(r"\(define " + name + r" '\(([^)]*)\)\)", self.source).group(1).split()
                  for name in ('terminal-timeline', 'application-timeline')]
        self.assertEqual(groups, [
            ['terminal-received', 'terminal-callback-enter', 'terminal-callback-return'],
            ['monitor-received', 'monitor-callback-enter', 'application-enter', 'application-complete']])
        self.assertIn('(apply <= (for/list ([name (in-list names)])', self.source)
        self.assertNotIn('(<= entered applied)', self.source)
        self.assertNotIn('(<= receipt applied)', self.source)

        def ordered(points):
            return all(all(points[a] <= points[b] for a, b in zip(group, group[1:])) for group in groups)

        before = {'monitor-received': 10, 'monitor-callback-enter': 11,
                  'application-enter': 12, 'application-complete': 13,
                  'terminal-received': 20, 'terminal-callback-enter': 21,
                  'terminal-callback-return': 22}
        self.assertTrue(ordered(before))
        after = dict(before, **{'application-complete': 23})
        self.assertTrue(ordered(after))
        for group in groups:
            for a, b in zip(group, group[1:]):
                invalid = dict(before)
                invalid[b] = invalid[a] - 1
                with self.subTest(reversed=(a, b)):
                    self.assertFalse(ordered(invalid))

    def test_host_delimiters_balance_without_evaluating_racket(self):
        # A deliberately narrow source scan, not a substitute for native Racket
        # compilation. Strings, line comments and character literals are skipped.
        source, stack, index = self.source, [], 0
        pairs = {')': '(', ']': '[', '}': '{'}
        while index < len(source):
            character = source[index]
            if character == ';':
                index = source.find('\n', index)
                if index < 0:
                    break
            elif character == '"':
                index += 1
                while index < len(source):
                    if source[index] == '\\':
                        index += 2
                        continue
                    if source[index] == '"':
                        break
                    index += 1
                self.assertLess(index, len(source), 'Unterminated Racket string')
            elif source[index:index + 2] == '#\\':
                index += 3
                while index < len(source) and source[index].isalpha():
                    index += 1
                index -= 1
            elif character in '([{':
                stack.append((character, index))
            elif character in ')]}':
                self.assertTrue(stack, f'Unexpected closing delimiter at {index}')
                self.assertEqual(stack[-1][0], pairs[character], f'Mismatched delimiter at {index}')
                stack.pop()
            index += 1
        self.assertEqual(stack, [])


if __name__ == '__main__':
    unittest.main()
