# Faithful isolated-process online-expansion diagnostic

2026-10-10. Implemented and headlessly tested; native capture/replay is pending.
This is an **initialization-instrumented copy of stock DrRacket 9.3**, not a
byte-identical stock worker, a production bridge, or a measured product speedup.
No local GUI/display, package install or remote write was performed.

## Runnable native contract (macOS first; Linux also supported)

Publish/copy only files named in SHA256SUMS. Exclude local compiled/ and
__pycache__/ directories; local Racket bytecode is not a portable native artifact.

The CI owner supplies a **dedicated independent deep clone of the pristine full
Racket 9.3 runtime** and its executable. It must not alias writable files or source
roots back to pristine/active benchmark installations. CI owns platform-specific
bundle/registry handling. These tools neither install packages nor rewrite package
registries. Do not point prepare.py at production or an active benchmark runtime.

Set REPLAY to this directory, DIAGNOSTIC_ROOT to that clone, and RACKET to its
executable. FIXTURE must be the existing deterministic mixed-1MiB file from
retained-host/performance/fixtures.py. CAPTURE and RESULTS must be new directories.

    python3 "$REPLAY/prepare.py" --diagnostic-root "$DIAGNOSTIC_ROOT" --racket "$RACKET"
    python3 "$REPLAY/capture.py" --racket "$RACKET" --fixture "$FIXTURE" --output "$CAPTURE"
    python3 "$REPLAY/supervise.py" --racket "$RACKET" --capture "$CAPTURE/capture.rktd" --output "$RESULTS" --trials 2

Stop if prepare or capture fails. Do not substitute a hand-built capture, registry,
settings object, base snapshot, or raised limit to get a replay number. A native
abnormal-termination/error is a valid observed terminal result, not success at
expanding the program. A replay with that result can still be diagnostically valid.

prepare.py resolves both patched files through the supplied Racket's
collection-file-path without instantiating GUI modules. It rejects sources outside
the supplied clone, source symlinks/hardlinks, wrong source hashes and ambiguous
anchors. It verifies all edits before writing, removes only those clone modules'
stale .zo/.dep, and compiles them, bounded at 240 seconds. --skip-compile is only
for an explicit separate CI compile stage. Compilation and manifest logs stay in
the disposable clone. Capture/replay source imports point at this frozen directory.

capture.py needs the CI owner's authorized real native session. It starts ordinary
DrRacket, loads the original fixture, sends the same native `x` key event at position
524139, and captures the actual 1,048,577-character edited snapshot, source identity,
frozen handler registry, prefab and open-file list at the existing send boundary.
It preserves coloring, online expansion, all handlers and the stock 134,217,728-byte
child limit. It does not run or alter the active latency benchmark. This capture's
timings are not performance evidence.

Both launchers clear every inherited OPENRACKET_* variable before setting only
their own diagnostic controls. Thus scan, color-budget, autosave and appearance
experiments cannot silently leak into these processes. Native preferences are read
and asserted, not changed to make the experiment pass.

## Pinned source and disabled behavior

Official drracket-core-lib archive SHA-1:
`d55515fcc1d1da846555ea0b5c1b593c4af619ef`.

- module-language.rkt SHA-256:
  `e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53`
- expanding-place.rkt SHA-256:
  `f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383`
- Base fixture SHA-256:
  `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`

The worker's only source insertion is a guard after stock initialization and before
its unchanged job loop. With OPENRACKET_EXPANSION_REPLAY absent or not exactly 1,
it loads no observer and reads/sends no new protocol messages. No original worker
source bytes are deleted/replaced. All stock handlers, locks, custodians, security
guards, expansion, compilation, exception and abort code remain intact.

The caller's capture observers are separately guarded by
OPENRACKET_EXPANSION_CAPTURE=1. **Integrated capture does not enable the replay
flag or receive/send a ready/continue packet.** Its existing request channels,
monitor callbacks and terminal callbacks remain intact. Flag-off capture tests
verify registry values are preserved and no helper/preferences work occurs.

The actual registry is observed at module-language.rkt:2509–2514. The actual
request is observed before line 2534's original send. The existing status/result
receives are observed before dispatch, with request IDs. Same-snapshot replacement
requests are handled without waiting forever on a killed prior pending thread;
up to eight immutable attempt records are retained, and only the current request's
real terminal outcome selects the final capture. Stale results cannot complete it.

