#!/usr/bin/env python3
"""Bounded, lossless, non-executable object-hash evidence transport.

Transport integrity is not eligibility or permission to execute native code.
All limits are hard refusal limits; no file/chunk is dropped to fit them.
"""
import base64
import binascii
import hashlib
import json
import lzma
import os
import pathlib
import re
import shutil
import stat
import struct
import tempfile

P = pathlib.Path
MIB = 1024 * 1024
COMPRESSED_LIMIT = 4 * MIB
FILE_LIMIT = 128 * MIB
TOTAL_LIMIT = 256 * MIB
FILE_COUNT_LIMIT = 512
MANIFEST_LIMIT = MIB
PATH_LIMIT = 512
IO_CHUNK = 64 * 1024
BASE64_CHUNK = 12 * 1024
DECOMPRESSION_MEMORY_LIMIT = 64 * MIB
LOG_LIMIT = 32 * MIB
ENVELOPE_LIMIT = 6 * MIB
MAGIC = b'OROHBNDL\x00\x01'
MANIFEST_SCHEMA = 'object-hash-bundle-manifest/v1'
ENVELOPE_SCHEMA = 'object-hash-bundle-envelope/v1'
FILTERS = [{'id': lzma.FILTER_LZMA2, 'preset': 6, 'dict_size': 16 * MIB}]
ENVELOPE_FIELDS = {'schema', 'encoding', 'compressed_bytes', 'compressed_sha256',
                   'uncompressed_bytes', 'manifest_sha256', 'raw_bytes',
                   'file_count', 'chunks'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate JSON member')
            out[key] = value
        return out
    def constant(_):
        raise ValueError('Non-finite JSON constant')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Invalid bounded JSON') from error


def integer(value, low, high, name):
    need(type(value) is int and low <= value <= high, 'Invalid ' + name)


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
         'Invalid SHA-256')


def safe_path(value):
    need(type(value) is str and 0 < len(value) <= PATH_LIMIT, 'Invalid relative path')
    parts = value.split('/')
    for part in parts:
        need(re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', part) is not None
             and part not in ('.', '..') and not part.endswith('.'), 'Unsafe relative path')
        need(part.split('.')[0].upper() not in
             {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
              *(f'LPT{i}' for i in range(1, 10))}, 'Reserved path component')
    return parts


def validate_manifest(value):
    need(type(value) is dict and set(value) == {'schema', 'files'}
         and value['schema'] == MANIFEST_SCHEMA, 'Invalid manifest shape')
    files = value['files']
    need(type(files) is list, 'Invalid manifest files')
    integer(len(files), 1, FILE_COUNT_LIMIT, 'file count')
    seen = set()
    total = 0
    prior = None
    for row in files:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Invalid file record')
        parts = safe_path(row['path'])
        folded = row['path'].casefold()
        need(folded not in seen, 'Duplicate/casefold duplicate file path')
        need(prior is None or prior < row['path'], 'Manifest paths must be sorted')
        for i in range(1, len(parts)):
            need('/'.join(parts[:i]).casefold() not in seen, 'File/directory path collision')
        need(not any(old.startswith(folded + '/') for old in seen), 'File/directory path collision')
        # Also reject differently cased names for a common directory component.
        for old in files[:len(seen)]:
            old_parts = old['path'].split('/')
            for a, b in zip(parts[:-1], old_parts[:-1]):
                if a.casefold() != b.casefold():
                    break
                need(a == b, 'Casefold duplicate directory path')
        seen.add(folded)
        prior = row['path']
        integer(row['bytes'], 0, FILE_LIMIT, 'raw file size')
        digest(row['sha256'])
        total += row['bytes']
        need(total <= TOTAL_LIMIT, 'Raw aggregate exceeds 256 MiB')
    return total


def physical_root(path):
    # Existing ancestor aliases, including an explicitly symlinked TMPDIR, are
    # canonicalized once. The selected root itself must be a physical directory.
    path = P(os.path.abspath(os.fspath(path)))
    need(not path.is_symlink(), 'Root symlink refused')
    resolved = path.resolve(strict=True)
    need(resolved.is_dir(), 'Physical directory required')
    return resolved


def _open_input(root, relative):
    """Walk from a physical root with nofollow; no links or special files."""
    parts = safe_path(relative)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    fd = os.open(root, flags | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            new_fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = new_fd
        leaf = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)
    try:
        st = os.fstat(leaf)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'Single-link regular input required')
        integer(st.st_size, 0, FILE_LIMIT, 'raw file size')
        return os.fdopen(leaf, 'rb'), st
    except BaseException:
        os.close(leaf)
        raise


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def _source_name(path, root, supplied_root):
    path = P(path)
    if path.is_absolute():
        # Preserve every internal component instead of resolving away links.
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.relative_to(supplied_root).as_posix()
    else:
        relative = path.as_posix()
    safe_path(relative)
    return relative


