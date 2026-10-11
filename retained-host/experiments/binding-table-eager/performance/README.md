# Eager binding-table completed-GUI measurement

This separate measurement package observes the default-off eager
`OPENRACKET_BINDING_TABLE_EAGER=1` candidate in `drracket/private/syncheck/gui.rkt`.
It does not implement or broaden that optimization. Three fresh macOS Racket 9.3
stock/candidate pairs open the exact 1 MiB fixture and insert one middle-comment
`x`. Both arms use the same common completion observer and repaired 50 ms heartbeat;
worker/type/nested/stack producer probes are absent or off. The 256 MiB worker cap,
all tools, online compilation, coloring, original 20 ms slicing and callback
priorities remain enabled and unchanged.

The candidate uses a private numeric duplicate index and start-range lookup cache
only for same-owning-editor exact integer coordinates. Accepted insertions execute
the original immutable `set-add` and public `hash-set!` immediately. There is no
journal, deferred public write, replay, or getter materialization. Public exposure
or unsupported input disables and drops both private caches. Custom equality/hash
callback parity remains outside this stock-built-in experiment's scope.

Normal navigation does not call the public getter. Ordinary readiness remains the
normal application completion plus final lexer-valid endpoint. The first and second
public getters are measured separately afterward. The candidate's first getter must
be at most 1.000 ms in every trial. This is a preregistered benchmark acceptance
bound approved before eager timing, not a universal real-time guarantee. There is
no rounding, tolerance, GC exemption, outlier deletion, or post-data widening.
Failed/GC-affected rows and all counters remain in the evidence and report.

This is a distinct experiment derived from the untouched lazy telemetry freeze
`openracket-binding-telemetry-freeze-20261011-0959`. That base passed native run
38131918285; its native success is provenance, not an eager native pass. Base
`SHA256SUMS` SHA256 is
`feea9575931d78f2abfa487b65efa8c453ec9b974f65c1346d13a26a2cef9b71`;
base `PACKAGE-MANIFEST.json` SHA256 is
`ad6ee29e4b32a73e48dfbbeac4f6a9f9899d894905dac482a5c3645b68344075`.

## Native gates and order

1. The host/CI adapter must first pass the candidate's native differential,
   duplicate/self-link, unsupported-input, public-exposure, public mutation, failure/interruption invalidation,
   reset/generation and actual host/tool correctness gates. Any failure blocks
   timing. No skip, static scan, synthetic fixture or source review substitutes.
2. Use independent deep runtime clones without mutable hardlinks or symlinks to the
   distribution. Stock has the exact stock GUI source; candidate has only the
   separately reviewed production GUI delta. All other experimental overlays are
   absent. Match `candidate-source-pins.json` to the candidate production manifest.
3. Run native headless measurement-helper preflight before either timing arm:

   ```sh
   python3 native_preflight.py --racket "$RACKET" \
     --pristine-source "$STOCK_PRIVATE" \
     --candidate-source "$CANDIDATE_OVERLAY_GUI" --profile "$PREFLIGHT_PROFILE"
   ```

   Preflight requires zero skips, both transformed-source native readers, common
   observer/metadata tests, actual existing-module activation refusals, repaired
   heartbeat lifecycle tests, public export shape/state/digest tests, the memory
   profile helper tests, and a deliberately failing RackUnit negative control.
   Every native helper test uses a process-fatal RackUnit handler. No local display,
   local installation or fallback interpreter is allowed. The preflight profile
   cannot be reused by a timing trial.
4. Prepare the exact same additive observer transform for each arm:

   ```sh
   python3 prepare_gui.py --arm stock --diagnostic-root "$STOCK_CLONE" --racket "$STOCK_RACKET"
   python3 prepare_gui.py --arm candidate --diagnostic-root "$CANDIDATE_CLONE" --racket "$CANDIDATE_RACKET"
   ```

   Three stock source pins plus the selected arm's exact GUI input must match.
   Removing marked blocks reconstructs that original input byte-for-byte, and
   reapplying the common transform must reproduce the installed source exactly.
   No arbitrary source or path normalization is allowed. Native compilation must
   pass. Retain each clone's manifest, source diff and compilation log.
