#!/usr/bin/env python3
"""Add opt-in observers to a CI-owned, already deep-cloned native runtime."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PINS = {
    "module-language.rkt": "e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53",
    "expanding-place.rkt": "f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383",
}

def enabled(flag):
    return f'(equal? (getenv "{flag}") "1")'

def invoke(export, args):
    return ('((dynamic-require (string->path\n'
            '                    (or (getenv "OPENRACKET_REPLAY_SUPPORT")\n'
            '                        (error \'openracket-replay "missing support path")))\n'
            f"                   '{export}) {args})")

READY = ('  ;; Opt-in diagnostic only. Integrated capture never sets this flag.\n'
         f'  (when {enabled("OPENRACKET_EXPANSION_REPLAY")}\n'
         f'    {invoke("worker-ready!", "p (current-logger) (preferences:get 'drracket:child-only-memory-limit)")})\n\n')
REGISTRY = '''       (for/list ([o-e-h (in-list (drracket:module-language-tools:get-online-expansion-handlers))])
         (list (drracket:module-language-tools:online-expansion-handler-mod-path o-e-h)
               (drracket:module-language-tools:online-expansion-handler-id o-e-h)
               (drracket:module-language-tools:online-expansion-handler-monitor? o-e-h)))'''

def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f"Non-unique or missing source anchor: {before[:80]}")
    return text.replace(before, after, 1)

def transform_worker(text):
    return replace_once(text, '  (let loop ([current-job #f]\n', READY + '  (let loop ([current-job #f]\n')

def registry_capture_expression():
    return ('       (let ([actual-registry\n' + REGISTRY.strip() + '])\n'
               f'         (when {enabled("OPENRACKET_EXPANSION_CAPTURE")}\n'
               f'           {invoke("capture-registry!", "actual-registry")})\n'
               '         actual-registry)')

def transform_language(text):
    text = replace_once(text, REGISTRY, registry_capture_expression())
    anchor = '               (place-channel-put expanding-place to-send)'
    addition = ('               (define openracket-capture-request-id\n'
                f'                 (and {enabled("OPENRACKET_EXPANSION_CAPTURE")}\n'
                f'                      {invoke("capture-request!", "to-send (preferences:get 'drracket:child-only-memory-limit)")}))\n')
    text = replace_once(text, anchor, addition + anchor)
    anchor = '                         (define got-status-update (place-channel-get pc-status-drracket-place))'
    text = replace_once(text, anchor, anchor + '\n'
                        '                         (when openracket-capture-request-id\n'
                        f'                           {invoke("capture-status!", "openracket-capture-request-id got-status-update")})')
    anchor = '                 (define res (place-channel-get pc-out))'
    text = replace_once(text, anchor, anchor + '\n'
                        '                 (when openracket-capture-request-id\n'
                        f'                   {invoke("capture-result!", "openracket-capture-request-id res")})')
    return text

def locate_source(runtime, racket):
    expression = "(begin (require json) (write-json (hasheq 'language (path->string (collection-file-path \"module-language.rkt\" \"drracket\" \"private\")) 'worker (path->string (collection-file-path \"expanding-place.rkt\" \"drracket\" \"private\")))))"
    run = subprocess.run([str(racket), '-e', expression], capture_output=True, text=True,
                         check=True, timeout=30)
    paths = json.loads(run.stdout)
    directory = Path(paths['language']).resolve().parent
    if runtime not in directory.parents:
        raise ValueError('Resolved source lies outside the supplied diagnostic clone')
    if Path(paths['worker']).resolve().parent != directory:
        raise ValueError('Resolved worker and caller use different source roots')
    for name, expected in PINS.items():
        target = directory / name
        if target.is_symlink() or target.stat().st_nlink != 1:
            raise ValueError(f'Source is linked instead of independently cloned: {target}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Unexpected official source: {name}')
    return directory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--diagnostic-root', required=True, type=Path)
    p.add_argument('--racket', required=True, type=Path)
    p.add_argument('--skip-compile', action='store_true', help='Only for explicitly separate CI compilation')
    a = p.parse_args()
    dest, racket = a.diagnostic_root.resolve(), a.racket.resolve()
    if not dest.is_dir() or dest not in racket.parents:
        p.error('Executable must be inside the already deep-cloned diagnostic root')
    out = locate_source(dest, racket)
    manifest = {'schema_version': 1, 'diagnostic_runtime': str(dest), 'racket': str(racket),
                'instrumented_copy': True, 'files': {}}
    # Verify everything before making the first change.
    edits = [(name, transformer((out / name).read_text())) for name, transformer in
             [('module-language.rkt', transform_language), ('expanding-place.rkt', transform_worker)]]
    for name, modified in edits:
        target = out / name
        target.write_text(modified)
        manifest['files'][name] = {'path': str(target), 'stock_sha256': PINS[name],
                                   'diagnostic_sha256': hashlib.sha256(modified.encode()).hexdigest()}
        for suffix in ['.zo', '.dep']:
            compiled = out / 'compiled' / (name.replace('.', '_') + suffix)
            if compiled.exists():
                compiled.unlink()
    compile_command = [str(racket), '-l', 'raco', 'make'] + [str(out / name) for name, _ in edits]
    manifest['compile_command'] = compile_command
    manifest['compiled'] = False
    path = dest / 'openracket-replay-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    if not a.skip_compile:
        result = subprocess.run(compile_command, capture_output=True, text=True, timeout=240)
        (dest / 'openracket-replay-compile.log').write_text(result.stdout + result.stderr)
        manifest['compile_exit_code'] = result.returncode
        manifest['compiled'] = result.returncode == 0
        path.write_text(json.dumps(manifest, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('Diagnostic clone compilation failed; see openracket-replay-compile.log')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
