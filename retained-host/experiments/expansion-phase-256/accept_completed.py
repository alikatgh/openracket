#!/usr/bin/env python3
"""Fail closed unless native cap256 capture and both phase replays completed cleanly."""
import argparse
import json
import math
from pathlib import Path

CAP = 268435456
XREF_PIN = 'acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7'
REQUIRED_PHASES = {
    'worker-start', 'monitor-start', 'worker-phase-09', 'worker-phase-10',
    'worker-phase-11', 'worker-phase-12', 'worker-phase-13',
    'monitor-build-trace-start', 'monitor-build-trace-complete/send-back-start',
    'monitor-acknowledge-go', 'go-send-expanded', 'go-wait-for-monitor',
}


def assess(capture, capture_host, capture_supervisor, replay, supervisor):
    failures = []
    def require(ok, reason):
        if not ok:
            failures.append(reason)
    def monitor(row, label):
        ev = row.get('monitor_evidence', {})
        require(ev.get('check_syntax_monitor_registry_entries') == 1, label + ': actual CheckSyntax monitor absent/ambiguous')
        for key in ('messages', 'trace_batches', 'trace_entries', 'rename_capability_rows'):
            require(type(ev.get(key)) is int and ev[key] > 0, label + ': missing clean monitor ' + key)
        for key in ('error_messages', 'invalid_payloads'):
            require(type(ev.get(key)) is int and ev[key] == 0, label + ': monitor errors or unclassified payloads')
    setup = capture_supervisor.get('memory_profile_setup', {})
    require(setup.get('verified') is True, 'headless one-key profile setup not verified')
    require(capture_supervisor.get('expected_memory_limit_bytes') == CAP, 'capture supervisor cap mismatch')
    require(capture_supervisor.get('gui_started') is True and capture_supervisor.get('exit_code') == 0
            and capture_supervisor.get('timeout') is False
            and capture_supervisor.get('cleanup', {}).get('complete') is True, 'capture process/cleanup failed')
    require(capture_host.get('status') == 'terminal_captured', 'capture host did not observe terminal')
    require(capture_host.get('preserved_preferences') ==
            {'child_limit_bytes': CAP, 'online_compilation': True, 'coloring': True}, 'effective GUI preferences mismatch')
    require(capture.get('status') == 'terminal_observed' and capture.get('actual_child_limit_bytes') == CAP,
            'capture terminal or actual cap missing')
    require(capture.get('terminal', {}).get('tag') == 'handler-results', 'capture did not complete with handler-results')
    monitor(capture, 'capture')
    require(supervisor.get('status') == 'ok' and supervisor.get('cleanup', {}).get('complete') is True,
            'replay supervisor/cleanup failed')
    require(supervisor.get('hard_wall_budget_seconds') == 157.0, 'replay deadline changed')
    require(replay.get('status') == 'complete' and replay.get('cleanup', {}).get('accepted') is True,
            'replay protocol/cleanup failed')
    require(replay.get('actual_worker_child_limit_bytes') == CAP, 'actual ready worker cap mismatch')
    require(replay.get('actual_worker_memory_accounting_available') is True, 'worker memory accounting unavailable')
    require(replay.get('phase_probe_enabled') is True, 'phase probe disabled')
    for key in ('snapshot_sha256', 'registry_sha256'):
        require(bool(capture.get(key)) and capture.get(key) == replay.get(key), key + ' differs from capture')
    trials = replay.get('trials', [])
    require(len(trials) == 2, 'expected exactly two replay trials')
    for i, row in enumerate(trials, 1):
        label = 'trial ' + str(i)
        require(row.get('trial') == i and row.get('outcome') == 'handler-results'
                and row.get('terminal', {}).get('tag') == 'handler-results', label + ': no completed handler-results')
        require(row.get('terminal_summary_matches_integrated_capture') is True, label + ': terminal summary differs')
        monitor(row, label)
        for key in ('trace_entries', 'rename_capability_rows'):
            require(row.get('monitor_evidence', {}).get(key) == capture.get('monitor_evidence', {}).get(key),
                    label + ': monitor scalar count differs from capture: ' + key)
        require(type(row.get('retained_place_channels')) is int and row['retained_place_channels'] > 0,
                label + ': actual rename endpoint not retained')
        phase = row.get('phase_probe', {})
        if not isinstance(phase, dict):
            phase = {}
        require(phase.get('trial') == i and phase.get('job_generation') == i and phase.get('active') is False,
                label + ': phase trial/generation/end mismatch')
        for key in ('phase_points_dropped', 'sample_ticks_dropped', 'input_events_dropped', 'stale_events_discarded'):
            require(type(phase.get(key)) is int and phase[key] == 0, label + ': incomplete phase/sample delivery: ' + key)
        points = phase.get('phase_points', [])
        require(REQUIRED_PHASES <= {p.get('phase') for p in points}, label + ': missing completed request phase coverage')
        require(all(p.get('trial') == i and p.get('job_generation') == i for p in points), label + ': stale phase generation')
        require(all(type(p.get('source_metrics', {}).get('monotonic_ms')) in (float, int)
                    and math.isfinite(p['source_metrics']['monotonic_ms'])
                    and p['source_metrics']['monotonic_ms'] >= 0 for p in points),
                label + ': invalid producer timestamp')
        source_times = {p.get('phase'): p.get('source_metrics', {}).get('monotonic_ms') for p in points}
        for seq in [('worker-phase-09', 'worker-phase-10', 'worker-phase-11', 'worker-phase-12', 'worker-phase-13'),
                    ('monitor-build-trace-start', 'monitor-build-trace-complete/send-back-start', 'monitor-acknowledge-go')]:
            times = [source_times.get(p) for p in seq]
            require(all(type(t) in (float, int) and math.isfinite(t) and t >= 0 for t in times)
                    and all(a <= b for a, b in zip(times, times[1:])),
                    label + ': missing/nonmonotonic producer phase times')
        ev = phase.get('attribution_evidence', {})
        require(ev.get('status') == 'coarse_thread_context_available', label + ': actual-thread context incomplete')
        for key in ('working_thread_registered', 'monitor_thread_registered', 'xref_service_thread_registered',
                    'usable_monitor_frames', 'usable_xref_frames'):
            require(ev.get(key) is True, label + ': missing ' + key)
        require(phase.get('xref_service_registration', {}).get('status') == 'registered_existing_service_thread',
                label + ': existing xref service not proven')
        require(phase.get('xref_service_registration', {}).get('source_sha256') == XREF_PIN,
                label + ': existing xref source pin missing/mismatched')
        require(phase.get('stock_logger_subscription') is False, label + ': stock logger subscription changed')
        if i == 2:
            require(type(row.get('prior_place_channels_retained_before_request')) is int and row['prior_place_channels_retained_before_request'] > 0,
                    'prior rename endpoints not retained through replacement')
            require(row.get('prior_terminal_retained_before_request') is True, 'prior real terminal not retained through replacement')
    require(type(replay.get('last_place_channels_retained_until_cleanup')) is int and replay['last_place_channels_retained_until_cleanup'] > 0,
            'last rename endpoints not retained through cleanup')
    require(replay.get('last_terminal_retained_until_cleanup') is True, 'last real terminal not retained through cleanup')
    return {'accepted': not failures, 'classification': 'completed_request_phase_evidence' if not failures else 'diagnostic_incomplete_or_failed',
            'failures': failures,
            'scope': 'Two completed cap256 requests with clean monitor schema, terminal summaries, phase coverage and approximate thread context. No full payload equality, allocation ownership, CPU attribution or speedup claim. The shared xref service is observed during each request, not proven to execute that request.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--results', required=True, type=Path)
    args = parser.parse_args()
    def read(base, name):
        return json.loads((base / name).read_text())
    try:
        report = assess(read(args.capture, 'capture-summary.json'), read(args.capture, 'capture-host.json'),
                        read(args.capture, 'capture-supervisor.json'), read(args.results, 'replay.json'),
                        read(args.results, 'supervisor.json'))
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        report = {'accepted': False, 'classification': 'diagnostic_incomplete_or_failed',
                  'failures': [f'Missing or malformed native evidence: {error}']}
    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['accepted'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
