# Named-style lookup: completed-GUI telemetry

This is a separate, local, default-off telemetry derivative. It does not change the
production optimization or authorize publication/native execution. Production is
pinned to owner freeze `openracket-named-style-index-freeze-20261011-1322`:

- Contents manifest SHA256: `5a698f6506e115cf8a7fbe9d80d312fd530ce3fd81e55cd7330cd6b5ba36413c`
- Production manifest SHA256: `c68afd7ac5a2a2c6b3ca61402ddb0274b22af9b6226edbcef71418e45a81c328`
- Stock `racket/snip/private/style.rkt`: `2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0`
- Candidate style source: `74eb24f0d6485187c9700cca421f4299dee67ea092a811d56b737972b2204c6d`
- Candidate-only flag: `OPENRACKET_NAMED_STYLE_INDEX=1`

The starting telemetry was the untouched 33-file `performance` directory in
`openracket-binding-eager-experiment-freeze-20261011-1230`, whose `SHA256SUMS`
SHA256 is `8c0e0fe66cf94cad688f935346a93fa7792e77b6e3bf7c85d012a1280c4c7fec`.
No predecessor's native results count as a native pass for this derivative.

## Unchanged workload and deadlines

Use three interleaved stock/candidate pairs in this order:
`stock, candidate, candidate, stock, stock, candidate`. Each trial has a fresh
process, profile and addon. Use independent deep runtime clones; no mutable
hardlinks, symlinks to the distribution or alternative experiment overlays.
Only the pinned production style module differs. The four pristine GUI modules,
including `syncheck/gui.rkt`, are identical before the common additive observer
and identical afterward. The transform functions/prefix are unchanged from the
base. Exact byte undo/reapplication is mandatory, not whitespace normalization.

The genuine DrRacket GUI opens the same ASCII 1 MiB file and dispatches one `x`
key event at position 524139. It retains all ordinary stock tools/features,
online compilation, coloring, the 256 MiB worker cap, original 20 ms scheduling,
callback priorities, late annotation application completion, and the original
source/lexer/currentness/clean handler-results/monitor/registry/settings guards.
Producer phase probes are OFF in both arms. No binding, xref, scan, budget,
appearance, autosave, scheduling or worker overlays may be installed.

- Original fixture: 1,048,576 bytes; SHA256 `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`
- Edited snapshot: 1,048,577 characters; SHA256 `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`
- Profile setup: 30 seconds; frame startup: 90 seconds; GUI process: 190 seconds
- One absolute post-edit deadline: `edit_dispatched_monotonic_ms + 90000`
- Process-group cleanup: 5 seconds; CI outer trial: 235 seconds; CI preparation: 285 seconds
- Preparation source discovery shares the original 30-second allowance as two
  15-second queries; native compilation remains 240 seconds. No deadline grows.

The single post-edit deadline includes ordinary readiness, worker metadata,
heartbeat join, untimed binding graph compatibility, final style snapshots,
final source/currentness/lexer checks and final evidence writes. There is no
export grace period. Do not rerun, discard or hide failed/partial trials.

## Gate order and exact command contract

The host owns mandatory production correctness gates before timing: small-style
native stock/candidate differential behavior, cache invalidation/publication and
interruption cases, actual editor lexer/style behavior, and WXME/save semantics.
Require real native success with zero skips. Source review, Python models and
synthetic helper fixtures cannot substitute for these gates.

The following commands are intended for the separately authorized native macOS
Racket 9.3 job. They were not run locally for this derivative.

1. Verify the owner production freeze and style pin. Prepare independent stock
   and candidate runtime clones, installing only the reviewed style candidate in
   its candidate clone. Clear inherited Racket collection/configuration overrides
   in the CI adapter and reject any unapproved overlay. Pass production gates.
2. Run native headless telemetry helper preflight with its own fresh profile:

   ```sh
   python3 native_preflight.py --racket "$RACKET" \
     --pristine-source "$STOCK_PRIVATE" --profile "$PREFLIGHT_PROFILE"
   ```

   It tests both arms' identical transformed native readers, actual existing-module
   refusals, style witness/replacement and malformed state cases, full binding
   graph shape, common observation/metadata, repaired heartbeat, memory profile,
   and a process-fatal RackUnit negative control. `test_gui_native` fails rather
   than skips when native Racket is absent. `native_preflight` rejects every skip.
3. Apply the common observer in each independent clone:

   ```sh
   python3 prepare_gui.py --arm stock --diagnostic-root "$STOCK_CLONE" --racket "$STOCK_RACKET"
   python3 prepare_gui.py --arm candidate --diagnostic-root "$CANDIDATE_CLONE" --racket "$CANDIDATE_RACKET"
   ```

   Preparation resolves the native style source, validates its arm pin/root and
   independent file identity, and stores it in `manifest.style_source`. All four
   GUI sources have exact stock input pins. Retain native compilation logs,
   source diffs and `openracket-gui-phase-manifest.json` for both clones.
4. Generate the shared fixture once and run the six fresh captures in the
   interleaved order above, under the unchanged outer timeout:

   ```sh
   python3 fixtures.py "$FIXTURES"
   python3 capture.py --arm stock --racket "$STOCK_RACKET" \
     --manifest "$STOCK_CLONE/openracket-gui-phase-manifest.json" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_STOCK"
   python3 capture.py --arm candidate --racket "$CANDIDATE_RACKET" \
     --manifest "$CANDIDATE_CLONE/openracket-gui-phase-manifest.json" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_CANDIDATE"
   ```

   Every output directory must be new. Capture clears every inherited
   `OPENRACKET_*` key and sets only the common observer keys plus the candidate's
   named-style flag. The host and activation helper independently reject any
   unexpected key, including a prior experiment flag present with value `0`.
   Prepared source/helper/manifest bytes are checked before profile setup and
   again immediately before GUI startup.
