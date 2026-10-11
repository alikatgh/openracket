# Bounded replay-only phase and actual-thread probe

2026-10-11. This is a separate revision of the completed isolated expansion
replay, copied from verified baseline manifest
`4ea9857a282b38da5d8c1d8033e405b13b64bf4340966fe50575dcffd95ca661`.
The recovered canonical directory is unchanged. Baseline native Mac run
38099774787 observed the stock 128 MiB OOM after finished-expansion in capture and
both replays. This new probe has **not yet executed in Racket or native CI**.
It is an initialization/phase-instrumented stock copy, not byte-identical stock.

## Exact native command, macOS first

CI supplies a new independent deep clone of pristine full Racket 9.3, its executable,
the deterministic mixed-1MiB fixture and fresh CAPTURE/RESULTS directories. Do not
reuse a previously patched runtime or capture: captured source hashes must match
this separately instrumented clone. Copy only manifest-listed files, excluding
compiled/ and __pycache__/.

    python3 "$PROBE/prepare_phase.py" --diagnostic-root "$DIAGNOSTIC_ROOT" --racket "$RACKET"
    python3 "$PROBE/capture.py" --racket "$RACKET" --fixture "$FIXTURE" --output "$CAPTURE"
    python3 "$PROBE/supervise.py" --racket "$RACKET" --capture "$CAPTURE/capture.rktd" --output "$RESULTS" --trials 2 --phase-probe

The preparation verifies three stock pins before edits and compiles the three
patched native modules **and** phase-probe.rkt, support.rkt, replay.rkt and
capture-host.rkt explicitly. Dynamic require alone would not ensure that compile
coverage. Preparation is bounded at 240 seconds. --skip-compile remains only for
an explicit separately bounded compilation step, never to bypass a compile error.

Capture code and its existing registry/request instrumentation are unchanged.
Capture clears all OPENRACKET_* variables and never enables the new phase hooks.
Replay's supervisor also clears inherited controls, then explicitly enables the
phase flag and supplies the frozen helper's absolute path only with --phase-probe.
Without that option, the new helper is not loaded and the old protocol applies.

## Source-preserving seams

See phase-source.diff for the complete stock-source diff. The original ep-log-info
calls and every other original worker/monitor source byte remain present. Removing
only the marked insertions and original readiness seam reconstructs stock exactly.
The module-language capture transformation is identical to the baseline.

- expanding-place.rkt pin: f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383
- module-language.rkt pin: e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53
- syncheck/online-comp.rkt pin: 1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5

No receiver subscribes to the stock background-compilation logger. This avoids
enabling its warning-level log-io? branch or retaining logger continuation marks.
Instead, guarded synchronous counter/timestamp hooks sit adjacent to existing named
phase09–13 points. Phase11→12 spans all non-monitor handler calls. Phase12→13 spans
compile/serialization when stock logic permits. Missing phase12 is only useful with
complete point delivery; dropped or missing rows cannot prove a phase was not reached.

The actual working thread registers at its lambda entry. The actual CheckSyntax
monitor/traversal thread registers at its own lambda entry, not in the caller or
rename-answerer thread. Online go records dispatch/wait points; monitor records
build-trace start, build-trace completion/send-back start, and acknowledgement.
A worker stack waiting in go is expected while traversal runs on the monitor thread.
Hook closures bind before the stock worker changes namespaces, so all hooks use the
same helper instance initialized before the replay ready/continue handshake.

## Lifetime, bounds and interpretation

- Collector/queues/buffers are created under the original worker custodian, outside
  the unchanged 134,217,728-byte child limit. All original handlers remain active.
- Registered threads are held only by weak boxes. The worker starts a new integer
  generation; its monitor inherits that generation through a parameter. Every point
  and sample includes trial/generation. Mismatched events are counted and discarded.
  Registrations are cleared at begin, end and stop. Temporary strong access while
  sampling ends when the immediately rendered row returns.
