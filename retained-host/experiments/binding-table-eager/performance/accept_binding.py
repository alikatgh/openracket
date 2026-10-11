#!/usr/bin/env python3
"""Strict paired completed-GUI acceptance for the default-off eager binding-table candidate."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from capture import read_source_pins

from accept_gui import (FILES as GUI_FILES, BASE, number, require, strict_json,
                        validate_arm, verify_runtime, verify_registry_sources)

FILES = GUI_FILES + ('activation.json', 'heartbeat.json', 'binding-export.json')
from prepare_gui import PINS
GUI_SOURCE = 'syncheck/gui.rkt'
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
    require(boundaries[4] == boundaries[1] + 90000,
            'Post-edit deadline must equal the recorded edit timestamp plus exactly 90 seconds')
    return {'records': len(rows), 'application_interval_records': within_application,
            'period_ms': hb['period_ms'], 'scope': 'Closed-loop queue/handler observations; not typing or physical input-to-photon'}

EXPORT_METRICS = ('monotonic_ms', 'allocation_bytes', 'managed_bytes', 'gc_ms', 'cpu_all_places_ms')
# Preregistered before eager timing; no tolerance, rounding, GC exemption or widening.
FIRST_GETTER_MAX_MS = 1.000
STATE_BOOL_FIELDS = {'enabled', 'active', 'in_flight', 'exposed'}
STATE_COUNT_FIELDS = {'generation', 'accepted', 'duplicates', 'eager_writes', 'stock_calls',
                      'pending', 'materializations', 'public_keys', 'indexed_edges', 'cached_starts',
                      'unsupported_fallbacks', 'failure_fallbacks'}
STATE_FIELDS = STATE_BOOL_FIELDS | STATE_COUNT_FIELDS | {'fallback_reason'}

def validate_binding_export(binding, host, arm):
    require(type(binding['schema_version']) is int and binding['schema_version'] == 1 and binding['kind'] == 'binding-table-eager-public-exposure' and
            binding['arm'] == arm and binding['verified'] is True and binding['status'] == 'complete' and
            binding['same_public_hash_identity'] is True, 'Wrong or incomplete public export evidence')
    points = [binding[k] for k in ('first_start', 'first_end', 'second_start', 'second_end')]
    require(all(type(p) is dict and set(p) == set(EXPORT_METRICS) and
                number(p['monotonic_ms']) and
                all(type(p[k]) is int and p[k] >= 0 for k in EXPORT_METRICS if k != 'monotonic_ms') for p in points), 'Invalid export command counters')
    times = [p['monotonic_ms'] for p in points]
    require(times == sorted(times), 'Export commands overlap or have nonmonotonic clocks')
    for counter in ('allocation_bytes', 'gc_ms', 'cpu_all_places_ms'):
        require([p[counter] for p in points] == sorted(p[counter] for p in points),
                'Export cumulative counter decreased: ' + counter)
    require(host['binding_export_verified'] is True and host['post_export_final_currentness_verified'] is True and
            number(binding['verified_monotonic_ms']) and number(host['post_export_final_verification_monotonic_ms']) and
            host['post_join_final_verification_monotonic_ms'] <= times[0] <= times[-1] <=
            binding['verified_monotonic_ms'] <= host['post_export_final_verification_monotonic_ms'] <
            host['post_edit_deadline_monotonic_ms'], 'Export/final source verification escaped readiness or deadline')
    summary = binding['export']
    require(set(summary) == {'key_count', 'edge_count', 'canonical_format', 'canonical_sha256',
                            'owning_editor_endpoints', 'mutable_strong_equal_hash', 'immutable_equal_set_values'} and
            all(type(summary[k]) is int and 1 <= summary[k] <= 300000 for k in ('key_count', 'edge_count')) and
            summary['key_count'] <= summary['edge_count'] and
            summary['canonical_format'] == 'racket-written-sorted-exact-integer-quadruples-v1' and
            type(summary['canonical_sha256']) is str and len(summary['canonical_sha256']) == 64 and
            all(c in '0123456789abcdef' for c in summary['canonical_sha256']) and
            all(summary[k] is True for k in ('owning_editor_endpoints', 'mutable_strong_equal_hash',
                                            'immutable_equal_set_values')), 'Incomplete full export shape/digest/counts')
    before, first, second = (binding[k] for k in ('before_state', 'after_first_state', 'after_second_state'))
    if arm == 'stock':
        require(before is first is second is None, 'Stock unexpectedly exposes candidate eager state')
    else:
        for state in (before, first, second):
            require(type(state) is dict and set(state) == STATE_FIELDS and
                    all(type(state[k]) is int and state[k] >= 0 for k in STATE_COUNT_FIELDS) and
                    all(type(state[k]) is bool for k in STATE_BOOL_FIELDS) and
                    (state['fallback_reason'] is False or
                     type(state['fallback_reason']) is str and state['fallback_reason'] in
                     ('public-exposure', 'unsupported-input', 'reentrant-call', 'interrupted')), 'Malformed candidate eager state')
        require(before['enabled'] is before['active'] is True and
                before['in_flight'] is before['exposed'] is False and
                before['accepted'] == before['eager_writes'] == before['indexed_edges'] > 0 and
                before['cached_starts'] == before['public_keys'] > 0 and
                before['generation'] > 0 and
                all(before[k] == 0 for k in ('pending', 'materializations', 'stock_calls',
                                             'unsupported_fallbacks', 'failure_fallbacks')) and
                before['fallback_reason'] is False,
                'No actual completed eager writes/private-cache evidence before exposure')
        require(first['enabled'] is first['exposed'] is True and
                first['active'] is first['in_flight'] is False and
                all(first[k] == 0 for k in ('pending', 'materializations', 'stock_calls',
                                            'indexed_edges', 'cached_starts',
                                            'unsupported_fallbacks', 'failure_fallbacks')) and
                first['fallback_reason'] == 'public-exposure' and
                all(first[k] == before[k] for k in ('accepted', 'duplicates', 'eager_writes',
                                                    'public_keys', 'generation')) and
                first == second and before['accepted'] == summary['edge_count'] and
                before['public_keys'] == summary['key_count'],
                'First getter failed cache disposal/preserved eager-write state or second getter changed state')
    duration = times[1]-times[0]
    return dict(binding, first_duration_ms=duration, second_duration_ms=times[3]-times[2],
                first_getter_max_ms=FIRST_GETTER_MAX_MS if arm == 'candidate' else None,
                first_getter_bound_passed=duration <= FIRST_GETTER_MAX_MS if arm == 'candidate' else None)

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
    require(data['capture-supervisor.json']['experiment'] == 'binding-table-eager',
            'Wrong experiment label')
    act = data['activation.json']
    require(type(act['schema_version']) is int and act['schema_version'] == 1 and act['kind'] == 'gui_binding_table_eager_activation' and act['arm'] == arm,
            'Wrong activation schema/arm')
    require(all(act[k] is True for k in ('verified', 'gui_handler_thread', 'gui_module_already_instantiated',
            'same_gui_module_instance')) and
            type(act['gui_namespace_base_phase']) is int and act['gui_namespace_base_phase'] == 0,
            'Actual GUI module instance was not verified')
    require(act['gui_module'] == 'drracket/private/syncheck/gui' and
            act['flag_name'] == 'OPENRACKET_BINDING_TABLE_EAGER' and
            act['activation_export'] == 'openracket-binding-table-eager-enabled?' and act['phase_points_enabled'] is False and
            type(act['unexpected_experiment_flags']) is list and act['unexpected_experiment_flags'] == [],
            'Wrong activation module/flag or unexpected producer points')
    require(manifest['arm'] == arm and manifest['original_pins'][GUI_SOURCE] == pins[arm + '_sha256'],
            'Wrong arm or original production GUI pin')
    expected = manifest['diagnostic_sources'][GUI_SOURCE]
    require(act['source_sha256'] == act['expected_source_sha256'] == expected, 'Wrong actual observed GUI bytes')
    require((arm == 'stock' and act['flag_value'] is None and act['export_status'] == 'missing' and act['binding_eager_enabled'] is None) or
            (arm == 'candidate' and act['flag_value'] == '1' and act['export_status'] == 'boolean' and act['binding_eager_enabled'] is True),
            'Loaded flag/export does not match the requested arm')
    path = Path(act['source'])
    require(not path.is_symlink() and path.resolve() == (Path(manifest['source_root']) / GUI_SOURCE).resolve()
            and root in path.resolve().parents and path.stat().st_nlink == 1 and
            hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Actual GUI module escaped clone or changed')
    heartbeat = validate_heartbeat(data['heartbeat.json'], data['capture-host.json'], result['gui_points'])
    binding = validate_binding_export(data['binding-export.json'], data['capture-host.json'], arm)
    result.update(actual_arm=arm, registry=normalized_registry,
                  terminal={'tag': result['terminal']['tag'], 'compiled_bytes': result['terminal']['compiled_bytes'],
                            'handler_keys': [(r[0], r[2]) for r in normalized_registry if not r[3]]},
                  activation=act, heartbeat=heartbeat, binding_export=binding)
    return result

def compare_pair(arms, manifests, pins):
    result = {'schema_version': 1, 'accepted': False, 'failures': [], 'arms': {},
              'candidate_first_getter_max_ms': FIRST_GETTER_MAX_MS,
              'scope': 'One matched eager completed-GUI pair; producer points off in both. Exact common-observer source and typed clone-relative registry identity required. Heartbeat is closed-loop responsiveness, not physical input latency. First and second public getters are separate compatibility costs after ordinary readiness. No speed claim from acceptance.'}
    for arm in ('stock', 'candidate'):
        try:
            result['arms'][arm] = validate_pair_arm(arms[arm], arm, manifests[arm], pins)
            if arm == 'candidate' and not result['arms'][arm]['binding_export']['first_getter_bound_passed']:
                result['failures'].append('candidate: First public getter exceeds preregistered 1.000 ms bound')
        except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
            result['failures'].append(arm + ': ' + str(error))
            raw = arms.get(arm, {})
            raw = raw if isinstance(raw, dict) else {}
            def at(name):
                val = raw.get(name)
                return val if isinstance(val, dict) else {}
            result['arms'][arm] = {'valid': False, 'host_status': at('capture-host.json').get('status'),
                                  'supervisor_status': at('capture-supervisor.json').get('status'),
                                  'raw_gui_records': at('gui-observation.json').get('records'),
                                  'raw_binding_export': at('binding-export.json')}
    if all(row['valid'] for row in result['arms'].values()):
        a, b = result['arms']['stock'], result['arms']['candidate']
        for key in ('terminal', 'monitor', 'source', 'registry', 'actual_prefab', 'pending_run_settings'):
            if a[key] != b[key]: result['failures'].append('Paired completed-work evidence differs: ' + key)
        if a['binding_export']['export'] != b['binding_export']['export']:
            result['failures'].append('Complete public binding graph digest/counts/shape differ')
        if any(a[k] == b[k] for k in ('profile_path', 'addon_path')):
            result['failures'].append('Fresh profiles/addons were reused')
        for key in ('stock_pins', 'helpers'):
            if (any(type(manifests[arm].get(key)) is not dict or not manifests[arm][key]
                    for arm in ('stock', 'candidate')) or
                    manifests['stock'].get(key) != manifests['candidate'].get(key)):
                result['failures'].append('Common observer bytes differ: ' + key)
        for arm in ('stock', 'candidate'):
            manifest = manifests[arm]
            expected_pins = dict(PINS, **{GUI_SOURCE: pins[arm + '_sha256']})
            if manifest.get('stock_pins') != PINS or manifest.get('original_pins') != expected_pins:
                result['failures'].append('Only the approved original GUI delta is allowed: ' + arm)
        left = manifests['stock'].get('diagnostic_sources', {})
        right = manifests['candidate'].get('diagnostic_sources', {})
        if (set(left) != set(PINS) or set(right) != set(PINS) or
                any(left.get(k) != right.get(k) for k in PINS if k != GUI_SOURCE) or
                left.get(GUI_SOURCE) == right.get(GUI_SOURCE)):
            result['failures'].append('Common transformed modules or distinct arm GUI bytes differ')
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
            verify_runtime(manifest_path, PACKAGE, ('activation.rkt', 'heartbeat.rkt', 'binding-export.rkt'), arm)
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
