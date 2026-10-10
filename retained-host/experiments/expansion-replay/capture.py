#!/usr/bin/env python3
"""CI-only native capture of the actual edited request; no installs or source edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from supervise import cleanup_group

BASE_SHA256 = '766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e'
EDIT_POSITION = 524139

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--racket', required=True, type=Path)
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    racket, fixture, output = a.racket.resolve(), a.fixture.resolve(), a.output.resolve()
    data = fixture.read_bytes()
    if len(data) != 1048576 or hashlib.sha256(data).hexdigest() != BASE_SHA256:
        p.error('Fixture must be the unchanged deterministic mixed-1MiB benchmark fixture')
    if output.exists():
        p.error('Capture output must be a new disposable directory')
    output.mkdir(parents=True)
    profile = output / 'profile'
    profile.mkdir()
    (profile / 'openracket-diagnostic-profile').write_text('openracket-expansion-diagnostic-profile\n')
    edited = data[:EDIT_POSITION] + b'x' + data[EDIT_POSITION:]
    config = {'fixture': str(fixture), 'output': str(output), 'edit_position': EDIT_POSITION}
    env = dict(os.environ)
    cleared_flags = sorted(key for key in env if key.startswith('OPENRACKET_'))
    for key in list(env):
        if key.startswith('OPENRACKET_'):
            env.pop(key)
    env.update({'PLTUSERHOME': str(profile), 'XDG_CONFIG_HOME': str(profile / '.config'),
                'XDG_CACHE_HOME': str(profile / '.cache'),
                'OPENRACKET_EXPANSION_CAPTURE': '1',
                'OPENRACKET_CAPTURE_CONFIG': json.dumps(config),
                'OPENRACKET_CAPTURE_OUTPUT': str(output),
                'OPENRACKET_CAPTURE_EXPECTED_SHA256': hashlib.sha256(edited).hexdigest(),
                'OPENRACKET_REPLAY_SUPPORT': str(Path(__file__).with_name('support.rkt').resolve())})
    command = [str(racket), str(Path(__file__).with_name('capture-host.rkt').resolve())]
    report = {'schema_version': 1, 'command': command, 'native_capture_only': True,
              'cleared_inherited_openracket_keys': cleared_flags,
              'base_fixture_sha256': BASE_SHA256, 'edited_snapshot_sha256': hashlib.sha256(edited).hexdigest(),
              'edited_snapshot_bytes': len(edited), 'timeout': False}
    process = None
    started = time.monotonic()
    try:
        with (output / 'stdout.log').open('wb') as stdout, (output / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                process.wait(timeout=190)
            except subprocess.TimeoutExpired:
                report['timeout'] = True
    except BaseException as e:
        report['error'] = f'{type(e).__name__}: {e}'
    finally:
        if process:
            report['cleanup'] = cleanup_group(process, time.monotonic() + 5)
            report['exit_code'] = process.returncode
        report['elapsed_seconds'] = time.monotonic() - started
        report['capture_exists'] = (output / 'capture.rktd').is_file()
        report['summary_exists'] = (output / 'capture-summary.json').is_file()
        (output / 'capture-supervisor.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if (report.get('exit_code') == 0 and not report['timeout']
                 and report.get('cleanup', {}).get('complete') and report['capture_exists']) else 1

if __name__ == '__main__':
    sys.exit(main())
