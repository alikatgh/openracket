"""Generator and report checks, without a native display or actual timings."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'contention'))
import run as runner


class ContentionTests(unittest.TestCase):
    def test_generated_hashes(self):
        manifest = json.loads((ROOT / 'contention/manifest.json').read_text())
        for name, expected in manifest['output_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / 'contention' / name).read_bytes()).hexdigest(), expected)

    def test_distinct_workload_and_bounded_producer(self):
        source = (ROOT / 'contention/retained-host.rkt').read_text()
        self.assertIn('[else "initial_coloring_typing"]', source)
        self.assertNotIn('(set! phase "warm_typing")', source)
        self.assertNotIn('(set! phase "initial_lexer_settle")', source)
        self.assertIn('(for ([i (in-range 80)] #:break contention-error)', source)
        self.assertIn('(semaphore-wait done)', source)
        self.assertIn('(gui-yield (thread-dead-evt contention-producer))', source)
        self.assertIn("(record! 'exact_resulting_source_verified #t)", source)
        self.assertLess(source.index("(record! 'memory_after_workload"),
                        source.index('(define original-source'))

    def test_summary_keeps_dispatch_and_completion(self):
        sample = {key: index for index, key in enumerate((
            'command_ms', 'command_plus_low_priority_fence_ms', 'queue_to_handler_ms',
            'queue_to_editor_completion_ms', 'queue_to_fence_ms',
            'producer_scheduling_delay_ms', 'scheduled_to_editor_completion_ms',
            'scheduled_to_fence_ms'))}
        summary = runner.summarize({'initial_coloring_key_samples': [sample],
                                    'keys_starting_with_lexer_invalid': 1,
                                    'post_typing_lexer_settle': {'complete': True}})
        self.assertEqual(summary['keys_starting_with_lexer_invalid'], 1)
        self.assertTrue(summary['post_typing_lexer_settle']['complete'])
        for key, value in sample.items():
            self.assertEqual(summary['initial_coloring_key_samples'][key]['median'], value)


if __name__ == '__main__':
    unittest.main()
