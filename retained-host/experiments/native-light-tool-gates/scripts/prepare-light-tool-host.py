#!/usr/bin/env python3
"""Derive a separate test-only light host from byte-exact accepted 1125 host.

No installed runtime, sibling checkout, network or native execution needed.
--check never writes. The accepted stock host is always an input, never output.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE_HOST = ROOT / 'tests/independent-native-host.rkt'
BASE_SHA256 = '80907227bdfb077485f7575b52d42d044bd41da53387b4d034add2118a6eaba8'

def derive(raw):
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('Accepted host bytes do not match frozen 1125 input')
    source = raw.decode('utf-8')
    additions = [
        ('         "native-tool-failure-diagnostics.rkt")',
         '         "native-tool-failure-diagnostics.rkt"\n'
         '         "native-light-state-observer.rkt")'),
        ('(define follow-on-result #f)',
         '(define follow-on-result #f)\n(define light-tool-states \'())'),
        ('  ;; Read-only capture before DrRacket\'s appearance tool can set an app override.',
         '''  ;; This separate entrypoint accepts only the explicit modern-light tool arm.
  ;; The stock control still runs the byte-identical accepted original host.
  (unless (and (equal? (getenv "OPENRACKET_UI") "modern")
               (equal? (getenv "OPENRACKET_HOST_THEME") "1")
               (equal? (getenv "OPENRACKET_NATIVE_APPEARANCE") "1")
               (equal? (getenv "OPENRACKET_THEME") "light")
               (not (getenv "OPENRACKET_NATIVE_APPEARANCE_CHECK"))
               (member follow-on-case '("debugger" "macro-stepper" "teaching-tests")))
    (error 'independent-native-light-tools-host "Explicit modern-light tool environment required"))
  ;; Read-only capture before DrRacket's appearance tool can set an app override.'''),
        ('  (when follow-on-case\n    (unless (member follow-on-case',
         '''  (set! light-tool-states
        (list (hash 'stage "before-tool"
                    'observed (on-gui (lambda () (observe-light-state! "before-tool"))))))

  (when follow-on-case
    (unless (member follow-on-case'''),
        ('  ;; A low-priority event turn allows actual paint work to follow the last update.',
         '''  (set! light-tool-states
        (append light-tool-states
                (list (hash 'stage "after-tool"
                            'observed (on-gui (lambda () (observe-light-state! "after-tool")))))))

  ;; A low-priority event turn allows actual paint work to follow the last update.'''),
        ("          'native_appearance_lifecycle (or native-appearance-result 'null)",
         "          'native_appearance_lifecycle (or native-appearance-result 'null)\n"
         "          'light_tool_states light-tool-states")]
    result = source
    for old, new in additions:
        if result.count(old) != 1:
            raise ValueError('Derivation anchor is not unique: ' + repr(old))
        result = result.replace(old, new)
    return result

def outputs(raw):
    result = derive(raw)
    patch = ''.join(difflib.unified_diff(raw.decode().splitlines(True), result.splitlines(True),
                    fromfile='accepted-1125/tests/independent-native-host.rkt',
                    tofile='light-gate/tests/independent-native-light-tools-host.rkt'))
    return {
        ROOT/'tests/independent-native-light-tools-host.rkt': result,
        ROOT/'reports/light-host.diff': patch,
        ROOT/'reports/light-host.json': json.dumps({
            'base_host_sha256': BASE_SHA256,
            'light_host_sha256': hashlib.sha256(result.encode()).hexdigest(),
            'scope': 'Six insertion-only test-host substitutions; accepted host and tool workflow modules unchanged',
            'native_execution': 'not run; local preparation only; publication on authorization hold',
            'cases': ['debugger','macro-stepper','teaching-tests']}, indent=2)+'\n'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-host', type=Path, default=BASE_HOST)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    generated = outputs(args.base_host.read_bytes())
    if any(p.resolve() == args.base_host.resolve() for p in generated):
        raise ValueError('Refusing to overwrite accepted input')
    for path, content in generated.items():
        if args.check:
            if path.read_bytes() != content.encode():
                raise ValueError('Generated output differs: ' + str(path))
        else:
            path.write_bytes(content.encode())
    print('Exact light host derivation verified' if args.check else 'Separate light host generated')
if __name__ == '__main__':
    main()
