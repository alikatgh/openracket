# Genuine-GUI nested-arrow and pending-gap diagnostic

One **common-observer plus slice-counter control** and one **nested-arrow and pending-stack probed** fresh macOS Racket 9.3
GUI process each open the mixed-1MiB fixture and insert one `x` in its middle
comment. Stock six-field requests, handler payloads, features, callback order and
20 ms trace batching remain intact. The registered public child-memory preference
is 256 MiB in both arms. This is a gross outcome/overhead check, not a precise
one-pair observer-cost estimate or a production optimization.

No standalone replay, readiness barrier, control channel, logger receiver, GC
observer, heartbeat or xref hook is included. The observed arm adds one bounded
pending-continuation stack-sampler thread plus nested original-arrow timings.
The worker producer-point flag is OFF in both arms. The separate
OPENRACKET_GUI_APPLICATION_POINTS flag enables all detailed observations only
for the observed arm; control retains the common observer and slice counters.

## CI order and commands

Native execution/publication belongs to the authorized CI worker. Do not install a
runtime or attempt a local GUI. Copy the final allowlist from the reviewed immutable
freeze into a **writable** package directory (`PACKAGE`). Independently clone the
approved stock distribution into `CLONE`; do not use hardlinked or linked source
files, patch the stock distribution, or change a previous frozen diagnostic.
`RACKET` must resolve inside `CLONE`. Use absolute paths. Clear inherited
`OPENRACKET_*` variables for preparation; capture clears them itself.

1. Before patching, resolve `STOCK_PRIVATE`: run the cloned runtime with
   `-e '(path->string (collection-file-path "module-language.rkt" "drracket" "private"))'`
   and use the returned file's parent directory. Retain the four original files
   for source/native tests. No GUI arm profile is initialized at this step.
2. From `PACKAGE`, run the mandatory headless gates before patching:

   ```sh
   python3 native_preflight.py --racket "$RACKET" \
     --pristine-source "$STOCK_PRIVATE" --profile "$PREFLIGHT_PROFILE"
   ```

   `PREFLIGHT_PROFILE` is a separate disposable test profile, never an arm profile.
   All Python and Racket lifecycle/reader/default-off/helper tests must pass with
   **zero skips**. These headless gates do not establish GUI completion.
3. Patch and compile only the independent clone:

   ```sh
   python3 prepare_gui.py --diagnostic-root "$CLONE" --racket "$RACKET"
   ```

   All four source pins and unique anchors must match. Removing marked insertions
   reconstructs stock source byte-for-byte. Native `raco make` must pass. Preserve
   the clone's `openracket-gui-phase-manifest.json`,
   `openracket-gui-phase-source.diff` and `openracket-gui-phase-compile.log`.
4. Generate the unchanged fixture and run exactly one process per arm:

   ```sh
   python3 fixtures.py "$FIXTURES"
   python3 capture.py --arm control --racket "$RACKET" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$CONTROL"
   python3 capture.py --arm observed --racket "$RACKET" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$OBSERVED"
   ```

   `CONTROL` and `OBSERVED` must not already exist. **Do not precreate or initialize
   their profiles.** Each launcher creates its own empty `profile`, configures its
   distinct empty `addon`, runs the exact proven memory helper once, verifies the
   persisted one-key delta, and only then creates its diagnostic marker and starts
   the GUI. It never recreates the profile after writing 256. Do not reuse the
   preflight profile. Preserve partial evidence when an arm fails; independently
   run the other arm and always run acceptance to classify the pair.
5. Run read-only acceptance:

   ```sh
   python3 accept_gui.py --control "$CONTROL" --observed "$OBSERVED" \
     --manifest "$CLONE/openracket-gui-phase-manifest.json" > "$ACCEPTANCE_JSON"
   ```

   Only exit 0 with `accepted: true` passes. Do not adjust the cap, timeouts,
   settings, expected snapshot or counts to convert a failure into a pass.

