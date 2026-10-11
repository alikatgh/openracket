# Actual Check Syntax handler gate

Status: all four actual monitor/go captures completed in macOS native run
38104720998. They contain 436 trace entries, 71 docs annotations and 535 successful
actual rename answers each. Exact ordered stock-to-stock equality fails because
stock reorders hash-enumerated annotation groups. The bounded annotation contract
passes all four preserved captures; its output explicitly retains
`exact_raw_order_equal: false`. See `TRACE-SEMANTICS.md` for source-backed scope.

There is still no local Racket executable. Portable tests use synthetic JSON
solely to test comparator behavior; native claims come from the actual CI files.

## What runs

`native-trace.rkt` resolves and verifies the pinned native modules, loads the
actual exported `drracket/private/syncheck/online-comp` `monitor` and `go`, reads
source-located modules, genuinely expands them in fresh base namespaces, and
consumes the registered handler's normal logger/send-back protocol. It neither
replaces the annotation implementation nor stubs xref or traversal.

Source-reviewed signatures:

- `monitor(send-back, path, the-source, orig-cust)` returns its monitor thread.
- `go(expanded, path, the-source, orig-cust)` waits until send-back completes.
- Documentation vectors contain method, start, end, key, label, path,
  definition-tag, and anchor: eight elements, all retained.
- Arrow vectors contain fourteen elements, including the genuine rename channel
  and request ID. ID-set vectors contain four elements.
- Every emitted rename endpoint is queried using `(list request-id query)` and
  the actual answerer thread. Both true and false replies must be observed.

The bounded comparator recognizes only the nine methods observed in this native
run. Other methods, including future ID-set emissions, fail closed pending review.

Fixtures cover repeated documented `racket/base` bindings, Unicode before source
positions, phase-one references, renamed and prefixed imports, and an imported
local submodule binding with no documentation. Each fixture requires nonempty
documentation and repeated documented references. Missing native docs is a hard
failure. This exercises the handler and xref protocol, not editor rendering.

## Allowed normalization

No trace entries or duplicates are removed or reordered. Numbers retain their
Racket spelling, and all labels, anchors, tags, source positions, request IDs,
symbols and strings are retained.

Only path values below two roots are normalized: the generated temporary fixture
root and the supplied disposable runtime root. The latter must contain the
resolved actual executable and all three resolved, pinned module sources. The
encoded path retains its Unix/Windows convention and every suffix byte. Paths
elsewhere retain every original byte. No global string replacement is used.
Genuine rename channel identities receive encounter-order IDs in the capture;
request IDs and actual answers remain in unchanged raw evidence. The bounded
comparator validates the actual one-channel, consecutive-ID table, then associates
each logical event with its own exact ordered answer vector. No answers are pooled
or detached from their original source/target. Unsupported values fail rather than
receiving an opaque printable placeholder.

## Native commands

Use full Racket 9.3 installations with their native documentation. `STOCK_ROOT`
and `CANDIDATE_ROOT` must be verified disposable installations; the candidate must
already contain this experiment's manifest-pinned overlay. These commands do not
install or patch anything. Set `STOCK_RACKET` and `CANDIDATE_RACKET` to their real
executables. Run from the experiment directory, with an existing `reports/`
directory and fresh output filenames.

```sh
env -u OPENRACKET_XREF_REPLY_CELL "$STOCK_RACKET" tests/native-trace.rkt \
  --runtime-root "$STOCK_ROOT" --mode stock --output reports/trace-stock-a.json
env -u OPENRACKET_XREF_REPLY_CELL "$STOCK_RACKET" tests/native-trace.rkt \
  --runtime-root "$STOCK_ROOT" --mode stock --output reports/trace-stock-b.json
env -u OPENRACKET_XREF_REPLY_CELL "$CANDIDATE_RACKET" tests/native-trace.rkt \
  --runtime-root "$CANDIDATE_ROOT" --mode off --output reports/trace-off.json
env OPENRACKET_XREF_REPLY_CELL=1 "$CANDIDATE_RACKET" tests/native-trace.rkt \
  --runtime-root "$CANDIDATE_ROOT" --mode on --output reports/trace-on.json
python3 tests/compare-trace.py reports/trace-stock-a.json \
  reports/trace-stock-b.json reports/trace-off.json reports/trace-on.json
```

Each command is a fresh process. Native default limits are 30 seconds per fixture,
5 seconds per rename answer, and a hard 180 seconds for the whole loaded suite;
custodians shut down monitors, answerers and xref workers on success or failure.
The fixture limit is recorded and can be explicitly set with `--timeout`; the
whole-suite limit remains 180 seconds. Apply an external subprocess timeout too
when scheduling native CI. Failure does not produce a successful capture file.

The comparator demands stable stock-to-stock bounded annotation semantics before
interpreting off/on. It preserves the complete duplicate-bearing typed inventory,
real-answer associations, order-sensitive docs/menu/color/tooltip/navigation
states, first retained binding metadata, and local/tail/different-binder ordering.
Only homogeneous require-arrow permutations within the identical binder range are
allowed. Native completion, source pins, activation and matching timeouts remain
mandatory. Exact raw-order comparisons and residual require-arrow paint positions
are always reported separately; no deterministic transient rendering or timing
claim is made.

The original exact-order comparator is preserved as `compare-trace-exact.py` with
the same four arguments. It intentionally continues to fail on this native stock
control. Neither raw traces nor native capture code were changed to make it pass.

## Pins and portable checks

| Source | SHA-256 |
| --- | --- |
| Stock xref | `acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7` |
| Candidate xref | Read from `manifest.json` (`d2db0c6860040909c31c8fa9f7945ad5b94da3a03e751791447faeee7c27105f` at preparation) |
| Stock traversals | `bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00` |
| Stock online-comp | `1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5` |

```sh
python3 -m unittest discover -s tests -p test_compare_trace.py -v
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 -m py_compile tests/compare-trace.py tests/compare-trace-exact.py
```

Prepared result: 22 bounded comparator mutation tests, 15 original exact
comparator tests, and 7 source/applier tests pass (44 total). Negative mutations
cover lost/duplicate events, source-only corruption, moved/changed answers, edge
or phase/geometry changes, docs end+1 overlap and menu first-wins behavior,
tooltip/definition/navigation order, first retained duplicate-edge metadata,
local/tail/different-binder ordering, unsupported forms, broken documentation
pairing and unstable stock semantics. The original tests retain activation,
source-pin, completion, Unicode and timeout evidence checks.
