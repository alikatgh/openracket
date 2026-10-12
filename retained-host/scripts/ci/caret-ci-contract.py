"""Pure focused CI safety and transport contracts; no native execution on import."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat

FREEZE_PIN = '33c9a2b7e2f2f4e9fa58310dfebf0071639c15d6715dbdab0d0b0b378edd0ff0'
ACCEPTED_PIN = '2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'
HELPERS_PIN = '5cd9c4a3850b1f2ca98793139cf44db22158216e698a6a99008f88d6518c14ad'
ARMS = ('original', 'patched')
FILES = ('composition.json', 'build.json', 'preflights.json', 'ready.json', 'stdout.txt', 'stderr.txt', 'capture.png', 'supervisor.json')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    """Durable atomic replacement. A failed/partial write never authorizes spawn."""
    path = Path(path)
    temp = path.with_name(path.name + '.pending')
    require(not temp.exists() and not temp.is_symlink(), 'Interrupted state write remains')
    with temp.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def check_members(root, members):
    root = Path(root).resolve()
    require(type(members) is dict, 'Exact member map required')
    require(len(set(n.casefold() for n in members)) == len(members), 'Case-folded member collision')
    for name, pin in members.items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and p.as_posix() == name, 'Unsafe member')
        path = root / p
        require(path.is_file() and not any((root / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts)+1)), 'Symlink or missing member: ' + name)
        require(re.fullmatch('[0-9a-f]{64}', pin) and sha(path) == pin, 'Member bytes differ: ' + name)
    return members

def verify_inputs(exp, source, support):
    require(sha(exp / 'MANIFEST.json') == FREEZE_PIN, 'Exact frozen48 manifest required')
    frozen = json.loads((exp / 'MANIFEST.json').read_text())['files']
    require(len(frozen) == 46, 'Frozen46 plus manifest/checksums required')
    check_members(exp, frozen)
    actual = {p.relative_to(exp).as_posix() for p in exp.rglob('*') if p.is_file()}
    require(actual == set(frozen) | {'MANIFEST.json', 'SHA256SUMS'}, 'Frozen package member set differs')
    # SHA256SUMS is independently derived and not recursively listed in MANIFEST.
    require(sha(exp / 'SHA256SUMS') == '58a5d15bce40ebe87dde469f9f5cc511cfb9e80e8745cfa27a7064e888ab3299', 'Exact frozen checksums required')
    require(sha(source / 'CONTENTS-SHA256.json') == ACCEPTED_PIN, 'Exact accepted155 manifest required')
    accepted = json.loads((source / 'CONTENTS-SHA256.json').read_text())
    require(len(accepted) == 155, 'Complete accepted155 source required')
    check_members(source, accepted)
    require(sha(support / 'EXACT-HELPERS.json') == HELPERS_PIN, 'Exact copied helper manifest required')
    helper = json.loads((support / 'EXACT-HELPERS.json').read_text())
    check_members(support, helper)
    return accepted

def inventory(root):
    root = Path(root)
    def entry(path):
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink():
            return ['symlink', mode, os.readlink(path)]
        if path.is_dir():
            return ['directory', mode]
        require(path.is_file(), 'Special filesystem member refused')
        return ['file', mode, info.st_size, sha(path)]
    if not root.exists() and not root.is_symlink():
        return {'.': ['absent']}
    result = {'.': entry(root)}
    if root.is_dir() and not root.is_symlink():
        for path in sorted(root.rglob('*')):
            result[path.relative_to(root).as_posix()] = entry(path)
    return result

def tree_sha(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def independent_copy(source, target):
    source, target = Path(source).resolve(), Path(target)
    require(not target.exists() and not target.is_symlink(), 'Clone must be absent')
    shutil.copytree(source, target, symlinks=True)
    for p in target.rglob('*'):
        rel = p.relative_to(target)
        if p.is_symlink():
            require(not p.resolve().is_relative_to(source), 'Clone aliases original runtime')
        elif p.is_file():
            a, b = (source / rel).stat(), p.stat()
            require((a.st_dev, a.st_ino) != (b.st_dev, b.st_ino), 'Mutable clone hardlink')
    require(inventory(source) == inventory(target), 'Independent runtime differs before setup')

class Safety:
    def __init__(self, path):
        self.path = Path(path)
    def initialize(self):
        require(not self.path.exists() and not self.path.is_symlink(), 'Never replace a safety ledger')
        write(self.path, {'blocked': False, 'active': {}, 'completed': []})
    def read(self):
        require(self.path.is_file() and not self.path.is_symlink(), 'Missing durable safety ledger; native commands blocked')
        require(not self.path.with_name(self.path.name + '.pending').exists(), 'Interrupted durable state; native commands blocked')
        value = json.loads(self.path.read_text())
        require(type(value) is dict and set(value) == {'blocked', 'active', 'completed'} and type(value['blocked']) is bool and type(value['active']) is dict and type(value['completed']) is list, 'Malformed durable safety ledger')
        return value
    def safe(self):
        value = self.read()
        require(value.get('blocked') is False and not value.get('active'), 'Prior prelaunch/cleanup uncertainty blocks native commands')
    def begin(self, token, kind, child_of=None):
        value = self.read()
        require(value.get('blocked') is False, 'Uncertain cleanup blocks native commands')
        if child_of is None:
            require(not value['active'], 'Prior owned launch remains unresolved')
        else:
            require(kind == 'capture' and set(value['active']) == {child_of} and value['active'][child_of]['kind'] == 'gui', 'Only bounded capture can accompany the owned GUI')
        require(token not in value['active'] and token not in value['completed'], 'Launch identifier reused')
        value['active'][token] = {'kind': kind, 'state': 'prelaunch', 'pid': None}
        write(self.path, value)
    def spawned(self, token, pid):
        require(type(pid) is int and pid > 0, 'Real positive process ID required')
        value = self.read()
        value['active'][token].update(state='spawned', pid=pid)
        write(self.path, value)
    def finish(self, token, verified):
        value = self.read()
        require(token in value['active'], 'Untracked launch completion')
        if verified:
            del value['active'][token]
            value['completed'].append(token)
        else:
            value['blocked'] = True
        write(self.path, value)

def validate_compositions(a, b, verifier):
    for arm, row in zip(ARMS, (a, b)):
        verifier.validate_composition(row, arm)
        require(len(row['files']) == 175, 'Exactly175 composed members required')
    require(sorted(n for n in set(a['files']) | set(b['files']) if a['files'].get(n) != b['files'].get(n)) == ['tool/info.rkt'], 'Only tool/info.rkt may differ between arms')

def validate_matrix(rows):
    require(type(rows) is list and [r.get('arm') for r in rows] == list(ARMS), 'Two exact independent arms required')
    require(all(r.get('attempted') is True and r.get('passed') is True for r in rows), 'Both actual native arms must pass')

def validate_preflight_record(record, spec):
    name, args, marker, injection, forbidden = spec
    if 'cleanup_verified' in record:
        require(record['cleanup_verified'] is True and record.get('forced_cleanup') is False and 'error' not in record, 'Standalone supervision or decoding failed')
    require(record.get('entrypoint') == name and record.get('arguments') == args, 'Wrong direct standalone invocation')
    require(record.get('timed_out') is False and type(record.get('timeout_seconds')) is int and record['timeout_seconds'] == 30, 'Unchanged30-second standalone deadline required')
    code = record.get('exit_code')
    require(type(code) is int and ((1 <= code <= 123) if injection else code == 0), 'Wrong or non-normal standalone exit')
    require(isinstance(record.get('stdout'), str) and isinstance(record.get('stderr'), str), 'Separate complete decoded streams required')
    output = record['stdout'] + '\n' + record['stderr']
    namespace = marker.split('_FAILURE ', 1)[0] if injection else marker.split('_OK ', 1)[0]
    lines = output.splitlines()
    wanted = [injection, marker] if injection else [marker]
    require(all(lines.count(line) == 1 for line in wanted), 'Exact unique typed marker required')
    require(sum(namespace in line for line in lines) == len(wanted) and output.count(namespace) == len(wanted), 'Extra or malformed marker in namespace')
    require(not forbidden or forbidden not in output, 'Injected failure reported success')

def validate_preflights(records, verifier):
    verifier.validate_preflights(records)
    for spec in verifier.PREFLIGHTS:
        row = next(r for r in records if (r['entrypoint'], r['arguments']) == (spec[0], spec[1]))
        validate_preflight_record(row, spec)
