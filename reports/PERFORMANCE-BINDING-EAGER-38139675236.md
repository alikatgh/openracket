# Mac eager binding-table experiment: reject adoption

Native run [38139675236](https://github.com/alikatgh/openracket/actions/runs/38139675236), commit `ff336169816d54d89804805c0304436934cc08cd`, completed successfully. All six trials and three matched pairs satisfy the preregistered correctness, completed-work and first-getter gates. The candidate does not demonstrate a speed benefit: two pairs regress, one improves, and application-stage heartbeat median delay worsens in every pair. Keep the candidate default-off; do not adopt it.

The eager implementation removes the previous lazy candidate’s multi-second public-getter stall. Its first getter is 0.023–0.028 ms in this run, below the unchanged 1.000 ms per-trial threshold. That correctness/resource improvement over the rejected design is not a gain over the matched stock runtime.

## Evidence and comparison contract
- 124 native result rows pass; all 65 JSON documents were reconstructed with recursive and whole-document digests. The local strict analyzer accepts the complete matrix with no failures. No failed timing record is omitted.
- Three fresh-process pairs, ordered stock/candidate, candidate/stock, stock/candidate. Official Racket 9.3 on the standard macOS ARM64 runner; one mixed 1 MiB source fixture and one real edit per trial. Both arms retain the same 256 MiB job preference, original 20 ms annotation batching, tools and source. Producer phase points are off in both arms.
- Both arms include identical common request/outcome/completion observers and the same 50 ms closed-loop low-priority heartbeat. “Stock” below means this common-observer stock control. There is no uninstrumented-overhead estimate or physical input-to-photon measurement.
- Every trial has one matching current request, clean `handler-results`, one monitor payload, 292,728 trace entries and 74,675 rename-capability rows, zero monitor errors/invalid payloads, completed lexer and actual final annotation application. Registry, prefab, pending Run settings, source and full export graph agree across all six. Profiles/addons are independently fresh.
- Actual GUI-module activation/source pins and the candidate’s live witness prove the eager path ran. All three candidates had 74,675 immediate accepted writes, 14,936 public keys, zero duplicates, pending entries, materializations, fallback calls and failures before exposure. First getter preserves the actual hash and all write counts while clearing only auxiliary caches; second getter leaves state unchanged.
- The complete exported graph is identical in every trial: 14,936 keys and 74,675 edges, mutable strong equal? hash with immutable equal? set values, SHA256 `6da6a80a8c6f9aac26502791d7abd00a8115b0088526671315fbff78cef50eb8`. Small native graph/navigation, actual-form mutation/fault tests and full trace/rename equivalence also pass.

## Completed work
All durations below are seconds. Application is actual annotation entry through the final synchronous application-complete endpoint. It includes yielded/interleaved GUI work and is not exclusive annotation CPU time. Request→application and open→application are separate endpoints; terminal receipt and lexer validity do not replace them.
| Pair | Application stock → eager | Application change | Request → application | Open → application |
| --- | --- | --- | --- | --- |
| 1 | 24.950 → 26.263 | +5.26% | 43.137 → 46.846 | 45.454 → 50.114 |
| 2 | 25.060 → 35.590 | +42.02% | 45.449 → 53.799 | 48.518 → 56.225 |
| 3 | 24.828 → 22.649 | -8.78% | 41.701 → 38.062 | 44.267 → 40.326 |

Application arm medians: 24.950 → 26.263 s, **5.26% slower**; median matched-pair change is also +5.26% here. Request→application medians are 43.137 → 46.846 s (+8.60%), and open→application medians are 45.454 → 50.114 s (+10.25%). These are descriptive results from three pairs, not estimates of a universal regression magnitude.

| Pair | Open → lexer observation | Application after lexer | Application after terminal return | Open → post-export verification |
| --- | --- | --- | --- | --- |
| 1 | 38.477 → 45.245 | 6.977 → 4.869 | 21.484 → 22.447 | 46.251 → 50.864 |
| 2 | 41.746 → 48.493 | 6.773 → 7.732 | 21.554 → 30.706 | 49.202 → 57.077 |
| 3 | 36.962 → 35.282 | 7.305 → 5.044 | 21.509 → 18.928 | 44.914 → 40.989 |

All application endpoints occur after lexer validity and the terminal callback return. The actual post-export endpoint includes waits, graph verification and reporting outside getter timing. Application + first getter is a disjoint two-interval sum, not an alternative readiness definition; because getters are under 0.03 ms, its result is effectively the same two regressions/one improvement.

## Public getter: no deferred work
| Pair | First getter ms, stock → eager | Second getter ms, stock → eager | Fixed eager ≤1.000 ms |
| --- | --- | --- | --- |
| 1 | 0.021 → 0.023 | 0.001 → 0.002 | PASS |
| 2 | 0.014 → 0.024 | 0.001 → 0.002 | PASS |
| 3 | 0.017 → 0.028 | 0.002 → 0.001 | PASS |

Each getter snapshot interval in either arm allocates 912 bytes and records zero GC and zero all-places CPU milliseconds. Full graph walking happens afterward and is excluded from the command interval. No graph traversal or replay is deferred into the eager getter. The threshold was fixed before this run and was not widened. It is a benchmark acceptance bound, not a real-time guarantee.

## Event-loop responsiveness
Heartbeat values are milliseconds, per-trial nearest-rank percentiles. Samples are selected by planned deadline within each inclusive endpoint window. Planned→handler includes producer scheduling lateness; queued→handler starts at actual submission. One request is outstanding at a time, so this is a closed-loop queue observation, not hardware typing. Trials are never pooled.
| Pair | Samples stock / eager | Application p50 | p95 | p99 | max |
| --- | --- | --- | --- | --- | --- |
| 1 | 207 / 192 | 37.000 → 123.159 | 140.582 → 142.170 | 166.961 → 244.808 | 364.968 → 341.614 |
| 2 | 209 / 266 | 34.435 → 121.922 | 134.167 → 148.258 | 247.890 → 224.017 | 301.281 → 389.476 |
| 3 | 210 / 175 | 19.534 → 120.851 | 134.044 → 137.062 | 153.727 → 246.948 | 292.739 → 325.349 |

Application p50 and p95 planned delay worsen in all three pairs. P99 and maximum are mixed, with two regressions each. Actual queued→handler application p50 is 36.696/19.801/18.638 ms stock versus 121.529/120.228/120.439 ms eager; the median shift is not explained solely by off-GUI producer lateness. This experiment does not identify which interleaved GUI activity caused the change.

| Pair | Whole-workload p95 | p99 | planned max | queued max | producer-lateness max |
| --- | --- | --- | --- | --- | --- |
| 1 | 173.947 → 170.775 | 1412.782 → 1314.142 | 3411.745 → 4915.482 | 3409.937 → 4903.694 | 183.258 → 1704.099 |
| 2 | 167.620 → 169.695 | 982.897 → 934.769 | 4414.285 → 3589.009 | 4413.102 → 3584.460 | 1172.559 → 1020.929 |
| 3 | 146.478 → 153.451 | 979.969 → 988.987 | 3598.057 → 3200.139 | 3597.778 → 3199.916 | 877.528 → 81.984 |

Multi-second whole-workload delays remain in both arms. Application boundary-clipped maximum handler gaps are 414.968/351.281/342.739 ms stock versus 391.614/439.476/375.349 ms eager. All heartbeat workers stop/join successfully; each arm drains one previously submitted request after stop. Drain completion is 6.311–19.231 ms after stop. Heartbeat ends before the separate public-getter measurements, so no getter-period percentile is claimed.

## Allocation, GC and memory
Allocation is cumulative byte churn, not simultaneous RAM. Counters are sampled at the same process endpoints and include concurrent/interleaved work across places; they do not establish which thread, custodian or component allocated the bytes. All-places CPU can exceed wall duration. No counter decreases were observed.
| Pair | Application allocation GB | Change | Application GC ms | All-places CPU seconds |
| --- | --- | --- | --- | --- |
| 1 | 10.743345 → 10.945920 | +1.89% | 925 → 1093 | 26.644 → 28.356 |
| 2 | 10.822448 → 10.903807 | +0.75% | 880 → 1499 | 26.922 → 38.334 |
| 3 | 10.722459 → 10.736318 | +0.13% | 906 → 979 | 26.501 → 24.587 |

Application allocation and GC increase in every pair. Allocation arm medians rise 1.49% (median paired change +0.75%); GC arm medians rise 906 → 1,093 ms. Adding the first getter contributes only the same 912 bytes in each arm and does not reverse this result.
| Pair | Request→application allocation GB | GC ms | Managed memory before getter MB |
| --- | --- | --- | --- |
| 1 | 20.277666 → 20.382478 | 7824 → 9245 | 1080.296 → 1026.033 |
| 2 | 20.280182 → 20.415080 | 8068 → 8372 | 1075.418 → 1095.071 |
| 3 | 20.256690 → 20.292239 | 7011 → 6478 | 1086.336 → 1083.579 |

The cumulative request interval allocates about 20.3–20.4 GB in all six trials. Managed snapshots are about 1.03–1.10 GB and must not be called RSS. This batch does not capture RSS or peak memory; no memory-footprint improvement is established.

## Earlier failures remain in the record
Run [38137618373](https://github.com/alikatgh/openracket/actions/runs/38137618373) failed correctness and produced no timings. Its three off-mode tests intentionally threw from a custom owner hash, then tried to count the stock-path hash whose runtime lock had been abandoned. The repaired test now observes that stock/off boundary on owned, bounded threads, retains insertion-error parity and verifies cleanup/reset. All three off modes now pass 2,836 assertions each; enabled passes 3,234. Production and all 33 telemetry files stayed byte-identical.

The earlier candidate-off Check Syntax workflow printed the correct eight-edge graph, then failed an unidentified postflight assertion with an empty exception message. The retry adds typed failure/scalar evidence but leaves every assertion unchanged. Candidate-off now passes with stock_calls=8 and public_keys=3. This does not identify or retroactively repair the earlier exact failing field. The small candidate-on duplicate count varies between the two native runs; all six measured workload requests in this run have duplicate count zero.

## Decision and reproducibility
Reject adoption. The eager design achieves its immediate-public-table/constant-time-exposure contract, but this matched workload shows no reliable completed-work improvement, no allocation reduction, and worse application median queue response. No further binding-table variant is justified by these results alone. The delivered preview remains separate; there is no combined preview speed claim.

- Raw log SHA256: `37483c96bb5f0b39a90a38d59219095ff645c9dc9905d12cbfe4c584b6cdd50e`.
- Coherent native source manifest: `b45348718db6c724823e9ff21056e127252f5baff3da337fd22de5bf685c181d`; production GUI: `80a32b3ebebbe741fe35a6c47f834cf35c0ea708c505961d0d98ce36ea37d6e3`.
- Common telemetry SHA256SUMS: `8c0e0fe66cf94cad688f935346a93fa7792e77b6e3bf7c85d012a1280c4c7fec`.
- New read-only analyzer v2 SHA256SUMS: `8a20c9b36b37706f51faea4af16511f27f2d7c68643529267ed01528099bf352`; 44 synthetic checks passed before data. This was newly authored after workspace loss, not asserted to recover an older analyzer hash.
- Full raw records, recomputed scalar acceptance, all six trial metrics and exact percentile selections are retained in the accompanying analysis.json. Independent raw-log/digest/arithmetic verification is recorded separately.

