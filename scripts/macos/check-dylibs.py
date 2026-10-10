#!/usr/bin/env python3
"""Fail closed if otool reveals anything beyond OS-provided dynamic libraries."""
from pathlib import Path
import sys
lines = Path(sys.argv[1]).read_text().splitlines()[1:]
if not lines:
    raise SystemExit('No dynamic library information found')
for line in lines:
    dependency = line.strip().split(' (compatibility version ', 1)[0]
    if not dependency.startswith(('/System/Library/', '/usr/lib/')):
        raise SystemExit('Unexpected dynamic dependency: ' + dependency)
print('Dynamic dependencies are system-provided only')
