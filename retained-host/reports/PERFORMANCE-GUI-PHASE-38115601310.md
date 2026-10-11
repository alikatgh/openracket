# macOS genuine-GUI phase result: late annotation application

Run [38115601310](https://github.com/alikatgh/openracket/actions/runs/38115601310),
commit `8b35effc0d96dc7bb205698998c1b5e90415194f`, 2026-10-11.

## Main finding

Both real DrRacket GUI processes completed the same edited 1 MiB request at the
256 MiB setting, including successful background analysis, a clean Check Syntax
trace, current final annotation application and a valid lexer. The long stage
previously hidden by terminal-callback/lexer endpoints is now visible:

- Trace application spans **21.778 seconds** in the common-observer control and
  **22.441 seconds** in the producer-observed arm.
- It finishes **18.211 / 19.373 seconds after the worker terminal callback returns**.
- It finishes **6.244 / 6.823 seconds after the lexer first appears valid**.

These spans include interleaved GUI work and scheduling; they are not exclusive
annotation CPU time. Nevertheless, late GUI processing is the clearest large
remaining user-facing interval. The next code review should prioritize the actual
trace consumers and their range/interval-map/binding-table operations. A worker
documentation-cache change would target only part of a smaller earlier stage.

This is successful attribution instrumentation, not an optimization or a speedup.
The previous standalone replay failures remain failures; this experiment bypasses
that mismatch by observing the actual GUI workflow.

## Successful work and identity

Mandatory native preflight passed all 53 test cases with zero skips, plus the
profile helper tests; exact diagnostic compilation passed. Strict paired
acceptance returned `accepted=true` with no failures, independently recomputed
from the raw records. Both processes exited cleanly without timeout or residual
processes. The original complete runtime tree remained unchanged.

The two arms use one independently cloned official Racket 9.3 macOS runtime and
fixture, with distinct empty profile/addon directories. The public preference is
268,435,456 bytes, verified on disk and in the actual worker with memory accounting
available. Coloring, online compilation, installed stock handlers and original
20 ms trace-application batching remain active. All GUI completion waits share the
original 90-second post-edit deadline inside the unchanged 190-second process bound.

Both arms have exactly one matching final request/job and identical:

- 1,048,577-character source, the original mixed 1 MiB fixture plus one middle-comment
  `x`; SHA256 `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`.
- Actual prefab `#s(prefab-module-settings #() (default) #t #t none #t)`;
  matching pending-next-Run settings are separately recorded, not used as a claim
  about a running evaluator.
- Actual ordered `go`/`monitor` registry, bound to the verified clone module's
  resolved path and source hash.
- `handler-results` with 270,280 compiled bytes, one clean trace containing
  292,728 rows and 74,675 channel-bearing rename-capability rows.
- Current generation-one application completion, no cancellation, stale events,
  duplicate points, dropped jobs or observer errors; unchanged final source and
  final lexer validity.

Rename rows are not distinct channel counts. Scalar trace/terminal agreement is
not full payload, annotation-order or capability-response equivalence. No product
behavior was changed by an optimization in this run.

## GUI timeline

All times below are within each process, relative to its actual request-observation
hook. They are not cold-launch or physical input-to-photon measurements.

| Endpoint | Common-observer control, seconds | Producer-observed, seconds |
|---|---:|---:|
| Actual monitor message received | 15.635 | 15.776 |
| Trace application entered | 16.206 | 16.300 |
| Worker terminal callback returned | 19.773 | 19.368 |
| First final lexer-valid observation | 31.740 | 31.918 |
| Final annotation application completed | 37.983 | 38.741 |

The first monitor callback lasts 20.244 / 21.099 ms, consistent with the source's
cooperative batching. Returning from that callback does not end the application:
stock queued continuations keep processing the remaining rows.

Common monitor receipt/schema processing before its queue attempt takes
551.137 / 506.014 ms. This includes the observer's full trace-schema walk, allocation
counter reads, concurrent runtime work and scheduling; it is an explicit common
cost, not a measured stock application stage. Queue attempt to monitor callback
entry is 18.916 / 18.169 ms. Terminal queue attempt to callback entry is 4.020 /
0.840 ms. These two real callback observations do not characterize typing tails.

The final application point follows the original normal empty-trace branch's
blue-box update, arrow update, running-color removal and running-state reset. It
records completion of those operations, not subsequent painting. Final source and
lexer checks pass after that endpoint.

## Producer-observed worker phases

The control emits no producer points. The observed arm has all ten expected points,
without duplicates or drops. Deltas here are between endpoints sampled in the same
worker place; allocation/CPU/GC counters still have whole-runtime scope.

| Interval | Wall seconds | Cumulative allocation GB, decimal | GC counter seconds |
|---|---:|---:|---:|
| Initial expansion | 4.985 | 3.289 | 1.524 |
| All handlers, parent interval | 7.142 | 4.431 | 1.750 |
| Trace construction, nested in handlers | 6.808 | 4.221 | 1.555 |
| Trace send until return, nested in handlers | 0.335 | 0.210 | 0.195 |
| Compilation | 5.642 | 5.311 | 1.736 |

Do not sum parent and nested intervals. Monitor acknowledgement to handlers-finished
is 0.024 ms; compile-finished to terminal-send-return is 0.123 ms. The original
full-trace send returns successfully in the GUI workflow. This evidence does not
establish why its isolated replay counterpart exhausted the same nominal limit.

## Late runtime allocation and GC observations

| GUI observation interval | Control wall seconds / allocation GB / GC seconds | Observed wall seconds / allocation GB / GC seconds |
|---|---:|---:|
| Application entry→completion | 21.778 / 10.502 / 0.822 | 22.441 / 10.659 / 0.773 |
| Terminal callback return→application completion | 18.211 / 6.567 / 0.485 | 19.373 / 6.603 / 0.500 |
| Request observation→application completion | 37.983 / 20.228 / 6.087 | 38.741 / 20.204 / 6.287 |

The corresponding application-span process CPU counters rise by 22.121 / 22.948
seconds; after the terminal callback they rise by 16.417 / 17.500 seconds. These
are aggregate process/all-place observations. They cannot assign work to an editor,
thread or particular trace method. Coloring, normal autosave, Check Syntax and
other stock GUI work can interleave. The recorded late GC time is much smaller
than the late wall span, so a claim that GC alone accounts for that delay would
not fit these observations.

The roughly 20 GB total is cumulative allocation churn, not retained RAM. This
minimal run did not collect peak RSS, a GC pause distribution, a heartbeat series
or paced typing samples. Earlier measurements cover different endpoints/workloads
and should not be merged with this one as if they were the same benchmark.

## Limits and next action

There is one observation per arm, in control-then-observed order. The approximately
0.758-second difference in request→application span cannot establish precise
observer overhead or a regression. Both arms include common request hashing,
registry/cap proof, monitor-schema scanning and post-terminal worker-report writing.
The latter may overlap application. No GUI hook writes reports while processing
the trace; host persistence happens after endpoints. No extra sampler, GC logger,
standalone readiness barrier or replay control channel is present.

The earlier memory-sensitivity report measured worker terminal callback and lexer
completion. Those successful capacity outcomes remain valid for those endpoints,
but this new application endpoint exposes additional work afterward. Future speed
comparisons should require final current annotation application as well.

Review the actual GUI trace-consumer data structures next. Preserve every annotation,
ordering rule, range boundary, source association and cancellation behavior. A safe
candidate must pass exact semantic regressions, then the same genuine-GUI completed-
work comparison; do not substitute fewer tools, a larger cap or earlier completion
markers for a speed improvement.

## Reproducibility

Frozen package manifest: `dcb636609bae519f9b61c67fc91f422f77e326e4466379f5bbba947006cf1fc1`.
All 44 transported instances covering 13 unique JSON documents passed canonical
digest reconstruction. Raw log SHA256:
`8f77ca4d79bea016f42ae1ea9ea0fe1ba8f3a7f88379abe91e1a991fb9366771`.

`analyze.py` recomputes strict paired acceptance before deriving intervals;
`test_analyze.py` has five passing completion/source/endpoint rejection tests.
Full derived values and input hashes are in `analysis-38115601310.json`. Raw
documents remain under `results/run-38115601310/decoded` in the CI evidence workspace.
