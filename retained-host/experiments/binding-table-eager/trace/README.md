# Unchanged worker traces for the binding-table experiment

This source-only subtree reuses the proven xref worker capture and bounded
annotation contract. It does not patch xref, traversals, online-comp, GUI code,
the native host or telemetry. No raw capture is edited or relabeled internally.

All four fresh worker processes run the byte-identical `native-trace.rkt --mode
stock`. The outer runtime clone and binding environment distinguish the four
experiment arms. Their `runtime.mode` stays `stock`, activation stays
`unexported`, and the xref flag stays unset, including in the binding-enabled arm.
The original stock xref, traversals and online-comp hashes are required in every
capture. Passing the binding experiment's GUI manifest is rejected.

`compare-binding-trace.py` imports the unchanged proven projection and strict
validator. Its comparison and CLI are mechanically copied from the proven source
with only: external arm names, all-four stock-xref validation, manifest-location
and original-xref-pin guard, and truthful report scope. `generate-comparator.py`
records seven exact source SHA256 pins and regenerates that narrow wrapper.
`upstream/` preserves the original relative manifest/tests layout and every
copied file byte-for-byte. The source provenance is
`openracket-recovery/publication-38/retained-host/experiments/xref-reply/`
(the six files in `tests/` and its adjacent `manifest.json`).
`TRACE-SEMANTICS.md` is a historical source-backed
review from the xref experiment, not evidence of this experiment's captures.

## Exact source/Python checks (safe without Racket)

From the binding experiment root:

```sh
python3 trace/generate-comparator.py --check
python3 -m unittest discover -s trace -p 'test_binding_trace.py' -v
python3 -m unittest discover -s trace/upstream/tests -p 'test_compare_trace*.py' -v
```

The wrapper suite inherits every original semantic mutation test, and adds
all-four-slot stock metadata/source-pin/completion negatives, fake xref off/on
rejection, timeout mismatch, wrong-manifest rejection, raw-byte preservation,
CLI failure/hash checks, and exact generator/pin/function-identity checks.
These are synthetic Python tests. They establish no native success.

## Native worker capture CLI (for the separately authorized native matrix)

Use four fresh processes in the matrix's disposable source-verified runtime
clones and its existing profile/compiled-cache isolation. Each variable below
must name the corresponding absolute clone root, containing `bin/racket`.
The native source resolves each module inside that clone and verifies its hash.
Do not run these commands against production or a retained delivered preview.
From the binding experiment root, with `STOCK_ROOT`, `STOCK_AGAIN_ROOT`,
`BINDING_OFF_ROOT`, and `BINDING_ON_ROOT` assigned by the matrix:

```sh
mkdir -p trace/captures
env -u OPENRACKET_XREF_REPLY_CELL -u OPENRACKET_BINDING_TABLE_INDEX \
  "$STOCK_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt \
  --mode stock --runtime-root "$STOCK_ROOT" --timeout 30 \
  --output trace/captures/stock.json
env -u OPENRACKET_XREF_REPLY_CELL -u OPENRACKET_BINDING_TABLE_INDEX \
  "$STOCK_AGAIN_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt \
  --mode stock --runtime-root "$STOCK_AGAIN_ROOT" --timeout 30 \
  --output trace/captures/stock-again.json
env -u OPENRACKET_XREF_REPLY_CELL OPENRACKET_BINDING_TABLE_INDEX=0 \
  "$BINDING_OFF_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt \
  --mode stock --runtime-root "$BINDING_OFF_ROOT" --timeout 30 \
  --output trace/captures/binding-candidate-off.json
env -u OPENRACKET_XREF_REPLY_CELL OPENRACKET_BINDING_TABLE_INDEX=1 \
  "$BINDING_ON_ROOT/bin/racket" trace/upstream/tests/native-trace.rkt \
  --mode stock --runtime-root "$BINDING_ON_ROOT" --timeout 30 \
  --output trace/captures/binding-candidate-on.json
```

## Compare the original raw captures

```sh
python3 trace/compare-binding-trace.py \
  trace/captures/stock.json trace/captures/stock-again.json \
  trace/captures/binding-candidate-off.json trace/captures/binding-candidate-on.json \
  > trace/captures/comparison.json
```

Optional `--manifest trace/upstream/manifest.json` is the same as the default.
Never substitute the parent binding-GUI manifest. Successful output includes
raw input SHA256 hashes, stock semantic stability, targeted annotation equality,
exact raw-order diagnostics, paint-order variation positions, fixture and
annotation/rename-answer counts. Non-equivalence or invalid evidence exits 1.
Raw-order equality is separately reported and may be false even on pristine
stock controls. It is never silently presented as exact trace equality.

The labels `stock`, `stock-again`, `binding-candidate-off`, and
`binding-candidate-on` describe caller-supplied outer arms, not authenticated GUI
activation. There is no `actual_enabled_activation: true` result from this
wrapper. `binding_gui_activation` explicitly says it is unassessed. Actual GUI
activation/hits, complete binding graph, navigation, first-exposure work and
performance must be established by the separate native GUI/telemetry gates.
This gate proves only the bounded completed worker annotation/projection and
five-query rename contract when real valid captures pass. Transient GUI replay,
paint/pixels, arbitrary programs/rename strings and timing are outside its claim.
