#!/usr/bin/env python3
"""Serialize unchanged native adapters; durable safety interlock, not acceptance."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ADAPTERS = {'light': 'run-light-tools.py', 'quit': 'run-native-quit.py'}
PHASES = ('prepare', 'cases')


def read_json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or nonregular safety evidence: ' + str(path))
    return json.loads(path.read_text())


def safety_reasons(root, active_phase=None):
    """Read original durable refusal/cleanup evidence without clearing it."""
    reports = root / 'reports'
    reasons = []
    blocked = reports / 'native-quit-ci/launch-blocked.json'
    if blocked.exists() or blocked.is_symlink():
        reasons.append('Quit launch-blocked.json requires diagnosis')
    state_dir = reports / 'functional-ci'
    for group in ADAPTERS:
        for phase in PHASES:
            path = state_dir / (group + '-' + phase + '.json')
            if not (path.exists() or path.is_symlink()) or (group, phase) == active_phase:
                continue
            try:
                state = read_json(path)
                if (not isinstance(state, dict) or type(state.get('schema')) is not int or
                        state.get('schema') != 1 or state.get('group') != group or
                        state.get('phase') != phase or state.get('status') != 'completed' or
                        state.get('cleanup_safe') is not True):
                    reasons.append(group + ' ' + phase + ' phase is unresolved or unsafe')
            except Exception as error:
                reasons.append(group + ' ' + phase + ' safety evidence unreadable: ' + str(error))
    light = reports / 'light-tools-ci'
    for folder in sorted(light.glob('tools-*')):
        try:
            if folder.is_symlink() or not folder.is_dir():
                raise ValueError('Nonregular native case directory')
            receipt = read_json(folder / 'supervisor.json')
            if (not isinstance(receipt, dict) or receipt.get('cleanup_verified') is not True or
                    'cleanup_error' not in receipt or receipt.get('cleanup_error') is not None or type(receipt.get('exit_code')) is not int):
                raise ValueError('Owned native process cleanup was not verified')
        except Exception as error:
            reasons.append(folder.name + ': ' + str(error))
    # Preparation helpers have their own durable supervisor receipts. A timeout,
    # signal or incomplete command may have left children and is never exit1-only.
    for folder in sorted(light.glob('command-*')):
        try:
            receipt = read_json(folder / 'supervisor.json')
            if (not isinstance(receipt, dict) or receipt.get('timed_out') is not False or
                    type(receipt.get('exit_code')) is not int or receipt['exit_code'] < 0):
                raise ValueError('Preparation/helper completion or cleanup is unresolved')
        except Exception as error:
            reasons.append(folder.name + ': ' + str(error))
    # A compile success is the durable boundary before the nine direct controls.
    # If their subprocess cleanup raises, the adapter can catch the exception and
    # exit1 without saving the failing control. Missing/partial records block GUI.
    rows_path = light / 'results.json'
    if rows_path.exists():
        try:
            rows = read_json(rows_path)
            for arm in ('stock', 'modern-light'):
                compiled = any(isinstance(row, dict) and row.get('passed') is True and
                               row.get('name') == arm + ' compile all15 and accepted runtime-path dependencies'
                               for row in rows)
                path = light / (arm + '-preflights.json')
                if compiled or path.exists() or path.is_symlink():
                    controls = read_json(path)
                    if not isinstance(controls, list) or len(controls) != 9:
                        raise ValueError(arm + ' direct control completion is incomplete')
                    for control in controls:
                        if (not isinstance(control, dict) or control.get('timed_out') is not False or
                                type(control.get('exit_code')) is not int or control['exit_code'] < 0):
                            raise ValueError(arm + ' direct control cleanup is unresolved')
        except Exception as error:
            reasons.append('Light preparation safety evidence: ' + str(error))
    # Also retain a cleanup refusal saved before a later receipt write failed.
    for group, relative, suffix in (
            ('light', 'light-tools-ci/results.json', ' owned-process cleanup'),
            ('quit', 'native-quit-ci/results.json', ' failure-only outer cleanup')):
        path = reports / relative
        if path.exists() or path.is_symlink():
            try:
                rows = read_json(path)
                if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                    raise ValueError('Expected original result rows')
                for row in rows:
                    if str(row.get('name', '')).endswith(suffix) and row.get('passed') is not True:
                        reasons.append(group + ': ' + str(row['name']) + ' requires diagnosis')
            except Exception as error:
                reasons.append(group + ' cleanup result evidence unreadable: ' + str(error))
    return reasons


def write_state(path, state):
    # An interrupted atomic replace leaves the preceding running marker intact.
    temp = path.with_suffix('.tmp')
    with temp.open('x') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
    temp.replace(path)
    print('OPENRACKET_FUNCTIONAL_INTERLOCK ' + json.dumps(state), flush=True)


def run_phase(root, group, phase, invoke=None):
    """Return the original red outcome; independent cleaned failures stay independent."""
    if group not in ADAPTERS or phase not in PHASES:
        raise ValueError('Unknown native group')
    directory = root / 'reports/functional-ci'
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / (group + '-' + phase + '.json')
    # Never overwrite a previous attempt, including an interrupted running marker.
    if state_path.exists() or state_path.is_symlink():
        raise RuntimeError('Native group already attempted; no implicit retry')
    reasons = safety_reasons(root)
    state = {'schema': 1, 'group': group, 'phase': phase, 'status': 'blocked' if reasons else 'running',
             'cleanup_safe': False, 'adapter_exit_code': None, 'reasons': reasons}
    write_state(state_path, state)
    if reasons:
        return 1
    argv = [sys.executable, str(root / 'scripts/ci' / ADAPTERS[group]), phase]
    # No new acceptance clock, environment override, output swallowing or cleanup.
    # Existing adapters own children and native deadlines; the workflow preserves
    # their original outer envelopes. Cancellation leaves the running marker red.
    try:
        code = (invoke or (lambda args: subprocess.run(args).returncode))(argv)
        if type(code) is not int:
            raise ValueError('Adapter returned no terminal integer exit status')
    except Exception as error:
        state.update(status='unresolved', reasons=['Adapter execution unresolved: ' + str(error)])
        write_state(state_path, state)
        return 1
    reasons = safety_reasons(root, active_phase=(group, phase))
    if group == 'quit' and phase == 'prepare' and code != 0:
        # Quit already records timeout/cleanup refusals. A normal command exit is
        # distinguishable from an exception during an unrecorded native query.
        try:
            rows = read_json(root / 'reports/native-quit-ci/results.json')
            prior = rows[-2] if rows and rows[-1].get('name') == 'prepare orchestration' else rows[-1]
            detail = prior.get('detail', '')
            terminal = (prior.get('passed') is False and isinstance(detail, str) and
                        detail.startswith('exit=') and detail[5:].isdigit() and
                        int(detail[5:]) > 0 and int(detail[5:]) != 124)
            if not terminal:
                raise ValueError('No recorded ordinary terminal command failure')
        except Exception as error:
            reasons.append('Quit preparation completion/cleanup unresolved: ' + str(error))
    if code < 0:
        reasons.append('Adapter terminated by signal; launch cleanup is unresolved')
    state.update(status='completed', cleanup_safe=not reasons, adapter_exit_code=code, reasons=reasons)
    write_state(state_path, state)
    return code if code > 0 else (1 if reasons or code < 0 else 0)


def main():
    if sys.flags.optimize:
        raise SystemExit('Optimized Python refused')
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'alikatgh/openracket' or
            os.environ.get('GITHUB_REF') != 'refs/heads/prototype/retained-drracket' or
            platform.system() != 'Darwin' or platform.machine() != 'arm64'):
        raise SystemExit('Exact public native CI context required')
    if len(sys.argv) != 7 or sys.argv[1] not in ADAPTERS or sys.argv[2] not in PHASES:
        raise SystemExit('Expected GROUP PHASE -- python3 retained-host/scripts/ci/ADAPTER PHASE')
    group, phase = sys.argv[1:3]
    if sys.argv[3:] != ['--', 'python3', 'retained-host/scripts/ci/' + ADAPTERS[group], phase]:
        raise SystemExit('Only the unchanged native phase adapter is allowed')
    root = Path(__file__).resolve().parents[2]
    return run_phase(root, group, phase)


if __name__ == '__main__':
    sys.exit(main())
