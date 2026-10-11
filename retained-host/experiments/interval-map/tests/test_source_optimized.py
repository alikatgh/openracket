"""Source checking must remain active under Python's optimized execution."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tests/check_interval_map_source.py"
STOCK = ROOT / "vendor/interval-map.rkt"
CANDIDATE = ROOT / "overlay/interval-map.rkt"


class OptimizedSourceChecks(unittest.TestCase):
    def test_valid_source_passes_optimized(self):
        result = subprocess.run([sys.executable, "-O", str(CHECK), str(STOCK), str(CANDIDATE)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS source scope", result.stdout)

    def test_unrelated_mutation_and_forced_enable_stay_rejected_optimized(self):
        original = CANDIDATE.read_text()
        mutations = [original.replace("(define (interval-map-cons*!", "(define (changed-cons*!", 1),
                     original.replace('(equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1")', "#t", 1)]
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "candidate.rkt"
            for source in mutations:
                file.write_text(source)
                result = subprocess.run([sys.executable, "-O", str(CHECK), str(STOCK), str(file)],
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("PASS source scope", result.stdout)


if __name__ == "__main__":
    unittest.main()
