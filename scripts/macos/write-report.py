#!/usr/bin/env python3
"""Generate results from this run, never convert inherited Linux evidence to Mac passes."""
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import subprocess

root = Path(__file__).resolve().parents[2]
def command(*args):
    try:
        return subprocess.check_output(args, stderr=subprocess.STDOUT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unavailable'

status = root / 'qa/macos-run/status.tsv'
rows = [line.split('\t', 1) for line in status.read_text().splitlines()] if status.exists() else []
archive = root / 'dist/macos/OpenRacket-macos-arm64-preview.zip'
packaged = archive.exists() and (archive.parent / 'SHA256SUMS.txt').exists()
lines = [
    '# OpenRacket macOS automated test report', '',
    'Generated: ' + datetime.now(timezone.utc).isoformat(),
    'Source commit: ' + os.environ.get('GITHUB_SHA', command('git', 'rev-parse', 'HEAD')),
    'Workflow: ' + os.environ.get('GITHUB_SERVER_URL', 'local') + '/' + os.environ.get('GITHUB_REPOSITORY', '') + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', ''),
    'Host: ' + platform.platform(),
    'macOS: ' + command('sw_vers', '-productVersion'),
    'Architecture: ' + platform.machine(),
    'Rust: ' + command('rustc', '--version'),
    'Cargo: ' + command('cargo', '--version'),
    'Racket: ' + command(os.environ.get('RACKET_BIN', 'racket'), '--version'),
    'Deployment target requested: ' + os.environ.get('MACOSX_DEPLOYMENT_TARGET', 'unspecified'),
    '', '## Checks executed during this run', '',
]
lines.extend('- ' + name + ': ' + result for name, result in rows)
if not rows:
    lines.append('- Test script did not produce results. Do not interpret this report as a pass.')
lines.extend([
    '- Bundle, ad-hoc seal, dynamic-library allowlist and archive round trip: ' + ('PASS' if packaged else 'NOT COMPLETED'),
    '', '## Scope and outstanding checks', '',
    'Rust/model/offscreen/native-runtime checks do not establish interactive desktop behavior.',
    'NOT TESTED: Finder launch; Gatekeeper acceptance after download; native focus, file dialogs, clipboard, IME, VoiceOver, HiDPI and app menu integration.',
    'NOT PROVIDED: Developer ID signature, Apple notarization, bundled Racket runtime, Intel binary, full DrRacket parity or a measured DrRacket speedup.',
    'The app contains only an ad-hoc integrity seal. Gatekeeper may block this preview. No security policy was changed or bypassed.',
    'Racket 9.3 CS is installed separately from the official checksum-pinned Minimal Racket archive for these core tests.',
    'The original Linux QA files remain Linux evidence; the statuses above are generated specifically by this run.',
    'Detailed output is in this workflow run’s logs. MANUAL-QA.md lists the remaining target-OS work.',
])
if packaged:
    lines += ['', '## Archive checksum', '', (archive.parent / 'SHA256SUMS.txt').read_text().strip()]
(root / 'MACOS-TEST-REPORT.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
