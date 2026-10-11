# Stock Debugger diagnostics and #lang BSL report correction

Status: immutable source-only freeze approved by the integration owner. No local Racket invocation, native execution, package operation, download, or remote call. The prior passing Macro Stepper result is not evidence for this candidate. The new headless Racket diagnostic regression is written but unrun.

## Observed run evidence

Run 38130180217, decoded locally under `openracket-recovery/results/run-38130180217`:

- `decoded/tools-pristine-stock-debugger-ready.json`: failed, blank `error`, 20 initial host checks. The host counter does not count the RackUnit checks in the tool gate.
- `images/tools-pristine-stock-debugger-failure-diagnostic.png`: stock Debugger panel open, Go and Step enabled, one stack row `??`, no completed output. Log has no `debugger-suspended` stage, so failure occurs before that emit.
- `decoded/tools-pristine-stock-teaching-tests-ready.json`: exact 20-second readiness failure for `htdp/bsl completes and exposes actual failure report`.
- `images/tools-pristine-stock-teaching-tests-failure-diagnostic.png`: actual Interactions report shows 42, two tests, one failure, actual 3 vs expected 4, and a source link at fixture.rkt line 5 column 0. This disproves the interpretation that no actual report appeared. The old harness waited for the separate test-panel editor instead.

## Debugger: exact assertion still unobserved

The strongest implicated check is old `independent-native-stock-tools.rkt:144`, `(check-eq? (send tab defs-containing-pc) defs)`. This is an inference, not recovered RackUnit payload. The old host serialized only `exn-message`; the exact failed check, source location, actual and expected values cannot be established conclusively from that erased evidence.

Authoritative cached Racket 9.3 sources:

- `gui-debugger/debug-tool.rkt:910-917`: `defs-containing-pc` resolves the first mark's syntax source via `filename->defs`; source #f instead falls back to current definitions.
- `debug-tool.rkt:928-947`: PC and frame endpoints are syntax positions, not proof that their source belongs to the open fixture.
- `debug-tool.rkt:1235-1250`: a stack row becomes `??` if its source cannot resolve or has no syntax position. The old readiness gate already requires positive PC, making an unresolved source the strongest explanation for the screenshot.
- `gui-debugger/marks.rkt:85-86`: exported `mark-source` returns the source syntax for the actual mark. The new snapshot reads this real object; it does not fabricate debug frames or modify debugger state.
- Prior run log lines 342/361/384/403 proves `exn:test:check-stack`, `check-info-name`, `check-info-value`, `pretty-info?`, `pretty-info-value` work on the pinned native RackUnit build. Existing coordinator/dispatcher negative controls already use those same APIs and rethrow the original exception.

Narrow change: host failure JSON now includes `failure_payload.exception_type` and bounded `check_info` entries, preserving name, location, expression, actual, expected and all other present fields. Racket 9.3 pretty-info wrappers are explicitly unwrapped, with their presence recorded. No predicate/assertion or fatal-exit semantics change. The actual host reports through `report-failure!`, which contains diagnostic-output exceptions and arbitrary raised values, then continues existing cleanup and exit 1 using the original failure. The standalone regression verifies exact identity across that boundary even with a closed output port and a non-exception raised token. A read-only snapshot immediately before existing source assertions emits actual top/current mark source/line/column/position/span, PC/status/endpoints, stack count, and both editor-resolution booleans. Diagnostic failure is reported separately and the unchanged source checks still run.

The complete old Debugger branch is reconstructed byte-for-byte by removing only this additive snapshot. Its SHA-256 remains `7749aca9412cd6cbfe70993fb7adae1e54dde188b6984ed893cc91a1f0f14f22`.

## Teaching tests: source-proven UI path

All paths below are relative to cached stock package roots listed in `ui-repair-source-evidence.json`.

