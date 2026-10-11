# Native GUI annotation application attribution

## Result and decision

The accepted diagnostic identifies arrow insertion as the largest measured annotation-call category: **6.993509 s across 74,675 calls, 66.18% of measured entry-call wall**. Documentation-menu calls contribute another **1.825075 s, 17.27%**. The `add-id-set` category has zero calls in this workload.

The observed application batch span is **28.809596 s**. Only **10.867999 s (37.72%)** is active-batch elapsed time; **17.941597 s (62.28%)** is measured requeue waiting. Arrow call-wall is **24.27% of the whole batch span**. This supports the approved narrow arrow/binding-range investigation, while requiring a separate explanation of the queue gaps. It does not establish that optimizing handler CPU will remove the whole 28.8 seconds.

Both genuine-GUI arms passed exact native acceptance. The overall workflow failed separate stock-tool and application-package checks, so this report does not call the complete build green. The observed arm had a shorter common application interval than control, but one instrumented/control pair cannot establish an overhead estimate or a product speedup.

## Run and accepted workload

- Run: [38125605788](https://github.com/alikatgh/openracket/actions/runs/38125605788), macOS job `114429230238`, 2026-10-11.
- Commit: `8821c54027faa4dd0526e2b3eac2cc0b66618342`.
- Native macOS Racket 9.3, one fresh GUI process per arm, separate fresh profile/addon directories, stock 256 MiB child limit (`268435456` bytes), actual memory accounting available, online compilation and coloring enabled.
- Workload: open the unchanged mixed 1 MiB fixture and insert one `x` in its middle comment at character 524139. Base length 1,048,576; final editor length 1,048,577. This is a specific single-edit diagnostic, not a general editing benchmark.
- Both arms include the common observer and identical scalar batch/yield/resume counters. Only observed enables the 13-tag/four-final application timing probe. Worker producer phase points are OFF in both arms; both phase arrays are empty.
- Native acceptance: `accepted: true`, `failures: []`; both arm summaries `valid: true`. All 27 diagnostic CI result rows pass, including no-skips native preflight, exact additive source preparation/clone compilation, both GUI captures, strict acceptance, evidence transport and the final pristine-runtime check.
- Native preflight records 69 tests, zero skips, plus 24 profile-helper tests. These headless tests are separate from the successful actual GUI trials. The offline analyzer has 29 passing synthetic tests; those are not native measurements.

The independent failing workflow branches include the stock native coordinator failure-propagation regression, the packaged-app stock-order observer assertion, withheld follow-on/relocation launches, and the packaged-app original `.rkt` handler verification. None changes the recorded pass/fail result of this diagnostic pair; none should be hidden by that pair's success.

## Outcome and currentness checks

Each arm has one matching final request (`request_id = 1`), one selected worker job, and current application generation 1. Each receives `handler-results` with 270,280 compiled bytes, one clean monitor message/trace batch, 292,728 trace entries, and 74,675 independently recognized rename-capability rows. The actual registry, source, settings and scalar terminal/monitor evidence match across arms.

Both final source snapshots are unchanged and their lexers are valid at completion. Terminal callbacks and application completion are current, with no cancellation, stale application event, duplicate GUI point, dropped record, observer failure, unknown tag, reentrant entry, unmatched event or open entry/final/batch/wait state. Both supervisors record exit 0, no timeout and complete cleanup. The observed snapshot is quiescent and all final calls return once. These checks establish the specified synchronous application outcome; they do not establish full payload/capability equality or finished painting.

## Observed batch accounting

| Quantity | Count | Total wall ms | Mean wall ms | Maximum wall ms |
| --- | --- | --- | --- | --- |
| Active batches | 525 | 10867.999 | 20.700950 | 121.345 |
| Requeue waits | 524 | 17941.597 | 34.239689 | 353.463 |
| All 13 entry-call categories | 292,728 | 10567.394 | 0.036100 | 111.627 largest category maximum |
| Four synchronous final calls | 4 | 8.076 | 2.019000 | 3.965 |
| Unassigned active remainder | not sampled | 292.529 | not available | not available |
| First batch start through final batch end | one span | 28809.596 | not applicable | not applicable |

The decomposition is **10,867.999 = 10,567.394 + 8.076 + 292.529 ms** of active time, and **28,809.596 = 10,867.999 + 17,941.597 ms** for the full batch span. Calls, finals and the remainder are components of active time, not extra durations to add on top of it. Counts reconcile as 525 batches = 524 yields + 1, and 524 waits = 524 resumes = 524 yields.

Independent decimal recomputation from raw JSON gives an active-plus-wait minus span balance of −2×10⁻¹² ms, a representation-level difference far inside the frozen 0.288095960 ms tolerance. The analyzer's floating-point balance is 0. The signed active remainder is positive; no negative value was hidden by the acceptance clamp. The tolerance is an arithmetic check, not a performance threshold.

The first batch starts 0.010 ms after common application-enter; the last batch ends 0.023 ms after common application-complete. Thus the 28,809.596 ms batch span differs from the 28,809.583 ms common application interval by 0.013 ms. Keep these boundary definitions separate even though the numeric difference is small here.

Active time includes entry calls, final calls, loop/dispatch work, observer work and scheduling. Submission of the next callback is in active time. Requeue wait begins only after `queue-callback` returns and ends at callback entry; it includes the prior callback's tail, eventspace waiting and any intervening GUI work. It is not an idle-time or scheduler-exclusive measurement.

## All 13 observed annotation categories

Times are cumulative inclusive call-wall measurements in the observed arm. Means are derived from sum/count; zero-count means are unavailable. Percentages use the 10,567.394 ms measured entry-call total, not the application span. Maxima are observed maxima, not percentiles.

| Exact stock tag | Calls | Wall sum ms | Mean ms | Maximum ms | Entry-call wall share |
| --- | --- | --- | --- | --- | --- |
| `syncheck:add-arrow/name-dup/pxpy` | 74,675 | 6993.509 | 0.093653 | 111.627 | 66.18% |
| `syncheck:add-tail-arrow` | 2,987 | 47.038 | 0.015748 | 4.129 | 0.45% |
| `syncheck:add-mouse-over-status` | 71,689 | 696.546 | 0.009716 | 9.643 | 6.59% |
| `syncheck:add-text-type` | 53,766 | 672.150 | 0.012501 | 34.935 | 6.36% |
| `syncheck:add-background-color` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-jump-to-definition/phase-level+space` | 29,870 | 298.176 | 0.009982 | 25.240 | 2.82% |
| `syncheck:add-require-open-menu` | 1 | 0.098 | 0.098000 | 0.098 | 0.00% |
| `syncheck:add-docs-menu` | 53,766 | 1825.075 | 0.033945 | 24.682 | 17.27% |
| `syncheck:add-definition-target/phase-level+space` | 2,987 | 4.071 | 0.001363 | 0.284 | 0.04% |
| `syncheck:unused-binder` | 2,987 | 30.731 | 0.010288 | 1.588 | 0.29% |
| `syncheck:add-id-set` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-prefixed-require-reference` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-unused-require` | 0 | 0.000 | not applicable | 0.000 | 0.00% |

The fixed-category count sum is exactly 292,728, matching entries started, entries completed and the independently observed trace-entry count. Arrow/name-dup calls plus id-set calls are exactly 74,675 + 0 = 74,675, matching the independently scanned rename-capability rows. Zero id-set calls means this particular workload supplies no id-set timing evidence; it does not establish that id-set is generally cheap or unused.

## Four final synchronous calls

| Operation in stock order | Count | Wall sum ms | Mean ms | Maximum ms |
| --- | --- | --- | --- | --- |
| `update-blue-boxes` | 1 | 3.921 | 3.921 | 3.921 |
| `update-drawn-arrows` | 1 | 3.965 | 3.965 | 3.965 |
| `remove-bkg-running-color` | 1 | 0.172 | 0.172 | 0.172 |
| `set-syncheck-running-mode` | 1 | 0.018 | 0.018 | 0.018 |

Their total is 8.076 ms. Blue-box timing includes argument evaluation. These calls may initiate later coroutine/cache/timer work, arrow timers/painting and running-indicator refresh. The small synchronous total is not evidence that all resulting work is cheap or already settled. Pointer/viewport-dependent final work remains unmeasured context.

## Request terminal lexer and application endpoints

All values below are milliseconds after that arm's own selected request observation. This removes each process's clock origin; no absolute timestamp is subtracted across processes. Lexer time is the first host observation of final-source validity, not the exact lexer-completion instant.

| Endpoint | Control ms | Observed ms |
| --- | --- | --- |
| request-observed | 0.000 | 0.000 |
| monitor-received | 24958.913 | 19449.366 |
| monitor-callback-queue-attempt | 25968.013 | 20040.041 |
| monitor-callback-enter | 25976.632 | 20057.230 |
| application-enter | 25978.305 | 20057.355 |
| monitor-callback-return | 25998.567 | 20077.422 |
| terminal-received | 31977.308 | 23657.587 |
| terminal-callback-queue-attempt | 31977.505 | 23657.645 |
| terminal-callback-enter | 31983.704 | 23661.284 |
| terminal-callback-return | 31986.511 | 23661.952 |
| lexer-first-valid-observed | 59195.185 | 40858.406 |
| application-complete | 68295.642 | 48866.938 |

In both actual arms, application completes after terminal callback return and after first observed lexer validity. The remaining application interval after terminal callback return is 36,309.131 ms control and 25,204.986 ms observed; after the lexer observation it is 9,100.457 ms control and 8,008.532 ms observed. These are elapsed endpoint separations, not exclusive residual work. The stock application endpoint need not follow the terminal in other runs; this report uses the actual order only.

Observed monitor receipt to queue attempt is 590.675 ms, followed by 17.189 ms to callback entry. Those are additional separate elapsed windows before common application begins. Common trace walking/correlation and concurrent runtime work can contribute; they are not attributed to an individual annotation tag. The first monitor callback returns after only 20.192 ms, well before complete application.

## Broad control perturbation

| Quantity | Control | Observed | Observed minus control |
| --- | --- | --- | --- |
| Common application wall ms | 42317.337 | 28809.583 | -13,507.754 |
| Request to application completion ms | 68,295.642 | 48,866.938 | -19,428.704 |
| Request to terminal callback return ms | 31,986.511 | 23,661.952 | -8,324.559 |
| Host elapsed including startup ms | 80683.691 | 57331.591 | -23352.100 |
| Supervisor elapsed ms | 81258.965 | 57904.468 | -23354.498 |
| Batch count | 642 | 525 | -117 |
| Yield/resume/wait count | 641 each | 524 each | -117 each |

The common application interval is 31.92% lower in observed. That is a single-pair descriptive difference, not negative instrumentation cost or an optimization gain. The workload, source and scalar outcome match, but scheduling/GC/process variability and measurement perturbation are not isolated. Control has no per-tag, final-call, active-duration or wait-duration samples to subtract. The 642 versus 525 batch counts also show that this pair did not have identical slicing. No repeated-pair confidence interval or causal overhead estimate is supported.

## Runtime counters and tail limits

| Overlapping endpoint window | Arm | Allocation counter delta bytes | GC counter delta ms | All-place process CPU delta ms |
| --- | --- | --- | --- | --- |
| common_application_entry_to_complete | control | 10,979,507,440 | 1,472 | 44,230 |
| common_application_entry_to_complete | observed | 11,542,046,336 | 994 | 30,524 |
| request_to_application_complete | control | 20,415,014,272 | 10,847 | 83,447 |
| request_to_application_complete | observed | 21,018,571,792 | 8,399 | 61,753 |
| request_to_terminal_callback_return | control | 13,312,889,616 | 9,929 | 49,528 |
| request_to_terminal_callback_return | observed | 13,460,160,352 | 7,733 | 37,783 |

For common application, observed allocation-counter growth is 562,538,896 bytes greater than control even though elapsed application time is lower. This is a broad counter difference, not per-tag allocation or a causal explanation of the timing difference. These counters have cumulative runtime scope and include concurrent and observer work. Allocation is not live/retained heap, peak memory, RSS, or bytes owned by the GUI thread. CPU may exceed wall because the counter includes work across places; it does not assign CPU to the application interval's named function. GC deltas cannot be subtracted from wall to infer mutator CPU or apportioned among the 13 tags. No negative counter deltas occur in the reported windows.

Only count, sum and maximum are retained for calls, batches and waits. The largest active batch is 121.345 ms; the largest requeue wait is 353.463 ms; the largest arrow call is 111.627 ms. Means and maxima do not reveal p95/p99 latency, ordering, which tags share a batch, or which intervening work accounts for a long wait. The unchanged stock 20 ms batching test is not a hard maximum observed wall duration. This probe has no heartbeat, stack sampling, per-batch event timeline, paint-completion observation or per-tag CPU/allocation/GC samples. Inclusive wall can include preemption, GC pauses and boundary-hook work. No physical typing latency, display completion, or exclusive CPU ownership is established.

## Next diagnostic scope

1. Follow the approved narrow source-level arrow/binding-range investigation. Determine what the actual arrow insertion path does and which operations merit a separately reviewed measurement. The evidence selects that path by observed inclusive wall; it does not yet identify a function, allocator, range structure, or CPU owner as the cause.
2. Preserve queue-gap attribution as a separate question. The 17.941597 s of requeue waiting is larger than active time and cannot be explained by the present tag buckets. Determine which existing GUI/runtime work can occupy those gaps before designing any further probe. Do not add waits to call-wall, assume that gaps are idle, or predict that a handler optimization will remove them unchanged.
3. Treat documentation-menu calls as the next substantial measured category if the narrower arrow investigation does not explain enough. The synchronous final-four total and zero id-set count do not justify eliminating deferred GUI work or generalizing beyond this fixture.

This report performs no additional native measurement, publication, runtime change, or measured-source edit. Any later optimization needs semantic/currentness/cancellation verification and an appropriate repeated end-to-end comparison; this attribution result alone is not an optimization acceptance gate.

## Provenance and independent verification

The saved analyzer output was recomputed from all 14 decoded arm records and the exact decoded acceptance using the frozen scalar validator; it matches exactly. Canonical transport digests for every required record and acceptance match the saved decoder index. A separate decimal arithmetic pass over the raw observed application JSON confirms counts, sums, residual, active/wait balance and composition. See [machine-readable analysis](analysis-38125605788.json) and [independent arithmetic verification](verification-38125605788.json).

Original native-file hashes, decoded-file hashes and canonical parsed-JSON hashes are different identities. All are retained separately in the analysis. The entire native acceptance, all native input hashes, local decoded paths/byte counts and frozen source digests are retained there. Hash validation does not claim that decoded formatting reproduces native file bytes. Native compilation, runtime containment, actual helper/source bytes and original fixture checks remain the CI's verified attestations; they were not rerun against nonexistent native paths locally. The decoder index also binds the host/lexer/supervisor scalars and individual batch boundaries that the acceptance summaries do not copy.

| Artifact or identity | SHA256 |
| --- | --- |
| Raw macOS job log | 8d15ea134bdaf242f3becdbf0d1853f6186083074e791584acbd02240e280008 |
| Decoder index | 690e438f0ed9e1aa93985e15066baa8f3b1d0bfed36c301f6133d21a22e49567 |
| Decoded native acceptance file | 8673e32520e3610cec5503e0e478d0a4c628f1833ffb9f71594bad69495e0db0 |
| Acceptance canonical JSON | 3b1daf781226bfb0481228a4bc35f5aa01f5c16e749dc4692734bf0531ac42c8 |
| Analysis JSON | b0d8109d4d88a162dfd98e5df964100b7617a62cfaf9c5d80b59bfac24182193 |
| Independent arithmetic JSON | 6bc4d416cda14df9f4f9bcd4e5ac6a174c2edfbe2360cad2da7422de4ed77e2f |
| Frozen measured package SHA256SUMS | 0a0117d4b8e20aa7804b5863bc30bad8da40aa6ad9a14136e6f0408e272147b9 |
| Analyzer source | f429b0b9df594450811354de4c5405db26a0ea09ab6ecaa2a2c40ac1157d9704 |
| Base fixture | 766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e |
| Edited/final snapshot | f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735 |

The native registered `go` and `monitor` handlers resolve to the verified cloned `syncheck/online-comp.rkt`, SHA256 `40375b7a80aa1139232c653ab2e216719267273925c22253a4043bbcd841a04f`. All four verified transformed source hashes and all 14 original native record hashes are included in the analysis JSON; the local helper manifest remains separate from the measured-source manifest.

Reproduce the read-only analysis from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 analyze.py \
  --decoded ../openracket-recovery/results/run-38125605788/decoded \
  --acceptance ../openracket-recovery/results/run-38125605788/decoded/annotation-application-ci-acceptance.json \
  --decode-index ../openracket-recovery/results/run-38125605788/decoded-index.json
```

Displayed sums/maxima are rounded to 0.001 ms and means to 0.000001 ms. The linked JSON retains full numeric input and derived precision. No rounded value replaces a native acceptance check.
