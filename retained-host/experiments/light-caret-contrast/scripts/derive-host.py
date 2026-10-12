#!/usr/bin/env python3
"""Exact insertion-only test derivative; never modify accepted source."""
from pathlib import Path
import argparse, difflib, hashlib
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'reference/native-light-tool-gates/tests/independent-native-light-tools-host.rkt'
BASE_SHA256 = '402c4b4fffbbf03f4593a17a0c13a116d59fb497dfd873030d6ddd3366d22451'

def derive(raw):
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('Exact accepted1553 light host required')
    s = raw.decode()
    changes = [
      ('         "native-light-state-observer.rkt")', '         "native-light-state-observer.rkt"\n         "native-light-caret-observer.rkt")'),
      ('  ;; This separate entrypoint accepts only the explicit modern-light tool arm.',
       '''  ;; Focused original/patched pair retains exactly the accepted Macro Stepper workflow.
  (unless (and (equal? (getenv "OPENRACKET_NATIVE_CASE") "macro-stepper")
               (member (getenv "OPENRACKET_CARET_ARM") '("original" "patched")))
    (error 'native-light-caret "Explicit palette arm and Macro Stepper required"))
  ;; This separate entrypoint accepts only the explicit modern-light tool arm.'''),
      ('  ;; A low-priority event turn allows actual paint work to follow the last update.',
       '''  ;; Add one real collapsed selection before the existing final paint/capture path.
  (on-gui (lambda () (prepare-caret-capture! frame definitions)))

  ;; A low-priority event turn allows actual paint work to follow the last update.'''),
      ('  (define geometry\n', '''  ;; Observe after the unchanged 500ms normal paint settle. No direct repaint.
  (define caret-state (on-gui (lambda () (observe-caret-state! frame definitions))))
  (define geometry
'''),
      ("          'light_tool_states light-tool-states", "          'light_tool_states light-tool-states\n          'caret_state caret-state")]
    for old,new in changes:
        if s.count(old) != 1:
            raise ValueError('Unique exact source seam missing: '+repr(old))
        s=s.replace(old,new)
    return s.encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    raw=BASE.read_bytes();new=derive(raw)
    outputs={ROOT/'native/tests/independent-native-light-caret-host.rkt':new,
      ROOT/'native-host.patch': ''.join(difflib.unified_diff(raw.decode().splitlines(True),new.decode().splitlines(True),fromfile='accepted1553/tests/independent-native-light-tools-host.rkt',tofile='focused/tests/independent-native-light-caret-host.rkt')).encode()}
    for path,data in outputs.items():
        if a.check:
            if path.read_bytes()!=data:raise ValueError('Derived artifact differs: '+str(path))
        else:path.write_bytes(data)
    print('Exact insertion-only caret host verified' if a.check else 'Exact caret host generated')
if __name__=='__main__':main()
