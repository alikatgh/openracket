"""Fail-closed scalar accounting for the bounded genuine-GUI application pair."""
import math

TAGS = tuple('syncheck:' + name for name in (
    'add-arrow/name-dup/pxpy', 'add-tail-arrow', 'add-mouse-over-status', 'add-text-type',
    'add-background-color', 'add-jump-to-definition/phase-level+space', 'add-require-open-menu',
    'add-docs-menu', 'add-definition-target/phase-level+space', 'unused-binder', 'add-id-set',
    'add-prefixed-require-reference', 'add-unused-require'))
FINALS = ('update-blue-boxes', 'update-drawn-arrows', 'remove-bkg-running-color',
          'set-syncheck-running-mode')

def require(value, reason):
    if not value:
        raise ValueError('Application profile: ' + reason)

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def count(value):
    return type(value) is int and value >= 0

def accumulator(row, timed, label):
    require(type(row) is dict and count(row.get('count')), 'invalid ' + label + ' count')
    if timed:
        require(number(row.get('wall_ms')) and number(row.get('max_wall_ms')),
                'nonfinite or invalid ' + label + ' timing')
        total, maximum, n = row['wall_ms'], row['max_wall_ms'], row['count']
        tolerance = 1e-5 * max(1.0, total)
        require(maximum <= total + tolerance and total <= n * maximum + tolerance,
                'inconsistent ' + label + ' sum/maximum/count')
        if n == 0:
            require(total == maximum == 0, 'nonzero empty ' + label)
    else:
        require(row.get('wall_ms') is None and row.get('max_wall_ms') is None,
                'control unexpectedly timed ' + label)
    return row

def validate_application(data, arm, common, host):
    timed = arm == 'observed'
    require(type(data) is dict and type(data.get('schema_version')) is int and
            data['schema_version'] == 1 and data.get('kind') == 'genuine-gui-annotation-application',
            'wrong schema/kind')
    require(data.get('probe_enabled') is timed and data.get('common_batch_counts') is True and data.get('snapshot_quiescent') is True,
            'wrong probe activation, nonquiescent snapshot or missing common slice counters')
    require(all(type(data.get(k)) is int and data[k] == 0 for k in
                ('dropped_records', 'observer_failures')) and
            type(data.get('selected_count')) is int and data['selected_count'] == 1,
            'errors, overflow or ambiguous selected application')
    records = data.get('records')
    require(type(records) is list and len(records) == 1 and type(records[0]) is dict,
            'exactly one record required')
    r = records[0]
    require(type(r.get('request_id')) is int and r['request_id'] == common['request_id'] and
            type(r.get('application_generation')) is int and
            r['application_generation'] == common['application_generation'] == 1,
            'request/generation differs from actual common token')
    require(r.get('completed') is True and r.get('cancelled') is False and
            common['application_current'] is True and common['application_cancelled'] is False,
            'cancelled, stale or incomplete application')
    require(all(type(r.get(k)) is int and r[k] == 0 for k in
                ('errors', 'unknown_tags', 'reentrant_entries', 'stale_events',
                 'unmatched_events', 'open_entry_depth')) and
            all(r.get(k) is False for k in ('open_final', 'active_batch', 'queued_wait')),
            'unknown, reentrant, stale, unmatched or unclosed work')
    require(all(count(r.get(k)) for k in ('entries_started', 'entries_completed',
                                        'yield_count', 'resume_count')), 'invalid entry/slice counters')
    active = accumulator(r.get('batch_active'), timed, 'batch active')
    wait = accumulator(r.get('requeue_wait'), timed, 'requeue wait')
    require(active['count'] == r['yield_count'] + 1 and
            wait['count'] == r['yield_count'] == r['resume_count'],
            'batch/yield/resume/wait count mismatch')
    tags, finals = r.get('tag_buckets'), r.get('final_updates')
    if not timed:
        require(tags == finals == [] and r['entries_started'] == r['entries_completed'] == 0 and
                r.get('first_batch_start_ms') is None and r.get('last_batch_end_ms') is None,
                'control unexpectedly collected per-entry/final/timing data')
        return dict(probe_enabled=False, batch_count=active['count'], yield_count=r['yield_count'],
                    scope='Common-observer plus identical scalar slice counters; all application timings OFF')
    require(type(tags) is list and len(tags) == 13 and all(type(row) is dict for row in tags) and
            tuple(row.get('tag') for row in tags) == TAGS, 'missing, duplicated, reordered or unknown tag rows')
    require(type(finals) is list and len(finals) == 4 and all(type(row) is dict for row in finals) and
            tuple(row.get('operation') for row in finals) == FINALS, 'missing or altered final-call rows')
    for row in tags:
        accumulator(row, True, row['tag'])
    for row in finals:
        accumulator(row, True, row['operation'])
        require(row['count'] == 1, 'final call missing or repeated')
    entries = sum(row['count'] for row in tags)
    require(entries == r['entries_started'] == r['entries_completed'] ==
            common['monitor_evidence']['trace_entries'], 'fixed13 counts do not reconcile full actual trace')
    rename_rows = tags[0]['count'] + tags[10]['count']
    require(rename_rows == common['monitor_evidence']['rename_capability_rows'],
            'arrow plus id-set counts do not reconcile independent actual rename-capability rows')
    first, last = r.get('first_batch_start_ms'), r.get('last_batch_end_ms')
    require(number(first) and number(last) and first <= last, 'invalid batch boundary timestamps')
    common_points = common['gui_points']
    require(common_points['application-enter']['monotonic_ms'] <= first and
            common_points['application-complete']['monotonic_ms'] <= last <
            host['post_edit_deadline_monotonic_ms'], 'batch boundaries disagree with common lifecycle/deadline')
    active_ms, wait_ms = active['wall_ms'], wait['wall_ms']
    span = last - first
    tolerance = 1e-5 * max(1.0, span)
    require(abs(active_ms + wait_ms - span) <= tolerance,
            'active plus nonoverlapping queued wait does not reconcile batch span')
    calls_ms = sum(row['wall_ms'] for row in tags)
    finals_ms = sum(row['wall_ms'] for row in finals)
    require(calls_ms + finals_ms <= active_ms + tolerance,
            'measured call/final wall exceeds whole active batch wall')
    return dict(probe_enabled=True, trace_entries=entries, rename_capability_rows=rename_rows, batch_count=active['count'],
                yield_count=r['yield_count'], batch_active=active, requeue_wait=wait,
                batch_span_wall_ms=span, measured_entry_call_wall_ms=calls_ms,
                synchronous_final_calls_wall_ms=finals_ms,
                other_batch_wall_ms=max(0.0, active_ms - calls_ms - finals_ms),
                tag_buckets=tags, final_updates=finals,
                scope='Inclusive observed wall, not exclusive CPU; residual includes loop, observer and scheduling work. Deferred GUI work and painting may remain.')
