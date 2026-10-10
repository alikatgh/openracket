#!/usr/bin/env python3
"""Create a clean OpenRacket source archive; run after final checks."""
from pathlib import Path
import hashlib, zipfile
root = Path(__file__).resolve().parents[1]
out = root.parent / 'OpenRacket-source.zip'
exclude = {'target', '.git', '.local', 'research', '__pycache__'}
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False) as z:
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if path.is_file() and not any(p in exclude for p in rel.parts):
            z.write(path, Path('OpenRacket') / rel)
print(out)
print(hashlib.sha256(out.read_bytes()).hexdigest())
