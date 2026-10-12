# Bounded object-hash evidence transport

Local portable implementation only; no native eligibility finding is implied.
This changes evidence encoding, not any diagnostic experiment or native gate.
An accepted byte transport is **not** an accepted native result.

## Budget and evidence-selection contract

The GitHub logs connector recovered roughly 8 MiB in a prior run. That observation
is not a documented delivery guarantee. Each completed compressed bundle must be
at most **4,194,304 bytes (4 MiB)**. Its base64 is at most 5,592,408 bytes. The
unchanged replay emitter adds bounded framing, leaving room within the observed
size for other log lines. Smaller bundles can still be truncated by a connector:
only a complete independently verified decode is usable. A final-witness bundle
and ordinary job logs count against the same observed budget; the caller must
account for them rather than assuming every individual 4 MiB allowance is additive.

Required source/.zo/.dep closure receipts, command/environment/outcome records,
failed raw stdout/stderr, actual eligibility observations, and captures remain
exact raw bytes. JSON is never reparsed/reserialized as a replacement for a raw
receipt. Invalid UTF-8, whitespace, invalid or partial JSON, NULs, and zero-length
streams survive unchanged. No evidence item is silently omitted or truncated.

The caller supplies the **complete explicit selection** of required files. This
codec cannot infer semantic completeness from arbitrary filenames. In particular,
the orchestration layer must retain full original/clone tree inventories locally
and select their reviewed summaries instead of their huge raw trees. Those
summaries must carry raw SHA-256, bytes, entry count and tree digest, together with
every changed before/after entry, without truncation. Merely hashing a required
receipt, failed stream, eligibility result, or capture is not a substitute for
transporting it. Failure selecting or summarizing required evidence makes the
whole result incomplete before any bundle is emitted.

## Exact binary format

One XZ stream, using LZMA2, a 16 MiB dictionary, and XZ SHA-256 integrity checking,
compresses this byte sequence:

1. Ten-byte magic/version: `b'OROHBNDL\x00\x01'`.
2. Four-byte unsigned big-endian length of the manifest JSON bytes.
3. Exactly that many manifest bytes.
4. Each file's exact bytes, concatenated in manifest order with no separators.
5. End of stream. No uncompressed or compressed trailing data, padding, second
   stream, archive records, permissions, links, or executable actions are allowed.

The manifest is canonical ASCII JSON, equivalent to Python's
`json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
allow_nan=False).encode('ascii')`:

```json
{"files":[{"bytes":3,"path":"commands/example/stdout.bin","sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}],"schema":"object-hash-bundle-manifest/v1"}
```

Manifest files are strictly lexicographically sorted by path. Fields shown above
are exhaustive. Path components use only ASCII letters, digits, `_`, `-`, and `.`;
empty, `.` and `..` components, trailing dots, Windows device names, separators
other than `/`, absolute paths, and ambiguous/casefold aliases are refused.
Components are at most 128 characters and complete paths at most 512 characters.
File/directory prefix collisions and differently cased shared directories are
also refused. JSON duplicate members, nonfinite constants, noncanonical manifest
serialization and unknown fields are invalid. Integer fields reject booleans.

Hard bounds, enforced by builder and verifier:

- Compressed bytes: 4 MiB
- A raw file: 128 MiB
- Sum of raw files: 256 MiB
- File count: 1–512, including empty files
- Manifest: 1 MiB
- Decompression memory: 64 MiB, independently of the declared expanded length
- Expanded stream: raw total plus bounded manifest and 14-byte header
- JSON envelope: 6 MiB; an input job log: 32 MiB

These bounds accommodate the existing 128 MiB supervisor raw-stream ceiling while
refusing unbounded aggregate output. They are ceilings, not promises that a full
native run fits. The 16 MiB dictionary exposes repetition across source/load maps;
compressor memory is governed by that fixed liblzma configuration, rather than
attacker-controlled XZ filter settings. The verifier enforces its independent
64 MiB liblzma memory ceiling. Expanded files stream to private staging with 64 KiB read/write
chunks; no 256 MiB raw aggregate is allocated in memory. The verifier has no tar
extraction or native-code execution path.

## Envelope and unchanged outer transport

`object-hash-bundle-envelope/v1` is a JSON object with exactly these fields:

- `schema`: `object-hash-bundle-envelope/v1`
- `encoding`: `xz+base64`
- `compressed_bytes`, `compressed_sha256`: exact XZ byte identity
- `uncompressed_bytes`: exact complete expanded stream size
- `manifest_sha256`: exact canonical manifest byte identity
- `raw_bytes`, `file_count`: exact manifest totals
- `chunks`: ordered canonical base64 strings, each encoding exactly 12,288 binary
  bytes except the last, which encodes the remaining 1–12,288 bytes

The unchanged `emit-replay-evidence.py` carries this envelope using its existing
JSON skeleton and bounded array-chunk framing. The envelope filename is
`object-hash-bundle-<first-16-compressed-SHA-hex>/supervisor.json`; the resulting
label appends `-supervisor`. There are no new giant log lines. SHA-256 distinctions
are intentional: outer canonical JSON SHA, exact compressed SHA, manifest SHA,
and each exact raw file SHA are separate checks.

