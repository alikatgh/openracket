#!/usr/bin/env python3
"""Single-mode native benchmark supervisor. No installs, patching, or preferences edits."""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import time
from fixtures import write_fixtures

ROOT = Path(__file__).resolve().parent

def quantiles(values):
    values = sorted(values)
    if not values:
        return {'n': 0}
    def percentile(p):
        return values[max(0, math.ceil(p * len(values)) - 1)]
    return {'n': len(values), 'median': statistics.median(values),
            'p95': percentile(.95), 'p99': percentile(.99), 'max': values[-1]}

def summarize(report):
    out = {key: report[key] for key in (
        'mode', 'status', 'error', 'fresh_process_gui_startup_ms', 'first_open',
        'first_jump', 'first_edit', 'initial_lexer_settle', 'final_lexer_settle',
        'preserved_settings', 'selected_language_settings', 'scan_activation', 'loaded_characters', 'memory_before_open',
        'initial_open_to_lexer_observation_ms', 'warm_input_phase_ms',
        'memory_after_initial_settle', 'memory_after_warm_input',
        'memory_after_workload', 'memory_after_explicit_gc') if key in report}
    for key in ('warm_editor_key_samples', 'warm_jump_samples'):
        out[key] = {metric: quantiles([row[metric] for row in report.get(key, [])])
                    for metric in ('command_ms', 'command_plus_low_priority_fence_ms')}
    samples = report.get('heartbeat_samples', [])
    out['heartbeat_by_phase'] = {
        phase: {metric: quantiles([row[metric] for row in samples if row['phase'] == phase])
                for metric in ('dispatch_ms', 'callback_gap_ms')}
        for phase in sorted({row['phase'] for row in samples})}
    return out

def native_rss(text, system):
    if system == 'Darwin':
        match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', text, re.M)
        return int(match[1]) if match else None
    match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', text)
    return int(match[1]) * 1024 if match else None

def live_group_members(pgid):
    """Read native process state; zombies cannot run or retain GUI work."""
    result = subprocess.run(['ps', '-axo', 'pid=,pgid=,stat=,uid='],
                            text=True, capture_output=True, check=True, timeout=3)
    members = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) != 4:
            continue
        pid, group, state, uid = columns
        if int(group) == pgid and not state.startswith('Z'):
            members.append({'pid': int(pid), 'state': state, 'uid': int(uid)})
    return members

def signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS can report EPERM for an already-exited group. Only treat that as
        # complete after independently observing no runnable group members.
        if not live_group_members(pgid):
            return False
        raise