Stock online expansion converts its prefab annotations to **none** at
module-language.rkt:145–157 (`#:irl #f`). The user's pending next-Run settings remain
stock lang-default/debug and are separately labeled. Passing debug into this
background request would change stock behavior and is forbidden.

## Exact capture and readiness

Capture persists Racket-serialized data, preserving string versus WXME bytes,
paths, symbols and the actual prefab. The response/status channels are deliberately
not serialized; replay makes real fresh channels in its process. The full frozen
registry order and monitor flags are retained. No handlers are guessed or omitted.

It captures package tables/checksums for every active scope, collection paths and
links, compiled roots/paths, cwd, executable/VM/architecture, seven path/profile
environment variables, preference identity/content hash, worker/caller/support
source hashes and every handler's resolved source hash. Replay fails closed on a
mismatch and names mismatching context fields.

A native shutdown can flush preferences. Capture therefore also preserves exact
preference bytes. Replay may restore **only the explicitly marked disposable
capture profile**, and only when its PLTUSERHOME and preference containment match.
It backs up post-exit contents in RESULTS/preferences-after-capture.rktd, records
the before/restored hashes in replay.json, and verifies exact restoration. It will
not restore outside that marked profile or follow a preference-file symlink.

Only standalone replay enables the ready/continue insertion. The worker creates
its ordinary stock compilation-lock client and dynamically imports every captured
handler before acknowledging readiness. The driver takes baseline counters before
sending continue and the genuine six-field request. All compile-lock, stock place,
response, status, monitor and rename-capability channels remain inside this OS
process. No subprocess capability relay is built.

## Outcomes, metrics and lifetimes

- Real terminal tags are handler-results, abnormal-termination, access-violation,
  reader-in-defs-error, exn:variable and exn. The status finished-expansion is never
  treated as terminal; handlers and compilation follow it.
- Worker-place death, terminal timeout, driver failure and cleanup failure are
  separate outcomes. The exact stock abnormal/OOM message and exception details
  are preserved in bounded summaries; truncation is explicit.
- The measured allocation metric is
  process_allocation_delta_during_isolated_expansion_interval. It includes the
  expansion workload, compiler manager, observers and result sink. No per-place
  counter subtraction or original concurrent GUI allocator-ownership claim occurs.
- CPU time is labeled process_cpu_counter_ms_all_places. Managed bytes are an
  estimate observed from the root, not a root-place ownership measurement. GC
  counters are runtime observations sampled from root/worker, not independent
  per-place counters; the two observations/receivers are separate and never summed.
  GC record receipt timestamps may lag actual GC. The worker's timestamp is checked
  against the root query's send/receive bounds on the actual native runner. Each
  observer stores at most 4096 rows and explicitly counts drops/truncation.
- The supervisor samples external process-group RSS using native ps on macOS/Linux.
  It reports unavailable RSS as null, observed interval peaks as sampled peaks,
  and stdout/poll/sample boundary uncertainty. These are not exact high-water or
  managed-heap values. Shared pages can be counted twice if real OS descendants
  exist. Places themselves are threads in this one OS process.
- Cold means first expansion in a fresh process after initialization, not cold disk
  cache. Warm means another request in the same worker/manager/process after the
  reported prior terminal outcome. No forced GC, dummy expansion, cache deletion,
  changed child limit or omitted handler creates apparent warmth.
- Monitor payloads are consumed by an expansion-only sink. All live capabilities
  are retained until replacement work is observed or final cleanup; terminal data
  remains retained until that same first replacement status/response. Actual
  terminal and capability objects are passed to stock void/reference-sink after
  cleanup (including the error path), preventing compiler liveness elimination
  during teardown. If replacement work times out or dies without any response,
  the preceding terminal and capabilities stay retained through that teardown;
  no empty new-result value overwrites them. This helper performs no foreign-memory access. GUI annotation/callback work
  is not replayed. Sink traversal/allocation is disclosed supporting overhead.
- A compiled-byte/terminal-summary mismatch is visible and must be investigated;
  it does not get silently recategorized or automatically treated as a speedup.
  Native path/layout effects and nondeterminism need evidence before interpretation.

