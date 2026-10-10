# Cooperative coloring budget: reject the 8 ms default

[Native run 38059373890](https://github.com/alikatgh/openracket/actions/runs/38059373890),
commit `10da76d194d8b1ceefdfbc39117d874aef15c1c5`, reviewed 2026-10-10.

## Decision

Keep the stock **20 ms** cooperative budget. The isolated 8 ms candidate reduces
synthetic input fence delays, but barely changes actual editor-command time,
slows the two completed matched workloads, and fails the existing lexer deadline
in the third candidate trial. A lower fence number alone is not a successful
speed improvement.

No scan optimization or retained appearance change is active in either arm.
Each process verifies scan-module absence and the actual loaded budget: pristine
stock export absent with the environment unset, or candidate export exactly
8.0 with environment `8`. Candidate color module SHA-256:
`e3770a8d0837ea98a4568b2474af1a10f30aee46705cffc29916120be5ada707`.
Both arms use the same frozen contention host
`01e7ab70522d84d32d1a4f63d629aeb4f6de4655ac3101b4f303ba90f401ebb4`
and supervisor `3225d6489e786490e462c16fb14d8212129c2d3368ec94a2ca53cf9de87c3fe3`.

## Workload and validity

After opening the same 1 MiB mixed Racket fixture and making the same first jump
and comment edit, a producer queues 80 further comment-character edits. It
maintains one outstanding request, with the next deadline 16 ms after the prior
GUI fence. This is closed-loop synthetic pacing, not an independent hardware
keyboard stream or physical input-to-photon measurement. Planned-deadline and
actual-enqueue times are both retained so producer suspension is visible.

**All 80 keys started while lexer-invalid in every Linux trial.** All three stock
trials and two candidate trials completed. Complete trials verify the exact final
source, final lexer readiness, and equal complete pending-next-Run language
settings/preferences. Tools, online compilation, coloring, the 128 MiB child
limit and stock instrumentation selection remain unchanged. The failed trial
does not reach final metadata or full-source verification; its partial records
remain available and are not substituted or discarded.

Native correctness passed on Linux: genuine Run/editor, EOF, WXME, Check Syntax,
returning Stop, and exact eight-case lexer/token/style/parenthesis comparison.
The separate hardened scan candidate also passed its own native gate; it was
not enabled in this budget experiment.

## Linux completed work and failure

| Pair and order | Stock open through completion | Budget 8 | Outcome |
|---|---:|---:|---|
| 1: stock, candidate | 44.089 s | 48.585 s | Candidate 10.2% slower |
| 2: candidate, stock | 38.489 s | Not complete | Candidate lexer deadline failure |
| 3: stock, candidate | 37.451 s | 47.209 s | Candidate 26.1% slower |

Pair 2 candidate completed its 80-key phase in 6.034 s, then remained invalid
after a 45.035 s post-typing wait. It exited with failure code 1, without hitting
the outer 60-second process timeout. Its recorded 53.262 s
`open_to_completed_workload_ms` field is only the interval to that failed
observation; **the field name does not make this completed work**. The completion
flag is false and the error is retained. Peak RSS reached 1,425.33 MiB in this
failed trial.

The two complete matched pairs are the only ones pooled below (160 keys/arm).
The overall three-pair comparison is incomplete and invalid as an acceptance
gate. These subset statistics are diagnostic, not a broad speedup estimate.

| Pooled key metric | Stock median / p95 / max (ms) | Budget 8 median / p95 / max (ms) |
|---|---:|---:|
| Editor command | 7.085 / 13.304 / 15.199 | 7.130 / 13.265 / 14.784 |
| Enqueue to GUI handler | 4.165 / 5.072 / 20.520 | 6.938 / 8.333 / 8.713 |
| Enqueue to editor completion | 11.108 / 17.199 / 28.160 | 10.362 / 16.349 / 22.597 |
| Planned deadline to editor completion | 12.242 / 18.710 / 40.717 | 11.437 / 17.601 / 23.808 |
| Planned deadline to low-priority fence | 123.595 / 129.637 / 153.880 | 58.943 / 66.418 / 72.964 |

Planned-deadline-to-editor p99 is 20.385 ms stock versus 23.680 ms candidate:
even that smaller completion metric does not improve uniformly. The 80-key
phase falls from roughly 11.2 s to 6.0 s, largely because this closed-loop driver
waits on each fence before offering another key. It must not be presented as a
doubling of physical typing responsiveness.

The post-typing lexer waits increase from 30.478 to 40.374 s in pair 1 and from
23.987 to 39.016 s in pair 3. Post-typing heartbeat gaps still reach 2.098 s in a
completed candidate trial and 2.370 s in the failed candidate trial. A smaller
token-boundary budget cannot preempt GC or an individual long lexer call.

## Allocation and GC tradeoff

| Complete pair | Stock/candidate allocation through final lexer observation | Stock/candidate GC CPU |
|---|---:|---:|
| 1 | 13.383 / 12.065 GB | 8.807 / 6.037 s |
| 3 | 11.002 / 11.819 GB | 6.176 / 5.778 s |

Allocation direction is mixed. Global cumulative counters are not allocator
ownership evidence, and concurrent place activity contributes to them. Completed
candidate peak RSS is 1,103.88 and 1,132.58 MiB, but the failed candidate reached
1,425.33 MiB. Excluding that failure would create a misleading memory-improvement
story. Background expansion terminal outcome remains unobserved in these
ordinary workloads.

## macOS gate

No macOS budget timing was collected. The budget arm's genuine returning-Stop
check timed out waiting for evaluation completion/Run availability; its stock
counterpart passed. Run/editor, EOF, WXME, Check Syntax and exact lexer comparison
passed in both arms. The Stop failure remains a real failed preservation gate;
this single run does not prove the threshold change caused it, given earlier
intermittent stock Stop failures. No retry or limit extension replaced it.

## Evidence and next step

Raw Linux trial/summary records, including the failed trial, are in
`run-38059373890/linux-performance-records.json` (12 records), with Linux and Mac
logs alongside. Reproduce the strict offline analysis with:

```
python3 performance/analyze_contention_pair.py linux-performance-records.json
python3 -m unittest discover -s performance -p '*analysis.py'
```

Proceed with supported allocation/GC attribution and the separate autosave seam.
Do not reduce coloring, instrumentation, tools or memory limits to manufacture a
faster result, and do not combine this rejected budget with the scan speed claim.
