#!/usr/bin/env python3
"""Patch only the checksum-verified official installation on the CI runner."""
import hashlib, json, os, pathlib, shutil, subprocess
root = pathlib.Path(__file__).resolve().parents[2]
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
temp = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
install = pathlib.Path(os.environ['OPENRACKET_CI_INSTALL']).resolve()
assert install.is_relative_to(temp) and install != temp, 'Disposable installation required'
racket = pathlib.Path(os.environ['RACKET']).resolve()
assert racket.is_relative_to(install), 'Runtime must belong to disposable installation'
code = '(display (collection-file-path "switchable-button.rkt" "mrlib"))'
target = pathlib.Path(subprocess.check_output([str(racket), '-e', code], text=True)).resolve()
assert target.is_relative_to(install), 'Refusing to patch any user/global package'
manifest = json.loads((root/'reports/patch-manifest.json').read_text())
assert hashlib.sha256(target.read_bytes()).hexdigest() == manifest['upstream_sha256'], 'Official source mismatch'
source = root/'overlay/mrlib/switchable-button.rkt'
assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['patched_sha256'], 'Overlay mismatch'
painter = root/'src/paint.rkt'
assert hashlib.sha256(painter.read_bytes()).hexdigest() == manifest['painter_sha256'], 'Painter mismatch'
painter_target = (target.parent/'private/openracket-paint.rkt').resolve()
assert painter_target.is_relative_to(install), 'Painter target escaped disposable installation'
shutil.copyfile(source, target)
shutil.copyfile(painter, painter_target)
print('Applied exact-SHA overlay in disposable full distribution:', target)
