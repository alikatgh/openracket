#!/usr/bin/env python3
"""Pin-checked additive compact observer for a disposable DrRacket 9.3 clone.

Use --source-private DIR --emit DIR to stage only the two instrumented files.
Use --diagnostic-root DIR --racket FILE to patch/compile an independent clone.
Never apply to a shared, recovered, frozen, or installed production runtime.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PINS = {
    "module-language.rkt": "e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53",
    "expanding-place.rkt": "f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383",
}
HERE = Path(__file__).resolve().parent
FLAG = '(equal? (getenv "OPENRACKET_COMPACT_OBSERVER") "1")'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def insert(text, anchor, addition, *, after=False):
    if text.count(anchor) != 1:
        raise ValueError(f"Non-unique or missing pinned source anchor: {anchor!r}")
    offset = text.index(anchor) + (len(anchor) if after else 0)
    return text[:offset] + addition + text[offset:]


def block(name, code):
    return f"\n;; OPENRACKET-COMPACT-BEGIN {name}\n{code}\n;; OPENRACKET-COMPACT-END {name}\n"


def invoke(export, args):
    return ('(let ([openracket-observer-started (current-inexact-monotonic-milliseconds)])\n'
            '  ((dynamic-require\n'
            '    (string->path (or (getenv "OPENRACKET_COMPACT_OBSERVER_SUPPORT")\n'
            '                         (error \'compact-observer "Missing support path")))\n'
            f"    '{export}) {args} openracket-observer-started))")


def transform_worker(text):
    if 'OPENRACKET-COMPACT-BEGIN' in text:
        raise ValueError('Compact observer is already present')
    return insert(text, '  (let loop ([current-job #f]\n',
                  block('worker-init',
                        f'  (when {FLAG}\n    ' + invoke(
                            'observer-worker-init!',
                            "(for/list ([h (in-list handlers)]) (list (handler-key h) (and (handler-monitor-pc h) #t))) (preferences:get 'drracket:child-only-memory-limit)") + ')'))


def transform_language(text):
    if 'OPENRACKET-COMPACT-BEGIN' in text:
        raise ValueError('Compact observer is already present')
    text = insert(text, '               (place-channel-put expanding-place to-send)',
                  block('request',
                        '               (define openracket-observer-id\n'
                        f'                 (and {FLAG}\n' + invoke('observer-request!', 'to-send') + '))'))
    text = insert(text, '                         (define got-status-update (place-channel-get pc-status-drracket-place))',
                  block('status', '                         (when openracket-observer-id\n' +
                        invoke('observer-status!', 'openracket-observer-id got-status-update') + ')'), after=True)
    text = insert(text, '                 (define res (place-channel-get pc-out))',
                  block('response', '                 (when openracket-observer-id\n' +
                        invoke('observer-response!', 'openracket-observer-id res') + ')'), after=True)
    text = insert(text,
                  '                       (when (eq? us pending-thread)\n                         (set-pending-thread #f #f))',
                  block('callback-enter', '                       (when openracket-observer-id\n' +
                        invoke('observer-callback-enter!', 'openracket-observer-id (eq? us pending-thread)') + ')'))
    text = insert(text, '                       (show-results res)',
                  block('callback-delivered', '                       (when openracket-observer-id\n' +
                        invoke('observer-callback-delivered!', 'openracket-observer-id') + ')'), after=True)
    return text


TRANSFORMS = {'module-language.rkt': transform_language, 'expanding-place.rkt': transform_worker}


def prepared(source):
    # Validate both files before producing either output.
    original = {name: (source / name).read_bytes() for name in PINS}
    for name, content in original.items():
        if digest(content) != PINS[name]:
            raise ValueError(f"Source is not exact pinned DrRacket 9.3: {name}")
    return {name: TRANSFORMS[name](content.decode('utf-8')).encode('utf-8')
            for name, content in original.items()}


def locate_source(runtime, racket):
    expression = ('(begin (require json) (write-json (hasheq '
                  "'language (path->string (collection-file-path \"module-language.rkt\" \"drracket\" \"private\")) "
                  "'worker (path->string (collection-file-path \"expanding-place.rkt\" \"drracket\" \"private\")))))")
    result = subprocess.run([str(racket), '-e', expression], check=True, capture_output=True,
                            text=True, timeout=30)
    paths = json.loads(result.stdout)
    source = Path(paths['language']).resolve().parent
    if runtime not in source.parents or Path(paths['worker']).resolve().parent != source:
        raise ValueError('Resolved caller/worker are not together inside the disposable clone')
    for name in PINS:
        target = source / name
        if target.is_symlink() or target.stat().st_nlink != 1:
            raise ValueError(f'Source is not an independent deep-cloned file: {target}')
    compiled = source / 'compiled'
    if compiled.is_symlink() or (compiled.exists() and runtime not in compiled.resolve().parents):
        raise ValueError('Compiled cache is not independent and inside the disposable runtime')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-private', type=Path)
    parser.add_argument('--emit', type=Path)
    parser.add_argument('--diagnostic-root', type=Path)
    parser.add_argument('--racket', type=Path)
    parser.add_argument('--skip-compile', action='store_true')
    args = parser.parse_args()
    stage = args.source_private is not None or args.emit is not None
    if stage:
        if not args.source_private or not args.emit or args.diagnostic_root or args.racket:
            parser.error('Staging requires only --source-private and --emit')
        source = args.source_private.resolve()
        output = args.emit.resolve()
        if output.exists():
            parser.error('Staging output must be a new directory')
        edits = prepared(source)
        output.mkdir(parents=True)
        manifest_dir = output
        racket = None
    else:
        if not args.diagnostic_root or not args.racket:
            parser.error('Clone application requires --diagnostic-root and --racket')
        runtime, racket = args.diagnostic_root.resolve(), args.racket.resolve()
        if not runtime.is_dir() or runtime not in racket.parents:
            parser.error('Executable must be inside the disposable cloned runtime')
        source = output = locate_source(runtime, racket)
        edits = prepared(source)
        manifest_dir = runtime
    manifest = {
        'schema_version': 1, 'observer': 'compact-native-online-expansion-v1',
        'historical_uninstrumented_baseline': False, 'instrumented_copy': True,
        'source_private': str(source), 'output_private': str(output),
        'support_sha256': digest((HERE / 'support.rkt').read_bytes()),
        'generator_sha256': digest(Path(__file__).read_bytes()),
        'files': {}, 'compiled': False,
    }
    for name, content in edits.items():
        (output / name).write_bytes(content)
        manifest['files'][name] = {'stock_sha256': PINS[name], 'observer_sha256': digest(content)}
        if not stage:
            for extension in ('.zo', '.dep'):
                path = output / 'compiled' / (name.replace('.', '_') + extension)
                if path.exists():
                    path.unlink()
    if not stage:
        command = [str(racket), '-l', 'raco', 'make', str(HERE / 'support.rkt')]
        command += [str(output / name) for name in edits]
        manifest['compile_command'] = command
        if not args.skip_compile:
            result = subprocess.run(command, capture_output=True, text=True, timeout=240)
            (manifest_dir / 'openracket-compact-observer-compile.log').write_text(result.stdout + result.stderr)
            manifest['compile_exit_code'] = result.returncode
            manifest['compiled'] = result.returncode == 0
    manifest_path = manifest_dir / 'openracket-compact-observer-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))
    if not stage and not args.skip_compile and not manifest['compiled']:
        raise SystemExit('Observer compilation failed; see clone compile log')


if __name__ == '__main__':
    main()
