# OpenRacket recovery and gap inventory — 2026-11-06

For Albert and the parallel ChatGPT **dotty** session. This inventory describes
the recovered Git sources, not a recovered October 27–30 working directory or a
newly validated application.

## Scope and provenance

- Working directory: `/Users/s_avelova/Documents/projects/openracket-codex-burn`.
- Local task branch: `codex-burn/20261106`, initially clean at
  `0aa912fa8abe00691768832b0f68fc04eebe211f`.
- Baseline: `origin/prototype/retained-drracket`, commit dated
  **2026-10-22 21:01:34 +08:00**, “Handle Darwin zombie-group signal rejection
  only after fresh quiescence proof.”
- Owner-established fact: **no local OpenRacket checkout existed on this Mac
  before today's clone**. The available Git reflogs corroborate a clone on
  November 6 at 15:43:04 +08:00 and creation of this task branch at 15:43:18.
  Reflogs alone cannot establish the absence of every earlier directory; no
  machine-wide file search was performed.
- This is a linked worktree with shared Git metadata. Only this worktree is the
  editing target; the other worktree's files were not surveyed or changed.

This task adds documentation and a local commit only. No push, merge, workflow
dispatch, deployment, runtime installation, release build or user-data cleanup
is part of it.

## Branches: local inventory versus live GitHub