def terminate_group(process):
    signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        signal_group(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    # A time wrapper can exit while its descendants survive. Inspect first;
    # never blindly re-signal an exited group or ignore a live cleanup failure.
    if live_group_members(process.pid):
        signal_group(process.pid, signal.SIGKILL)
    deadline = time.monotonic() + 2
    while live_group_members(process.pid):
        if time.monotonic() >= deadline:
            raise RuntimeError('Timed-out process group still has live members after SIGKILL')
        time.sleep(.025)

def run_trial(args, fixture, repetition):
    directory = args.output / f'{fixture["name"]}-{repetition:02d}'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / 'measurements.json'
    env = os.environ.copy()
    home = directory / 'profile'
    home.mkdir(exist_ok=True)
    env['PLTUSERHOME'] = str(home)
    env['XDG_CONFIG_HOME'] = str(home / '.config')
    env['XDG_CACHE_HOME'] = str(home / '.cache')
    # PLTADDONDIR, active package set and OpenRacket mode remain caller-controlled.
    env['OPENRACKET_BENCH_CONFIG'] = json.dumps({
        'fixture': fixture['path'], 'output': str(output), 'mode': args.mode,
        'edit_position': fixture['edit_position'], 'characters': fixture['characters'],
        'profile': getattr(args, 'profile', False),
        'metadata_only': getattr(args, 'metadata_only', False),
        'scan_activation': getattr(args, 'scan_activation', 'none')})
    command = [args.racket, str(ROOT / 'retained-host.rkt')]
    system = platform.system()
    resource_file = directory / 'native-resource.txt'
    if Path('/usr/bin/time').exists() and system == 'Linux':
        command = ['/usr/bin/time', '-v', '-o', str(resource_file)] + command
    elif Path('/usr/bin/time').exists() and system == 'Darwin':
        command = ['/usr/bin/time', '-l'] + command
    started = time.monotonic()
    timeout = False
    with (directory / 'stdout.log').open('w') as stdout, (directory / 'stderr.log').open('w') as stderr:
        process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timeout = True
            terminate_group(process)
    report = {}
    if output.exists():
        try:
            report = json.loads(output.read_text())
        except (ValueError, OSError) as error:
            report['report_read_error'] = str(error)
    stderr = (directory / 'stderr.log').read_text(errors='replace')
    resources = resource_file.read_text(errors='replace') if resource_file.exists() else stderr
    report.update({'fixture_metadata': fixture, 'repetition': repetition,
                   'process_wall_ms': (time.monotonic() - started) * 1000,
                   'native_max_rss_bytes': native_rss(resources, system),
                   'exit_code': process.returncode, 'timeout': timeout})
    if timeout:
        report['status'] = 'timeout'
    elif process.returncode != 0 or report.get('status') != 'complete':
        report['status'] = 'failed'
    if report['status'] != 'complete':
        report['stderr_tail'] = stderr[-12000:]
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('OPENRACKET_PERFORMANCE_TRIAL_JSON_BEGIN', flush=True)
    print(json.dumps(report, separators=(',', ':')), flush=True)
    print('OPENRACKET_PERFORMANCE_TRIAL_JSON_END', flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, help='Label only; caller sets real app environment')
    parser.add_argument('--racket', default='racket')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--fixture', choices=['all', 'mixed-100k', 'mixed-1mib'], default='all')
    parser.add_argument('--profile', action='store_true', help='Separate attribution-only trial; adds sampling/logging overhead')
    parser.add_argument('--metadata-only', action='store_true', help='Open fixture and read settings; no latency workload')
    parser.add_argument('--scan-activation', choices=['none', 'stock', 'candidate'], default='none',
                        help='Read-only assertion of scan helper absence/selection; never enables it')
    args = parser.parse_args()
    if args.metadata_only and args.profile:
        parser.error('--metadata-only and --profile are mutually exclusive')
    if not (1 <= args.repetitions <= 10 and 1 <= args.timeout <= 300):
        parser.error('repetitions must be1..10; timeout must be1..300 seconds')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    fixtures = write_fixtures(args.output / 'fixtures')
    if args.fixture != 'all':
        fixtures = [fixture for fixture in fixtures if fixture['name'] == args.fixture]
    metadata = {'schema_version': 1, 'mode': args.mode,
                'measurement_kind': ('metadata_only' if args.metadata_only else
                                     'instrumented_attribution_only' if args.profile else 'ordinary_timing'),
                'platform': platform.platform(),
                'machine': platform.machine(), 'logical_cpus': os.cpu_count(),
                'runner_os': os.getenv('RUNNER_OS'), 'runner_arch': os.getenv('RUNNER_ARCH'),
                'github_sha': os.getenv('GITHUB_SHA'), 'repetitions': args.repetitions,
                'per_trial_timeout_seconds': args.timeout,
                'measurement_warning': 'Synthetic editor events and event-loop fences; not physical input-to-photon. Fresh process, not cold filesystem cache. Stock settings unchanged.'}
    plan = [(fixture, repetition)
            for repetition in range(1, args.repetitions + 1) for fixture in fixtures]
    reports, skipped = [], []
    consecutive_startup_failures = 0
    fail_fast_reason = None
    for index, (fixture, repetition) in enumerate(plan):
        report = run_trial(args, fixture, repetition)
        reports.append(report)
        if report['status'] != 'complete' and 'fresh_process_gui_startup_ms' not in report:
            consecutive_startup_failures += 1
        else:
            consecutive_startup_failures = 0
        if consecutive_startup_failures >= 2:
            fail_fast_reason = 'Two consecutive trials failed before GUI readiness; remaining trials were not run.'
            skipped = [{'fixture': row['name'], 'repetition': rep, 'status': 'not_run',
                        'reason': fail_fast_reason} for row, rep in plan[index + 1:]]
            print('OPENRACKET_PERFORMANCE_FAIL_FAST ' + fail_fast_reason, flush=True)
            break
    aggregate = dict(metadata, fail_fast_reason=fail_fast_reason, trials_not_run=skipped,
                     trials=[summarize(report) | {
        'fixture': report['fixture_metadata']['name'], 'repetition': report['repetition'],
        'native_max_rss_bytes': report['native_max_rss_bytes'],
        'process_wall_ms': report['process_wall_ms']} for report in reports])
    (args.output / 'summary.json').write_text(json.dumps(aggregate, indent=2) + '\n')
    print('OPENRACKET_PERFORMANCE_SUMMARY_JSON_BEGIN', flush=True)
    print(json.dumps(aggregate, separators=(',', ':')), flush=True)
    print('OPENRACKET_PERFORMANCE_SUMMARY_JSON_END', flush=True)
    return 0 if not skipped and all(report['status'] == 'complete' for report in reports) else 1

if __name__ == '__main__':
    sys.exit(main())