def _fresh_file(path):
    path = P(path)
    need(not path.exists() and not path.is_symlink(), 'Fresh output file required')
    return path.open('xb')


def _durable_json(path, value):
    with _fresh_file(path) as stream:
        stream.write(packed(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(P(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _build_bundle(paths, reports, output):
    """Build once, without emitting; never modify originals. Return an envelope.

    paths are explicit report-relative names or paths beneath reports. output's
    parent must already exist. Existing output files are never overwritten.
    The returned envelope contains lossless base64 chunks for emit_bundle.
    """
    supplied_root = P(os.path.abspath(os.fspath(reports)))
    root = physical_root(reports)
    paths = list(paths)
    integer(len(paths), 1, FILE_COUNT_LIMIT, 'file count')
    names = sorted(_source_name(p, root, supplied_root) for p in paths)
    files, identities = [], {}
    # Validate names/duplicates before opening any input.
    validate_manifest({'schema': MANIFEST_SCHEMA, 'files':
                       [{'path': p, 'bytes': 0, 'sha256': '0' * 64} for p in names]})
    total = 0
    for name in names:
        stream, before = _open_input(root, name)
        with stream:
            total += before.st_size
            need(total <= TOTAL_LIMIT, 'Raw aggregate exceeds 256 MiB')
            h, size = hashlib.sha256(), 0
            for block in iter(lambda: stream.read(IO_CHUNK), b''):
                size += len(block)
                need(size <= before.st_size, 'Input grew during hashing')
                h.update(block)
            need(size == before.st_size and _identity(before) == _identity(os.fstat(stream.fileno())),
                 'Input changed during hashing')
        files.append({'path': name, 'bytes': size, 'sha256': h.hexdigest()})
        identities[name] = _identity(before)
    manifest = packed({'schema': MANIFEST_SCHEMA, 'files': files})
    need(len(manifest) <= MANIFEST_LIMIT, 'Manifest exceeds 1 MiB')
    output = P(output)
    parent = physical_root(output.parent.resolve(strict=True))
    output = parent / output.name
    safe_path(output.name)
    need(not output.exists() and not output.is_symlink(), 'Fresh bundle output required')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.bundle-', suffix='.xz', dir=parent, delete=False) as dest:
            temporary = P(dest.name)
            compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, check=lzma.CHECK_SHA256, filters=FILTERS)
            compressed_size = 0
            def put(raw):
                nonlocal compressed_size
                compressed_size += len(raw)
                need(compressed_size <= COMPRESSED_LIMIT, 'Compressed bundle exceeds 4 MiB; evidence incomplete')
                dest.write(raw)
            put(compressor.compress(MAGIC + struct.pack('>I', len(manifest)) + manifest))
            for row in files:
                stream, before = _open_input(root, row['path'])
                with stream:
                    need(_identity(before) == identities[row['path']], 'Input changed before compression')
                    h, size = hashlib.sha256(), 0
                    for block in iter(lambda: stream.read(IO_CHUNK), b''):
                        size += len(block)
                        need(size <= row['bytes'], 'Input grew during compression')
                        h.update(block)
                        put(compressor.compress(block))
                    need(size == row['bytes'] and h.hexdigest() == row['sha256']
                         and _identity(os.fstat(stream.fileno())) == identities[row['path']],
                         'Input changed during compression')
            put(compressor.flush())
            dest.flush()
            os.fsync(dest.fileno())
        # Link is an atomic no-clobber publish; removing our temporary name
        # immediately leaves the completed bundle with one link.
        os.link(temporary, output)
        temporary.unlink()
        temporary = None
        raw = output.read_bytes()
        return {'schema': ENVELOPE_SCHEMA, 'encoding': 'xz+base64',
                'compressed_bytes': len(raw), 'compressed_sha256': sha(raw),
                'uncompressed_bytes': len(MAGIC) + 4 + len(manifest) + total,
                'manifest_sha256': sha(manifest), 'raw_bytes': total,
                'file_count': len(files),
                'chunks': [base64.b64encode(raw[i:i + BASE64_CHUNK]).decode('ascii')
                           for i in range(0, len(raw), BASE64_CHUNK)]}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def build_bundle(paths, reports, output):
    """Build once or raise with an explicit local incomplete receipt.

    Never try another codec, omit files, or retry after emission. The caller must
    keep the overall result incomplete on any exception, including reporting
    failures. No original file is modified or removed.
    """
    try:
        return _build_bundle(paths, reports, output)
    except Exception as error:
        result = {'schema': 'object-hash-transport-status/v1', 'complete': False,
                  'stage': 'build', 'emission_attempted': False,
                  'error_type': type(error).__name__, 'error': str(error),
                  'originals_preserved': True}
        try:
            parent = physical_root(P(output).parent.resolve(strict=True))
            name = P(output).name + '.incomplete.json'
            safe_path(name)
            _durable_json(parent / name, result)
        except Exception:
            pass
        try:
            print('OPENRACKET_OBJECT_HASH_TRANSPORT_INCOMPLETE ' +
                  packed({'complete': False, 'stage': 'build',
                          'error_type': type(error).__name__}).decode('ascii'), flush=True)
        except Exception:
            pass
        raise

def _envelope(value):
    if isinstance(value, (str, bytes)):
        need(len(value) <= ENVELOPE_LIMIT, 'Envelope exceeds 6 MiB')
        value = strict_json(value)
    need(type(value) is dict and set(value) == ENVELOPE_FIELDS
         and value['schema'] == ENVELOPE_SCHEMA and value['encoding'] == 'xz+base64',
         'Invalid envelope shape')
    integer(value['compressed_bytes'], 1, COMPRESSED_LIMIT, 'compressed size')
    integer(value['raw_bytes'], 0, TOTAL_LIMIT, 'raw aggregate')
    integer(value['uncompressed_bytes'], len(MAGIC) + 4,
            TOTAL_LIMIT + MANIFEST_LIMIT + len(MAGIC) + 4, 'uncompressed size')
    integer(value['file_count'], 1, FILE_COUNT_LIMIT, 'file count')
    digest(value['compressed_sha256'])
    digest(value['manifest_sha256'])
    chunks = value['chunks']
    count = (value['compressed_bytes'] + BASE64_CHUNK - 1) // BASE64_CHUNK
    need(type(chunks) is list and len(chunks) == count, 'Incorrect compressed chunk count')
    raw = bytearray()
    for i, chunk in enumerate(chunks):
        need(type(chunk) is str and 0 < len(chunk) <= BASE64_CHUNK * 4 // 3,
             'Invalid bounded base64 chunk')
        try:
            part = base64.b64decode(chunk, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError('Invalid base64') from error
        expected = min(BASE64_CHUNK, value['compressed_bytes'] - i * BASE64_CHUNK)
        need(len(part) == expected and base64.b64encode(part).decode('ascii') == chunk,
             'Noncanonical or incorrectly sized base64 chunk')
        raw.extend(part)
    need(len(raw) == value['compressed_bytes'] and sha(raw) == value['compressed_sha256'],
         'Compressed byte SHA-256 mismatch')
    return value, bytes(raw)


class _XZReader:
    def __init__(self, raw, limit):
        self.raw, self.position, self.total, self.buffer = raw, 0, 0, b''
        self.limit = limit
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ,
                                           memlimit=DECOMPRESSION_MEMORY_LIMIT)

    def _fill(self):
        while not self.buffer and not self.decoder.eof:
            if self.decoder.needs_input:
                need(self.position < len(self.raw), 'Truncated XZ stream')
                part = self.raw[self.position:self.position + IO_CHUNK]
                self.position += len(part)
            else:
                part = b''
            try:
                self.buffer = self.decoder.decompress(part, max_length=min(IO_CHUNK, self.limit - self.total + 1))
            except lzma.LZMAError as error:
                raise ValueError('Invalid XZ stream or dictionary exceeds memory bound') from error
            self.total += len(self.buffer)
            need(self.total <= self.limit, 'Decompressed byte bound exceeded')
            if self.decoder.eof:
                need(not self.decoder.unused_data and self.position == len(self.raw), 'Trailing compressed data or concatenated XZ stream')
                need(self.decoder.check == lzma.CHECK_SHA256, 'XZ SHA-256 integrity check required')

    def read(self, size):
        out = bytearray()
        while len(out) < size:
            self._fill()
            if not self.buffer:
                break
            take = min(size - len(out), len(self.buffer))
            out.extend(self.buffer[:take])
            self.buffer = self.buffer[take:]
        return bytes(out)

    def exact(self, size):
        raw = self.read(size)
        need(len(raw) == size, 'Truncated uncompressed bundle')
        return raw

    def finish(self):
        need(self.read(1) == b'' and self.decoder.eof and self.total == self.limit,
             'Trailing or missing uncompressed data')


def decode_verified(document, output):
    """Validate first, publish only verified bytes in a fresh private directory.

    document is a dict or bounded JSON bytes/string. No tar, links, permissions,
    subprocess, imports from restored files, or executable actions are accepted.
    """
    envelope, compressed = _envelope(document)
    reader = _XZReader(compressed, envelope['uncompressed_bytes'])
    need(reader.exact(len(MAGIC)) == MAGIC, 'Invalid bundle magic/version')
    size = struct.unpack('>I', reader.exact(4))[0]
    integer(size, 1, MANIFEST_LIMIT, 'manifest size')
    raw_manifest = reader.exact(size)
    need(sha(raw_manifest) == envelope['manifest_sha256'], 'Manifest raw SHA-256 mismatch')
    manifest = strict_json(raw_manifest)
    need(packed(manifest) == raw_manifest, 'Noncanonical manifest JSON')
    total = validate_manifest(manifest)
    need(total == envelope['raw_bytes'] and len(manifest['files']) == envelope['file_count']
         and len(MAGIC) + 4 + size + total == envelope['uncompressed_bytes'], 'Envelope/manifest accounting mismatch')
    output = P(output)
    parent = physical_root(output.parent.resolve(strict=True))
    output = parent / output.name
    safe_path(output.name)
    need(not output.exists() and not output.is_symlink(), 'Fresh decode output directory required')
    temporary = P(tempfile.mkdtemp(prefix='.verified-bundle-', dir=parent))
    try:
        for row in manifest['files']:
            target = temporary.joinpath(*safe_path(row['path']))
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as stream:
                os.chmod(target, 0o600)
                remaining, h = row['bytes'], hashlib.sha256()
                while remaining:
                    block = reader.exact(min(IO_CHUNK, remaining))
                    stream.write(block)
                    h.update(block)
                    remaining -= len(block)
                need(h.hexdigest() == row['sha256'], 'Raw file SHA-256 mismatch: ' + row['path'])
                stream.flush()
                os.fsync(stream.fileno())
        reader.finish()
        need(not output.exists() and not output.is_symlink(), 'Decode destination appeared during verification')
        temporary.rename(output)
        temporary = None
        return {'schema': 'object-hash-verified-transport/v1', 'transport_verified': True,
                'compressed_sha256': envelope['compressed_sha256'],
                'compressed_bytes': envelope['compressed_bytes'], 'raw_bytes': total,
                'file_count': len(manifest['files']), 'files': manifest['files'],
                'output': str(output)}
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)


def emit_bundle(bundle, emitter, transport_dir):
    """Emit a build_bundle envelope exactly once, via the unchanged emitter.

    A durable attempt marker precedes emission. Any partial failure prevents a
    second attempt in this transport directory, even with a different bundle.
    Full failure details remain local; one bounded explicit incomplete marker is
    printed if possible. This method never retries or recompresses.
    """
    directory = physical_root(transport_dir)
    attempted = False
    try:
        envelope, _ = _envelope(bundle)
        label_dir = directory / ('object-hash-bundle-' + envelope['compressed_sha256'][:16])
        need(not label_dir.exists() and not label_dir.is_symlink(), 'Fresh envelope directory required')
        # Validate and write all material before any output is attempted.
        label_dir.mkdir(mode=0o700)
        target = label_dir / 'supervisor.json'
        _durable_json(target, envelope)
        # Preflight unchanged encoder too: oversize refusal never emits a prefix.
        emitter.encode(envelope)
        _durable_json(directory / 'emission-attempt.json', {
            'schema': 'object-hash-emission-attempt/v1',
            'compressed_sha256': envelope['compressed_sha256'],
            'state': 'one-attempt-no-retry'})
        attempted = True
        emitter.emit(target)
        result = {'schema': 'object-hash-transport-status/v1', 'complete': True,
                  'compressed_bytes': envelope['compressed_bytes'],
                  'compressed_sha256': envelope['compressed_sha256'],
                  'raw_bytes': envelope['raw_bytes'], 'file_count': envelope['file_count'],
                  'label': label_dir.name + '-supervisor'}
        _durable_json(directory / 'emission-result.json', result)
        return result
    except Exception as error:
        result = {'schema': 'object-hash-transport-status/v1', 'complete': False,
                  'emission_attempted': attempted, 'error_type': type(error).__name__,
                  'error': str(error), 'originals_preserved': True}
        # A failed/uncertain prior attempt must never be overwritten or retried.
        failure = directory / 'transport-incomplete.json'
        if not failure.exists() and not failure.is_symlink():
            try:
                _durable_json(failure, result)
            except Exception:
                pass
        try:
            print('OPENRACKET_OBJECT_HASH_TRANSPORT_INCOMPLETE ' +
                  packed({'complete': False, 'error_type': type(error).__name__,
                          'emission_attempted': attempted}).decode('ascii'), flush=True)
        except Exception:
            pass
        return result


def envelope_from_log(log, label=None):
    """Strictly recover this envelope through the unchanged replay log framing.

    Other replay documents are ignored. Multiple matching envelopes require an
    explicit label. Missing/duplicate/reordered framing never yields a document.
    """
    need(type(log) is str and len(log.encode('utf-8')) <= LOG_LIMIT, 'Log exceeds 32 MiB')
    if label is not None:
        need(re.fullmatch(r'object-hash-bundle-[0-9a-f]{16}-supervisor', label) is not None,
             'Invalid object-hash envelope label')
    active, completed, seen = {}, {}, set()
    for line in log.splitlines():
        marker = re.search(r'OPENRACKET_REPLAY_(DOCUMENT_BEGIN|DOCUMENT_JSON|ARRAY_JSON|DOCUMENT_END) (.*)$', line)
        if not marker:
            continue
        # Never accept duplicate JSON fields in an examined transport frame.
        need(len(marker.group(0).encode('utf-8')) < 60000, 'Replay line bound exceeded')
        data = strict_json(marker.group(2))
        need(type(data) is dict and type(data.get('label')) is str, 'Invalid replay frame')
        name = data['label']
        if re.fullmatch(r'object-hash-bundle-[0-9a-f]{16}-supervisor', name) is None or (label is not None and name != label):
            continue
        kind = marker.group(1)
        if kind == 'DOCUMENT_BEGIN':
            need(set(data) == {'label', 'sha256', 'arrays'} and name not in seen, 'Duplicate/invalid document begin')
            digest(data['sha256'])
            integer(data['arrays'], 0, 1, 'array count')
            seen.add(name)
            active[name] = {'header': data, 'data': None, 'rows': []}
            continue
        need(name in active, 'Replay frame without begin')
        state = active[name]
        if kind == 'DOCUMENT_JSON':
            need(set(data) == {'label', 'data'} and state['data'] is None and not state['rows'], 'Duplicate/reordered document JSON')
            need(type(data['data']) is dict and set(data['data']) == ENVELOPE_FIELDS, 'Invalid envelope skeleton')
            state['data'] = data['data']
        elif kind == 'ARRAY_JSON':
            need(set(data) == {'label', 'id', 'index', 'items'} and state['data'] is not None
                 and type(data['id']) is int and data['id'] == 0
                 and type(data['index']) is int and data['index'] == len(state['rows'])
                 and type(data['items']) is list and 0 < len(data['items']) <= 20, 'Invalid/reordered array chunk')
            need(all(type(x) is str and len(x) <= BASE64_CHUNK * 4 // 3 for x in data['items']), 'Invalid array items')
            state['rows'].extend(data['items'])
            need(len(state['rows']) <= (COMPRESSED_LIMIT + BASE64_CHUNK - 1) // BASE64_CHUNK, 'Too many array items')
        else:
            need(set(data) == {'label'} and state['data'] is not None, 'Invalid document end')
            value = dict(state['data'])
            chunks = value['chunks']
            if type(chunks) is dict:
                need(set(chunks) == {'__openracket_log_array__', 'length', 'sha256'}
                     and type(chunks['__openracket_log_array__']) is int and chunks['__openracket_log_array__'] == 0
                     and type(chunks['length']) is int and chunks['length'] == len(state['rows'])
                     and state['header']['arrays'] == 1, 'Invalid array descriptor')
                digest(chunks['sha256'])
                need(sha(packed(state['rows'])) == chunks['sha256'], 'Array canonical hash mismatch')
                value['chunks'] = state['rows']
            else:
                need(type(chunks) is list and state['header']['arrays'] == 0 and not state['rows'], 'Unexpected array data')
            need(sha(packed(value)) == state['header']['sha256'], 'Envelope canonical hash mismatch')
            _envelope(value)
            need(name == 'object-hash-bundle-' + value['compressed_sha256'][:16] + '-supervisor', 'Envelope label/hash mismatch')
            completed[name] = value
            del active[name]
    need(not active, 'Truncated envelope document')
    need(len(completed) == 1, 'Exactly one complete envelope required; select a label if needed')
    return next(iter(completed.values()))
