# Genuine-GUI producer phase diagnostic

One **common-observer control** and one **producer-observed** fresh macOS Racket 9.3
GUI process each open the mixed-1MiB fixture and insert one `x` in its middle
comment. Stock six-field requests, handler payloads, features, callback order and
20 ms trace batching remain intact. The registered public child-memory preference
is 256 MiB in both arms. This is a gross outcome/overhead check, not a precise
one-pair observer-cost estimate or a production optimization.

No standalone replay, readiness barrier, control channel, logger receiver, GC
observer, extra observation thread, stack sampling or xref hook is included.

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
  lexer and worker-report waits share the original terminal deadline without reset.
- Original fixture stays unchanged on disk. Final editor snapshot and final lexer
  validity are verified separately and retain separate timestamps.

## Source seams and overhead

`prepare_gui.py` contains the four exact stock pins. It adds guarded marked blocks
in module-language.rkt, expanding-place.rkt, syncheck/online-comp.rkt and
syncheck/gui.rkt. With the common flag absent, no helper is dynamically loaded.
Both arms collect common source/settings/registry/cap/terminal/application proof;
only the observed arm collects the ten producer points.

Candidate snapshots are identified by actual source, length and SHA256 at actual
request/new-job entry. Worker hashing happens before child-custodian creation.
Observer state retains bounded scalars, never snapshots, syntax, trace payloads,
editor objects, channels or continuations. Common correlation hashing and the
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
cleanup. Missing, duplicate, stale, nonfinite, clipped, ambiguous or dropped
evidence fails closed. Both arms' actual registries/settings, scalar terminal
shape, monitor message/trace-entry/channel-row counts and source identity must
agree. Actual source/helper bytes and compilation are checked against the manifest.

Observed points cover expansion start/end, handlers, trace build/send, monitor ack,
compile completion and terminal send return. Their allocation/CPU/GC counters have
whole-runtime scope, not thread ownership or causal attribution. Do not subtract
GUI and worker timestamps across places/processes. Scalar schema/count agreement
is not full payload or capability equality. Real channels and stock lifetimes are
untouched. GUI success with replay OOM does not establish an allocator cause.

OUTPUT-SCHEMA.json describes the bounded outputs. Native reader, lifecycle/helper
tests, compilation and both GUI trials remain mandatory CI gates. Four native-only
tests skip without Racket; portable success must not be called native acceptance.
Previous frozen diagnostics remain untouched.