Counters end immediately when the driver consumes the terminal message, before
result hashing/JSON, GC control queries and teardown. Those queries have separately
disclosed boundary skew. Whole initialization is measured separately.

## Bounds and cleanup acceptance

Native capture: at most 90 seconds for frame startup and 90 seconds after the edit
for an actual terminal result, with a 190-second outside process bound and bounded
process-group cleanup. It exits its disposable process without opening save dialogs.

Replay: 30-second initialization acknowledgement, 60 seconds per actual terminal
result, 2 seconds cooperative teardown, and an outside 157-second total budget for
the default two trials (including 5-second startup cushion and cleanup reserve).
The outside supervisor owns TERM/KILL, process membership verification and direct
child reaping. Ordinary same-group descendants are cleaned up; a descendant that
creates a new session/group is outside this supervisor's supported containment.

Each cleanup component is independently attempted. The control channel must return
exactly `stopped`; the place must be observed dead; the root logger must stop; and
the diagnostic custodian is shut down. Any missing/wrong acknowledgement or cleanup
exception makes the diagnostic fail even if a terminal result was already observed.
Outside process-group cleanup remains the safety backstop, not a validity excuse.

## Artifacts and phase contract

Capture directory: capture.rktd, immutable capture-attempt-N.rktd files,
capture.launch.json, capture-summary.json, capture-host.json,
capture-supervisor.json, stdout.log, stderr.log and the marked disposable profile.
Do not dump serialized snapshot/payload files into CI logs.

Replay directory: replay.json (actual outcomes/allocation/GC/parity/cleanup),
supervisor.json (external RSS/phases/exit/cleanup), stdout.log and stderr.log.
The driver emits bounded lines prefixed OPENRACKET_REPLAY_PHASE_JSON with event
initializing, interval_start, interval_end, cleanup or finished, plus trial,
monotonic_ms and outcome. Supervisor timestamps are independent observed boundaries.

## Headless checks and scope

Portable CI checks use the supplied executable, an explicit already-supported
test profile, and the **pristine installed** drracket/private source directory:

    export REPLAY_TEST_RACKET="$RACKET"
    export REPLAY_TEST_PROFILE="$TEST_PROFILE"
    export REPLAY_TEST_SOURCE_DIR="$PRISTINE_DRRACKET_PRIVATE"
    python3 -m unittest -v test_implementation test_supervise
    PLTUSERHOME="$REPLAY_TEST_PROFILE" "$REPLAY_TEST_RACKET" test_support.rkt

REPLAY_TEST_SOURCE_DIR must contain the original pinned module-language.rkt and
expanding-place.rkt, not their diagnostic copies. Their SHA-256s are verified
before use. This path does not read local cached package ZIPs. REPLAY_TEST_PROFILE
sets PLTUSERHOME for the mock protocol/reader subprocesses; no package is installed.
Other package-path environment variables remain caller-controlled. For only the
real-place protocol portion, without any source-directory input, use
`python3 -m unittest -v test_implementation.RealPlaceProtocol test_supervise`.

The following additional local archive/fixture provenance checks require the
original source-cache workspace. They are not required inputs to the portable CI
test command above:

    python3 inspect_contract.py
    python3 test_contract.py

Without overrides, test_implementation.py retains the original local toolchain,
profile and archive-backed source defaults as a convenience. Native prepare,
capture and replay CLI contracts are unchanged by these test-only overrides.

The launch-context tests preserve the exact captured environment strings and check
resolved path identity separately. An explicit symlink-alias case covers macOS
`/var` versus `/private/var` spelling without relaxing runtime context validation.

Racket compilation of support.rkt, replay.rkt and capture-host.rkt is also checked.
The protocol tests use an explicitly labeled fake expansion worker in a real
Racket place, with real channel capabilities. They test framing, actual-terminal
waiting, cold/warm sequencing, death, timeout and cleanup; they are **not actual
stock expansion results**. Native tests and source compilation remain CI gates.

SEAM-PROPOSAL.md is historical rationale; this README and SHA256SUMS are the current
run/freeze contract. No macOS performance result follows from Linux-only checks.
