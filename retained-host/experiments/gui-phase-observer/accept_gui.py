#!/usr/bin/env python3
"""Read-only, fail-closed acceptance of two genuine GUI phase observations."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from prepare_gui import PINS, TRANSFORMS

CAP = 268435456
SNAPSHOT = 'f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735'
BASE = '766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e'
FILES = ('capture-host.json', 'capture-supervisor.json', 'gui-observation.json',
         'worker-init.json', 'worker-phase-1.json', 'memory-profile.json')
METRICS = ('monotonic_ms', 'process_allocation_counter_bytes', 'gc_counter_ms',
           'process_cpu_counter_ms_all_places')
PHASES = ('worker-phase-09', 'worker-phase-10', 'worker-phase-11',
          'monitor-build-start', 'monitor-built-send-start', 'monitor-send-return',
          'monitor-ack', 'worker-phase-12', 'worker-phase-13', 'terminal-send-return')
GUI_POINTS = ('request-observed', 'monitor-received', 'monitor-callback-queue-attempt',
              'monitor-callback-enter', 'monitor-callback-return', 'application-enter',
              'application-complete', 'terminal-received', 'terminal-callback-queue-attempt',
              'terminal-callback-enter', 'terminal-callback-return')

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def integer(value, minimum=0):
    return type(value) is int and value >= minimum

def strict_json(path, maximum=1024 * 1024):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
            'Missing, linked or oversized evidence: ' + str(path))
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON value: ' + value)
    data = json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)
    require(type(data) is dict, 'Evidence is not an object: ' + str(path))
    return data

def metric(value):
    require(type(value) is dict and all(number(value.get(k)) for k in METRICS),
            'Missing or non-finite producer/GUI metrics')
    return value['monotonic_ms']

def ordered(points, sequence):
    values = [metric(points[k]) for k in sequence]
    require(values == sorted(values), 'Nonmonotonic points: ' + ', '.join(sequence))

def registry(rows):
    require(type(rows) is list and 0 < len(rows) <= 32, 'Missing or unbounded registry')
    result = []
    for row in rows:
        require(type(row) is dict and all(type(row.get(k)) is str and 0 < len(row[k]) <= 4096
                for k in ('module_spec', 'export', 'source', 'source_sha256')) and
                type(row.get('monitor')) is bool, 'Malformed/truncated registry identity')
        require(len(row['source_sha256']) == 64, 'Wrong registry source digest')
        result.append((row['source'], row['source_sha256'], row['export'], row['monitor']))
    require(sum(row[3] for row in result) == 1, 'Expected exactly one actual monitor')
    return result

def validate_arm(data, arm):
    host, sup, gui, init, worker, profile = (data[k] for k in FILES)
    require(host['status'] == sup['status'] == 'gui_application_complete' and
            host['arm'] == sup['arm'] == arm, 'GUI process did not complete this arm')
    require(sup['exit_code'] == 0 and type(sup['exit_code']) is int and sup['timeout'] is False and
            sup['cleanup']['complete'] is True and sup['gui_started'] is True and
            sup['native_gui_capture_only'] is True and sup['standalone_replay'] is False and
            not sup['host_evidence_errors'], 'Native completion/cleanup proof failed')
    require(sup['base_fixture_sha256'] == BASE and sup['edited_snapshot_sha256'] == SNAPSHOT and
            sup['edited_snapshot_characters'] == sup['edited_snapshot_bytes'] == 1048577,
            'Launcher source identity differs')
    require(host['racket_version'] == '9.3' and host['os'] == 'macosx', 'Wrong runtime/platform')
    require(host['edited_snapshot_sha256'] == host['final_snapshot_sha256'] == SNAPSHOT and
            host['final_snapshot_characters'] == 1048577 and host['source_unchanged'] is True and
            host['lexer_valid_at_completion'] is True, 'Final source/lexer evidence differs')
    require(host['preserved_preferences'] == {'child_limit_bytes': CAP, 'coloring': True,
                                             'online_compilation': True}, 'Stock feature/preferences differ')
    require(host['actual_worker_child_limit_bytes'] == init['child_limit_bytes'] ==
            worker['actual_child_limit_bytes'] == CAP and
            host['actual_worker_memory_accounting_available'] is init['memory_accounting_available'] is
            worker['memory_accounting_available'] is True, 'Actual worker cap/accounting proof missing')
    require(profile['status'] == 'verified' and profile['phase'] == 'before-timed-gui' and
            profile['runtime_version'] == '9.3' and sup['memory_profile_setup']['verified'] is True and
            not sup['memory_profile_setup']['errors'], 'Headless setup did not verify')
    for key in ('expected_limit_bytes', 'selected_limit_bytes', 'readback_limit_bytes', 'persisted_limit_bytes'):
        require(type(profile[key]) is int and profile[key] == CAP, 'Wrong setup limit: ' + key)
    require(all(profile[k] is True for k in ('profile_was_empty', 'addon_was_empty',
            'only_expected_preference_changed', 'legacy_preference_store_absent', 'runtime_fallback_store_absent'))
            and profile['gui_initialized'] is False and profile['disk_key_count_before'] == 0 and
            profile['disk_key_count_after'] == 1 and profile['one_key_delta'] ==
            [{'key': 'plt:framework-pref:drracket:child-only-memory-limit', 'before_present': False,
              'after_value': CAP}], 'Fresh one-key preference setup missing')
    require(all(type(gui[k]) is int and gui[k] == 0 for k in ('error_count', 'dropped_records')) and
            not gui['errors'], 'Common observer reported errors or drops')
    require(len(gui['records']) == len(gui['matching_request_ids']) == 1, 'Ambiguous matching GUI request')
    rec = gui['records'][0]
    request_id = rec['request_id']
    require(integer(request_id, 1) and gui['matching_request_ids'] == [request_id] and
            gui['request_count'] == request_id and host['matching_request_id'] == request_id,
            'Selected GUI request is stale or inconsistent')
    require(rec['snapshot_sha256'] == worker['snapshot_sha256'] == SNAPSHOT and
            rec['snapshot_characters'] == 1048577 and rec['snapshot_kind'] == 'string' and
            rec['source'] == worker['source'] == host['fixture'], 'Actual worker/GUI source mismatch')
    require(rec['actual_prefab'] == worker['actual_prefab'] and
            rec['actual_prefab_truncated'] is False and rec['prefab_annotations_none'] is True and
            rec['actual_child_limit_bytes'] == CAP, 'Actual prefab/cap mismatch or truncated evidence')
    require(rec['terminal']['tag'] == worker['terminal'] == 'handler-results' and
            integer(rec['terminal']['compiled_bytes'], 1) and rec['terminal_callback_current'] is True and
            rec['application_current'] is True and type(rec['application_generation']) is int and rec['application_generation'] == 1 and
            rec['application_cancelled'] is False and type(rec['stale_application_events']) is int and
            rec['stale_application_events'] == 0 and
            type(rec['point_duplicates']) is int and rec['point_duplicates'] == 0,
            'No current successful terminal/application completion')
    monitor = rec['monitor_evidence']
    require(all(integer(monitor[k], 1) for k in ('messages', 'trace_batches', 'trace_entries', 'rename_capability_rows'))
            and all(type(monitor[k]) is int and monitor[k] == 0 for k in ('error_messages', 'invalid_payloads')),
            'Monitor trace/capability evidence incomplete')
    points = rec['gui_points']
    require(set(points) == set(GUI_POINTS), 'Missing, extra, cancelled or stale GUI endpoints')
    ordered(points, ('request-observed', 'monitor-received', 'monitor-callback-queue-attempt',
                     'monitor-callback-enter', 'application-enter', 'monitor-callback-return'))
    ordered(points, ('application-enter', 'application-complete'))
    ordered(points, ('request-observed', 'terminal-received', 'terminal-callback-queue-attempt',
                     'terminal-callback-enter', 'terminal-callback-return'))
    # Trace application can finish before the terminal; do not invent that order.
    deadline = host['post_edit_deadline_monotonic_ms']
    require(number(deadline) and number(host['first_final_lexer_valid_observed_monotonic_ms']) and
            max(metric(p) for p in points.values()) < deadline and
            host['first_final_lexer_valid_observed_monotonic_ms'] < deadline, 'Original deadline was exceeded')
    for field, label in (('terminal_received_monotonic_ms', 'terminal-received'),
                         ('terminal_callback_enter_monotonic_ms', 'terminal-callback-enter'),
                         ('terminal_callback_return_monotonic_ms', 'terminal-callback-return'),
                         ('application_complete_monotonic_ms', 'application-complete')):
        require(host[field] == points[label]['monotonic_ms'], 'Host/observer endpoint mismatch')
    require(registry(gui['actual_registry']) == registry(init['actual_registry']), 'GUI/worker registry differs')
    require(type(worker['selected_job_count']) is int and type(worker['selected_job_id']) is int and
            worker['selected_job_count'] == worker['selected_job_id'] == 1 and
            all(type(worker[k]) is int and worker[k] == 0 for k in ('dropped_jobs', 'observer_failures')) and
            worker['emission_after_stock_terminal_send'] is True and
            worker['phase_points_enabled'] is (arm == 'observed'), 'Worker correlation/activation failed')
    phase_rows = worker['phase_points']
    if arm == 'control':
        require(phase_rows == [], 'Control unexpectedly collected producer points')
    else:
        require(len(phase_rows) == len(PHASES) and {r['phase'] for r in phase_rows} == set(PHASES) and
                all(type(r['duplicate_writes']) is int and r['duplicate_writes'] == 0 for r in phase_rows),
                'Missing, duplicated or unknown worker producer points')
        ordered({r['phase']: r['producer_metrics'] for r in phase_rows}, PHASES)
    return dict(valid=True, terminal=rec['terminal'], monitor=monitor, source=rec['source'],
                registry=registry(gui['actual_registry']), actual_prefab=rec['actual_prefab'],
                pending_run_settings=host['pending_run_serialized_settings'],
                profile_path=profile['profile_path'], addon_path=profile['addon_path'],
                gui_points=points, phase_points=phase_rows,
                scope='Same-process GUI endpoint durations; worker producer deltas have runtime-wide counter scope')

def compare(arms):
    result = {'schema_version': 1, 'accepted': False, 'arms': {}, 'failures': [],
              'scope': 'One common-observer control and one producer-observed GUI. Gross outcome/overhead check only; no precise observer-cost or speedup estimate. Scalar terminal/monitor agreement is not full trace/capability equality.'}
    for arm in ('control', 'observed'):
        try:
            result['arms'][arm] = validate_arm(arms[arm], arm)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            result['failures'].append(arm + ': ' + str(error))
            raw = arms.get(arm, {})
            raw = raw if isinstance(raw, dict) else {}
            def object_at(name):
                value = raw.get(name)
                return value if isinstance(value, dict) else {}
            result['arms'][arm] = {'valid': False,
                'host_status': object_at('capture-host.json').get('status'),
                'supervisor_status': object_at('capture-supervisor.json').get('status'),
                'raw_gui_records': object_at('gui-observation.json').get('records')}
    if all(row['valid'] for row in result['arms'].values()):
        a, b = (result['arms'][arm] for arm in ('control', 'observed'))
        for key in ('terminal', 'monitor', 'source', 'registry', 'actual_prefab', 'pending_run_settings'):
            if a[key] != b[key]: result['failures'].append('Paired evidence differs: ' + key)
        if any(a[x] == b[x] for x in ('profile_path', 'addon_path')):
            result['failures'].append('Paired fresh profiles were reused')
    result['accepted'] = not result['failures']
    return result

def verify_runtime(manifest_path, package):
    m = strict_json(manifest_path)
    require(m['compiled'] is True and type(m['compile_exit_code']) is int and m['compile_exit_code'] == 0,
            'Native diagnostic compilation did not pass')
    require(m['stock_pins'] == PINS and set(m['diagnostic_sources']) == set(PINS), 'Wrong source pins')
    root, source = Path(m['diagnostic_root']).resolve(), Path(m['source_root']).resolve()
    racket = Path(m['racket'])
    require(root in source.parents and racket.is_file() and root in racket.resolve().parents, 'Runtime escaped clone')
    verified = {}
    for name, expected in m['diagnostic_sources'].items():
        path = source / name
        require(not path.is_symlink() and root in path.resolve().parents and path.stat().st_nlink == 1 and
                hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Actual diagnostic source differs: ' + name)
        text = path.read_text()
        original = re.sub(r'\n;; GUI-OBSERVE-BEGIN ([^\n]+)\n.*?\n;; GUI-OBSERVE-END \1\n', '', text, flags=re.S)
        require(hashlib.sha256(original.encode()).hexdigest() == PINS[name] and
                TRANSFORMS[name](original) == text, 'Diagnostic source is not the exact pinned additive transform: ' + name)
        verified[name] = expected
    for name, expected in m['helpers'].items():
        path = package / name
        require(name in ('gui-observer.rkt', 'gui-phase.rkt', 'capture-host.rkt', 'memory-profile.rkt') and
                not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                'Actual helper bytes differ: ' + name)
    require(set(m['helpers']) == {'gui-observer.rkt', 'gui-phase.rkt', 'capture-host.rkt', 'memory-profile.rkt'},
            'Missing actual helper pins')
    return verified

def verify_registry_sources(arms, manifest):
    """Bind the actual registered handlers to the exact prepared stock module."""
    root = Path(manifest['diagnostic_root']).resolve()
    expected = (Path(manifest['source_root']) / 'syncheck/online-comp.rkt').resolve()
    pin = manifest['diagnostic_sources']['syncheck/online-comp.rkt']
    require(root in expected.parents and expected.is_file() and
            hashlib.sha256(expected.read_bytes()).hexdigest() == pin, 'Prepared handler bytes differ')
    for arm in ('control', 'observed'):
        rows = arms[arm]['registry']
        require([(row[2], row[3]) for row in rows] == [('go', False), ('monitor', True)],
                'Actual handler exports/order differ from the stock fixture registry')
        for source, recorded_hash, _, _ in rows:
            require(Path(source).resolve() == expected and recorded_hash == pin,
                    'Actual registered handler is not the verified clone module: ' + arm)
    return {'source': str(expected), 'sha256': pin}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--observed', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    arms, errors, hashes = {}, [], {}
    for arm in ('control', 'observed'):
        arms[arm] = {}
        for name in FILES:
            path = getattr(args, arm) / name
            try:
                arms[arm][name] = strict_json(path)
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, ValueError) as error: errors.append(str(error))
    report = compare(arms)
    try: report['verified_runtime_sources'] = verify_runtime(args.manifest, Path(__file__).resolve().parent)
    except (OSError, KeyError, TypeError, ValueError) as error: errors.append(str(error))
    if all(row['valid'] for row in report['arms'].values()):
        try:
            report['verified_registered_handler'] = verify_registry_sources(report['arms'], strict_json(args.manifest))
            fixture = Path(report['arms']['control']['source'])
            require(fixture.is_file() and not fixture.is_symlink() and fixture.stat().st_size == 1048576 and
                    hashlib.sha256(fixture.read_bytes()).hexdigest() == BASE, 'Original fixture was changed or is unavailable')
            report['original_fixture_sha256'] = BASE
        except (OSError, KeyError, TypeError, ValueError) as error: errors.append(str(error))
    report['failures'].extend(errors)
    report['accepted'] = not report['failures']
    report['input_sha256'] = hashes
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['accepted'] else 1

if __name__ == '__main__': raise SystemExit(main())
