#!/usr/bin/env python3
"""Headless launch-profile and compilation isolation checks; no package installation."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RACKET = os.environ.get('RACKET', '/workspace/shared/racket-toolchain/racket/bin/racket')

class PortableProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='openracket-portable-')
        self.root = Path(self.temporary.name) / 'proof with spaces'
        (self.root / 'scripts').mkdir(parents=True)
        shutil.copy2(ROOT / 'scripts/proof-env.sh', self.root / 'scripts/proof-env.sh')
        self.probe = self.root / 'scripts/probe.sh'
        self.probe.write_text('#!/bin/sh\nset -eu\n. "$(dirname "$0")/proof-env.sh"\nrun_racket "$@"\n')
        self.env = dict(os.environ, RACKET=RACKET)
    def tearDown(self):
        self.temporary.cleanup()
    def run_probe(self, *args):
        return subprocess.run(['sh', str(self.probe), *args], env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    def test_profile_and_compiled_roots_are_explicit(self):
        self.env.update(PLTUSERHOME='/unused-foreign-profile', PLTCOMPILEDROOTS='/unused-foreign-cache')
        result = self.run_probe('-e', '(require json)(write-json (hash \'profile (getenv "PLTUSERHOME") \'roots (for/list ([p (current-compiled-file-roots)]) (if (path? p) (path->string p) (symbol->string p))) \'addon (path->string (find-system-path \'addon-dir))))')
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        value = json.loads(result.stdout)
        self.assertEqual(value['profile'], str(self.root / 'profile'))
        self.assertEqual(value['roots'], [str(self.root / 'profile/compiled-cache'), 'same'])
        self.assertEqual(Path(value['addon']), self.root / 'profile/.local/share/racket')
    def test_spawned_runtime_inherits_the_isolated_addon_and_cache(self):
        self.env.update(PLTADDONDIR='/unused-foreign-addon', PLTCOMPILEDROOTS='/unused-foreign-cache')
        child = "(require json)(write-json (hash 'addon (path->string (find-system-path 'addon-dir)) 'roots (map (lambda (p) (if (path? p) (path->string p) (symbol->string p))) (current-compiled-file-roots))))"
        import json
        parent = '(require racket/system)(unless (system* (getenv "RACKET") "-e" ' + json.dumps(child) + ') (exit 1))'
        result = self.run_probe('-e', parent)
        self.assertEqual(result.returncode,0,result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(Path(value['addon']),self.root / 'profile/.local/share/racket')
        self.assertEqual(value['roots'],[str(self.root / 'profile/compiled-cache'),'same'])
    def test_symbolic_profile_paths_are_refused_before_runtime(self):
        for relative in ('profile', 'profile/.local', 'profile/.local/share',
                         'profile/.local/share/racket', 'profile/.cache', 'profile/compiled-cache'):
            with self.subTest(relative=relative):
                profile = self.root / 'profile'
                if profile.exists(): shutil.rmtree(profile)
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                foreign = Path(self.temporary.name) / 'foreign'
                foreign.mkdir(exist_ok=True)
                target.symlink_to(foreign, target_is_directory=True)
                result = self.run_probe('-e', '(display "runtime should not start")')
                self.assertEqual(result.returncode, 2)
                self.assertIn('Refusing symbolic-link profile path', result.stderr)
                self.assertNotIn('runtime should not start', result.stdout)
                target.unlink()
    def test_colon_path_is_refused(self):
        renamed = self.root.with_name('proof:ambiguous')
        self.root.rename(renamed)
        self.root = renamed
        self.probe = renamed / 'scripts/probe.sh'
        result = self.run_probe('-e', '(void)')
        self.assertEqual(result.returncode, 2)
        self.assertIn('must not contain a colon', result.stderr)
    def test_actual_recompile_writes_first_root_only(self):
        source = Path(self.temporary.name) / 'stock-source'
        source.mkdir()
        module = source / 'value.rkt'
        module.write_text('#lang racket/base\n(provide value)\n(define value 1)\n')
        # Direct compilation writes only our fixture's stock-style .zo, with no
        # compilation manager rebuilding dependencies in the official runtime.
        program = r'''(require racket/file racket/path)
          (define source (string->path (vector-ref (current-command-line-arguments) 0)))
          (define compiled-dir (build-path (path-only source) "compiled"))
          (make-directory* compiled-dir)
          (parameterize ([read-accept-reader #t]
                         [current-load-relative-directory (path-only source)])
            (define code (call-with-input-file source
              (lambda (in) (compile (read-syntax source in)))))
            (call-with-output-file (build-path compiled-dir "value_rkt.zo")
              #:exists 'error (lambda (out) (write code out))))'''
        result = self.run_probe('-e', program, '--', str(module))
        self.assertEqual(result.returncode, 0, result.stderr)
        zo = source / 'compiled/value_rkt.zo'
        old_bytes = zo.read_bytes()
        module.write_text('#lang racket/base\n(provide value)\n(define value 2)\n')
        result = self.run_probe('-e', '(require compiler/cm)(managed-compile-zo (string->path (vector-ref (current-command-line-arguments) 0)))', '--', str(module))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(zo.read_bytes(), old_bytes)
        self.assertFalse((source / 'compiled/value_rkt.dep').exists())
        cache = self.root / 'profile/compiled-cache'
        self.assertTrue(list(cache.rglob('value_rkt.zo')))
        self.assertTrue(list(cache.rglob('value_rkt.dep')))
        result = self.run_probe('-e', '(display (dynamic-require (string->path (vector-ref (current-command-line-arguments) 0)) \'value))', '--', str(module))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '2')
    def test_preflight_reports_missing_modules_with_failure_exit(self):
        for relative in ('scripts/preflight.rkt', 'reports/patch-manifest.json'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        result = self.run_probe(str(self.root / 'scripts/preflight.rkt'))
        self.assertEqual(result.returncode, 1, result.stderr)
        import json
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['native_window_started'])
        self.assertTrue(any(not row['available'] for row in report['module_checks']))
        self.assertTrue(all(not row['available'] for row in report['source_checks']))
    def test_launch_activation_and_stock_clearing(self):
        import json
        fake = Path(self.temporary.name) / 'fake-racket'
        fake.write_text("#!/usr/bin/env python3\nimport os,sys,json\na=sys.argv[1:]\nif '-e' in a:\n s=a[a.index('-e')+1]\n if '(version)' in s: print('9.3',end='')\n elif '(system-type)' in s: print('macosx',end='')\n sys.exit(0)\nprint(json.dumps({'args':a,'env':{k:os.environ.get(k) for k in ('PLTUSERHOME','PLTCOMPILEDROOTS','OPENRACKET_UI','OPENRACKET_HOST_THEME','OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD','OPENRACKET_NATIVE_APPEARANCE')}}))\n")
        fake.chmod(0o755)
        for name in ('launch-openracket.sh', 'launch-stock.sh'):
            shutil.copy2(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        def launch(script, **overrides):
            env = dict(self.env, RACKET=str(fake))
            for key in ('OPENRACKET_AUTOSAVE_GUARD','OPENRACKET_NATIVE_APPEARANCE',
                        'OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD','OPENRACKET_HOST_THEME'):
                env.pop(key, None)
            env.update(overrides)
            result = subprocess.run(['sh',str(self.root / 'scripts' / script),'file with spaces.rkt'],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        modern = launch('launch-openracket.sh')
        self.assertEqual(modern['env']['OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD'],'1')
        self.assertEqual(modern['env']['OPENRACKET_NATIVE_APPEARANCE'],'1')
        self.assertEqual(modern['env']['OPENRACKET_HOST_THEME'],'1')
        self.assertEqual(modern['args'][-1],'file with spaces.rkt')
        optout = launch('launch-openracket.sh',OPENRACKET_AUTOSAVE_GUARD='0',
                        OPENRACKET_NATIVE_APPEARANCE='0',OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD='1')
        self.assertIsNone(optout['env']['OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD'])
        self.assertEqual(optout['env']['OPENRACKET_NATIVE_APPEARANCE'],'0')
        stock = launch('launch-stock.sh',OPENRACKET_HOST_THEME='1',OPENRACKET_NATIVE_APPEARANCE='1',
                       OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD='1')
        for key in ('OPENRACKET_HOST_THEME','OPENRACKET_NATIVE_APPEARANCE','OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD'):
            self.assertIsNone(stock['env'][key])
        self.assertEqual(stock['env']['OPENRACKET_UI'],'stock')
        self.assertEqual(Path(stock['env']['PLTUSERHOME']),self.root / 'profile-stock-preferences')
    def test_launcher_execs_use_same_roots(self):
        for name in ('launch-openracket.sh', 'launch-stock.sh'):
            source = (ROOT / 'scripts' / name).read_text()
            for line in source.splitlines():
                if line.startswith('  exec ') or line.startswith('exec '):
                    self.assertIn('-R "$COMPILED_ROOTS"', line)

if __name__ == '__main__':
    unittest.main()
