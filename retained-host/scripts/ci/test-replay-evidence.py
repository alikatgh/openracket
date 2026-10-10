import hashlib,importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('evidence',pathlib.Path(__file__).with_name('emit-replay-evidence.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class EvidenceTests(unittest.TestCase):
 def test_lossless_nested_gc_rows(self):
  value={'trials':[{'gc':{'records':[{'time':i,'info':'GC λ'} for i in range(97)]}},{'result':'error remains visible'}]}
  skeleton,chunks=mod.encode(value);self.assertEqual(len(chunks),1)
  rows=[]
  for chunk in chunks[0]['rows']:self.assertEqual(chunk['index'],len(rows));rows+=chunk['items']
  self.assertEqual(hashlib.sha256(mod.packed(rows).encode()).hexdigest(),chunks[0]['sha256'])
  skeleton['trials'][0]['gc']['records']=rows;self.assertEqual(skeleton,value)
 def test_oversized_single_line_refused(self):
  with self.assertRaises(AssertionError):mod.encode({'unexpected':'x'*60001})
 def test_request_payload_file_refused(self):
  with self.assertRaises(AssertionError):mod.emit(pathlib.Path('capture.rktd'))
if __name__=='__main__':unittest.main()
