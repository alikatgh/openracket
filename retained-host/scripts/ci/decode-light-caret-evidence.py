#!/usr/bin/env python3
"""Decode byte-exact caret evidence; missing/failed bundles remain diagnostic."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

CI = Path(__file__).resolve().parent
C = module('caret_decode_contract', CI / 'caret-ci-contract.py')
D = module('caret_shared_decoder', CI / 'light-caret-support/decode-light-tools-evidence.py')

def decode(log, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Use an absent evidence directory')
    # Shared decoder verifies complete chunk ordering, lengths and SHA-256.
    index = D.decode(log, output / 'raw')
    seen = set()
    result = []
    for row in index:
        label = row['label']
        match = re.fullmatch(r'evidence-caret-(original|patched)-([a-z0-9-]+)-supervisor', label)
        if not match:
            continue
        arm, suffix = match.groups()
        name = next((n for n in C.FILES + ('compile-registration.json', 'native-registration.json') if n.replace('.', '-') == suffix), None)
        if name is None:
            raise ValueError('Unknown arm evidence label')
        if (arm, name) in seen:
            raise ValueError('Repeated arm evidence member')
        seen.add((arm, name))
        source = Path(row['path'])
        if source.name != name:
            raise ValueError('Label/filename disagreement')
        target = output / arm / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        result.append({'arm': arm, 'member': name, 'sha256': C.sha(target), 'bytes': target.stat().st_size})
    missing = {arm: [n for n in C.FILES if (arm, n) not in seen] for arm in C.ARMS}
    status = {'members': result, 'missing': missing, 'programmatic_validation': 'not run', 'visual_review': 'pending'}
    # Decoding success is never an acceptance claim, including complete failures.
    (output / 'decoded-caret-index.json').write_text(json.dumps(status, indent=2) + '\n')
    return status

def validate(output, exp):
    pair = module('caret_decoded_pair', Path(exp) / 'scripts/validate-caret-pair.py')
    value = pair.validate_pair(Path(output) / 'original', Path(output) / 'patched')
    value.update(visual_review='pending', rendered_state_acceptance='pending-independent-visual-review')
    return value

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--validate', action='store_true')
    a = p.parse_args()
    print(json.dumps(decode(a.log.read_text(), a.output), indent=2))
    if a.validate:
        print(json.dumps(validate(a.output, CI.parents[1] / 'experiments/light-caret-contrast'), indent=2))
