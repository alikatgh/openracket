"""Portable source contracts only. Native fault controls require official Mac CI."""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReloadDiagnosticSourceTests(unittest.TestCase):
    def test_original_acceptance_is_not_relaxed(self):
        # Exact pre-diagnostic acceptance implementation remains authoritative.
        for name, pin in {
            "native/bootstrap.rkt": "667dc724830160c1bbe00f2b95234dd1bf880ec064ea5e7c282d596c13de4721",
            "native/snapshot.rkt": "468eed9ede02ccad91200546bf158e2eb182fe8a87e6b300c3fbbb52f0b9427e",
        }.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), pin)
        gate = (ROOT / "native/editor-gate.rkt").read_text()
        for term in ("(* 256 1024)", "30000", "40000", "(send restored load-file path 'standard)",
                     "(same! (editor-view restored) restored-view", "(record! 'rich_restored restored-view)",
                     "same-identities! original-snips", "same-identities! original-styles"):
            self.assertIn(term, gate)
        self.assertEqual(gate.count("(send restored load-file"), 1)
        self.assertNotIn("'text-force-cr", gate)
    def test_fault_controls_are_mandatory_before_fixture(self):
        gate = (ROOT / "native/editor-gate.rkt").read_text()
        self.assertIn("(run-failure-observation-controls!)", gate)
        start = gate.index("(define (run-gate!")
        self.assertLess(gate.index("(run-failure-observation-controls!)", start),
                        gate.index("(make-eventspace)", start))
    def test_reader_overloads_forward_once_and_keep_results(self):
        source = (ROOT / "native/failure-observation.rkt").read_text()
        for call in ("(super read-from-file stream)", "(super read-from-file stream argument)",
                     "(super read-from-file stream start overwrite?)"):
            self.assertEqual(source.count(call), 1)
        self.assertIn("(apply values results)", source)
        self.assertIn("(raise original)", source)
        self.assertIn("(best-effort (lambda () (observe-failure! original)))", source)
        self.assertIn("(check (eq? caught failure)", source)
        self.assertIn("actual arguments and values preserved", source)
        self.assertIn("super reader called exactly once", source)
    def test_native_fault_controls_cover_malformed_state_and_output(self):
        source = (ROOT / "native/failure-observation.rkt").read_text()
        for term in ("(raise diagnostic-failure)", "(write-json (hasheq 'malformed",
                     "(close-output-port closed-output)", "(display \"injected write\" closed-output)",
                     "original reader exception", "false reader result survives malformed/write-failing observations",
                     "failure observer is absent on success", "success values preserved"):
            self.assertIn(term, source)
    def test_failure_evidence_is_bounded_and_lossless(self):
        source = (ROOT / "native/reload-diagnostic.rkt").read_text()
        for term in ("(read-bytes (add1 byte-limit) in)", "(< 0 size byte-limit)",
                     "'sha256 (digest bytes)", "'encoding \"byte-array\"",
                     '(bytes->list bytes)', "'partial_restored",
                     "(send stream tell)", "(send stream ok?)", "(< (length events) 8)",
                     "(send registry find-position cls)", "(eq? (send registry nth index) cls)",
                     "(write-json report (open-output-string))"):
            self.assertIn(term, source)
        self.assertNotIn("(send registry add", source)
        self.assertNotIn("(send registry find ", source)
        self.assertNotIn("(send stream get", source)
        self.assertNotIn("(send stream skip", source)
        self.assertNotIn("(send stream jump-to", source)
        self.assertNotIn("(send restored load-file", source)
        self.assertNotIn("file->bytes", source)
    def test_diagnostics_publish_only_inside_failure_observer(self):
        source = (ROOT / "native/reload-diagnostic.rkt").read_text()
        start = source.index("(define (call/observe-reload-failure")
        body = source[start:]
        self.assertIn("(call/preserve-failure\n   load!\n   (lambda (original)", body)
        self.assertEqual(source.count("(record! 'reload_failure report)"), 1)
        self.assertLess(body.index("(write-json report"), body.index("(record! 'reload_failure"))
        self.assertIn('(hasheq \'status "unavailable"', source)
    def test_tell_runs_only_after_reader_has_failed(self):
        source = (ROOT / "native/reload-diagnostic.rkt").read_text()
        self.assertIn('(if failed?\n      (let ([position (send stream tell)])', source)
        self.assertIn('(equal? result \'(#f))', source)
        self.assertIn('(equal? phase "raised")', source)
        self.assertIn("'logical_item_position position", source)
        self.assertEqual(source.count("(send stream tell)"), 1)
    def test_native_fake_stream_controls_guard_tell_perturbation(self):
        source = (ROOT / "native/reload-diagnostic.rkt").read_text()
        for term in ("(stream-view stream #f)", "(stream-view stream #t)",
                     "(= tell-calls 0)", "(= tell-calls 1)",
                     "injected tell failure", "tell error preserves original false reader result",
                     "tell error is isolated while original returned value remains recorded",
                     "(run-forwarding-controls!)"):
            self.assertIn(term, source)

if __name__ == "__main__":
    unittest.main()
