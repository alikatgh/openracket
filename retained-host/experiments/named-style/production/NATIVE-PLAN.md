# Native and adoption gates: not executed

The present task authorizes local source/model work only. There is no permission
to install or run local Racket, mutate GitHub, trigger CI or alter a delivered
preview. The current publication hold must be resolved before any remote action.
The scripts below are prepared artifacts, not evidence that these steps ran.

## 1. Native actual-source parity

Use an explicitly authorized official native Racket 9.3 environment. Resolve its
real `racket/snip/private/style.rkt`; verify it is the exact official pinned source.
Verify the same directory's `prefs.rkt` against its separate pin. Then the runner
stages fresh temporary complete stock/candidate modules beside pinned prefs files.
It does not replace the installed source or extract/reimplement the style-list
class. Dependencies come from the native official distribution.

The future command is:

```sh
python scripts/run_native.py \
  --racket /explicit/native/racket \
  --official-style-source /resolved/official/racket/snip/private/style.rkt \
  --prefs /resolved/official/racket/snip/private/prefs.rkt \
  --report /explicit/output/native.json
```

This uses separate fresh native processes for flag unset, `0`, unexpected `yes`,
and `1`. Each compares complete stock and candidate module outcomes, with genuine
`eq?` assertions inside each instance and deterministic object-identity IDs in
cross-module traces. Failure raises and makes the process exit nonzero; nonempty
JSON evidence, minimum checks, exact mode/activation and actual cold/warm counters
are independently validated with exact integer types (booleans/floats are not
counts). Cross-mode complete observation traces must match. A wrong-object-identity
negative-control run must terminate with a **positive** exit code (signals and
timeouts are rejected). Stderr must contain the exact deliberate failure line
`named-style-differential: negative-control-wrong-object-identity: #f != #t` exactly
once, preceded by the exact unique injection line
`OPENRACKET_NAMED_STYLE_NEGATIVE_CONTROL_INJECTED_V1` exactly once. Duplicate,
embedded, altered-operand, wrong-stream and reversed evidence is rejected. No
success or partial JSON record may appear in either output stream, including
prefixed JSON. These conditions and actual-launch evidence are all required. Assertions use uncaught errors, so a test framework's
nonfatal check handler cannot produce false success.

A timeout, launch error or malformed JSON is recorded with the command, existing
time bound and partial stdout/stderr. Other independent modes, publication tests
and negative control still run; the report and runner exit remain failed. Source
tests mock these failures and require complete collection plus terminal failure.
No native failure is converted to a passing or skipped arm.

Coverage prepared in `differential.rkt`:

- Basic, absent, empty, case-sensitive, Unicode/composed/decomposed and ordinary
  mutable input/query strings; exact wrong-type contract outcomes
- Many unnamed insertions followed by named hit/miss, existing-name creation,
  replacement identity, cross-list convert/copy, public override dispatch
- Reentrant before-insertion duplicate creation: absence/inner/final outer lookup
  identity at callbacks, exact notification/state trace
- Actual duplicate base reordering followed by the existing stock exception and
  changed first-member winner; actual join shift reorder and partial state
- Nested batches, failing pre-insertion notification, self-removing callback
- Read-only diagnostics, no prewarm, exact enabled/disabled actual-use counters

The separate full-source **test-only** hooked module is obtained by two reversible
insertions: a parameter declaration and its invocation immediately before the
single cache publication. The production overlay contains neither. It tests
reentrant publication, explicit exception/escape before publication, an old
continuation resuming after a newer publication, and deterministic cross-thread
out-of-order publication with bounded owned workers. No production mutex or
callback is introduced.

Portable source tests deliberately alter the comparator's identity trace and
activation/counter evidence and require rejection. Native results remain unknown
until the real runner finishes. Lexical delimiter checks are not macro expansion
or API validation; a native compile/test failure must be diagnosed, not waved away.

## 2. Genuine GUI/editor/WXME gates still required

The isolated full-module parity test above does **not** establish native editor
integration. Its copied style modules have distinct private style class/interface
identities from an already-loaded `racket/gui` module. Do not mix those copied
classes with stock GUI contracts and call that a rich-file test.

A separately authorized integration run must apply the exact overlay to the
runtime's real pinned source, clear/rebuild the appropriate compiled source using
that environment's approved workflow, and load the editor with that same module
instance. Run stock, flag-off and flag-on arms independently. Verify resolved
source hash, export activation and actual editor style-list evidence before using
any results. Retain exact restoration evidence.

Required integration gates before timing/adoption:

1. Genuine styled/rich editor and WXME save/reload: named styles, base/shift/delta
   relations, indexed order, snips and exact per-position style/contents outcomes.
2. Actual stock lexer token ranges/classifications, parentheses and per-position
   styles after initial coloring and repeated edits/undo.
3. Genuine complete Check Syntax trace and rename, no lost tools/presentation,
   and ordinary final application completion.
4. Both macOS and Linux correctness as applicable; existing native contracts and
   prior tool availability gates must pass independently of this experiment.

The whole-map invalidation cost on anonymous style additions is intentional and
must stay visible; no prewarming or new heuristic is authorized to hide it.

## 3. Timing only after all correctness/use gates

A bounded matched Mac experiment may then compare stock, patched-off and patched-on
with this candidate alone. Keep 256 MiB, original 20 ms batching, queue priority,
real tools and normal completion semantics. Binding, interval, xref, scan and
budget overlays stay absent. Include cold initialization/rebuilds, warm use,
actual total member traversals, named-entry/member counts, allocation/GC/managed
memory, lexer readiness, existing low-rate heartbeat and full ordinary completion.
Sparse samples or a microbenchmark do not justify adoption. Reject regressions in
completion or response tails, or inconclusive use/cold-cost evidence. No speed
claim or adoption decision is made by this source-only package.
