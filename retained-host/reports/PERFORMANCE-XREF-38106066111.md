# Mac xref reply-cell experiment: no reliable speed improvement

**Decision: do not adopt this candidate as a speed optimization.** Three matched
Mac pairs show mixed readiness/GC results, worse planned-input p95 in every
pair, and the same background out-of-memory result in all six trials. The
candidate remains separate and default-off; the delivered preview is unchanged.

## Verified evidence

- [Native run 38106066111](https://github.com/alikatgh/openracket/actions/runs/38106066111), commit `6165c48f71fe601cf9b2d2e4692347cacdb0a380`.
- Official full Racket 9.3, standard Mac ARM64 runner, same stock appearance/tools,
  stock 20 ms color budget and 128 MiB child-job limit. Actual worker memory
  accounting is available. Scan/autosave/appearance candidates are absent.
- Native reply-service 54/54 and observer-helper 12/12 test cases pass, including
  the twelve nested kill/custodian scenarios. Actual documentation/rename tests,
  real-host Check Syntax, compilation and all six observation gates pass.
- The bounded completed-annotation contract preserves 436 entries, 71 documentation
  annotations and 535 real five-query rename answers per capture. Original raw
  trace ordering remains nondeterministic even across stock runs. This does not
  certify deterministic transient paint order or arbitrary programs/rename names.
- All six worker-loaded source hashes/flags match their intended arm. Ordered
  handlers, pending-next-Run language settings, preferences, actual online prefab,
  final source, observer bytes and activation exclusions match exactly.
- Next-Run instrumentation resolves `lang-default` to `debug`; the independent
  stock online request prefab remains `#s(prefab-module-settings #() (default) #t #t none #t)`.
- All six processes complete within the unchanged 60s outer bound, with complete
  final lexer and current final-request callback evidence, no observer drops or
  errors. Every one of 80 paced keys begins while the lexer is invalid.

The fixture is 1,048,576 ASCII characters. The same middle-comment edit inserts
`x` plus 80 `a` keys; final 1,048,657-character source SHA-256 is
`55f0c420e49ecfe21ca72b015457cce645ccf3b93bdbfec3f898e36fb54b41c7`.
Trial order is stock/candidate, candidate/stock, stock/candidate, with fresh
profiles and 1000×700 windows. This new common-observer workload is not a direct
comparison to older uninstrumented or larger-window measurements.

## Actual tool outcome

Every final request receives `finished-expansion`, followed by
`abnormal-termination` with explicit “Expansion thread terminated unexpectedly
(out of memory)”. All six have **zero monitor trace messages** and
`tool_succeeded=false`. Lexer readiness and callback completion are observable
endpoints, not successful background Check Syntax. The candidate does not
remove the capacity failure at the stock128 MiB job limit.

## Readiness and input responsiveness

Times below retain each interleaved pair. Lower is better. Planned-input p95 is
nearest-rank over the 80 keys in that trial, measured from the off-GUI producer's
planned deadline to editor-command completion.

| Pair | Open→lexer, stock→candidate | Change | Planned-input p95, stock→candidate |
|---|---:|---:|---:|
|1|42.332→37.698s|−10.9%|32.209→33.803 ms|
|2|33.656→33.852s|+0.6%|30.058→35.704 ms|
|3|31.713→44.513s|+40.4%|28.093→36.931 ms|

Arm-median open→lexer time is 33.656→37.698s, about 12.0% worse. Median per-trial
planned-input p95 is 30.058→35.704 ms. These three observations do not support a
stable speedup or a precise general regression estimate.

| Pair/arm | Planned→editor median/p95/max | Queue→handler p95/max | Planned→fence p95/max |
|---|---:|---:|---:|
|1 stock|12.335/32.209/44.541 ms|5.761/15.784 ms|186.977/660.448 ms|
|1 candidate|15.331/33.803/50.803 ms|9.128/25.127 ms|180.271/552.371 ms|
|2 stock|12.469/30.058/125.145 ms|5.977/88.859 ms|189.638/609.134 ms|
|2 candidate|13.209/35.704/535.864 ms|6.539/19.460 ms|182.208/653.124 ms|
|3 stock|14.171/28.093/38.430 ms|7.052/20.731 ms|172.270/701.335 ms|
|3 candidate|17.306/36.931/49.587 ms|13.436/21.255 ms|191.228/743.995 ms|

Candidate pair2 illustrates why enqueue-only timing is insufficient: one key
misses its planned deadline by 517.522 ms before submission, then waits only
3.155 ms for the GUI handler. Its full planned→editor latency is 535.864 ms.
The producer is closed-loop, with one request and a 16 ms pause after each prior
fence. It is not an independent hardware input stream.

Seconds-long GUI stalls remain. During post-typing coloring, maximum heartbeat
callback gaps are 3.277→2.006s, 3.625→1.287s and 1.481→3.576s. These are mixed;
they are not a consistent responsiveness improvement. Whole-run maxima also
include the synchronous initial open. Event-loop/fence/command observations do
not measure physical input-to-photon.

The final background OOM callback occurs before lexer readiness in every trial:
31.577→28.960s,27.429→26.500s and25.705→32.793s after open. A quicker failure
callback would not constitute successful analysis throughput.

## Allocation, GC and memory

These deltas use the same GUI-observed counters, from immediately before open to
the existing workload-end snapshot after terminal observation/idle. They include
coloring, original background jobs, ordinary autosave cadence and reporting.
They do not isolate the xref function or allocate bytes to a particular place.
Decimal GB is used below; cumulative allocation is **churn, not retained RAM**.

| Pair/arm | Cumulative allocation | GC counter delta | Native maximum RSS |
|---|---:|---:|---:|
|1 stock|11.538 GB|7.439s|1.235 GB|
|1 candidate|11.237 GB|5.877s|1.199 GB|
|2 stock|11.046 GB|6.769s|1.226 GB|
|2 candidate|11.043 GB|4.868s|1.240 GB|
|3 stock|11.032 GB|4.834s|1.179 GB|
|3 candidate|11.394 GB|7.766s|1.253 GB|

Arm medians are 11.046→11.237 GB churn, 6.769→5.877s GC counter time, and
1.226→1.240 GB maximum RSS. The lower median GC reading is not consistent across
pairs and accompanies worse median readiness/input tails. No event-level GC
ledger was collected here; these counters cannot attribute each GUI gap to GC.
Cross-place counters are not summed or differenced as ownership evidence.

Observed request counts are 3/4/3 stock versus 3/2/3 candidate. Earlier nonfinal
requests have no observed terminal after subsequent edits replace them. The
fixed-input end-to-end workload matches, but the number and extent of background
jobs does not. This precludes calling the global allocation difference a pure
reply-thread cost. It also explains why these GUI churn totals must not be
compared directly with the earlier single-request isolated replay.

## Observer costs and limits

Identical helper source is loaded in both arms. Caller-side expected-source
construction/registration takes 43.025–64.109 ms before GUI workload startup;
the nested helper hash/registration portion is 6.083–6.702 ms. Summed GUI hook
elapsed intervals are 14.371–25.129 ms over 6–8 calls. The worker's one-shot observer
through its primary evidence-file write takes 3.581–7.686 ms.

These partial self-cost counters exclude the second timing-file write and do not
quantify indirect heap retention, GC or scheduling effects. Concurrent hook
intervals are not CPU self-time. They cannot be subtracted to manufacture
uninstrumented latency or used as proof of zero overhead. Full JSON persistence
is inherited and equal across arms; global counter deltas include it.

The 128 MiB preference limits the accounted background job custodian when memory
accounting is available; it is not a cap on the entire app's RSS and is unrelated
to the cumulative allocation totals. A separately authorized 128/256/512 MiB
stock configuration experiment can test capacity and responsiveness tradeoffs.
It must retain successful monitor/terminal evidence, all original tools and the
same deadlines, and must not be described as a code optimization.

## Reproduction and integrity

`analyze.py paired-records.json` validates the six records and emits all derived
pair, key-tail, phase-heartbeat, allocation and observer statistics. The result
is `analysis-38106066111.json`; all original partial/request records remain in
the decoded source evidence. Three read-only analyzer regression tests pass.

Raw Mac log SHA-256:
`1d169089ebee26cbc4a829456304cf246c73f4ee3dd952d1b0022516084f676d`.
The CI decoder verified all 28 documents and recursive array digests; the original
runtime full-tree comparison passes. No artifact upload was used.

Production xref hashes:
- stock `acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7`
- candidate `d2db0c6860040909c31c8fa9f7945ad5b94da3a03e751791447faeee7c27105f`
- common observer `79c02e6652e7fa4158531384c2d0382a32487b21620522529e325c44394d0d7b`
