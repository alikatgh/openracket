#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_check', ROOT/'scripts/verify-installed-candidate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class InstalledSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='scan-source-check-')
        self.root = Path(self.tmp.name)/'runtime'; self.root.mkdir()
        self.unit = self.root/'unit.rkt'
        self.framework = self.root/'text-misc.rkt'
        self.helper = self.root/'helper.rkt'
        shutil.copyfile(ROOT/'vendor/unit-v9.3.rkt', self.unit)
        shutil.copyfile(ROOT/'vendor/text-misc-v9.3.rkt', self.framework)
    def tearDown(self): self.tmp.cleanup()
    def check(self, mode):
        return module.check(self.root, self.unit, self.framework, self.helper, mode)
    def candidate(self):
        shutil.copyfile(ROOT/'overlay/drracket/private/unit.rkt', self.unit)
        shutil.copyfile(ROOT/'overlay/drracket/private/openracket-all-string-snips.rkt', self.helper)
    def test_stock_and_candidate(self):
        self.assertFalse(self.check('stock')['native_activation_proven'])
        self.candidate()
        self.assertEqual(self.check('candidate')['source_check'], 'passed')
    def test_generic_framework_tamper_refused(self):
        self.candidate(); self.framework.write_bytes(self.framework.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'generic mixin'): self.check('candidate')
    def test_wrong_arm_refused(self):
        self.candidate()
        with self.assertRaisesRegex(ValueError, 'composition'): self.check('stock')
    def test_helper_tamper_refused(self):
        self.candidate(); self.helper.write_text('wrong')
        with self.assertRaisesRegex(ValueError, 'helper source'): self.check('candidate')
    def test_outside_path_refused(self):
        self.unit = Path(self.tmp.name)/'outside.rkt'
        shutil.copyfile(ROOT/'vendor/unit-v9.3.rkt', self.unit)
        with self.assertRaisesRegex(ValueError, 'selected runtime'): self.check('stock')
    def test_root_symlink_refused(self):
        alias = Path(self.tmp.name)/'alias'; alias.symlink_to(self.root, target_is_directory=True)
        self.root = alias
        with self.assertRaisesRegex(ValueError, 'real directory'): self.check('stock')
    def test_file_symlink_refused(self):
        original = self.root/'original.rkt'; self.unit.rename(original); self.unit.symlink_to(original)
        with self.assertRaisesRegex(ValueError, 'symlinked'): self.check('stock')
if __name__ == '__main__': unittest.main()
