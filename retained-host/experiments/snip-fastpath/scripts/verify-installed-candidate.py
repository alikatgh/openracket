#!/usr/bin/env python3
"""Read-only source identity gate; actual activation needs a native assertion."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root, unit, framework, helper, mode):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Runtime root must be a real directory')
    root = root.resolve()
    paths = []
    for given in (unit, framework, helper):
        p = Path(given)
        if p.is_symlink():
            raise ValueError('Refuse a symlinked source file')
        p = p.resolve()
        if not p.is_relative_to(root) or p == root:
            raise ValueError('Source must belong to the selected runtime root')
        paths.append(p)
    unit, framework, helper = paths
    manifest = json.loads((ROOT/'reports/fastpath-manifest.json').read_text())
    source = manifest['sources']
    if digest(framework) != source['framework/private/text-misc.rkt']['upstream_sha256']:
        raise ValueError('Framework generic mixin is not exact original source')
    expected_unit = source['drracket/private/unit.rkt'][
        'upstream_sha256' if mode == 'stock' else 'patched_sha256']
    if digest(unit) != expected_unit:
        raise ValueError('DrRacket composition source does not match selected arm')
    if mode == 'stock':
        if helper.exists():
            raise ValueError('Private candidate helper unexpectedly exists in pristine arm')
    elif digest(helper) != manifest['helper_sha256']:
        raise ValueError('Private candidate helper source mismatch')
    return {'source_check': 'passed', 'mode': mode, 'root': str(root),
            'unit': str(unit), 'unit_sha256': digest(unit),
            'framework': str(framework), 'framework_sha256': digest(framework),
            'helper': str(helper), 'helper_sha256': digest(helper) if helper.exists() else None,
            'native_activation_proven': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--unit', required=True)
    p.add_argument('--framework', required=True)
    p.add_argument('--helper', required=True)
    p.add_argument('--mode', choices=['stock', 'candidate'], required=True)
    args = p.parse_args()
    try:
        print(json.dumps(check(**vars(args)), sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, f'Candidate source check refused: {error}\n')


if __name__ == '__main__':
    main()
