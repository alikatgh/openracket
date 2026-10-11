#!/usr/bin/env python3
"""Read-only, outcome-aware single-trial phase observer control validator."""
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

CAP = 268435456
MANIFEST_PIN = '44b6c593c61eb752b7da04eece27245f127d9c448dff576b52751f354e0c7e56'
PHASE_PIN = 'c7d84fc494be611634335348b75d39bcb4acb7fe9293df576e3d9a831fd53bee'
SETTINGS = '#s(prefab-module-settings #() (default) #t #t none #t)'
SNAPSHOT = 'f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735'
SOURCES = {
    'module-language.rkt': ('e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53', '69112d85d994b3817e2cba9ff1f2be9ff1907cdeb915dfc44fb461e064f186ee'),
    'expanding-place.rkt': ('f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383', '1783d57f187245f760b998caf18ad0b426bd8ae737a75cbf246289dd4181951b'),
    'syncheck/online-comp.rkt': ('1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5', '631b0dc64a67a818a819782e751886a0529c90611cc41e55e5118a8973392609'),
}
CONTEXT = {
    'xref.rkt': 'acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7',
    'traversals.rkt': 'bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00',
}
REQUIRED_PHASES = {
    'worker-start', 'monitor-start', 'worker-phase-09', 'worker-phase-10',
    'worker-phase-11', 'worker-phase-12', 'worker-phase-13', 'go-send-expanded',
    'go-wait-for-monitor', 'monitor-build-trace-start',
    'monitor-build-trace-complete/send-back-start', 'monitor-acknowledge-go',
}
TERMINALS = {'handler-results', 'abnormal-termination', 'access-violation',
             'reader-in-defs-error', 'exn:variable', 'exn'}
INCOMPLETE = {'supervisor_interval_timeout', 'worker_place_died'}
MONITOR_COUNTS = ('messages', 'trace_batches', 'trace_entries', 'rename_capability_rows',
                  'error_messages', 'invalid_payloads', 'other_monitor_messages')
