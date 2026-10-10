"""Headless generated-workload checks, not actual native autosave evidence."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'performance'))
import run as runner


class AutosaveWorkloadTests(unittest.TestCase):
    def test_exact_frozen_output_hashes(self):
        manifest = json.loads((ROOT / 'performance/manifest.json').read_text())
        for name, digest in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / 'performance' / name).read_bytes()).hexdigest(), digest)

    def test_real_method_and_forced_dirty_precondition(self):
        source = (ROOT / 'performance/retained-host.rkt').read_text()
        self.assertEqual(source.count('(send editor do-autosave)'), 1)
        before = source.index('  (send editor set-modified #t)')
        call = source.index('(send editor do-autosave)')
        self.assertNotIn('gui-yield', source[before:call])
        self.assertNotIn('(pause ', source[before:call])
        self.assertNotIn('preferences:set', source)
        self.assertNotIn('(send editor save-file', source)
        self.assertIn('[else "settled_editor_autosave"]', source)

    def test_recovery_verification_is_outside_timing(self):
        source = (ROOT / 'performance/retained-host.rkt').read_text()
        after = source.index("(record! 'memory_after_autosave")
        self.assertGreater(source.index("(send restored load-file auto-name 'guess #f)"), after)
        self.assertGreater(source.index('(bytes=? original-file-bytes (file->bytes fixture))'), after)
        self.assertIn("(record! 'autosave_queued_gui_probe_ms probe-delay)", source)
        self.assertIn("'exact_recovered_source #t", source)
        self.assertIn("'format_restored #t", source)
        self.assertIn("'new_artifact_path_verified #t", source)
        self.assertIn("'recovery_toc_entry_verified #t", source)
        self.assertIn('(equal? (simplify-path auto-directory #f) (simplify-path fixture-directory #f))', source)
        self.assertIn("(record! 'autosave_prior_state", source)
        before = source.index('(define existing-artifact-paths (directory-list')
        call = source.index('(send editor do-autosave)')
        self.assertNotIn('(pause ', source[before:call])
        self.assertNotIn('(fence!)', source[before:call])

    def test_allocation_snapshots_exclude_json_persistence(self):
        source = (ROOT / 'performance/retained-host.rkt').read_text()
        before = source.index('(define memory-before-save (memory-snapshot))')
        after = source.index('(define memory-after-save-fence (memory-snapshot))')
        self.assertNotIn('(record!', source[before:after])
        self.assertLess(source.index('(define memory-after-save-command (memory-snapshot))'),
                        source.index('  (fence!)', before))

    def test_relevant_save_preferences_are_read_only_metadata(self):
        source = (ROOT / 'performance/retained-host.rkt').read_text()
        for key in ('framework:autosaving-on?', 'framework:autosave-delay',
                    'framework:backup-files?', 'framework:verify-change-format'):
            self.assertIn(key, source)

    def test_summary_keeps_actual_operation_and_recovery(self):
        sample = {'actual_autosave': {'command_ms': 10}, 'autosave_queued_gui_probe_ms': 12,
                  'autosave_recovery': {'exact_recovered_source': True},
                  'autosave_activation': {'status': 'verified'}}
        summary = runner.summarize(sample)
        for key, value in sample.items():
            self.assertEqual(summary[key], value)


if __name__ == '__main__':
    unittest.main()
