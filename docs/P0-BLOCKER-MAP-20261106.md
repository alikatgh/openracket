# P0/P1 blocker evidence map — 2026-11-06

This completes the documentation portion of [OPEN-WORK.md](OPEN-WORK.md)'s P0:
map the known evidence and preserve the missing inputs. It does **not** complete
dotty's file/test reconciliation or any native acceptance gate. Read alongside
the [recovery inventory](RECOVERY-AND-GAP-2026-11-06.md).

Recovery anchor: `0aa912fa8abe00691768832b0f68fc04eebe211f`, dated
2026-10-22 21:01:34 +08:00. This review began at local commit
`ca105f7424d06f1df60be6cbfdeb69c8d57f2c7c` on `codex-burn/20261106`.
The historical reports cited below are unchanged from that recovery anchor;
their outcomes were read, not rerun. Reported native results concern retained
DrRacket 9.3, not acceptance of the separate Iced or Cocoa application.

## Blocker map

Paths in link labels are repository-relative. Each P1 subrow belongs to one of
the two P1 entries in OPEN-WORK; splitting the evidence does not add new gates.
**Unknown** means the reviewed evidence does not establish the answer.

| Blocker | Evidence path and historical narrowing | What headless can still prove | What needs GUI/native |
|---|---|---|---|
| **P0 — missing/rebuilt October 27–30 files versus October 22** | No retained-host report supplies dotty's missing-file inventory or patch. [retained-host/reports/patch-manifest.json](../retained-host/reports/patch-manifest.json) pins the known toolbar upstream/patched/painter bytes and presentation-only scope; [retained-host/reports/archive-integrity.json](../retained-host/reports/archive-integrity.json) records upstream archive checksums. Neither establishes later navigation changes. | Compare supplied paths/patches and raw-byte hashes against the exact anchor, [retained-host/BASE-SOURCE-SHA256.json](../retained-host/BASE-SOURCE-SHA256.json) and the appropriate track's manifest. For Cocoa, [cocoa-native-ci/PUBLIC-SOURCE.json](../cocoa-native-ci/PUBLIC-SOURCE.json) names packaged source; a matching filename is not a matching reconstruction. **Unknown:** originals' locations, missing/rebuilt path set, exact reconstruction baseline and equivalence. No such inputs were supplied in the reviewed materials. | File identity reconciliation itself needs no GUI. Any claim that reconstructed navigation works in the Cocoa application requires that application's own native evidence; retained-host passes cannot provide it. |
| **P0 — dotty's reported 14 tests** | [retained-host/reports/status.json](../retained-host/reports/status.json) records 120 Racket tests, 12 patcher tests and 14 native toolbar tests per mode. [retained-host/reports/RESULTS.md](../retained-host/reports/RESULTS.md), “Passed in the first real native Linux run,” identifies those toolbar checks. These are different historical suites, not corroboration of dotty's 14 navigation tests. | Match the supplied exact command, working directory, runtime, tested revision/file hashes, test names, full output and exit status to the reconstruction. **Unknown:** all those details and what the 14 tests cover. A count alone cannot establish shared tests, shared bytes or navigation behavior. | Source/model tests may establish their own contracts headlessly. Native navigation, focus/selection and recovery claims require the actual target app; the required boundary depends on the still-unavailable tests. |
| **P1 Stop — intermittent first-Stop completion** | [retained-host/reports/RESULTS.md](../retained-host/reports/RESULTS.md), fourth/fifth runs: Linux first-Stop sequences passed; pristine Mac timed out at 20 seconds. [retained-host/reports/NATIVE-REPAIR-38054215191.md](../retained-host/reports/NATIVE-REPAIR-38054215191.md) and [retained-host/reports/ci-eighth-run.json](../retained-host/reports/ci-eighth-run.json): both strict Mac arms passed, pristine Linux failed and matching modern Linux was skipped. Four isolated break-delivery controls passed per platform. | Reconcile stage outcomes and compare callback, fixture, polling and thread/custodian observations. [retained-host/reports/INDEPENDENT-QA.md](../retained-host/reports/INDEPENDENT-QA.md) separates an earlier invalid “Run must be disabled” assumption from later genuine completion timeouts. Pending-next-Run settings equality does not prove live evaluator configuration; isolated break delivery does not prove the real Stop lifecycle. **Unknown:** cause, frequency and why platform outcomes changed. | Fresh matched pristine-stock/modern cases with unchanged fixture, resource settings and 20-second bound; actual running/break-target state, Stop→Kill label and completed interruption. Neither a Mac-only diagnosis nor cross-platform parity follows from the reports. |
| **P1 Stop — returning-action discriminator and causal attribution** | [retained-host/reports/NATIVE-REPAIR-38054215191.md](../retained-host/reports/NATIVE-REPAIR-38054215191.md), “Separate Stop discriminator,” adds `stop-returning` without replacing original `stop`. [retained-host/reports/PERFORMANCE-BUDGET-38059373890.md](../retained-host/reports/PERFORMANCE-BUDGET-38059373890.md): Linux returning Stop passed; Mac budget arm timed out while stock passed. The report retains the failure and does not attribute it to the budget change. | Inspect [retained-host/tests/independent-native-stop-returning.rkt](../retained-host/tests/independent-native-stop-returning.rkt): each real GUI action returns before polling, and the completion bound remains 20 seconds. Compare this discriminator with the original case without changing assertions. **Unknown:** whether nested dispatch or the changed budget contributed; logged post-completion reuse is observational. | Execute both real callback routes under matched unchanged bounds and preserve timeout state/unexpected modal captures. A returning-action pass cannot silently replace a failing original case. |
| **P1 Stop — actual second Kill, dialogs, cleanup and successful Run recovery** | [retained-host/reports/FOLLOW-ON-ACCEPTANCE.md](../retained-host/reports/FOLLOW-ON-ACCEPTANCE.md), “Stop / Kill state and labels,” explicitly excludes these from first-Stop proof. The fourth-run sequence comparison in [retained-host/reports/ci-fourth-run.json](../retained-host/reports/ci-fourth-run.json) covers first Stop only. | Inspect [retained-host/tests/independent-native-workflows.rkt](../retained-host/tests/independent-native-workflows.rkt) to distinguish one Stop invocation and Run availability from an actual second Kill and a subsequent successful evaluation. **Unknown:** the excluded dialog/recovery outcomes; no closure is supplied by the reviewed reports. | Invoke the real second Kill, retain confirmation/notification behavior and any unexpected modal, verify cleanup, then complete a successful Run with retained source/editor state. |
| **P1 large files — capacity versus analysis completion/readiness** | [retained-host/reports/PERFORMANCE-BASELINE-38050824369.md](../retained-host/reports/PERFORMANCE-BASELINE-38050824369.md): six Mac 1 MiB trials failed the 45-second lexer gate. [retained-host/reports/PERFORMANCE-MEMORY-38107957744.md](../retained-host/reports/PERFORMANCE-MEMORY-38107957744.md): three 128 MiB trials explicitly OOM; all 256/512 MiB trials completed the measured worker outcome. At 256 MiB, final callback took **33.222–39.155 s**, while callback plus valid coloring took **33.274–44.117 s**. [retained-host/reports/PORTABLE-INSTALLATION-38114573816.md](../retained-host/reports/PORTABLE-INSTALLATION-38114573816.md) verifies fresh-profile 256 MiB installation while preserving existing/explicit choices. | Reconcile exact workload, worker outcome, preference ownership and endpoint definitions. This is the smallest **tested** sufficient job cap, not a speedup or whole-app RAM cap. Failed 128 MiB work and completed 256 MiB work cannot form a speed ratio. **Unknown:** an algorithmic improvement and current end-to-end editing latency. | A current matched complete-work test must retain tools, instrumentation and bounds, and observe the successful current worker, lexer and final GUI annotation application. The capacity/installer passes do not close stalls. |
| **P1 large files — late annotation work and event-loop waiting** | [retained-host/reports/PERFORMANCE-GUI-PHASE-38115601310.md](../retained-host/reports/PERFORMANCE-GUI-PHASE-38115601310.md): application completed 6.244/6.823 s after lexer validity. [retained-host/reports/PERFORMANCE-ANNOTATION-APPLICATION-38125605788.md](../retained-host/reports/PERFORMANCE-ANNOTATION-APPLICATION-38125605788.md): 28.810 s application span comprised 10.868 s active work and 17.942 s waiting; arrows dominated measured entry-call wall time. [retained-host/reports/PERFORMANCE-ARROW-GAP-38128156864.md](../retained-host/reports/PERFORMANCE-ARROW-GAP-38128156864.md) narrows a large arrow bucket to binding-table work, but sampled stacks are mostly truncated and the capture ends before completion. | Reconcile overlapping endpoints, inclusive call timings and sample coverage; inspect the real application/queue seams. **Unknown:** the late waiting region and exclusive CPU/allocation/GC ownership. Samples suggesting coloring/style/scanning are hypotheses, not complete attribution. The capacity study's 80-key workload and later one-edit GUI studies must remain separate. | Genuine current annotation completion, matched queue/command observations, cancellation and recovery with original tools. Heartbeats and synthetic keys do not establish physical input-to-photon latency or completed display painting; those need desktop measurement. |
| **P1 large files — binding-table optimization moves or increases work** | [retained-host/reports/PERFORMANCE-BINDING-TABLE-38131918285.md](../retained-host/reports/PERFORMANCE-BINDING-TABLE-38131918285.md): lazy application gains deferred 5.625–8.551 s and about 2.633 GB allocation into the first public getter; application plus getter worsened every pair. [reports/PERFORMANCE-BINDING-EAGER-38139675236.md](../reports/PERFORMANCE-BINDING-EAGER-38139675236.md): eager getter stayed below 0.03 ms, but two of three complete-work pairs regressed and application median queue delay worsened in every pair. Both candidates remain default-off. | Check activation/source pins and public getter/export semantics, keeping all completed work in the comparison. Removing a deferred getter stall is a contract improvement over the lazy candidate, not proof of a gain over stock. **Unknown:** a useful complete-work optimization; these results do not justify adoption. | Any changed candidate needs actual native semantics plus full matched completed-work/queue evidence. Headless getter/model correctness cannot establish current large-file responsiveness. |
| **P1 large files — latest named-style experiment** | [reports/PERFORMANCE-NAMED-STYLE-38161626767.md](../reports/PERFORMANCE-NAMED-STYLE-38161626767.md): all six native arms passed and the cache served roughly 320,000 natural lookups per candidate trial, but full readiness/application regressed in two of three pairs. Early submission→handler maximum worsened in all three pairs. Candidate remains default-off. | Preserve paired results rather than selecting favorable separate-arm medians. The proposed default-object hashing diagnostic is a hypothesis, not an executed improvement. **Unknown:** cause of variability, exclusive lookup savings and reliable end-to-end benefit; the frozen schema lacks RSS/peak-memory evidence. | An isolated future candidate requires native semantics and a complete matched workload before a speed/latency claim. No further tuning run or activation is authorized by this documentation map. |

