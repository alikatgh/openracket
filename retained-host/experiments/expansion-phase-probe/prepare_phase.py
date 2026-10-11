#!/usr/bin/env python3
"""Separate opt-in phase/thread copy; never edits the recovered replay baseline."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
from prepare import PINS, READY, locate_source, replace_once, transform_language, transform_worker

PHASE_PIN = '1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5'
ALL_PINS = dict(PINS, **{'syncheck/online-comp.rkt': PHASE_PIN})
PREFIX = ''';; BEGIN OPENRACKET REPLAY-ONLY PHASE HOOK
(define openracket-phase-hook
  (and (equal? (getenv "OPENRACKET_EXPANSION_REPLAY") "1")
       (equal? (getenv "OPENRACKET_EXPANSION_PHASE_PROBE") "1")
       (dynamic-require
        (string->path (or (getenv "OPENRACKET_REPLAY_PHASE_MODULE")
                         (error 'phase-probe "Missing frozen phase module")))
        'phase-hook!)))
;; END OPENRACKET REPLAY-ONLY PHASE HOOK

'''

def hook(label, indent):
    return (indent + ';; BEGIN OPENRACKET REPLAY-ONLY PHASE POINT\n' +
            indent + f"(when openracket-phase-hook (openracket-phase-hook '{label}))\n" +
            indent + ';; END OPENRACKET REPLAY-ONLY PHASE POINT\n')

def transform_phase_worker(text):
    text = transform_worker(text)
    text = replace_once(text, '(provide start)\n', PREFIX + '(provide start)\n')
    for number, label in [(0, '00 starting monitors'), (9, '09 starting expansion'),
                          (10, '10 finished expansion'), (11, '11 getting handler results'),
                          (12, '12 handlers finished'), (13, '13 compile finished')]:
        anchor = f'         (ep-log-info "expanding-place.rkt: {label}")'
        name = 'worker-start' if number == 0 else f'worker-phase-{number:02d}'
        text = replace_once(text, anchor, hook(name, '         ') + anchor)
    return text

def transform_phase_monitor(text):
    text = replace_once(text, '(provide go monitor)\n', PREFIX + '(provide go monitor)\n')
    points = [
        ('  (thread\n   (λ ()\n     (let loop ()\n',
         '  (thread\n   (λ ()\n' + hook('monitor-start', '     ') + '     (let loop ()\n'),
        ('  (define c (make-channel))', hook('go-send-expanded', '  ') + '  (define c (make-channel))'),
        ('  (channel-get c))', hook('go-wait-for-monitor', '  ') + '  (channel-get c))'),
        ('               (define trace (build-trace obj the-source orig-cust path))',
         hook('monitor-build-trace-start', '               ') + '               (define trace (build-trace obj the-source orig-cust path))'),
        ('               (send-back trace))]',
         hook('monitor-build-trace-complete/send-back-start', '               ') + '               (send-back trace))]'),
        ('                (channel-put val (void))',
         hook('monitor-acknowledge-go', '                ') + '                (channel-put val (void))'),
    ]
    for before, after in points:
        text = replace_once(text, before, after)
    return text

TRANSFORMS = {'module-language.rkt': transform_language, 'expanding-place.rkt': transform_phase_worker,
              'syncheck/online-comp.rkt': transform_phase_monitor}

def verify_sources(directory):
    original = {}
    for name, pin in ALL_PINS.items():
        path = directory / name
        if path.is_symlink() or path.stat().st_nlink != 1 or directory not in path.resolve().parents:
            raise ValueError(f'Source must be independently cloned inside its root: {path}')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError(f'Unexpected official source: {name}')
        original[name] = data.decode('utf-8')
    return original

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic-root', required=True, type=Path)
    parser.add_argument('--racket', required=True, type=Path)
    parser.add_argument('--skip-compile', action='store_true')
    args = parser.parse_args()
    dest, racket = args.diagnostic_root.resolve(), args.racket.resolve()
    if not dest.is_dir() or dest not in racket.parents:
        parser.error('Executable must be inside the already deep-cloned diagnostic root')
    directory = locate_source(dest, racket)
    expression = '(path->string (collection-file-path "online-comp.rkt" "drracket" "private" "syncheck"))'
    located = subprocess.run([str(racket), '-e', expression], capture_output=True, text=True, check=True, timeout=30)
    if Path(json.loads(located.stdout)).resolve() != (directory / 'syncheck/online-comp.rkt').resolve():
        raise ValueError('Actual CheckSyntax module resolves outside the pinned source root')
    original = verify_sources(directory)
    edits = {name: transform(original[name]) for name, transform in TRANSFORMS.items()}
    helpers = [Path(__file__).resolve().with_name(name) for name in
               ('phase-probe.rkt', 'support.rkt', 'replay.rkt', 'capture-host.rkt')]
    observer_files = {p.name: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in helpers}
    manifest = {'schema_version': 1, 'instrumented_copy': True, 'phase_probe': True,
                'baseline_manifest_sha256': '4ea9857a282b38da5d8c1d8033e405b13b64bf4340966fe50575dcffd95ca661',
                'diagnostic_runtime': str(dest), 'racket': str(racket), 'files': {}, 'compiled': False}
    diffs = []
    for name, changed in edits.items():
        path = directory / name
        path.write_text(changed)
        manifest['files'][name] = {'path': str(path), 'stock_sha256': ALL_PINS[name],
                                  'diagnostic_sha256': hashlib.sha256(changed.encode()).hexdigest()}
        for suffix in ('.zo', '.dep'):
            compiled = path.parent / 'compiled' / (path.name.replace('.', '_') + suffix)
            if compiled.exists():
                compiled.unlink()
        diffs.extend(difflib.unified_diff(original[name].splitlines(True), changed.splitlines(True),
                                         fromfile='stock/' + name, tofile='phase-probe/' + name))
    (dest / 'openracket-phase-source.diff').write_text(''.join(diffs))
    manifest['observer_files'] = observer_files
    # Dynamic require is not a compilation dependency. Compile helpers explicitly.
    command = [str(racket), '-l', 'raco', 'make'] + [str(directory / name) for name in edits] + [str(p) for p in helpers]
    manifest['compile_command'] = command
    target = dest / 'openracket-replay-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    if not args.skip_compile:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        (dest / 'openracket-replay-compile.log').write_text(result.stdout + result.stderr)
        manifest.update(compiled=result.returncode == 0, compile_exit_code=result.returncode)
        target.write_text(json.dumps(manifest, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('Diagnostic compilation failed; see openracket-replay-compile.log')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
