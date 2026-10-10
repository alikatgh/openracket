#!/usr/bin/env python3
"""Test refusal/idempotence without installing or modifying any stock package."""
import hashlib,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PatchTests(unittest.TestCase):
 def test_idempotent_generation(self):
  target=ROOT/'overlay/mrlib/switchable-button.rkt'
  before=target.read_bytes()
  subprocess.run(['python3',str(ROOT/'scripts/prepare-overlay.py')],check=True,capture_output=True)
  self.assertEqual(before,target.read_bytes())
 def test_refuses_modified_source(self):
  before=(ROOT/'overlay/mrlib/switchable-button.rkt').read_bytes()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'switchable-button.rkt'
   p.write_bytes((ROOT/'vendor/switchable-button-v9.3.rkt').read_bytes()+b'\n; altered upstream\n')
   proc=subprocess.run(['python3',str(ROOT/'scripts/prepare-overlay.py'),'--source',str(p)],capture_output=True,text=True)
   self.assertNotEqual(proc.returncode,0)
   self.assertIn('stock source differs',proc.stderr)
  self.assertEqual(before,(ROOT/'overlay/mrlib/switchable-button.rkt').read_bytes())
 def test_pristine_original_matches_pin(self):
  source=ROOT/'vendor/switchable-button-v9.3.rkt'
  self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),(ROOT/'vendor/upstream-sha256.txt').read_text().split()[0])
if __name__=='__main__': unittest.main()