## Interpretation and remaining inputs

The original [status.json](../retained-host/reports/status.json) is a fifth-run
snapshot, not the latest results ledger. Its third prerequisite,
Debugger/Macro Stepper/teaching/accessibility coverage, maps to OPEN-WORK's P2/P3
work rather than another P1. Bounded tools already passed in
[reports/NATIVE-TOOLS-38140896349.md](../reports/NATIVE-TOOLS-38140896349.md) and
[reports/FUNCTIONAL-MAC-38154975508.md](../reports/FUNCTIONAL-MAC-38154975508.md).
Broader lifecycle, Language-dialog/pedagogical Step, accessibility and physical
input remain distinct; this map does not relabel the passing fixtures untested.

Earlier rejected paths also remain evidence: the
[8 ms budget](../retained-host/reports/PERFORMANCE-BUDGET-38059373890.md) lowered
synthetic fence delay while slowing completed work/failing a trial; the
[xref reply candidate](../retained-host/reports/PERFORMANCE-XREF-38106066111.md)
left all six 128 MiB analyses OOM; the
[interval-map matrix](../retained-host/reports/PERFORMANCE-INTERVAL-MAP-38121983444.md)
was incomplete with no consistent responsiveness gain. Keep the original tools,
coloring, instrumentation, 20 ms budget and fixed bounds visible in future paired
work. Performance candidates with common-observer stock controls are not a
measured speedup of the delivered appearance preview.

The next P0 step is to obtain dotty's **nonsecret** baseline, path inventory,
patch/export, per-file hashes and exact 14-test command/output. Classify each
provided file as recovered original, reconstruction or new work, identify its
application track, and compare it without applying or overwriting it. Until those
inputs exist, reconciliation stays **open**; missing evidence does not establish
deletion, recovered originals or equivalence.

Headless arithmetic reanalysis is possible only where the actual raw records
and exact analyzer are available. A report's recorded digest or external
`results/...`, `decoded`, screenshot or `analysis.json` path does not establish
that the referenced evidence is present in this checkout. No external logs or
screenshots were downloaded or freshly validated here. Supervisor/watcher
failures that prevented a stage from executing are blocked execution, not an
observed DrRacket Stop result or a passing performance trial.

## Checks for this increment

Read-only report/fixture inspection, comparison of the cited historical reports
against the exact recovery anchor, P0/P1 table coverage, local Markdown link and
whitespace checks. Only this document is changed and committed locally.

No product tests, builds, native acceptance, GUI automation, installations,
downloads or remote writes were run. No temporary/build output was allocated
and no files were deleted. Disk headroom was checked against the 1.5 GiB floor;
the final measured document size and free space are reported with the commit.
