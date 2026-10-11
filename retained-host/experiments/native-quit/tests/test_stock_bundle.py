"""Pure stock-control plist fixture tests; does not generate or run native code."""
import hashlib,importlib.util,json,pathlib,plistlib,shutil,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('stock_bundle',ROOT/'scripts/prepare-stock-bundle.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class Metadata(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=pathlib.Path(self.temp.name)/'OpenRacketStockQuitControl.app';(self.app/'Contents/MacOS').mkdir(parents=True)
        self.native=self.app/'Contents/MacOS/OpenRacketStockQuitControl';self.native.write_bytes(b'unit-only-native-bytes')
        self.plist=self.app/'Contents/Info.plist';self.info={'CFBundleExecutable':'OpenRacketStockQuitControl','CFBundleIdentifier':'org.racket-lang.OpenRacketStockQuitControl','CFBundlePackageType':'APPL','CFBundleDocumentTypes':[{'CFBundleTypeExtensions':['rkt']}],'UnknownPreserved':['value',42]};self.write()
    def write(self):self.plist.write_bytes(plistlib.dumps(self.info))
    def test_removes_only_association_and_preserves_native_bytes(self):
        b=self.native.read_bytes();r=M.prepare(self.app);expected=dict(self.info);expected.pop('CFBundleDocumentTypes')
        self.assertEqual(plistlib.loads(self.plist.read_bytes()),expected);self.assertEqual(self.native.read_bytes(),b)
        self.assertTrue(r['native_bytes_unchanged']);self.assertTrue(r['removed_only_document_types'])
    def test_absent_claim_does_not_even_rewrite_plist(self):
        self.info.pop('CFBundleDocumentTypes');self.write();b=self.plist.read_bytes();M.prepare(self.app);self.assertEqual(self.plist.read_bytes(),b)
    def test_wrong_identity_and_environment_claim_refused_without_write(self):
        for key,value in [('CFBundleIdentifier','other'),('CFBundleExecutable','other'),('LSEnvironment',{'bad':'value'})]:
            old=dict(self.info);self.info[key]=value;self.write();b=self.plist.read_bytes()
            with self.subTest(key=key),self.assertRaises(ValueError):M.prepare(self.app)
            self.assertEqual(self.plist.read_bytes(),b);self.info=old
    def test_symlinked_components_refused_without_outside_mutation(self):
        for index,component in enumerate(('Contents','Contents/Info.plist','Contents/MacOS','Contents/MacOS/OpenRacketStockQuitControl')):
            case=pathlib.Path(self.temp.name)/('case-'+str(index));case.mkdir();app=case/self.app.name
            shutil.copytree(self.app,app);target=app/component;outside=case/'outside-owned-witness';target.rename(outside)
            target.symlink_to(outside,target_is_directory=outside.is_dir())
            def snapshot():
                paths=[outside] if outside.is_file() else sorted(p for p in outside.rglob('*') if p.is_file())
                return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            before=snapshot()
            with self.subTest(component=component),self.assertRaises(ValueError):M.prepare(app)
            self.assertEqual(snapshot(),before)
            self.assertFalse((case/'stock-control-metadata.json').exists())
    def test_existing_preparation_receipt_prevents_retry(self):
        M.prepare(self.app);b=self.plist.read_bytes()
        with self.assertRaises(ValueError):M.prepare(self.app)
        self.assertEqual(self.plist.read_bytes(),b)
if __name__=='__main__':unittest.main(verbosity=2)