- Source hooks use a bounded 128-entry asynchronous queue with a zero-timeout put.
  Full queues drop explicitly counted records instead of blocking stock work. No
  expanded syntax, terminal payloads, continuation marks or exception objects are
  stored in probe records.
- The collector samples only the two explicitly registered threads every 250 ms.
  Per trial: at most 256 sample rows, 128 phase points, 8 frames per thread and 240
  characters per text field. Drops, frame/text truncation and sampling errors are
  explicit. No sampling thread suspends or resumes a stock thread.
- Point source timestamps/counters are taken inside the hook. Receipt timestamps
  are separate and may lag. Samples label the latest *received* phase points; they
  are not exact scheduler boundaries. Sample before/after counters include any
  concurrent runtime activity and must not be labeled sampler-owned allocation.
- continuation-marks/thread and continuation-mark-set->context are the same public
  APIs used by stock abort-job. Official9.3 cont-marks.scrbl calls contexts approximate
  human hints. Retained output is bounded; temporary continuation capture/conversion
  cost and OS scheduler delay are **not** hard-bounded by the frame cap.
- Counter observations cover runtime activity; do not sum root/worker GC counters,
  assign allocator/CPU ownership, or equate sampled stack occupancy with CPU time.
  GC event rows can lag and undercount interval totals. Missing rows do not mean no GC.
- All hook/sampling/serialization/control overhead is part of this separate profile.
  These results cannot establish a speedup or be subtracted from the baseline as a
  causal ownership estimate.

The original outside process bounds stay unchanged: 30 s initialization, 60 s per
terminal, 2 s cleanup, 157 s default total for two trials. Probe control exchanges
are additionally bounded inside that budget. Any stop failure still fails cleanup
acceptance. The surviving collector is stopped and the whole place/group is cleaned
up by the existing protocol. If the worker dies or the terminal times out, phase
results may be missing and attribution is incomplete; no new unbounded salvage query
is attempted. An actual terminal summary is saved before optional post-terminal
probe queries, so their failure does not disguise an observed OOM/result.

## Evidence acceptance and output

replay.json retains ordinary terminal/allocation/GC fields and adds trial.phase_probe.
Its attribution_evidence requires both actual registrations and nonempty monitor
frames to report coarse_thread_context_available; otherwise it says incomplete.
That status establishes only usable approximate context, not ownership or a specific
bottleneck. A valid OOM terminal is never by itself attribution success. Preserve all
capped records in CI transport; byte-size-aware transport may be needed.

Prepare writes openracket-phase-source.diff, the clone manifest with source/helper
hashes, and the compilation log. Replay reports the helper hash. All channels and
thread objects remain within the diagnostic process. No production bridge is built.

## Tests and exact local coverage

    export REPLAY_TEST_RACKET="$RACKET"
    export REPLAY_TEST_PROFILE="$TEST_PROFILE"
    export REPLAY_TEST_SOURCE_DIR="$PRISTINE_DRRACKET_PRIVATE"
    python3 -m unittest -v test_phase_probe test_implementation test_supervise
    PLTUSERHOME="$REPLAY_TEST_PROFILE" "$RACKET" test_support.rkt

The phase Python tests run Racket reader, disabled-hook and real-thread fake-work
checks when REPLAY_TEST_RACKET exists. Native CI must require those gates to execute,
not accept their local skips. test_phase_probe.rkt exercises real thread objects,
generations, custodian shutdown and missing-frame acceptance; it never runs DrRacket.

This recovered environment has no available Racket executable. Local checks cover
Python compilation, exact source pins/insertions, source contracts, fake executable
supervision and the existing supervisor suite. The three Racket gates are explicitly
skipped; reader/compilation/thread execution must pass on native CI before capture.
validation.json and phase-python-tests.log are current. baseline-validation.json,
final-tests.log, portable-tests.log and BASELINE-README.md are preserved historical
baseline evidence, not validation of this new Racket helper.
