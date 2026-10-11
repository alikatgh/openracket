# macOS stock memory-limit sensitivity: successful analysis at 256 MiB

Date: 2026-10-11. Native evidence: [GitHub Actions run 38107957744](https://github.com/alikatgh/openracket/actions/runs/38107957744), commit `0cb2eeb546061771806ff228fc2356692e97a631`.

## Result and recommendation

**256 MiB was the smallest tested limit that completed the final background analysis in all three trials.** The original 128 MiB setting failed with an explicit out-of-memory terminal in all three. Both 256 and 512 MiB delivered a genuine clean Check Syntax monitor message and the original `handler-results` response, followed by the current final-source GUI callback, in all three trials.

This supports a capacity choice for this tested 1 MiB fixture. It does not establish a code optimization, a universal sufficient limit, or a responsive large-file experience. At 256 MiB, the final tool callback still took **33.222–39.155 seconds** from open; observing both valid coloring and that callback took **33.274–44.117 seconds**. Increasing to 512 MiB had no consistent timing benefit. A fresh isolated preview can use 256 MiB subject to its separate adoption checks, while preserving existing user choices and stock installations. The setting affects both background jobs and the Run evaluator.

## Matched workload and verification

- Official full Racket 9.3 CS on one standard macOS 15.7.9 ARM64 GitHub runner with **7 GiB physical RAM**. One large workload ran at a time. All nine processes completed within the existing 60-second process deadline; the 45-second coloring and 15-second final-response bounds were unchanged.
- Three cyclic rounds: 128/256/512, then 256/512/128, then 512/128/256 MiB. Each trial had a fresh GUI process, preference home and add-on directory. This is not a cold filesystem-cache claim.
- The same stock window, editors, lexer, tools, default 20 ms coloring budget, source fixture, edits and 80 synthetic keys were used. All 80 keys started while the lexer was invalid in every trial. The 1000×700 requested window fits the observed 1024×768 desktop.
- No xref reply-cell, scan, color-budget, autosave or appearance candidate was installed. The same compact observer was installed in the independent diagnostic runtime for every arm. The pristine distribution, including bytecode, passed the whole-tree unchanged check.
- Only `drracket:child-only-memory-limit` varied. Before the timed GUI process, the public registered preference setter wrote it to an empty disposable profile. The helper verified the exact original 128 MiB default, a one-key disk delta, forced disk readback, fresh paths, and absence of legacy/runtime fallback stores. GUI-side preference capture and the actual expansion worker's cap independently matched each requested limit. Custodian memory accounting was available in all nine workers.
- Pending-next-Run language settings, all other captured preferences, actual ordered handler registry and actual online-request prefab matched. Pending annotations were `lang-default`, resolved to `debug`, with no metadata errors. The actual online prefab was `#s(prefab-module-settings #() (default) #t #t none #t)`; these are separate observations, not a claim that the two configuration formats are interchangeable.
- The exact final editor source was verified after the timed work: 1,048,657 characters, SHA-256 `55f0c420e49ecfe21ca72b015457cce645ccf3b93bdbfec3f898e36fb54b41c7`. Each accepted terminal matched that source and the current request. All observers reported zero dropped requests and zero observer errors.
- Native preparation passed real preference persistence/refusal tests, observer protocol and kill-safety tests, source/supervisor/validator checks, caller compilation, and a genuine stock host Check Syntax smoke test. The Unix-only legacy-home refusal test was appropriately skipped on macOS; the native test class itself was executed.

## Actual analysis outcome and timing

Seconds below start at the first file-open command. “Callback” is the actual final-source callback completion recorded at the original GUI response seam. “Both observed” is the later harness observation after valid coloring and that callback are both available. Coloring validity alone does not prove tool completion. `finished-expansion` alone is also insufficient.

| Round | Limit MiB | Final tool result | Clean monitor messages | Open → valid lexer, s | Open → actual callback, s | Open → both observed, s |
|---|---:|---|---:|---:|---:|---:|
| 1 | 128 | out of memory | 0 | 44.167 | 33.059 | 44.178 |
| 1 | 256 | handler-results | 1 | 44.112 | 39.155 | 44.117 |
| 1 | 512 | handler-results | 1 | 47.630 | 41.604 | 47.640 |
| 2 | 128 | out of memory | 0 | 28.877 | 25.351 | 28.882 |
| 2 | 256 | handler-results | 1 | 43.605 | 38.656 | 43.613 |
| 2 | 512 | handler-results | 1 | 48.654 | 42.591 | 48.669 |
| 3 | 128 | out of memory | 0 | 30.440 | 26.462 | 30.454 |
| 3 | 256 | handler-results | 1 | 33.268 | 33.222 | 33.274 |
| 3 | 512 | handler-results | 1 | 29.081 | 30.913 | 30.936 |

All three 128 MiB terminals were `abnormal-termination` with the explicit message “Expansion thread terminated unexpectedly (out of memory)” and zero monitor messages. All six larger-limit terminals were `handler-results`, with one real pair-shaped monitor message and zero monitor string/other errors. These trials observe the actual stock response and clean monitor delivery; they do not repeat a whole trace-equivalence comparison for the 1 MiB fixture.

Median open→lexer times were 30.440, 43.605 and 47.630 seconds for 128, 256 and 512 MiB. Their corresponding actual callback medians were 26.462, 38.656 and 41.604 seconds. **The 128 MiB timing is an early-failure path, so these are not equal-work speed ratios.** In the third 512 MiB trial the lexer became valid at 29.081 seconds, but the tool callback arrived at 30.913 seconds. Reporting only the coloring endpoint would omit 1.832 seconds of unfinished analysis there.

512 MiB completed later than 256 MiB in the first two rounds and earlier in the third. Three observations per limit do not establish a distribution or a universal resource policy.

## Typing and event-loop tails

The producer submits one outstanding key at a time, with its next intended deadline 16 ms after the previous low-priority fence. This is **closed-loop synthetic pacing**. Planned-deadline latency includes a delayed producer as well as GUI queueing and editor handling. Queue→handler excludes delays before submission. The low-priority fence includes other queued work and does not measure pixels reaching a display. None of these numbers is physical input-to-photon latency.

Each row contains 80 keys. Percentiles use nearest rank, so p99 equals the observed maximum for this sample count. No keys or failed tool outcomes were discarded.

| Round / MiB | Planned → editor median / p95 / max, ms | Queue → handler p95 / max, ms | Planned → low-priority fence p95 / max, ms |
|---|---:|---:|---:|
| 1 / 128 | 16.007 / 44.332 / 79.206 | 7.195 / 23.484 | 211.480 / 962.400 |
| 1 / 256 | 16.109 / 34.214 / 61.608 | 7.483 / 20.896 | 190.294 / 813.593 |
| 1 / 512 | 18.578 / 53.036 / 104.319 | 18.944 / 21.915 | 187.975 / 779.815 |
| 2 / 128 | 11.817 / 29.037 / 44.013 | 6.452 / 20.618 | 180.946 / 587.984 |
| 2 / 256 | 13.760 / 40.205 / 67.230 | 10.452 / 29.483 | 182.943 / 852.179 |
| 2 / 512 | 14.812 / 37.115 / 46.445 | 8.724 / 14.903 | 175.778 / 781.719 |
| 3 / 128 | 10.508 / 33.271 / 91.261 | 5.948 / 24.300 | 167.250 / 762.584 |
| 3 / 256 | 15.121 / 37.578 / 54.498 | 6.742 / 19.267 | 176.746 / 728.209 |
| 3 / 512 | 10.415 / 25.838 / 29.748 | 5.905 / 6.803 | 158.893 / 501.493 |

At 256 MiB, planned→editor p95 was 34.214–40.205 ms, and maxima were 54.498–67.230 ms. Individual synchronous editor-command p95 was 25.627–29.493 ms. Producer scheduling delay reached 53.520 ms in the first 256 MiB trial, which a queue-only measure would miss. Planned→fence maxima were 728.209–852.179 ms. There is no consistent typing-tail improvement from 512 MiB.

Heartbeat callbacks use a separate 16 ms, one-outstanding-request probe. Callback gaps can include a delayed producer, GUI work and garbage collection. They are not a direct per-pause causal classification.

| Round / MiB | Synchronous file-open command, ms | Maximum heartbeat gap during typing, ms | Maximum heartbeat gap during post-typing coloring, ms | Maximum heartbeat gap across all phases, ms |
|---|---:|---:|---:|---:|
| 1 / 128 | 2451.796 | 728.073 | 1261.417 | 2453.973 |
| 1 / 256 | 2596.171 | 109.985 | 872.838 | 2601.414 |
| 1 / 512 | 2713.145 | 556.974 | 1156.911 | 2715.417 |
| 2 / 128 | 1533.844 | 416.527 | 1157.828 | 1535.966 |
| 2 / 256 | 2493.969 | 693.714 | 894.151 | 2500.974 |
| 2 / 512 | 2334.630 | 572.394 | 1315.407 | 2337.342 |
| 3 / 128 | 1604.362 | 499.522 | 1426.401 | 1606.948 |
| 3 / 256 | 1668.390 | 579.740 | 972.297 | 1671.131 |
| 3 / 512 | 1517.008 | 363.768 | 701.372 | 1519.629 |

The 256 MiB synchronous open still blocked for 1.668–2.596 seconds. Subsequent heartbeat gaps reached 0.694 seconds during typing and 0.973 seconds during post-typing coloring. These establish a remaining responsiveness problem even when background analysis has enough capacity. Raw evidence and the derived JSON retain every heartbeat and the separate dispatch/gap, editor, producer and fence summaries rather than collapsing them into one “latency” number.

## Allocation, garbage collection and resident memory

“Allocated GB” is cumulative allocation churn from the GUI's before-open snapshot to the end-of-workload snapshot. That endpoint includes both completion observations and the subsequent 500 ms idle interval, before the explicit cleanup collections. It includes concurrent stock work, intermediate requests, observer activity and reporting allocations; it is not the allocation of just the final expansion or a particular thread/place. GC is the elapsed GC counter delta over that same scope. Peak native RSS is the operating system's maximum for the whole child process, including startup/cleanup outside the narrower counter interval. GB below is decimal; configured MiB is binary.

| Round / MiB | Allocated GB | GC counter, s | Peak native RSS, GB | Managed bytes at workload end, GB | Observed requests |
|---|---:|---:|---:|---:|---:|
| 1 / 128 | 11.832 | 6.645 | 1.221 | 0.663 | 4 |
| 1 / 256 | 17.822 | 7.139 | 1.492 | 1.046 | 3 |
| 1 / 512 | 17.806 | 8.435 | 1.528 | 1.001 | 3 |
| 2 / 128 | 11.736 | 4.588 | 1.236 | 0.670 | 3 |
| 2 / 256 | 17.452 | 7.591 | 1.487 | 1.002 | 3 |
| 2 / 512 | 17.807 | 8.759 | 1.507 | 0.994 | 3 |
| 3 / 128 | 11.567 | 4.636 | 1.241 | 0.664 | 3 |
| 3 / 256 | 17.331 | 6.024 | 1.543 | 1.007 | 3 |
| 3 / 512 | 17.778 | 5.300 | 1.501 | 1.055 | 3 |

Successful 256/512 MiB trials allocated 17.331–17.822 GB cumulatively, versus 11.567–11.832 GB for the aborted 128 MiB trials. This is **allocation churn, not 17 GB of resident RAM**. The larger trials complete trace/tool work that the 128 MiB trials abort, so lower allocation in the aborted arm is not evidence of greater efficiency.

At 256 MiB, observed peak RSS was 1.487–1.543 GB and end-of-workload managed memory was 1.002–1.046 GB. At 512 MiB, peak RSS was 1.501–1.528 GB. The job limit is a custodian-owned live-memory limit checked after collection, not an application-wide RSS ceiling. In stock DrRacket this same preference also governs the Run evaluator. It should not be described as restricting the whole application to 128/256/512 MiB.

At 256 MiB, the GC counter increased by 6.024–7.591 seconds. This run does not have timestamped per-collection attribution sufficient to assign each GUI pause to GC or identify the thread that caused the allocation. Earlier tests showed that cumulative counters cannot safely partition GUI versus place allocation ownership; this report uses same-observer endpoint deltas and does not subtract cross-place baselines or sum them.

There were three observed requests in eight trials and four in the first 128 MiB trial. Replaced nonfinal requests can do different amounts of work before cancellation. The final request/source is exact, but whole-process churn is not a pure cost of one completed request.

## Instrumentation and limits

All three arms used the identical compact observer, not the heavier phase/stack profiler. One-time GUI registration took 48.513–84.137 ms before the timed open. Summed measured GUI hook time was 11.930–48.074 ms over 7–8 calls; the actual worker's one-shot observation plus primary JSON write took 2.757–10.095 ms. Those are directly observed local intervals, not a complete causal estimate of observer-induced GC/scheduling overhead. The secondary timing-file write is not included in its own measurement.

Profile setup took 663.232–1333.877 ms before starting the GUI timer. Even the 128 MiB arm explicitly persisted its one expected preference key. This fresh matrix is internally matched; older implicit-default or uninstrumented runs should not be combined into a new speed ratio. Autosave cadence and all tools stayed enabled. Normal scheduler/cache variation remains, and three trials are insufficient for significance claims.

## Next useful engineering experiment

Use the now-adequate 256 MiB configuration for one genuine final-request capture and two bounded replays of the unchanged stock worker/registry protocol. Reuse the existing phase probes, and add only a weak reference to the already-instantiated xref service thread alongside the actual working and monitor threads. Require a clean monitor trace and `handler-results`, preserve current timeouts, and keep source/settings/capture identity checks.

This can distinguish initial expansion, document lookup, trace construction/serialization and compilation through actual completed work. The previous 128 MiB phase probe ended during Check Syntax after `document-variable`; its monitor could be waiting on the unsampled serial xref service. The rejected reply-cell change did not establish that service as the allocation owner. A completed phase breakdown is the smallest next step before selecting an allocation reduction or a process-isolation experiment. It is diagnostic work and should not delay the separately tested capacity update.

## Reproduction and evidence integrity

- Run and source: [38107957744](https://github.com/alikatgh/openracket/actions/runs/38107957744), [commit 0cb2eeb](https://github.com/alikatgh/openracket/commit/0cb2eeb546061771806ff228fc2356692e97a631).
- Frozen experiment: `experiments/memory-sensitivity`; source setup and measured workload were reviewed before publication. Native logs contain complete losslessly chunked evidence; no capture payload or artifact upload was used.
- All 45 JSON documents were reconstructed with exact recursive-array and whole-document digests. The strict nine-record matrix validator passed after reconstruction.
- Raw macOS log SHA-256: `e557bed4bd7eab294de338314f9e2600af5919584099f89fd8759ea4d97a9234`.
- Reconstructed matrix SHA-256: `3c525da661155a2e254dc1fc9b977908d1c097adbd581fccaa35fbfa4f7db337`.
- Common observer support SHA-256: `79c02e6652e7fa4158531384c2d0382a32487b21620522529e325c44394d0d7b`.
- Public preference helper SHA-256: `9b761799e61b45388ae21461d358a819274ae1923e88959351a9f9b46337abc0`.
- Original loaded xref SHA-256: `acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7`.

`analyze.py` derives every table from all nine raw records and rejects incomplete matrices, changed settings, mismatched actual caps, reused profiles or inconsistent final outcomes. `test_analyze.py` has five passing regression tests, including real-data capacity classification, outcome/trace rejection, one-key/profile checks and nearest-rank quantiles. Full derived per-trial quantiles, heartbeat phases and counter endpoints are retained in `analysis-38107957744.json`.
