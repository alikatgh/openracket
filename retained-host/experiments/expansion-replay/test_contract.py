#!/usr/bin/env python3
"""Headless source-contract tests, not worker or native benchmarks."""
import unittest
from pathlib import Path
from inspect_contract import build_report, ready_copy, READY_INSERT


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.worker = build_report(Path("/workspace/shared/openracket-drracket-host"))

    def test_verified_archives(self):
        self.assertTrue(all(r["verified"] for r in self.report["archives"].values()))

    def test_exact_base_fixture(self):
        self.assertEqual(self.report["fixture"]["bytes"], 1048576)
        self.assertEqual(self.report["fixture"]["edit_position"], 524139)

    def test_all_source_contracts(self):
        self.assertTrue(all(self.report["source_checks"].values()))

    def test_ready_seam_preserves_all_original_worker_bytes(self):
        patched = ready_copy(self.worker)
        self.assertEqual(patched.replace(READY_INSERT, "", 1), self.worker)

    def test_ready_after_handlers_before_job_loop(self):
        patched = ready_copy(self.worker)
        self.assertLess(patched.index("(dynamic-require file id)"), patched.index(READY_INSERT))
        self.assertLess(patched.index(READY_INSERT), patched.index("(let loop ([current-job #f]"))

    def test_missing_anchor_fails_closed(self):
        with self.assertRaises(ValueError):
            ready_copy("#lang racket/base\n")

    def test_no_false_performance_status(self):
        self.assertEqual(self.report["status"], "source_contract_verified_native_run_pending")
        self.assertIsNone(self.report["performance_measurements"])
        self.assertFalse(self.report["native_or_expansion_execution"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
