"""Offline rejection tests; native profile persistence tests live in ../profile."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from profile_setup import validate_setup, prepare_memory_profile, PINS, KEY, DISK_KEY
import run

class ProfileSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.racket = self.root / 'runtime/bin/racket'; self.racket.parent.mkdir(parents=True)
        self.racket.touch()
        self.home = self.root / 'profile'; self.addon = self.root / 'addon'
        self.home.mkdir(); self.addon.mkdir()
        self.store = self.home / 'prefs.rktd'; self.store.write_text('fresh helper evidence')
        self.env = {'PLTUSERHOME': str(self.home), 'PLTADDONDIR': str(self.addon)}
        limit = 128 * 1024 * 1024
        self.report = {'status': 'verified', 'phase': 'before-timed-gui', 'runtime_version': '9.3',
                       'runtime_root': str(self.root / 'runtime'), 'runtime_executable': str(self.racket),
                       'expected_default_limit_bytes': limit, 'original_default_limit_bytes': limit,
                       'expected_limit_bytes': limit, 'selected_limit_bytes': limit,
                       'readback_limit_bytes': limit, 'persisted_limit_bytes': limit,
                       'preference_key': KEY, 'persisted_preference_key': DISK_KEY,
                       'profile_was_empty': True, 'addon_was_empty': True, 'gui_initialized': False,
                       'only_expected_preference_changed': True, 'profile_path': str(self.home),
                       'legacy_preference_store_absent': True, 'runtime_fallback_store_absent': True,
                       'addon_path': str(self.addon), 'preference_store_path': str(self.store),
                       'preference_store_sha256': hashlib.sha256(self.store.read_bytes()).hexdigest(),
                       'disk_key_count_before': 0, 'disk_key_count_after': 1,
                       'one_key_delta': [{'key': DISK_KEY, 'before_present': False, 'after_value': limit}],
                       'sources': {name: {'path': str(self.root / 'runtime' / name), 'sha256': pin,
                                           'expected_sha256': pin} for name, pin in PINS.items()}}

    def test_three_exact_limits(self):
        for mib in (128, 256, 512):
            for key in ('expected_limit_bytes', 'selected_limit_bytes', 'readback_limit_bytes', 'persisted_limit_bytes'):
                self.report[key] = mib * 1024 * 1024
            self.report['one_key_delta'][0]['after_value'] = mib * 1024 * 1024
            self.assertEqual(validate_setup(self.report, mib, self.env, self.racket), [])

    def test_wrong_paths_source_or_limits_rejected(self):
        for key, value in [('profile_path', str(self.addon)), ('addon_path', str(self.home)),
                           ('only_expected_preference_changed', False), ('persisted_limit_bytes', 1),
                           ('gui_initialized', True), ('runtime_executable', '/outside/racket'),
                           ('legacy_preference_store_absent', False), ('runtime_fallback_store_absent', False)]:
            with self.subTest(key=key):
                old = self.report[key]; self.report[key] = value
                self.assertTrue(validate_setup(self.report, 128, self.env, self.racket))
                self.report[key] = old
        self.report['sources']['eval_helpers']['sha256'] = 'bad'
        self.assertTrue(validate_setup(self.report, 128, self.env, self.racket))
        self.assertTrue(validate_setup(self.report, 1024, self.env, self.racket))

    def test_disk_mutation_after_helper_is_rejected(self):
        self.store.write_text('unexpected subsequent preference change')
        self.assertTrue(validate_setup(self.report, 128, self.env, self.racket))

    def test_missing_addon_refused_before_process(self):
        args = types.SimpleNamespace(profile_helper=Path(__file__), memory_limit_mib=128, racket=str(self.racket))
        with mock.patch('profile_setup.subprocess.Popen') as spawn:
            result = prepare_memory_profile(args, {}, self.root, run.terminate_group)
        self.assertFalse(result['verified']); spawn.assert_not_called()

    def test_setup_timeout_is_explicit_and_reaped(self):
        self.racket.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n'); self.racket.chmod(0o755)
        args = types.SimpleNamespace(profile_helper=Path(__file__), memory_limit_mib=128, racket=str(self.racket))
        result = prepare_memory_profile(args, os.environ | self.env, self.root, run.terminate_group, timeout_seconds=.15)
        self.assertFalse(result['verified']); self.assertTrue(result['timeout'])
        self.assertIsNotNone(result['exit_code'])
        self.assertLess(result['elapsed_ms_before_timed_process'], 6000)

    def test_setup_failure_blocks_gui_process(self):
        from fixtures import write_fixtures
        import contextlib, io
        args = types.SimpleNamespace(profile_helper=Path(__file__), memory_limit_mib=128,
                                     racket=str(self.racket), output=self.root, mode='memory-test', timeout=60,
                                     xref_activation='stock', xref_source_sha256=run.STOCK_XREF_SHA256,
                                     observer_support=Path(__file__))
        setup = {'verified':False, 'errors':['deliberate refusal'], 'configuration':None}
        with mock.patch.object(run, 'prepare_memory_profile', return_value=setup), \
             mock.patch.object(run.subprocess, 'Popen') as spawn, contextlib.redirect_stdout(io.StringIO()):
            result = run.run_trial(args, write_fixtures(self.root/'fixtures')[0], 1)
        spawn.assert_not_called()
        self.assertEqual(result['status'], 'setup_failed')
        self.assertEqual(result['process_wall_ms'], 0)
        self.assertFalse(result['timeout'])


class FrozenWorkloadTests(unittest.TestCase):
    def test_gui_workload_diff_is_only_metadata(self):
        source = (Path(__file__).parent/'retained-host.rkt').read_text()
        source = source.replace("(hash-set! report 'expected_memory_limit_bytes (hash-ref config 'expected_memory_limit_bytes))\n", '')
        source = source.replace('stock_memory_configuration_with_common_compact_observer',
                                'matched_gui_with_common_compact_observer')
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         'bdd09123bdd69512fe3c2ce8f652e9174b09a497373871665b03a78fbddf1afe')

    def test_common_observer_bytes_are_unchanged(self):
        observer = Path(__file__).parent.parent/'observer'
        self.assertEqual(hashlib.sha256((observer/'support.rkt').read_bytes()).hexdigest(),
                         '79c02e6652e7fa4158531384c2d0382a32487b21620522529e325c44394d0d7b')
        self.assertEqual(hashlib.sha256((observer/'prepare.py').read_bytes()).hexdigest(),
                         '485983c449dc2a02e342700ae4ed82e53c293006cdbff70400bd8d9bcc57402b')

    def test_profile_setup_is_before_gui_timer_and_launch(self):
        source = (Path(__file__).parent/'run.py').read_text().split('def run_trial(',1)[1]
        setup = source.index('setup = prepare_memory_profile')
        timer = source.index('started = time.monotonic()')
        spawn = source.index('process = subprocess.Popen')
        self.assertLess(setup, timer); self.assertLess(timer, spawn)

if __name__ == '__main__': unittest.main()
