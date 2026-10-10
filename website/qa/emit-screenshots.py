#!/usr/bin/env python3
"""Bounded screenshot evidence in ordinary free job logs, no artifact storage."""
import base64, hashlib, pathlib, struct, sys
root = pathlib.Path(sys.argv[1])
labels = ('desktop', 'desktop-dark', 'desktop-lower', 'mobile', 'mobile-lower')
total = 0
for label in labels:
    path = root / (label + '.png')
    if not path.exists():
        print(f'OPENRACKET_WEBSITE_SCREENSHOT_MISSING {label}')
        continue
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'Not PNG'
    assert 1024 <= len(data) <= 350 * 1024, f'{label}: PNG outside bounded 1KiB–350KiB range'
    width, height = struct.unpack('>II', data[16:24])
    assert 300 <= width <= 1600 and 300 <= height <= 1600
    total += len(data)
    assert total <= 1500 * 1024, 'Total evidence limit exceeded'
    digest = hashlib.sha256(data).hexdigest()
    print(f'OPENRACKET_WEBSITE_SCREENSHOT_BEGIN {label} {len(data)} {digest}', flush=True)
    encoded = base64.b64encode(data).decode('ascii')
    for i in range(0, len(encoded), 3072):
        print(f'OPENRACKET_WEBSITE_SCREENSHOT_DATA {label} {i//3072:04d} {encoded[i:i+3072]}', flush=True)
    print(f'OPENRACKET_WEBSITE_SCREENSHOT_END {label}', flush=True)
print(f'Actual captured PNG total: {total} bytes. Inspect the decoded pixels before claiming visual approval.')
