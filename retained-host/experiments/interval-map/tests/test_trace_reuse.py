"""Guard the interval-specific activation while retaining the verified trace gates."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TraceReuseChecks(unittest.TestCase):
    def test_native_activation_selects_actual_interval_module(self):
        source = (ROOT / "tests/native-trace.rkt").read_text()
        self.assertIn("(dynamic-require 'data/interval-map", source)
        self.assertIn("'openracket-interval-map-fast-set-enabled?", source)
        self.assertIn('"OPENRACKET_INTERVAL_MAP_FAST_SET"', source)
        self.assertNotIn("openracket-xref-reply-cell", source)
        self.assertNotIn("OPENRACKET_XREF_REPLY_CELL", source)
        self.assertIn("'(interval-map xref traversals online-comp)", source)
        self.assertIn('acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7', source)

    def test_actual_handler_and_rename_protocol_remain_nonvacuous(self):
        source = (ROOT / "tests/native-trace.rkt").read_text()
        for anchor in ["(define suite-timeout 180)", "(define fixture-timeout 30)",
                       "(monitor (lambda (payload)", "(go expanded source-path source-path orig-cust)",
                       "(place-channel-put channel (list request-id query))",
                       "(handle-evt channel (lambda (v) (list v)))",
                       "'rename_answers rename-answers", "'trace (map encode trace)",
                       '"rename protocol must exercise both true and false answers"']:
            self.assertIn(anchor, source)


if __name__ == "__main__":
    unittest.main()
