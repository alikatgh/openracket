# Native GUI arrow and pending gap diagnostic

## Result and decision

The accepted nested diagnostic identifies the original `add-to-bindings-table` expression as the largest measured component inside arrow insertion: **4.598716 seconds across 74,675 calls**, with every binding result true. Start-range and end-range insertion take **0.612092 and 0.629834 seconds**. Together the three nested operations account for **5.840642 seconds, 95.48% of inclusive arrow wall**. Inclusive arrows take **6.117304 seconds, 66.73% of measured entry-call wall and 25.29% of the full application batch span**. This supports a narrowly scoped investigation of the original binding-table operation while preserving its semantics. It does not establish CPU, allocation or GC ownership.

The observed batch span is **24.185719 seconds = 9.423734 seconds active + 14.761985 seconds queued waiting**. Waiting is **61.04%** of that span. Sparse pending-handler stacks repeatedly contain exact coloring, style-change, graphics-update and editor-port/snip-scan functions, but the samples cannot assign the entire waiting interval to them.

**Coverage materially limits the gap conclusion.** Of 143 stored samples, 142 end before the first host observation of final lexer validity. The sole later sample is wait 166; none of waits 167–454 is sampled. The last capture ends **6.086294 seconds before application-complete**. Coloring-related sample prominence therefore describes the earlier sampled portion of this run; the final portion remains unsampled. This is not a complete explanation of the 14.762 seconds of waiting.

Both genuine-GUI arms pass exact native acceptance. The downloaded macOS log independently verifies **29/29 passing diagnostic result rows**, including native preflight, compilation, captures, acceptance, evidence transport and the final pristine-runtime check. The workflow completed successfully. Observed common application wall is 24.185675 seconds versus 22.351600 seconds control. A single common-observer control and one more heavily instrumented process establish neither a gain nor precise/causal instrumentation overhead.

## Run and accepted workload

