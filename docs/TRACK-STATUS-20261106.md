# Three-track status — 2026-11-06

This snapshot covers local branch `codex-burn/20261106` through `3d87b38`,
the latest implementation commit inspected for this documentation sync. The
recovery anchor is `0aa912f` (October 22); today's nine commits run from
`91834b7` through `ca105f7` and the later `54c6b0c`, `e072cb4`, `3d87b38`.
See the [recovery inventory](RECOVERY-AND-GAP-2026-11-06.md) for provenance and
the still-unknown October 27–30 work. No remote state was refreshed here.

**Headless** means source/model/protocol or offscreen checks without an OS
window. **GUI/native** requires the actual application's controls and state,
even when automated. **Desktop/manual** covers the relevant physical input,
OS integration and accessibility environment. Offscreen native-widget rendering
is headless evidence. Proof from one application track does not certify another.

## What each track proves

| Track | Evidence currently available | What today's burn adds | Acceptance still open |
| --- | --- | --- | --- |
| **Root Rust/Iced preview** — `src/`, `runtime/` | [October 10 Linux QA](../qa/RESULTS.md) records model/file tests, in-process Iced widget events/rendering and real-Racket supervisor/app flows. It launched no OS window and is not a fresh result for today's changed source. | Root bridge rejects trailing garbage/second JSON values before dispatch; Python harness and real-Racket regression cases were expanded. Small Rust model tests and module documentation were added. These are headless changes; Rust test compilation was blocked. | Current changed bridge/Rust integration execution is not established by this sync. macOS compilation/window behavior, native dialogs, focus/clipboard, IME, accessibility, HiDPI and packaging remain unverified by the Linux report. Teaching tools, Check Syntax, debugger, Macro Stepper, WXME/snips and plugins remain outside this plain-text preview. |
| **Retained DrRacket host** — `retained-host/` | Historical reports record real DrRacket 9.3 core, input/EOF, WXME, bounded tool and native workflow passes. [P0/P1 map](P0-BLOCKER-MAP-20261106.md) distinguishes the fifth-run snapshot from later results. These are genuine GUI/native results within their recorded fixtures, not new November 6 acceptance. | Evidence decoder distinguishes valid JSON `null` from missing payload and rejects duplicates; headless prerequisites and historical counts are clarified. The blocker-to-report documentation map is complete. | Missing/rebuilt files and dotty's exact 14-test evidence remain unreconciled. Intermittent Stop completion, actual second Kill/dialog/cleanup/Run recovery and large-file stalls remain open. Broader tool lifecycle, Language-dialog/pedagogical Step, accessibility, IME and physical input need their own evidence. |
| **Cocoa source package** — `cocoa-native-ci/` | [Source-hygiene report](COCOA-SOURCE-HYGIENE-20261106.md) records successful in-memory admission of all 1,159 members / 20,551,193 raw bytes from nine pinned parts, plus 16 focused passing tests on Python 3.14.4. No extraction, compilation or app launch was involved. | `validate-package` reuses the extraction validator without writing source; descriptor schema/accounting and rejection tests were added. Separate adapter tests extend fail-closed supervisor edge coverage. | The native workflow has not passed. Broader adapter execution, runner/toolchain compatibility, bootstrap cleanup edges and a post-full-gate runtime-clone witness remain gaps. Compiler/build/smoke/full-gate receipts are absent. Screenshots, ordinary UI behavior, VoiceOver, system IME, performance and DrRacket parity remain unverified. |

There is **no new GUI/native or desktop/manual acceptance** in this snapshot,
and no notarized macOS app is established. Retained-host's historical native
passes cannot validate the separate Iced or Cocoa application. The historical
retained app-launch report describes an unsigned destination-built app, not a
delivered binary; see the [repository overview](../README.md).

## Today's commits and their proof boundaries

Listed in ancestry order, not as a new aggregate test result:

