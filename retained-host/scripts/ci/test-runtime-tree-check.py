#!/usr/bin/env python3
"""Synthetic filesystem tests for the runtime immutability witness; no GUI."""
import os,pathlib,subprocess,sys,tempfile,unittest
SCRIPT=pathlib.Path(__file__).with_name('runtime-tree-check.py')

class RuntimeTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='openracket-tree-test-')
        self.root=pathlib.Path(self.temp.name);self.runtime=self.root/'Racket copy'
        (self.runtime/'compiled').mkdir(parents=True)
        (self.runtime/'source.rkt').write_text('#lang racket/base\n')
        (self.runtime/'compiled/source_rkt.zo').write_bytes(b'synthetic-bytecode')
        self.manifest=self.root/'baseline.json'
        self.env={**os.environ,'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'alikatgh/openracket','GITHUB_REF':'refs/heads/prototype/retained-drracket','RUNNER_TEMP':str(self.root)}
    def tearDown(self):self.temp.cleanup()
    def run_check(self,operation):
        return subprocess.run([sys.executable,str(SCRIPT),operation,str(self.runtime),str(self.manifest)],env=self.env,text=True,capture_output=True)
    def baseline(self):self.assertEqual(self.run_check('baseline').returncode,0)
    def test_identical_runtime_passes_and_baseline_is_not_overwritten(self):
        self.baseline();self.assertEqual(self.run_check('compare').returncode,0)
        self.assertNotEqual(self.run_check('baseline').returncode,0)
    def test_changed_compiled_file_is_detected(self):
        self.baseline();(self.runtime/'compiled/source_rkt.zo').write_bytes(b'recompiled')
        self.assertNotEqual(self.run_check('compare').returncode,0)
    def test_added_deleted_and_mode_changed_files_are_detected(self):
        for change in ('add','delete','mode'):
            with self.subTest(change=change):
                self.manifest.unlink(missing_ok=True);self.baseline()
                p=self.runtime/'source.rkt'
                if change=='add':(self.runtime/'new.zo').write_text('new')
                elif change=='delete':p.unlink()
                else:p.chmod(0o600 if p.stat().st_mode&0o777 !=0o600 else 0o644)
                self.assertNotEqual(self.run_check('compare').returncode,0)
                (self.runtime/'new.zo').unlink(missing_ok=True);p.write_text('#lang racket/base\n')
    def test_root_mode_and_link_target_changes_are_detected(self):
        link=self.runtime/'link';link.symlink_to('source.rkt');self.baseline()
        link.unlink();link.symlink_to('compiled/source_rkt.zo');self.assertNotEqual(self.run_check('compare').returncode,0)
        self.manifest.unlink();self.baseline();self.runtime.chmod(0o700 if self.runtime.stat().st_mode&0o777 !=0o700 else 0o755)
        self.assertNotEqual(self.run_check('compare').returncode,0)
    def test_root_symlink_is_refused(self):
        alternate=self.root/'link-root';alternate.symlink_to(self.runtime,target_is_directory=True)
        result=subprocess.run([sys.executable,str(SCRIPT),'baseline',str(alternate),str(self.manifest)],env=self.env,capture_output=True)
        self.assertNotEqual(result.returncode,0)
if __name__=='__main__':unittest.main()
