#!/usr/bin/env python3
"""Native headless acceptance gate; no skipped Racket tests and no GUI launch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--racket', required=True, type=Path)
    parser.add_argument('--pristine-source', required=True, type=Path)
    parser.add_argument('--profile', required=True, type=Path)
    args = parser.parse_args()
    racket = args.racket.resolve()
    if not racket.is_file():
        parser.error('Native Racket executable required; skipped gates are not acceptance')
    args.profile.mkdir(parents=True, exist_ok=True)
    os.environ.update(REPLAY_TEST_RACKET=str(racket), REPLAY_TEST_PROFILE=str(args.profile.resolve()),
                      REPLAY_TEST_SOURCE_DIR=str(args.pristine_source.resolve()))
    for key in list(os.environ):
        if key.startswith('OPENRACKET_'):
            del os.environ[key]
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        ['test_cap256', 'test_phase_probe', 'test_implementation', 'test_supervise'])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped or not result.wasSuccessful():
        return 1
    env = dict(os.environ, PLTUSERHOME=str(args.profile.resolve()))
    here = Path(__file__).resolve().parent
    subprocess.run([str(racket), '-l', 'raco', 'test', str(here / 'test_support.rkt')], env=env, check=True, timeout=30)
    subprocess.run([str(racket), '-l', 'raco', 'test', str(here / 'memory-profile.rkt')], env=env, check=True, timeout=30)
    print(json.dumps({'native_preflight': 'passed', 'tests': result.testsRun, 'skipped': 0,
                      'support_and_profile_helper_tests': 'passed'}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
