#!/usr/bin/env python3
"""CI-only genuine-GUI control/observed capture; never constructs or replays a job."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from profile_setup import prepare_memory_profile
from supervise import cleanup_group

BASE_SHA256 = '766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e'
EDITED_SHA256 = 'f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735'
EDIT_POSITION = 524139
EXPECTED_CHARACTERS = 1048577
MEMORY_LIMIT_BYTES = 268435456
HERE = Path(__file__).resolve().parent


def read_bounded_json(path, maximum_bytes):
    """Read evidence only from a bounded regular, non-symlink JSON file."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
        raise ValueError('Missing or invalid bounded evidence: ' + path.name)
    with path.open('rb') as stream:
        raw = stream.read(maximum_bytes + 1)
    if len(raw) > maximum_bytes:
        raise ValueError('Evidence exceeds bound: ' + path.name)
    def nonfinite(value):
        raise ValueError('Non-finite JSON value: ' + value)
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            nonfinite(value)
        return result
    result = json.loads(raw, parse_constant=nonfinite, parse_float=finite_float)
    if not isinstance(result, dict):
        raise ValueError('Evidence is not an object: ' + path.name)
    return result


def check_host_evidence(output, arm):
    """Require the GUI host's successful gate, plus its bounded source evidence.

    Detailed cross-arm/phase acceptance belongs to the separate validator. This
    launcher must still reject an exited host with missing or incomplete proof.
    """
    errors = []
    try:
        host = read_bounded_json(output / 'capture-host.json', 64 * 1024)
        summary = read_bounded_json(output / 'gui-observation.json', 1024 * 1024)
        worker = read_bounded_json(output / 'worker-init.json', 16 * 1024)
        if host.get('status') != 'gui_application_complete' or host.get('arm') != arm:
            errors.append('GUI host did not complete the requested arm')
        if (host.get('edited_snapshot_sha256') != EDITED_SHA256
                or host.get('final_snapshot_sha256') != EDITED_SHA256
                or host.get('final_snapshot_characters') != EXPECTED_CHARACTERS
                or host.get('source_unchanged') is not True
                or host.get('lexer_valid_at_completion') is not True):
            errors.append('GUI host did not verify unchanged final source and lexer')
        if (type(worker.get('child_limit_bytes')) is not int
                or worker.get('child_limit_bytes') != MEMORY_LIMIT_BYTES
                or worker.get('memory_accounting_available') is not True):
            errors.append('Actual GUI worker memory limit/accounting did not verify')
        ids, records = summary.get('matching_request_ids'), summary.get('records')
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(records, list):
            errors.append('GUI observation did not identify exactly one request')
        else:
            matching = [r for r in records if isinstance(r, dict) and r.get('request_id') == ids[0]]
            if (len(matching) != 1 or matching[0].get('snapshot_sha256') != EDITED_SHA256
                    or matching[0].get('snapshot_characters') != EXPECTED_CHARACTERS):
                errors.append('GUI observation does not match the exact edited request')
        if any(type(summary.get(key)) is not int or summary[key] != 0
               for key in ('error_count', 'dropped_records')):
            errors.append('GUI observer reported errors, drops or missing counters')
        application = read_bounded_json(output / 'application-profile.json', 64 * 1024)
        from validate_application import validate_application
        if isinstance(records, list) and len(records) == 1:
            validate_application(application, arm, records[0], host)
        else:
            errors.append('Application profile lacks unique common request evidence')
        phase = read_bounded_json(output / 'worker-phase-1.json', 64 * 1024)
        if phase.get('phase_points_enabled') is not False or phase.get('phase_points') != []:
            errors.append('Producer phase points must be disabled in both application arms')
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append(str(error))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('control', 'observed'), required=True)
    parser.add_argument('--racket', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    racket, fixture, output = args.racket.resolve(), args.fixture.resolve(), args.output.resolve()
    data = fixture.read_bytes()
    if len(data) != 1048576 or hashlib.sha256(data).hexdigest() != BASE_SHA256:
        parser.error('Fixture must be the unchanged deterministic mixed-1MiB benchmark fixture')
    edited = data[:EDIT_POSITION] + b'x' + data[EDIT_POSITION:]
    if (len(edited.decode('ascii')) != EXPECTED_CHARACTERS
            or hashlib.sha256(edited).hexdigest() != EDITED_SHA256):
        parser.error('Exact middle-comment x edit does not match the approved snapshot')
    if output.exists() or args.output.is_symlink():
        parser.error('Capture output must be a new disposable directory')
    output.mkdir(parents=True)
    profile = output / 'profile'
    profile.mkdir()
    config = {'fixture': str(fixture), 'output': str(output),
              'edit_position': EDIT_POSITION, 'arm': args.arm}
    env = dict(os.environ)
    cleared_flags = sorted(key for key in env if key.startswith('OPENRACKET_'))
    for key in cleared_flags:
        env.pop(key)
    env.update({'PLTUSERHOME': str(profile), 'PLTADDONDIR': str(output / 'addon'),
                'XDG_CONFIG_HOME': str(profile / '.config'),
                'XDG_CACHE_HOME': str(profile / '.cache'),
                'OPENRACKET_GUI_OBSERVER': '1',
                'OPENRACKET_GUI_OBSERVER_SUPPORT': str(HERE / 'gui-observer.rkt'),
                'OPENRACKET_GUI_PHASE_SUPPORT': str(HERE / 'gui-phase.rkt'),
                'OPENRACKET_GUI_APPLICATION_SUPPORT': str(HERE / 'application-probe.rkt'),
                'OPENRACKET_GUI_OBSERVER_OUTPUT': str(output),
                'OPENRACKET_GUI_EXPECTED_SHA256': EDITED_SHA256,
                'OPENRACKET_GUI_EXPECTED_SOURCE': str(fixture),
                'OPENRACKET_GUI_EXPECTED_CHARACTERS': str(EXPECTED_CHARACTERS),
                'OPENRACKET_CAPTURE_CONFIG': json.dumps(config)})
    if args.arm == 'observed':
        env['OPENRACKET_GUI_APPLICATION_POINTS'] = '1'
    command = [str(racket), str(HERE / 'capture-host.rkt')]
    report = {'schema_version': 1, 'command': command, 'arm': args.arm,
              'native_gui_capture_only': True, 'standalone_replay': False,
              'cleared_inherited_openracket_keys': cleared_flags,
              'base_fixture_sha256': BASE_SHA256, 'edited_snapshot_sha256': EDITED_SHA256,
              'edited_snapshot_bytes': len(edited), 'edited_snapshot_characters': EXPECTED_CHARACTERS,
              'timeout': False, 'expected_memory_limit_bytes': MEMORY_LIMIT_BYTES}
    setup_args = SimpleNamespace(racket=racket, memory_limit_mib=256,
                                 profile_helper=HERE / 'memory-profile.rkt')
    setup_cleanup = []

    def terminate_setup(process):
        setup_cleanup.append(cleanup_group(process, time.monotonic() + 5))

    setup = prepare_memory_profile(setup_args, env, output, terminate_setup)
    setup['cleanup'] = setup_cleanup
    report['memory_profile_setup'] = setup
    if not setup['verified']:
        report.update(status='setup_failed', gui_started=False)
        (output / 'capture-supervisor.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 1
    # The exact approved helper requires an empty home; mark only after verification.
    (profile / 'openracket-diagnostic-profile').write_text('openracket-expansion-diagnostic-profile\n')
    report['gui_started'] = True
    process = None
    started = time.monotonic()
    try:
        with (output / 'stdout.log').open('wb') as stdout, (output / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                process.wait(timeout=190)
            except subprocess.TimeoutExpired:
                report['timeout'] = True
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        if process:
            report['cleanup'] = cleanup_group(process, time.monotonic() + 5)
            report['exit_code'] = process.returncode
        report['elapsed_seconds'] = time.monotonic() - started
        report['observation_exists'] = (output / 'gui-observation.json').is_file()
        report['host_evidence_errors'] = check_host_evidence(output, args.arm)
        accepted = (report.get('exit_code') == 0 and not report['timeout']
                    and report.get('cleanup', {}).get('complete') is True
                    and not report['host_evidence_errors'] and 'error' not in report)
        report['status'] = 'gui_application_complete' if accepted else 'failed'
        (output / 'capture-supervisor.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if accepted else 1


if __name__ == '__main__':
    sys.exit(main())
