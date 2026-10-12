#!/usr/bin/env python3
"""Decode complete byte-exact light CI evidence after bounded replay validation."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def unwrap(value):
    if not isinstance(value, dict) or set(value) != {'filename', 'encoding', 'bytes', 'sha256', 'chunks'}:
        raise ValueError('Exact byte-wrapper fields required')
    name = value['filename']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ('.', '..'):
        raise ValueError('Unsafe evidence filename')
    if value['encoding'] != 'base64' or type(value['bytes']) is not int or not 0 <= value['bytes'] <= 16 * 1024 * 1024:
        raise ValueError('Invalid encoding or evidence size')
    chunks = value['chunks']
    if not isinstance(chunks, list) or not all(isinstance(c, str) and len(c) <= 10924 for c in chunks):
        raise ValueError('Invalid evidence chunks')
    raw = b''.join(base64.b64decode(c, validate=True) for c in chunks)
    if len(raw) != value['bytes'] or hashlib.sha256(raw).hexdigest() != value['sha256']:
        raise ValueError('Whole-file byte hash or size mismatch')
    return name, raw


def decode(log, output):
    if output.exists():
        raise ValueError('Use a new output directory; never overwrite evidence')
    replay = module('light_replay_decoder', Path(__file__).with_name('decode-replay-evidence.py'))
    documents = replay.decode(log, output / 'replay-documents')
    index = []
    seen = set()
    for row in documents:
        label = row['label']
        if not label.startswith('evidence-') or not label.endswith('-supervisor'):
            continue
        if label in seen:
            raise ValueError('Repeated light evidence label: ' + label)
        seen.add(label)
        name, raw = unwrap(json.loads(Path(row['path']).read_text()))
        folder = output / label.removeprefix('evidence-').removesuffix('-supervisor')
        folder.mkdir()
        destination = folder / name
        destination.write_bytes(raw)
        index.append({'label': label, 'path': str(destination), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    if not index:
        raise ValueError('No light byte-wrapper evidence found')
    (output / 'decoded-light-index.json').write_text(json.dumps(index, indent=2) + '\n')
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(decode(args.log.read_text(), args.output), indent=2))


if __name__ == '__main__':
    main()
