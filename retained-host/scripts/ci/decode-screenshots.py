#!/usr/bin/env python3
"""Decode exact bounded OS PNG evidence from downloaded GitHub job logs."""
import argparse, base64, hashlib, pathlib, re, struct
p=argparse.ArgumentParser()
p.add_argument('log', type=pathlib.Path)
p.add_argument('output', type=pathlib.Path)
a=p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
active=None
count=0
for line in a.log.read_text().splitlines():
    begin=re.search(r'OPENRACKET_SCREENSHOT_BEGIN ([a-z-]+) ([0-9]+) ([0-9a-f]{64})$',line)
    data=re.search(r'OPENRACKET_SCREENSHOT_DATA ([a-z-]+) ([0-9]{4}) ([A-Za-z0-9+/=]+)$',line)
    end=re.search(r'OPENRACKET_SCREENSHOT_END ([a-z-]+)$',line)
    if begin:
        assert active is None, 'Nested or incomplete image blocks'
        label,size,digest=begin.groups()
        plain = label.removesuffix('-failure-diagnostic').removesuffix('-timeout-diagnostic')
        allowed = {'pristine-stock','stock-fallback','modern-light','modern-dark','pristine-stock-stop-returning',
                   'modern-dark-native-appearance-restored',
                   'interval-stock-check-syntax','interval-candidate-on-check-syntax','xref-stock-check-syntax','xref-candidate-on-check-syntax','memory-stock-check-syntax','portable-modern-default','portable-modern-optout','portable-stock-launcher','portable-memory-restored','portable-memory-explicit-stock','portable-memory-custom','portable-memory-existing','portable-stock-after-memory'}
        allowed.update(mode+'-'+case for mode in ('pristine-stock','modern-dark')
                       for case in ('stop','input-eof','wxme','check-syntax'))
        allowed.update('mac-app-'+mode+'-'+step for mode in ('coldempty','coldfile','relocated') for step in ('coldempty','coldfile','warmfile','duplicate'))
        assert plain in allowed, 'Unknown screenshot evidence label'
        assert 1024<=int(size)<=300*1024
        active=(label,int(size),digest,[])
    elif data:
        assert active is not None, 'Unmatched data block'
        label,index,payload=data.groups()
        assert label==active[0] and int(index)==len(active[3]), 'Missing or unordered chunks'
        active[3].append(payload)
    elif end:
        assert active is not None and end.group(1)==active[0], 'Unmatched image end'
        label,size,digest,chunks=active
        raw=base64.b64decode(''.join(chunks),validate=True)
        assert len(raw)==size and hashlib.sha256(raw).hexdigest()==digest, 'PNG integrity mismatch'
        assert raw[:8]==b'\x89PNG\r\n\x1a\n', 'Not PNG'
        width,height=struct.unpack('>II',raw[16:24])
        output=a.output/(label+'.png')
        assert not output.exists(), 'Refusing to overwrite existing evidence'
        output.write_bytes(raw)
        print(f'{output}: {width}x{height}, {size} bytes, SHA256 {digest}')
        count+=1
        active=None
assert active is None, 'Log ended before final image chunk'
print(f'Decoded {count} intact native screenshot(s). Inspect pixels before claiming visual validation.')
