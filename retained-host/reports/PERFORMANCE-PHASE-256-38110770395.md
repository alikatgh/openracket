# 256 MiB phase diagnostic: successful GUI capture, failed isolated replays

Date: 2026-10-11. [Run 38110770395](https://github.com/alikatgh/openracket/actions/runs/38110770395), [commit 5e6dce2](https://github.com/alikatgh/openracket/commit/5e6dce2ffec02848152f3405677d3f9bc1e44c59).

## Result

**Completed-request diagnostic acceptance failed and stays failed.** The actual DrRacket GUI request succeeded at 256 MiB, producing `handler-results` and one clean Check Syntax trace with **292,728 entries**, including **74,675 channel-bearing rename rows**. Both phase-instrumented isolated replays of that captured request instead produced explicit out-of-memory terminals before any monitor trace reached the driver.

The new phase points nevertheless narrow the failure: **both replays finished building the trace, then failed after entering the original trace-send path and before monitor acknowledgement or compilation.** This differs from the earlier 128 MiB probe, which died during trace construction. It is not a speed result or proof that 256 MiB is inadequate for the real GUI. The successful integrated capture and the earlier three successful 256 MiB GUI trials remain separate evidence.

## What passed, failed and was observed

- All 71 mandatory native preflight checks ran without skips. Pinned clone preparation, real GUI capture, worker protocol supervision and cleanup passed. The original full runtime remained unchanged.
- The actual GUI preference and captured request cap were 268,435,456 bytes. Both replay workers acknowledged that cap with custodian memory accounting available. Stock tools, the request prefab and ordered handler registry were preserved. No product optimization was enabled.
- The exact captured edited source was 1,048,577 characters, SHA-256 `f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735`. Both replays matched it, the source identity, actual prefab and registry. Registry SHA-256 was `d463642729368e267344dbee36742765debfeb7976b708bae8bd8d4fa7cc88d5`.
- This capture uses the original single-comment-edit diagnostic, not the separate 80-key contention workload. The capture took 35.266 seconds overall and the lexer was still invalid at its terminal observation. Its elapsed time includes capture/startup work and is not a matched GUI benchmark endpoint.
- Capture reported one selected request (`matching_request_ids=[1]`), one trace batch, no monitor errors or unknown payloads, and a compiled result of 270,280 bytes. It does not establish a prior completed same-source warm-up.
- Both replay terminals were `abnormal-termination`, explicitly “Expansion thread terminated unexpectedly (out of memory).” Each delivered zero monitor messages, zero trace entries and zero retained rename endpoints. Neither matched the successful capture terminal.
- Worker, monitor and actual existing xref-service threads were registered and had usable frames. No phase points, sample ticks or input events were dropped; no stale-generation events were accepted. Replay 1 had 55 sample ticks and replay 2 had 56.
- Strict acceptance correctly rejected missing successful terminals, missing trace delivery/count parity, missing completed phases and missing successful-result capability retention. The driver exiting normally means it observed and cleaned up those failures; it does not turn them into successful expansions.

## Observed phase boundaries

Phase counters below are sampled within the worker place at producer-side boundaries. They include concurrent runtime and observer work. They do not identify the thread that allocated memory. GB is decimal cumulative allocation churn, not resident RAM.

| Observed interval | Replay 1 wall, s | Replay 1 allocated, GB | Replay 1 GC counter, s | Replay 2 wall, s | Replay 2 allocated, GB | Replay 2 GC counter, s |
|---|---:|---:|---:|---:|---:|---:|
| Initial expansion, worker phases 09→10 | 5.611 | 2.616 | 1.326 | 5.331 | 2.617 | 1.190 |
| Build trace, monitor start→complete/send-start | 8.190 | 3.019 | 1.325 | 8.519 | 2.908 | 1.580 |
| Send-start→post-OOM probe end | 1.174 | 0.111 | 1.016 | 1.456 | 0.148 | 1.240 |

The final row includes the failed send interval, collection, OOM teardown and later diagnostic control queries. It is **not pure serialization cost**. Worker phase 12 (handlers finished), phase 13 (compile finished) and the monitor acknowledgement were absent in both runs.

The original `online-comp.rkt` calls `send-back` immediately after `build-trace` returns. The original `expanding-place.rkt` send-back closure calls `place-channel-put` with the complete monitor message under the job's limited custodian. No monitor response reached the replay driver, so the driver's later monitor-schema and capability walks cannot have caused this particular pre-delivery failure. This establishes the observed failure interval, not the precise internal allocation or root cause.

## Thread samples and their limits

During the trace-construction interval, the monitor's first frame was `document-variable` in `traversals.rkt:1538` in 18 of 30 sample ticks in replay 1 and 13 of 32 in replay 2. Other visible work included identifier tables, syntax traversal and contract traversal. The second replay's final pre-send sample showed `reverse` beneath the monitor's trace-building call. These are approximate wall-clock observations, not percentages of CPU time or allocation.

All 111 xref-service samples exposed only the anonymous service lambda at original `xref.rkt:14`. That lambda contains both the request wait and service processing. The coarse stack does not resolve waiting versus inlined work, and does not establish the service as the allocator. It also does not justify another reply-cell optimization after the earlier candidate failed its speed comparison.

Retained stacks were bounded at eight frames. Replay 1 truncated ten monitor stacks; replay 2 truncated nine monitor stacks and one working-thread stack. No frame name or source text was truncated. Full capped records, not just the common frames, remain in the evidence.

## Whole isolated intervals and GC visibility

| Metric | Replay 1 | Replay 2 |
|---|---:|---:|
| Root-observed interval wall time, s | 15.433 | 15.479 |
| Runtime cumulative allocation churn, GB | 5.884 | 5.798 |
| Root-observed GC counter delta, s | 3.923 | 4.051 |
| Sampled process-group peak RSS, GB | 0.906 | 0.935 |
| Root GC log records | 200 | 198 |
| Largest wall duration in observed root GC rows, ms | 335.079 | 284.058 |
| Worker GC log records | 0 | 0 |

The supervisor's RSS is periodically sampled with `ps`, not the operating system's exact high-water mark. Its sample counts were 79 and 81 within the respective intervals. The observed root GC rows comprised 198 minor plus two major collections, then 197 minor plus one major. None was text-truncated and no receiver-buffer drops were recorded. Receipt-filtered records are not a complete collection ledger or a maximum-pause bound; zero worker rows do not mean no worker collection. Root and worker counters are not summed or assigned allocator ownership.

The common driver, initialization barrier, GC receivers, captured preference restoration, compiler manager and result sink remain part of standalone replay. The phase-enabled arm additionally has source hooks, bounded records, cross-thread continuation capture/formatting and control queries. Its retained buffers are small and bounded, but that does not prove its transient cost is harmless near a live-memory limit. No exact causal overhead or GUI input-delay comparison was measured here.

## Next bounded discriminator

At the same 256 MiB setting, capture one fresh real GUI request, then replay it once with phase observation off and once with it on, each in a fresh process. Use the existing frozen source and flag; retain the original initialization, terminal and cleanup deadlines. Keep all actual outcomes and the original failed completed-phase acceptance visible.

- If the off replay succeeds while the on replay fails, that is single-pair evidence of instrumentation sensitivity, requiring caution about the profiled limit boundary.
- If both fail, disabling phase sampling is insufficient to restore the GUI outcome; the broader standalone replay/collector/context difference remains.
- If both succeed, the earlier failure remains real but is not reproduced by that pair. It does not justify discarding it or calling the overhead zero.

This control is approved separately. No larger cap, disabled tool, altered send protocol or production patch is needed to ask this question. Settle the diagnostic's validity before using it to choose an allocation patch or process bridge.

## Integrity and reproducibility

The exact diagnostic freeze manifest is `44b6c593c61eb752b7da04eece27245f127d9c448dff576b52751f354e0c7e56`. Seven JSON documents were reconstructed with exact recursive/full digests from ordinary CI logs. The raw macOS log SHA-256 is `d737e5649428ea415e5d119ad9fe8a19d59b51c43547dc0acea3fad21b25c66b`.

The source remains an instrumented stock copy; no source payload/artifact upload was used. `inspect_failure.py` derives this failed-run classification and the observed phase intervals while retaining the original acceptance failures. `analyze.py`, the completed-request analyzer, deliberately refuses this run because completed-request acceptance is false. Raw records and derived `analysis-38110770395.json` preserve both OOMs and every measured scope distinction.
