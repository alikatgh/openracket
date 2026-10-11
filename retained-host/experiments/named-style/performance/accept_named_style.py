#!/usr/bin/env python3
"""Strict paired completed-GUI acceptance for the default-off named-style lookup candidate."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from capture import read_source_pins

from accept_gui import (FILES as GUI_FILES, BASE, number, require, strict_json,
                        validate_arm, verify_runtime, verify_registry_sources)

FILES = GUI_FILES + ('activation.json', 'heartbeat.json', 'binding-export.json', 'style-witness.json')
from prepare_gui import PINS
GUI_SOURCE = 'syncheck/gui.rkt'
PACKAGE = Path(__file__).resolve().parent

def same(a, b):
    return number(a) and number(b) and abs(a-b) < .002

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


STATE_BOOL_FIELDS = {'enabled', 'cache-valid'}
STATE_COUNT_FIELDS = {'lookups', 'hits', 'rebuilds', 'members-traversed', 'named-entries', 'member-count'}
STATE_FIELDS = STATE_BOOL_FIELDS | STATE_COUNT_FIELDS
LABELS = ['before-open', 'after-open', 'ordinary-ready', 'post-join', 'final']

def validate_style_witness(w, host, arm):
    require(type(w['schema_version']) is int and w['schema_version'] == 1 and
            w['kind'] == 'actual-editor-named-style-counters' and w['arm'] == arm and
            w['verified'] is True and host['style_witness_verified'] is True and
            w['diagnostic_counters_synchronized'] is False and w['synthetic_lookup_performed'] is False,
            'Wrong or incomplete actual-editor style witness')
    rows = w['snapshots']
    require(type(rows) is list and len(rows) == len(LABELS), 'Incomplete style snapshots')
    for row, label in zip(rows, LABELS):
        require(type(row) is dict and set(row) == {'label', 'style_list_identity', 'actual_definitions_editor', 'monotonic_ms', 'state'} and
                row['label'] == label and row['actual_definitions_editor'] is True and
                type(row['style_list_identity']) is int and row['style_list_identity'] >= 1 and
                number(row['monotonic_ms']), 'Malformed style checkpoint identity, label or clock')
        state = row['state']
        if arm == 'stock':
            require(state is None, 'Stock has candidate-only state')
        else:
            require(type(state) is dict and set(state) == STATE_FIELDS and
                    all(type(state[k]) is bool for k in STATE_BOOL_FIELDS) and
                    all(type(state[k]) is int and state[k] >= 0 for k in STATE_COUNT_FIELDS) and
                    state['enabled'] is True, 'Malformed, missing, extra or disabled style scalar state')
    ids = [row['style_list_identity'] for row in rows]
    require(ids[0] == 1 and ids[1] in (1, 2) and ids[1:] == [ids[1]] * 4,
            'Style list changed after post-open checkpoint or identity was invented')
    replaced = ids[0] != ids[1]
    baseline = rows[1] if replaced else rows[0]
    require(w['style_list_replaced_on_open'] is replaced and w['workload_baseline'] == baseline['label'],
            'Style baseline crossed object identities or concealed open replacement')
    times = [r['monotonic_ms'] for r in rows]
    require(times == sorted(times) and times[0] <= host['workload_started_monotonic_ms'] <=
            times[1] <= host['edit_dispatched_monotonic_ms'] <= host['workload_completed_monotonic_ms'] <=
            times[2] <= host['post_join_final_verification_monotonic_ms'] <= times[3] <=
            host['post_export_final_verification_monotonic_ms'] <= times[4] < host['post_edit_deadline_monotonic_ms'],
            'Style snapshots escaped the original workload/deadline checkpoints')
    deltas = None
    if arm == 'candidate':
        first, ready = baseline['state'], rows[2]['state']
        deltas = {k: ready[k] - first[k] for k in STATE_COUNT_FIELDS}
        require(deltas['lookups'] > 0 and deltas['hits'] > 0,
                'Only startup activity or no real same-instance workload lookup/hit increase')
    # No synchronized arithmetic is asserted across counters. Aborted traversals,
    # races, and anonymous member insertions need not obey synthetic equalities.
    return dict(w, workload_counter_deltas=deltas,
                delta_scope='Selected same-actual-style-list file workload through ordinary-ready')

def validate_binding_export(binding, host, arm):
    require(type(binding['schema_version']) is int and binding['schema_version'] == 1 and
            binding['kind'] == 'post-readiness-binding-graph' and binding['arm'] == arm and
            binding['verified'] is True and binding['status'] == 'complete' and binding['timed'] is False and
            binding['same_public_hash_identity'] is True, 'Wrong or incomplete untimed public graph evidence')
    require(not any(k in binding for k in ('first_start', 'first_end', 'second_start', 'second_end',
                                          'before_state', 'after_first_state', 'after_second_state')),
            'Binding getter experiment must be absent')
    require(host['binding_export_verified'] is True and host['post_export_final_currentness_verified'] is True and
            number(binding['started_monotonic_ms']) and number(binding['verified_monotonic_ms']) and
            number(host['post_export_final_verification_monotonic_ms']) and
            host['post_join_final_verification_monotonic_ms'] <= binding['started_monotonic_ms'] <=
            binding['verified_monotonic_ms'] <= host['post_export_final_verification_monotonic_ms'] <
            host['post_edit_deadline_monotonic_ms'], 'Graph verification escaped readiness or deadline')
    summary = binding['export']
    require(type(summary) is dict and set(summary) == {'key_count', 'edge_count', 'canonical_format', 'canonical_sha256',
                            'owning_editor_endpoints', 'mutable_strong_equal_hash', 'immutable_equal_set_values'} and
            all(type(summary[k]) is int and 1 <= summary[k] <= 300000 for k in ('key_count', 'edge_count')) and
            summary['key_count'] <= summary['edge_count'] and
            summary['canonical_format'] == 'racket-written-sorted-exact-integer-quadruples-v1' and
            type(summary['canonical_sha256']) is str and len(summary['canonical_sha256']) == 64 and
            all(c in '0123456789abcdef' for c in summary['canonical_sha256']) and
            all(summary[k] is True for k in ('owning_editor_endpoints', 'mutable_strong_equal_hash',
                                            'immutable_equal_set_values')), 'Incomplete full export shape/digest/counts')
    return binding

def validate_pair_arm(data, arm, manifest, pins):
    require(data['capture-host.json']['arm'] == data['capture-supervisor.json']['arm'] == arm,
            'Actual arm labels disagree')
    common = copy.deepcopy(data)
    common['capture-host.json']['arm'] = common['capture-supervisor.json']['arm'] = 'control'
    result = validate_arm(common, 'control')
    verify_registry_sources({'control': result, 'observed': result}, manifest)
    root = Path(manifest['diagnostic_root']).resolve()
    rows = data['gui-observation.json']['actual_registry']
    expected_display = ['(' + r['module_spec'] + ' ' + r['export'] + ')' for r in rows if not r['monitor']]
    require(result['terminal']['handler_keys'] == expected_display, 'Terminal handler/source association differs')
    normalized_registry = []
    for source, sha, export, monitor in result['registry']:
        path = Path(source).resolve()
        require(root in path.parents, 'Actual registry path escaped its verified clone')
        normalized_registry.append((path.relative_to(root).as_posix(), sha, export, monitor))
    supervisor = data['capture-supervisor.json']
    require(supervisor['experiment'] == 'named-style-index', 'Wrong experiment label')
    act = data['activation.json']
    require(type(act['schema_version']) is int and act['schema_version'] == 1 and
            act['kind'] == 'gui_named_style_index_activation' and act['arm'] == arm, 'Wrong activation schema/arm')
    require(all(act[k] is True for k in ('verified', 'gui_handler_thread', 'gui_module_already_instantiated',
            'style_module_already_instantiated', 'same_gui_imported_style_instance', 'actual_editor_style_list', 'syncheck_module_already_instantiated')) and
            all(type(act[k]) is int and act[k] == 0 for k in ('gui_namespace_base_phase', 'style_namespace_base_phase')),
            'Actual already-instantiated GUI-imported style instance was not verified')
    require(act['gui_module'] == 'racket/gui/base' and act['style_module'] == 'racket/snip/private/style' and
            act['flag_name'] == 'OPENRACKET_NAMED_STYLE_INDEX' and
            act['activation_export'] == 'openracket-named-style-index-enabled?' and
            act['state_export'] == 'openracket-named-style-index-state' and
            act['phase_points_enabled'] is False and type(act['unexpected_experiment_flags']) is list and
            act['unexpected_experiment_flags'] == [], 'Wrong module/flag/export or unexpected experiment flags')
    expected = pins[arm + '_sha256']
    require(manifest['arm'] == arm and manifest['original_pins'] == PINS and
            manifest['style_source']['module'] == 'racket/snip/private/style' and
            manifest['style_source']['sha256'] == expected,
            'Wrong arm, common GUI pins or production style pin')
    require(act['source_sha256'] == act['expected_source_sha256'] == expected and
            supervisor['expected_style_source_sha256'] == supervisor['production_style_source_sha256'] == expected and
            supervisor['expected_gui_source_sha256'] == manifest['diagnostic_sources'][GUI_SOURCE],
            'Actual native source differs from pinned clone')
    require((arm == 'stock' and act['flag_value'] is None and act['export_status'] == 'missing' and
             act['state_export_status'] == 'missing' and act['named_style_index_enabled'] is None) or
            (arm == 'candidate' and act['flag_value'] == '1' and act['export_status'] == 'boolean' and
             act['state_export_status'] == 'procedure' and act['named_style_index_enabled'] is True),
            'Loaded style flag/export does not match arm')
    path = Path(act['source'])
    require(not path.is_symlink() and path.resolve() == Path(manifest['style_source']['source']).resolve() and
            Path(act['runtime_root']).resolve() == root and root in path.resolve().parents and
            path.stat().st_nlink == 1 and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            'Actual native style module escaped clone or changed')
    gui_path = Path(act['syncheck_source'])
    require(not gui_path.is_symlink() and gui_path.resolve() == (Path(manifest['source_root']) / GUI_SOURCE).resolve() and
            root in gui_path.resolve().parents and gui_path.stat().st_nlink == 1 and
            hashlib.sha256(gui_path.read_bytes()).hexdigest() == act['syncheck_source_sha256'] == manifest['diagnostic_sources'][GUI_SOURCE],
            'Actual existing annotation GUI module differs from common observed source')
    heartbeat = validate_heartbeat(data['heartbeat.json'], data['capture-host.json'], result['gui_points'])
    binding = validate_binding_export(data['binding-export.json'], data['capture-host.json'], arm)
    style = validate_style_witness(data['style-witness.json'], data['capture-host.json'], arm)
    result.update(actual_arm=arm, registry=normalized_registry,
                  terminal={'tag': result['terminal']['tag'], 'compiled_bytes': result['terminal']['compiled_bytes'],
                            'handler_keys': [(r[0], r[2]) for r in normalized_registry if not r[3]]},
                  activation=act, heartbeat=heartbeat, heartbeat_evidence=data['heartbeat.json'],
                  host_evidence=data['capture-host.json'], binding_export=binding, style_witness=style)
    return result

def compare_pair(arms, manifests, pins):
    result = {'schema_version': 1, 'accepted': False, 'failures': [], 'arms': {},
              'scope': 'One matched named-style completed-GUI pair; producer phases off. Untimed graph correctness after ordinary readiness. Actual same-editor-list diagnostic counters are unsynchronized. Heartbeat is closed-loop responsiveness, not physical input latency. No speed claim from acceptance.'}
    for arm in ('stock', 'candidate'):
        try:
            result['arms'][arm] = validate_pair_arm(arms[arm], arm, manifests[arm], pins)
        except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
            result['failures'].append(arm + ': ' + str(error))
            raw = arms.get(arm, {})
            raw = raw if isinstance(raw, dict) else {}
            def at(name):
                value = raw.get(name)
                return value if isinstance(value, dict) else {}
            result['arms'][arm] = {'valid': False, 'host_status': at('capture-host.json').get('status'),
                'supervisor_status': at('capture-supervisor.json').get('status'),
                'raw_gui_records': at('gui-observation.json').get('records'),
                'raw_binding_export': at('binding-export.json'), 'raw_style_witness': at('style-witness.json'),
                'raw_activation': at('activation.json'), 'raw_heartbeat': at('heartbeat.json')}
    if all(row['valid'] for row in result['arms'].values()):
        a, b = result['arms']['stock'], result['arms']['candidate']
        for key in ('terminal', 'monitor', 'source', 'registry', 'actual_prefab', 'pending_run_settings'):
            if a[key] != b[key]: result['failures'].append('Paired completed-work evidence differs: ' + key)
        if a['binding_export']['export'] != b['binding_export']['export']:
            result['failures'].append('Complete public binding graph digest/counts/shape differ')
        if any(a[k] == b[k] for k in ('profile_path', 'addon_path')):
            result['failures'].append('Fresh profiles/addons were reused')
        for key in ('stock_pins', 'helpers', 'original_pins', 'diagnostic_sources'):
            if (any(type(manifests[arm].get(key)) is not dict or not manifests[arm][key]
                    for arm in ('stock', 'candidate')) or manifests['stock'].get(key) != manifests['candidate'].get(key)):
                result['failures'].append('Common GUI/observer bytes differ: ' + key)
        if any(manifests[arm]['stock_pins'] != PINS or manifests[arm]['original_pins'] != PINS or
               set(manifests[arm]['diagnostic_sources']) != set(PINS) for arm in ('stock', 'candidate')):
            result['failures'].append('Only the approved original style module delta is allowed')
        left = Path(manifests['stock']['style_source']['source']).relative_to(Path(manifests['stock']['diagnostic_root']))
        right = Path(manifests['candidate']['style_source']['source']).relative_to(Path(manifests['candidate']['diagnostic_root']))
        if left != right or pins['stock_sha256'] == pins['candidate_sha256']:
            result['failures'].append('Distinct pinned style sources must have the same clone-relative identity')
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
            verify_runtime(manifest_path, PACKAGE, ('activation.rkt', 'heartbeat.rkt', 'binding-export.rkt', 'style-witness.rkt'), arm)
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
