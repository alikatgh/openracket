# Mac binding-table experiment: earlier annotation completion, costly first public access

## Decision

Keep this lazy candidate default-off. All six workloads and all three strict paired comparisons pass, and annotation application finishes 15.79–20.83% sooner. The same candidate defers 5.625–8.551 seconds of synchronous work and about 2.633 GB of allocation to the first public binding-table getter. Application-period heartbeat maxima worsen in every pair. This is useful evidence for an eager revision, not a sufficiently balanced improvement to ship.

The ordinary workflow and the public-getter workload are both real measurements. The first can improve without the second being free. They are reported separately rather than silently changing the definition of readiness.

## Run and validity

- [Native run 38131918285](https://github.com/alikatgh/openracket/actions/runs/38131918285), commit `b5f19d0a4b63bba8dcae928c12bedbe04f7ed453`; standard macOS runner, official Racket 9.3.
- All 122 CI result rows pass, including zero-skip native preflights, actual extracted-method mutation/differential cases, stock/off/on genuine Check Syntax graph/navigation checks, complete semantic annotation and real rename-query checks, and the original full-runtime witness. The semantic trace gate retains raw-order nondeterminism; it does not claim identical transient painting.
- Six fresh processes/profiles/addon paths, in order stock/candidate, candidate/stock, stock/candidate. All six have the same exact edited source, pending Run configuration, actual worker prefab/registered handlers, verified 256 MiB limit and memory accounting, clean handler-results plus monitor trace, final lexer validity and completed GUI annotation application. Each selected request is request 1 of 1, with no replacement.
- Every trial exports the same 14,936-key, 74,675-edge graph, canonical SHA-256 `6da6a80a8c6f9aac26502791d7abd00a8115b0088526671315fbff78cef50eb8`, with the same public mutable strong equal?-hash and immutable equal?-set shape. Actual editor ownership, public getter identity and candidate state transitions are checked.
- All 65 decoded documents passed the recursive/full transport digest checks. The read-only analyzer independently re-verifies its frozen 32-file telemetry package, complete selected evidence, scalar acceptance summaries, source-path associations, exact ordered matrix and equality across all six trials. It does not pretend to reopen native runner files locally.
- Source/telemetry remain the reviewed final1023 candidate and0959 telemetry. Production GUI SHA-256 `1ba5b93e748091888e2f61b1518fe625a86d5b771e471f11204461e9ace02025`; telemetry SHA256SUMS `feea9575931d78f2abfa487b65efa8c453ec9b974f65c1346d13a26a2cef9b71`. Raw log SHA-256 `bb7c79f6baa1892893f702f9e6473d2ac815366ee39ff7862f1e28f0ff46c75f`.

## Workload and endpoints

Both arms use identical common observers and a 50 ms closed-loop, one-outstanding low-priority heartbeat; detailed producer points are off. The workload opens the same mixed 1 MiB Racket fixture and inserts one character in a middle comment. Original tools, lexer, 20 ms application batching and queue priority remain enabled. The only product delta is the default-off private same-owner binding index. Stock and candidate appearance are identical. This is not a repeated typing or physical input-to-photon test.

“Application” is the interval from actual GUI annotation application entry through the final synchronous completion endpoint, including interleaved event-loop work and yielded waits. Request→application and open→application are broader intervals. Lexer readiness and worker terminal callbacks are earlier, separate observations. The first and second public getters run only after ordinary completion, heartbeat stop/join and verification; graph serialization/checks occur outside the getter timers. The original deadline is unchanged.

## Ordinary completion: all three paired application intervals improve

| Pair | Stock application s | Candidate application s | Paired reduction | Request→application s | Open→application s |
| --- | --- | --- | --- | --- | --- |
| 1 | 35.417 | 28.554 | 19.38% | 62.637 → 49.806 | 66.094 → 52.983 |
| 2 | 24.835 | 20.914 | 15.79% | 42.188 → 41.594 | 44.481 → 44.290 |
| 3 | 24.734 | 19.581 | 20.83% | 41.783 → 37.784 | 43.953 → 40.084 |

Application arm medians are 24.835→20.914 s (15.79% lower); the median matched-pair reduction is 19.38%. Request→application paired reductions are 20.48%, 1.41%, 9.57%; open→application reductions are 19.84%, 0.43%, 8.80%. The much slower first stock trial makes an unqualified aggregate gain misleading. These are three descriptive observations per arm, not confidence intervals or a universal speed claim.

| Pair | Open→first lexer-valid observation s | Application after lexer observation s | Application after terminal callback return s |
| --- | --- | --- | --- |
| 1 | 57.013 → 49.940 | 9.081 → 3.043 | 30.402 → 25.130 |
| 2 | 36.309 → 42.419 | 8.172 → 1.871 | 21.562 → 17.314 |
| 3 | 36.379 → 38.197 | 7.574 → 1.886 | 21.534 → 15.942 |

The lexer observation is later in candidate pairs 2 and 3, despite earlier final application completion. These endpoints cannot be substituted for each other. The data do not identify which competing GUI work caused the changed timing.

## Deferred public access: a multi-second synchronous regression

| Pair | Stock first getter ms | Candidate first getter s | Candidate second getter ms | Candidate first allocation GB | Candidate first GC ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.025 | 8.551 | 0.035 | 2.634 | 131 |
| 2 | 0.024 | 5.781 | 0.006 | 2.633 | 84 |
| 3 | 0.025 | 5.625 | 0.013 | 2.633 | 79 |

Before every candidate first getter, all 74,675 accepted entries are pending, with zero duplicates, zero stock insertions and no fallback. The first getter performs one materialization and 74,675 original stock insertions, clears the pending journal and permanently selects the original path for that table. The second getter returns the same hash without further materialization. Thus this fixture demonstrates deferred insertion, not removal of duplicate work. Stock first getters allocate 912 bytes in each measured snapshot interval; candidate first getters allocate about 2.633 GB.

| Pair | Stock application + first getter s | Candidate application + first getter s | Candidate increase | Open→post-export verification s |
| --- | --- | --- | --- | --- |
| 1 | 35.417 | 37.105 | 4.77% | 67.353 → 62.716 |
| 2 | 24.835 | 26.695 | 7.49% | 45.098 → 50.763 |
| 3 | 24.734 | 25.206 | 1.91% | 44.853 → 46.426 |

The sum is two non-overlapping measured intervals, not a replacement readiness endpoint or exclusive CPU time. It excludes intervening work, graph export and verification. Even this limited sum is worse in every pair. The actual open→post-export verification endpoint improves in pair 1 but worsens in pairs 2 and 3. The heartbeat has stopped before getter measurement, so no getter-period heartbeat percentile is claimed; the measured synchronous GUI call itself exposes the stall.

## Responsiveness: completion improvement does not translate to uniformly better dispatch

| Trial | n | Planned p50 ms | p95 ms | p99 ms | max ms | Queued p95 ms | Queued max ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 stock | 285 | 119.251 | 144.956 | 166.983 | 233.959 | 139.771 | 233.417 |
| 1 candidate | 185 | 125.771 | 153.020 | 261.611 | 364.544 | 147.995 | 362.395 |
| 2 stock | 220 | 18.787 | 134.207 | 153.716 | 292.312 | 133.487 | 291.739 |
| 2 candidate | 134 | 123.531 | 140.591 | 157.982 | 347.254 | 137.644 | 346.620 |
| 3 stock | 209 | 22.669 | 138.798 | 207.301 | 324.598 | 138.348 | 318.003 |
| 3 candidate | 126 | 124.643 | 151.587 | 180.973 | 380.769 | 146.021 | 380.449 |

Application planned-deadline p50/p95/max worsen in all three pairs; p99 is mixed. Across-trial median planned p50 is 22.669→124.643 ms and median per-trial maximum is 292.312→364.544 ms. Shorter candidate application windows and changed overlap with coloring can alter these distributions; this does not prove a changed queue priority or causally assign the regression to one function.

| Trial | n | Whole planned p95 ms | p99 ms | max ms | Queued p99 ms | Producer-late max ms | Clipped handler-gap max ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 stock | 393 | 181.663 | 1281.831 | 5371.146 | 461.798 | 2058.519 | 5421.103 |
| 1 candidate | 280 | 186.239 | 1294.172 | 4531.458 | 261.249 | 1369.793 | 4581.417 |
| 2 stock | 304 | 150.165 | 650.981 | 3333.323 | 291.739 | 816.078 | 3383.293 |
| 2 candidate | 229 | 170.224 | 1177.978 | 4338.847 | 1177.777 | 723.423 | 4388.817 |
| 3 stock | 291 | 164.413 | 894.074 | 3128.741 | 318.003 | 1208.214 | 3178.721 |
| 3 candidate | 211 | 179.505 | 1147.919 | 3423.137 | 1147.774 | 764.471 | 3473.121 |

Whole-workload planned p95/p99 worsen in every pair; maximum improves in pair 1 and worsens in pairs 2 and 3. Multi-second gaps remain. The planned timestamp includes off-GUI producer scheduling lateness, which can itself be delayed by GC; queued-to-handler isolates only delay after submission. Samples are selected by planned deadline within the window, including a late final callback. Every trial has one after-stop drain row, and cooperative join succeeds. Nearest-rank percentiles are computed per trial, never pooled across unequal runs. These callbacks do not measure real keyboard, display or photon latency.

## Allocation, GC and memory

| Trial | Application alloc GB | Application GC ms | Application all-places CPU s | Request→app alloc GB | Request→app GC ms |
| --- | --- | --- | --- | --- | --- |
| 1 stock | 11.007 | 1259 | 37.993 | 20.317 | 12140 |
| 1 candidate | 10.727 | 1193 | 29.970 | 20.135 | 9006 |
| 2 stock | 10.679 | 938 | 26.709 | 20.270 | 6897 |
| 2 candidate | 10.634 | 932 | 23.175 | 20.041 | 8312 |
| 3 stock | 10.698 | 830 | 25.354 | 20.264 | 7017 |
| 3 candidate | 10.548 | 887 | 20.394 | 20.079 | 6948 |

Application allocation falls only 0.43–2.54% per pair; median paired reduction 1.40%. Application all-places CPU falls 13.23–21.12%, while GC is mixed. The extra first-getter interval then raises application-plus-first-getter allocation by 21.38–24.23% versus stock. Request→application allocation remains around 20 GB in every trial. These are whole-runtime counters over same-process intervals, including concurrent tools, coloring and common observers; they do not establish thread/custodian allocation ownership. Allocation is cumulative churn, not resident RAM.

Managed-memory snapshots immediately before the first getter are 1.074–1.082 GB stock and 1.084–1.096 GB candidate; candidate after-getter snapshots are 1.099–1.102 GB. The small signed managed-memory change does not erase the allocation churn because GC runs during the call. This batch records neither RSS nor peak memory, so it supports no RSS/peak comparison. Counter snapshots are sequential; no cross-arm counter subtraction or GC subtraction is used to invent CPU ownership.

## Smallest supported next experiment

Test an eager private lookup cache under the same narrow same-owner/exact-integer scope: retain the original set-add and hash-set! for each accepted edge immediately, while avoiding only repeated object-containing hash-ref and set-member? work. The public getter should return an already-current original hash, with no deferred insertion loop. Auxiliary state must be committed only after the original operations succeed, and exposure/unsupported inputs must permanently fall back for that table. Preserve the explicit custom equality/hash callback caveat and all actual-form, exported-graph, navigation and trace tests.

This is a proposal supported by the binding attribution and this run’s deferred-cost result, not a measured optimization. A named-style lookup index remains a separate possible follow-on, with weaker sparse-sample attribution. Keep the lazy candidate off; do not combine candidates or change the stock scheduling budget to conceal the regression.

## Evidence files

- `analysis.json`: complete six-trial raw evidence, frozen-validator correspondence, per-pair comparisons, descriptive medians, heartbeat windows and all caveats.
- Native `decoded-index.json`, 65 decoded documents, `summary.json` and raw log remain preserved under run38131918285; no failed prior run is overwritten.
- Frozen analyzer package `openracket-binding-analysis`, SHA256SUMS `cec0e8e4e0019fb35405e5d6ffa5583a0b5dcd20167b666ed13f83f1ff78a1c7`; 33 synthetic mutation/arithmetic tests passed independently before native analysis. Synthetic fixtures are clearly marked and are not native observations.
- Independent verifier in `independent/verify.py` reconstructed all 65 documents directly from raw log chunks, matched all 122 native result rows to summary.json, and recomputed every reported timing, getter, counter and heartbeat value without using the analyzer arithmetic. Verification passes; see `independent/verification.json`, `independent/trials.csv` and `independent/README.md`.