ENV_KEYS = {'PLTUSERHOME', 'PLTADDONDIR', 'PLTCOLLECTS', 'PLTCOMPILEDROOTS',
            'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(value):
    raise ValueError('non-finite JSON number: ' + value)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    data = json.loads(Path(path).read_text(), parse_constant=reject, object_pairs_hook=unique)
    if type(data) is not dict:
        raise ValueError(str(path) + ': expected JSON object')
    return data


def obj(value):
    return value if type(value) is dict else {}


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def utc(value):
    try:
        result = datetime.fromisoformat(value)
        return result if result.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def terminal_valid(value):
    if type(value) is not dict or not isinstance(value.get('tag'), str) or value.get('tag') not in TERMINALS:
        return False
    if value['tag'] == 'handler-results':
        keys = value.get('handler_keys')
        return (type(keys) is list and bool(keys) and all(isinstance(k, str) and k for k in keys)
                and integer(value.get('loaded_paths_count'))
                and integer(value.get('compiled_bytes'), 1) and digest(value.get('compiled_sha256')))
    if value['tag'] == 'abnormal-termination':
        return (isinstance(value.get('message'), str) and type(value.get('explicit_out_of_memory')) is bool
                and value['explicit_out_of_memory'] == ('out of memory' in value['message']))
    return isinstance(value.get('exception_details'), str) and type(value.get('exception_details_truncated')) is bool


def monitor(value):
    value = obj(value)
    valid = (type(value.get('check_syntax_monitor_registry_entries')) is int
             and value['check_syntax_monitor_registry_entries'] == 1
             and all(integer(value.get(k)) for k in MONITOR_COUNTS)
             and type(value.get('errors')) is list)
    clean = valid and all(value[k] > 0 for k in MONITOR_COUNTS[:4]) and all(value[k] == 0 for k in MONITOR_COUNTS[4:]) and value['errors'] == []
    return valid, clean


def process_cleanup(value):
    value = obj(value)
    return (all(value.get(k) is True for k in ('attempted', 'complete', 'child_reaped', 'membership_verified'))
            and value.get('remaining_live_pids') == [] and value.get('errors') == [])


def internal_cleanup(value):
    value = obj(value)
    return (all(value.get(k) is True for k in ('accepted', 'control_stopped', 'place_dead',
                'root_logger_stopped', 'diagnostic_custodian_shutdown'))
            and value.get('control_acknowledgement') == 'stopped' and value.get('errors') == [])


def phase_assessment(value):
    """Missing completed phases on a real failure do not invalidate that failure."""
    failures = []
    def require(ok, reason):
        if not ok:
            failures.append(reason)
    p = obj(value)
    require(p.get('enabled') is True and type(p.get('trial')) is int and p.get('trial') == 1
            and type(p.get('job_generation')) is int and p.get('job_generation') == 1
            and p.get('active') is False, 'phase enabled/trial/generation/end mismatch')
    for key in ('phase_points_dropped', 'sample_ticks_dropped', 'input_events_dropped', 'stale_events_discarded'):
        require(type(p.get(key)) is int and p[key] == 0, 'missing or dropped phase delivery: ' + key)
    for key, expected in (('frame_cap', 8), ('text_cap', 240), ('phase_point_cap', 128),
                          ('sample_cap', 256), ('sample_period_ms', 250)):
        require(number(p.get(key)) and p[key] == expected, 'phase bound changed: ' + key)
    points = p.get('phase_points')
    points = points if type(points) is list else []
    require(len(points) <= 128 and all(type(x) is dict for x in points), 'invalid phase point list')
    points = [obj(x) for x in points]
    labels = [x.get('phase') for x in points]
    present = {x for x in labels if isinstance(x, str)}
    require(REQUIRED_PHASES <= present, 'missing completed request phase coverage')
    require(len(present) == len(labels), 'duplicate or malformed phase labels')
    require(all(type(x.get('trial')) is int and x.get('trial') == 1
                and type(x.get('job_generation')) is int and x.get('job_generation') == 1 and
                number(obj(x.get('source_metrics')).get('monotonic_ms')) for x in points),
            'invalid phase generation or producer timestamp')
    times = {x.get('phase'): obj(x.get('source_metrics')).get('monotonic_ms') for x in points if isinstance(x.get('phase'), str)}
    for sequence in [('worker-phase-09', 'worker-phase-10', 'worker-phase-11', 'worker-phase-12', 'worker-phase-13'),
                     ('monitor-build-trace-start', 'monitor-build-trace-complete/send-back-start', 'monitor-acknowledge-go')]:
        ts = [times.get(x) for x in sequence]
        require(all(number(t) for t in ts) and all(a <= b for a, b in zip(ts, ts[1:])), 'missing or nonmonotonic producer phase times')
    evidence = obj(p.get('attribution_evidence'))
    require(evidence.get('status') == 'coarse_thread_context_available' and all(evidence.get(k) is True for k in
            ('working_thread_registered', 'monitor_thread_registered', 'xref_service_thread_registered',
             'usable_monitor_frames', 'usable_xref_frames')), 'actual monitor/service thread context incomplete')
    service = obj(p.get('xref_service_registration'))
    require(service.get('status') == 'registered_existing_service_thread' and service.get('source_sha256') == CONTEXT['xref.rkt'], 'existing service source not proven')
    require(p.get('stock_logger_subscription') is False, 'stock logger subscription changed or missing')
    return {'complete': not failures, 'failures': failures, 'present_phases': labels,
            'missing_phases': sorted(REQUIRED_PHASES - present)}


def assess(capture, host, capture_sup, off, off_sup, on, on_sup):
    """Validate recorded schemas; CLI additionally requires actual file/source checks."""
    errors = []
    def require(ok, reason):
        if not ok:
            errors.append(reason)
    documents = [capture, host, capture_sup, off, off_sup, on, on_sup]
    require(all(type(d) is dict for d in documents), 'one or more evidence documents are null/malformed')
    capture, host, capture_sup, off, off_sup, on, on_sup = map(obj, documents)
    setup = obj(capture_sup.get('memory_profile_setup'))
    conf = obj(setup.get('configuration'))
    require(setup.get('verified') is True and setup.get('exit_code') == 0 and setup.get('timeout') is False,
            'one-key profile setup failed')
    require(conf.get('status') == 'verified' and conf.get('only_expected_preference_changed') is True
            and conf.get('disk_key_count_before') == 0 and conf.get('disk_key_count_after') == 1
            and conf.get('one_key_delta') == [{'after_value': CAP, 'before_present': False,
                    'key': 'plt:framework-pref:drracket:child-only-memory-limit'}], 'one-key preference change not proven')
    require(all(conf.get(k) == CAP for k in ('selected_limit_bytes', 'expected_limit_bytes',
                'persisted_limit_bytes', 'readback_limit_bytes')) and conf.get('original_default_limit_bytes') == CAP // 2,
            'profile memory limit mismatch')
    require(all(conf.get(k) is True for k in ('profile_was_empty', 'addon_was_empty',
             'legacy_preference_store_absent', 'runtime_fallback_store_absent'))
            and conf.get('gui_initialized') is False, 'fresh headless profile not proven')
    require(capture_sup.get('expected_memory_limit_bytes') == CAP and capture_sup.get('gui_started') is True
            and capture_sup.get('exit_code') == 0 and capture_sup.get('timeout') is False
            and process_cleanup(capture_sup.get('cleanup')), 'capture process/cap/cleanup failed')
    require(host.get('status') == 'terminal_captured' and host.get('racket_version') == '9.3'
            and host.get('preserved_preferences') == {'child_limit_bytes': CAP, 'coloring': True, 'online_compilation': True},
            'actual GUI preference or runtime mismatch')
    require(capture.get('status') == 'terminal_observed' and capture.get('actual_child_limit_bytes') == CAP
            and terminal_valid(capture.get('terminal')) and obj(capture.get('terminal')).get('tag') == 'handler-results'
            and monitor(capture.get('monitor_evidence'))[1], 'capture did not deliver clean handler-results and monitor trace')
    require(capture.get('snapshot_sha256') == SNAPSHOT and capture.get('snapshot_bytes') == 1048577
            and capture.get('snapshot_characters') == 1048577 and capture.get('snapshot_kind') == 'string'
            and capture.get('settings') == SETTINGS, 'snapshot or actual prefab settings mismatch')
    require(host.get('edited_snapshot_sha256') == SNAPSHOT and capture_sup.get('edited_snapshot_sha256') == SNAPSHOT,
            'capture snapshot witnesses disagree')
    require(digest(capture.get('registry_sha256')) and type(capture.get('registry')) is list
            and bool(capture.get('registry')) and isinstance(capture.get('source'), str) and bool(capture.get('source')),
            'capture registry/source identity missing')
    observations = {}
    for name, replay, sup, enabled in [('off', off, off_sup, False), ('on', on, on_sup, True)]:
        def need(ok, reason):
            require(ok, name + ': ' + reason)
        config = obj(sup.get('config'))
        need(config.get('trials') == 1 and type(config.get('trials')) is int, 'expected exactly one configured trial')
        need(config.get('phase_probe', False) is enabled and replay.get('phase_probe_enabled') is enabled,
             'phase enablement mismatch')
        need(all(config.get(k) == v for k, v in [('init_timeout_seconds', 30), ('terminal_timeout_seconds', 60),
             ('cleanup_timeout_seconds', 2)]) and sup.get('hard_wall_budget_seconds') == 97
             and sup.get('cleanup_reserve_seconds') == 2 and sup.get('startup_cushion_seconds') == 5
             and sup.get('sample_period_seconds') == .1, 'existing one-trial limits changed')
        need(process_cleanup(sup.get('cleanup')) and internal_cleanup(replay.get('cleanup')), 'cleanup incomplete')
        need(sup.get('errors') == [] and sup.get('stdout_unparsed_bytes') == 0, 'supervisor protocol errors or unread bytes')
        need(replay.get('actual_worker_child_limit_bytes') == CAP and replay.get('actual_worker_memory_accounting_available') is True,
             'actual ready cap/accounting not proven')
        need(replay.get('instrumented_stock_copy') is True and replay.get('racket_version') == '9.3'
             and replay.get('os') == host.get('os') and replay.get('vm') == 'chez-scheme', 'runtime identity mismatch')
        for key in ('snapshot_sha256', 'snapshot_bytes', 'snapshot_characters', 'registry_sha256', 'registry', 'source'):
            need(key in capture and replay.get(key) == capture[key], key + ' differs from capture')
        need(replay.get('prefab_settings') == SETTINGS and replay.get('capture_terminal') == capture.get('terminal'),
             'prefab settings or copied capture terminal differs')
        if enabled:
            need(replay.get('phase_probe_sha256') == PHASE_PIN, 'phase module hash mismatch')
        else:
            need('phase_probe_sha256' not in replay, 'disabled run loaded phase module')
        rows = replay.get('trials')
        need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, 'expected exactly one recorded trial')
        row = obj(rows[0]) if type(rows) is list and rows else {}
        need(type(row.get('trial')) is int and row.get('trial') == 1
             and row.get('warmth') == 'fresh-process first expansion after initialization; not cold disk cache'
             and row.get('prior_terminal_retained_before_request') is False
             and row.get('prior_capabilities_retained_before_request') == 0
             and row.get('prior_place_channels_retained_before_request') == 0, 'fresh first trial not proven')
        need(integer(sup.get('pid'), 1) and sup.get('pgid') == sup.get('pid')
             and utc(sup.get('started_utc')) is not None and utc(sup.get('finished_utc')) is not None
             and number(sup.get('started_monotonic_ms')), 'fresh process witness missing')
        outcome, terminal = row.get('outcome'), row.get('terminal')
        complete_terminal = outcome in TERMINALS if isinstance(outcome, str) else False
        incomplete = outcome in INCOMPLETE if isinstance(outcome, str) else False
        need(complete_terminal or incomplete, 'unknown or missing trial outcome')
        need((complete_terminal and terminal_valid(terminal) and terminal['tag'] == outcome)
             or (incomplete and terminal is None), 'terminal schema inconsistent with outcome')
        need(type(row.get('terminal_summary_matches_integrated_capture')) is bool and
             row['terminal_summary_matches_integrated_capture'] == (terminal is not None and terminal == capture.get('terminal')),
             'terminal summary parity claim inconsistent with actual summary')
        need(monitor(row.get('monitor_evidence'))[0], 'malformed monitor scalar evidence')
        need(integer(row.get('retained_place_channels')) and integer(row.get('retained_capabilities'))
             and integer(replay.get('last_place_channels_retained_until_cleanup'))
             and integer(replay.get('last_capabilities_retained_until_cleanup')),
             'malformed capability retention evidence')
        need(replay.get('last_terminal_retained_until_cleanup') is complete_terminal, 'terminal retention witness inconsistent')
        need(obj(sup.get('timeout')).get('triggered') is False
             and obj(sup.get('death')).get('finished_event_received') is True
             and sup.get('status') == ('ok' if complete_terminal else 'driver_failed')
             and obj(sup.get('death')).get('returncode') == (0 if complete_terminal else 1)
             and replay.get('status') == ('complete' if complete_terminal else 'incomplete_terminal_protocol'),
             'driver/supervisor status inconsistent with outcome')
        intervals = sup.get('intervals')
        interval = obj(intervals[0]) if type(intervals) is list and intervals else {}
        need(type(intervals) is list and len(intervals) == 1 and interval.get('trial') == 1
             and interval.get('outcome') == outcome and interval.get('closure') == 'interval_end',
             'supervisor interval does not corroborate one outcome')
        phase = row.get('phase_probe')
        need(phase is None or type(phase) is dict, 'malformed phase record')
        if not enabled:
            need(phase is None, 'disabled observer emitted phase record')
        phase_info = phase_assessment(phase) if enabled else {'complete': None, 'reason': 'observer disabled as intended'}
        clean = monitor(row.get('monitor_evidence'))[1]
        channels = row.get('retained_place_channels')
        retained = (integer(channels, 1) and replay.get('last_place_channels_retained_until_cleanup') == channels
                    and replay.get('last_capabilities_retained_until_cleanup') == row.get('retained_capabilities'))
        success = outcome == 'handler-results' and terminal_valid(terminal) and clean and retained
        scalar_parity = all(obj(row.get('monitor_evidence')).get(k) == obj(capture.get('monitor_evidence')).get(k)
                            for k in ('trace_entries', 'rename_capability_rows'))
        observed = ('oom' if outcome == 'abnormal-termination' and obj(terminal).get('explicit_out_of_memory') is True
                    else 'timeout' if outcome == 'supervisor_interval_timeout' else outcome)
        differences = {k: {'capture': obj(capture.get('terminal')).get(k), 'replay': obj(terminal).get(k)}
                       for k in sorted(set(obj(capture.get('terminal'))) | set(obj(terminal)))
                       if obj(capture.get('terminal')).get(k) != obj(terminal).get(k)}
        observations[name] = {'observed_outcome': observed, 'recorded_outcome': outcome, 'terminal': terminal,
            'all_recorded_outcomes': [{k: obj(r).get(k) for k in ('trial','outcome','terminal','statuses',
                'terminal_summary_matches_integrated_capture')} for r in rows] if type(rows) is list else rows,
            'statuses': row.get('statuses'), 'replay_status': replay.get('status'), 'supervisor_status': sup.get('status'),
            'supervisor_timeout': sup.get('timeout'), 'supervisor_death': sup.get('death'),
            'last_observed_terminal_before_probe_queries': replay.get('last_observed_terminal_before_probe_queries'),
            'successful_replay': success, 'terminal_summary_parity': terminal is not None and terminal == capture.get('terminal'),
            'terminal_summary_differences': differences, 'monitor_evidence': row.get('monitor_evidence'),
            'monitor_scalar_parity': scalar_parity, 'rename_capabilities_retained': retained,
            'phase_completeness': phase_info, 'pid': sup.get('pid'), 'pgid': sup.get('pgid'),
            'started_utc': sup.get('started_utc'), 'finished_utc': sup.get('finished_utc')}
    off_config, on_config = obj(off_sup.get('config')), obj(on_sup.get('config'))
    require(isinstance(off_config.get('capture'), str) and off_config['capture'] == on_config.get('capture'), 'both arms must use the same captured file')
    require(isinstance(off_config.get('output'), str) and isinstance(on_config.get('output'), str)
            and off_config['output'] != on_config['output'], 'results directories must differ')
    commands = [x.get('command') for x in (capture_sup, off_sup, on_sup)]
    require(all(type(x) is list and len(x) == 2 for x in commands)
            and commands[1] == commands[2] and commands[0][0] == commands[1][0],
            'runtime/driver commands differ or are malformed')
    require(type(off_sup.get('launch_context')) is dict and off_sup['launch_context'] == on_sup.get('launch_context'), 'restored launch contexts differ')
    require(integer(off_sup.get('pid'), 1) and integer(on_sup.get('pid'), 1)
            and number(off_sup.get('started_monotonic_ms')) and number(on_sup.get('started_monotonic_ms'))
            and (off_sup['pid'], off_sup['started_monotonic_ms']) != (on_sup['pid'], on_sup['started_monotonic_ms'])
            and number(off_sup.get('elapsed_seconds'))
            and off_sup['started_monotonic_ms'] + 1000 * off_sup['elapsed_seconds'] <= on_sup['started_monotonic_ms'],
            'separate sequential process identities not proven')
    start0, end0, start1, end1 = [utc(s.get(k)) for s, k in [(off_sup,'started_utc'), (off_sup,'finished_utc'), (on_sup,'started_utc'), (on_sup,'finished_utc')]]
    require(all(x is not None for x in (start0,end0,start1,end1)) and start0 <= end0 <= start1 <= end1,
            'sequential off-then-on process lifetimes not proven')
    result = {'schema_version': 1, 'observation_valid': not errors, 'observation_failures': errors,
              'observations': observations, 'both_successful': all(x['successful_replay'] for x in observations.values()),
              'both_terminal_summary_parity': all(x['terminal_summary_parity'] for x in observations.values()),
              'both_monitor_scalar_parity': all(x['monitor_scalar_parity'] for x in observations.values()),
              'on_phase_complete': observations['on']['phase_completeness']['complete'],
              'prior_completed_phase_acceptance': {'run': '38110770395', 'accepted': False, 'unchanged_by_this_control': True},
              'scope': 'One observation per arm. Phase-observation off retains readiness/control and GC observers, unlike GUI capture. Pinned replay validates captured source/runtime/settings/registry before ready. Scalar monitor and terminal summaries are not full payload/capability equivalence. No causal allocator, CPU ownership, timing improvement, or speedup claim.'}
    classify(result)
    return result


