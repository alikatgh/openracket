#!/usr/bin/env python3
"""Run every isolation source/adapter/transport test through a symlinked TMPDIR."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def verify_inputs():
    spec = importlib.util.spec_from_file_location('release_isolation_contract', HERE / 'launcher-isolation-contract.py')
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    contract.frozen_sources(ROOT / 'experiments/relative-launcher-isolation-probe')


def main():
    if sys.flags.optimize:
        raise SystemExit('Optimized Python is not accepted')
    sys.dont_write_bytecode = True
    verify_inputs()  # Verify before importing or executing any frozen source/test.
    with tempfile.TemporaryDirectory(prefix='isolation-release-') as temporary:
        parent = Path(temporary).resolve()
        actual = parent / "Real Temp Unicode λ's"
        actual.mkdir()
        alias = parent / "Alias Temp Unicode λ's"
        alias.symlink_to(actual, target_is_directory=True)
        env = dict(os.environ, TMPDIR=str(alias), TMP=str(alias), TEMP=str(alias),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONOPTIMIZE='')
        # tempfile may cache its root, so verify alias choice in a new interpreter.
        check = ('import json,os,pathlib,tempfile; a=pathlib.Path(os.environ["TMPDIR"]); '
                 'assert a.is_symlink(); assert pathlib.Path(tempfile.gettempdir()) == a; '
                 'd=tempfile.TemporaryDirectory(); p=pathlib.Path(d.name); '
                 'assert p.parent == a; assert p.resolve().parent == a.resolve(); '
                 'print(json.dumps({"alias":str(a),"canonical":str(a.resolve()),'
                 '"temporary":str(p),"fresh_subprocess":True})); d.cleanup()')
        probe = subprocess.run([sys.executable, '-B', '-c', check], env=env, check=True,
                               stdout=subprocess.PIPE, text=True)
        print('OPENRACKET_ALIAS_TMPDIR ' + probe.stdout.strip(), flush=True)
        commands = [
            ([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
             ROOT / 'experiments/relative-launcher-isolation-probe'),
            ([sys.executable, '-B', str(HERE / 'test-launcher-isolation-adapter.py')], ROOT),
            ([sys.executable, '-B', str(HERE / 'test-replay-evidence.py')], ROOT),
        ]
        receipts = []
        for argv, cwd in commands:
            print('OPENRACKET_RELEASE_TEST ' + json.dumps({'argv': argv, 'cwd': str(cwd)}), flush=True)
            result = subprocess.run(argv, cwd=cwd, env=env, check=False)
            receipts.append({'argv': argv, 'cwd': str(cwd), 'exit_code': result.returncode})
        print('OPENRACKET_RELEASE_RESULT ' + json.dumps({'alias_verified_in_fresh_subprocess': True,
                                                        'tests': receipts}), flush=True)
        return 0 if all(row['exit_code'] == 0 for row in receipts) else 1


if __name__ == '__main__':
    sys.exit(main())
