import copy,hashlib,importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('e',ROOT/'named-style-evidence.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
spec=importlib.util.spec_from_file_location('transport',ROOT/'emit-replay-evidence.py');transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)
class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=pathlib.Path(self.t.name).resolve()
 def inputs(self):
  items=[]
  for i,label in enumerate(sorted(e.expected_labels())):
   p=self.root/(str(i)+'.json');p.write_text(json.dumps({'value':i,'unicode':'λ'},indent=2)+'\n');items.append((p,label))
  bylabel={label:p for p,label in items}
  for pair in range(1,4):
   for arm in ('stock','candidate'):
    manifest=bylabel[arm+'-prepared-manifest']
    bylabel[f'pair-{pair}-{arm}-capture-supervisor'].write_text(json.dumps({'manifest':str(manifest),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}))
  acceptances=[]
  for pair in range(1,4):
   folder=self.root/f'pair-{pair}';folder.mkdir(exist_ok=True);a=folder/'acceptance.json'
   a.write_text(json.dumps({'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p,label in items if label.startswith(f'pair-{pair}-')}}));acceptances.append(a)
  return items,acceptances
 def test_raw_canonical_are_separate_and_acceptance_is_bound(self):
  items,a=self.inputs();r=e.create_map(items,a,self.root/'map.json');self.assertTrue(r['verified']);self.assertEqual(len(r['entries']),62)
  self.assertNotEqual(r['entries'][0]['raw_sha256'],r['entries'][0]['canonical_sha256'])
 def test_missing_and_changed_original_keep_partial_map(self):
  items,a=self.inputs();items[0][0].unlink();r=e.create_map(items,a,self.root/'map.json');self.assertFalse(r['verified']);self.assertEqual(len(r['entries']),61);self.assertGreaterEqual(len(r['errors']),2)
 def test_duplicate_label_and_mismatched_receipt_fail(self):
  items,a=self.inputs();items[1]=(items[1][0],items[0][1]);self.assertFalse(e.create_map(items,a,self.root/'map.json')['verified'])
  items,a=self.inputs();a[0].write_text(json.dumps({'input_sha256':{str(items[0][0]):'0'*64}}));self.assertFalse(e.create_map(items,a,self.root/'map2.json')['verified'])
 def test_duplicate_path_unknown_label_and_wrong_coverage_refused(self):
  items,a=self.inputs();items[1]=(items[0][0],items[1][1]);self.assertFalse(e.create_map(items,a,self.root/'map.json')['verified'])
  items,a=self.inputs();items[0]=(items[0][0],'unrelated');self.assertFalse(e.create_map(items,a,self.root/'map2.json')['verified'])
  items,a=self.inputs();r=json.loads(a[0].read_text());r['input_sha256'].pop(next(iter(r['input_sha256'])));a[0].write_text(json.dumps(r));self.assertFalse(e.create_map(items,a,self.root/'map3.json')['verified'])
 def test_duplicate_json_nonfinite_symlink_and_nonobject_refused(self):
  p=self.root/'a.json'
  for data in ('{"x":1,"x":2}','{"x":NaN}','[]'):
   p.write_text(data)
   with self.assertRaises(ValueError):e.input_record(p)
  p.write_text('{}');link=self.root/'b.json';link.symlink_to(p)
  with self.assertRaises(ValueError):e.input_record(link)
 def test_unicode_large_nested_text_roundtrip_and_array_transport(self):
  value={'runs':[{'stdout':'🧪λ\n' * 30000,'stderr':'failure\n' * 600} for _ in range(4)]}
  wrapped=e.wrap_text(value);self.assertEqual(e.restore_text(wrapped),value)
  skeleton,chunks=transport.encode(wrapped);self.assertTrue(chunks)
  self.assertLess(len(transport.packed(skeleton).encode()),45000)
  p=self.root/'source.json';p.write_text(json.dumps(value,ensure_ascii=False));before=p.read_bytes();out=self.root/'wrapped.json';r=e.transport_json_copy(p,out)
  self.assertEqual(p.read_bytes(),before);self.assertEqual(r['original_raw_sha256'],hashlib.sha256(before).hexdigest());self.assertEqual(e.restore_text(r['document']),value)
 def test_missing_duplicate_reordered_changed_chunks_refused(self):
  good=e.wrap_text('🧪abcdef' * 1400)
  for mutate in (lambda x:x['chunks'].pop(),lambda x:x['chunks'].append(x['chunks'][0]),lambda x:x['chunks'].reverse(),lambda x:x['chunks'][0].update(text='bad'),lambda x:x.update(bytes=True),lambda x:x['chunks'][0].update(index=True)):
   bad=copy.deepcopy(good);mutate(bad)
   with self.assertRaises(ValueError):e.restore_text(bad)
 def test_prepared_manifest_bound_through_hashed_supervisor(self):
  items,a=self.inputs();supervisor=next(p for p,label in items if label=='pair-2-candidate-capture-supervisor')
  value=json.loads(supervisor.read_text());value['manifest_sha256']='0'*64;supervisor.write_text(json.dumps(value))
  receipt=json.loads(a[1].read_text());receipt['input_sha256'][str(supervisor)]=hashlib.sha256(supervisor.read_bytes()).hexdigest();a[1].write_text(json.dumps(receipt))
  result=e.create_map(items,a,self.root/'map.json');self.assertFalse(result['verified']);self.assertTrue(any('Supervisor' in row['error'] for row in result['errors']))
 def test_reserved_text_marker_refused(self):
  with self.assertRaises(ValueError):e.wrap_text({e.TEXT_KEY:'collision'})
if __name__=='__main__':unittest.main()
