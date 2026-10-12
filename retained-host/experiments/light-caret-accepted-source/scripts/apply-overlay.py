#!/usr/bin/env python3
"""Apply/revert only inside this proof's isolated profile. No downloads."""
from pathlib import Path
import argparse,hashlib,json,os,tempfile
ROOT=Path(__file__).resolve().parents[1]
if (ROOT/'profile').is_symlink():
 raise SystemExit('STOP: isolated profile root may not be a symbolic link.')
PROFILE=(ROOT/'profile').resolve()
PKGS=PROFILE/'.local/share/racket/9.3/pkgs'
TARGET=PKGS/'gui-lib/mrlib/switchable-button.rkt'
PAINT=PKGS/'gui-lib/mrlib/private/openracket-paint.rkt'
manifest=json.loads((ROOT/'reports/patch-manifest.json').read_text())
p=argparse.ArgumentParser()
p.add_argument('--revert',action='store_true')
a=p.parse_args()
for path in (TARGET,PAINT):
 if not path.resolve().is_relative_to(PROFILE):
  raise SystemExit('STOP: target leaves isolated profile.')
if not TARGET.exists():
 raise SystemExit('BLOCKED: official gui-lib is not installed in the isolated profile. No changes made.')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for path, expected_hash in ((ROOT/'vendor/switchable-button-v9.3.rkt',manifest['upstream_sha256']),
                            (ROOT/'overlay/mrlib/switchable-button.rkt',manifest['patched_sha256']),
                            (ROOT/'src/paint.rkt',manifest['painter_sha256'])):
 if sha(path) != expected_hash:
  raise SystemExit(f'STOP: source integrity check failed for {path.name}; no changes made.')
actual=sha(TARGET)
if actual not in (manifest['upstream_sha256'],manifest['patched_sha256']):
 raise SystemExit('STOP: target has unrelated changes; refusing to overwrite.')
def atomic_copy(source, target):
 tmp_name=None
 try:
  with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.openracket-', delete=False) as out:
   tmp_name=out.name
   out.write(source.read_bytes())
  os.replace(tmp_name,target)
  tmp_name=None
 finally:
  if tmp_name is not None:
   Path(tmp_name).unlink(missing_ok=True)
if a.revert:
 atomic_copy(ROOT/'vendor/switchable-button-v9.3.rkt',TARGET)
 # Retain the harmless unused renderer file, so reverting never deletes data.
 print('Restored exact stock switchable-button.rkt. Isolated tool/profile remain separate.')
else:
 if actual==manifest['patched_sha256']:
  print('Version-pinned patch already present; refreshing shared painter only.')
 atomic_copy(ROOT/'src/paint.rkt',PAINT)
 atomic_copy(ROOT/'overlay/mrlib/switchable-button.rkt',TARGET)
 print('Applied to isolated gui-lib only. Use OPENRACKET_UI=stock for stock painter/metrics.')
