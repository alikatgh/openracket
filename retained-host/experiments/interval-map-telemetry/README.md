# Completed-GUI interval-map comparison

Three fresh matched macOS Racket 9.3 stock/candidate pairs open the same 1 MiB
mixed Racket fixture and insert one `x` in its middle comment. The candidate is
only the separately reviewed, default-off `data/interval-map` direct-set tail.
This package measures its effect; it contains no production optimization.

Both arms use the same common GUI observer, with **worker producer points OFF**,
and the same low-rate GUI heartbeat. Actual 256 MiB capacity, online compilation,
coloring, tools and original 20 ms trace/colorer batching remain enabled. All
outcomes, including timeouts and failures, are retained. A native correctness
failure blocks timing; acceptance alone does not establish a speed improvement.

## Required native order

Use independent, writable, deep runtime clones with no mutable hardlinks or links
back to the original distribution. Stock contains the official interval-map;
candidate contains only the reviewed candidate. All earlier scan, budget, xref,
autosave and appearance overlays must be absent. The CI adapter owns runtime
cloning, production application, source witnesses and remote publication.

1. Verify both exact candidate pins in `candidate-source-pins.json` against the
   separately reviewed production manifest. Preserve unchanged skip-list/order
   support pins. Run stock/off/on randomized actual-map differential tests, full
   semantic annotation and real rename-channel comparison, and actual host Check
   Syntax/docs-map equivalence. No timing until those gates pass.
2. In each clone, resolve the parent of the official `module-language.rkt`. Before
   common observer insertion, run from this package:

   ```sh
   python3 native_preflight.py --racket "$RACKET" \
     --pristine-source "$STOCK_PRIVATE" --profile "$PREFLIGHT_PROFILE"
   ```

   Preflight requires zero skips, native reader/lifecycle tests, actual module
   activation refusal cases, cooperative heartbeat tests and the actual isolated
   preference helper tests. Its disposable profile is never a timing profile.
3. Insert the identical, pinned common observer into each clone:

   ```sh
   python3 prepare_gui.py --diagnostic-root "$CLONE" --racket "$RACKET"
   ```

   Four stock private-source pins and exact unique anchors must match. Removing
   marked blocks reconstructs stock byte-for-byte. Native compilation must pass.
   Preserve each clone's `openracket-gui-phase-manifest.json` and compile/diff logs.
4. Generate one shared fixture, then run six fresh processes in order
   stock/candidate, candidate/stock, stock/candidate:

   ```sh
   python3 fixtures.py "$FIXTURES"
   python3 capture.py --arm stock --racket "$STOCK_RACKET" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_STOCK"
   python3 capture.py --arm candidate --racket "$CANDIDATE_RACKET" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_CANDIDATE"
   ```

   Output directories must not exist. Do not preinitialize profiles: capture
   creates a distinct empty home/addon, persists only the public memory preference
   using the proven helper, verifies readback, then starts the GUI. It clears
   inherited `OPENRACKET_*`; only candidate sets `OPENRACKET_INTERVAL_MAP_FAST_SET=1`.
   `OPENRACKET_GUI_PHASE_POINTS` is absent in both. CI also clears inherited Racket
   collection/configuration overrides and verifies actual resolved clone paths.
5. For each pair, always run strict read-only acceptance, retaining partial data:

   ```sh
   python3 accept_interval.py --stock "$PAIR_STOCK" --candidate "$PAIR_CANDIDATE" \
     --stock-manifest "$STOCK_CLONE/openracket-gui-phase-manifest.json" \
     --candidate-manifest "$CANDIDATE_CLONE/openracket-gui-phase-manifest.json" \
     > "$PAIR_ACCEPTANCE"
   ```

   Exit 0 plus `accepted:true` and an empty `failures` list is required. Overall
   acceptance additionally requires all six commands and all three strict pairs.
   Do not change caps, timeouts, workload or expected outcomes to pass a failure.

## Workload, endpoints and unchanged bounds

