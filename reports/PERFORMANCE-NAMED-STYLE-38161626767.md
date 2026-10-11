# Mac named-style lookup: complete valid trial, inconsistent speed result

## Decision

Keep the candidate default-off and do not adopt it from this run. All native correctness gates and all six measurement arms passed, but ordinary full readiness and annotation application became slower in two of three matched pairs. The cache was active and served roughly 320,000 natural file-workload lookups per candidate trial. That activity did not translate into a consistent end-to-end or responsiveness gain.

Run [38161626767](https://github.com/alikatgh/openracket/actions/runs/38161626767), commit `bb6e994c0fca8ae1dd4796b12d6c70c65ab2acc3`, on the standard free Mac runner. Three pairs are descriptive evidence, not a confidence interval or a universal regression/speedup claim. No trial was omitted.

## Complete-work timings

Times are seconds. Full readiness is the host’s ordinary file-open/edit workload completion, requiring final source identity, lexer completion, successful actual worker/monitor outcome, and the late annotation-application endpoint. The post-edit and annotation intervals overlap the full workload; do not add them.

| Pair | Open/edit → full ready stock | Candidate | Change | Post-edit → full ready stock / candidate | Annotation application stock / candidate | Application change |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 47.360 | 53.177 | +12.28% | 45.579 / 50.998 | 26.728 / 27.338 | +2.28% |
| 2 | 59.698 | 40.890 | -31.50% | 58.009 / 38.547 | 33.011 / 21.696 | -34.27% |
| 3 | 39.396 | 41.559 | +5.49% | 37.496 / 39.459 | 21.220 / 22.636 | +6.67% |

The separate arm medians are 47.360 → 41.559 seconds for full readiness (12.25% lower), but the median paired percentage change is +5.49%, with a median paired delay of 2.162 seconds. Annotation arm medians likewise look 15.31% lower while the median paired percentage change is +2.28%. The large pair-2 improvement must not conceal the pair-1 and pair-3 regressions. Pair 2 ran candidate before stock; pairs 1 and 3 ran stock before candidate. These observations do not isolate the cause of the variability.

## GUI responsiveness

One low-priority callback is outstanding at a time, planned 50 ms after the previous callback. These are closed-loop queue measurements, not physical typing, rendering, or input-to-photon latency. Each percentile is nearest-rank within its own trial; unequal trial streams are never pooled. Rows are selected by planned deadline within the stated window. An outstanding final callback may run after the window and is retained.

Whole-workload callback latency, milliseconds. Each cell is p50 / p95 / p99 / maximum.

| Pair/arm | Samples | Planned deadline → handler | Submission → handler |
|---|---:|---:|---:|
| 1 stock | 312 | 107.70 / 165.30 / 894.59 / 3383.50 | 106.51 / 144.40 / 288.38 / 3383.30 |
| 1 candidate | 331 | 111.70 / 170.15 / 858.83 / 4119.18 | 109.45 / 159.78 / 857.86 / 4119.17 |
| 2 stock | 360 | 118.02 / 169.25 / 931.40 / 3129.04 | 114.65 / 154.48 / 900.86 / 3128.96 |
| 2 candidate | 272 | 102.82 / 163.92 / 873.00 / 4526.45 | 101.08 / 149.36 / 872.63 / 4524.76 |
| 3 stock | 257 | 106.48 / 159.55 / 775.76 / 3687.85 | 105.31 / 143.84 / 775.10 / 3687.31 |
| 3 candidate | 268 | 108.48 / 155.90 / 1012.83 / 3721.37 | 106.95 / 149.70 / 818.47 / 3721.23 |

The maximum submission→handler delay is the first queued callback in every trial, spanning the early open/edit work. It worsens in all three pairs. The median of the three per-trial submission→handler p95 values rises from 144.40 to 149.70 ms, and the median of the three p99 values rises from 775.10 to 857.86 ms. Planned-deadline tails are mixed and cannot support a broad responsiveness improvement.

Annotation-window submission→handler latency, milliseconds:

| Pair/arm | Samples | p50 | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|
| 1 stock | 228 | 19.64 | 139.69 | 167.18 | 288.38 |
| 1 candidate | 231 | 17.96 | 137.38 | 198.81 | 313.16 |
| 2 stock | 251 | 120.41 | 148.07 | 180.70 | 407.52 |
| 2 candidate | 199 | 13.63 | 132.16 | 163.25 | 359.00 |
| 3 stock | 182 | 16.92 | 130.53 | 160.94 | 342.49 |
| 3 candidate | 192 | 17.15 | 137.97 | 159.38 | 362.63 |

Full consecutive handler gaps also include the intended 50 ms pacing and producer scheduling; they are a different metric. Whole-workload p99 gaps stock→candidate were 374.64→363.69, 463.28→700.52, and 755.05→869.64 ms. Maximum full gaps were 1458.76→2275.17, 2268.42→1274.84, and 1049.99→1199.06 ms. The initial boundary-clipped gap is retained separately because the first callback has no previous handler timestamp. All producers stopped and joined cleanly; one already queued callback per trial was drained after stop.

## Allocation and GC accounting

Allocation is cumulative whole-runtime churn, not live memory or RSS. GC and CPU counters share whole-runtime scope with overlapping GUI/worker work; they do not identify exclusive annotation, lookup, or thread cost. Counter snapshots exist at request/application points, not at the later host full-ready endpoint. The following intervals overlap and must not be summed. GB means 10^9 bytes.

| Pair/arm | Request → application complete allocation GB | GC seconds | Application interval allocation GB | GC seconds |
|---|---:|---:|---:|---:|
| 1 stock | 20.277593 | 7.495 | 10.759090 | 0.941 |
| 1 candidate | 20.304910 | 9.805 | 10.713203 | 1.102 |
| 2 stock | 20.371100 | 10.128 | 10.922839 | 1.241 |
| 2 candidate | 20.206146 | 7.025 | 10.460900 | 0.860 |
| 3 stock | 20.232782 | 6.347 | 10.761278 | 0.793 |
| 3 candidate | 20.168414 | 6.787 | 10.468112 | 0.847 |

Request→application allocation changes are +0.135%, −0.810%, and −0.318%. Application-interval allocation falls in all pairs, by 0.426%, 4.229%, and 2.724%, but that runtime-wide reduction does not establish exclusive lookup savings. Request→terminal-return allocation rises in all pairs (about 13.44–13.62 GB stock versus 13.66–13.79 GB candidate), illustrating how overlapping endpoints matter. GC time is higher in the candidate in pairs 1 and 3. Managed live/peak memory, RSS and physical RAM are unavailable in this frozen measurement schema; no memory-footprint conclusion is supported. The unchanged 256 MiB worker ownership limit is a separate setting, not total RAM use.

## Actual cache activity

All five snapshots reference the same actual definitions editor style-list instance in each trial. Startup had naturally populated 62 members/35 named entries and performed 38 rebuilds traversing 1,233 members before the file workload. No synthetic lookup or warmup was added. The counters are cumulative per instance and unsynchronized diagnostic observations; they are not whole-process counters or a guarantee about concurrent mutation.

| Candidate pair | Initial lookups / hits | Open→ordinary-ready lookups / hits | Later ready→final lookups / hits | File-workload rebuilds / members traversed |
|---|---:|---:|---:|---:|
| 1 | 222 / 184 | 319991 / 319991 | 177 / 177 | 0 / 0 |
| 2 | 211 / 173 | 319680 / 319680 | 33 / 33 | 0 / 0 |
| 3 | 211 / 173 | 319711 / 319711 | 0 / 0 | 0 / 0 |

Thus the optimized path is genuinely exercised at high volume, but this file workload does not measure a cold file-triggered rebuild or repeated membership invalidation. Stock has no fabricated counter export. Small native correctness separately covers mutation, duplicate-name winners, reentrant publication, actual incremental lexer/style and rich save/reload behavior.

## Validity and provenance

- All 139 CI rows passed: source/native compile, no-skip native helpers, lookup/publication controls, four actual editor/WXME arms, genuine Check Syntax/full annotation and rename controls, six timed processes, three strict pairs, six-arm matrix and pristine-runtime witness.
- The four rich fixtures now save/reload equivalently at 1,613 bytes. Their common SHA256 is `b9f8219144f0976a4c63062e441392635bfeafa153f4c112eebacf4af30a5809`. The previous stock-identical failure was traced to a missing per-eventspace wxmedia registry entry; only test setup was repaired.
- Every timing arm returned actual handler-results with clean monitor evidence, matching source/settings/registry/prefab and the exact canonical 14,936-key / 74,675-edge graph (`6da6a80a8c6f9aac26502791d7abd00a8115b0088526671315fbff78cef50eb8`). The graph export is outside primary timing.
- Both arms retain the 1 MiB fixture, same edit, stock scheduling/budget, all tools, isolated 256 MiB profiles, identical common observers, producer phase points off, and original bounds. No xref, binding-table, interval-map, scan or budget overlay is mixed in.
- All 62 raw-file/manifest byte-hash attestations are linked to separately verified decoded canonical JSON values. All three original 20-input pair receipts and both prepared manifests match. Original serialization was not reconstructed or confused with canonical JSON.
- Frozen analyzer `a5d84fc4e444615e00df217b40b680b0cf5bc0126a7503d39514671cbe018255` passes all 30 offline tests and accepts this full matrix with zero failures. Native evidence retains 92 decoded documents and three screenshots; no artifact uploads.
- Coherent source manifest: `0a8003091634b9b83d02391614a88bd5bd7e09db123e4f8f3f13eeec83482184`. Telemetry manifest: `840fe01e282b60ee8613a87c63e7e7ed21233741c3fb30eb923dcd3bec75bdc4`. Candidate style source: `74eb24f0d6485187c9700cca421f4299dee67ea092a811d56b737972b2204c6d`.
- Original native log SHA256: `c548a3d541a2d6d81077ef3f74e2fde96230a7a6a77e29c5b0bbb5ab2e6302c2`. No frozen native experiment or analyzer source was changed for this report.

## Next decision

Do not spend another tuning run on this lookup cache or enable it by selecting only its favorable pair. The next already source-reviewed question is whether genuine editor default-object hashing allocates avoidable vectors under the actual inspector. Its bounded weak-identity diagnostic preserves the original hash body and still requires a fully isolated core/GUI rebuild and native semantics/control gates. A useful eligibility witness would justify one precise candidate; it would not itself prove a speedup. The current results continue to point toward reducing consequential shared runtime/application work rather than accumulating small lookup changes.
