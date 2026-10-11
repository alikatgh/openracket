# Named-style native compatibility controls (source-only)

Native execution, package installation, archive retrieval, remote publication and
CI remain on hold. This package has run only portable Python/static checks. It
adds no production change, observer, substitute editor or performance workload.

## Exact reuse and narrow scope

`PROVENANCE.json` pins every unchanged copy from
`openracket-binding-eager-experiment-freeze-20261011-1230`:

- `native/tests/reference-host-0520.rkt` is the accepted stock host, byte-for-byte.
- Its workflow, appearance workflow and returning-Stop runtime-path dependencies
  are unchanged. All **six** files under `native/tool/` are included with their
  original relative paths, including platform and Cocoa/GTK helper dependencies.
- The complete original `trace/` sources are retained. That subtree's original
  README/generator/comparator/tests are historical binding-experiment references.
  For this named-style experiment use the runner and commands below instead.
- No eager postflight, patched binding GUI, candidate binding source or observer
  is copied into the native control.

Candidate identity is exactly
`openracket-named-style-index-freeze-20261011-1322`, with
`CONTENTS-SHA256.json` SHA256
`5a698f6506e115cf8a7fbe9d80d312fd530ce3fd81e55cd7330cd6b5ba36413c`.
The actual resolved `racket/snip/private/style.rkt` must be stock
`2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0`
or candidate
`74eb24f0d6485187c9700cca421f4299dee67ea092a811d56b737972b2204c6d`.
`RUNTIME-PINS.json` additionally pins the sibling prefs module, unchanged syncheck
GUI/xref/traversals/online-comp, text/color, DrRacket unit, toolbar and interval map.
These exclude earlier binding, autosave, budget, appearance and interval variants
at the named source seams; they are not a whole-installation integrity claim.

The 82-line `native/bootstrap.rkt` resolves the real executable and modules inside
the selected runtime root, verifies hashes, source-loads the actual style module
before GUI imports, checks its phase-zero namespace and exact exports, prints one
source proof, then invokes the unchanged host. Stock requires both candidate
exports absent and an unset flag; candidate-off requires boolean false and `0`;
candidate-on requires boolean true and `1`. Other experiment flags are rejected.
The read-only state export's presence/arity is checked; it is never called and
no styles or lookups are created to manufacture activity.

The host runs only `OPENRACKET_NATIVE_CASE=check-syntax` with stock UI, retaining
its ordinary Run and Check Syntax callbacks, fixed fixture, READY/capture
handshake and 60-second outer acceptance bound. The comparator extracts the
existing original `OPENRACKET_BINDING_GRAPH` line and requires the exact ordered
integer eight-edge fixture, including all four zero spans. Original raw logs are
kept. The unchanged workflow filters same-editor endpoints and removes duplicate
numeric edges. This gate makes **no claim about filtered entries, full table or
getter semantics**. Those are verified by the separate existing full telemetry.
Real-editor/WXME and large-workload instance proofs are separate gates and are
not duplicated here.

The four actual handler/rename processes all invoke the unchanged
`native-trace.rkt --mode stock`; xref remains original and its flag stays unset.
The external arms are stock, stock-again, named-style-candidate-off and
named-style-candidate-on. `generate-named-style-comparator.py` makes a separately
reviewable label-only derivative of the pinned accepted comparator. It retains
the exact original validator, semantic projection, source associations, duplicate
multiplicity, order-sensitive checks, real five-query rename answers and raw-order
diagnostics. A trace result explicitly leaves GUI named-style activation
unassessed. Raw trace JSON is never relabeled or rewritten.

## Safe portable checks

From this package root, with Python 3.12 or later:

```sh
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tests -v
python3 trace/generate-comparator.py --check
python3 trace/generate-named-style-comparator.py --check
python3 -m unittest discover -s trace -p 'test_*trace.py' -v
python3 -m unittest discover -s trace/upstream/tests -p 'test_compare_trace*.py' -v
```

The controls suite tests graph/type/source/environment mutations, exact stock
activation, every zero span, independent failure collection, source/dependency
closure, raw-byte preservation, launch failures, capture failures, malformed
PNGs, 60-second timeout, exact-deadline and late completion. Original and inherited
trace mutation suites remain intact. These checks do not establish native success.

## Future exact native CLI (not authorized or run yet)