Base fixture: 1,048,576 ASCII characters/bytes, SHA256
`766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`.
Insert `x` at 524139: 1,048,577 characters/bytes, SHA256
`f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
The original disk fixture must stay unchanged.

The actual worker cap must be 268435456 bytes with memory accounting available.
Startup has its original 90-second deadline; all post-edit terminal, application,
lexer, worker-report, heartbeat-join and final verification work shares the original
absolute90-second deadline. The native process bound remains 190 seconds, separate
profile setup 30 seconds, and external process-group cleanup 5 seconds. CI's235-second
outer envelope includes those distinct steps without extending the native bound.

Application completion is the exact stock normal empty-trace branch after the
blue-box/arrow/running-state updates. A lexically retained scalar token follows
original 20 ms continuations and must still be current before stock clears state.
Receipt, queue attempt, callback entry/return, first lexer-valid observation and
actual annotation application completion remain separate timestamps. Application
may finish before terminal receipt. Cancellation/replacement/stale continuations
cannot pass. Final source, lexer and application currentness are rechecked after
the last heartbeat-join GUI yield, within the same deadline. This is not a paint
or physical input-to-photon endpoint.

## Activation and heartbeat

`activation.rkt` checks the already-instantiated actual GUI module's phase-zero
import index and existing `data/interval-map` instance. It never creates a
substitute namespace or loads a new instance for evidence. Only missing-export
uses the documented failure thunk; load/namespace/syntax errors propagate.
Stock requires the export absent and flag unset. Candidate requires its exact
source hash, flag 1 and boolean export true. Acceptance checks actual source files
inside the corresponding clone and unchanged three support-library hashes. This
is a process-wide library change, not proof of exclusive GUI allocation ownership.

Heartbeat starts immediately before fixture open, stops after completed workload
verification, then cooperatively joins using GUI yield and the existing deadline.
An off-GUI producer schedules one low-priority callback every 50 ms **after the
previous handler**, with at most one outstanding callback. It retains intended
scheduled time, submission time and handler time, so producer/GC suspension is
visible separately from queue delay. This is closed-loop pacing; it is not an
independent stream of hardware input or a typing benchmark.

Records are bounded to 4096; overflow/errors/missing coverage fail acceptance.
A submitted callback can drain after stop and is explicitly marked. The frozen
stop-to-last-pre-stop-handler gap remains separate from the last drained handler.
No heartbeat callback/producer does I/O, GC, thread kill or stock custodian changes.
JSON conversion and output happen after endpoints or on failure. All raw rows are
retained for application-window and whole-workload tail analysis.

## Common observation cost and comparison

Common observer/helper bytes match both arms. The four additive source seams are
unchanged from the accepted genuine-GUI diagnostic. Common request hashing,
monitor schema walking, scalar endpoint counters, and post-terminal worker report
writing remain measurement costs. The worker report contains identity only and
an empty producer-point list. No standalone replay, readiness barrier, log receiver,
GC observer or stack sampling is included. This is a common-observer comparison,
not an uninstrumented stock baseline.

Actual registry paths are verified in each clone before comparing typed relative
module/export/monitor/hash identities. Raw absolute module specs and terminal keys
are retained and checked against their own actual registry, never blindly rewritten.
Both arms must match actual source, prefab, pending-next-Run settings, terminal
shape, monitor/trace/rename-row counts and common helper/source hashes. Scalar
counts do not replace the separate full correctness gates.

GUI endpoint allocation/CPU/GC counters have whole-runtime scope and can include
concurrent worker/coloring/autosave/tool activity. Do not infer thread ownership or
sum overlapping intervals. Cumulative allocation is churn, not resident memory.
This harness does not add RSS polling or per-key input. Report elapsed completion,
heartbeat planned/dispatch/gap tails and counter deltas with all failed trials and
small-sample limitations. Do not claim physical display latency or speed until the
actual six matched native observations support it.

`OUTPUT-SCHEMA.json` describes eight bounded output files. Six native-only tests
skip without local Racket; portable tests cannot establish native acceptance.
