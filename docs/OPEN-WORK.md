# Open work — recovery baseline 2026-11-06

Priorities derive from [status.json's blocking prerequisites](../retained-host/reports/status.json)
and [FOLLOW-ON-ACCEPTANCE.md](../retained-host/reports/FOLLOW-ON-ACCEPTANCE.md).
See [the recovery inventory](RECOVERY-AND-GAP-2026-11-06.md) for branches,
the unknown October 27–30 gap and the separate Iced/Cocoa tracks.

**Headless only** means no native window is needed. **GUI/native** requires
real retained DrRacket controls/state, even if automated. **Desktop/manual**
requires the relevant physical input or accessibility environment. Headless
preparation cannot close a native acceptance item. All run outcomes below are
checked-in historical reports, not checks repeated on November 6.

| Priority | Work and completion condition | Required evidence |
|---|---|---|
| P0 | Reconcile dotty's missing/rebuilt files and 14-test evidence against the exact October 22 baseline. Map each blocker to the later report that narrows it; preserve unknowns. | **Headless only:** patch/path/hash review and exact test command/output; no build or install needed for inventory. |
| P1 | Diagnose intermittent stock Stop completion with matched stock/modern fixtures and unchanged bounds. Then cover actual second Kill, confirmation/notification, cleanup and successful Run recovery. | **GUI/native.** [Later report](../retained-host/reports/NATIVE-REPAIR-38054215191.md) passed strict Stop on Mac but failed pristine Linux; neither a blanket Mac-only diagnosis nor full parity follows. |
| P1 | Attribute large-file lexer stabilization and event-loop stalls without disabling stock tools. Separate memory capacity, analysis completion and editing latency; retain matched workloads/settings and timings. | **GUI/native**, with headless report/source analysis first. [256 MiB capacity acceptance](../retained-host/reports/PORTABLE-INSTALLATION-38114573816.md) did not eliminate 33–39-second analysis or establish a speedup. |
| P2 | Extend input/EOF, WXME and Check Syntax beyond bounded passing fixtures: actual EOF-snip pointer targeting; native rich clipboard/drag-drop/plugin-snip round trips; arrows/rename, source/selection and cross-workflow recovery. | **GUI/native + desktop/manual** for physical routes. [Input/EOF, WXME and binding-table comparisons passed historically](../retained-host/reports/NATIVE-REPAIR-38054215191.md); retain those results and test the uncovered boundaries. |
| P2 | Complete tool lifecycle scope beyond the accepted Debugger, Macro Stepper and teaching fixtures, especially edit-induced obsolete Macro Stepper sessions, unchanged definitions and retained editor/window recovery. | **GUI/native.** Bounded stepping, navigation and teaching failure-link/fix/rerun already passed in [dark](../reports/NATIVE-TOOLS-38140896349.md) and [light](../reports/FUNCTIONAL-MAC-38154975508.md) reports; do not relabel them wholly untested. |
| P3 | Exercise the actual Language dialog with a registered teaching-language object/default settings, graphical pedagogical Step controls/order/visibility, stepping output and return to definitions. | **GUI/native.** A successful `#lang htdp/bsl` test-report fixture does not establish this separate follow-on gate. |
| P3 | Close accessibility, IME, HiDPI, focus and physical keyboard/pointer coverage on the intended environment, retaining stock controls, readable output and recoverable edits. | **Desktop/manual**, supported by native captures/state. [Native acceptance scope](../retained-host/reports/NATIVE-ACCEPTANCE.md) remains broader than headless, offscreen or programmatic-control tests. |

Keep fresh processes/profiles for future paired native cases. If pristine stock
fails, diagnose or correct the fixture before comparing modern mode. Preserve
unexpected modal text/screenshots and bounded failure/cleanup evidence; do not
dismiss dialogs or weaken assertions to manufacture a pass.

Current increment stops at documentation and a **local commit**. No push,
merge, workflow activation, release build, Racket package install or large
download. Historical successes do not certify the current Cocoa package or
complete DrRacket parity.