Use a fresh authorized macOS synthetic native runner, full official Racket 9.3,
and two independently deep-copied, canonical, nonoverlapping disposable runtime
roots. The existing outer native matrix must retain complete original-installation
before/after witnesses. The stock clone stays pristine. Apply only the exact
frozen named-style candidate to the candidate clone by its reviewed installer.
Do not use a delivered preview, eager-binding clone, test observer or a patched
xref runtime. Do not raise the stock small-fixture memory preference.

Keep test sources in a new disposable writable copy of this whole package, verify
all package hashes, and preserve `native/tests/`, `native/tool/` and
`trace/upstream/manifest.json` relative layout. The authorized matrix's native
preflight must compile every file listed under `native/**/*.rkt` and the unchanged
`trace/upstream/tests/native-trace.rkt` against both selected runtimes using its
per-runtime isolated compiled cache. It must also compile the selected actual
style source. This preflight is required before interpreting a native run. No
compilation or environment creation is performed by this package's runner.

Assign `STOCK_ROOT` and `CANDIDATE_ROOT` to the two existing verified absolute
runtime paths, and `OUTPUT` to a new absolute evidence directory. From the
verified writable package copy, in a clean shell without inherited `OPENRACKET_*`,
Racket collection/config/link/cache overrides or profile overrides:

```sh
python3 scripts/run_native.py \
  --stock-root "$STOCK_ROOT" \
  --candidate-root "$CANDIDATE_ROOT" \
  --output "$OUTPUT" \
  --authorize-native-execution
```

The flag is an operational interlock, not user permission. The runner never
creates/patches runtimes, installs packages, downloads archives, publishes or
starts CI. It refuses non-macOS execution rather than substituting another screen
capture contract. Host processes use `/usr/sbin/screencapture -x`; successful exit
and original bounded PNG bytes, CRCs, dimensions and SHA256 must be present for
acceptance. The capture wait is capped to the smaller of 15 seconds and the
remaining outer bound. Completion observed **at or after** 60 seconds fails.
The ACK still releases host cleanup after a failed capture, but cannot make the
control pass. Raw stdout/stderr, READY, screenshot, process evidence and failure
details remain available. Nothing is overwritten. All three host and all four
trace arms are attempted independently even if a preceding arm fails.

Every process has a distinct fresh preference/addon/XDG profile. Stock and
stock-again leave `OPENRACKET_NAMED_STYLE_INDEX` unset; the candidate arms set
exactly `0` and `1`. Other experiment and resolver flags are refused. Runtimes'
compiled-cache preparation/isolation remains the explicitly required outer
matrix responsibility, matching the accepted native process contract.

For audit, the runner's four actual worker command forms are:

```sh
"$STOCK_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt --mode stock --runtime-root "$STOCK_ROOT" --timeout 30 --output "$OUTPUT/trace-stock/trace.json"
"$STOCK_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt --mode stock --runtime-root "$STOCK_ROOT" --timeout 30 --output "$OUTPUT/trace-stock-again/trace.json"
"$CANDIDATE_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt --mode stock --runtime-root "$CANDIDATE_ROOT" --timeout 30 --output "$OUTPUT/trace-named-style-candidate-off/trace.json"
"$CANDIDATE_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt --mode stock --runtime-root "$CANDIDATE_ROOT" --timeout 30 --output "$OUTPUT/trace-named-style-candidate-on/trace.json"
```

These illustrate subprocess argv only. Do not bypass the runner's exact flag,
fresh-profile or process-bound setup by executing these lines alone. The unchanged
trace suite bounds each fixture at 30 seconds and the suite at 180; the runner
retains the accepted 200-second outer process bound.

Recheck the original raw outputs without any native process:

```sh
python3 scripts/compare_controls.py \
  --stock "$OUTPUT/host-stock" \
  --candidate-off "$OUTPUT/host-candidate-off" \
  --candidate-on "$OUTPUT/host-candidate-on"
python3 trace/compare-named-style-trace.py \
  "$OUTPUT/trace-stock/trace.json" \
  "$OUTPUT/trace-stock-again/trace.json" \
  "$OUTPUT/trace-named-style-candidate-off/trace.json" \
  "$OUTPUT/trace-named-style-candidate-on/trace.json"
```

Passing these gates alone does not establish complete DrRacket compatibility,
physical interaction-to-photon performance, arbitrary-program/rename parity,
editor/WXME semantics, workload cache hits, performance benefit or adoption.
