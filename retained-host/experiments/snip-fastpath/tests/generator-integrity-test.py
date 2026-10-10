#!/usr/bin/env python3
"""No installation or runtime launch: isolated exact-source generation checks."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GeneratorIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='openracket-private-scan-')
        self.root = Path(self.tmp.name)
        for name in ('vendor', 'scripts'):
            shutil.copytree(ROOT/name, self.root/name,
                            ignore=shutil.ignore_patterns('__pycache__', 'compiled'))
        (self.root/'reports').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_generator(self):
        return subprocess.run([sys.executable, str(self.root/'scripts/prepare-fastpath.py')],
                              cwd=self.root, capture_output=True, text=True)

    def test_deterministic_output_and_manifest(self):
        self.assertEqual(self.run_generator().returncode, 0)
        first = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.run_generator().returncode, 0)
        self.assertEqual(first, {p.relative_to(self.root): p.read_bytes()
                                for p in self.root.rglob('*') if p.is_file()})
        manifest = json.loads((self.root/'reports/fastpath-manifest.json').read_text())
        helper = self.root/'overlay'/manifest['helper_module']
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(),
                         manifest['helper_sha256'])
        unit = self.root/'overlay/drracket/private/unit.rkt'
        self.assertEqual(hashlib.sha256(unit.read_bytes()).hexdigest(),
                         manifest['sources']['drracket/private/unit.rkt']['patched_sha256'])
        self.assertFalse((self.root/'overlay/framework/private/text-misc.rkt').exists())

    def check_refused(self, filename, mutate):
        source = self.root/'vendor'/filename
        source.write_bytes(mutate(source.read_bytes()))
        result = self.run_generator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refuse byte-different', result.stderr)
        self.assertFalse((self.root/'overlay').exists())

    def test_framework_raw_bytes_are_pinned(self):
        self.check_refused('text-misc-v9.3.rkt', lambda b: b.replace(b'\n', b'\r\n'))

    def test_drracket_raw_bytes_are_pinned(self):
        self.check_refused('unit-v9.3.rkt', lambda b: b.replace(b'\n', b'\r\n'))

    def test_framework_content_tamper_is_refused(self):
        self.check_refused('text-misc-v9.3.rkt', lambda b: b+b'\n; tampered\n')

    def test_drracket_content_tamper_is_refused(self):
        self.check_refused('unit-v9.3.rkt', lambda b: b+b'\n; tampered\n')

if __name__ == '__main__':
    unittest.main()