def classify(result):
    arms = result.get('observations', {})
    off, on = obj(arms.get('off')), obj(arms.get('on'))
    if not result['observation_valid']:
        label = 'invalid_or_incomplete_control_evidence'
        conclusion = 'Recorded outcomes are retained, but the control cannot establish the intended comparison.'
    elif (off.get('successful_replay') and off.get('terminal_summary_parity')
          and off.get('monitor_scalar_parity') and on.get('observed_outcome') == 'oom'):
        label = 'conditional_single_observation_instrumentation_sensitivity'
        conclusion = 'Off succeeded and on OOMed once: conditional single-observation evidence of instrumentation sensitivity; no exact allocator cause established.'
    elif off.get('observed_outcome') == on.get('observed_outcome') == 'oom':
        label = 'phase_off_insufficient_to_restore_gui_outcome'
        conclusion = 'Both arms OOMed once: disabling the phase observer was insufficient to restore the successful GUI outcome; the broader isolated-replay mismatch remains.'
    elif result.get('both_successful'):
        label = 'both_replays_succeeded_single_observation'
        conclusion = 'Both arms succeeded once. Summary parity and phase completeness are reported separately; no equivalence or speedup is established.'
    else:
        label = 'other_observed_outcomes_inconclusive'
        conclusion = 'The preserved outcomes do not isolate phase instrumentation as the cause of the prior GUI/replay mismatch.'
    result.update(classification=label, conclusion=conclusion)


