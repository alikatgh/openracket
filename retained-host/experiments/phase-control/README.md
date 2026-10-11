# Single-observation phase observer control

This read-only Python validator compares one genuine 256 MiB GUI capture with one
phase-observation-off replay and one phase-observation-on replay in fresh processes.
It does not run Racket, start a GUI, install anything, edit sources, or write results.
The native CI adapter owns execution. Only stdout contains the validation report.

## Exact native sequence

Use the already approved frozen phase-256 package, whose SHA256SUMS digest is
`44b6c593c61eb752b7da04eece27245f127d9c448dff576b52751f354e0c7e56`.
Keep native preflight and preparation unchanged. PROBE is the manifest-verified
package; CONTROL is this package. RACKET is the physical executable inside the
fresh independently prepared clone. FIXTURE is the unchanged deterministic mixed
1 MiB fixture. CAPTURE, OFF_RESULTS and ON_RESULTS must be new external directories.

    python3 "$PROBE/capture.py" --racket "$RACKET" --fixture "$FIXTURE" --output "$CAPTURE"
    python3 "$PROBE/supervise.py" --racket "$RACKET" --capture "$CAPTURE/capture.rktd" --output "$OFF_RESULTS" --trials 1
    python3 "$PROBE/supervise.py" --racket "$RACKET" --capture "$CAPTURE/capture.rktd" --output "$ON_RESULTS" --trials 1 --phase-probe
    python3 "$CONTROL/validator.py" --probe "$PROBE" --capture "$CAPTURE" --off "$OFF_RESULTS" --on "$ON_RESULTS" > "$REPORT/observer-control-validation.json"

Run both arms once, sequentially, and run validation even after an arm fails.
Preserve each command's exit status and all raw files. Do not allow shell `set -e`
to discard the on arm or final validation after the off arm fails. A failed capture
precondition should stop native work and still preserve/validate available evidence.
Do not retry either replay to obtain success, reuse the old capture, increase limits,
change timeout settings, or modify instrumentation. There is no speed comparison.

Keep the captured file, launch JSON, fixture, native clone's
`openracket-replay-manifest.json`, and all referenced sources available until the
validator runs. Afterward transport/preserve all raw outcomes and validation JSON.
The stdout report includes hashes of inputs and actual source bytes it verified.
The validator never rewrites, normalizes or truncates the evidence files.

## Meaning of the report and exit status

Exit 0 means `observation_valid: true`. It does NOT mean either replay succeeded.
Exit 1 means control evidence is missing, malformed, inconsistent, or out of scope;
readable outcomes and their differences are still preserved in the report.

Separate fields report:
- `observation_valid` and detailed failed prerequisites
- Each original outcome/terminal, statuses and supervisor timeout/death record
- `both_successful`, requiring handler-results, a clean nonempty actual monitor
  trace and retained real rename capability channels
- `both_terminal_summary_parity` and exact terminal summary field differences
- `both_monitor_scalar_parity`, comparing trace-entry and rename-capability-row counts
- `on_phase_complete`, including required producer phases, no drops/stale records,
  finite ordered times, correct generation, and usable monitor/service thread context
- The prior run 38110770395's completed-phase acceptance, which remains failed

A genuine observed OOM with matching inputs, cap/accounting, one trial and clean
teardown is a valid observed failure. It is never successful replay equivalence.
A terminal interval timeout can likewise be a valid observed failed attempt when
readiness, actual trial and cleanup are recorded. An outer timeout with missing
readiness/trial/result cannot establish the complete comparison; its timeout and
any readable outcome are retained. Missing phases are reported separately from
validity of a genuine failure. A malformed phase object fails observation validity.

Off success + on OOM is conditional single-observation evidence of instrumentation
sensitivity only when off also matches the capture terminal summary and monitor
scalar counts. A clean but unequal off result remains inconclusive. Both OOM means turning phase observation off was insufficient to
restore the GUI outcome. Both success establishes only that each arm succeeded
once. Other outcome combinations remain inconclusive. Nothing identifies an exact
allocator cause, proves full trace/payload/capability equality, CPU ownership,
reproducibility across repeated trials, or an integrated GUI speedup.

Phase-observation off still retains readiness/control and GC observation absent
from GUI capture. Source hooks are in both prepared copies but are guarded off in
the off process. One sequential off/on pair also cannot remove order/cache effects.
Rename-capability row counts are not counts of distinct channel endpoints.

## Identity, bounds and provenance

The validator checks the complete frozen probe manifest; the native prepared clone's
three transformed sources against independently derived fixed byte hashes; pristine
xref/traversals pins; and helper paths/hashes. The existing pinned replay calls its
snapshot/registry/prefab/runtime/source validator before emitting ready fields.
Those checks cover the serialized capture's exact captured runtime context, worker,
caller, support and registered-handler bytes. This Python program deliberately does
not implement a second Racket deserializer or execute another native query.

It checks actual capture/ready 268435456-byte caps, memory accounting, the public
one-key profile setup, source/settings/snapshot/registry identities, common captured
launch context, and distinct process identities `(pid, started_monotonic_ms)` with
nonoverlapping elapsed and UTC lifetimes. Legitimate PID reuse is accepted only
with a distinct later start. Exactly one fresh first trial per arm is required.

Replay bounds remain 30 s initialization + 60 s terminal + 2 s cleanup + 5 s cushion
= 97 s total per one-trial process; RSS sampling remains 0.1 s. Capture's frozen
190 s outer, 90 s gates, 5 s cleanup, and helper 30 s limits are unchanged. No new
high-frequency observer, native workload, production changes or local GUI run.

`fixtures/run-38110770395/` contains the original seven failed-run JSON documents,
byte-for-byte, and explicit provenance. Tests adapt them only in memory, visibly
changing trial count/flags/process witnesses to generate synthetic control cases.
These test fixtures are never accepted as evidence of a new native off/on run.

## Portable validation

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$CONTROL" -v

Tests cover synthetic success, OOM, interval/outer timeout, incomplete phase evidence,
actual prior failure records, scalar/terminal differences, null/malformed JSON,
source mismatches, cap/settings/registry failures, fresh-process proofs, PID reuse,
unchanged one-trial bounds, and read-only CLI failure behavior. No Racket is needed.
Copy only ALLOWLIST.txt entries; do not copy caches. Verify SHA256SUMS before use.
