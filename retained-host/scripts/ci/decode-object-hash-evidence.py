#!/usr/bin/env python3
"""Verify a bounded envelope or GitHub log, then restore non-executable bytes."""
import argparse
import importlib.util
import json
import pathlib
import sys
sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('object_hash_transport', HERE / 'object-hash-transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=pathlib.Path, help='Envelope JSON, or job log with --log')
    parser.add_argument('output', type=pathlib.Path, help='Fresh output directory; parent must exist')
    parser.add_argument('--log', action='store_true', help='Read unchanged replay log framing')
    parser.add_argument('--label', help='Select one object-hash envelope in a multi-bundle log')
    args = parser.parse_args()
    try:
        transport.need(args.log or args.label is None, '--label requires --log')
        root = transport.physical_root(args.input.parent.resolve(strict=True))
        stream, st = transport._open_input(root, args.input.name)
        with stream:
            limit = transport.LOG_LIMIT if args.log else transport.ENVELOPE_LIMIT
            transport.need(st.st_size <= limit, 'Input exceeds bounded decoder input size')
            raw = stream.read(limit + 1)
            transport.need(len(raw) <= limit, 'Input grew beyond decoder bound')
        document = transport.envelope_from_log(raw.decode('utf-8'), args.label) if args.log else raw
        result = transport.decode_verified(document, args.output)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(json.dumps({'schema': 'object-hash-transport-status/v1', 'complete': False,
                          'transport_verified': False, 'error': str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
