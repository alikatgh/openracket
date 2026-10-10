#!/usr/bin/env python3
"""Keep the verified stock distribution pristine; clone locally for the overlay."""
import os, pathlib, shutil
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
temp = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
source = pathlib.Path(os.environ['OPENRACKET_CI_INSTALL']).resolve()
assert source.is_relative_to(temp) and source != temp, 'Disposable source required'
target = source.with_name(source.name+'-modern')
assert not target.exists() and target.is_relative_to(temp), 'New disposable destination required'
shutil.copytree(source, target, symlinks=True)
for path in target.rglob('*'):
    if path.is_symlink():
        assert not path.resolve().is_relative_to(source), f'Clone links back to pristine runtime: {path}'
with open(os.environ['GITHUB_ENV'], 'a') as out:
    out.write(f'RACKET={target}/bin/racket\nRACO={target}/bin/raco\nOPENRACKET_CI_INSTALL={target}\n')
print('Preserved pristine stock runtime:', source)
print('Created disposable modern runtime:', target)
print(target)
