#!/usr/bin/env python3
"""Deep-copy the pinned pristine runtime for one isolated CI experiment."""
import json, os, pathlib, shutil, sys

assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
assert sys.argv[1:] in (['scan'], ['budget'], ['portable']), 'Explicit bounded purpose required'
purpose = sys.argv[1]
temp = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
source = pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
assert source.is_relative_to(temp) and source != temp
target = source.with_name(source.name+'-'+purpose)
assert not target.exists() and target.is_relative_to(temp)
shutil.copytree(source, target, symlinks=True)
for path in target.rglob('*'):
    relative = path.relative_to(target)
    if path.is_symlink():
        assert not path.resolve().is_relative_to(source), f'Link back to pristine: {relative}'
    elif path.is_file():
        a, b = (source/relative).stat(), path.stat()
        assert (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino), f'Hardlink: {relative}'
print('OPENRACKET_INDEPENDENT_RUNTIME '+json.dumps({'purpose':purpose,'source':str(source),'target':str(target),'mutable_hardlinks':False}))
