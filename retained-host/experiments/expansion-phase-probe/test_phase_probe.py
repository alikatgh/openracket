#!/usr/bin/env python3
"""Source/host tests plus explicit skipped Racket gates when no runtime is available."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import prepare_phase as phase
import supervise

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('REPLAY_TEST_SOURCE_DIR', '/tmp/17916276701791627670599-drracket-core-lib/drracket/private'))
RACKET = os.environ.get('REPLAY_TEST_RACKET') or shutil.which('racket')
HAS_RACKET = bool(RACKET and Path(RACKET).is_file())

def stripped(text):
    return re.sub(r'(?m)^[ ]*;; BEGIN OPENRACKET REPLAY-ONLY PHASE (?:HOOK|POINT)\n.*?^[ ]*;; END OPENRACKET REPLAY-ONLY PHASE (?:HOOK|POINT)\n(?:\n)?',
                  '', text, flags=re.S)

class PhaseSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = phase.verify_sources(SOURCE)

    def test_three_official_pins_and_worker_matches_recovered_contract(self):
        contract = json.loads((HERE / 'observed-contract.json').read_text())
        self.assertEqual(phase.ALL_PINS['expanding-place.rkt'], contract['worker_sha256'])
        self.assertEqual(phase.ALL_PINS['module-language.rkt'], contract['module_language_sha256'])
        self.assertEqual(len(self.original), 3)

    def test_worker_only_adds_guarded_insertions_and_original_readiness(self):
        original = self.original['expanding-place.rkt']
        patched = phase.transform_phase_worker(original)
        self.assertEqual(stripped(patched).replace(phase.READY, '', 1), original)
        self.assertEqual(patched.count('dynamic-require'), original.count('dynamic-require') + 2)
        for number in ('09', '10', '11', '12', '13'):
            self.assertIn("'worker-phase-" + number, patched)

    def test_monitor_only_adds_guarded_insertions_to_actual_traversal_thread(self):
        original = self.original['syncheck/online-comp.rkt']
        patched = phase.transform_phase_monitor(original)
        self.assertEqual(stripped(patched), original)
        definition = patched.index('(define (monitor send-back')
        self.assertGreater(patched.index("'monitor-start"), definition)
        self.assertEqual(patched.count("'monitor-start"), 1)
        self.assertLess(patched.index("'monitor-build-trace-start"), patched.index('(define trace (build-trace'))
        self.assertLess(patched.index('(define trace (build-trace'), patched.index("'monitor-build-trace-complete/send-back-start"))
        self.assertLess(patched.index("'monitor-build-trace-complete/send-back-start"), patched.index('(send-back trace)'))

    def test_no_capture_changes_or_stock_logger_subscription(self):
        from prepare import transform_language
        self.assertIs(phase.TRANSFORMS['module-language.rkt'], transform_language)
        helper = (HERE / 'phase-probe.rkt').read_text()
        self.assertNotIn('make-log-receiver', helper)
        self.assertNotIn('log-message', helper)
        for key in ('expanding-place.rkt', 'syncheck/online-comp.rkt'):
            patched = phase.TRANSFORMS[key](self.original[key])
            restored = stripped(patched).replace(phase.READY, '', 1)
            self.assertEqual(restored, self.original[key])

    def test_both_flags_are_required_before_loading_hook_closure(self):
        self.assertIn('(equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")', phase.PREFIX)
        self.assertIn('(equal? (getenv "OPENRACKET_EXPANSION_PHASE_PROBE") "1")', phase.PREFIX)
        self.assertLess(phase.PREFIX.index('OPENRACKET_EXPANSION_PHASE_PROBE'), phase.PREFIX.index('dynamic-require'))
        self.assertNotIn('dynamic-require', phase.hook('worker-phase-11', ' '))

    def test_weak_thread_lifetimes_generations_and_retention_caps_are_explicit(self):
        helper = (HERE / 'phase-probe.rkt').read_text()
        for evidence in ['(make-weak-box (current-thread))', '(weak-box-value ref)',
                         '(thread-generation (add-one! generation))', '(= gen expected-generation)',
                         '(hash-clear! refs)', '(make-async-channel 128)', '(define sample-cap 256)',
                         '(define frame-cap 8)', '(define text-cap 240)', '(define point-cap 128)',
                         '(async-channel-put-evt inbox event)', 'input_events_dropped',
                         'transient_cost_bound', 'gc_visibility', 'stale_events_discarded']:
            self.assertIn(evidence, helper)
        self.assertIn('(continuation-mark-set->context (continuation-marks actual))', helper)
        self.assertNotIn('(thread-suspend', helper)
        self.assertNotIn('(custodian-limit-memory', helper)

    def test_missing_anchors_or_source_pin_mismatch_fail_closed(self):
        with self.assertRaises(ValueError):
            phase.transform_phase_worker('')
        with self.assertRaises(ValueError):
            phase.transform_phase_monitor('')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'syncheck').mkdir()
            for name, content in self.original.items():
                (root / name).write_text(content)
            (root / 'syncheck/online-comp.rkt').write_text('modified')
            with self.assertRaisesRegex(ValueError, 'Unexpected official source'):
                phase.verify_sources(root)

    @unittest.skipUnless(os.name == 'posix', 'POSIX directory aliases')
    def test_resolved_symlink_alias_keeps_source_pins_and_confinement_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            actual = base / 'actual'
            (actual / 'syncheck').mkdir(parents=True)
            for name, content in self.original.items():
                (actual / name).write_text(content)
            alias = base / 'alias'
            alias.symlink_to(actual, target_is_directory=True)
            self.assertNotEqual(alias, alias.resolve())
            with self.assertRaisesRegex(ValueError, 'independently cloned inside its root'):
                phase.verify_sources(alias)
            root = alias.resolve()
            self.assertEqual(phase.verify_sources(root), self.original)
            target = root / 'syncheck/online-comp.rkt'
            target.write_text('modified')
            with self.assertRaisesRegex(ValueError, 'Unexpected official source'):
                phase.verify_sources(root)
            target.write_text(self.original['syncheck/online-comp.rkt'])
            outside = base / 'outside'
            (root / 'syncheck').rename(outside)
            (root / 'syncheck').symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'independently cloned inside its root'):
                phase.verify_sources(root)

    def test_actual_terminal_is_recorded_before_phase_end_query(self):
        text = (HERE / 'replay.rkt').read_text()
        self.assertLess(text.index("'last_observed_terminal_before_probe_queries"),
                        text.index("(when completed? (phase-control! 'phase-end"))

    def test_attribution_acceptance_and_explicit_dynamic_helper_compilation(self):
        helper = (HERE / 'phase-probe.rkt').read_text()
        self.assertIn('(and worker-registered? monitor-registered? usable-monitor-frames?)', helper)
        self.assertIn('"coarse_thread_context_available" "incomplete"', helper)
        for field in ['name_truncated', 'source_truncated', 'error_truncated', 'frames_truncated']:
            self.assertIn(field, helper)
        prepare = (HERE / 'prepare_phase.py').read_text()
        for name in ['phase-probe.rkt', 'support.rkt', 'replay.rkt', 'capture-host.rkt']:
            self.assertIn(repr(name), prepare)
        self.assertIn('+ [str(p) for p in helpers]', prepare)

class PhaseSupervisorTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX process-group supervisor')
    def test_phase_environment_is_explicitly_opted_in_after_inherited_flags_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            config = {'capture': 'fake', 'output': str(output), 'trials': 1, 'phase_probe': True,
                      'init_timeout_seconds': .2, 'terminal_timeout_seconds': .2, 'cleanup_timeout_seconds': .35}
            program = '''import json,os,pathlib
c=json.loads(os.environ['OPENRACKET_REPLAY_CONFIG'])
assert os.environ['OPENRACKET_EXPANSION_PHASE_PROBE']=='1'
assert pathlib.Path(os.environ['OPENRACKET_REPLAY_PHASE_MODULE']).name=='phase-probe.rkt'
assert pathlib.Path(os.environ['OPENRACKET_REPLAY_PHASE_MODULE']).is_absolute()
assert 'OPENRACKET_UNRELATED' not in os.environ
assert 'OPENRACKET_EXPANSION_CAPTURE' not in os.environ
pathlib.Path(c['output'],'replay.json').write_text('{}')
print('OPENRACKET_REPLAY_PHASE_JSON '+json.dumps({'event':'finished','trial':1,'monotonic_ms':0}),flush=True)
'''
            with mock.patch.dict(os.environ, {'OPENRACKET_EXPANSION_PHASE_PROBE':'stale',
                                             'OPENRACKET_REPLAY_PHASE_MODULE':'stale', 'OPENRACKET_UNRELATED':'1'}):
                result = supervise.run_supervised([sys.executable, '-c', program], output, config,
                                                  startup_cushion_seconds=.1)
            self.assertEqual(result['status'], 'ok', result)

@unittest.skipUnless(HAS_RACKET, 'Racket executable absent; native/headless Racket CI gate remains required')
class PhaseRacketTests(unittest.TestCase):
    def run_racket(self, path):
        env = {key:value for key,value in os.environ.items() if not key.startswith('OPENRACKET_')}
        if os.environ.get('REPLAY_TEST_PROFILE'):
            env['PLTUSERHOME'] = os.environ['REPLAY_TEST_PROFILE']
        env.update(OPENRACKET_EXPANSION_REPLAY='1', OPENRACKET_EXPANSION_PHASE_PROBE='1')
        return subprocess.run([RACKET, str(path)], env=env, check=True, capture_output=True, text=True, timeout=20)

    def test_bounded_probe_actual_threads_and_warm_generation(self):
        self.run_racket(HERE / 'test_phase_probe.rkt')

    def test_generated_sources_read_without_instantiation(self):
        original = phase.verify_sources(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, transform in phase.TRANSFORMS.items():
                path = root / Path(name).name
                path.write_text(transform(original[name]))
                reader = root / 'reader.rkt'
                reader.write_text('#lang racket/base\n(parameterize ([read-accept-reader #t]) (call-with-input-file '+json.dumps(str(path))+" (lambda (in) (read-syntax 'source in))))\n")
                self.run_racket(reader)

    def test_disabled_phase_hook_does_not_load_any_module(self):
        for replay, probe in [(False,False), ('1',False), (False,'1')]:
            values = {'OPENRACKET_EXPANSION_REPLAY':replay, 'OPENRACKET_EXPANSION_PHASE_PROBE':probe}
            pairs = ' '.join('('+json.dumps(k)+' . '+(json.dumps(v) if v else '#f')+')' for k,v in values.items())
            body = '#lang racket/base\n(define (getenv key) (cdr (assoc key \'('+pairs+'))))\n'
            body += '(define (dynamic-require . args) (error \'disabled "module loaded"))\n'
            body += phase.PREFIX + phase.hook('worker-start', '')
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'disabled.rkt'
                path.write_text(body)
                self.run_racket(path)

if __name__ == '__main__':
    unittest.main(verbosity=2)
