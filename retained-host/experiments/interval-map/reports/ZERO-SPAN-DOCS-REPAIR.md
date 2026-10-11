# Source-confirmed zero-span docs guard repair

## Conclusion and authoritative evidence

Stock permits a documented identifier with syntax span 0. The pinned
`traversals.rkt` lines 1538–1564 accepts any non-false `syntax-span`, including
zero, and computes `fin = start + span`. `gui.rkt` lines 658–663 passes those
positions unchanged to the blueboxes consumer. `blueboxes-gui.rkt` lines 673–677
stores `(start fin+1 tag path url-tag)` on `[start,fin+1)`. Thus a zero-span source
annotation legitimately produces a one-character stored interval.

This is actual stock behavior, not merely a permissible type: both inspected
native runs 38119983626 and 38120803297 contain 30 zero-span documentation rows
among their 71 docs rows across five fixtures. Examples are repeated-base
`#%app` at 118→118 and `#%datum` at 35→35. See the parent-owned
`STOCK-ZERO-SPAN-DOCS-EVIDENCE.json` for every exact typed row from run38120803297
and its input trace SHA-256. That evidence file is unchanged.

The corrected condition is therefore `stored_start <= stored_end - 1`.
Requiring a strict inequality incorrectly excluded real stock data.

## Narrow change and neighboring assumptions

Only that inequality changes in the native and Python acceptance predicates.
Actual map intervals still require exact integers and strict positive width;
stored ranges still enclose their actual possibly split intervals, remain in
`[0,55]`, and have exactly five fields. Nonoverlap, order, duplicate preservation,
full typed values, source/identity/activation pins and the exact `+` boundary
witness are unchanged. No success schema field is added or removed.

Review of the neighboring assumptions found no further change justified:

- The pinned interval-map source preserves values when splitting intervals;
  enclosing stored geometry, rather than exact stored/key equality, is correct.
- Producer positions are exact source coordinates; all 71 inspected stock docs
  rows have `0 <= start <= fin <= source-length`. The pinned 54-character GUI
  fixture therefore retains its existing maximum stored endpoint 55.
- The consumer constructs one proper five-element list. xref rejects missing
  definition tags/paths before emission. Every inspected actual docs row has a
  typed Unix path and a string anchor; all definition tags have the already
  accepted `form` or `def` heads. Existing support for false anchors is retained.
- The unchanged `+` has source range `[36,37)`, stored range `[36,38)`, its exact
  kernel definition tag, reference path and anchor. Its actual 36/37/38 lookup
  controls and the complete ordered map comparison remain mandatory.

This is a source-pinned fixture gate, not a claim about every possible program,
platform, tag type or synthesized source location. No broader shape relaxation
was made.

## Failure-only diagnostics

Each actual entry's geometry/type guards and success encoding run within one
failure handler. On exception it emits the actual typed bounds and stored value
with entry index and preceding endpoint, then re-raises the original exception.
The recursive next-entry step is outside that handler, preventing repeated
reports for earlier successful entries. A failure writing diagnostics is caught
locally so it cannot replace the original fatal guard exception.

The new GUI-free diagnostic helper is independent of success encoding. It keeps
raw path bytes, distinguishes primitive types and pair structure, and bounds
inspection to 256 items, depth 24, 4096 raw data bytes, and 32768 serialized JSON
bytes. Truncation and unsupported types mark the failure record incomplete.
There is no lossy success fallback. Only failed entries emit
`OPENRACKET_INTERVAL_DOCS_ENTRY_FAILURE`; successful captures keep their original
schema and encoder unchanged. The separate helper is necessary because the
success encoder correctly refuses malformed/out-of-root paths and does not
provide a diagnostic raw-byte cap.

## Verification and remaining uncertainty

- 78 docs comparator/source tests pass, including zero-span one-character and
  source-end positives; missing/extra end+1, empty actual interval, reversed
  range, and out-of-source mutations remain rejected.
- Exact source-reversal tests recover the immutable 0714 postflight hash and
  the original comparator hash, proving the limited acceptance/diagnostic scope.
- Python compilation and static Racket delimiter/string scans pass.
- `racket tests/docs-entry-diagnostic-test.rkt` is prepared to verify exact typed
  entry round-trip and bounds/truncation behavior with the actual helper. It has
  not been run locally. No native/package/runtime action was taken here.

The native host failure reported only the old generic geometry/value message;
there was no captured failing entry. Stock zero-span rows prove the guard was
invalid, but do not prove that every remaining actual GUI entry will satisfy the
unchanged predicates. Native docs capture and full ordered parity are still
pending. If another entry fails, the new bounded diagnostic will expose its
actual values without relaxing acceptance.

Immutable 0714, the earlier frozen trees, and the parent-owned native run reports
remain unchanged. `zero-span-docs-repair.patch` contains the exact source diff.
