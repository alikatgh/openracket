#!/usr/bin/env python3
"""Require native headless gates before patching/running either genuine-GUI arm."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--racket',required=True,type=Path)
    parser.add_argument('--pristine-source',required=True,type=Path)
    parser.add_argument('--candidate-source',required=True,type=Path)
    parser.add_argument('--profile',required=True,type=Path)
    args=parser.parse_args()
    racket=args.racket.resolve()
    if not racket.is_file():parser.error('Native Racket executable required; skips cannot pass acceptance')
    args.profile.mkdir(parents=True,exist_ok=True)
    os.environ.update(GUI_TEST_RACKET=str(racket),GUI_TEST_PROFILE=str(args.profile.resolve()),
                      GUI_TEST_SOURCE_DIR=str(args.pristine_source.resolve()),
                      GUI_TEST_CANDIDATE_SOURCE=str(args.candidate_source.resolve()))
    for key in list(os.environ):
        if key.startswith('OPENRACKET_'):del os.environ[key]
    modules=['test_gui_source','test_gui_native','test_capture','test_accept_gui','test_telemetry','test_accept_binding','test_prepared_runtime']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
    if result.skipped or not result.wasSuccessful():return 1
    env=dict(os.environ,PLTUSERHOME=str(args.profile.resolve()))
    profile_helper = json.dumps(str(Path(__file__).with_name('memory-profile.rkt').resolve()))
    profile_gate = ('(begin (require rackunit) (current-check-handler raise) '
                    "(dynamic-require '(submod (file " + profile_helper + ") test) #f) "
                    '(displayln "OPENRACKET_MEMORY_PROFILE_TESTS_PASSED"))')
    subprocess.run([str(racket), '-e', profile_gate], env=env, check=True, timeout=30)
    print(json.dumps({'native_headless_preflight':'passed','tests':result.testsRun,'skipped':0,
                      'profile_helper_tests':'passed','native_gui_execution':False}))
    return 0

if __name__=='__main__':raise SystemExit(main())
