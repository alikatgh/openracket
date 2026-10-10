#!/usr/bin/env python3
"""Detect any installer mutation of its complete selected runtime, including compiled files."""
import hashlib, json, os, pathlib, stat, sys

assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
assert len(sys.argv) == 4 and sys.argv[1] in ('baseline','compare')
operation = sys.argv[1]
temp = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
root, manifest = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
assert not root.is_symlink() and root.is_dir()
root = root.resolve(); manifest = manifest.resolve()
assert root.is_relative_to(temp) and root != temp
assert manifest.is_relative_to(temp) and not manifest.is_relative_to(root)
entries = {'.': ['directory', stat.S_IMODE(root.stat().st_mode)]}
for path in sorted(root.rglob('*')):
    key = str(path.relative_to(root))
    info = path.lstat()
    if path.is_symlink():
        entries[key] = ['symlink', os.readlink(path)]
    elif path.is_file():
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
        entries[key] = ['file', stat.S_IMODE(info.st_mode), info.st_size, digest.hexdigest()]
    elif path.is_dir():
        entries[key] = ['directory', stat.S_IMODE(info.st_mode)]
    else:
        raise ValueError('Unexpected non-file runtime entry: '+key)
tree_digest = hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
report = {'root':str(root),'entries':entries,'tree_sha256':tree_digest}
if operation == 'baseline':
    assert not manifest.exists(), 'Never overwrite a baseline'
    manifest.write_text(json.dumps(report,sort_keys=True)+'\n')
else:
    before = json.loads(manifest.read_text())
    assert before['root'] == str(root)
    if before['entries'] != entries:
        changed = sorted(k for k in set(before['entries'])|set(entries) if before['entries'].get(k) != entries.get(k))
        print('OPENRACKET_RUNTIME_TREE_MUTATION '+json.dumps({'changed_count':len(changed),'first_changed_paths':changed[:30]}),flush=True)
        raise SystemExit('Selected installed runtime changed; portable setup is not accepted')
print('OPENRACKET_RUNTIME_TREE_CHECK '+json.dumps({'operation':operation,'root':str(root),'entries':len(entries),'tree_sha256':tree_digest,'status':'passed'}))
