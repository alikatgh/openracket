import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_budget', ROOT / 'scripts/prepare-budget.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SourceTests(unittest.TestCase):
    def test_exact_official_pin(self):
        self.assertEqual(hashlib.sha256((ROOT / 'vendor/color-v9.3.rkt').read_bytes()).hexdigest(), module.PIN)

    def test_only_configuration_and_defer_threshold_change(self):
        stock = (ROOT / 'vendor/color-v9.3.rkt').read_text()
        patched = (ROOT / 'overlay/framework/private/color.rkt').read_text()
        self.assertEqual(patched.count(module.CONFIG), 1)
        self.assertEqual(patched.count(module.NEW), 1)
        self.assertEqual(patched.replace(module.CONFIG, '', 1).replace(module.NEW, module.OLD, 1), stock)

if __name__ == '__main__':
    unittest.main()