- Run: [38128156864](https://github.com/alikatgh/openracket/actions/runs/38128156864), 2026-10-11.
- Commit: `bc4958688060e9ff6b8d9806cdb36d3cd70fa0d1`.
- Native macOS Racket 9.3, one fresh GUI process per arm, separate fresh profile/addon directories, stock 256 MiB child limit (`268435456` bytes), actual memory accounting available, online compilation and coloring enabled.
- Workload: open the unchanged mixed 1 MiB fixture and insert one `x` at character 524139 in its middle comment. Base length 1,048,576; final editor length 1,048,577. This is one specific first-edit diagnostic, not a general editing benchmark.
- Both arms retain common GUI observation, scalar slice counters, per-entry guards, correlation hashing and trace-schema scanning. Only observed enables detailed application/nested-arrow timing and the bounded pending-handler sampler. Worker producer phase points are OFF in both arms, with empty phase arrays.
- Native acceptance is `accepted: true`, `failures: []`, and both arm summaries are valid. Native preflight reports 97 tests with zero skips, plus 24 profile-helper tests. Separate adapter and transport suites report 6 and 19 passing tests respectively. The offline analyzer has 55 passing synthetic tests; these are separate from native evidence.
- Original 20 ms replay batching, callback priority, feature configuration, 90-second absolute post-edit deadline, 190-second GUI process bound and 235-second outer bound remain unchanged. No product optimization was tested.

## Outcome and currentness

Each arm has one matching final request, selected worker job 1 and current application generation 1. Both receive `handler-results` with **270,280 compiled bytes**, one clean monitor message/trace batch, **292,728 trace entries** and **74,675 independently recognized rename-capability rows**. Actual registry, source, pending next-Run settings and scalar terminal/monitor evidence match. The registry contains the exact prepared `syncheck/online-comp.rkt` handlers in the original `go` then `monitor` order.

Final source snapshots are unchanged and final lexers are valid. Terminal callback and normal application endpoint are current and noncancelled. No duplicate/stale events, dropped records, observer errors, unknown tags, reentrant entries, unmatched/open entry/final/batch/wait state or nested-arrow state remain. Both supervisors record exit 0, no timeout, complete cleanup and verified fresh one-key preference setup. Source/currentness is reverified after sampler stop and join. These checks establish synchronous application completion, not completed painting or full trace/capability equality.

The pending next-Run settings agree exactly as serialized. They are recorded configuration context, not worker instrumentation. The child memory limit is an actual worker cap, not an allocation budget for the whole GUI process.

## Observed application accounting

| Quantity | Count | Wall sum ms | Mean ms | Maximum ms |
| --- | --- | --- | --- | --- |
| Active batches | 455 | 9,423.734 | 20.711503 | 112.292 |
| Requeue waits | 454 | 14,761.985 | 32.515385 | 289.827 |
| All 13 entry-call categories | 292728 | 9,167.909 | 0.031319 | 101.945 largest category maximum |
| Four synchronous final calls | 4 | 4.690 | 1.172500 | 3.543 largest final maximum |
| Signed unassigned active remainder | not separately sampled | 251.135 | not available | not available |
| First batch through final batch end | one span | 24,185.719 | not applicable | not applicable |

The decomposition is **9,423.734 = 9,167.909 + 4.690 + 251.135 ms** active, and **24,185.719 = 9,423.734 + 14,761.985 ms** full span. Entry calls, finals and remainder are components of active time; nested arrow operations are components of the arrow category. None should be added twice.

Observed counts reconcile as 455 batches = 454 yields + 1, and 454 waits = 454 resumes = 454 yields. Control has 435 batches and 434 yields/resumes/waits; its detailed durations are unmeasured, not zero. Slice counts can change under instrumentation.

Independent decimal recomputation from the raw JSON gives active + wait − span = **1E-12 ms**, far inside the frozen **0.241857190 ms** arithmetic tolerance. The signed active remainder and arrow remainder are positive. No negative remainder was hidden by a clamp. This tolerance is an accounting check, not a performance threshold.

The first batch starts **0.025 ms after common application-enter**, and the last batch ends **0.069 ms after common application-complete**. Therefore the full batch span exceeds the common application interval by **0.044 ms**. The definitions remain distinct even though this difference is small.

Active time includes dispatch, instrumentation, scheduling and queue submission. Requeue wait starts after the original queue call returns and includes the old callback tail, eventspace waiting and intervening GUI work. It is not idle time or scheduler-exclusive work.

## All 13 annotation categories

All times are inclusive observed call-wall. Percentages use the **9,167.909 ms entry-call sum**; the full batch span is a separate denominator. Means are sum/count, maxima are observed maxima, and zero-count means are unavailable.

| Exact stock tag | Calls | Wall sum ms | Mean ms | Maximum ms | Entry-call share |
| --- | --- | --- | --- | --- | --- |
| `syncheck:add-arrow/name-dup/pxpy` | 74,675 | 6,117.304 | 0.081919 | 101.945 | 66.73% |
| `syncheck:add-tail-arrow` | 2,987 | 53.117 | 0.017783 | 5.205 | 0.58% |
| `syncheck:add-mouse-over-status` | 71,689 | 642.886 | 0.008968 | 6.211 | 7.01% |
| `syncheck:add-text-type` | 53,766 | 596.467 | 0.011094 | 42.409 | 6.51% |
| `syncheck:add-background-color` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-jump-to-definition/phase-level+space` | 29,870 | 239.079 | 0.008004 | 4.026 | 2.61% |
| `syncheck:add-require-open-menu` | 1 | 0.117 | 0.117000 | 0.117 | 0.00% |
| `syncheck:add-docs-menu` | 53,766 | 1,480.665 | 0.027539 | 13.327 | 16.15% |
| `syncheck:add-definition-target/phase-level+space` | 2,987 | 6.577 | 0.002202 | 3.114 | 0.07% |
| `syncheck:unused-binder` | 2,987 | 31.697 | 0.010612 | 1.257 | 0.35% |
| `syncheck:add-id-set` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-prefixed-require-reference` | 0 | 0.000 | not applicable | 0.000 | 0.00% |
| `syncheck:add-unused-require` | 0 | 0.000 | not applicable | 0.000 | 0.00% |

Counts sum exactly to 292,728, matching entries started, entries completed and the independent actual trace count. Arrow/name-dup + id-set counts are 74,675 + 0 = 74,675, matching independent rename-capability rows. Zero id-set calls provide no timing evidence for that category in other workloads.

## Nested original arrow operations

| Operation | Calls | Wall sum ms | Mean ms | Maximum ms | Inclusive-arrow share |
| --- | --- | --- | --- | --- | --- |
| `add-to-bindings-table` | 74,675 | 4,598.716 | 0.061583 | 101.858 | 75.18% |
| `start-add-to-range/key` | 74,675 | 612.092 | 0.008197 | 7.834 | 10.01% |
| `end-add-to-range/key` | 74,675 | 629.834 | 0.008434 | 24.584 | 10.30% |
| Nested total | three expression groups | 5,840.642 | not a per-arrow distribution | not aggregatable | 95.48% |
| Signed inclusive-arrow remainder | not separately timed | 276.662 | not available | not available | 4.52% |
| Inclusive original arrow entry | 74,675 | 6,117.304 | 0.081919 | 101.945 | 100% |

Binding outcomes are **74,675 true, 0 false**. Binding-expression count equals arrow count, and each endpoint count equals true bindings. Thus the original short-circuit endpoint branch was taken for every recorded arrow in this workload. There is no false-result timing sample here.

The binding expression accounts for about 75.18% of inclusive arrow wall and 19.01% of the full batch span. Its 101.858 ms maximum and the arrow category's 101.945 ms maximum are independent accumulator maxima, not paired per-call records. Inclusive call-wall can contain preemption, GC pauses and concurrent/observer work. The 276.662 ms arrow remainder contains unassigned work around the nested expressions; it is not pure observation overhead or exclusive CPU.

## Four final synchronous calls

| Operation in original order | Count | Wall sum ms | Mean ms | Maximum ms |
| --- | --- | --- | --- | --- |
| `update-blue-boxes` | 1 | 3.543 | 3.543000 | 3.543 |
| `update-drawn-arrows` | 1 | 0.911 | 0.911000 | 0.911 |
| `remove-bkg-running-color` | 1 | 0.226 | 0.226000 | 0.226 |
| `set-syncheck-running-mode` | 1 | 0.010 | 0.010000 | 0.010 |

The total is **4.690 ms**. Blue-box timing includes argument evaluation. These calls may initiate later coroutine/cache/timer, drawing/painting or running-indicator refresh work. Their small synchronous total is not proof that those later effects have completed or are cheap. Pointer/viewport-dependent context is not controlled by this measurement.

## Sparse pending-handler evidence

The sampler retained **143/143 attempts**, all with useful source evidence, spanning **127 distinct waits out of 454 (27.97%)**. There are **327 unsampled wait identities**. The 100 ms nominal cadence, 1,024-attempt cap, eight-frame cap and 240-character name/source cap remain unchanged. The cap was not reached, termination is cooperative `stopped`, and the snapshot is quiescent and complete.

The raw document preserves all 143 rows and all **1,144 frame occurrences**. There are **1,142 occurrences with a usable source and two source-less frames**, no completely missing frame lists and no text truncations. **141/143 samples (98.60%) report depth truncation**; every row contains eight frames, including two rows that do not report truncation. Therefore deeper callers are absent from almost all retained rows. There are 105 distinct exact rendered source/function/truncation groups.

The source/function table below is descriptive. `D/` substitutes only the identical clone-root prefix `/Users/runner/work/_temp/openracket-full.QjF764/racket-arrow-gap-probe/`; `H/` substitutes only `/Users/runner/work/openracket/openracket/retained-host/experiments/arrow-gap-probe/`. All remaining path text and function names are exact. No grouping merges basenames or normalizes paths. An unnamed frame is not an unknown file: its exact source remains available.

| Exact source with prefix substitution | Exact rendered function | Frame occurrences | Distinct samples | Distinct waits |
| --- | --- | --- | --- | --- |
| `D/share/pkgs/gui-lib/mred/private/wx/common/queue.rkt` | (unnamed) | 171 | 97 | 91 |
| `D/share/pkgs/gui-lib/framework/private/color.rkt` | `colorer-driver method in text-mixin` | 104 | 104 | 96 |
| `D/share/pkgs/gui-lib/mred/private/wxme/mline.rkt` | `update-graphics` | 104 | 19 | 19 |
| `D/share/pkgs/gui-lib/framework/private/color.rkt` | `colorer-callback method in text-mixin` | 96 | 96 | 90 |
| `D/share/pkgs/gui-lib/framework/private/color.rkt` | `continue-re-tokenize method in text-mixin` | 91 | 91 | 87 |
| `D/share/pkgs/gui-lib/mred/private/wxme/text.rkt` | `do-change-style method in text%` | 55 | 55 | 53 |
| `H/capture-host.rkt` | (unnamed) | 45 | 37 | 35 |
| `D/share/pkgs/gui-lib/mred/private/wxme/text.rkt` | `find-snip/pos method in text%` | 28 | 28 | 28 |
| `D/share/pkgs/gui-lib/framework/private/racket.rkt` | `wrapped-get-token` | 20 | 20 | 20 |
| `D/share/pkgs/gui-lib/mred/private/snipfile.rkt` | `open-input-text-editor` | 14 | 14 | 14 |
| `D/share/pkgs/gui-lib/mred/private/wxme/text.rkt` | `find-next-non-string-snip method in text%` | 14 | 14 | 14 |

The exact `colorer-driver` function appears in **104/143 samples (72.73%)**, `do-change-style` in **55/143 (38.46%)**, and `update-graphics` in **19/143 (13.29%)**. The latter produces **104 frame occurrences**, showing why occurrences are not sample counts. `open-input-text-editor` and `find-next-non-string-snip` appear in the **same 14 samples**, not 28 independent samples. One stack can contain several listed functions, so rows and sample percentages cannot be added into exclusive work shares.

These actual functions support the limited observation that tokenization/coloring, style changes, graphics updates and editor-port/snip scanning were on retained handler stacks while replay was pending. Queue-loop and diagnostic-host frames also occur; the common observer and host are part of this diagnostic context. No sample assigns the whole pending interval to a frame, proves that a function was using CPU at that instant, or attributes allocation/GC to it. The complete exact 105-group inventory, row indices and raw coordinates remain in `analysis-38128156864.json`.

### Wait duration lower bounds

For each distinct sampled wait, take the maximum capture-finished timestamp minus that wait's queue-return timestamp. Sum only across distinct waits. This produces **8,304.821 ms**, a demonstrated pending-duration lower bound equal to **56.26% of the 14,761.985 ms total actual waiting**. Repeated samples from one wait do not repeatedly add that wait's age.

This is not time owned by the sampled frames, unbiased temporal coverage, or the full duration of those 127 waits. The remainder of the total cannot be equated to unsampled-wait duration because sampled waits can continue after their last captured age. Longer waits have more chances to be sampled.

### Sampling position and lexer relation

| Observed endpoint | Same-process monotonic ms | Ms after selected request |
| --- | --- | --- |
| Sampler started | 6,967.636 | -542.270 |
| First batch started | 24,881.573 | 17,371.667 |
| First actual stored sample | 24,970.311 | 17,460.405 |
| First host observation of final lexer validity | 42,119.438 | 34,609.532 |
| Last stored capture ended | 42,980.929 | 35,471.023 |
| Common application completed | 49,067.223 | 41,557.317 |
| Last batch ended | 49,067.292 | 41,557.386 |
| Sampler stop requested | 49,086.213 | 41,576.307 |
| Sampler finished | 49,092.864 | 41,582.958 |
| Sampler joined | 49,093.137 | 41,583.231 |
| Post-join source/currentness verified | 49,223.662 | 41,713.756 |

The first actual sample is **88.738 ms after the first batch start**. The first 142 samples end before the host observes final lexer validity at 42,119.438 ms. The sole later sample ends at **42,980.929 ms**, **861.491 ms after that observation**, on wait 166 with retained paint/refresh-related names (`on-paint`, `redraw`, `refresh`, `process-snips`, `lloop`, style conversion and a loop). This is one raw observation, not an explanation of the remaining interval.

No rows cover the final **6,086.294 ms before common application-complete**, or **6,086.363 ms before final batch end**. There are no samples for the later 288 wait ordinals 167–454, plus 39 other unsampled waits among ordinals 1–166. The sampler continued until after application completion and joined successfully, so the absence is not an early-stop record. The bounded output does not retain each idle tick's timestamp; it does not establish precisely why no pending token was captured later. Short waits, phase alignment, scheduling effects or other timing structure must not be resolved by guesswork.

Lexer time is the first host observation of validity, not exact lexer completion. The strong pre-lexer concentration and depth truncation mean that the stack frequencies should not be extrapolated over the later application region or the full queue-gap total.

### Cadence capture costs and omissions

| Quantity and domain | Count or sum | Maximum | Mean where defensible |
| --- | --- | --- | --- |
| All cadence ticks | 390 | not applicable | not applicable |
| Pending-token attempts / stored rows | 143 / 143 | not applicable | not applicable |
| Idle ticks without pending token | 247 | not applicable | not applicable |
| Missed cadence ticks, all ticks | 31 | not retained by tick | not applicable |
| Stored-row missed-before / missed-through-capture ticks | 0 / 0 | 0 | not applicable |
| All-cadence scheduling delay, ms | 4,148.622 | 1,069.687 | 10.637492 per cadence tick |
| Stored-row scheduling delay, ms | 162.078 | 13.181 | 1.133413 |
| Actual capture/render duration, ms | 10.861 | 0.595 | 0.075951 per capture in this run |
| Stored-row actual spacing, ms | 18,010.506 across 142 intervals | 912.902 | 126.834549 |

Scheduling-delay totals/maxima cover **all 390 cadence ticks**, including 247 idle ticks. Capture-duration totals/maxima cover actual capture/render calls, including later-discarded calls if any; this run has no discards, so all 143 actual captures are retained. Stored-row scheduling delay is only 162.078 ms versus 4,148.622 ms for all cadence ticks. The approximately 3,986.544 ms difference belongs to nonstored/idle cadence ticks in this run; it is not per-stack or pending-gap ownership. All 31 missed ticks occur outside the retained rows' zero-missed counters. Idle tick timestamps were not retained, so neither quantity can be localized to the final unsampled region.

Stored actual spacing ranges from **88.901 to 912.902 ms**, with mean **126.834549 ms**. A 100 ms schedule does not imply evenly spaced useful pending samples. Capture duration ranges from **0.036 to 0.595 ms**, totaling **10.861 ms**. That narrow counter is not total observation overhead: it omits other bookkeeping/cadence work, nested timing overhead, common correlation/reporting and any perturbation of batching or runtime activity. Public continuation capture/conversion has no hard execution-time bound despite bounded retained output.

Race discards, stop discards, invalid-token discards, attempt-error discards, capture errors, absent/collected/dead/invalid handlers, handler deaths during capture, sampler errors and early wakes are all zero. No stock logger subscription is enabled. Truncation is explicitly preserved rather than silently treated as complete stack coverage.

## Common GUI endpoints

Values are milliseconds after each arm's own selected request observation. No absolute clocks are subtracted across processes. The table separates receipt, queue attempt, callback entry/return, application completion and first observed lexer validity.

| Endpoint | Control ms | Observed ms |
| --- | --- | --- |
| request-observed | 0.000 | 0.000 |
| monitor-received | 15,676.984 | 16,812.971 |
| monitor-callback-queue-attempt | 16,260.157 | 17,362.093 |
| monitor-callback-enter | 16,272.683 | 17,371.410 |
| application-enter | 16,272.836 | 17,371.642 |
| monitor-callback-return | 16,292.901 | 17,393.422 |
| terminal-received | 19,865.065 | 21,007.330 |
| terminal-callback-queue-attempt | 19,865.119 | 21,007.389 |
| terminal-callback-enter | 19,875.036 | 21,021.297 |
| terminal-callback-return | 19,875.446 | 21,022.974 |
| lexer-first-valid-observed | 31,580.678 | 34,609.532 |
| application-complete | 38,624.436 | 41,557.317 |

Application completes after terminal callback return and after the first host lexer-valid observation in both actual arms. The application-minus-terminal separations are **18,748.990 ms control** and **20,534.343 ms observed**; application-minus-lexer-observation separations are **7,043.758 and 6,947.785 ms**. These are endpoint separations, not exclusive remaining-work measurements. Other runs need not have this order.

## Same process elapsed and runtime counter windows

Each counter delta below is end minus start within the same arm. Allocation is the cumulative runtime allocation counter, GC is a cumulative runtime GC counter, and CPU is the process/all-places CPU counter. They are not per-tag, per-frame or exclusive thread measurements. Counter reads inside each point are sequential, not atomic. They can include worker, concurrent, observer and reporting work; allocation is not live heap, RSS or peak memory. CPU can exceed elapsed wall across places. No negative counter deltas occur in the listed windows.

Do not sum overlapping windows, subtract GC from wall to infer mutator CPU, or use these deltas to claim that bindings, coloring or sampled stacks allocated the bytes or caused the GC.

### Control

| Same-arm window | Wall ms | Allocation bytes | GC ms | CPU all places ms |
| --- | --- | --- | --- | --- |
| request to monitor receipt | 15,676.984 | 9,093,301,648 | 5,544 | 24,250 |
| monitor receipt to queue attempt | 583.173 | 518,539,696 | 104 | 844 |
| monitor queue attempt to callback entry | 12.526 | 15,066,800 | 1 | 23 |
| first monitor callback entry to return | 20.218 | 31,783,552 | 2 | 36 |
| common application entry to complete | 22,351.600 | 10,545,519,600 | 844 | 23,759 |
| request to terminal receipt | 19,865.065 | 13,696,696,880 | 5,987 | 31,107 |
| terminal receipt to queue attempt | 0.054 | 7,968 | 0 | 0 |
| terminal queue attempt to callback entry | 9.917 | 2,657,600 | 0 | 9 |
| terminal callback entry to return | 0.410 | 42,000 | 0 | 0 |
| request to terminal callback return | 19,875.446 | 13,699,404,448 | 5,987 | 31,116 |
| request to application complete | 38,624.436 | 20,172,591,472 | 6,493 | 48,876 |

### Observed

| Same-arm window | Wall ms | Allocation bytes | GC ms | CPU all places ms |
| --- | --- | --- | --- | --- |
| request to monitor receipt | 16,812.971 | 9,006,773,508 | 6,093 | 25,668 |
| monitor receipt to queue attempt | 549.122 | 515,496,224 | 100 | 866 |
| monitor queue attempt to callback entry | 9.317 | 12,066,288 | 0 | 15 |
| first monitor callback entry to return | 22.012 | 34,654,320 | 6 | 33 |
| common application entry to complete | 24,185.675 | 12,051,802,960 | 911 | 25,864 |
| request to terminal receipt | 21,007.330 | 13,623,515,012 | 6,520 | 32,834 |
| terminal receipt to queue attempt | 0.059 | 7,968 | 0 | 1 |
| terminal queue attempt to callback entry | 13.908 | 3,660,960 | 0 | 13 |
| terminal callback entry to return | 1.677 | 41,984 | 0 | 2 |
| request to terminal callback return | 21,022.974 | 13,627,225,924 | 6,520 | 32,850 |
| request to application complete | 41,557.317 | 21,586,335,284 | 7,104 | 52,414 |

## Broad control comparison

| Measurement | Control | Observed | Observed minus control |
| --- | --- | --- | --- |
| Common application wall ms | 22,351.600 | 24,185.675 | 1,834.075 (+8.21%) |
| Request to application complete ms | 38,624.436 | 41,557.317 | 2,932.881 (+7.59%) |
| Request to terminal callback return ms | 19,875.446 | 21,022.974 | 1,147.528 (+5.77%) |
| Host elapsed including startup ms | 47,039.818 | 49,006.744 | 1,966.926 |
| Supervisor elapsed ms | 47,386.317 | 49,364.126 | 1,977.808 |
| Batches | 435 | 455 | 20 |
| Yields / waits / resumes | 434 | 454 | 20 |

These are signed descriptive differences from one pair, not a precise estimate of observation overhead or a product speedup. Control has common observation and scalar counters rather than an uninstrumented production baseline. The observed process adds application/nested measurements and sampling. Scheduling, GC and run-to-run variation are not separated. Detailed control tag/final/batch/wait timings are absent and cannot be subtracted. Earlier diagnostic runs have different instrumentation and independent process variability; no cross-run gain is claimed here.

## Provenance and independent verification

The read-only analyzer reverified all 30 members plus the manifest of `openracket-arrow-gap-probe-freeze-20261011-0915` before importing exact verified source bytes. Frozen manifest SHA256 is `bbbc78ffcee48ce9fdf489689799cbb061f3635d0d4672a7bf0ef93e69c1e53c`. Frozen `compare` accepted the decoded eight-file arms and its full scalar arm summaries matched native acceptance exactly. Native source/handler/fixture attestations and all 16 original input hash entries were structurally checked. All 16 raw decoded documents and acceptance matched the saved canonical decoder index.

A separate read-only recomputation reproduced `analysis-38128156864.json` with exact canonical equality, recomputed accounting with decimal arithmetic, verified every same-arm endpoint/counter subtraction, and independently rebuilt all 105 exact source/function groups with their occurrence counts, sample indices and wait sets. It also verified the downloaded log hash and all 29 native diagnostic result rows. Full details are in `verification-38128156864.json`.

Original native byte hashes remain distinct from decoded-byte hashes and canonical JSON hashes. Native runtime/helper/fixture files are unavailable locally and were not reopened; their source verification remains a native CI attestation. The canonical decoder index binds raw frames, coordinates and host/sampler fields omitted from scalar acceptance to transported complete JSON values. It does not independently prove original native bytes or CI truthfulness.

The 20 MiB queued-sample bound applies to native control-only-escaped JSON. The offline reader's separate 64 MiB ceiling accommodates `ensure_ascii` expansion; it does not relax native acceptance. The actual decoded observed sampler file here is 550,075 bytes.

| Artifact | SHA256 |
| --- | --- |
| analysis-38128156864.json | `20e2840f7d998d359d10aadbce2a5c3259680a36d3a060650babb37cedd2698a` |
| macos.log | `21dccb0f22dc79e86b4edb824f6b6e750ee281fb8a0453faeddf73da35574982` |
| decoded-index.json | `b9bdf172b138b5d7067afd2643891022f4a0c93567e64ff30b04cbbf1a24bc77` |
| arrow-gap-probe-ci-acceptance.json | `02cfc5fcfb063ab7786f15e1806d272ad06299e2f219e64aeb5f3caab6d3002c` |
| analyze.py | `a6279c7807e89febadc188c9f3a316ce6bcbef758799f9418b3eda8c11b0c040` |

The original fixture hash is `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`; the final edited snapshot hash is `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`. Complete original native input hashes, decoded hashes, canonical hashes and prepared-source hashes remain in the analysis artifact.

## What this supports next

1. The original binding-table expression is the strongest measured nested-arrow target for a semantics-preserving source investigation. Its elapsed cost is established for this workload; ownership of allocations, CPU or GC is not.
2. The early sampled waiting region contains actual coloring/style/graphics/editor-port activity. Its strong pre-lexer concentration and almost universal depth truncation must accompany any explanation. The late region needs evidence before assigning a cause.
3. A performance-change decision needs repeated comparable control/observed trials and preserved output/currentness/feature checks. This accepted pair supplies a focused diagnostic, not a gain claim or authorization for a product change.

No production/source/native/runtime changes or remote actions were made while preparing this report. Raw evidence and the measured-source freeze remain unchanged.
