#!/usr/bin/env python3
"""Deterministic, reader-valid, mixed Racket fixtures. No GUI or downloads."""
import hashlib, json
from pathlib import Path

HEADER = '#lang racket/base\n; OpenRacket deterministic performance fixture v1\n'

def generate(size):
    blocks, length, i, anchors = [HEADER], len(HEADER), 0, []
    while True:
        block = (f'; warm-input-target-{i:06d}: comments stay comments during synthetic typing\n'
                 f'(define (sample-{i:06d} x)\n'
                 '  (define message "a string with \\"escapes\\" and (parentheses)")\n'
                 '  (define pattern #rx"[a-z]+")\n'
                 '  (define data `((alpha ,x) (beta . 42) #(1 2 3)))\n'
                 '  (for/list ([n (in-range 12)] #:when (even? n))\n'
                 '    (list (+ x n) message pattern data #t #\\space)))\n\n')
        if length + len(block) + 7 > size:
            break
        anchors.append(length + len(f'; warm-input-target-{i:06d}: '))
        blocks.append(block)
        length += len(block)
        i += 1
    remaining = size - length
    assert remaining >= 7
    blocks.append('#|' + ('x' * (remaining - 5)) + '|#\n')
    text = ''.join(blocks)
    data = text.encode('ascii')
    assert len(text) == size == len(data)
    return data, anchors[len(anchors) // 2]

def write_fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for name, size in [('mixed-100k', 100_000), ('mixed-1mib', 1_048_576)]:
        data, anchor = generate(size)
        path = directory / (name + '.rkt')
        path.write_bytes(data)
        records.append({'name': name, 'path': str(path.resolve()), 'characters': size,
                        'bytes': size, 'edit_position': anchor,
                        'sha256': hashlib.sha256(data).hexdigest()})
    (directory / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    return records

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    print(json.dumps(write_fixtures(parser.parse_args().directory), indent=2))
