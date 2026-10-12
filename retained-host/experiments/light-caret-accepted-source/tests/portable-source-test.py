#!/usr/bin/env python3
"""Source provenance for the combined installer; no install or GUI execution."""
import hashlib,json
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
class PortableSourceTests(unittest.TestCase):
    def test_tested_appearance_implementation_remains_exact(self):
        base=json.loads((ROOT/'BASE-SOURCE-SHA256.json').read_text())
        allowed={'README.md','scripts/proof-env.sh','scripts/setup-openracket.sh',
                 'scripts/launch-openracket.sh','scripts/launch-stock.sh','scripts/preflight.rkt',
                 'scripts/package-proof.py'}
        changed={name for name,value in base.items() if digest(ROOT/name)!=value}
        self.assertEqual(changed - {'reports/patch-manifest.json'},allowed)
        reference=ROOT/'tests/reference/polish-patch-manifest-1316.json'
        self.assertEqual(digest(reference),base['reports/patch-manifest.json'])
        old=json.loads(reference.read_text());current=json.loads((ROOT/'reports/patch-manifest.json').read_text())
        old.pop('source');source=current.pop('source')
        self.assertTrue(source.endswith('/vendor/switchable-button-v9.3.rkt'))
        self.assertEqual(current,old)
    def test_measured_guard_has_exact_native_measured_bytes(self):
        self.assertEqual(digest(ROOT/'overlay/framework/private/text-misc.rkt'),
                         '00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d')
        self.assertFalse((ROOT/'overlay/drracket/private/openracket-all-string-fastpath.rkt').exists())
        self.assertFalse((ROOT/'overlay/framework/private/color.rkt').exists())
    def test_combined_save_caller_is_an_exact_bounded_derivative(self):
        with tempfile.TemporaryDirectory(prefix='openracket-portable-source-') as temp:
            root=Path(temp)
            for rel in ('scripts/prepare-portable-save-test.py','tests/reference/autosave-host-1448.rkt'):
                path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,path)
            (root/'reports').mkdir()
            result=subprocess.run([sys.executable,str(root/'scripts/prepare-portable-save-test.py')],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ('tests/portable-native-save-host.rkt','reports/portable-save-caller.patch',
                         'reports/portable-save-caller.json'):
                self.assertEqual((root/name).read_bytes(),(ROOT/name).read_bytes(),name)
    def test_native_save_and_failure_fixtures_remain_exact(self):
        for name,sha in {'independent-native-save-recovery.rkt':'43fe9b415804bc5458bdaacf86bd9ebdd8cad34dd477fef9c3aa35698c799a01',
                         'review-native-save-failure.rkt':'e8f78dcd4f81b711e674745491eb4126abf97e55c066c53972b781a7c1211f46'}.items():
            self.assertEqual(digest(ROOT/'tests'/name),sha)
if __name__=='__main__': unittest.main()
