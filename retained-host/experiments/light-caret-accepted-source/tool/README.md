# Retained-host appearance tool

A bounded appearance extension for the real DrRacket 9.3 frame, editor canvases,
and tools. This is **source and headless-tested work, not a native-GUI-validated
release**. The current isolated profile lacks the installed GUI dependencies;
no display is available. See `../reports/THEME-HOOKS.md` and `validation.log`.

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

With a complete suitable Racket installation:

    raco make tool/tool.rkt
    raco test tool/tests.rkt tool/frame-chrome-tests.rkt

In this workspace, use the installed 9.3 runtime and explicit isolated add-on path
shown in `validation.log` / the report. `info.rkt`, `layout.rkt`, `appearance-state.rkt`, `frame-chrome.rkt`, and the two
test modules compile; all 28 focused tests pass (13 theme/state and 15 chrome). Full `tool.rkt` compilation is blocked at
the missing `racket/gui/base` dependency, before GUI startup.

The tests cover palette validity/contrast, opt-in gating, installed-font choice,
mixin preservation contracts with test doubles, strict snapshot value validation,
preference rollback when a scheme is missing or a callback fails, and the
production margin painter's pixel bounds/DC recovery/focus behavior. They are not a substitute
for testing the real stock editor, snips, tools, or tool host on a display.
