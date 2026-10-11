# macOS online-expansion attribution: run 38099774787

## Finding and decision

The actual stock-configured background request for the edited 1 MiB fixture ended
with an explicit out-of-memory terminal under the unchanged 128 MiB child limit.
Two isolated-process replays reproduced that exact terminal. Each allocated over
4 GB cumulatively and consumed over 2 seconds of GC CPU without the GUI workload.
This establishes substantial churn in the original background-expansion workload
and its support machinery. It is a diagnosis, not a product speedup or proof that
process isolation will remove a particular amount of GUI latency.

The next smallest experiment is a bounded phase/actual-thread probe. Every trial
received `finished-expansion`, but none delivered a Check Syntax monitor trace.
Stock sends that status before synchronous handler processing; Check Syntax's
`go` waits while its monitor builds the trace, and compilation follows the handlers.
This makes trace construction a plausible location, but the current evidence does
not identify the exact allocating function or prove that compilation was never
reached. Producer-side phase counters and samples of both actual threads should
resolve this before choosing an allocation patch or a heavier process bridge.

No limit increase, disabled tool, changed lexer budget or reconstructed handler
list is justified by this result.

## Provenance and validity

- [Native run 38099774787](https://github.com/alikatgh/openracket/actions/runs/38099774787),
  commit `b22ced970504e53eb1012c91f6b355e1b4d5dddd`.
- Official full Racket 9.3 CS on the standard macOS ARM64 runner, with a dedicated
  deep-cloned diagnostic runtime. The original runtime's complete 26,838-entry
  tree comparison passed, hash
  `adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`.
- Reviewed diagnostic manifest SHA-256:
  `4ea9857a282b38da5d8c1d8033e405b13b64bf4340966fe50575dcffd95ca661`.
  This is an initialization-instrumented copy of stock, not a byte-identical worker.
- The genuine definitions editor loaded the original 1,048,576-character fixture
  and inserted the intended `x` at comment position 524,139. The actual selected
  request contains 1,048,577 ASCII characters/bytes, digest
  `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
- The actual frozen registry has two registrations from the stock
  `drracket/private/syncheck/online-comp.rkt`: `go` as an ordinary handler and
  `monitor` as a monitor handler. Its serialized digest is
  `af394d9818e314a25ff315e575b16ac5171ad55a8dd549c271a69c923e5720ef`.
- Actual worker prefab:
  `#s(prefab-module-settings #() (default) #t #t none #t)`.
  Its `none` annotations are stock online-expansion behavior. The unchanged
  pending-next-Run configuration remains `lang-default`; these are different
  configurations, not a benchmark instrumentation reduction.
- Native capture verified coloring and online compilation enabled and the
  134,217,728-byte child limit. Replay verified that same actual worker limit.
  Exact snapshot, source identity, registry and prefab match in both replays.
  The frozen validator also checks captured runtime paths, package tables,
  preference state and worker/caller/handler/support hashes before replay.
- Capture shutdown changed its disposable preference file. Replay explicitly
  restored the exact captured bytes only within the marked diagnostic profile,
  backed up the post-capture bytes, and recorded both hashes. No user profile or
  product preference was changed.

The capture and replay drivers completed without an outside timeout. Internal
cleanup received exactly `stopped`, observed the worker dead, stopped its logger
and shut down its diagnostic custodian. External cleanup reaped the process and
verified no remaining live or zombie group members. No unparsed stdout remained.
All five JSON documents were reconstructed using document/array digest checks;
no serialized fixture payload or Actions artifact was uploaded.

## Observed outcomes and costs

| Observation | First expansion after initialization | Same-process repeat after that outcome |
|---|---:|---:|
| Terminal | explicit out-of-memory | explicit out-of-memory |
| Terminal matches integrated capture | yes | yes |
| Elapsed interval | 8,647.571 ms | 8,283.032 ms |
| Process CPU, all places | 8,404 ms | 8,082 ms |
| Cumulative process allocation | 4,307,266,976 bytes | 4,143,898,592 bytes |
| Allocation in GiB | 4.011 | 3.859 |
| GC CPU counter delta, observed from root | 2,395 ms | 2,204 ms |
| GC CPU counter delta, observed from worker | 2,395 ms | 2,204 ms |
| Sampled process RSS interval peak | 671,432,704 bytes | 657,850,368 bytes |
| Available RSS samples | 57 of 57 | 53 of 53 |
| Monitor messages | 0 | 0 |

The exact terminal text in the native capture and both replays is:
“Expansion thread terminated unexpectedly (out of memory)”. All observed status
sequences were `finished-expansion` followed by the separately received abnormal
terminal. `finished-expansion` does not mean the handler/compile pipeline completed.
The diagnostic's successful exit means that it faithfully observed this failure
and cleaned up; it does not mean the Racket program's background analysis succeeded.

Initialization before the first measured interval took 775.710 ms. The second
trial follows an OOM result, so “warm” means only repeated work in the same
worker/manager/process after that outcome. It is not a successfully warmed program
or a separate fresh-process trial. Two intervals do not establish statistical
significance or a throughput improvement.

The 4 GB figures are cumulative allocation churn, including memory reclaimed along
the way. They are not required RAM. Sampled RSS was about 640.3/627.4 MiB and includes
the driver, worker, loaded libraries and support threads; it is not the 128 MiB
constrained job's retained memory. The child limit is not a whole-process RSS cap.
RSS was externally sampled, not an exact high-water mark, and no GUI memory-saving
claim can be made by comparing this process with a complete DrRacket process.

The root and worker GC observations are not independent ownership counters and
must not be added together. GC CPU was about 28.5%/27.3% of the measured process CPU
in these intervals. The process allocation scope includes the unchanged worker,
its handlers and compiler manager, the result sink, and diagnostic observers.
This isolation does not identify the original concurrent GUI's allocation owner.

## GC event visibility is incomplete

Root-side receipt-filtered logs contain 166 rows (164 minor, 2 major) in trial 1
and 197 rows (196 minor, 1 major) in trial 2. Neither collector reported explicit
buffer drops or text truncation. The worker-side receiver contained zero rows,
which is missing visibility, not evidence of zero worker-related GC.

The root rows' CPU durations sum to only 1,483/1,475 ms, below the corresponding
2,395/2,204 ms counter deltas. Receipt timestamps show substantial delivery delay;
zero buffer drops therefore does not imply a complete event ledger at the endpoint.
The largest observed row spans 288.502/355.364 ms, but those values are not maximum
pause bounds. Do not use incomplete rows to assign phase ownership or claim all
large pauses have been explained. Counter totals are the stronger evidence here.

## Source-backed next experiment

Keep this completed replay and its records unchanged. In a separate diagnostic
revision:

1. Add guarded producer-side timestamps/allocation/GC observations at the stock
   expansion, handler and compilation boundaries. Preserve the original logger
   calls and logger-level behavior. Simply enabling its info receiver changes
   `log-io?` and selects a different IO-reading branch, so the new observer should
   not enable that stock logger accidentally.
2. Register the actual working thread and actual Check Syntax monitor thread using
   replay-only hooks. Sample them outside the constrained job custodian; retain
   only weak thread references, tag job generations, immediately render bounded
   stack frames and discard continuation marks. Sampling the working thread alone
   could show only its legitimate `channel-get` wait.
3. Retain the same exact request, registry, prefab, memory limit, terminal checks,
   process supervision and cleanup acceptance. Report the added diagnostic
   overhead; do not compare its profiled timings as a speedup.
4. If a specific allocation hotspot is established, test one narrow optimization
   with completed lexer/tool results, paired Mac typing/heartbeat tails and memory
   evidence. Otherwise, a default-off GUI-connected subprocess prototype remains
   a possible next experiment, but requires genuine compiler-lock/channel,
   Check Syntax/rename, abort/death and rich-source compatibility gates first.

Pinned source anchors: `expanding-place.rkt` sends status at line 235, begins
handlers at 236/242, finishes them at 264, compiles at 273 and finishes compilation
at 285. In `syncheck/online-comp.rkt`, `go` waits at 59 while the monitor calls
`build-trace` at 122 and `send-back` at 123. These are locations in the verified
9.3 sources, not an allocation attribution already established by this run.

## Evidence files and offline check

The decoded evidence is under
`openracket-recovery/results/run-38099774787/decoded`, with the raw `macos.log`
beside it. The accompanying read-only `analyze.py` validates terminal/identity/
cleanup conditions and recomputes interval values; `analysis-38099774787.json`
contains its output and decoded-file SHA-256s.

| Decoded file | SHA-256 |
|---|---|
| capture-capture-host.json | 25ae3c9d6f9461a857acac2046cbc957ebe1e64680234be4f09d2e7cbd05ce86 |
| capture-capture-summary.json | bdb94b12f0beea620712fef708896613564c5995206d74b45c0a1ed51f1d6a5f |
| capture-capture-supervisor.json | 61ef4c67af7c8327c0f3e9a872ca61f969648eca4dee9a79443c8ee0c700523f |
| replay-replay.json | fcd753b01e9e01e21f8491ffd6f732155f8d5370331e411996d3724921b7acc4 |
| replay-supervisor.json | 6f4c9317ac0b23dae337b60a49568d2748f1874cecf66d01a42b8f56f018fab2 |