1. `htdp-lib/lang/private/teach-module-begin.rkt:170-173` configures `htdp/bsl/runtime` and provides the test submodule.
2. `htdp-lib/htdp/bsl/runtime.rkt:157-163` sets test value rendering; it does not install the legacy separate-panel display callback.
3. `htdp-lib/test-engine/test-markup.rkt:51-59` default `display-test-results-parameter` writes markup to the current output port via `write-special` when supported.
4. In contrast, `htdp-lib/lang/htdp-langs.rkt:177-188` legacy teaching-language `on-execute` installs the separate test-display-gui callback. The gate's `#lang htdp/bsl` fixture takes the inline path, as the screenshot independently confirms.
5. `htdp-lib/test-engine/test-markup.rkt:274-277` renders `unequal` with actual then expected. Lines 193-197 interpret `~F` as framed value markup. The candidate checks flattened visible text for the translated 3-vs-4 message, plus summary and location label.
6. `gui-lib/framework/private/text-port.rkt:674-684` creates a real `srcloc-snip:snip%`, puts the label into its nested editor, then activates its link. The candidate finds this actual class in the actual Interactions snip tree.
7. `gui-lib/framework/main.rkt:36-55` exports the source-link class via signature; `framework/private/sig.rkt:26-30` declares it. `framework/private/srcloc-snip.rkt:75-93` exposes `srcloc` as an init-field, creates the nested editor and installs its original clickback over range 0 to end.
8. `framework/private/srcloc-snip.rkt:20-27` selects via `handler:edit-file`, start=position-1 and end=position+span-1. It does not populate Interactions `get-error-ranges`.
9. `framework/private/handler.rkt:97-105` locates the existing editor's frame and calls `make-visible` with that exact range. `drracket-core-lib/drracket/private/unit.rkt:3431-3438` activates the matching retained tab/editor, focuses its canvas, and sets that selection.

For the unchanged failure form, source position=78 and span=25 imply selection [77,102]. The candidate first moves the definitions selection to [0,0], invokes the installed nested-editor clickback, then requires exact retained editor/tab identity and [77,102] containing exactly `(check-expect (bump 2) 4)`. This distinguishes a real link effect from the selection already matching.

After the existing one-character unsaved correction and real Run, the candidate checks actual evaluator state 2 tests/2 successes/0 failures, visible both-tests-passed and 42, retained Interactions identity, no previous summary/detail/location label, and no source-link snips remaining. It never calls a report-renderer to fabricate UI, installs a clickback, mutates a model, or bypasses the real Run control.

## Unchanged native behavior and bounds

- Complete Macro Stepper branch SHA-256 unchanged: `0cf56eac6c88e29d530c21fa8cafacb1ece3d453e12fcab4a44545242548d83d`.
- Five coordinator/dispatcher Racket modules unchanged byte-for-byte.
- All old Debugger assertions and real Debug/Step/Go calls unchanged.
- Coordinator default wait remains 20 seconds; ordinary tool launch and evaluation identities retained.
- Same BSL failure fixture, real Run control and actual user evaluator snapshot APIs retained.
- No runtime/product source touched; no appearance-default work included.

Diagnostic limitation: each value is truncated to 2,000 characters after `format`; arbitrary custom-writer work is bounded only by the existing outer native timeout.

## Verification and next native run

Local: pinned host derivation verified; 11 stock-tool source checks, 8 dispatch-source checks, and 6 coordinator-source checks passed. Racket delimiter checks are lexical only; they are not Racket reader/expander/compiler proof.

Native integration needs the new `tests/native-tool-failure-diagnostics.rkt` helper beside the host. Mandatory preflight: compile changed Racket files, then run both diagnostic standalone modes described below. Then keep all prior coordinator/dispatcher positive/negative controls and real stock cases. Debugger is intentionally still allowed to fail at its original assertion; use its typed payload and pre-assert mark snapshot to identify the next genuinely necessary change. Test teaching failure/link/correction, and only compare modern behavior after the corresponding genuine stock gate passes.


## Mandatory diagnostic standalone CLI contract

Run using `racket` directly, not `raco test`, because deliberately caught RackUnit failures are part of this regression.

- Positive: `racket tests/native-tool-failure-diagnostics-standalone.rkt`
  - Must exit 0.
  - Must emit exactly one `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained`.
  - Must not emit either injection/failure marker.
- Negative: `racket tests/native-tool-failure-diagnostics-standalone.rkt --inject-failure`
  - Must exit nonzero.
  - Must emit exactly one `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE`.
  - Must emit exactly one `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong`.
  - Must not emit the success marker.

The negative reporter validates the actual typed payload, writes its marker, then attempts to write to a closed port. After that contained diagnostic failure, the original RackUnit exception is re-raised outside the diagnostic boundary. All positive-run assertions are outside diagnostic catches.
