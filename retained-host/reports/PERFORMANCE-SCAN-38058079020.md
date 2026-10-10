# Isolated snip-scan experiment: native measurements

Run: [38058079020](https://github.com/alikatgh/openracket/actions/runs/38058079020)  
Commit: `028f01282977aed8aa11764ca3e881dbaab8a2ec`  
Linux and macOS results reviewed: 2026-10-10.

## Finding

On this Linux runner, the isolated scan candidate improved the observed time to
initial lexer readiness in all three matched 1 MiB pairs, by **6.0–12.5%**. It
also substantially reduced typical synthetic key-to-queue-fence durations.
Synchronous file opening and editor key-handler duration were essentially
unchanged. Multisecond event-loop gaps remain, and a candidate key-fence outlier
was worse than every stock sample. This is a useful partial improvement, not a
complete solution to responsiveness and not production approval.

The measured helper SHA-256 is
`873d8f2ec457074fd983ccfe92b0f016587513211f2f92edfb751f991b4faa47`.
Later contract-wrapper hardening is **not** included in these measurements.
The measured guard preserves detached-snip contract behavior but still needs
the separately identified object/c-wrapper safety refinement and native test.

## Validity and scope

- Six fresh processes: pair 1 stock/candidate, pair 2 candidate/stock, pair 3
  stock/candidate. All initial and final lexer gates completed, exit codes were
  zero, and no process timed out.
- Official full Racket 9.3, Linux x64 standard GitHub runner, identical appearance
  and preferences, identical 1,048,576-character/byte fixture. This is fresh
  process state, not a claim of cold operating-system filesystem caches.
- Fixture SHA-256:
  `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`.
- Pristine Framework source stayed unchanged. The candidate changes one pinned
  stock definitions-editor composition to the private scan helper. Each process
  verifies its own helper activation. Scan flag unset for stock, `1` for
  candidate; color-budget flag and all appearance flags unset in both arms.
- Native gate: 14 actual editor preservation cases passed. The eight-case
  stock/candidate lexer comparison passed exact final token ranges/classes,
  normalized styles, parentheses and edited source, including the stateful
  don't-stop lexer case.
- Pending-next-Run settings match exactly: source-determined language, raw
  annotations `lang-default`, fixture-reader default/effective annotation
  `debug`, no metadata errors. This does not inspect live evaluator state.
- Coloring and online compilation remain enabled. The default child limit is
  134,217,728 bytes. Inline overview and spelling preferences retain the same
  stock defaults in both arms.
- Same frozen harness in all arms: retained-host
  `b803200cf79fbbacbbdfa16879c9b577ca61d79728a66cf1a0a745d560e58a4f`,
  supervisor `a455819c4c55f25cf2f8cda64df192ea205d768ff659edac71b5b71ca56b67bb`.
  Do not compare these numbers directly with older runs using another harness
  or runner allocation.

## Linux latency and completed workload

Values are medians of three per-process values, except the explicitly pooled
240-key distribution. Milliseconds unless seconds are shown.

| Measure | Stock | Candidate |
|---|---:|---:|
| Fresh-process GUI startup | 3,420.95 | 3,421.20 |
| Synchronous file-open command | 1,860.69 | 1,883.67 |
| File-open command plus low-priority fence | 1,922.25 | 1,945.78 |
| First near-end jump command | 13.98 | 13.43 |
| First middle-comment edit command | 18.34 | 17.31 |
| Open through initial lexer-ready observation | 30.741 s | 28.255 s |
| Initial lexer wait alone | 28.561 s | 26.047 s |
| Final lexer wait after typing/jumps | 46.22 | 43.15 |
| Paced 80-key phase | 4.101 s | 2.734 s |
| Paced keys/second | 19.51 | 29.26 |
| Whole supervised process | 42.066 s | 38.609 s |

Open-to-readiness includes the same intervening near-end jump and first edit;
it is not a measurement of the lexer alone. Paced throughput includes a fixed
16 ms wait after each key fence and is not unpaced typing capacity.

| Pair | Order | Stock open-to-ready | Candidate open-to-ready | Candidate/stock |
|---|---|---:|---:|---:|
| 1 | stock, candidate | 31.641 s | 28.255 s | 0.8930 |
| 2 | candidate, stock | 30.741 s | 28.898 s | 0.9400 |
| 3 | stock, candidate | 30.092 s | 26.343 s | 0.8754 |

The ratio of arm medians is 0.9191 (8.1% lower). The median of individual paired
ratios is 0.8930; these are different descriptive summaries. With three pairs,
neither establishes statistical significance or a general hardware speedup.

### Pooled synthetic key distribution

| Metric, 240 samples per arm | Stock | Candidate |
|---|---:|---:|
| Editor command median | 8.130 | 7.953 |
| Editor command p95 | 16.072 | 15.985 |
| Editor command p99 | 17.845 | 18.130 |
| Editor command max | 18.648 | 28.119 |
| Command plus fence median | 36.731 | 16.381 |
| Command plus fence p95 | 40.616 | 19.195 |
| Command plus fence p99 | 46.754 | 27.333 |
| Command plus fence max | 49.465 | 402.924 |

The candidate's large outlier is pair 2, key index 21 (zero-based): the editor
command took 1.796 ms, followed by a much longer fence delay. Its cause is not
attributed by this ordinary timing run. Reporting p95 alone would hide it.
The candidate also has warm-input heartbeat gaps of 314.454 ms and 301.898 ms
in pairs 1 and 2; the largest stock warm-input gap is 49.396 ms. The first pair's
long heartbeat gap is not represented by a similarly long individual key fence,
which demonstrates why both observations are retained.

Initial-settle maximum heartbeat gaps by pair are stock/candidate:
3.732/4.242 s, 3.293/4.621 s, and 4.234/2.240 s. Thus the scan shortcut does not
eliminate the major initial responsiveness problem. These are event-loop
observations, not physical keyboard-to-photon measurements.

## Allocation, GC and memory

| Per-process median | Stock | Candidate |
|---|---:|---:|
| Cumulative allocation: open to initial readiness | 11.149 GB | 10.846 GB |
| Cumulative allocation: open to workload end | 11.935 GB | 11.653 GB |
| GC CPU counter delta: open to initial readiness | 7.721 s | 8.216 s |
| GC CPU counter delta: open to workload end | 7.917 s | 8.425 s |
| Native process peak RSS | 1,130.46 MiB | 1,117.47 MiB |
| Managed memory after explicit end-of-run GC | 685.87 MiB | 684.61 MiB |

GB above is decimal, MiB binary. Allocation counters include the whole runtime
and benchmark overhead; they are not allocation-owner attribution. Allocation
to initial readiness falls in all three pairs, by 3.84%, 2.23% and 2.50%. GC CPU
is mixed: stock/candidate 7.721/8.216 s, 7.376/8.583 s and 8.190/6.239 s. Do not
claim a GC improvement from these results. Peak RSS is slightly lower in every
pair, without a large memory reduction. Collection timings here are cumulative
counters, not the per-event wall intervals from the earlier sampled diagnostic.

## Limits and next test

### macOS: incomplete and mixed

Both native correctness gates passed on the macOS ARM64 runner: 14 editor cases
and exact lexer/token/style/parenthesis equivalence. Five of six timing processes
completed. **Pair 2 stock hit the unchanged 60-second outer process timeout**;
the complete three-pair performance gate correctly remained failed.

| Pair | Stock open-to-ready observation | Candidate | Completed pair? |
|---|---:|---:|---|
| 1 | 31.341 s | 35.001 s | Yes; candidate 11.7% slower |
| 2 | 45.100 s, partial trial | 34.181 s | No; stock subsequently timed out |
| 3 | 32.232 s | 29.030 s | Yes; candidate 9.9% faster |

The failed stock trial reached initial lexer validity (42.345 s wait after its
first open/jump/edit), but no complete warm-key sequence, final lexer observation
or final selected-language metadata was persisted. Native peak RSS was also
unavailable after termination. The timeout stack was inside stock
`find-next-non-string-snip` through editor-port creation and a colorer callback;
this is an interrupted location, not an allocation or CPU attribution. Its raw
partial report and stderr are retained and must not be replaced by a successful
run or treated as a completed matched comparison.

For context only, the two fully matched pairs contain 160 keys per arm. Their
stock/candidate fence median is 36.053/27.321 ms, p95 60.720/62.427 ms, p99
80.185/154.864 ms and maximum 102.839/275.382 ms. Synchronous command median is
4.341/6.502 ms. This selected subset does not establish a macOS benefit; its
readiness direction is mixed and candidate high tails are worse. The unmatched
completed candidate trial is retained in raw evidence but excluded from those
paired key distributions. The analyzer labels the overall comparison invalid.

On those two pairs, cumulative allocation to initial readiness is about 2%
lower for the candidate, but GC CPU increases (5.835/6.531 s and 5.083/5.569 s).
These small samples do not establish a GC or memory improvement. No cross-OS
speed comparison is appropriate: hardware, OS scheduling and GUI backends differ.
The macOS desktop is 1024×768 while the common benchmark requests 1200×820; this
same within-OS setup does not establish full-window visible-presentation timing.

### Follow-through

The current ordinary run does not observe background expansion's terminal
outcome. Equal preferences and complete lexer state must not be presented as
proof of complete background-tool work. No tool, instrumentation setting or
memory limit was disabled to obtain these numbers.

Keep the scan optimization isolated and complete its wrapper regression before
shipping. The separate cooperative-budget experiment should then compare equal
arms with typing during initial coloring, explicit scheduling/handler/editor
timings, final lexer completion, and GC/allocation tradeoffs. Smaller slices
cannot preempt a GC pause or a long individual lexer call.

Reproduction of the offline analysis:

```
python3 performance/analyze_scan_pair.py linux-performance-records.json
python3 -m unittest discover -s performance -p test_scan_analysis.py
```

Raw evidence is retained under the CI result directory for this run as
`linux-performance-records.json` (12 trial/summary records with pair/arm labels)
and `linux.log`. The analyzer validates completion, activation, fixture, runtime,
appearance and settings equality before marking a matched comparison valid.