def file_evidence(probe, capture_dir, off_dir, on_dir, capture, host, cs, off_sup, on_sup):
    """Read bytes only. No runtime execution, network, imports, or result mutation."""
    failures, hashes = [], {}
    def check(ok, message):
        if not ok:
            failures.append(message)
    def record(path):
        path = Path(path)
        value = sha(path)
        hashes[str(path)] = value
        return value
    try:
        check(record(probe / 'SHA256SUMS') == MANIFEST_PIN, 'frozen probe manifest hash mismatch')
        entries = {}
        for line in (probe / 'SHA256SUMS').read_text().splitlines():
            pin, name = line.split('  ', 1)
            if not digest(pin) or Path(name).name != name or name in entries:
                raise ValueError('malformed probe manifest')
            entries[name] = pin
            check(record(probe / name) == pin, 'frozen probe bytes changed: ' + name)
        # Existing pinned replay executes validate-capture! before emitting ready fields.
        # Rehash actual transformed sources against independently derived fixed pins.
        config = obj(obj(cs.get('memory_profile_setup')).get('configuration'))
        root = Path(config['runtime_root']).resolve()
        manifest_path = root / 'openracket-replay-manifest.json'
        manifest = read(manifest_path)
        record(manifest_path)
        check(manifest.get('compiled') is True and manifest.get('compile_exit_code') == 0
              and manifest.get('expected_child_limit_bytes') == CAP, 'prepared source compilation/cap not proven')
        check(Path(manifest['diagnostic_runtime']).resolve() == root and manifest.get('racket') == cs['command'][0], 'prepared runtime identity mismatch')
        files = obj(manifest.get('files'))
        check(set(files) == set(SOURCES), 'prepared source set mismatch')
        for name, (stock, modified) in SOURCES.items():
            item = obj(files.get(name))
            path = Path(item['path'])
            check(root in path.resolve().parents and not path.is_symlink() and path.stat().st_nlink == 1, 'source not independently cloned: ' + name)
            check(item.get('stock_sha256') == stock and item.get('diagnostic_sha256') == modified
                  and record(path) == modified, 'actual source bytes mismatch: ' + name)
        context = obj(manifest.get('unmodified_context_sources'))
        check(set(context) == set(CONTEXT), 'context source set mismatch')
        for name, pin in CONTEXT.items():
            item = obj(context.get(name)); path = Path(item['path'])
            check(root in path.resolve().parents and not path.is_symlink() and path.stat().st_nlink == 1
                  and item.get('modified') is False and item.get('sha256') == pin and record(path) == pin,
                  'context source bytes mismatch: ' + name)
        helpers = obj(manifest.get('observer_files'))
        check(set(helpers) == {'phase-probe.rkt','support.rkt','replay.rkt','capture-host.rkt','memory-profile.rkt'}, 'observer helper set mismatch')
        for name, item in helpers.items():
            check(Path(item['path']).resolve() == (probe / name).resolve()
                  and item.get('sha256') == entries.get(name) and record(item['path']) == entries.get(name), 'observer source bytes mismatch: ' + name)
        check(cs.get('command') == [manifest['racket'], str(probe / 'capture-host.rkt')], 'capture did not use frozen host')
        launch = read(capture_dir / 'capture.launch.json')
        check(set(launch) == {'environment','cwd','snapshot_sha256','registry_sha256'}
              and set(obj(launch.get('environment'))) == ENV_KEYS
              and all(v is False or isinstance(v, str) for v in obj(launch.get('environment')).values()), 'capture launch context malformed')
        check(launch.get('snapshot_sha256') == capture.get('snapshot_sha256')
              and launch.get('registry_sha256') == capture.get('registry_sha256'), 'capture launch identity mismatch')
        record(capture_dir / 'capture.launch.json')
        check((capture_dir / 'capture.rktd').stat().st_size > 0, 'empty captured request')
        record(capture_dir / 'capture.rktd')
        for name, directory, sup in [('off',off_dir,off_sup), ('on',on_dir,on_sup)]:
            conf = obj(sup.get('config'))
            check(conf.get('capture') == str(capture_dir / 'capture.rktd') and conf.get('output') == str(directory), name + ': input/output path mismatch')
            check(sup.get('command') == [manifest['racket'],str(probe / 'replay.rkt')]
                  and sup.get('launch_context') == launch and sup.get('cwd') == launch.get('cwd'), name + ': frozen command/launch mismatch')
            check(obj(sup.get('driver_result')).get('exists') is True
                  and obj(sup.get('driver_result')).get('path') == str(directory / 'replay.json'), name + ': result path mismatch')
        memory = read(capture_dir / 'memory-profile.json')
        check(memory == config, 'raw memory-profile record differs from setup configuration')
        fixture = Path(host['fixture']); data = fixture.read_bytes(); record(fixture)
        check(hashlib.sha256(data).hexdigest() == cs.get('base_fixture_sha256')
              == '766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e'
              and hashlib.sha256(data[:524139] + b'x' + data[524139:]).hexdigest() == SNAPSHOT,
              'fixture/edited snapshot bytes mismatch')
    except (OSError, ValueError, TypeError, AttributeError, KeyError, IndexError) as error:
        failures.append('missing or malformed file/source evidence: ' + str(error))
    return failures, hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('probe','capture','off','on'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(argv)
    args.probe, args.capture, args.off, args.on = [p.resolve() for p in (args.probe,args.capture,args.off,args.on)]
    paths = [args.capture / x for x in ('capture-summary.json','capture-host.json','capture-supervisor.json')]
    paths += [d / x for d in (args.off,args.on) for x in ('replay.json','supervisor.json')]
    docs, failures, hashes = [], [], {}
    for path in paths:
        try:
            hashes[str(path)] = sha(path)
            docs.append(read(path))
        except (OSError, ValueError, TypeError) as error:
            docs.append({}); failures.append(str(path) + ': ' + str(error))
    try:
        result = assess(*docs)
        extra, source_hashes = file_evidence(args.probe,args.capture,args.off,args.on,*docs[:3],docs[4],docs[6])
        hashes.update(source_hashes); failures += extra
        result['observation_failures'] += failures
        result['observation_valid'] = not result['observation_failures']
        classify(result)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError) as error:
        result = {'schema_version':1, 'observation_valid':False, 'classification':'invalid_or_incomplete_control_evidence',
                  'observation_failures': failures + ['malformed evidence: ' + str(error)],
                  'recorded_evidence': docs, 'scope':'Malformed evidence retained without inference.'}
    result['input_sha256'] = hashes
    result['frozen_probe_manifest_sha256'] = MANIFEST_PIN
    print(json.dumps(result, indent=2, allow_nan=False))
    # Exit 0 means valid observation only; OOM is never relabeled replay success.
    return 0 if result['observation_valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