Origin is [alikatgh/openracket](https://github.com/alikatgh/openracket).
The connected GitHub branch listing and a read-only
`git ls-remote --symref origin HEAD 'refs/heads/*'` check on November 6 agree
with the clone's remote-tracking refs:

| GitHub branch | Tip | Commit date (+08:00) | Local representation |
|---|---|---|---|
| `prototype/retained-drracket` | `0aa912fa` | 2026-10-22 | `origin/prototype/retained-drracket`; task branch starts here |
| `website/openracket` | `84f3b602` | 2026-10-12 | `origin/website/openracket` |
| `main` (GitHub default) | `64c0f457` | 2026-10-11 | `origin/main` and local `main` |
| `ci/rust-preview-checks` | `519d8076` | 2026-10-10 | `origin/ci/rust-preview-checks` |

Full tip identities:

```text
prototype/retained-drracket 0aa912fa8abe00691768832b0f68fc04eebe211f
website/openracket         84f3b6025ea67c939eb91eacd62dfe9821d04a2e
main                       64c0f45744f30e5650061318c58678cc671cb379
ci/rust-preview-checks      519d807615836f2db3dd34b2ec08f5a464c673ce
```

`prototype/retained-drracket` is the newest advertised branch tip. `main` is
older documentation work, not the newest application source. At this baseline,
`origin/main...0aa912fa` has **6 main-only and 65 prototype-only commits**;
the branches have diverged, so newest does not mean a strict superset.

The only local branches at survey start were `main` and `codex-burn/20261106`.
The latter had no same-named GitHub branch. `origin/HEAD -> origin/main` is a
symbolic default reference, not another branch. This is a non-shallow clone.
The local documentation commit will advance only `codex-burn/20261106`; the
baseline and remote tips above remain the recovery anchors.

## What the prototype actually contains

| Area | Recoverable contents and interpretation |
|---|---|
| [Root README](../README.md), `src/`, `runtime/` | Original Rust/Iced plain-text editor and real subprocess Racket bridge. Definitions/Interactions, tabs, guarded saves, errors/navigation and bounded runtime transport are documented. It lacks full DrRacket tools and WXME support. This track's README, source, runtime, runtime tests and `docs/macos` are unchanged between the checked `main` and prototype tips. |
| [retained-host](../retained-host/README.md) | Separate reuse of genuine DrRacket 9.3 editors, evaluator, callbacks and tool registry. Contains guarded presentation overlays, appearance tools, autosave work, isolated-profile launch/setup helpers, memory-default work, preservation tests, performance harnesses and experiments. The original host is retained; this is not the root Iced application. |
| [Retained candidate guide](../retained-host/PORTABLE-CANDIDATE.md) and [later installation report](../retained-host/reports/PORTABLE-INSTALLATION-38114573816.md) | Historical Mac source-preview installation, isolated appearance/autosave and fresh-profile 256 MiB preference acceptance. Existing profiles retain their choices. The limit is per job, not whole-app RAM; older pending wording inside frozen source is not the last report. |
| [cocoa-native-ci](../cocoa-native-ci/README.md) | Another application track: a source-only Cocoa editor package with Rust/Racket engine, Scintilla/vendor inputs, manifests, adapters and compile-first native CI configuration. Its README says it has not passed that native workflow. It includes no compiled app, runtime, installer or DMG. |
| [runtime-tests](../runtime-tests/test_bridge.py) | Python subprocess/protocol checks against the root `runtime/bridge.rkt`, plus IPC, parameter-retention and Rust supervisor benchmarks. A real installed Racket is required for bridge execution. The parameter and supervisor benchmarks use Linux `/proc`; they are not Mac GUI evidence. |
| [docs/macos](macos/BUILD-PLAN.md) | Prepared build/packaging and manual QA guidance for the original Iced preview. The build-only workflow is manual and does not retain a downloadable app. The publish YAML is an inert example. These older documents do not describe acceptance of the separate retained-host or Cocoa tracks. |
| `reports/` and `retained-host/reports/` | Checked-in historical run summaries, scope limits, hashes and acceptance plans. Their linked runs and screenshots were not freshly downloaded or revalidated in this inventory. A referenced external evidence directory is not necessarily present in this clone. |

### Cocoa source is packaged, not absent

[PUBLIC-SOURCE.json](../cocoa-native-ci/PUBLIC-SOURCE.json) declares **1,159 files**
and **20,551,193 raw file bytes**, including `cocoa/`, `engine/`, `racket/`,
`tests/`, `ci/`, `benchmarks/` and `vendor/`. For example, the manifest names
`cocoa/BracketNavigation.hpp` and `cocoa/DiagnosticNavigation.hpp`; those names
alone do not establish dotty's reconstructed navigation changes.

The nine checked-in [source parts](../cocoa-native-ci/SOURCE-PARTS.json) total
**4,689,100 bytes**. This survey verified every part's byte count and SHA-256,
the concatenated payload hash, and the manifest's declared file/byte totals:

```text
e9ee1056763f8e0b946d3a4e065b8136c4b1f445b2eed0e8342aa4896330b05d
```

No source extraction or application build was needed. These checks establish
intact package parts and consistent descriptors, not full decoded-member
admission, compilation or native correctness. The adapter documents strict
path/member/hash validation before writing decoded source.

## Open blockers, with the age of the evidence preserved

[status.json](../retained-host/reports/status.json) describes the retained-host
proof, not the Cocoa or Iced application. It pins the fifth native run
`38050824369`, commit `fcf24f95dd0196b3be4945d1eede50e91ea43846`.
Its `blocking_prerequisites` are exactly:

1. “Diagnose untouched macOS stock Stop completion timeout before certifying matching modern workflow”
2. “Attribute large-file lexer stabilization and multi-second event-loop stalls without disabling stock tools”
3. “Debugger/Macro Stepper/teaching/accessibility coverage remains open”

That snapshot records 120 Racket and 12 patcher tests, basic native host passes,
12 valid Linux performance trials and six valid Mac 100k trials. All six Mac
1 MiB trials failed readiness. It explicitly has
`native_stock_workflow_parity_verified: false` and `speedup_claim: false`.
These are historical report values, not tests run today. Its `remote_writes`
field describes earlier publication, not authorization or a write in this task.

Later checked-in evidence narrows, but does not erase, those blockers:

| Blocker | Later evidence and remaining gap |
|---|---|
| Stop completion | [Eighth-run report](../retained-host/reports/NATIVE-REPAIR-38054215191.md) records strict Stop passing both Mac arms but failing pristine Linux. Intermittent completion and full parity remained unresolved. The [follow-on plan](../retained-host/reports/FOLLOW-ON-ACCEPTANCE.md) separately excludes actual second Kill, its dialogs and recovery from the first-Stop proof. Diagnose stock behavior before blaming an overlay. |
| Large-file readiness/stalls | [Installation/capacity report](../retained-host/reports/PORTABLE-INSTALLATION-38114573816.md) records the tested 1 MiB workload failing at stock 128 MiB and completing at 256 MiB, still taking about 33–39 seconds. This explains a measured capacity failure, not all stalls or end-to-end latency. Keep stock tools, instrumentation and limits visible in matched comparisons. |
| Debugger/Macro Stepper/teaching | [Later dark-mode tool report](../reports/NATIVE-TOOLS-38140896349.md) records all three bounded stock/modern workflows passing, including debugger stepping, macro navigation and teaching report navigation/fix/rerun. [Later light-tools/Quit report](../reports/FUNCTIONAL-MAC-38154975508.md) adds light-mode tool passes and tested Quit/unsaved-document paths. These supersede earlier blanket “untested” wording for those fixtures. Broad parity, Language-dialog/pedagogical Step coverage, accessibility, IME and physical-input behavior remain separate. |

The follow-on plan itself is dated October 10 and contains earlier “not yet
executed” wording. Use its acceptance criteria alongside later outcome reports,
not as the latest results ledger. The short next-work list is
[OPEN-WORK.md](OPEN-WORK.md).

## October 27–30 gap: unknown and missing locally

Dotty reports that October 27–30 working files are missing and that navigation
fixes were rebuilt from the October 22 source with **14 tests**. That is a
parallel-session report. This survey has not received or compared its patch,
file inventory, exact source hashes or test output, and did not reproduce it.

Observed here:

- The clone's available history and advertised branch tips stop before that
  interval; `git log --all --since=2026-10-27 --until=2026-10-31` returned no
  commits at survey time, before this documentation commit.
- The task worktree started clean at the October 22 prototype tip. There was no
  uncommitted October 27–30 file set here to inventory.
- The Cocoa public package intentionally distributes reviewed source without
  its development history, prior result files or local provenance, per its
  [README](../cocoa-native-ci/README.md). A packaged file list is not a complete
  inventory of another session's workspace.

**Likely gap:** work created after the published October 22 baseline was not
captured in the branch history available to this clone. Whether it was saved,
committed elsewhere, exported, or retained in dotty's environment is unknown.
This evidence does not establish deletion, loss of an earlier Mac checkout,
the location of the missing files, or equivalence of a reconstruction.

For reconciliation, dotty should supply a nonsecret file/path list, patches or
exports for the missing/rebuilt work, the exact baseline used, and the 14-test
command/output. Compare those against the existing manifests and source before
applying anything. Preserve originals and classify recovered originals,
reconstructions and newly written changes separately. Historical paths in
reports, including `openracket-recovery/results/...`, do not prove those
directories existed on this Mac before today's clone.

## Safe next engineering steps without large downloads/builds

1. **Reconcile the gap first.** Work from this branch and the exact October 22
   anchor. Review dotty's patch and test evidence when available; do not reset
   or overwrite either session's files or claim the missing work is recovered.
2. **Keep the application track explicit.** Continue retained-host work against
   its stock control and acceptance plan; review Cocoa navigation against its
   packaged source and tests. Root bridge tests cannot certify either GUI.
   Reuse the existing DrRacket host, manifests, adapters and tests.
3. **Prepare one bounded investigation.** For Stop, inspect real callbacks,
   existing `stop`/`stop-returning` fixtures and timeout receipts. For stalls,
   inspect existing capacity, lexer and event-loop reports before selecting
   one hypothesis. Write the stock/modern acceptance and fixed timeout first.
4. **Use static checks first.** Review source diffs, JSON manifests, shell/Python
   syntax and documentation links without installing packages or toolchains.
   Any future process-only bridge test needs an already installed compatible
   Racket and measures only that protocol. Do not run Linux `/proc` probes on
   macOS as if they were equivalent evidence.
5. **Defer native execution to a separately prepared, authorized run.** GUI
   acceptance requires genuine native frames/state and relevant screenshots;
   accessibility/IME/physical input need their own desktop checks. Check current
   capacity, spending enforcement and workflow prerequisites before activation.
   The Cocoa workflow can download full Racket and perform an offline Cargo
   release/native build; “offline” does not make it a lightweight survey command.

Read-only commands for a later inventory refresh, from this worktree:

```sh
git status --short --branch
git branch --all --verbose --no-abbrev
git ls-remote --symref origin HEAD 'refs/heads/*'
git log --all --since=2026-10-27 --until=2026-10-31 --oneline
git rev-list --left-right --count origin/main...0aa912fa
git diff --check
```

The new local commit records this inventory in November; it is not recovered
October work. Do not run the README's release-build or package-setup
commands merely to refresh this inventory. Both retained and Cocoa workflows
have push triggers on `prototype/retained-drracket` with path filters; pushing
there can activate work. This task has no push authorization.

## Verification of this inventory

Performed: local clean-state/ref/reflog/history inspection; live GitHub branch
listing and remote-tip comparison; targeted reading of the listed tree areas;
Cocoa part/descriptor integrity checks; documentation link and whitespace checks.
Only the two requested Markdown documents are intended changes.

Not performed: product tests (including dotty's 14), source-bundle extraction,
Rust/Cocoa/Racket builds, package installs, new CI runs, native GUI interaction,
fresh historical-log/screenshot validation, packaging, upload or deployment.
This document is a durable recovery inventory, not a readiness or release claim.
