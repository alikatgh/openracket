#!/usr/bin/env python3
"""Headless source-contract tests; no GUI, download, install, or frozen-source write."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('compact_prepare', HERE / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
DEFAULT_SOURCE = Path('/tmp/17916276701791627670599-drracket-core-lib/drracket/private')
BLOCK = re.compile(r'\n;; OPENRACKET-COMPACT-BEGIN ([a-z-]+)\n.*?\n;; OPENRACKET-COMPACT-END \1\n', re.S)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls.source = Path(os.environ.get('OPENRACKET_TEST_STOCK_PRIVATE', DEFAULT_SOURCE))
        if not cls.source.exists():
            raise unittest.SkipTest('Exact stock DrRacket source directory is not available')
        cls.output = prepare.prepared(cls.source)

    def test_exact_pins(self):
        for name, pin in prepare.PINS.items():
            self.assertEqual(prepare.digest((self.source / name).read_bytes()), pin)

    def test_original_sources_recovered_byte_for_byte(self):
        for name, content in self.output.items():
            self.assertEqual(BLOCK.sub('', content.decode()).encode(), (self.source / name).read_bytes())

    def test_only_expected_additions(self):
        self.assertEqual(BLOCK.findall(self.output['module-language.rkt'].decode()),
                         ['request', 'status', 'response', 'callback-enter', 'callback-delivered'])
        self.assertEqual(BLOCK.findall(self.output['expanding-place.rkt'].decode()), ['worker-init'])

    def test_worker_observation_after_imports(self):
        text = self.output['expanding-place.rkt'].decode()
        self.assertLess(text.index('(dynamic-require file id)'), text.index('observer-worker-init!'))
        self.assertLess(text.index('observer-worker-init!'), text.index('(let loop ([current-job #f]'))

    def test_request_uses_original_payload(self):
        text = self.output['module-language.rkt'].decode()
        self.assertLess(text.index('observer-request!'), text.index('(place-channel-put expanding-place to-send)'))
        self.assertIn("'observer-request!) to-send openracket-observer-started", text)
        self.assertIn("'observer-response!) openracket-observer-id res", text)

    def test_delivery_after_original_callback(self):
        text = self.output['module-language.rkt'].decode()
        self.assertLess(text.index('observer-response!'), text.index('observer-callback-enter!'))
        self.assertLess(text.index('observer-callback-enter!'), text.index('(show-results res)'))
        self.assertLess(text.index('(show-results res)'), text.index('observer-callback-delivered!'))

    def test_rejects_changed_pin_without_writing(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            root = Path(temp)
            for name in prepare.PINS:
                (root / name).write_bytes((self.source / name).read_bytes())
            name = next(iter(prepare.PINS))
            (root / name).write_bytes((root / name).read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'exact pinned'):
                prepare.prepared(root)

    def test_anchor_reapplication_rejected(self):
        with self.assertRaises(ValueError):
            prepare.transform_language(self.output['module-language.rkt'].decode())

    def test_gui_helper_does_not_write_or_log(self):
        support = (HERE / 'support.rkt').read_text()
        gui = support[:support.index('(define (observer-worker-init!')]
        self.assertNotIn('call-with-output-file', gui)
        self.assertNotIn('log-message', gui)
        self.assertNotIn('make-log-receiver', support)
        self.assertNotIn('(thread ', support)
        self.assertNotIn('(make-custodian', support)

    def test_full_source_hash_only_at_registration(self):
        support = (HERE / 'support.rkt').read_text()
        request = support[support.index('(define (observer-request!'):support.index('(define (update-record')]
        self.assertNotIn('digest', request)
        self.assertNotIn('sha256', request.replace("'snapshot_sha256", ''))
        self.assertIn('(string=? snapshot expected)', request)

    def test_no_shared_lock_or_blocking_readers(self):
        support = (HERE / 'support.rkt').read_text()
        self.assertNotIn('call-with-semaphore', support)
        self.assertNotIn('semaphore-wait', support)
        self.assertNotIn('make-semaphore', support)
        query = support[support.index('(define (observer-final-outcome)'):support.index(';; Called inside expanding-place')]
        self.assertNotIn('box-cas!', query)
        self.assertNotIn('(sync', query)
        self.assertIn('(box-cas! state old completed)', support)

    def test_ordered_registry_retains_monitor_flags(self):
        worker = self.output['expanding-place.rkt'].decode()
        self.assertIn('(list (handler-key h) (and (handler-monitor-pc h) #t))', worker)

    def test_worker_memory_evidence_and_untruncated_registry_paths(self):
        support = (HERE / 'support.rkt').read_text()
        worker = support[support.index('(define (observer-worker-init!'):]
        self.assertIn("'memory_accounting_available (custodian-memory-accounting-available?)", worker)
        self.assertIn("'child_memory_limit child-limit", worker)
        self.assertIn("'module (if (path? module-file) (path->string module-file) (format \"~s\" module-file))", worker)
        self.assertNotIn('(short-string module-file)', worker)
        self.assertNotIn('(short-string module-spec)', worker)


if __name__ == '__main__':
    unittest.main(verbosity=2)
