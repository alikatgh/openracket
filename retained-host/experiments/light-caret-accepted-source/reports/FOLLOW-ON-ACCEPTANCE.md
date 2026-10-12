# Follow-on native preservation gates

Status: 2026-10-10, third CI source candidate. Excluded from the second run;
now integrated as tests/independent-native-workflows.rkt through the real-host
harness optional OPENRACKET_NATIVE_CASE. Reader checked locally; not yet
GUI-expanded or executed. Each case
must run with a genuine registered DrRacket frame on its eventspace handler thread,
in a fresh disposable profile/process, unchanged between stock and modern modes.
Keep all stock tool registration, evaluation settings and resource limits. On any
unexpected modal, preserve its title/text and a screenshot; do not dismiss it to pass.

## Priority 1: paths directly exposed to the appearance changes

- **Stop / Kill state and labels.** Invoke the real Run widget on a program that
  prints a marker then sleeps. Invoke `frame.get-break-button.command`, observe
  `tab.does-break-kill?` and localized Kill label immediately, then await normal
  interruption cleanup with Run enabled. Candidate `stop` tests the first Stop
  transition without causing the separate stock forced-kill dialog. Actual second
  Kill, its confirmation/notification dialog, and recovery remain separate gates.
  Source: `drracket/private/unit.rkt:1349–1377, 5144–5156, 5230–5238`.
- **Input box and EOF.** Run `read-line`; discover the actual nested input editor by
  `interactions.get-box-input-text%`, send Unicode plus Return through its key event
  route, and assert the program receives it. On the second blocked read, invoke
  `send-eof-to-box-in-port` and assert `eof-object?` in real evaluator output. This
  exercises port semantics and retained rich editor/input state. Physical pointer
  hit-testing of the EOF snip is not covered by the candidate.
  Source: `framework/private/text-port.rkt:285–290, 441–500, 1128–1160`;
  `drracket/private/rep.rkt:1052–1123`.
- **WXME rich documents.** Insert a real image snip and nested editor snip into the
  retained definitions editor, save in standard WXME form to a generated file,
  reopen through `frame.change-to-file`, compare exact image bytes/nested Unicode,
  then focus/activate/repaint the original canvas and verify snip object identities
  and selection remain unchanged. This directly checks the new paint/focus hooks.
  Candidate `wxme`. Native drag/drop, arbitrary plugin snip classes, clipboard and
  OS accessibility are still distinct gates.
- **Check Syntax.** After a real Run establishes module language, invoke
  `frame.syncheck:get-button.command`; await a nonempty actual
  `definitions.syncheck:get-bindings-table`, no error report, unchanged source,
  then compare that table and selection across focus/activation/repaint. The table
  is an upstream automated-test seam, not a fabricated parser. Candidate
  `check-syntax` emits sorted numeric binding endpoints for paired comparison and
  requires the known `bump` and `x` definition/use edges in its exact fixture.
  Source: `drracket/private/syncheck/gui.rkt:498–532, 2630–2636, 2657–2688, 2852–2861`.

`tests/independent-native-workflows.rkt` exports `run-follow-on-check!` for these four
cases. An assertion raises and must produce a failing job; it is not a no-throw
smoke test. The caller owns bounded diagnostics and final process cleanup.

## Priority 2: actual tool lifecycle and secondary windows

- **Debugger.** Public frame getters provide `get-debug-button`, `get-step-button`,
  `get-resume-button`, pause/over/out controls. The active tab exposes `debug?`,
  `get-break-status`, `get-stack-frames`, and `get-pc`. A finite pure fixture should
  enter through the actual Debug widget, stop at an instrumented expression,
  verify stack/source-position plus enabled-state, step once to a different source
  state, then resume to expected output. Retain original editor objects and check
  debugger gutter/selection pixels around the new margin rail. Capture controls
  before/after. The local-member-name debug callback itself should not be bypassed.
  Source: `gui-debugger/debug-tool.rkt:853–946, 1020–1107, 1188–1204, 1535–1540`.
- **Macro Stepper.** `frame.run-macro-stepper` is a real public-final tool method.
  On a known `define-syntax-rule` fixture, identify a newly shown registered
  macro-stepper frame, obtain `get-widget`, and await nonempty browser text via
  `widget.get-view.get-text`. The public `navigate-to-start`, `navigate-next`,
  `navigate-to-end` and `navigate-previous` update real stepper derivation state.
  Compare start/end text, successful previous navigation, unchanged definitions,
  and obsolete-session warning after an early definition edit. Close only that
  newly created tool frame, then Run again to verify original frame recovery.
  Source: `macro-debugger/tool.rkt:193–230`; `macro-debugger/view/frame.rkt:68–95`;
  `macro-debugger/view/stepper.rkt:137–141, 310–324, 353–380`.
  Do not treat the presence of a second window as proof that macro stepping works.

## Priority 3: teaching languages and cross-workflow recovery

- **Teaching runtime.** A generated `#lang htdp/bsl` module with a simple definition,
  expression and `check-expect` can exercise the real teaching reader/evaluator,
  output, and stock test-engine pane in both modes. A deliberately failing
  `check-expect` must produce the same failure count/location; fix and rerun must
  clear the old failure. This does not substitute for choosing a teaching language
  through the actual Language dialog or using the graphical Step tool.
- **Language picker / Step tool.** Verify stock menu/dialog control identities and
  select a specific registered teaching-language object with its real default
  settings, then compare Step button registration/visibility/order, actual stepping
  output, and return to definitions. `drracket:language-configuration` exports
  registered language settings through the official tool API; use the real
  Language dialog if the automation cannot establish the exact object. Do not
  reconstruct metadata or mutate undocumented preferences to manufacture a pass.
  Sources: `stepper/stepper-tool.rkt`, `test-engine/test-tool.rkt`,
  `drracket/tool-lib.rkt` language-configuration exports.

## Interpretation

Run the same checks in pristine stock first. If a check fails there, repair or
narrow the test before attributing it to the appearance overlay. Use separate
fresh processes to contain modal/tool state. Preserve actual source text, tool
output, labels and screenshots on failure. These gates expand concrete coverage;
none alone certifies all stock DrRacket functionality or physical input latency.