5. Always run read-only strict pair acceptance, including failed pairs:

   ```sh
   python3 accept_named_style.py --stock "$PAIR_STOCK" --candidate "$PAIR_CANDIDATE" \
     --stock-manifest "$STOCK_CLONE/openracket-gui-phase-manifest.json" \
     --candidate-manifest "$CANDIDATE_CLONE/openracket-gui-phase-manifest.json"
   ```

   Success requires exit zero, `accepted:true`, `failures:[]`, and two valid arms.
   Capture exit zero alone is insufficient. Preserve stdout/stderr and every
   output artifact/failed report. The CI adapter owns the six-trial matrix; see
   `CI-CONTRACT.json` for exact cross-trial fields and stopping gates.

## Actual GUI instance, source and activity witness

`activation.rkt` first requires the already-instantiated phase-zero
`racket/gui/base`, `racket/snip/private/style`, and
`drracket/private/syncheck/gui` instances. It never attaches another namespace,
imports an alternative style instance or uses loader exceptions to classify
stock. Only the missing-export thunk handles an absent stock export. Syntax,
namespace, loader, inspector, source and contract failures propagate.

The actual definitions editor's `get-style-list` object must be an instance of
the private style class and the GUI-exported style class. No public/private class
`eq?` assumption is made. The pinned Racket 9.3 `class-internal.rkt`
SHA256 `1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f`,
lines 4397–4402, implements class membership through `class-orig-cls` and
`unwrap-object`, explicitly handling contracted classes and wrapped objects.
A native activation helper fixture also tests an internal object against a
`class/c`-wrapped GUI class export. Candidate export
`openracket-named-style-index-enabled?` must be true; its
`openracket-named-style-index-state` reader must exist and succeed on the actual
editor list via the private, collision-safe local-member key. Stock has neither
export. Both the resolved native style source and actual existing annotation GUI
source must match their independent runtime root, manifest paths and exact hashes.

Five read-only scalar checkpoints are recorded, with monotonic timestamps and
opaque `eq?` list identities, never raw editor/style payloads:

1. `before-open`: after frame sizing/focus and before heartbeat/workload start
2. `after-open`: immediately after the original file-open/length check, before the one edit
3. `ordinary-ready`: immediately after the unchanged completed-work timestamp
4. `post-join`: after heartbeat join and final source/currentness/lexer checks
5. `final`: after untimed full binding graph verification and final rechecks

There is no style-state polling in the hot loop, synthetic `find-named-style`
call, artificial cold reset, prewarming, clock/log hook in the candidate, or
change to ordinary readiness. Every absolute snapshot is retained. If file open
keeps the same style-list instance, `before-open` is the delta baseline. If it
replaces the list, that replacement is explicitly recorded and `after-open` is
the baseline. The list must remain identical from `after-open` through `final`.
Counters from different instances are never subtracted.

Candidate state must be an immutable exact eight-field scalar hash:
`enabled`, `lookups`, `hits`, `rebuilds`, `members-traversed`, `cache-valid`,
`named-entries`, `member-count`. Boolean/count types are checked exactly; bools
are not counts. Counts are diagnostic and unsynchronized. The selected real file
interval to ordinary-ready must have strictly positive lookup and warm-hit
increases, so startup activity alone cannot pass. Natural startup warming of the
same list is allowed and visible in the absolute baseline. Report all rebuild,
traversed-member, cache-validity and size evidence, including aborted builds.

Do not invent synchronized counter identities, `hits <= lookups`, rebuild/visit
ratios, cache-valid-at-end requirements, or global monotonicity claims. Deltas for
all six counts are descriptive, and negative non-activity deltas are retained.
These counters describe only the observed editor style-list instance, not all
style lists or the whole process. A nonpositive lookup/hit increase fails this
activity gate; it does not prove that no candidate code executed anywhere.

## Full graph correctness and interpretation

`binding-export.rkt` retains the complete original public graph shape and digest
check after ordinary readiness and heartbeat join. The two ordinary getters are
untimed; they must return the same public hash identity. There is no binding
candidate state method, first/second getter metric or getter latency threshold.
No claim is made about hidden or deferred work.

Each endpoint must be an exact in-range owning-editor integer triple. The table
must be a nonempty mutable strong `equal?` hash; values must be nonempty immutable
strong `equal?` sets without impersonation. All edges become sorted exact integer
quadruples, Racket-written before SHA256. Every trial's complete digest, counts
and shape witnesses must agree. Raw graphs/source text are not logged.

The unchanged repaired 50 ms closed-loop heartbeat permits only one outstanding
low-priority callback. Producer lateness, dispatch latency, handler gaps,
after-stop drain and pre-stop tail remain distinct. There must be actual
application-window coverage, zero errors/drops/outstanding work and a cooperative
join. No forced GC, thread kill or custodian change is used by the heartbeat.

Report primary file-open/edit readiness and annotation timing, all heartbeat
latencies/tails, all five absolute style snapshots and selected interval deltas,
and every failed trial. Do not sum overlapping intervals. Existing allocation,
GC and CPU counters have whole-runtime scope; style diagnostics have per-list
scope. This is not physical input-to-photon latency. Three pairs do not establish
universal speed, arbitrary-extension semantics, or a reason to enable by default.

## Local verification

```sh
python3 -m unittest test_gui_source test_capture test_accept_gui test_telemetry \
  test_accept_named_style test_prepared_runtime -v
python3 -m py_compile *.py
```

Only these portable Python checks were run locally. Native helper/production/editor
correctness and six genuine GUI trials remain unexecuted under the hold. The
portable suite's success is not native acceptance or performance evidence.
