"""Portable named-style telemetry contracts. Native behavior is gated separately."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import capture
from test_capture import SOURCE_PINS, complete_evidence, write_evidence
from test_gui_source import balanced

HERE = Path(__file__).resolve().parent
COMMON_HELPER_PINS = {'gui-observer.rkt': 'c74f75d8e1727956a948d7e4ac94c700bd25539ba609d06af44f52bd7ea05e5e', 'gui-phase.rkt': 'ee05b328cfe494dce75b16b4a4151f73f9939f2d9f6a84e47cc7fa55b0bc9e3a', 'memory-profile.rkt': '9b761799e61b45388ae21461d358a819274ae1923e88959351a9f9b46337abc0', 'profile_setup.py': '9bb3dc30255a4effca1a91f2f407e0af3ae0fce298f2fc20ed823544176daddb', 'supervise.py': '0505de6044b8e9c389088bf3714cd95a9c0bef501dadddf08d3617fbb5437b58', 'fixtures.py': '9fdd094f82ef9f292e7c618d26075d822e0597d7df333f8ed5bab7449b776b6d', 'test_gui_observer.rkt': 'c1ab791f97d43f77452b98391feaea024cbad4c5c23b3836da3681071bc28072', 'test_gui_phase.rkt': 'b586b18a908dd94db1c25798d8e5730bf9cce982f6739769e92e5aa523924680'}


class EvidenceTests(unittest.TestCase):
    def test_source_pins_require_two_distinct_exact_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pins.json'
            path.write_text(json.dumps(dict(SOURCE_PINS, module='racket/snip/private/style')))
            self.assertEqual(capture.read_source_pins(path), SOURCE_PINS)
            for bad in ({}, {'stock_sha256': 'a' * 64},
                        dict(SOURCE_PINS, candidate_sha256='A' * 64),
                        dict(SOURCE_PINS, candidate_sha256='a' * 64),
                        dict(SOURCE_PINS, stock_sha256=True),
                        dict(SOURCE_PINS, candidate_sha256='0' * 63)):
                with self.subTest(bad=bad):
                    path.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        capture.read_source_pins(path)

    def test_complete_both_phase_off_arms_require_new_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('stock', 'candidate'):
                rows = complete_evidence(arm)
                write_evidence(root, rows)
                self.assertEqual(capture.check_host_evidence(root, arm, SOURCE_PINS[arm + '_sha256']), [])
                for file in ('activation.json', 'heartbeat.json', 'binding-export.json', 'style-witness.json'):
                    (root / file).unlink()
                    self.assertTrue(capture.check_host_evidence(root, arm, SOURCE_PINS[arm + '_sha256']))
                    write_evidence(root, rows)

    def test_activation_absence_mismatch_and_errors_fail_closed(self):
        bad_fields = [('schema_version', True), ('kind', 'gui_binding_table_activation'),
                      ('flag_name', 'OPENRACKET_BINDING_TABLE_INDEX'),
                      ('activation_export', 'openracket-binding-table-index-enabled?'), ('verified', False), ('gui_handler_thread', False),
                      ('gui_module_already_instantiated', False),
                      ('same_gui_imported_style_instance', False),
                      ('source_sha256', 'f' * 64), ('expected_source_sha256', 'f' * 64),
                      ('export_status', 'error'), ('phase_points_enabled', True),
                      ('unexpected_experiment_flags', ['OPENRACKET_BINDING_TABLE_INDEX']),
                      ('unexpected_experiment_flags', None)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('stock', 'candidate'):
                for field, value in bad_fields + [('flag_value', '0'),
                                                 ('named_style_index_enabled', False)]:
                    with self.subTest(arm=arm, field=field):
                        rows = complete_evidence(arm)
                        rows['activation.json'][field] = value
                        write_evidence(root, rows)
                        self.assertTrue(capture.check_host_evidence(root, arm, SOURCE_PINS[arm + '_sha256']))

    def test_stock_null_activation_fields_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for field in ('flag_value', 'named_style_index_enabled'):
                rows = complete_evidence('stock')
                del rows['activation.json'][field]
                write_evidence(root, rows)
                self.assertTrue(capture.check_host_evidence(root, 'stock', SOURCE_PINS['stock_sha256']))

    def test_heartbeat_missing_dropped_incomplete_or_unbounded_fails(self):
        bad_fields = [('joined', False), ('producer_exited', False), ('join_timed_out', True),
                      ('outstanding_callbacks', 1), ('error_count', 1), ('dropped_records', 1),
                      ('outstanding_callbacks', False), ('period_ms', 1), ('max_records', 8192),
                      ('records', []), ('records', [{}] * 4097), ('handled_count', 0),
                      ('submitted_count', 2), ('submitted_count', True)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for field, value in bad_fields:
                with self.subTest(field=field):
                    rows = complete_evidence('stock')
                    rows['heartbeat.json'][field] = value
                    write_evidence(root, rows)
                    self.assertTrue(capture.check_host_evidence(root, 'stock', SOURCE_PINS['stock_sha256']))
    def test_launcher_rejects_prior_export_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for field, value in (('schema_version', True), ('schema_version', 2),
                                 ('kind', 'binding-table-public-exposure')):
                rows = complete_evidence('candidate')
                rows['binding-export.json'][field] = value
                write_evidence(root, rows)
                with self.subTest(field=field):
                    self.assertTrue(capture.check_host_evidence(root, 'candidate', SOURCE_PINS['candidate_sha256']))


class StaticTests(unittest.TestCase):
    def test_common_proven_helpers_unchanged(self):
        for name, sha in COMMON_HELPER_PINS.items():
            raw = (HERE / name).read_bytes()
            if name.startswith('test_'):
                self.assertEqual(raw.count(b'(current-check-handler raise)\n'), 1)
                raw = raw.replace(b'\n(current-check-handler raise)\n', b'')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha, name)

    def test_native_verified_heartbeat_and_common_transform_are_byte_identical(self):
        pins = {
            'heartbeat.rkt': '134b98c1e2d43495db12994267e5d3147b54a8ede12342c8d87d2f639e6297d7',
            'test_heartbeat.rkt': 'cb55904fac366d1d95a75be0ec7f859183c08986c435d7abc1282967edbf3f03',
        }
        for name, sha in pins.items():
            self.assertEqual(hashlib.sha256((HERE / name).read_bytes()).hexdigest(), sha, name)

    def test_binding_graph_is_untimed_after_ordinary_readiness(self):
        source = (HERE / 'binding-export.rkt').read_text()
        self.assertEqual(source.count('(send editor syncheck:get-bindings-table)'), 2)
        self.assertNotIn('(define (point)', source)
        self.assertNotIn('eager', source)
        self.assertIn("'timed #f", source)

    def test_helpers_and_native_tests_static_reader(self):
        for name in ('activation.rkt', 'test_activation.rkt', 'heartbeat.rkt', 'test_heartbeat.rkt', 'binding-export.rkt', 'test_binding_export.rkt', 'style-witness.rkt', 'test_style_witness.rkt'):
            balanced((HERE / name).read_text())

    def test_activation_proves_actual_existing_private_and_gui_instance(self):
        source = (HERE / 'activation.rkt').read_text()
        self.assertIn('(module->namespace actual)', source)
        for name in ('gui-module', 'style-module'):
            self.assertLess(source.index('(existing-module '+name+')', source.index('(define (existing-module-evidence')),
                            source.index('(dynamic-require actual-gui'))
        self.assertIn('(is-a? actual-style-list style-class)', source)
        self.assertIn('(is-a? actual-style-list gui-style-class)', source)
        self.assertNotIn('(eq? gui-style-class style-class)', source)
        self.assertIn('(lambda () missing)', source)
        for forbidden in ('with-handlers', 'namespace-attach-module', 'namespace-require',
                          'make-base-namespace', '(eval ', 'find-named-style'):
            self.assertNotIn(forbidden, source)
        self.assertIn("'racket/gui/base 'racket/snip/private/style", source)

    def test_host_keeps_io_outside_workload_and_uses_shared_deadline(self):
        source = (HERE / 'capture-host.rkt').read_text()
        self.assertIn('(persist-telemetry! "activation.json" activation (* 16 1024))', source)
        self.assertIn('(persist-telemetry! "heartbeat.json" (heartbeat-summary heartbeat) (* 2 1024 1024))', source)
        self.assertIn('(heartbeat-join! heartbeat gui-yield deadline)', source)
        self.assertIn('(min (or workload-deadline +inf.0)', source)
        self.assertEqual(source.count('90000'), 2)
        start = source.index('(set! heartbeat (start-heartbeat! queue-callback))')
        opened = source.index('(send frame change-to-file fixture)', start)
        final = source.index("(hash-set! report 'workload_completed_monotonic_ms", opened)
        stop = source.index('(heartbeat-stop! heartbeat)', final)
        persist = source.index('(persist-extra-evidence!)', stop)
        self.assertLess(start, opened)
        self.assertLess(final, stop)
        self.assertLess(stop, persist)
        for forbidden in ('persist-extra-evidence!', 'persist-telemetry!', 'write-json', 'jsexpr->string'):
            self.assertNotIn(forbidden, source[start:final])
        self.assertIn('not physical input-to-photon or actual typing', source)
        join = source.index('(heartbeat-join! heartbeat gui-yield deadline)', stop)
        verified = source.index('(define final-record (complete-observation))', join)
        self.assertLess(join, verified)
        export = source.index('(verify-binding-export editor arm expected-characters', verified)
        postexport = source.index('(define post-export-record (complete-observation))', export)
        self.assertLess(verified, export)
        self.assertLess(export, postexport)
        self.assertLess(postexport, persist)
        self.assertIn("(hash-ref report 'edit_dispatched_monotonic_ms) 90000", source)
        for gate in ("'final_snapshot_sha256 (digest", "'lexer_valid_at_completion (send editor is-lexer-valid?)",
                     "(hash-ref completed-record 'request_id)", '(< (current-inexact-monotonic-milliseconds) deadline)'):
            self.assertIn(gate, source[postexport:persist])
        for gate in ("'final_snapshot_characters (send editor last-position)",
                     "'final_snapshot_sha256 (digest", "'lexer_valid_at_completion (send editor is-lexer-valid?)",
                     "(hash-ref completed-record 'request_id)"):
            self.assertIn(gate, source[verified:persist])


    def test_heartbeat_has_no_reporting_kill_or_gc(self):
        source = (HERE / 'heartbeat.rkt').read_text()
        for forbidden in ('kill-thread', 'custodian-shutdown-all', 'collect-garbage', 'make-log-receiver',
                          'write-json', 'displayln', 'fprintf', 'call-with-output-file', 'jsexpr->string'):
            self.assertNotIn(forbidden, source)
        for field in ('scheduled_monotonic_ms', 'submitted_monotonic_ms', 'handler_monotonic_ms',
                      'producer_lateness_ms', 'dispatch_latency_ms', 'handler_gap_ms',
                      'stop_handler_gap_ms', 'outstanding_callbacks', 'join_timed_out'):
            self.assertIn(field, source)
        self.assertIn('50.0', source)
        self.assertIn('4096', source)


class DerivativeContracts(unittest.TestCase):
    def test_entire_common_source_transform_prefix_is_unchanged(self):
        prefix=(HERE/'prepare_gui.py').read_bytes().split(b'def arm_pins(arm):')[0]
        self.assertEqual(hashlib.sha256(prefix).hexdigest(), '136d95cb4ce7c1d68944641f3460866d9742d094b75c605c00844578ced8c9fd')

    def test_native_helper_gate_cannot_skip(self):
        native = (HERE/'test_gui_native.py').read_text()
        gate = (HERE/'native_preflight.py').read_text()
        self.assertNotIn('skipUnless',native)
        self.assertNotIn('skipIf',native)
        self.assertIn("raise RuntimeError('Native Racket required",native)
        self.assertIn('if result.skipped or not result.wasSuccessful():return 1',gate)
        for test in ('test_activation.rkt','test_binding_export.rkt','test_style_witness.rkt','test_heartbeat.rkt'):
            self.assertIn(test,native)
        self.assertIn('test_rackunit_failure_is_process_fatal_negative_control',native)

    def test_no_new_deadline_or_prewarmer(self):
        prepare=(HERE/'prepare_gui.py').read_text()
        host=(HERE/'capture-host.rkt').read_text()
        style=(HERE/'style-witness.rkt').read_text()
        self.assertEqual(prepare.count('timeout=15'),2)
        self.assertEqual(prepare.count('timeout=240'),1)
        self.assertEqual(host.count('90000'),2)
        for forbidden in ('(send actual find-named-style','(send editor find-named-style','collect-garbage','sleep','yield'):
            self.assertNotIn(forbidden,style.replace('yield,',''))
        self.assertEqual(host.count('(style-snapshot!'),5)
        polling=host[host.index('(define completed-record'):host.index('(define points (hash-ref completed-record')]
        self.assertNotIn('style-snapshot!',polling)

if __name__ == '__main__':
    unittest.main()
