#!/usr/bin/env python3
"""Strict paired completed-GUI acceptance for the isolated interval-map candidate."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from capture import read_source_pins

from accept_gui import (FILES as GUI_FILES, BASE, number, require, strict_json,
                        validate_arm, verify_runtime, verify_registry_sources)

FILES = GUI_FILES + ('activation.json', 'heartbeat.json')
SUPPORT = {'skip-list.rkt': 'd92807a371dc56c9dafd556b1f87b13c0f99fd3ec0fa4d4e244afb5e78bef46b',
           'private/skip-list.rkt': '559e7843e71c934ecde37fd2cf8983d84fedfa90729adce1da738cb0a7114833',
           'order.rkt': 'a6b436ef6c8842a508634931e52dc7e8bdcfb7391094f7c36cf51d93d03b6f8f'}
PACKAGE = Path(__file__).resolve().parent

def same(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and abs(a-b) < .002

def validate_heartbeat(hb, host, points):
    require(hb['schema_version'] == 1 and hb['kind'] == 'gui-heartbeat' and hb['clock'] == 'monotonic',
            'Wrong heartbeat schema')
    require(hb['period_ms'] == 50.0 and hb['max_records'] == 4096 and hb['producer_exited'] is True and
            hb['joined'] is True and hb['join_timed_out'] is False, 'Heartbeat pacing or cooperative cleanup failed')
    require(all(type(hb[k]) is int and hb[k] == 0 for k in ('outstanding_callbacks', 'dropped_records', 'error_count'))
            and hb['errors'] == [], 'Heartbeat has errors, drops or outstanding work')
    rows = hb['records']
    require(type(rows) is list and 0 < len(rows) <= 4096 and type(hb['submitted_count']) is int and
            type(hb['handled_count']) is int and type(hb['record_count']) is int and
            hb['submitted_count'] == hb['handled_count'] == hb['record_count'] == len(rows),
            'Heartbeat record/count evidence incomplete')
    start, stop = hb['started_monotonic_ms'], hb['stopped_monotonic_ms']
    require(number(start) and number(stop) and start <= stop, 'Invalid heartbeat lifetime')
    previous = None
    last_before_stop = start
    within_application = 0
    for i, row in enumerate(rows, 1):
        require(type(row['sequence']) is int and row['sequence'] == i and type(row['after_stop']) is bool,
                'Heartbeat sequence/state malformed')
        scheduled, submitted, handled = (row[k] for k in
            ('scheduled_monotonic_ms', 'submitted_monotonic_ms', 'handler_monotonic_ms'))
        require(all(number(t) for t in (scheduled, submitted, handled)) and start <= scheduled <= submitted <= handled,
                'Heartbeat clock/order invalid')
        require(same(row['dispatch_latency_ms'], handled-submitted) and
                same(row['producer_lateness_ms'], submitted-scheduled), 'Heartbeat latency arithmetic differs')
        if previous is None:
            require(row['handler_gap_ms'] is None and same(scheduled, start + hb['period_ms']),
                    'First heartbeat gap/deadline differs')
        else:
            require(same(scheduled, previous + hb['period_ms']) and submitted >= previous and
                    same(row['handler_gap_ms'], handled-previous), 'Heartbeat is not the declared closed-loop stream')
        require(row['after_stop'] is (handled >= stop), 'Heartbeat after-stop classification differs')
        if points['application-enter']['monotonic_ms'] <= handled <= points['application-complete']['monotonic_ms']:
            within_application += 1
        if handled < stop: last_before_stop = handled
        previous = handled
    require(number(hb['last_handler_monotonic_ms']) and same(previous, hb['last_handler_monotonic_ms']) and
            number(hb['stop_handler_gap_ms']) and same(hb['stop_handler_gap_ms'], stop-last_before_stop),
            'Heartbeat tail-gap evidence differs')
    require(within_application > 0, 'No heartbeat reached the actual application interval')
    boundaries = [host[k] for k in ('workload_started_monotonic_ms', 'edit_dispatched_monotonic_ms',
                  'workload_completed_monotonic_ms', 'post_join_final_verification_monotonic_ms',
                  'post_edit_deadline_monotonic_ms')]
    require(all(number(t) for t in boundaries) and host['heartbeat_verified'] is True and
            start <= boundaries[0] <= boundaries[1] <= boundaries[2] <= stop <= boundaries[3] < boundaries[4] and
            previous <= boundaries[3] and max(p['monotonic_ms'] for p in points.values()) <= boundaries[2],
            'Heartbeat/workload boundaries escaped original deadline')
    return {'records': len(rows), 'application_interval_records': within_application,
            'period_ms': hb['period_ms'], 'scope': 'Closed-loop queue/handler observations; not typing or physical input-to-photon'}

def validate_pair_arm(data, arm, manifest, pins):
    require(data['capture-host.json']['arm'] == data['capture-supervisor.json']['arm'] == arm,
            'Actual arm labels disagree')
    # Reuse the proven producers-OFF common GUI contract. Only its label is
    # adapted in memory after checking the real label; no source evidence changes.
    common = copy.deepcopy(data)
    common['capture-host.json']['arm'] = common['capture-supervisor.json']['arm'] = 'control'
    result = validate_arm(common, 'control')
    verify_registry_sources({'control': result, 'observed': result}, manifest)
    root = Path(manifest['diagnostic_root']).resolve()
    rows = data['gui-observation.json']['actual_registry']
    # The actual terminal's display keys must first match its actual typed registry.
    expected_display = ['(' + r['module_spec'] + ' ' + r['export'] + ')' for r in rows if not r['monitor']]
    require(result['terminal']['handler_keys'] == expected_display, 'Terminal handler/source association differs')
    normalized_registry = []
    for source, sha, export, monitor in result['registry']:
        path = Path(source).resolve()
        require(root in path.parents, 'Actual registry path escaped its verified clone')
        normalized_registry.append((path.relative_to(root).as_posix(), sha, export, monitor))
    act = data['activation.json']
    require(act['schema_version'] == 1 and act['kind'] == 'gui_interval_map_activation' and act['arm'] == arm,
            'Wrong activation schema/arm')
    require(all(act[k] is True for k in ('verified', 'gui_handler_thread', 'gui_module_already_instantiated',
            'gui_phase0_import_verified', 'interval_map_already_instantiated')) and
            type(act['gui_namespace_base_phase']) is int and act['gui_namespace_base_phase'] == 0,
            'Actual GUI dependency instance was not verified')
    require(act['gui_module'] == 'drracket/private/syncheck/gui' and act['interval_map_module'] == 'data/interval-map' and
            act['flag_name'] == 'OPENRACKET_INTERVAL_MAP_FAST_SET' and
            act['activation_export'] == 'openracket-interval-map-fast-set-enabled?' and act['phase_points_enabled'] is False,
            'Wrong activation module/flag or unexpected producer points')
    expected = pins[arm + '_sha256']
    require(act['source_sha256'] == act['expected_source_sha256'] == expected, 'Wrong actual interval-map bytes')
    require((arm == 'stock' and act['flag_value'] is None and act['export_status'] == 'missing' and act['fast_set_enabled'] is None) or
            (arm == 'candidate' and act['flag_value'] == '1' and act['export_status'] == 'boolean' and act['fast_set_enabled'] is True),
            'Loaded flag/export does not match the requested arm')
    path = Path(act['source'])
    require(not path.is_symlink() and root in path.resolve().parents and path.name == 'interval-map.rkt' and
            path.parent.name == 'data' and path.stat().st_nlink == 1 and
            hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Actual interval module escaped clone or changed')
    for name, pin in SUPPORT.items():
        support = path.parent / name
        require(not support.is_symlink() and root in support.resolve().parents and support.stat().st_nlink == 1 and
                hashlib.sha256(support.read_bytes()).hexdigest() == pin, 'Supporting data library changed: ' + name)
    heartbeat = validate_heartbeat(data['heartbeat.json'], data['capture-host.json'], result['gui_points'])
    result.update(actual_arm=arm, registry=normalized_registry,
                  terminal={'tag': result['terminal']['tag'], 'compiled_bytes': result['terminal']['compiled_bytes'],
                            'handler_keys': [(r[0], r[2]) for r in normalized_registry if not r[3]]},
                  activation=act, heartbeat=heartbeat)
    return result

def compare_pair(arms, manifests, pins):
    result = {'schema_version': 1, 'accepted': False, 'failures': [], 'arms': {},
              'scope': 'One matched completed-GUI pair; producer points off in both. Exact common-observer source and typed clone-relative registry identity required. Heartbeat is closed-loop responsiveness, not physical input latency. No speed claim from acceptance.'}
    for arm in ('stock', 'candidate'):
        try: result['arms'][arm] = validate_pair_arm(arms[arm], arm, manifests[arm], pins)
        except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
            result['failures'].append(arm + ': ' + str(error))
            raw = arms.get(arm, {})
            raw = raw if isinstance(raw, dict) else {}
            def at(name):
                val = raw.get(name)
                return val if isinstance(val, dict) else {}
            result['arms'][arm] = {'valid': False, 'host_status': at('capture-host.json').get('status'),
                                  'supervisor_status': at('capture-supervisor.json').get('status'),
                                  'raw_gui_records': at('gui-observation.json').get('records')}
    if all(row['valid'] for row in result['arms'].values()):
        a, b = result['arms']['stock'], result['arms']['candidate']
        for key in ('terminal', 'monitor', 'source', 'registry', 'actual_prefab', 'pending_run_settings'):
            if a[key] != b[key]: result['failures'].append('Paired completed-work evidence differs: ' + key)
        if any(a[k] == b[k] for k in ('profile_path', 'addon_path')):
            result['failures'].append('Fresh profiles/addons were reused')
        for key in ('stock_pins', 'diagnostic_sources', 'helpers'):
            if (any(type(manifests[arm].get(key)) is not dict or not manifests[arm][key]
                    for arm in ('stock', 'candidate')) or
                    manifests['stock'].get(key) != manifests['candidate'].get(key)):
                result['failures'].append('Common observer bytes differ: ' + key)
    result['accepted'] = not result['failures']
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arm in ('stock', 'candidate'):
        parser.add_argument('--' + arm, type=Path, required=True)
        parser.add_argument('--' + arm + '-manifest', type=Path, required=True)
    args = parser.parse_args()
    arms, manifests, errors, hashes = {}, {}, [], {}
    try: pins = read_source_pins(PACKAGE / 'candidate-source-pins.json')
    except (OSError, ValueError) as error:
        pins = {}; errors.append(str(error))
    for arm in ('stock', 'candidate'):
        arms[arm] = {}; manifests[arm] = {}
        for name in FILES:
            path = getattr(args, arm) / name
            try:
                arms[arm][name] = strict_json(path, 2*1024*1024 if name == 'heartbeat.json' else 1024*1024)
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, ValueError) as error: errors.append(str(error))
        manifest_path = getattr(args, arm + '_manifest')
        try:
            manifests[arm] = strict_json(manifest_path)
            verify_runtime(manifest_path, PACKAGE, ('activation.rkt', 'heartbeat.rkt'))
        except (OSError, KeyError, TypeError, ValueError) as error: errors.append(str(error))
    report = compare_pair(arms, manifests, pins)
    if all(row['valid'] for row in report['arms'].values()):
        try:
            fixture = Path(report['arms']['stock']['source'])
            require(fixture.is_file() and not fixture.is_symlink() and fixture.stat().st_size == 1048576 and
                    hashlib.sha256(fixture.read_bytes()).hexdigest() == BASE, 'Original fixture changed')
        except (OSError, ValueError) as error: errors.append(str(error))
    report['failures'].extend(errors); report['accepted'] = not report['failures']; report['input_sha256'] = hashes
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['accepted'] else 1

if __name__ == '__main__': raise SystemExit(main())
