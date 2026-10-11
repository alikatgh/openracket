"""Pure checks for the isolated stock/modern-light native tool adapter."""
import base64
import hashlib
import json
from pathlib import Path
import shutil

FREEZE_PIN = 'afc635cd538ecbf39fe9c1427c5bddfd06684d4336281ad5667084f33cd70795'
ALLOWLIST_PIN = 'c1ea6a1017813e567ed4e9e09566d2a287a81a9865a1edcd05a3437a0dc5f3f4'
ACCEPTED_PIN = '2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'
CASES = ('debugger', 'macro-stepper', 'teaching-tests')
ARMS = ('stock', 'modern-light')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check_members(root, members):
    require(isinstance(members, dict), 'Manifest must be an object')
    for name, digest in members.items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'Unsafe manifest path')
        source = root / p
        require(source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(root.resolve()), 'Unsafe source: ' + name)
        require(sha(source) == digest, 'Source hash mismatch: ' + name)

def frozen_sources(exp):
    require(sha(exp / 'DELIVERABLE-SHA256.json') == FREEZE_PIN, 'Frozen payload manifest pin mismatch')
    members = json.loads((exp / 'DELIVERABLE-SHA256.json').read_text())['files']
    # 46 total files means 45 listed members plus the manifest itself.
    require(len(members) == 45, 'Exactly 45 frozen members plus manifest required')
    check_members(exp, members)
    require(sha(exp / 'FROZEN-NATIVE-ALLOWLIST.json') == ALLOWLIST_PIN, 'Native allowlist pin mismatch')
    native = json.loads((exp / 'FROZEN-NATIVE-ALLOWLIST.json').read_text())['files']
    require(len(native) == 16 and sum(n.endswith('.rkt') for n in native) == 15, 'Exact native16 / Racket15 set required')
    require(all(n.startswith('tests/') and '/reference/' not in n for n in native), 'Only native test paths may enter proof')
    check_members(exp, native)
    return native

def assemble_proof(root, proof, exp, app_contract):
    native = frozen_sources(exp)
    baseline = app_contract.source_copy(root, proof, ACCEPTED_PIN, 155)
    shutil.copy2(proof / 'CONTENTS-SHA256.json', proof / 'BASE-0520-CONTENTS.json')
    for name, digest in native.items():
        destination = proof / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        shutil.copy2(exp / name, destination)
        baseline[name] = digest
    (proof / 'CONTENTS-SHA256.json').write_text(json.dumps(baseline, indent=2) + '\n')
    check_members(proof, baseline)
    return native

def validate_preflight_record(record, spec):
    name, args, marker, injection, forbidden = spec
    require(record.get('entrypoint') == name and record.get('arguments') == args, 'Wrong preflight invocation')
    require(record.get('timed_out') is False and type(record.get('timeout_seconds')) is int and record['timeout_seconds'] == 30, 'Unchanged successful supervisor required')
    code = record.get('exit_code')
    require(type(code) is int and ((1 <= code <= 123) if injection else code == 0), 'Wrong or non-normal preflight exit')
    require(isinstance(record.get('stdout'), str) and isinstance(record.get('stderr'), str), 'Separate full streams required')
    output = record['stdout'] + '\n' + record['stderr']
    lines = output.splitlines()
    namespace = marker.split('_FAILURE exception=', 1)[0] if injection else marker.split('_OK ', 1)[0]
    wanted = [injection, marker] if injection else [marker]
    require(all(lines.count(line) == 1 for line in wanted), 'Exact unique typed marker required')
    require(sum(namespace in line for line in lines) == len(wanted) and output.count(namespace) == len(wanted), 'Extra or malformed marker in namespace')
    require(not forbidden or forbidden not in output, 'Injected failure reported success')
    return True

def validate_preflights(records, verifier):
    verifier.validate_preflights(records)
    for spec in verifier.PREFLIGHTS:
        record = next(r for r in records if (r['entrypoint'], r['arguments']) == (spec[0], spec[1]))
        validate_preflight_record(record, spec)
    return True

def run_case_matrix(native_case, record, readiness):
    """Every independent stock prerequisite runs despite isolated case failures."""
    results = []
    for case in CASES:
        stock_passed = False
        for arm in ARMS:
            row = {'arm': arm, 'case': case, 'attempted': False, 'passed': False}
            if readiness.get(arm) is not True:
                row['reason'] = 'Required reader/compile/headless preparation unavailable'
            elif arm == 'modern-light' and not stock_passed:
                row['reason'] = 'Corresponding actual stock prerequisite failed'
            else:
                row['attempted'] = True
                try:
                    row['passed'] = native_case(case, arm == 'modern-light') is True
                except Exception as error:
                    row['reason'] = str(error)
            if arm == 'stock':
                stock_passed = row['passed']
            results.append(row)
            record(arm + ' ' + case + ' matrix result', row['passed'], row.get('reason', 'Actual completed native result'))
    return results

def validate_matrix(rows):
    require(isinstance(rows, list) and len(rows) == 6, 'Six native matrix rows required')
    require([(r.get('arm'), r.get('case')) for r in rows] == [(a, c) for c in CASES for a in ARMS], 'Exact unique stock-first matrix required')
    require(all(r.get('passed') is True and r.get('attempted') is True for r in rows), 'All six native cases must actually pass')
    return True

def wrap_bytes(path):
    """Transport complete evidence, including trees/streams, with existing emitter."""
    raw = path.read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, 'Evidence exceeds explicit16MiB bound; fail rather than truncate')
    return {'filename': path.name, 'encoding': 'base64', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'chunks': [base64.b64encode(raw[i:i+8192]).decode() for i in range(0, len(raw), 8192)]}
