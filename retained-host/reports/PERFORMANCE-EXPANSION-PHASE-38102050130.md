# macOS expansion phase attribution: run 38102050130

## Result

Both actual replays enter Check Syntax trace construction and terminate with the
same explicit stock out-of-memory result before trace construction, handler
processing or compilation completes. The phase records have no dropped inputs or
points. The working thread waits while the actual monitor traverses expanded
syntax and annotates variables. The last live monitor sample in both trials is
`document-variable` in stock `traversals.rkt:1538`.

This locates the failing stage. It does **not** establish that one sampled function
owns all allocation or that a subprocess bridge fixes the failure. Initial macro
expansion itself already accounts for roughly 2.62 GB of cumulative allocation;
the later trace-building interval adds another 1.35–1.62 GB. A useful next change
must preserve Check Syntax output, rename capabilities and the existing memory
limit, rather than hide the work or merely move its failure.

## Provenance and gates

- [Run 38102050130](https://github.com/alikatgh/openracket/actions/runs/38102050130),
  commit `f0d11231c92e9a8f7f955657673be9eb531607f7`, standard macOS ARM64 runner.
- Probe manifest `d7187ac4708dde9ae5de9c09ce5e369aacd1fcfd9257a16c6c827a94a7362ace`.
  This includes a test-only canonical-path repair after run 38101560719; all Racket
  probe/runtime, preparation, capture and supervision bytes are unchanged from the
  preceding `95f1c2c` source freeze.
- All 61 source/mock/Racket checks, 12 lossless evidence-transport checks, actual
  native request capture, two replays, terminal parity, separate stack-evidence
  completeness, and the 26,838-entry pristine-runtime comparison pass.
- The real edited fixture remains 1,048,577 ASCII bytes/characters, digest
  `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
  The actual ordered stock `go`/`monitor` registry and prefab are captured and
  replayed, rather than reconstructed. Prefab:
  `#s(prefab-module-settings #() (default) #t #t none #t)`.
- Coloring and online compilation remain enabled. Actual worker child limit is
  134,217,728 bytes. No stock logger subscription is added, so its `log-io?` branch
  is unchanged. The phase hooks are off during genuine native capture.
- Actual capture and both replays report `abnormal-termination`, explicitly
  “Expansion thread terminated unexpectedly (out of memory)”. Each receives
  `finished-expansion`, but no monitor message. Native capture's lexer is still
  invalid at the terminal observation.
- Both internal cleanups receive `stopped` and observe the worker dead. External
  supervision exits normally, reaps the direct child, confirms an empty group,
  and reports no timeout or cleanup error. All five evidence documents and every
  chunked array were reconstructed with digest verification.

## Producer-side phase observations

These are concurrent runtime counters between diagnostic producer timestamps.
They include observer/support activity and do not assign allocator ownership.
The trace interval ends at the post-terminal probe endpoint, so it also includes
OOM/GC/shutdown observation and the bounded control exchange.

| Interval | Trial 1 | Trial 2 |
|---|---:|---:|
| Initial expansion, phase 09 → 10 elapsed | 5,793.631 ms | 6,396.821 ms |
| Initial expansion cumulative allocation | 2,629,210,256 bytes | 2,615,438,224 bytes |
| Initial expansion GC CPU observation | 1,309 ms | 1,587 ms |
| Trace start → post-terminal probe end | 5,755.624 ms | 7,028.454 ms |
| Trace interval cumulative allocation | 1,620,460,560 bytes | 1,346,545,296 bytes |
| Trace interval GC CPU observation | 1,739 ms | 2,527 ms |
| Whole root observation interval elapsed | 12,099.978 ms | 13,699.531 ms |
| Whole interval cumulative allocation | 4,389,143,104 bytes | 4,086,849,360 bytes |
| Whole interval GC CPU observation | 3,409 ms | 4,188 ms |
| Sampled process RSS interval peak | 666,271,744 bytes | 647,430,144 bytes |

The root interval and probe interval have different endpoints. Their allocation
counter baselines also cannot be mixed: worker-start is later than root-before,
yet its cumulative reading is 7,344,288/7,940,704 bytes lower. This is direct evidence
against treating cross-place readings as one perfectly aligned ledger. The phase
deltas above subtract observations made within the same worker place; the whole
interval subtracts root observations. Do not force their totals to sum or derive
precise ownership percentages by dividing one scope by the other.

Cumulative allocation is reclaimed churn,
not simultaneous RAM; RSS covers the entire diagnostic process, rather than the
limited child job. These profiled timings are not paired performance measurements
against the earlier unprofiled replay and do not establish a slowdown or speedup.

Both trials record, in producer-time order:

1. Working and monitor thread registration.
2. Phase 09 starting expansion; phase 10 finishing expansion.
3. Phase 11 entering handlers; `go` dispatching expanded syntax and waiting.
4. Monitor `build-trace` start.
5. Explicit OOM, with no trace-complete/send-back-start point, monitor acknowledgement,
   phase 12 handler completion, or phase 13 compile completion.

The original compile call follows phase 12, so compilation is not reached in these
observations. No input events, phase points, sampling ticks or stale-generation
events are lost. Maximum observed phase delivery lag is 11.696/12.667 ms, which is
why producer timestamps, rather than receipt timestamps, define these intervals.

## Actual thread contexts

The observer records 41/45 sample ticks. During trace construction, 17/19 samples
contain a live monitor stack; two later samples in each trial see the working
thread dead and monitor weak reference collected. All live trace-stage working
thread samples show the expected handler wait context.

The final live monitor stack in both trials is:

    document-variable        traversals.rkt:1538
    annotate-variables       traversals.rkt:776
    expanded-expression      traversals.rkt:48
    build-trace              online-comp.rkt:77 (instrumented line)
    monitor                  online-comp.rkt:135/125 (instrumented lines)

`document-variable` is the first frame in 6/17 and 2/19 live trace-stage samples.
Other first frames include `level+tail+mod-loop:223`, syntax-list operations,
identifier-table operations, `collect-general-info`, `add-sub-range-binders`,
`add-disappeared-bindings`, class dispatch and `hash-ref!`.

These are coarse wall-clock context samples, not CPU shares. Repeated recursive
frames must not be counted as independent samples. Monitor frame lists hit the
eight-frame cap in 9/12 rows across the complete trials; no source/name text was
truncated and there were no sampling errors. Consequently the evidence identifies
traversal/annotation work without proving an exclusive allocating function or the
exact instruction that triggers the memory-limit shutdown.

## Next bounded change

Review the exact `document-variable`/`annotate-variables` source and its repeatedly
invoked documentation/binding queries for a narrow, semantics-preserving reduction
in repeated work or retained data. The terminal stage is now established, so this
review should precede a broad transport rewrite. Any candidate must first prove
equivalent complete annotation traces, documentation links, lexical/module/phase
distinctions and live rename/name-duplication behavior on successful inputs.

Then measure a fresh matched macOS GUI workload with unchanged settings and the
same source, recording completed tool outcomes, lexer readiness, queued and
scheduled typing tails, GC/allocation and memory. Keep actual OOM outcomes visible.
If no safe local reduction is supported, process isolation remains an experiment
for GUI responsiveness, with compiler-lock/capability and cancellation gates; it
cannot be presented as repairing this stock OOM merely by changing processes.

## Reproduction and retained evidence

Raw log SHA-256:
`6cb3cd0de23f282bb6019d2f436e531abaac5613678ad2e942042f1eed6b6e47`.
Decoded documents are in `openracket-recovery/results/run-38102050130/decoded`.
The accompanying `analyze_phase.py` validates ordinary replay identity/cleanup,
checks trial/generation/observer flags, and emits phase counter deltas and sampled
frame counts. `analysis-38102050130.json` contains all recomputed values plus each
decoded document's SHA-256. The original completed replay report and raw evidence
remain unchanged.