The strict decoder accepts a recovered envelope JSON file or the original replay
frames in a job log. The log route verifies frame shape, order, counts, exact
array/document hashes and duplicate JSON keys itself, without changing the
inherited emitter or decoder. Multiple bundles in one log require `--label`.
Source JSON inside a transported raw file is never modified or interpreted.

## APIs and integration

```python
envelope = transport.build_bundle(paths, reports, output_xz)
status = transport.emit_bundle(envelope, unchanged_emitter, transport_directory)
verified = transport.decode_verified(envelope_or_json_bytes, fresh_output_directory)
```

`paths` is an explicit list of report-relative names or absolute paths underneath
`reports`. The source root must be physical; existing ancestor aliases such as an
explicitly symlinked TMPDIR are canonicalized once. Internal path components are
walked using `O_NOFOLLOW`; only regular files with one link are read. Device/inode,
mode/link count, size, nanosecond mtime/ctime, and hashes are checked across the
hashing and compression passes. These are trusted-run evidence-consistency
checks, not a security claim against a hostile concurrently rewriting filesystem.
The caller should select quiescent report files after command cleanup.

Output parents and the emission directory must already exist. Output files are
fresh and never overwritten. The builder publishes its complete XZ only after
it fits the cap. A build refusal writes an explicit `<output>.incomplete.json`
when possible and emits a small incomplete marker; it raises to its caller. The
orchestrator must keep acceptance red on every exception, including inability to
write that incomplete report. Every original raw file remains where it was.
Temporary unfinished compressed copies may be removed, never original evidence.

Before any emission, the envelope and unchanged emitter encoding are preflighted,
and a durable `emission-attempt.json` is written. `emit_bundle` emits exactly once;
any partial output prevents another attempt in that directory, even with a
different envelope. It never retries, recompresses, shrinks, or drops evidence.
Its result has `complete: false` on failures; full diagnostics stay in a local
`transport-incomplete.json` when writable and a small incomplete marker is printed
when stdout remains writable. Persisting the post-emission completion receipt is
part of success. The caller must require that status and final native verdict
independently, and must not dispatch a fresh retry because the first log is short.

The verifier checks the compressed SHA before decompression, validates the
manifest before writing raw files, verifies every file SHA, and requires exact
XZ EOF/check/accounting before publishing a fresh output directory. Failure
removes private incomplete staging; it never leaves an apparently verified output
directory. Restored files use mode 0600 and directories 0700. Existing output
paths or symlinks are refused. No restored content is executed.

CLI examples:

```sh
python3 decode-object-hash-evidence.py envelope.json verified-main
python3 decode-object-hash-evidence.py job.log verified-main --log
python3 decode-object-hash-evidence.py job.log verified-final --log \
  --label object-hash-bundle-0123456789abcdef-supervisor
```

## Portable verification and synthetic budget estimate

```sh
PYTHONDONTWRITEBYTECODE=1 python3 test-object-hash-transport.py -v
PYTHONDONTWRITEBYTECODE=1 python3 test-object-hash-transport.py --estimate
```

Run both in fresh processes normally and with TMPDIR explicitly set to an
existing symlink. Normal test fixture roots canonicalize once; explicit refusal
fixtures create their own links after that point. Tests cover exact arbitrary
bytes, empty files, source mutations, symlinks/hardlinks/special files, unsafe and
casefold paths, malformed/duplicate JSON, wrong hashes, truncation, corrupt XZ,
compressed/uncompressed trailing data, concatenated streams, memory and expanded
bounds, raw bounds, incompressible cap refusal, existing destinations, outer log
framing, CLI recovery, and no retry after partial emission.

The reproducible estimate is **synthetic, not native execution or native receipts**.
It includes actual helper `.rkt` and API provenance source bytes, two 2,048-module
synthetic receipt maps shaped after `receipt-lib.rkt`, 19 repeated load-audit maps
shaped after `audit-loads.rkt`, and three distinct 384 KiB high-entropy
capture-sized placeholders. Product hashes, module names/counts, captures and
results are synthetic. The code is never run as Racket. Actual native module count,
GUI screenshot sizes, failed-stream entropy and total log budget remain unknown.

Measured with provenance raw SHA-256
`f4e4b1d7ba004a285a566e0d6005ecf1985c933a34133db70a2649b3b1c40771`:

- 71 files, 61,425,829 raw bytes
- 2,077,792 XZ bytes
- 2,771,245 envelope JSON bytes
- 2,781,621 complete emitted log bytes
- 32,890 bytes in the longest emitted line
- All 71 files restored and compared byte-for-byte

The independent worst-case fixture uses 4 MiB + 256 KiB of deterministic
high-entropy bytes. It exceeds the compressed cap, emits an explicit incomplete
report, publishes no bundle, and preserves the original bytes. Compression ratio
is never assumed to rescue oversized evidence. A real over-budget run remains
incomplete with original evidence retained locally; it is not an accepted result.