5. Generate one shared fixture and run six new processes/profiles/addons in order
   stock/candidate, candidate/stock, stock/candidate:

   ```sh
   python3 fixtures.py "$FIXTURES"
   python3 capture.py --arm stock --racket "$STOCK_RACKET" \
     --manifest "$STOCK_CLONE/openracket-gui-phase-manifest.json" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_STOCK"
   python3 capture.py --arm candidate --racket "$CANDIDATE_RACKET" \
     --manifest "$CANDIDATE_CLONE/openracket-gui-phase-manifest.json" \
     --fixture "$FIXTURES/mixed-1mib.rkt" --output "$PAIR_CANDIDATE"
   ```

   Each output directory must be new. Capture creates a fresh profile/addon and
   persists only the authorized public memory preference through the unchanged
   helper. All inherited `OPENRACKET_*` keys are cleared. Candidate alone receives
   `OPENRACKET_BINDING_TABLE_EAGER=1`; both have producer phase points disabled.
   The host and activation probe independently reject every unexpected
   `OPENRACKET_*` key, including prior experiment flags even if set to `0`.
   CI clears inherited Racket collection/configuration overrides and verifies the
   actual runtime source locations. Capture verifies the full prepared manifest
   before profile setup and again immediately before GUI startup, using the
   verified transformed GUI hash rather than the production source hash.
6. Always run strict read-only pair acceptance, retaining all partial evidence:

   ```sh
   python3 accept_binding.py --stock "$PAIR_STOCK" --candidate "$PAIR_CANDIDATE" \
     --stock-manifest "$STOCK_CLONE/openracket-gui-phase-manifest.json" \
     --candidate-manifest "$CANDIDATE_CLONE/openracket-gui-phase-manifest.json"
   ```

   Success requires exit 0, `accepted:true`, and `failures:[]`. Across all six
   accepted trials, CI additionally requires exact equality of the complete
   `arms[arm].binding_export.export` object: canonical digest, key count, edge
   count and shape witnesses. Compare actual source/prefab/settings/terminal/
   monitor/typed registry evidence across all six and require six distinct fresh
   profile/addon paths. Pair success alone is not matrix success or a speed claim.

## Exact workload and shared bounds

