#!/usr/bin/env python3
"""Package source/evidence only; never include installed dependencies or caches."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
files=[]
for name in ['README.md','PORTABLE-CANDIDATE.md','BASE-SOURCE-SHA256.json','DELIVERED-BASE-CONTENTS.json','POLISH-CANDIDATE.md','src','tool','scripts','tests','overlay','vendor','reports','design','performance']:
 p=ROOT/name
 for f in ([p] if p.is_file() else p.rglob('*')):
  if f.is_file() and 'compiled' not in f.parts and '__pycache__' not in f.parts:
   if 'package-sources' in f.parts: continue
   if p.name == 'performance' and 'fixtures' in f.relative_to(p).parts[:-1]: continue
   if f.name in {'stock-package-install.log','stock-package-install-resume.log','cached-packages.json'}: continue
   files.append(f)
for name in ['toolbar-paint-proof.png','stock-toolbar-9.3.patch']:
 files.append(ROOT/'artifacts'/name)
files=sorted(set(files))
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
zip_path=ROOT/'artifacts/OpenRacket-native-candidate.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in files: z.write(p,arcname='OpenRacket-native-candidate/'+str(p.relative_to(ROOT)))
 z.writestr('OpenRacket-native-candidate/CONTENTS-SHA256.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(zip_path) as z:
 if z.testzip() is not None: raise SystemExit('Archive verification failed')
print(f'{zip_path}: {len(files)} source/evidence files, {zip_path.stat().st_size} bytes; ZIP CRC verified')
