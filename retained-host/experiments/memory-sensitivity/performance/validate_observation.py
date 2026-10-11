"""Strict read-only validation of the compact observer in one fresh GUI trial."""
import hashlib
import json
import math
from pathlib import Path

STOCK_PREFAB = '#s(prefab-module-settings #() (default) #t #t none #t)'

def finite_ms(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def validate(report, directory, fixture, arm, expected_xref_hash, racket, *, expected_limit_bytes=134217728):
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    check(arm == 'stock', 'Only pristine stock xref is allowed')
    check(type(expected_limit_bytes) is int and expected_limit_bytes in (134217728, 268435456, 536870912),
          'Unsupported expected memory limit')
    check(report.get('expected_memory_limit_bytes') == expected_limit_bytes, 'GUI requested limit differs')
    setup = report.get('memory_profile_setup', {})
    configuration = report.get('memory_limit_configuration', {})
    check(setup.get('verified') is True and setup.get('configuration') == configuration, 'Pre-timing setup missing')
    check(configuration.get('expected_limit_bytes') == configuration.get('selected_limit_bytes') ==
          configuration.get('persisted_limit_bytes') == expected_limit_bytes and
          configuration.get('only_expected_preference_changed') is True, 'One-key memory setup differs')
    worker = None
    path = Path(directory) / 'worker-init.json'
    try:
        if path.is_symlink():
            raise ValueError('Worker evidence is a symlink')
        worker = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        errors.append('Worker evidence unavailable: ' + str(error))
    if isinstance(worker, dict):
        check(worker.get('event') == 'worker-init-after-handler-imports', 'Wrong activation seam')
        check(worker.get('worker_context') is True and worker.get('xref_already_instantiated') is True,
              'Actual worker xref was not proven already instantiated')
        check(worker.get('racket_version') == '9.3', 'Worker is not Racket9.3')
        check(worker.get('child_memory_limit') == expected_limit_bytes, 'Worker memory limit changed')
        check(worker.get('memory_accounting_available') is True, 'Worker memory accounting is unavailable')
        check(worker.get('xref_sha256') == expected_xref_hash, 'Worker xref source hash mismatch')
        resolved_source = Path(worker.get('xref_path', '')).resolve()
        root = Path(racket).resolve().parents[1]
        check(resolved_source.is_relative_to(root), 'Loaded xref is outside the supplied runtime')
        registry = worker.get('actual_handler_registry', [])
        check(isinstance(registry, list) and len(registry) == 2 and
              [(r.get('export'), r.get('monitor')) for r in registry] == [('go', False), ('monitor', True)],
              'Actual ordered stock handler registry differs')
        for handler in registry:
            module = Path(handler.get('module', '')).resolve()
            check(module.is_relative_to(root) and module.name == 'online-comp.rkt',
                  'Actual handler module is not the known clone-local stock handler')
        if arm == 'candidate':
            check(worker.get('xref_export_status') == 'boolean' and
                  worker.get('xref_reply_cell_enabled') is True and worker.get('xref_flag') == '1',
                  'Actual candidate worker flag/export is not enabled')
        else:
            check(worker.get('xref_export_status') == 'missing' and
                  worker.get('xref_reply_cell_enabled') is None and worker.get('xref_flag') is None,
                  'Actual stock worker is not pristine xref with flag absent')
    elif worker is not None:
        errors.append('Worker evidence is not an object')
    overhead = None
    try:
        overhead_path = Path(directory) / 'worker-init-overhead.json'
        if overhead_path.is_symlink():
            raise ValueError('Worker overhead evidence is a symlink')
        overhead = json.loads(overhead_path.read_text())
        check(isinstance(overhead, dict) and overhead.get('event') == 'worker-observer-one-shot-cost',
              'Worker overhead evidence has the wrong schema')
        if isinstance(overhead, dict):
            check(all(finite_ms(overhead.get(key)) for key in
                      ('primary_write_and_close_ms', 'observer_through_primary_write_ms')) and
                  overhead.get('timing_file_write_measured') is False and
                  overhead.get('indirect_gc_and_scheduling_effects_measured') is False,
                  'Worker overhead evidence is incomplete')
    except (OSError, ValueError) as error:
        errors.append('Worker overhead evidence unavailable: ' + str(error))
    original = Path(fixture['path']).read_bytes()
    position = fixture['edit_position']
    expected = original[:position] + b'x' + b'a' * 80 + original[position:]
    digest = hashlib.sha256(expected).hexdigest()
    summary = report.get('online_expansion_observer')
    outcome = report.get('online_expansion_outcome')
    if not isinstance(summary, dict):
        errors.append('No compact GUI observer summary')
    else:
        check(summary.get('enabled') is True and summary.get('complete_observation') is True,
              'Compact observer is disabled/incomplete')
        check(summary.get('dropped_requests') == 0 and summary.get('observer_error_count') == 0,
              'Compact observer dropped records or failed')
        check(summary.get('generation') == 1 and summary.get('expected_sha256') == digest,
              'Registered final snapshot does not match fixture edits')
        check(summary.get('expected_characters') == len(expected), 'Final character count mismatch')
        records = summary.get('records', [])
        check(isinstance(records, list) and len(records) == summary.get('request_count'),
              'Request record count is incomplete')
        if isinstance(outcome, dict) and isinstance(records, list):
            final = [r for r in records if r.get('final_match') is True]
            # The independent status channel may arrive later. Compare the
            # outcome identity and callback, not an accidental total ordering.
            keys = ('request_id', 'generation', 'snapshot_sha256', 'terminal',
                    'callback_current', 'callback_delivered_ms')
            check(bool(final) and all(outcome.get(k) == final[-1].get(k) for k in keys),
                  'Outcome is not the latest matched final request')
    if not isinstance(outcome, dict):
        errors.append('No final-source terminal callback outcome')
        tool_succeeded = False
        tool_category = 'missing-outcome'
    else:
        check(outcome.get('snapshot_sha256') == digest and outcome.get('generation') == 1,
              'Terminal snapshot/generation mismatch')
        check(outcome.get('callback_current') is True and
              finite_ms(outcome.get('callback_delivered_ms')),
              'Current final callback has not completed')
        terminal = outcome.get('terminal', {})
        check(isinstance(terminal, dict) and terminal.get('tag') in
              ('handler-results', 'abnormal-termination', 'access-violation',
               'reader-in-defs-error', 'exn:variable', 'exn'), 'Unknown/missing actual terminal')
        check(outcome.get('actual_prefab') == STOCK_PREFAB and
              outcome.get('actual_prefab_truncated') is False, 'Actual online settings changed or truncated')
        counts = [outcome.get(key) for key in ('monitor_messages', 'monitor_string_errors',
                                              'monitor_pair_messages', 'monitor_empty_messages',
                                              'monitor_other_messages')]
        known_counts = all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in counts)
        check(known_counts and counts[0] == sum(counts[1:]), 'Monitor outcome metadata is incomplete')
        tag = terminal.get('tag') if isinstance(terminal, dict) else 'missing-terminal'
        clean_monitor = known_counts and counts[0] > 0 and counts[1] == counts[4] == 0
        tool_succeeded = tag == 'handler-results' and clean_monitor
        tool_category = (tag if tag != 'handler-results' or clean_monitor
                         else 'handler-results-with-incomplete-or-failed-monitor')
    check(report.get('exact_resulting_source_verified') is True, 'Actual editor source not verified')
    check(report.get('post_typing_lexer_settle', {}).get('complete') is True, 'Lexer is incomplete')
    check(report.get('online_terminal_wait', {}).get('complete') is True, 'Tool outcome wait incomplete')
    settings = report.get('selected_language_settings', {})
    check(settings.get('status') == 'complete' and settings.get('errors') == {} and
          settings.get('effective_annotations') == 'debug', 'Pending-next-Run settings/instrumentation unavailable or changed')
    preferences = report.get('preserved_settings', {})
    check(preferences.get('drracket:child-only-memory-limit') == str(expected_limit_bytes) and
          preferences.get('framework:coloring-active') == '#t' and
          preferences.get('drracket:online-compilation-default-on') == '#t' and
          'UNAVAILABLE' not in preferences.values(), 'Stock preferences unavailable or changed')
    for key in ('scan_activation', 'budget_activation'):
        activation = report.get(key, {})
        check(activation.get('status') == 'verified' and activation.get('expected') == 'stock',
              'Another experiment is active or unverified: ' + key)
    check(len(report.get('initial_coloring_key_samples', [])) == 80, 'Incomplete paced typing workload')
    return {'verified': not errors, 'errors': errors, 'expected_snapshot_sha256': digest,
            'actual_worker': worker, 'worker_observer_overhead': overhead,
            'tool_succeeded': tool_succeeded, 'tool_outcome_category': tool_category,
            'contention_observed': report.get('keys_starting_with_lexer_invalid', 0) > 0,
            'scope': 'Observer correctness, not a claim that the actual tool outcome succeeded'}