The unchanged 1,048,576-byte ASCII fixture has SHA256
`766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`.
Insert one `x` at position 524139. The resulting 1,048,577-character snapshot has
SHA256 `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
The disk fixture remains unchanged. Actual worker cap is 268435456 bytes, with
memory accounting available.

Bounds remain 30 seconds for profile preparation, 90 seconds for GUI startup,
190 seconds for the native process and 5 seconds for process-group cleanup.
There is one absolute post-edit 90-second deadline for terminal/application/lexer/
worker metadata, heartbeat join, both public getters, graph verification and final
source/currentness checks. This revision explicitly anchors that deadline to
`edit_dispatched_monotonic_ms + 90000`, tightening the earlier 0610 construction
that started it a few lines later. Acceptance verifies this exact relation.
The primary application timestamps and completion seam are unchanged.

## Activation and public exposure evidence

Distinct output labels are `gui_binding_table_eager_activation` for activation,
`binding-table-eager-public-exposure` for export, and `binding-table-eager` for the
supervisor experiment. The activation Boolean field is `binding_eager_enabled`.
The validator rejects prior experiment labels and state schemas.

`activation.rkt` resolves the actual GUI module and requires its existing phase-zero
namespace before reading its activation export. It cannot instantiate another
module, inspect an unrelated dependency, attach a namespace or substitute a worker
instance. Only the missing-export thunk classifies stock; namespace/load/inspector/
syntax failures remain errors. Stock requires absent export and unset flag;
candidate requires the matching transformed GUI hash, flag `1` and boolean export
`openracket-binding-table-eager-enabled?` equal to true.

After ordinary completion, heartbeat stop/join and post-join source verification,
`binding-export.rkt` records scalar state, times the first public getter, records
state, times the second getter, and requires identical returned hash identity and
unchanged second state. No reporting callback, full graph walk or file write is
inside either command's start/end snapshots.

Stock must lack `openracket:get-binding-table-eager-state`. Candidate state has
exactly these fields: `enabled`, `active`, `in_flight`, `generation`, `accepted`,
`duplicates`, `eager_writes`, `stock_calls`, `pending`, `materializations`,
`public_keys`, `indexed_edges`, `cached_starts`, `exposed`,
`unsupported_fallbacks`, `failure_fallbacks`, and `fallback_reason`.

Before the first getter, enabled/active must be true; in_flight/exposed false;
accepted = eager_writes = indexed_edges > 0; cached_starts = public_keys > 0;
generation > 0; pending/materializations/stock_calls/both fallback counters zero;
fallback_reason false. `public_keys` is the actual constant-time public hash-count.
The first getter must set active false and exposed true, clear both private-cache
counts, preserve accepted/duplicates/eager_writes/public_keys/generation, and use
`public-exposure` reason. All zero counters and in_flight remain unchanged. Second
state must equal first. Full exported edge_count = accepted and key_count =
public_keys. Every Boolean and exact nonnegative integer is type-checked.

The pair validator applies the candidate first-getter bound to the unrounded
first_end.monotonic_ms - first_start.monotonic_ms. Bound failure keeps the complete
structurally valid arm report, graph digest, states, timestamps, allocation/GC/CPU
counters, and second-getter duration. Structurally invalid arms retain partial raw
scalar export evidence. The bound does not alter stock or second-getter timing. `valid:true` describes
structurally valid arm evidence; `first_getter_bound_passed:false` can coexist with
it, but necessarily makes the pair `accepted:false` with an explicit failure.

Outside command timing, every source/target endpoint must be an in-range exact
integer triple with `eq?` owning-editor identity. The table must be nonempty,
mutable, strong, `equal?`-based; values must be nonempty immutable strong `equal?`
sets without impersonation. All directed edges become exact-integer quadruples,
lexicographically sorted and Racket-written before SHA256. No raw source, editor,
table or graph payload is logged. Key/edge counts and the full digest are compared.
Finally, current application identity, unchanged source, lexer validity and the
original deadline are checked again. Partial scalar export evidence is retained
if the exposure helper fails.

## Heartbeat and interpretation

The repaired heartbeat uses a 50 ms closed-loop producer with one outstanding
low-priority callback. Scheduled/submitted/handled timestamps distinguish producer
lateness from dispatch delay. Submitted work may drain after stop and is marked;
the pre-stop tail gap remains separate. Record cap is 4096; drops, errors, missing
application-window coverage or incomplete cooperative join fail acceptance.
No producer/callback does I/O, forced GC, thread kill or custodian changes.

The common observer retains original application continuations and checks the live
request token immediately before stock clears running state. Receipt, queue attempt,
callback entry/return, application completion and first lexer-valid time remain
separate. Application completion may precede terminal receipt. No paint or physical
input-to-photon claim is made. Counter deltas have whole-runtime scope, including
concurrent worker/coloring/tool activity; cumulative allocation measures churn,
not RSS. Do not sum overlapping intervals or attribute allocation to one thread.

Report primary readiness, heartbeat tails, separately timed first/second public
getter cost, all failed trials and the limitations of three pairs. Default-off
candidate timing does not establish arbitrary-extension semantics or justify
turning the experiment on by default.

## Evidence and local portable checks

Nine required files per arm: `capture-host.json`, `capture-supervisor.json`,
`gui-observation.json`, `worker-init.json`, `worker-phase-1.json`,
`memory-profile.json`, `activation.json`, `heartbeat.json`, `binding-export.json`.
The worker-phase file is common identity-only terminal metadata with
`phase_points_enabled:false` and `phase_points:[]`. Keep stdout/stderr, manifests,
compile/diff logs, exit statuses and failed partial artifacts as well.

Raw paths and hashes remain unchanged. Acceptance compares only verified
clone-relative typed registry identities and binds each raw terminal handler key
to its own actual registry. Common helper bytes, three unchanged input modules,
and all common transformed sources must match; only the pinned original GUI delta
is permitted. All four transformed sources are independently undo/reapply verified.

```sh
python3 -m unittest test_gui_source test_capture test_accept_gui test_telemetry \
  test_accept_binding test_prepared_runtime -v
```

These portable checks never count as native correctness or performance evidence.
Eager-specific headless cases cover every missing/wrong-type state field, before/
after cache/write invariants, old-flag/schema rejection, exact bound boundary and
strict over-bound failure with retained GC-affected evidence. Native preflight
keeps same-source transformed readers for both arms and all inherited common gates.
The inherited interval-specific validator/tests have been replaced by
`accept_binding.py` and `test_accept_binding.py`; common observer, heartbeat,
profile, launch and source regression coverage remains enabled.
