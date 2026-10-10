# Retained DrRacket: first completed native performance baseline

Run: https://github.com/alikatgh/openracket/actions/runs/38050824369

## Finding

The retained modern appearance has **not demonstrated the requested large speedup**.
The first completed Linux comparison is broadly similar on the 1 MiB workload, with
slightly higher modern memory use. Initial background work still causes seconds-long
responsiveness gaps. These results justify profiling the retained implementation;
they do not justify calling it faster or feature-complete.

## Linux evidence

Same standard Ubuntu 24.04 CI runner, full official Racket 9.3 CS, same generated
fixtures, three fresh-process trials per size and mode. All 12 trials completed with
correct source lengths and synthetic inserted text; both initial/final lexer waits
completed. Stock sources were pristine; the modern runtime was a separate clone.
The job's retained native core and eight scoped preservation cases passed.

Numbers below are medians across three trials. A command time ends when the native
method returns. It is not full background completion, a presented frame, or physical
input-to-photon. Warm figures are medians of the three per-trial medians.

| Measurement |100k stock|100k modern|1 MiB stock|1 MiB modern|
|---|---:|---:|---:|---:|
| Fresh-process GUI startup, s |3.091|2.961|3.195|3.052|
| First file-load command, ms |186.8|254.6|1371.6|1358.4|
| First file-load through queue fence, ms |223.4|272.9|1456.4|1408.9|
| First near-end jump command, ms |11.6|7.7|15.4|13.0|
| First middle-file edit command, ms |14.5|10.8|16.2|11.8|
| Lexer-valid wait after initial open/jump/edit, s |2.424|2.472|23.912|23.654|
| Warm editor key command, ms |2.09|1.86|6.22|5.54|
| Warm key through low-priority queue fence, ms |6.73|5.88|25.01|24.47|
| Native peak RSS, MiB |822.1|831.8|1114.8|1148.0|
| Racket-managed memory after final explicit GC, MiB |565.0|571.5|674.8|681.6|

The 1 MiB synchronous load differs by under 1%; warm queue-fence medians differ by
about 2%; modern peak RSS is about 3% higher. The 100k modern load command was about 36%
slower. Three ordered trials on a shared CI machine cannot establish significance,
and the later mode can benefit from OS caches. No broader speedup claim follows.

### Warm tails and responsiveness

Pooled 240 synthetic key events per size/mode (80 in each of three processes),
nearest-rank tails. Events within a process are correlated.

| Queue-fence latency |100k stock|100k modern|1 MiB stock|1 MiB modern|
|---|---:|---:|---:|---:|
|p95, ms|9.76|9.80|30.12|30.57|
|p99, ms|31.45|31.65|38.49|35.72|
|Maximum, ms|38.00|33.34|40.30|47.33|

The largest heartbeat callback gaps during initial lexer stabilization were:

- 100k: stock 516.7 ms; modern 522.9 ms
- 1 MiB: stock 2983.1 ms; modern 4117.2 ms

Both modes have real long intervals during which the heartbeat did not run.
Enqueue-to-dispatch delay and callback gaps are retained separately: some gaps
include a stalled sampler/worker schedule, so the shorter dispatch figure alone
would conceal them. They are responsiveness probes, not compositor/frame timings.

From before opening through initial stabilization, the 1 MiB trials accumulated
5.27–7.21 s additional stock GC CPU time and5.09–7.96 s modern GC CPU time. This makes
allocation/GC important attribution targets, but it does not yet prove which
operation causes the longest pause. CPU/GC counters are not wall-clock pauses.

## Settings and limitations

Verified identical in every Linux trial:

- Evaluator child-only memory limit 134217728 bytes (128 MiB)
- Coloring enabled
- Online compilation enabled
- Inline overview disabled by the unchanged stock default
- All three recorded spell-check settings disabled by unchanged stock defaults
- Exact fixture SHA-256 and byte/character counts

The selected-language instrumentation metadata is **not yet verified** by this run.
Racket 9.3's public simple-settings-annotations accessor rejected the valid
lang-default result under its own result contract. Both modes show the same error,
but identical errors do not prove equality. The next read-only metadata capture
uses the documented settings-vector API and preserves serialized language settings;
no instrumentation setting is changed.

The requested benchmark frame is 1200×820. Linux uses a 1280×900 Xvfb native display.
Do not compare these numbers to another OS or to the older Rust/Syntect prototype.
This run does not measure Run, Check Syntax, debugger, macro expansion, teaching-tool
performance, WXME performance, IME, accessibility or input-to-photon. Correctness
coverage is scoped separately and is not an assertion of exhaustive parity.

## Next bounded diagnostic

One separate pristine-stock 1 MiB process will collect the standard 10 ms statistical
sampler on the actual GUI handler, timestamped stock colorer/edit-sequence logs,
GC messages, online-expansion lifecycle logs and bounded stalled-handler stacks.
It changes no tool, language, memory-limit or custodian setting. Its overhead is
explicit and its timing is excluded from the ordinary baseline. Only attributed
expensive paths should motivate a semantics-preserving optimization proposal.

## macOS evidence from the same run

Use these as paired results within the macOS runner only. They are not a hardware
or operating-system comparison with Linux. The native desktop was 1024×768; the
benchmark requested a 1200×820 window, which could extend beyond the visible
viewport. The exact effective benchmark window geometry was not recorded.

All six 100k trials completed. All six 1 MiB trials failed the unchanged 45-second
lexer-valid limit after opening, jumping and editing. No 1 MiB warm typing result
is valid or reported. These were explicit workload failures, not outer process
timeouts or cleanup failures. The native core checks passed, but the separate
pristine-stock Stop/evaluator-completion test failed, so macOS acceptance remains
blocked independently of the performance failures.

### Completed 100k workload

Again, values are medians over three processes; warm values are medians of the
per-process medians.

| Measurement | Stock | Modern |
|---|---:|---:|
| Fresh-process GUI startup, s |7.864|8.299|
| First file-load command, ms |648.2|877.4|
| First near-end jump command, ms |63.6|63.6|
| First middle-file edit command, ms |53.9|82.9|
| Lexer-valid wait after initial work, s |5.001|5.680|
| Warm editor key command, ms |6.03|7.44|
| Warm key through queue fence, ms |23.00|26.16|
| Native peak RSS, MiB |872.5|884.5|
| Managed memory after final explicit GC, MiB |574.3|582.8|

Pooled 240-event warm queue-fence tails per mode:

| Tail | Stock | Modern |
|---|---:|---:|
|p95, ms|60.39|68.32|
|p99, ms|109.81|109.43|
|Maximum, ms|111.71|320.17|

This small sample shows no speedup; the modern synchronous file-load median is
about 35% higher. It is insufficient to establish a general regression across
machines or workloads.

### Failed 1 MiB workload: partial observations only

The synchronous file-load medians before failure were 3075.6 ms stock and
3378.1 ms modern. All six subsequent lexer waits remained invalid at approximately
45 seconds. The largest heartbeat gap during that wait was 4797.1 ms stock and
3574.6 ms modern. A lower single observed maximum does not establish an improvement,
especially when every trial fails the completion condition.

The same 128 MiB evaluator limit, enabled coloring/online compilation and unchanged
overview/spell-check defaults were recorded in both modes. The completed 100k trials
hit the same annotation-accessor contract error as Linux; the failed 1 MiB trials
never reached that metadata step. Explicit language-instrumentation equality is
therefore still unverified for this run. No time limit or feature setting is being
relaxed to manufacture a completed result.
