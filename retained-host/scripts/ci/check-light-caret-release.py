#!/usr/bin/env python3
"""Run the complete portable gate in ordinary and genuine symlinked TMPDIRs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CI = Path(__file__).resolve().parent
ROOT = CI.parents[1]
spec = importlib.util.spec_from_file_location('caret_release_contract', CI / 'caret-ci-contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

def main():
    C.require(not sys.flags.optimize, 'Optimized Python refused')
    exp, source = ROOT / 'experiments/light-caret-contrast', ROOT / 'experiments/light-caret-accepted-source'
    C.verify_inputs(exp, source, CI / 'light-caret-support')
    tests = [exp / 'tests/test_package.py', CI / 'test-light-caret-adapter.py']
    with tempfile.TemporaryDirectory(prefix='caret-release-') as temporary:
        work = Path(temporary).resolve()
        real = work / 'physical-tmp'; real.mkdir()
        alias = work / 'aliased-tmp'; alias.symlink_to(real, target_is_directory=True)
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONOPTIMIZE', 'TMPDIR', 'REQUIRE_ALIASED_TMPDIR')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        for label in ('ordinary', 'aliased'):
            selected = {**env}
            if label == 'aliased':
                selected.update(TMPDIR=str(alias), REQUIRE_ALIASED_TMPDIR='1')
            for test in tests:
                print('PORTABLE_ONLY ' + label + ' ' + test.name, flush=True)
                result = subprocess.run([sys.executable, '-B', str(test)], env=selected, timeout=120)
                C.require(result.returncode == 0, label + ' complete portable suite failed')
    print(json.dumps({'status': 'passed', 'ordinary_and_real_symlinked_tmpdir': True,
                      'case_sensitive_filesystem_assumed': False, 'native_execution': 'not run'}))

if __name__ == '__main__':
    main()
