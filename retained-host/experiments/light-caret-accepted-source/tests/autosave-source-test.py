"""Exact bytes, deterministic generation and refusal tests; no GUI or install."""
import hashlib, json
from pathlib import Path
import shutil, subprocess, sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
PIN='7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638'
class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='openracket-autosave-')
        self.root=Path(self.temp.name)
        for name in ('scripts','vendor'): shutil.copytree(ROOT/name,self.root/name,ignore=shutil.ignore_patterns('__pycache__','compiled'))
        (self.root/'reports').mkdir()
    def tearDown(self): self.temp.cleanup()
    def generate(self):
        return subprocess.run([sys.executable,self.root/'scripts/prepare-autosave.py'],capture_output=True,text=True)
    def test_only_two_guards_and_config_export_differ(self):
        self.assertEqual(self.generate().returncode,0)
        original=(self.root/'vendor/text-misc-v9.3.rkt').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),PIN)
        source=(self.root/'overlay/framework/private/text-misc.rkt').read_text()
        start=source.index(';; Default-off experiment:')
        end=source.index('(provide text-misc@ openracket-experimental-save-scan-guard?)',start)
        source=source[:start]+source[end:]
        source=source.replace('(provide text-misc@ openracket-experimental-save-scan-guard?)','(provide text-misc@)',1)
        guard="(or (not openracket-experimental-save-scan-guard?) (eq? format 'same))"
        self.assertEqual(source.count(guard),2)
        source=source.replace(guard+'\n               ', '',1).replace(guard+'\n                   ','',1)
        self.assertEqual(source.encode(),original)
    def test_output_and_manifest_are_deterministic(self):
        self.assertEqual(self.generate().returncode,0)
        first={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.generate().returncode,0)
        self.assertEqual(first,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        m=json.loads((self.root/'reports/autosave-manifest.json').read_text())
        self.assertEqual(hashlib.sha256((self.root/'overlay'/m['module']).read_bytes()).hexdigest(),m['patched_sha256'])
        self.assertFalse(m['default_enabled'])
    def test_crlf_upstream_is_refused(self):
        p=self.root/'vendor/text-misc-v9.3.rkt';p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'))
        r=self.generate();self.assertNotEqual(r.returncode,0);self.assertIn('Refuse byte-different',r.stderr)
        self.assertFalse((self.root/'overlay').exists())
    def test_tampered_upstream_is_refused(self):
        p=self.root/'vendor/text-misc-v9.3.rkt';p.write_bytes(p.read_bytes()+b'\n; altered\n')
        self.assertNotEqual(self.generate().returncode,0)
        self.assertFalse((self.root/'overlay').exists())
    def test_required_save_sources_are_not_overlays(self):
        required=json.loads((ROOT/'reports/required-stock-save-sources.json').read_text())
        for filename,metadata in required.items():
            self.assertEqual(hashlib.sha256((ROOT/'vendor'/filename).read_bytes()).hexdigest(),metadata['sha256'])
            self.assertFalse(metadata['modified'])
            self.assertFalse((ROOT/'overlay'/metadata['original_module']).exists())
        source=(ROOT/'vendor/editor-misc-v9.3.rkt').read_text()
        self.assertIn("(save-file auto-name 'copy #f)",source)
if __name__=='__main__':unittest.main()
