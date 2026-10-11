# macOS phase-observer control: replay mismatch remains

Run [38113445332](https://github.com/alikatgh/openracket/actions/runs/38113445332),
commit `8e2bed70d040f7090fde987f89868287a8ab21f5`, 2026-10-11.

## Result

The actual 256 MiB DrRacket GUI request completed successfully. Both fresh isolated
replay processes, with phase observation off and on, explicitly ran out of memory
before delivering any Check Syntax monitor message. Disabling phase sampling alone
was insufficient to restore the successful GUI outcome. This is a diagnostic
finding, not a speed improvement or an equivalent completed-work comparison.

The control validator accepted the evidence with no observation failures. It
separately reports `both_successful=false`, terminal-summary parity false,
monitor-scalar parity false, and completed phase coverage false. The earlier
[38110770395 completed-phase acceptance](https://github.com/alikatgh/openracket/actions/runs/38110770395)
remains failed. Exit zero from these replay drivers means the real OOM was observed
and cleanup completed; it does not mean background analysis succeeded.

## Exact workload and safeguards

- One new GUI capture, then one off and one on replay in fresh, sequential processes.
  Off PID 3727 ended before on PID 3934 began. Both were first requests after initialization.
- Official Racket 9.3 on macOS. The actual worker cap was 268,435,456 bytes and
  custodian memory accounting was available in both arms. The captured profile was
  initialized through the verified public one-key preference setup.
- Snapshot: 1,048,577 ASCII characters, the deterministic 1 MiB fixture plus one
  real comment edit. SHA256 `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
  This is different from the earlier 80-key contention workload.
- Captured source, ordered registry, actual prefab settings, launch context and
  source pins matched in both arms. Registry SHA256
  `3bb53d3cf597b5a2c33e94bf251b17e1428831339526e6b1fba00cd1b420fb94`.
  Prefab: `#s(prefab-module-settings #() (default) #t #t none #t)`.
- Coloring and online compilation stayed enabled. Native initialization/terminal/
  cleanup bounds stayed 30/60/2 seconds, with the existing 97-second one-trial
  supervisor bound. Neither replay timed out. Internal and external cleanup passed.
- The prepared runtime source was unchanged from manifest `44b6c593…`; the reviewed
  control validator manifest was `34700917…`. Original runtime tree hashes stayed
  identical. No capture payload or CI artifact was uploaded.

The off arm still includes replay readiness/control and GC observation, unlike
the GUI capture. It is not an uninstrumented stock process. One sequential pair
also cannot establish reproducibility or remove order/cache effects.

## Actual outcomes

| Observation | GUI capture | Phase off | Phase on |
|---|---:|---:|---:|
| Terminal | handler-results | explicit OOM | explicit OOM |
| Monitor messages | 1 | 0 | 0 |
| Trace entries received | 292,728 | 0 | 0 |
| Rename-capability rows | 74,675 | 0 | 0 |
| Interval elapsed, ms | not comparable | 8,911.306 | 9,112.682 |
| Cumulative allocation, bytes | not measured here | 5,920,650,560 | 5,882,791,872 |
| Runtime GC counter delta, ms | not measured here | 2,376 | 2,457 |
| Largest sampled process RSS, bytes | not measured here | 915,472,384 | 906,149,888 |

The GUI returned a 270,280-byte compiled result, SHA256
`cf6fe105b208f0d5b068b07d30d304ba0be9c1bfcaa7cf2864c5425428ae00c2`,
with one clean monitor trace. Its 22,414.933 ms capture elapsed includes startup
and capture work, and the lexer was still invalid at that terminal. It is not a
fully settled GUI timing. The matching request list was `[1]`; this does not prove
a prior completed same-source warmup. Rename rows reuse the trace object's channel
pair; they are not 74,675 distinct endpoints.

Each replay's root GC receiver recorded 199 events: 197 minor and two major, with
no dropped or truncated rows. Largest observed GC wall pauses were 211.376 ms off
and 212.588 ms on. Worker GC receivers recorded zero rows; that is missing
visibility, not evidence of zero collections. Root and worker counters must not
be summed or assigned allocator ownership. Allocation totals are cumulative churn,
not retained RAM. RSS had 59/60 periodic available samples and is not an exact OS peak.

## Phase-on failure location

| Producer interval | Wall ms | Runtime allocation bytes | GC counter ms |
|---|---:|---:|---:|
| Initial expansion, phase 09→10 | 3,452.462 | 2,615,080,848 | 899 |
| Trace build start→complete/send start | 4,707.295 | 3,019,901,920 | 761 |
| Send start→post-OOM probe endpoint | 715.784 | 112,466,816 | 666 |

The final row includes the failed send interval, GC, OOM teardown and subsequent
probe queries. It is not a pure serialization measurement. Same-worker producer
counter differences still include concurrent runtime activity.

Trace construction completed. No monitor acknowledgement, worker phase 12
(handlers complete), or phase 13 (compile complete) followed. This again brackets
failure after the original send-back begins and before monitor delivery. The
driver's payload/capability walk runs only after delivery, so it cannot explain
this pre-delivery failure.

All three actual thread roles were registered. The on arm recorded 34 sample ticks
without dropped/stale events. Seven monitor rows hit the eight-frame cap; text
fields were not truncated. Eleven monitor first frames were `document-variable`.
Every xref sample was the anonymous outer service lambda, which contains both
waiting and service execution. These samples do not identify its allocation work.

## Engineering decision

Stop extending the isolated replay as a proxy for successful GUI work. The next
bounded observation should use the genuine 256 MiB GUI worker and record only
cheap phase counters/timestamps, with a normal GUI control to disclose observer
overhead. It should preserve real monitor/handler success, settings and final
source, distinguish GUI receipt from application completion, and omit the replay
readiness/control path and stack sampling. This is intended to select an actual
GUI bottleneck, not justify a production change from failed replay timings.

No limit increase, feature disablement, process bridge or trace-format change is
supported by this control alone. The known full-trace send/copy/retention overlap
remains a source-backed hypothesis, not an established GUI allocator cause.

## Evidence and reproducibility

Nine unique documents were reconstructed with exact recursive-array and whole-
document digests. A separate independent review recomputed the validator outcomes
and checked all 36 transported document instances. Analysis is in `analysis-38113445332.json`;
`analyze.py` is read-only and its five tests retain failure/parity/source/cap guards.

Raw log SHA256: `89882a20ae8ccfb29afe32c1129670028a26a27d0048dc916a1a20a9afff1fa4`.
Raw decoded evidence remains under `results/run-38113445332/decoded` in the CI
evidence workspace. The independent installer path probe was handled separately;
its path-representation finding changes neither these timings nor outcomes.