| Commit | Scope | Evidence boundary |
| --- | --- | --- |
| `91834b7` | Recovery inventory and initial open-work list | Documentation and package-part integrity; no reconstructed-work or native acceptance claim. |
| `603619b` | Cocoa adapter regression cases for Darwin zombie/session lookup and rejected signals | Test source for fail-closed supervisor behavior, not a retained-host Stop result or proof of executed native prerequisites. |
| `fe83f1b` | Root bridge whole-frame validation and protocol/adversarial cases | Headless protocol changes. Python harness checks do not execute Racket; real-Racket cases require an installed executable. Explicit process-kill coverage does not prove the Rust supervisor deadline or a GUI Stop action. |
| `a8d2481` | Root/Cocoa/macOS documentation | Separates the three applications and corrects packaging/status claims; no build or launch proof. |
| `0c3356e` | Retained-host replay-evidence decoder/tests and appearance-tool guidance | Transport validation and prerequisite clarification. The preserved 28-test appearance freeze count is historical, not a fresh suite count. |
| `ca105f7` | Rust module documentation and no-op redo, Unicode search and runtime-path byte-limit cases | Commit records rustfmt/whitespace checks passing. `cargo test --lib --offline --locked` stopped before compilation because `rfd` was not cached; the added Rust cases are not a passing test result. |
| `54c6b0c` | P0/P1 evidence map | Documentation mapping is complete; file/test reconciliation and native blockers remain open. |
| `e072cb4` | Python protocol harness, malformed-frame and replay-evidence edge cases | [Offline checks](../runtime-tests/README.md) use in-memory/mocked I/O; additional reset/shutdown rejection cases require real Racket. Added coverage alone is not a recorded runtime pass. |
| `3d87b38` | Cocoa package admission, focused tests and compile-first gap review | Recorded local package check and 16 focused tests passed. Broader `test_adapter.py` was not run in that increment; successful extraction and Python 3.11 execution were not tested. No native workflow result. |

This sync inspected commit diffs and checked-in reports. It reran no product
tests, historical native runs, external logs or screenshots. Where the table
describes added cases without a checked-in execution receipt, it makes no
passing-run claim. A Racket-dependent skip is not runtime validation. Current
headless commands and their prerequisites are in the
[root protocol guide](../runtime/PROTOCOL.md#verification),
[runtime test guide](../runtime-tests/README.md),
[retained tool guide](../retained-host/tool/README.md#headless-checks) and
[Cocoa guide](../cocoa-native-ci/README.md#lightweight-source-check).

## Remaining work and interpretation

[OPEN-WORK.md](OPEN-WORK.md) remains the prioritized backlog. Its P0 map is
complete, while reconciliation awaits nonsecret paths/patches, baseline/hashes
and exact 14-test command/output. A matching filename or test count does not
establish recovered originals or equivalent navigation behavior.

The retained-host [status snapshot](../retained-host/reports/status.json) is
historical, records full native stock parity as unverified and makes no speedup claim.
Later strict Mac Stop passes narrow the evidence without resolving intermittent
completion. The tested 256 MiB per-job default is capacity evidence, not a
whole-app RAM cap or responsiveness fix: analysis callbacks still took about
33–39 seconds, with later GUI application work separately measured. Binding-table
and named-style experiments remain default-off; the evidence does not support
adoption or a reliable complete-work speedup.

Retain the bounded historical tool passes in
[dark](../reports/NATIVE-TOOLS-38140896349.md) and
[light](../reports/FUNCTIONAL-MAC-38154975508.md) fixtures. Broader lifecycle and
physical routes remain separate gates under
[follow-on acceptance](../retained-host/reports/FOLLOW-ON-ACCEPTANCE.md).
For Cocoa, the [compile-first gaps](COCOA-SOURCE-HYGIENE-20261106.md#remaining-compile-first-ci-gaps)
must accompany any future build claim; source admission is not compilation.

## Checks and delivery for this sync

Only this document and `OPEN-WORK.md` are changed. Commit/report cross-checks,
all 27 local Markdown targets/anchors and the whitespace check passed. A separate
read-only review found no supported status/acceptance inaccuracies. No product
test, build, install, download, GUI action or cloud execution is part of this
increment. No temporary/build output is allocated and no cleanup deletion is
needed. Delivery is a local documentation commit, with no push or submission.
