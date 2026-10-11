"""No native execution: process and timeout calls are injected test doubles."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_native

class RunnerTests(unittest.TestCase):
    def test_preserves_raw_failure_output(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            out=Path(temp)/"on"
            raw=b"\xff\x00full failure\n"*1000
            def fake(command, **kwargs):
                kwargs["stdout"].write(raw); kwargs["stderr"].write(raw)
                return SimpleNamespace(returncode=1)
            r=run_native.capture(Path("/fake/racket"),Path("/fake"),"on",out,run=fake)
            self.assertEqual(r["returncode"],1)
            self.assertEqual((out/"stderr.bin").read_bytes(),raw)
            self.assertEqual(r["stderr.bin"]["bytes"],len(raw))
    def test_timeout_retains_partial_bytes_and_failure_status(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            out=Path(temp)/"stock"
            def fake(command, **kwargs):
                kwargs["stdout"].write(b"before timeout")
                raise subprocess.TimeoutExpired(command,180)
            r=run_native.capture(Path("/fake/racket"),Path("/fake"),"stock",out,run=fake)
            self.assertTrue(r["timed_out"])
            self.assertIsNone(r["returncode"])
            self.assertEqual((out/"stdout.bin").read_bytes(),b"before timeout")
            self.assertTrue((out/"process.json").is_file())
    def test_launch_failure_retains_traceback(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            def fake(*a,**k): raise OSError("explicit test launch failure")
            r=run_native.capture(Path("/fake/racket"),Path("/fake"),"stock",Path(temp)/"stock",run=fake)
            self.assertIn("explicit test launch failure",r["launch_failure"])
            self.assertFalse(r["native_executed"])
    def test_environment_contamination_rejected(self):
        for key in ("OPENRACKET_BINDING_TABLE","OPENRACKET_NAMED_STYLE_INDEX","PYTHONOPTIMIZE",
                    "PLTCOLLECTS","PLTCOMPILEDROOTS","PLTCONFIGDIR","PLTLINKS","PLT_LINKS",
                    "PLT_COMPILED_FILE_CHECK","PLT_ZO_PATH","PLTDRDEBUG","PLTDRCM","PLTDRPAR",
                    "PLTUSERHOME","PLTADDONDIR","XDG_CONFIG_HOME","XDG_CACHE_HOME","XDG_DATA_HOME"):
            with self.subTest(key=key), patch.dict(os.environ,{key:"1"},clear=True), self.assertRaises(ValueError):
                run_native.environment("stock",Path("/tmp/parser-only-profile"))
    def test_explicit_flag_and_distinct_profile(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertNotIn("OPENRACKET_NAMED_STYLE_INDEX",run_native.environment("stock",Path("/profiles/a")))
            self.assertEqual(run_native.environment("off",Path("/profiles/b"))["OPENRACKET_NAMED_STYLE_INDEX"],"0")
            self.assertEqual(run_native.environment("on",Path("/profiles/c"))["OPENRACKET_NAMED_STYLE_INDEX"],"1")
    def test_rejects_relative_native_paths(self):
        with self.assertRaises(ValueError): run_native.native_paths(Path("racket"),Path("runtime"))

if __name__=="__main__": unittest.main()
