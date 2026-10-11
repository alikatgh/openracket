import contextlib,hashlib,importlib.util,io,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).parent
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/file);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
mod=module('evidence','emit-replay-evidence.py');decoder=module('decoder','decode-replay-evidence.py')
class EvidenceTests(unittest.TestCase):
 def roundtrip(self,value,mutate=None):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);p=root/'replay/replay.json';p.parent.mkdir();p.write_text(json.dumps(value,ensure_ascii=False))
   out=io.StringIO()
   with contextlib.redirect_stdout(out):mod.emit(p)
   lines=out.getvalue().splitlines();self.assertTrue(all(len(x.encode())<60000 for x in lines))
   if mutate:lines=mutate(lines)
   rows=decoder.decode('\n'.join(lines),root/'decoded');self.assertEqual(len(rows),1)
   self.assertEqual(json.loads(pathlib.Path(rows[0]['path']).read_text()),value)
   self.assertEqual(rows[0]['canonical_sha256'],hashlib.sha256(mod.packed(value).encode()).hexdigest())
   return lines
 def test_lossless_nested_gc_rows(self):
  self.roundtrip({'trials':[{'gc':{'records':[{'time':i,'info':'GC λ'} for i in range(97)]}},{'result':'error remains visible'}]})
 def test_under_forty_large_samples(self):
  self.roundtrip({'trials':[{'samples':[{'thread':'x'*2500,'index':i} for i in range(32)]}]})
 def test_byte_not_just_count_splits(self):
  value={'rows':[{'a':'x'*3000,'b':'y'*3000} for _ in range(22)]}
  lines=self.roundtrip(value);rows=[json.loads(x.split(' ',1)[1]) for x in lines if 'ARRAY_JSON ' in x]
  self.assertTrue(any(len(row['items'])<20 for row in rows));self.assertTrue(all(len(row['items'])<=20 for row in rows))
 def test_maximum_phase_probe_nested_stacks(self):
  # Two trials, 256 samples each, two actual threads, 8 capped frames/thread.
  sample={'threads':[{'role':role,'frames':[{'name':'🌈'*240,'source':'🌈'*240,'line':i} for i in range(8)]} for role in ('worker','monitor')]}
  self.roundtrip({'trials':[{'phase_probe':{'samples':[sample for _ in range(256)],'points':[{'phase':i} for i in range(128)]}} for _ in range(2)]})
 def test_reordered_chunks_rejected(self):
  def change(lines):
   ids=[i for i,x in enumerate(lines) if 'ARRAY_JSON ' in x];lines[ids[0]],lines[ids[1]]=lines[ids[1]],lines[ids[0]];return lines
  with self.assertRaisesRegex(AssertionError,'Missing/reordered'):self.roundtrip({'records':list(range(100))},change)
 def test_nested_array_digest_tampering_rejected(self):
  def change(lines):
   i=next(i for i,x in enumerate(lines) if 'ARRAY_JSON ' in x);p,s=lines[i].split(' ',1);data=json.loads(s);data['items'][0]='tampered';lines[i]=p+' '+json.dumps(data);return lines
  with self.assertRaises(AssertionError):self.roundtrip({'records':list(range(100))},change)
 def test_whole_document_digest_tampering_rejected(self):
  def change(lines):return [x.replace('"small":"correct"','"small":"changed"') for x in lines]
  with self.assertRaisesRegex(AssertionError,'Whole-document hash'):self.roundtrip({'small':'correct'},change)
 def test_truncated_document_rejected(self):
  with self.assertRaisesRegex(AssertionError,'Truncated'):self.roundtrip({'small':'correct'},lambda lines:lines[:-1])
 def test_oversized_single_line_refused(self):
  with self.assertRaises(AssertionError):mod.encode({'unexpected':'x'*60001})
 def test_oversized_single_item_refused(self):
  with self.assertRaises(AssertionError):mod.encode({'items':['x'*60001]})
 def test_reserved_key_refused(self):
  with self.assertRaises(AssertionError):mod.encode({'__openracket_log_array__':0})
 def test_request_payload_file_refused(self):
  with self.assertRaises(AssertionError):mod.emit(pathlib.Path('capture.rktd'))
if __name__=='__main__':unittest.main()
