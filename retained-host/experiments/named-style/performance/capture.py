#!/usr/bin/env python3
"""CI-only genuine-GUI stock/candidate named-style lookup capture; never constructs or replays a job."""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from profile_setup import prepare_memory_profile
from supervise import cleanup_group
from accept_gui import verify_runtime, strict_json

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
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    result = json.loads(raw, parse_constant=nonfinite, parse_float=finite_float, object_pairs_hook=unique_pairs)
    if not isinstance(result, dict):
        raise ValueError('Evidence is not an object: ' + path.name)
    return result


def read_source_pins(path=None):
    pins = read_bounded_json(path or HERE / 'candidate-source-pins.json', 16 * 1024)
    if pins.get('module') != 'racket/snip/private/style':
        raise ValueError('Wrong candidate style module')
    selected = {key: pins.get(key) for key in ('stock_sha256', 'candidate_sha256')}
    if any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
           for value in selected.values()):
        raise ValueError('Source pins must contain exact lowercase stock/candidate SHA256 values')
    if selected['stock_sha256'] == selected['candidate_sha256']:
        raise ValueError('Stock and candidate source pins must differ')
    return selected


def check_host_evidence(output, arm, expected_source_sha256=None):
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
        phase = read_bounded_json(output / 'worker-phase-1.json', 64 * 1024)
        if phase.get('phase_points_enabled') is not False:
            errors.append('Producer phase points must be disabled in both timing arms')
        expected = expected_source_sha256
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('Verified native style source SHA256 is required')
        activation = read_bounded_json(output / 'activation.json', 16 * 1024)
        if (not {'flag_value', 'named_style_index_enabled'} <= activation.keys()
                or type(activation.get('schema_version')) is not int or activation.get('schema_version') != 1
                or activation.get('kind') != 'gui_named_style_index_activation'
                or activation.get('flag_name') != 'OPENRACKET_NAMED_STYLE_INDEX'
                or activation.get('activation_export') != 'openracket-named-style-index-enabled?'
                or activation.get('verified') is not True or activation.get('arm') != arm
                or activation.get('source_sha256') != expected
                or activation.get('expected_source_sha256') != expected
                or activation.get('gui_module_already_instantiated') is not True
                or activation.get('same_gui_imported_style_instance') is not True
                or activation.get('style_module_already_instantiated') is not True
                or activation.get('actual_editor_style_list') is not True
                or activation.get('syncheck_module_already_instantiated') is not True
                or activation.get('state_export') != 'openracket-named-style-index-state'
                or activation.get('state_export_status') != ('procedure' if arm == 'candidate' else 'missing')
                or activation.get('gui_handler_thread') is not True
                or activation.get('phase_points_enabled') is not False
                or type(activation.get('unexpected_experiment_flags')) is not list
                or activation.get('unexpected_experiment_flags') != []
                or activation.get('flag_value') != ('1' if arm == 'candidate' else None)
                or activation.get('export_status') != ('boolean' if arm == 'candidate' else 'missing')
                or activation.get('named_style_index_enabled') is not (True if arm == 'candidate' else None)):
            errors.append('Actual GUI named-style activation/source evidence did not verify')
        heartbeat = read_bounded_json(output / 'heartbeat.json', 2 * 1024 * 1024)
        heart_rows = heartbeat.get('records')
        if (heartbeat.get('joined') is not True or heartbeat.get('producer_exited') is not True
                or heartbeat.get('join_timed_out') is not False
                or any(type(heartbeat.get(key)) is not int or heartbeat[key] != 0
                       for key in ('outstanding_callbacks', 'dropped_records', 'error_count'))
                or heartbeat.get('period_ms') != 50.0 or heartbeat.get('max_records') != 4096
                or not isinstance(heart_rows, list) or not 1 <= len(heart_rows) <= 4096
                or type(heartbeat.get('handled_count')) is not int
                or heartbeat.get('handled_count') != len(heart_rows)
                or type(heartbeat.get('submitted_count')) is not int
                or heartbeat.get('submitted_count') != heartbeat.get('handled_count')):
            errors.append('Common bounded GUI heartbeat did not stop/join cleanly')
        style = read_bounded_json(output / 'style-witness.json', 64 * 1024)
        if (style.get('kind') != 'actual-editor-named-style-counters' or style.get('arm') != arm
                or style.get('verified') is not True or host.get('style_witness_verified') is not True
                or style.get('diagnostic_counters_synchronized') is not False
                or style.get('synthetic_lookup_performed') is not False):
            errors.append('Actual definitions style-list workload witness failed')
        binding = read_bounded_json(output / 'binding-export.json', 64 * 1024)
        if (type(binding.get('schema_version')) is not int or binding.get('schema_version') != 1
                or binding.get('kind') != 'post-readiness-binding-graph'
                or binding.get('verified') is not True or binding.get('arm') != arm
                or binding.get('same_public_hash_identity') is not True
                or host.get('binding_export_verified') is not True
                or host.get('post_export_final_currentness_verified') is not True):
            errors.append('Public binding export or final post-export verification failed')
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append(str(error))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('stock', 'candidate'), required=True)
    parser.add_argument('--racket', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
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
    try:
        source_pins = read_source_pins()
        manifest = strict_json(args.manifest)
        verified_sources = verify_runtime(args.manifest, HERE,
            ('activation.rkt', 'heartbeat.rkt', 'binding-export.rkt', 'style-witness.rkt'), args.arm)
        if Path(manifest['racket']).resolve() != racket:
            raise ValueError('Capture executable differs from verified prepared clone')
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    expected_source_sha256 = manifest['style_source']['sha256']
    output.mkdir(parents=True)
    profile = output / 'profile'
    profile.mkdir()
    config = {'fixture': str(fixture), 'output': str(output),
              'edit_position': EDIT_POSITION, 'arm': args.arm,
              'expected_gui_source_sha256': verified_sources['syncheck/gui.rkt'],
              'expected_gui_source': str(Path(manifest['source_root']) / 'syncheck/gui.rkt'),
              'expected_style_source_sha256': expected_source_sha256,
              'expected_style_source': manifest['style_source']['source'],
              'runtime_root': manifest['diagnostic_root']}
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
                'OPENRACKET_GUI_OBSERVER_OUTPUT': str(output),
                'OPENRACKET_GUI_EXPECTED_SHA256': EDITED_SHA256,
                'OPENRACKET_GUI_EXPECTED_SOURCE': str(fixture),
                'OPENRACKET_GUI_EXPECTED_CHARACTERS': str(EXPECTED_CHARACTERS),
                'OPENRACKET_CAPTURE_CONFIG': json.dumps(config)})
    if args.arm == 'candidate':
        env['OPENRACKET_NAMED_STYLE_INDEX'] = '1'
    command = [str(racket), str(HERE / 'capture-host.rkt')]
    report = {'schema_version': 1, 'command': command, 'arm': args.arm,
              'native_gui_capture_only': True, 'standalone_replay': False,
              'experiment': 'named-style-index', 'phase_points_enabled': False,
              'expected_gui_source_sha256': verified_sources['syncheck/gui.rkt'],
              'expected_style_source_sha256': expected_source_sha256,
              'production_style_source_sha256': source_pins[args.arm + '_sha256'],
              'manifest': str(args.manifest.resolve()),
              'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
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
    # Recheck the actual observed source and helpers immediately before GUI startup,
    # after profile preparation, so a valid but stale manifest cannot authorize it.
    try:
        if (verify_runtime(args.manifest, HERE,
                ('activation.rkt', 'heartbeat.rkt', 'binding-export.rkt', 'style-witness.rkt'), args.arm) != verified_sources or
                hashlib.sha256(args.manifest.read_bytes()).hexdigest() != report['manifest_sha256']):
            raise ValueError('Prepared runtime or manifest changed before GUI startup')
    except (OSError, KeyError, TypeError, ValueError) as error:
        report.update(status='runtime_verification_failed', gui_started=False, error=str(error))
        (output / 'capture-supervisor.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 1
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
        report['host_evidence_errors'] = check_host_evidence(output, args.arm, expected_source_sha256)
        accepted = (report.get('exit_code') == 0 and not report['timeout']
                    and report.get('cleanup', {}).get('complete') is True
                    and not report['host_evidence_errors'] and 'error' not in report)
        report['status'] = 'gui_application_complete' if accepted else 'failed'
        (output / 'capture-supervisor.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if accepted else 1


if __name__ == '__main__':
    sys.exit(main())
