# Interval-map candidate: incomplete Mac comparison, no adoption

## Result

Keep the direct-set candidate default-off. Native preservation gates passed, but
only two of three planned timing pairs were accepted. Those two show a small
0.6–1.7% reduction in the annotation-application interval, mixed end-to-end
completion, and no consistent responsiveness improvement. This does not establish
a meaningful speed gain. No full-matrix median or speedup is claimed.

The failed candidate trial remains in the report. Its actual worker, lexer and
application reached their endpoints, but its heartbeat failed early and never
completed valid cleanup/final verification. Its partial endpoint observations are
not substituted for a valid paired trial.

## Exact evidence and workload

- [Native run38121983444](https://github.com/alikatgh/openracket/actions/runs/38121983444),
  commit `89489cb5d7ece27fceb178d092bc55850a1304d9`.
- Raw macOS log SHA256:
  `da1d186dd61b9b7dc34a8cd9bd5a0d6d6cc9ee12f59ef2bcefe942c4e24e28c5`.
- Telemetry manifest:
  `82bf5dba355c5374b5e0246a92a8b1064eafcffbed9ac3bba3eead52d1353f85`.
- Official interval-map source:
  `1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de`.
- Candidate source:
  `1f1636316c3ba3f307fcb33f44d68c00ee9804b775fac7d78916db01d87fec4d`.

One 1 MiB mixed-Racket file plus the identical single middle-comment edit in each
fresh Mac process. Actual child cap 256 MiB, accounting available, online tools and
coloring enabled, original 20 ms batching. Candidate changes only the independently
reviewed interval-map setter tail; earlier scan/budget/xref/appearance/autosave
experiments are absent. Producer phase points are off in both arms. Common
source/registry/terminal/application observers and a 50 ms closed-loop GUI
heartbeat remain measurement costs.

All actual-map differential modes, full annotation/rename comparisons, actual
GUI docs-map parity, native telemetry preflight and original-runtime witnesses
passed. Stock/candidate activation and complete-work identity are checked per
process. Accepted pairs 2/3 have matching actual prefab, pending-next-Run settings,
compiled-result size and monitor shape: one clean 292,728-entry trace with 74,675
rename-capability rows. These are rows, not 74,675 distinct channel endpoints.

Six commands ran in order stock 1, candidate 1, candidate 2, stock 2, stock 3,
candidate 3. Five commands passed; pair 1 candidate failed. Both pair 1 and the full
matrix correctly remain rejected. No earlier failed run is replaced or hidden.

## Completion: every trial retained

Durations in seconds. Application is entry to the actual final annotation
application endpoint. Request begins at the actual GUI request observation.
Open begins immediately before the real file-open route. These intervals include
interleaved GUI/runtime work and are not exclusive annotation CPU or paint time.

| Pair | Arm | Process | Application | Request→application complete | Open→application complete |
|---|---|---|---:|---:|---:|
|1|Stock|valid, pair rejected|18.007|31.226|32.983|
|1|Candidate|failed heartbeat; partial endpoints only|18.108|30.990|32.762|
|2|Stock|accepted pair|18.782|31.640|33.384|
|2|Candidate|accepted pair|18.464|31.029|32.810|
|3|Stock|accepted pair|17.930|30.519|32.278|
|3|Candidate|accepted pair|17.826|30.737|32.531|

Accepted pair 2: application 318 ms shorter (1.69%); request→complete 611 ms shorter
(1.93%). Accepted pair 3: application 104 ms shorter (0.58%), but request→complete
218 ms longer (0.71%). No ratios are calculated for the failed pair.

Application completion remains 15.106–15.851 seconds after the worker terminal
callback returns and 5.772–6.080 seconds after the first lexer-valid observation in
the accepted pairs. The later endpoint matters: earlier backend/lexer readiness
is not final annotation readiness. Final source/lexer/currentness is verified
again after the heartbeat joins in the valid processes.

## GUI responsiveness: no consistent improvement

The heartbeat has one outstanding low-priority callback. Its next deadline is
50 ms after the preceding handler. Planned→handler delay includes producer lateness
and queue delay; queue→handler isolates delay after submission. It is closed-loop
observation, not an independent hardware input stream, paced typing, or physical
input-to-photon. This workload contains one controlled edit, so no per-key typing
claim is available.

Application-window samples are selected by their planned deadline being within
application entry/completion. Quantiles are nearest-rank per trial, never pooled
across arms. All raw rows remain available.

| Pair/arm | Samples | Planned p50/p95/p99/max (ms) | Queued p95/max (ms) | Handler-gap max (ms) |
|---|---:|---|---|---:|
|2 stock|165|15.940 /130.094 /176.576 /180.773|129.312 /180.644|230.773|
|2 candidate|163|15.667 /132.579 /192.052 /206.943|131.545 /206.628|256.943|
|3 stock|158|16.958 /128.927 /161.649 /214.750|128.557 /214.508|264.750|
|3 candidate|155|19.378 /137.061 /148.922 /205.006|134.847 /204.624|255.006|

Application p95 planned and queue delay are higher in both candidate observations.
Maxima and p99 are mixed. A handler gap includes the intentional 50 ms pacing
interval and must not be called an equivalent uninterrupted GUI stall.

Whole-workload planned p95/p99/max (ms): pair 2 stock 151.288 /644.212 /2480.280,
candidate 143.459 /709.504 /2494.741; pair 3 stock 137.121 /674.005 /2468.726,
candidate 144.241 /717.733 /2514.467. Whole-workload queue maxima are 2480.159 /
2494.492 and 2468.543 /2513.255 respectively. These retain the initial open/edit
period rather than excluding its roughly 2.5-second worst planned delay.
Producer lateness can be material: pair 2 maxima 552.990 /616.469 ms, which a
queue-only metric would miss. No causal GC attribution follows from these delays.

Pair 1 candidate has only 70 total rows and five application-window rows because
the heartbeat stopped early. Its tail summaries are explicitly unusable. Pair 1
stock has 228 whole-workload/159 application-window samples but lacks a valid mate.

## Allocation, GC and CPU counters

Application-span cumulative allocation is 10.544→10.312 GB in pair 2 and
10.544→10.268 GB in pair 3: decreases of232.4 MB (2.20%) and 275.9 MB (2.62%).
Decimal GB/MB are used. This is allocation churn, not live RAM or RSS.

| Accepted pair/arm | Application allocation (bytes) | Application GC (ms) | Application process CPU, all places (ms) | Request→complete allocation (bytes) | Request→complete GC (ms) |
|---|---:|---:|---:|---:|---:|
|2 stock|10,543,966,032|734|20,198|20,231,878,272|5,179|
|2 candidate|10,311,590,848|668|19,831|19,927,171,968|5,070|
|3 stock|10,543,989,808|668|19,389|20,206,730,048|5,076|
|3 candidate|10,268,073,584|672|19,317|19,928,044,868|5,102|

All counters are observed from the GUI runtime and can include concurrent
background worker, coloring, autosave, tool and observer work. They do not identify
the allocating thread, establish exclusive setter cost, or permit adding overlapping
intervals. CPU includes parallel places. GC time is an accumulated counter, not a
pause distribution. RSS/peak resident memory is not collected by this minimal
harness. The two accepted pairs do not justify a universal memory/speed claim.

## Failed heartbeat: precise observation and source defect

Pair 1 candidate recorded:

- Heartbeat start 3280.302 ms; last handled callback 18818.005 ms.
- At 19000.789 ms it stopped with `duplicate-callback`, one error, 71 submitted,
  70 handled, one outstanding, no dropped records, producer exited.
- Product application completed at 36041.859 ms, and the host verified its initial
  final source/lexer snapshot at 36149.707 ms. Heartbeat coverage had already ended.
- Join reached the unchanged post-edit deadline 94950.465 ms. Process exited 1
  after 95.090 seconds; the outer 190-second timeout did not fire. External process
  cleanup was complete. The required post-join final verification is absent.

`heartbeat.rkt` treated a single false `box-cas!` claim result as proof of duplicate
invocation. The official 9.3 reference explicitly allows this operation to fail
spuriously while leaving the box unchanged. Rejecting a first callback this way
skips its acknowledgment and strands the outstanding count, matching the observed
state. The queue-error cleanup claim repeats the same assumption. This is a real
harness contract defect, independent of the production candidate.

The raw record does not contain the once-box value or callback sequence at the
error, so it cannot prove the hardware-level spurious event by itself. A narrow
repair should retry while the box remains unclaimed, retain true-duplicate
rejection, and deterministically inject false CAS outcomes through the actual
callback/queue-error paths. It must preserve pacing, deadlines, acknowledgment
ownership and all failure semantics. The original failed trial must remain failed.
See the [official box CAS contract](https://docs.racket-lang.org/reference/boxes.html).

## Decision and next evidence

Do not adopt or advertise this candidate as a speed improvement. Preserve the
small allocation observation as partial evidence. Repair and native-test the
heartbeat separately; another six-trial run solely to fill the invalid pair is
not warranted by these tiny, inconsistent timing differences.

The next useful measurement is narrowly bounded attribution of the actual long
GUI annotation-application phase by annotation type, including arrows/rename and
documentation work, while preserving successful final application. That can choose
a higher-impact seam instead of repeatedly tuning the same small setter change.

`analyze.py` retains all six trials, revalidates accepted scalar endpoints and
heartbeat arithmetic, binds accepted endpoint/monitor/terminal data back to the
native pair records, and refuses missing evidence. Seven regression tests pass,
including failure relabeling, missing records, tail/cap corruption and acceptance
mismatch. `analysis-38121983444.json` contains every derived value and 51 decoded
input-file hashes. These local analysis checks do not replace the native source
and correctness gates.