## Workload and bounds

- Base: 1,048,576 ASCII characters/bytes, SHA256
  `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`.
- Insert `x` at 524139, yielding 1,048,577 characters/bytes, SHA256
  `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
- Actual public preference/worker cap 268435456 bytes; actual memory accounting
  must be available. Online compilation and coloring remain enabled.
- Existing 90-second startup and 90-second post-edit absolute deadlines, 190-second
  process limit, 30-second setup, 5-second external process-group cleanup. Application,
  lexer, worker-report and cooperative sampler-join waits share the original terminal
  deadline without reset. The outer CI bound remains 235 seconds.
- Original fixture stays unchanged on disk. Final editor snapshot and final lexer
  validity are verified separately and retain separate timestamps.

## Source seams and overhead

`prepare_gui.py` contains the four exact stock pins. It adds guarded marked blocks
in module-language.rkt, expanding-place.rkt, syncheck/online-comp.rkt and
syncheck/gui.rkt. With the common flag absent, no helper is dynamically loaded.
Both arms collect common source/settings/registry/cap/terminal/application proof;
both collect identical scalar actual-batch/yield/resume counters; only the observed
arm collects application/nested-arrow timing and bounded pending-handler stacks. The successful 0535 common gui-observer.rkt is
byte-identical. Existing producer helper calls remain, but collect no points in
either arm.

Candidate snapshots are identified by actual source, length and SHA256 at actual
request/new-job entry. Worker hashing happens before child-custodian creation.
Observer state retains bounded scalars and immediately rendered stack text, never
snapshots, syntax, trace payloads, editor objects, channels or continuations. The
sampler has only a weak handler reference between captures; transient public
continuation conversion can have unbounded depth/cost. Common correlation hashing and the
trace-schema walk are observer work and included in gross overhead.

Pending-thread/GUI hooks do no reporting I/O. The host reads the in-memory scalar
summary and writes it once after endpoints, or once on failure. Complete parsed
worker-init and phase files are cached, not reread every wait tick. Worker init
writes one common bounded identity/accounting report before requests.

The existing original-custodian result-forwarder writes worker-phase-1.json after
its unchanged actual handler-results send returns. Both arms emit this common
identity report; the control's points list is empty. Post-terminal report writing
can overlap GUI application and belongs in the disclosed gross overhead.

The source-proven application endpoint is the stock normal empty-trace branch,
after blue-box/arrow updates, running-color removal and mode reset. The captured
scalar request/generation token must still be live immediately before stock clears
its state. Cancellation, replacement and stale queued continuations cannot pass.
Actual receipt, queue attempt, callback entry/return and application completion
have distinct labels. Application can finish before terminal arrival, so its
timeline is checked independently. Completion does not measure painting.

## Acceptance and interpretation

Each arm requires exactly one matching final request/job, actual handler-results
with positive compiled bytes, positive clean monitor trace with real
place-channel-bearing rename rows, a current terminal callback, a current normal
noncancelled application endpoint, unchanged final source, valid lexer and complete
cleanup. Missing, duplicate, stale, nonfinite, identity-clipped, ambiguous or dropped
required evidence fails closed. Both arms' actual registries/settings, scalar terminal
shape, monitor message/trace-entry/channel-row counts and source identity must
agree. Actual source/helper bytes and compilation are checked against the manifest.

The worker report contains no producer points in either arm. Existing common
GUI endpoint allocation/CPU/GC counters retain their whole-runtime scope, not
thread ownership or causal attribution. Do not subtract GUI and worker timestamps
across places/processes. Scalar schema/count agreement
is not full payload or capability equality. Real channels and stock lifetimes are
untouched. GUI success with replay OOM does not establish an allocator cause.

OUTPUT-SCHEMA.json describes the bounded outputs. Native reader, lifecycle/helper
tests, compilation and both GUI trials remain mandatory CI gates. Eight native-only
tests skip without Racket; portable success must not be called native acceptance.
Previous frozen diagnostics remain untouched.

## Required evidence files

Each arm supplies eight files, in this canonical order:
1. capture-host.json
2. capture-supervisor.json
3. gui-observation.json
4. worker-init.json
5. worker-phase-1.json
6. memory-profile.json
7. application-profile.json (64 KiB hard ceiling)
8. queued-samples.json (20 MiB hard ceiling; control contains disabled metadata)

The sampler file retains at most 1,024 pending attempts and eight bounded rendered
frames per stored sample. Honest frame/text truncation is explicit and does not
itself invalidate useful raw evidence. Missing useful source frames, unsafe
handler observations, capture errors, capping or an unjoined sampler fail complete
attribution. Its JSON writer uses control-only escaping; an oversized serialized
file fails reporting rather than truncating to success. Preserve partial files
on any failure; they never establish successful attribution.

## Application timing contract

application-profile.json is a separate <=64 KiB final scalar snapshot. The host
serializes it once after closed GUI work, or once as explicitly nonquiescent partial
failure evidence. It is not serialized while polling. The helper is GUI-thread-only;
failed snapshots must never be treated as coherent concurrent measurements.
At most eight application records retain copied request/generation numbers, fixed
13 tag accumulators, fixed four final-call accumulators and three nested-arrow
accumulators, plus scalar batch and queue state. Each accumulator has count, cumulative wall milliseconds and maximum
wall milliseconds. No per-entry or per-batch rows, payloads, editors, channels,
continuations, filesystem I/O or memory/GC/CPU samples are retained or generated by
the application hooks.

The 13 categories are the exact stock process-trace-element dispatch tags, including
zero-count categories. Before/after scalar calls bracket the one unchanged original
process-trace-element invocation. There is no new per-entry thunk, exception handler,
dynamic-wind or parameterization. Original exceptions and escapes propagate unchanged;
they leave open state and cannot pass acceptance. Classification and counter-update
work mostly lies outside the sampled call interval, but helper return/entry overhead
lies inside it. No estimated overhead is subtracted. Call-wall includes preemption,
GC pauses and nested GUI work if it occurs. Reentrant instrumented calls are recorded
as invalid and rejected, never assigned exclusive ownership.

The four final synchronous expressions are separately timed, in original order:
update-blue-boxes (including argument evaluation), update-drawn-arrows, removal of
the running color, and set-syncheck-running-mode. The reset timer closes before the
existing common application-complete observation. All four must return exactly once.
These calls can initiate later coroutine/cache/timer, arrow/paint and running-indicator
refresh work. Completion is not blue-box-settled, paint completion or all deferred
GUI work. Selection is left at the original fixture edit, with the unchanged focus,
scroll and frame setup. Pointer/viewport-dependent final work is unmeasured context;
no pointer movement or settings changes are introduced to accelerate an arm.

An actual batch starts immediately before the stock initial loop, or at entry to its
existing queued continuation. The original 20 ms test, current-inexact-milliseconds
clock, iteration variable, chunk drain, callback closure, #f queue priority and exact
annotation order remain unchanged. A yielded active interval ends AFTER the original
queue-callback returns, so scheduling cost belongs to active time. Requeue wait begins
at that same boundary and ends at callback entry. It includes the old callback's tail
return, eventspace waiting and any intervening GUI work. It is observed elapsed waiting,
not scheduler-exclusive attribution. A skipped cancelled continuation closes as cancelled.

Active batch totals contain measured entry calls, four synchronous final calls,
loop/dispatch overhead, instrumentation and scheduling. Report these separately:
- measured_entry_call_wall_ms is the sum of the fixed13 call-wall accumulators
- synchronous_final_calls_wall_ms is the sum of the final4 accumulators
- other_batch_wall_ms is active minus those measured intervals; it is not a pure
  observer-cost or CPU estimate
- requeue_wait is measured separately, without overlap with active intervals

The observed profile's active+wait total must reconcile to its own first_batch_start_ms
through last_batch_end_ms. The first boundary is AFTER common application-enter and
the last boundary is AFTER common application-complete, so do not equate this span
with the common application duration. Floating-point accounting tolerance is 1e-5
of the span (minimum scale 1 ms), not a performance threshold. Control retains only
common batch/yield/resume/wait counts, empty tag/final arrays and null timings.
Per-entry condition guards remain in both patched arms; the observed arm additionally
performs scalar attribution. Instrumentation may change slice count. Paired slice
counts are exposed and need not match; both full actual trace counts must still match.

Acceptance additionally requires observed fixed13 sum = entries started = entries
completed = actual received trace_entries; arrow/name-dup + id-set counts = the
independent common monitor rename_capability_rows; all four final counts = 1; batches = yields+1;
waits = resumes = yields; no drops, helper errors, unknown tags, reentrancy, stale events,
unmatched state, open entry/final/batch or queued wait. An enabled producer flag in
either arm fails. All original source/settings/cap/currentness/lexer/cleanup checks
remain mandatory. This is a bounded attribution diagnostic, not a production change.

## Bounded nested-arrow and pending-continuation diagnostic (2026-10-11)

This working tree derives from the exact 0812 application-probe freeze. It adds
observation only; it is not a production change or an optimization candidate.
The four upstream stock source hashes and the 1 MiB first-edit workload remain
pinned. Both GUI arms retain the 256 MiB child limit, original 20 ms replay
scheduler and callback priority, 90-second absolute post-edit deadline,
190-second native-process limit and 235-second outer limit.

Observed-only arrow details time the original add-to-bindings-table boolean
expression and original start/end add-to-range/key expressions. Instrumentation
retains their arguments, guards, short circuit, order, exceptions, multiple
return values and all dynamic last-position calls. Fixed accumulators retain
no editor, arrow, syntax or trace payload. Detail requires one current selected
arrow entry; unrelated method calls outside replay are ignored, while active
context conflicts, reentrancy and unmatched/stale hooks fail attribution.
Bindings true plus false must equal original arrow count; each endpoint count
must equal true bindings. Nested times are already inside inclusive arrow time.

application-pending-box has one GUI writer and stores only an immutable scalar
request/generation/wait-ordinal/queue-return timestamp token. The existing yield
publishes it, and the matching callback entry clears it before the stock liveness
check. A stale callback cannot clear a newer wait. queued-sampler.rkt samples
only while this original replay continuation is pending. It checks the identical
token immediately before and after capture/rendering, discarding races. Its
only persistent GUI-handler reference is weak and its caller verifies the
actual eventspace handler. Samples are unclassified raw stacks at 100 ms cadence,
with at most 1,024 attempts, eight immediately rendered frames per sample and
240 characters per name/source field. Attempts, stored samples, errors,
truncations, missing/dead handlers, capture durations and delayed/missed cadence
are distinct evidence. Reaching the cap stops normally and is incomplete.

Retained sample data is bounded; the public continuation capture/conversion can
create transient contexts and has no hard execution-time bound. Sampling is
sparse and wall-clock biased, not complete queued-gap or CPU attribution. No
stock logger subscription, thread kill, custodian change, or blocking GUI hook
lock is introduced. The host cooperatively stops and joins within the original
absolute deadline, then revalidates request/generation/currentness, empty pending
state, unchanged source and lexer validity. Full sampler summaries are only
published after the worker exits; failures preserve safe partial evidence.
queued-samples.json has a hard 20 MiB serialized ceiling with JSON control-only
escaping. Exceeding that bound fails reporting; it never truncates to success.

Mandatory native preflight includes test_arrow_probe.rkt, generated-original
arrow-method behavior tests and test_queued_sampler.rkt. It must report zero
skips before either real GUI arm. Local Python/static results alone do not prove
native compilation, GUI lifecycle, frame usefulness or diagnostic acceptance.
