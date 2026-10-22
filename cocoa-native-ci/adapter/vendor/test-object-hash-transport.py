#!/usr/bin/env python3
"""Portable exact-byte/refusal tests and clearly synthetic compression estimate."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import lzma
import os
import pathlib
import random
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load('transport_tests', HERE / 'object-hash-transport.py')
E = load('unchanged_emitter_tests', HERE / 'emit-replay-evidence.py')


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve(strict=True)
        self.reports = self.root / 'reports'
        self.reports.mkdir()
        self.transport = self.root / 'transport'
        self.transport.mkdir()
        self.number = 0

    def fresh(self):
        self.number += 1
        return self.root / ('decoded-' + str(self.number))

    def write(self, name='result.json', data=b'{"passed":false}\n'):
        path = self.reports / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def build(self, paths=None):
        if paths is None:
            paths = [self.write()]
        with contextlib.redirect_stdout(io.StringIO()):
            return T.build_bundle(paths, self.reports, self.root / ('bundle-' + str(self.number) + '.xz'))

    def forged(self, manifest=None, payload=b'abc', tail=b'', manifest_raw=None, declared=None, compressed=None):
        if manifest is None:
            manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': 'a.bin', 'bytes': len(payload), 'sha256': T.sha(payload)}]}
        if manifest_raw is None:
            manifest_raw = T.packed(manifest)
        raw = T.MAGIC + struct.pack('>I', len(manifest_raw)) + manifest_raw + payload + tail
        compressed = lzma.compress(raw, check=lzma.CHECK_SHA256) if compressed is None else compressed
        return {'schema': T.ENVELOPE_SCHEMA, 'encoding': 'xz+base64',
                'compressed_bytes': len(compressed), 'compressed_sha256': T.sha(compressed),
                'uncompressed_bytes': len(raw) if declared is None else declared,
                'manifest_sha256': T.sha(manifest_raw), 'raw_bytes': sum(r['bytes'] for r in manifest['files']),
                'file_count': len(manifest['files']),
                'chunks': [base64.b64encode(compressed[i:i + T.BASE64_CHUNK]).decode('ascii')
                           for i in range(0, len(compressed), T.BASE64_CHUNK)]}

    def recompressed(self, envelope, compressed):
        envelope = copy.deepcopy(envelope)
        envelope.update(compressed_bytes=len(compressed), compressed_sha256=T.sha(compressed),
                        chunks=[base64.b64encode(compressed[i:i + T.BASE64_CHUNK]).decode('ascii')
                                for i in range(0, len(compressed), T.BASE64_CHUNK)])
        return envelope

    def reject(self, envelope):
        output = self.fresh()
        with self.assertRaises((ValueError, OSError)):
            T.decode_verified(envelope, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob('.verified-bundle-*')))


class ExactBytesTests(Fixture):
    def test_binary_empty_whitespace_and_nonjson_preserved(self):
        originals = {'a.bin': bytes(range(256)) * 50,
                     'empty.bin': b'', 'nested/bad-stdout.bin': b'\xff\x00FAIL\n{truncated',
                     'raw.json': b'{ "order": 1, "space": [2, 3] }\n',
                     'screenshot.png': b'\x89PNG\r\n\x1a\nraw fixture, not native capture'}
        env = self.build([self.write(name, data) for name, data in originals.items()])
        output = self.fresh()
        result = T.decode_verified(T.packed(env), output)
        self.assertTrue(result['transport_verified'])
        self.assertEqual(result['file_count'], len(originals))
        for name, data in originals.items():
            self.assertEqual((output / name).read_bytes(), data)
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o600)
        self.assertEqual(sorted(originals), [x['path'] for x in result['files']])

    def test_actual_unchanged_emitter_roundtrip_with_many_chunks(self):
        payload = random.Random(71).randbytes(500000)
        env = self.build([self.write(data=payload)])
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = T.emit_bundle(env, E, self.transport)
        self.assertTrue(status['complete'])
        text = stream.getvalue()
        self.assertLess(max(map(len, text.splitlines())), E.LINE_LIMIT)
        restored = T.envelope_from_log('\n'.join('2026-10-11T00:00:00Z ' + line for line in text.splitlines()))
        self.assertEqual(env, restored)
        output = self.fresh()
        T.decode_verified(restored, output)
        self.assertEqual((output / 'result.json').read_bytes(), payload)

    def test_tiny_bundle_unchunked_outer_roundtrip(self):
        env = self.build()
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertTrue(T.emit_bundle(env, E, self.transport)['complete'])
        self.assertEqual(T.envelope_from_log(stream.getvalue()), env)

    def test_existing_ancestor_alias_and_explicit_symlink_tmp(self):
        physical = self.root / 'physical'
        physical.mkdir()
        alias = self.root / 'tmp-alias'
        alias.symlink_to(physical, target_is_directory=True)
        reports = alias / 'reports'
        reports.mkdir()
        path = reports / 'raw.bin'
        path.write_bytes(b'exact')
        env = T.build_bundle([path], reports, alias / 'bundle.xz')
        T.decode_verified(env, alias / 'decoded')
        self.assertEqual((physical / 'decoded/raw.bin').read_bytes(), b'exact')

    def test_cli_envelope_and_log(self):
        env = self.build()
        path = self.root / 'envelope.json'
        path.write_bytes(T.packed(env))
        args = [sys.executable, str(HERE / 'decode-object-hash-evidence.py')]
        result = subprocess.run(args + [str(path), str(self.fresh())], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            T.emit_bundle(env, E, self.transport)
        log = self.root / 'log.txt'
        log.write_text(stream.getvalue())
        result = subprocess.run(args + [str(log), str(self.fresh()), '--log'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        log.write_text(stream.getvalue().replace('DOCUMENT_END', 'LOST_END'))
        result = subprocess.run(args + [str(log), str(self.fresh()), '--log'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stderr)['transport_verified'])


class RefusalTests(Fixture):
    def test_manifest_duplicate_json_fields(self):
        env = self.forged(manifest_raw=b'{"files":[],"files":[],"schema":"object-hash-bundle-manifest/v1"}')
        self.reject(env)

    def test_duplicate_envelope_json_fields(self):
        env = self.forged()
        raw = T.packed(env)
        self.reject(raw[:-1] + b',"schema":"object-hash-bundle-envelope/v1"}')

    def test_trailing_json_nonfinite_and_noncanonical_manifest(self):
        self.reject(T.packed(self.forged()) + b' {}')
        self.reject(T.packed(self.forged()).replace(b'"raw_bytes":3', b'"raw_bytes":NaN'))
        manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': 'a', 'bytes': 3, 'sha256': T.sha(b'abc')}]}
        self.reject(self.forged(manifest, manifest_raw=json.dumps(manifest).encode()))

    def test_all_unsafe_paths(self):
        for path in ['', '../a', '/root', 'a//b', 'a/./b', 'a/../b', 'a\\b', 'C:/a', 'a\x00b', 'x\ny', 'AUX', 'nul.txt', 'a.', 'a /b', '\u212a.txt']:
            with self.subTest(path=path):
                manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': path, 'bytes': 3, 'sha256': T.sha(b'abc')}]}
                self.reject(self.forged(manifest))

    def test_duplicate_casefold_paths_and_prefixes(self):
        for paths in [('a', 'a'), ('A', 'a'), ('A/a', 'a/b'), ('a', 'a/b'), ('a/b', 'A')]:
            with self.subTest(paths=paths):
                manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': p, 'bytes': 0, 'sha256': T.sha(b'')} for p in paths]}
                self.reject(self.forged(manifest, b''))

    def test_unknown_fields_and_manifest_order(self):
        env = self.forged()
        env['links'] = []
        self.reject(env)
        manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': 'a', 'bytes': 3, 'sha256': T.sha(b'abc'), 'mode': 0o755}]}
        self.reject(self.forged(manifest))
        manifest['files'][0].pop('mode')
        manifest['files'].append({'path': '0', 'bytes': 0, 'sha256': T.sha(b'')})
        self.reject(self.forged(manifest))

    def test_link_and_special_file_inputs(self):
        target = self.write('physical/data.bin', b'raw')
        link = self.reports / 'symlink.bin'
        link.symlink_to(target)
        internal = self.reports / 'internal'
        internal.symlink_to(target.parent, target_is_directory=True)
        hard = self.reports / 'hard.bin'
        os.link(target, hard)
        fifo = self.reports / 'fifo'
        os.mkfifo(fifo)
        for path in [link, internal / 'data.bin', hard, target, fifo]:
            with self.subTest(path=path), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises((ValueError, OSError)):
                    T.build_bundle([path], self.reports, self.fresh().with_suffix('.xz'))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            T.build_bundle([target], internal, self.fresh().with_suffix('.xz'))

    def test_existing_or_link_output_refused(self):
        env = self.forged()
        output = self.root / 'exists'
        output.mkdir()
        with self.assertRaises(ValueError):
            T.decode_verified(env, output)
        link = self.root / 'dangling'
        link.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError):
            T.decode_verified(env, link)
        self.assertTrue(link.is_symlink())

    def test_compressed_sha_and_raw_sha_and_manifest_sha(self):
        for field in ['compressed_sha256', 'manifest_sha256']:
            env = self.forged()
            env[field] = 'f' * 64
            self.reject(env)
        manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': 'a.bin', 'bytes': 3, 'sha256': 'f' * 64}]}
        self.reject(self.forged(manifest))

    def test_truncated_corrupt_trailing_concatenated_compressed(self):
        env = self.forged()
        compressed = base64.b64decode(env['chunks'][0])
        mutated = bytearray(compressed)
        mutated[len(mutated)//2] ^= 1
        for raw in [compressed[:-1], compressed[:24], bytes(mutated), compressed + b'x', compressed + b'\0' * 4, compressed + compressed]:
            with self.subTest(size=len(raw)):
                self.reject(self.recompressed(env, raw))

    def test_missing_or_trailing_uncompressed_bytes(self):
        self.reject(self.forged(tail=b'x'))
        env = self.forged()
        manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': 'a.bin', 'bytes': 4, 'sha256': T.sha(b'abcd')}]}
        self.reject(self.forged(manifest, b'abc'))
        env['uncompressed_bytes'] -= 1
        self.reject(env)

    def test_bad_integer_types_bounds_and_base64(self):
        for field, value in [('compressed_bytes', True), ('compressed_bytes', T.COMPRESSED_LIMIT + 1),
                             ('raw_bytes', T.TOTAL_LIMIT + 1), ('file_count', 513), ('raw_bytes', -1),
                             ('uncompressed_bytes', T.TOTAL_LIMIT + T.MANIFEST_LIMIT + 100)]:
            env = self.forged()
            env[field] = value
            self.reject(env)
        for chunks in [['!'], [], [base64.b64encode(b'x').decode()] * 1000, ['A' * 16388]]:
            env = self.forged()
            env['chunks'] = chunks
            self.reject(env)

    def test_explicit_uncompressed_limits(self):
        self.assertEqual((T.FILE_LIMIT, T.TOTAL_LIMIT, T.FILE_COUNT_LIMIT), (128*T.MIB, 256*T.MIB, 512))
        for sizes in [[T.FILE_LIMIT+1], [100*T.MIB]*3, [0]*513]:
            manifest = {'schema': T.MANIFEST_SCHEMA, 'files': [{'path': f'{i:04d}', 'bytes': n, 'sha256': '0'*64} for i,n in enumerate(sizes)]}
            with self.assertRaises(ValueError):
                T.validate_manifest(manifest)
        oversized = self.reports / 'huge.bin'
        with oversized.open('wb') as stream:
            stream.truncate(T.FILE_LIMIT+1)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            T.build_bundle([oversized], self.reports, self.root / 'big.xz')
        self.assertTrue(oversized.exists())
        self.assertFalse((self.root/'big.xz').exists())
        self.assertFalse(json.loads((self.root/'big.xz.incomplete.json').read_text())['complete'])

    def test_decompression_bomb_stops_at_declared_limit(self):
        env = self.forged(payload=b'z' * (2*T.MIB))
        env['uncompressed_bytes'] = 64
        self.reject(env)
        # Exercise the streaming limit directly, independently of manifest gates.
        raw = lzma.compress(b'z'*(2*T.MIB), check=lzma.CHECK_SHA256)
        reader = T._XZReader(raw, 64)
        with self.assertRaisesRegex(ValueError, 'bound exceeded'):
            reader.read(65)
        self.assertLessEqual(reader.total, 65)

    def test_xz_memory_and_integrity_check_limits(self):
        env = self.forged()
        compressed = base64.b64decode(env['chunks'][0])
        # Current stream uses the default 8 MiB dictionary; a smaller verifier
        # memory bound must reject rather than allocate that dictionary.
        with patch.object(T, 'DECOMPRESSION_MEMORY_LIMIT', 1024):
            self.reject(env)
        raw = lzma.decompress(compressed)
        self.reject(self.recompressed(env, lzma.compress(raw, check=lzma.CHECK_NONE)))

    def test_worst_case_compressed_cap_refusal_keeps_original(self):
        raw = random.Random(51).randbytes(T.COMPRESSED_LIMIT + 256*1024)
        path = self.write('incompressible.bin', raw)
        output = self.root / 'over-budget.xz'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), self.assertRaisesRegex(ValueError, 'exceeds 4 MiB'):
            T.build_bundle([path], self.reports, output)
        self.assertFalse(output.exists())
        self.assertEqual(T.sha(path.read_bytes()), T.sha(raw))
        self.assertIn('TRANSPORT_INCOMPLETE', stream.getvalue())
        self.assertFalse(list(self.root.glob('.bundle-*')))

    def test_input_mutation_between_passes_refused(self):
        path = self.write(data=b'abc')
        opened, count = T._open_input, 0
        def tampered(*args):
            nonlocal count
            count += 1
            if count == 2:
                path.write_bytes(b'def')
            return opened(*args)
        with patch.object(T, '_open_input', tampered), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'Input changed'):
            T.build_bundle([path], self.reports, self.root / 'changed.xz')
        self.assertFalse((self.root / 'changed.xz').exists())

    def test_partial_emission_no_retry_even_with_different_bundle(self):
        env = self.build()
        class BrokenEmitter:
            encode = staticmethod(E.encode)
            calls = 0
            def emit(self, _):
                self.calls += 1
                print('OPENRACKET_REPLAY_DOCUMENT_BEGIN {"partial":true}')
                raise OSError('fixture output stopped')
        emitter = BrokenEmitter()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(T.emit_bundle(env, emitter, self.transport)['complete'])
            other = self.forged(payload=b'different')
            self.assertFalse(T.emit_bundle(other, emitter, self.transport)['complete'])
        self.assertEqual(emitter.calls, 1)
        self.assertTrue((self.transport / 'emission-attempt.json').is_file())
        self.assertTrue((self.transport / 'transport-incomplete.json').is_file())
        self.assertTrue((self.reports / 'result.json').is_file())

    def test_outer_missing_duplicate_reordered_and_corrupt(self):
        env = self.build([self.write(data=random.Random(2).randbytes(100000))])
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            T.emit_bundle(env, E, self.transport)
        lines = stream.getvalue().splitlines()
        variants = [lines[:-1], lines+lines, lines[1:], [lines[0]]+lines[2:]]
        idx = next(i for i,x in enumerate(lines) if 'ARRAY_JSON' in x)
        variants += [lines[:idx]+[lines[idx]]+lines[idx:], lines[:idx]+lines[idx+1:]]
        variants += [[x.replace('"arrays":1', '"arrays":1,"arrays":1') for x in lines]]
        variants += [lines + [lines[0] + 'trailing'], lines + [lines[0][:-2]]]
        for variant in variants:
            with self.subTest(lines=len(variant)), self.assertRaises(ValueError):
                T.envelope_from_log('\n'.join(variant))


def estimate():
    """Synthetic scaling model using real helper/provenance source bytes.

    This does not execute Racket or claim these are native receipt counts/hashes.
    It models 2,048 source/zo/dep records per arm and 19 repeated load maps, with
    distinct deterministic synthetic product hashes and actual source snippets.
    """
    temp = tempfile.TemporaryDirectory()
    root = pathlib.Path(temp.name).resolve(strict=True)
    reports = root / 'reports'
    reports.mkdir()
    paths = []
    def put(name, raw):
        path = reports / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        paths.append(path)
    provenance_raw = (HERE/'object-hash-native/API-PROVENANCE.json').read_bytes()
    provenance = json.loads(provenance_raw)
    sources = provenance['evidence']
    put('synthetic-basis/API-PROVENANCE.json', provenance_raw)
    for path in sorted((HERE/'object-hash-native').glob('*.rkt')):
        put('synthetic-basis/'+path.name, path.read_bytes())
    seed = random.Random(901)
    records = {}
    for arm in ['stock', 'diagnostic']:
        base = '/private/var/folders/synthetic/object-hash-'+arm
        rows = []
        for n in range(2048):
            source = sources[n % len(sources)]
            name = base+'/runtime/share/pkgs/synthetic-'+str(n)+'/'+pathlib.PurePosixPath(source['path']).name
            zo = base+'/compiled'+name+'/compiled/module_rkt.zo'
            row = {'nominal_path': name,
                   'source': {'path': name, 'size': len(source['content'].encode()), 'sha256': T.sha(source['content'].encode())},
                   'bytecode': {'path': zo, 'size': 1024+n, 'sha256': seed.randbytes(32).hex()},
                   'dependency': {'path': zo[:-3]+'.dep', 'size': 200+n%500, 'sha256': seed.randbytes(32).hex()},
                   'dep_source_sha1': hashlib.sha1(source['content'].encode()).hexdigest(),
                   'target_machine': 'ta6osx', 'reason': 'recorded-dependency',
                   'dependencies': [{'path': base+'/runtime/collects/racket/base.rkt', 'external': False, 'indirect': False}]}
            rows.append(row)
        records[arm] = rows
        receipt = {'schema': 'object-hash-rebuild-receipts/v1', 'mode': 'full',
                   'synthetic_not_native_evidence': True, 'runtime_root': base+'/runtime',
                   'probe_root': base+'/probe', 'helper_root': base+'/ci', 'compiled_root': base+'/compiled',
                   'modules': rows, 'external_files': [], 'primitives': [], 'runtime_paths': [],
                   'live_registry_observed': False, 'online_handler_registry_complete': False,
                   'registered_and_static_closure_complete': True, 'arbitrary_dynamic_graph_proven': False,
                   'runtime_audit_scope': 'initial-place-and-inheriting-threads', 'child_place_dynamic_audit_complete': False}
        raw = T.packed(receipt)+b'\n'
        put(arm+'-full-receipts.json', raw)
        put('commands/'+arm+'-full-receipts/stdout.bin', raw)
    for case in range(19):
        arm = 'stock' if case == 16 else 'diagnostic'
        raw = b''.join(b'OBJECT_HASH_LOAD_AUDIT '+T.packed({'schema': 'object-hash-load-audit/v1', 'event': 'modules', 'data': row})+b'\n' for row in records[arm])
        put('commands/synthetic-case-'+str(case)+'/stdout.bin', raw)
        put('commands/synthetic-case-'+str(case)+'/stderr.bin', b'')
        put('commands/synthetic-case-'+str(case)+'/process.json', T.packed({'native_executed': False, 'synthetic_not_native_evidence': True, 'passed': False})+b'\n')
    # Screenshots are explicitly synthetic high-entropy capture-sized payloads,
    # not PNGs or eligibility evidence, and not substituted for real captures.
    for case in ['stock', 'off', 'on']:
        put('commands/synthetic-host-'+case+'/capture-sized.bin', seed.randbytes(384*1024))
    env = T.build_bundle(paths, reports, root/'bundle.xz')
    transport = root/'transport'
    transport.mkdir()
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        status = T.emit_bundle(env, E, transport)
    T.need(status['complete'], 'Synthetic estimate transport incomplete')
    restored = T.envelope_from_log(stream.getvalue())
    result = T.decode_verified(restored, root/'decoded')
    for path in paths:
        T.need(path.read_bytes() == (root/'decoded'/path.relative_to(reports)).read_bytes(), 'Synthetic byte roundtrip mismatch')
    out = {'schema': 'object-hash-synthetic-compression-estimate/v1', 'native_executed': False,
           'synthetic_only': True, 'modules_per_arm': 2048, 'load_maps': 19,
           'high_entropy_capture_bytes': 3*384*1024,
           'basis_provenance_raw_sha256': T.sha(provenance_raw),
           'file_count': env['file_count'], 'raw_bytes': env['raw_bytes'],
           'compressed_bytes': env['compressed_bytes'], 'envelope_json_bytes': len(T.packed(env)),
           'emitted_log_bytes': len(stream.getvalue().encode()),
           'maximum_log_line_bytes': max(len(x.encode()) for x in stream.getvalue().splitlines()),
           'lossless_file_roundtrip': result['transport_verified']}
    temp.cleanup()
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    if sys.argv[1:] == ['--estimate']:
        estimate()
    else:
        unittest.main()
