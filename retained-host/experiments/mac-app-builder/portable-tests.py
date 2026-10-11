#!/usr/bin/env python3
"""SOURCE CHECKS ONLY. Never invokes Racket, installs software or opens a GUI.

The 20 unchanged baseline tests use the reviewed PYTHON reference decorator with
this candidate's byte-identical scripts, not the unexecuted Racket implementation.
Additional checks cover syntax delimiters, source pins, and the new build shell.
Python is optional QA tooling, NOT a dependency for building the app on a Mac.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / 'openracket-mac-app-plan'
FROZEN = HERE.parent / 'openracket-preview-memory-freeze-20261011-0520'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# The baseline Python test module imports make_app by name. Changing HERE only
# selects our copied scripts; we never change/write the reviewed reference files.
oracle = load('make_app', REFERENCE / 'make_app.py')
oracle.HERE = HERE
baseline = load('baseline_app_contracts', REFERENCE / 'test_app.py')
baseline.FROZEN = FROZEN

def scan_racket_delimiters(path):
    """Lexical balance only, intentionally NOT a Racket parser/compiler."""
    text = path.read_text()
    stack = []
    i = 0
    while i < len(text):
        ch = text[i]
        if text.startswith('#<<', i):
            end = text.index('\n', i)
            marker = text[i + 3:end]
            finish = text.index('\n' + marker + '\n', end)
            i = finish + len(marker) + 2
            continue
        if ch == ';':
            end = text.find('\n', i)
            i = len(text) if end < 0 else end + 1
            continue
        if ch == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                elif text[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise AssertionError(f'{path.name}: unterminated string')
            continue
        if ch in '([{':
            stack.append((ch, i))
        elif ch in ')]}':
            assert stack and stack[-1][0] == {')': '(', ']': '[', '}': '{'}[ch], (path.name, i, stack[-1:] if stack else [])
            stack.pop()
        i += 1
    assert not stack, (path.name, stack)

class PortSourceContracts(unittest.TestCase):
    def test_unchanged_app_scripts_and_generator(self):
        for name in ('bootstrap.sh', 'runtime-dispatch.sh', 'report-error.applescript', 'make-native-launcher.rkt'):
            self.assertEqual((HERE/name).read_bytes(), (REFERENCE/name).read_bytes(), name)
    def test_racket_delimiters_only(self):
        for name in ('make-app.rkt', 'make-native-launcher.rkt', 'test-app.rkt'):
            scan_racket_delimiters(HERE/name)
    def test_shell_syntax(self):
        for name in ('build-app.sh', 'bootstrap.sh', 'runtime-dispatch.sh'):
            subprocess.run(['/bin/sh', '-n', str(HERE/name)], check=True)
    def test_exact_manifest_and_155_sources(self):
        manifest = FROZEN/'CONTENTS-SHA256.json'
        self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(), oracle.MANIFEST_SHA256)
        self.assertIn(oracle.MANIFEST_SHA256, (HERE/'make-app.rkt').read_text())
        data = json.loads(manifest.read_text())
        self.assertEqual(len(data), 155)
        for name, sha in data.items():
            self.assertEqual(hashlib.sha256((FROZEN/name).read_bytes()).hexdigest(), sha, name)
    def test_new_entry_sanitizes_before_fake_racket(self):
        with tempfile.TemporaryDirectory(prefix="racket-port ' λ ") as tmp:
            root=Path(tmp); source=root/'source'; (source/'profile').mkdir(parents=True)
            runtime=root/'runtime'; runtime.mkdir(); fake=runtime/'racket'
            capture=root/'capture.json'
            # Explicit fake fixture only. It reports argv/env and exits; it never
            # forwards to Racket, downloads a runtime or evaluates app code.
            fake.write_text(f'#!{sys.executable}\nimport os,sys,json\njson.dump({{"argv":sys.argv[1:],"env":dict(os.environ)}},open(os.environ["QA_CAPTURE"],"w"))\n')
            fake.chmod(0o755)
            env=dict(os.environ, QA_CAPTURE=str(capture))
            for key in oracle.ISOLATION_OVERRIDES:
                env[key]='poison'
            env.update(PLTCOMPILEDROOTS='/poison',PLTADDONDIR='/poison',PLTUSERHOME='/poison',XDG_CACHE_HOME='/poison')
            command=['/bin/sh',str(HERE/'build-app.sh'),'--source',str(source),'--runtime-root',str(runtime),'--racket',str(fake),'--output',str(root/'new.app')]
            subprocess.run(command,env=env,check=True)
            result=json.loads(capture.read_text())
            self.assertEqual(result['argv'][:5], ['-U','-A',str(source/'profile/.local/share/racket'),'-R',str(source/'profile/compiled-cache')+':'])
            self.assertEqual(result['argv'][5],str(HERE/'make-app.rkt'))
            for key in oracle.ISOLATION_OVERRIDES:
                self.assertNotIn(key,result['env'])
            self.assertEqual(result['env']['PLTUSERHOME'],str(source/'profile'))
            self.assertEqual(result['env']['PATH'],'/usr/bin:/bin:/usr/sbin:/sbin')
            for managed in ('profile/.local','profile/.cache','profile/compiled-cache'):
                link=source/managed; link.symlink_to(root,target_is_directory=True)
                capture.unlink(missing_ok=True)
                result=subprocess.run(command,env=env,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(capture.exists())
                link.unlink()
            for bad in ('relative','/tmp/bad\nname','/tmp/bad\rname'):
                altered=command.copy(); altered[altered.index('--output')+1]=bad
                result=subprocess.run(altered,env=env,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(capture.exists())
    def test_rackunit_has_twenty_numbered_contracts(self):
        text=(HERE/'test-app.rkt').read_text()
        import re
        self.assertEqual(re.findall(r'\((?:fixture-test|test-case) "(\d\d) ',text),[f'{i:02}' for i in range(1,21)])
    def test_no_python_in_product_entrypoints(self):
        for name in ('build-app.sh','make-app.rkt','bootstrap.sh','runtime-dispatch.sh','make-native-launcher.rkt'):
            self.assertNotIn('python', (HERE/name).read_text().lower(),name)

if __name__ == '__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(baseline),unittest.defaultTestLoader.loadTestsFromTestCase(PortSourceContracts)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
