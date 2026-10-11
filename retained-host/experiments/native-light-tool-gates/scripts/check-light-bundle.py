#!/usr/bin/env python3
"""Verify the complete frozen local payload and native integration hashes."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for manifest in ('BASELINE-1125-SHA256.json','FROZEN-NATIVE-ALLOWLIST.json','DELIVERABLE-SHA256.json'):
    data=json.loads((ROOT/manifest).read_text())
    for relative,expected in data['files'].items():
        path=ROOT/relative
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise SystemExit('Hash mismatch: '+relative)
print('Frozen light-tool payload, native allowlist, and unchanged accepted inputs verified')
