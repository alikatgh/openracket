# Retained-host appearance tool

A bounded appearance extension for the real DrRacket 9.3 frame, editor canvases,
and tools. This directory includes **source and historical headless validation,
which do not establish a native-GUI-validated release**. The original isolated
profile lacked the installed GUI dependencies and a display. See
`../reports/THEME-HOOKS.md` and `validation.log` for that validation history.

The separate polish candidate additionally includes an opt-in app-native
appearance prototype. See [native capability, restoration and verification
limits](NATIVE-APPEARANCE.md). Cocoa is the primary candidate; GTK is experimental
and remains disabled in tool integration. Native execution of this addition is
not yet validated.

## Scope

- Paired OpenRacket Light / OpenRacket Dark schemes, registered through the stock
  `info.rkt` scheme mechanism and selectable in standard Colors preferences.
- Matching definitions/interactions backgrounds, syntax, REPL, and gutter colors.
- An installed monospaced face, 13-point editor text, and font smoothing.
- Modest editor canvas insets and spacing around the retained toolbar controls.
- Quiet pane edges, a focused-editor rail within canvas margins, and stock status-row spacing.
- A Preferences panel to reapply or restore the saved appearance.
- An optional bridge to `mrlib/private/openracket-paint` for theme and localized
  toolbar role labels. Standalone use does not require that patched module.

There are no new editors, evaluators, document buffers, tool buttons, keymaps,
sidebars, or replacement command handlers. The new paint/focus/activation hooks
forward stock methods; native selection and native menus/dialogs/status controls
retain their existing implementations.

## Explicit activation

Discovery of the package alone does not restyle a profile. The tool unit is
inert unless `OPENRACKET_HOST_THEME=1` is set and `OPENRACKET_UI` is not `stock`.
Use that opt-in **only with the isolated proof profile**. First use retains the
stock light/dark/platform preference; `OPENRACKET_THEME=light` or `dark` explicitly
selects a mode. Following the native mode by default keeps stock platform chrome
and the editor appearance cohesive.
Later user changes in the stock Fonts and Colors preference panels are preserved.
The package must already be installed and its info-domain metadata registered by
an authorized local package setup. No setup or dependency installation is
performed by this tool. Do not retry the currently blocked package installation
as part of running the headless checks.

The settings snapshot covers only the six settings this tool changes. Restore
does not clear or touch unrelated DrRacket preferences. Geometry changes take
effect for new windows/canvases; close and reopen a window to undo that spacing.
`OPENRACKET_UI=stock` suppresses this tool's registration and presentation hooks;
it does not erase preferences previously chosen in the proof profile.
For full rollback, use **Restore previous appearance** while the opted-in tool is
still active, then reopen windows; alternatively start with a fresh isolated
profile. Uninstalling the package alone does not restore saved editor font/scheme
preferences. Do not discard or reset a real user profile.

## Headless checks

Run these commands from the repository root. Check the available runtime first;
the historical `/workspace/shared/...` paths in the report are not a current
local toolchain configuration.

### Python-only regression checks

The evidence transport tests use Python's standard library and synthetic local
fixtures. They do not start an application, CI job, or Racket process:

    python3 -B retained-host/scripts/ci/test-replay-evidence.py

This suite checks bounded, lossless evidence reconstruction, hashes, chunk
ordering, and missing/duplicate document payload rejection. A valid JSON `null`
payload is distinct from a missing payload. `-B` avoids bytecode cache output;
temporary fixtures are cleaned by the tests. These are transport checks, not
appearance or native acceptance tests.

### Racket checks with existing dependencies

| Test module under `retained-host/tool/` | Existing requirements and boundary |
| --- | --- |
| `tests.rkt` | Racket, RackUnit and `setup/getinfo`; theme/state contracts and canvas/frame doubles. Reads `tool.rkt` as syntax without loading its GUI imports. |
| `frame-chrome-tests.rkt` | Racket, RackUnit and `racket/draw`; off-screen pixel bounds, drawing-context recovery, focus and status-row doubles. No display or `racket/gui/base` is needed. |
| `native-appearance-tests.rkt` | Racket, RackUnit and `racket/gui/dynamic`; injectable controller/policy contracts. Verifies that the platform factory leaves the GUI unstarted. |
| `native-appearance-native-tests.rkt` | **Exclude from headless execution.** Its program entry point dynamically loads `racket/gui/base` and shows native windows. |

If `racket` and `raco` are already available with the listed libraries:

    raco test --direct retained-host/tool/tests.rkt \
      retained-host/tool/frame-chrome-tests.rkt \
      retained-host/tool/native-appearance-tests.rkt

With an explicitly configured `racket -A ... -l raco --` invocation, retain
`test --direct`: child test processes otherwise do not inherit that add-on path.
If the runtime or a required library is absent, record these checks as blocked
and continue with the Python-only checks. Do not install packages or attempt
full `tool.rkt` compilation as part of headless validation; that GUI entry point
requires `racket/gui/base`.

`validation.log` preserves the original freeze result of 28 passing tests
(13 theme/state and 15 chrome) and the separate missing-GUI compilation failure.
Later source adds tests, including native-controller contracts; the preserved
counts are historical evidence, not a fresh result for the current checkout.
The Racket doubles and off-screen drawing checks do not establish behavior of
the real stock editor, snips, tools, or tool host on a display.
