"""Fail-closed evidence checks for sparse pending-continuation observations."""
import math

MAXIMUM_BYTES = 20 * 1024 * 1024
COUNTS = ('attempts', 'stored_samples', 'race_discarded', 'stop_discarded',
          'invalid_token_discarded', 'attempt_errors_discarded', 'capture_errors', 'absent_handlers',
          'collected_handlers', 'dead_handlers', 'invalid_handlers',
          'died_during_capture', 'missing_frames', 'frames_truncated',
          'text_fields_truncated', 'usable_source_samples', 'cadence_ticks',
          'idle_ticks', 'early_wakes', 'missed_cadence_ticks', 'sampler_errors')
TIMES = ('scheduling_delay_ms', 'max_scheduling_delay_ms',
         'capture_duration_ms', 'max_capture_duration_ms')
BAD = ('invalid_token_discarded', 'attempt_errors_discarded', 'capture_errors', 'absent_handlers',
       'collected_handlers', 'dead_handlers', 'invalid_handlers',
       'died_during_capture', 'sampler_errors')


def require(value, reason):
    if not value:
        raise ValueError('Queued sampler: ' + reason)


def count(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def near(a, b):
    return abs(a - b) <= 1e-5 * max(1.0, abs(a), abs(b))


def text(value):
    return value is None or (type(value) is str and len(value) <= 240)


def validate_sampler(data, arm, common, host, application):
    enabled = arm == 'observed'
    require(type(data) is dict and type(data.get('schema_version')) is int and
            data['schema_version'] == 1 and
            data.get('kind') == 'genuine-gui-pending-continuation-samples', 'wrong schema/kind')
    require(data.get('enabled') is enabled and data.get('snapshot_quiescent') is True and
            data.get('capped') is False and data.get('incomplete') is False and
            data.get('stock_logger_subscription') is False, 'activation/quiescence/completeness failed')
    for key, value in (('sample_period_ms', 100), ('attempt_cap', 1024), ('frame_cap', 8), ('text_cap', 240)):
        require(number(data.get(key)) and data[key] == value and
                (key == 'sample_period_ms' or type(data[key]) is int), 'wrong fixed bound: ' + key)
    require(all(count(data.get(k)) for k in COUNTS) and all(number(data.get(k)) for k in TIMES),
            'invalid counters/timing')
    require(all(data[k] == 0 for k in BAD) and data.get('sampler_error') is None,
            'unsafe handler, invalid token or sampler/capture errors')
    rows = data.get('samples')
    require(type(rows) is list and len(rows) == data['stored_samples'] <= data['attempts'] <= 1024,
            'sample/attempt count or bound differs')
    require(data['attempts'] == data['stored_samples'] + data['race_discarded'] +
            data['stop_discarded'] + data['invalid_token_discarded'] + data['attempt_errors_discarded'] and
            data['cadence_ticks'] == data['attempts'] + data['idle_ticks'],
            'attempt/discard/cadence accounting differs')
    require(data['max_scheduling_delay_ms'] <= data['scheduling_delay_ms'] and
            data['max_capture_duration_ms'] <= data['capture_duration_ms'], 'invalid aggregate maximum')
    require(host.get('gui_handler_verified') is True and host.get('sampler_joined') is True and
            host.get('post_join_current') is True, 'actual handler or post-join currentness proof missing')
    lifecycle = [host.get(k) for k in ('sampler_stop_requested_monotonic_ms',
                 'sampler_joined_monotonic_ms', 'post_join_verified_monotonic_ms')]
    require(all(number(x) for x in lifecycle) and lifecycle == sorted(lifecycle),
            'invalid stop/join/reverification timestamps')
    stop, joined, verified = lifecycle
    points = common['gui_points']
    require(stop >= max(p['monotonic_ms'] for p in points.values()) and
            stop >= host['first_final_lexer_valid_observed_monotonic_ms'] and
            verified < host['post_edit_deadline_monotonic_ms'], 'original endpoint/deadline bound differs')
    if not enabled:
        require(data.get('termination') == 'disabled' and data.get('stopped') is False and
                data.get('started_monotonic_ms') is None and data.get('finished_monotonic_ms') is None and
                all(data[k] == 0 for k in COUNTS + TIMES) and rows == [],
                'control unexpectedly sampled or has altered disabled lifecycle')
        return dict(enabled=False, samples=0, joined=True, post_join_current=True,
                    scope='Sampler disabled; common GUI lifecycle verification retained')
    require(data.get('termination') == 'stopped' and data.get('stopped') is True,
            'sampler did not stop cooperatively')
    started, finished = data.get('started_monotonic_ms'), data.get('finished_monotonic_ms')
    require(number(started) and number(finished) and
            started <= points['request-observed']['monotonic_ms'] and
            stop <= finished <= joined, 'sampler start/finish differs from real lifecycle')
    require(data['usable_source_samples'] > 0 and rows, 'no useful pending-handler stack evidence')
    app = application['records'][0]
    previous_finished = started
    previous_ordinal = 0
    wait_origins = {}
    wait_lower_bounds = {}
    totals = dict(capture=0.0, delay=0.0, missed=0, missing=0, truncated=0, text_truncated=0, useful=0)
    for row in rows:
        require(type(row) is dict and count(row.get('request_id'), 1) and
                count(row.get('application_generation'), 1) and count(row.get('wait_ordinal'), 1) and
                row['request_id'] == common['request_id'] and
                row['application_generation'] == common['application_generation'] and
                previous_ordinal <= row['wait_ordinal'] <= app['yield_count'], 'stale/malformed pending token')
        fields = ('queued_monotonic_ms', 'planned_monotonic_ms', 'actual_monotonic_ms',
                  'capture_started_monotonic_ms', 'capture_finished_monotonic_ms',
                  'capture_duration_ms', 'scheduling_delay_ms')
        require(all(number(row.get(k)) for k in fields) and
                all(count(row.get(k)) for k in ('missed_before_capture_ticks', 'missed_cadence_ticks')),
                'invalid sample timestamps/cadence')
        queued, planned, actual, begin, end = (row[k] for k in fields[:5])
        require(started + 100 <= planned <= actual <= begin <= end <= finished and
                previous_finished <= actual and app['first_batch_start_ms'] <= queued <= begin and
                end <= points['application-complete']['monotonic_ms'], 'sample outside live application interval')
        require(near(row['capture_duration_ms'], end - begin) and
                near(row['scheduling_delay_ms'], actual - planned) and
                row['missed_before_capture_ticks'] == math.floor(max(0, actual - planned) / 100) and
                row['missed_cadence_ticks'] == math.floor(max(0, end - planned) / 100),
                'sample duration/delay/missed cadence arithmetic differs')
        if row['wait_ordinal'] in wait_origins:
            require(wait_origins[row['wait_ordinal']] == queued, 'same wait ordinal has different origin')
        else:
            require(not wait_origins or queued >= max(wait_origins.values()), 'wait origins out of order')
            wait_origins[row['wait_ordinal']] = queued
        previous_ordinal, previous_finished = row['wait_ordinal'], end
        age = end - queued
        require(age <= app['requeue_wait']['max_wall_ms'] + 1e-5 * max(1, app['requeue_wait']['max_wall_ms']),
                'sampled pending age exceeds the actual maximum requeue wait')
        wait_lower_bounds[row['wait_ordinal']] = max(wait_lower_bounds.get(row['wait_ordinal'], 0), age)
        require(row.get('state') == 'live_at_sample' and row.get('capture_performed') is True and
                row.get('error') is None and row.get('error_truncated') is False,
                'stored sample does not prove a live actual handler')
        frames = row.get('frames')
        require(type(frames) is list and len(frames) <= 8 and type(row.get('frames_truncated')) is bool and
                (not row['frames_truncated'] or len(frames) == 8), 'unbounded or malformed frame list')
        require(all(count(row.get(k)) for k in ('text_fields_truncated', 'missing_frame_sources',
                                               'usable_source_frames')), 'invalid frame counters')
        truncations = useful = 0
        for frame in frames:
            require(type(frame) is dict and text(frame.get('name')) and text(frame.get('source')) and
                    type(frame.get('name_truncated')) is bool and type(frame.get('source_truncated')) is bool and
                    frame.get('source_kind') in ('path', 'string', 'symbol', 'missing', 'unsupported'),
                    'invalid or oversized rendered frame')
            for field in ('name', 'source'):
                if frame[field + '_truncated']:
                    require(type(frame[field]) is str and len(frame[field]) == 240, 'truncation witness differs')
                    truncations += 1
            require((frame['source'] is None) == (frame['source_kind'] in ('missing', 'unsupported')),
                    'source kind/text differs')
            for field, minimum in (('line', 1), ('column', 0), ('position', 1)):
                require(field in frame and (frame[field] is None or count(frame[field], minimum)),
                        'invalid source coordinate')
            useful += int(type(frame['source']) is str and len(frame['source']) > 0)
        require(row['text_fields_truncated'] == truncations and row['usable_source_frames'] == useful and
                row['missing_frame_sources'] == len(frames) - useful, 'rendered frame counter mismatch')
        totals['capture'] += row['capture_duration_ms']
        totals['delay'] += row['scheduling_delay_ms']
        totals['missed'] += row['missed_cadence_ticks']
        totals['missing'] += not frames
        totals['truncated'] += row['frames_truncated']
        totals['text_truncated'] += truncations
        totals['useful'] += useful > 0
        require(row['capture_duration_ms'] <= data['max_capture_duration_ms'] + 1e-6 and
                row['scheduling_delay_ms'] <= data['max_scheduling_delay_ms'] + 1e-6,
                'stored sample exceeds aggregate maximum')
    require(data['usable_source_samples'] == totals['useful'] and
            totals['capture'] <= data['capture_duration_ms'] + 1e-5 * max(1, data['capture_duration_ms']) and
            totals['delay'] <= data['scheduling_delay_ms'] + 1e-5 * max(1, data['scheduling_delay_ms']) and
            totals['missed'] <= data['missed_cadence_ticks'], 'aggregate capture/cadence totals do not cover rows')
    require(sum(wait_lower_bounds.values()) <= app['requeue_wait']['wall_ms'] +
            1e-5 * max(1, app['requeue_wait']['wall_ms']),
            'sampled distinct-wait lower bounds exceed total actual requeue wait')
    require(totals['missing'] <= data['missing_frames'] <= data['attempts'] and
            totals['truncated'] <= data['frames_truncated'] <= data['attempts'] and
            totals['text_truncated'] <= data['text_fields_truncated'] <= data['attempts'] * 16,
            'aggregate discarded/stored frame counts differ')
    return dict(enabled=True, samples=len(rows), usable_source_samples=data['usable_source_samples'],
                attempts=data['attempts'], race_discarded=data['race_discarded'], stop_discarded=data['stop_discarded'],
                sampled_waits=len(wait_origins), cadence_ticks=data['cadence_ticks'],
                sampled_distinct_wait_lower_bound_ms=sum(wait_lower_bounds.values()),
                missed_cadence_ticks=data['missed_cadence_ticks'],
                capture_duration_ms=data['capture_duration_ms'], max_capture_duration_ms=data['max_capture_duration_ms'],
                scheduling_delay_ms=data['scheduling_delay_ms'], max_scheduling_delay_ms=data['max_scheduling_delay_ms'],
                frames_truncated=data['frames_truncated'], text_fields_truncated=data['text_fields_truncated'],
                missing_frames=data['missing_frames'], joined=True, post_join_current=True,
                scope='Sparse live-handler frames bracketed by one immutable pending token; no full gap, CPU or allocation ownership')
