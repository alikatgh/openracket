# OpenRacket retained workspace refinement

## Implemented scope

This refinement uses the real stock DrRacket editor canvases and Framework status
row. It adds scheme-adaptive pane edges, a clear keyboard-focus cue in unused
canvas margin, and calmer status spacing. It is integrated through class mixins,
not an alternative editor, a screenshot overlay, or a replica of native controls.

`tool/frame-chrome.rkt` is production code. `tool/frame-chrome-tests.rkt` tests the
same painter and mixins without loading a GUI. Fifteen headless tests pass under
the official Racket 9.3 runtime. Native host verification is a separate gate.

## Composition and hierarchy

The stock filename/path and definition selector remain at the left. The original
conditional Save button and registered tools retain their stock positions and
ordering; Check Syntax, Debug, Macro Stepper, Run and Stop remain familiar.

Definitions stays above Interactions unless the user selects the stock horizontal
layout. The original draggable divider, orientation, hide/show commands, pane
splits and split proportions are not altered. Native tabs, their labels, unsaved
markers, close/reorder actions, and keyboard navigation remain stock. No sidebar
is added.

The existing theme package chooses an installed monospaced face, keeps Fonts and
Colors preferences available, and applies 12 DIP horizontal / 10 DIP vertical
editor insets. The new visual hierarchy is deliberately quiet:

| Surface | Treatment | Implementation |
| --- | --- | --- |
| Definitions and Interactions | A one-DIP perimeter, derived from the active editor palette | Canvas margin painter after stock editor paint |
| Keyboard-focused editor | Two-DIP accent rail at x=2, from y=vertical-inset to the symmetric bottom inset | `has-focus?`, `is-enabled?`, and forwarded window-activation callbacks |
| Inactive editor/window | Quiet perimeter only | Original native caret and selection behavior retained |
| Stock information row | Border 6 DIP; inter-child spacing 10 DIP | Public `get-info-panel`, `border`, and `spacing` |
| Tabs, menus and native status widgets | Native OS presentation and native control fonts | No replacements, patches, or child-tree traversal |

The perimeter is decorative rather than a focus indication. Its RGB components
are 82% current canvas background plus 18% current default text. This follows
custom color schemes instead of assuming a particular light/dark background.

The active rail uses #86AEFF on dark backgrounds and #245EDB on light backgrounds
when that meets 3:1 contrast. Otherwise it uses the user's default text color if
that meets 3:1, then falls back to black or white. The focus cue is supplemental;
native selection colors, selected text, caret, accessibility and input methods
are untouched.

The whole painted region is outside editor content. When the horizontal inset is
less than 5 DIP, vertical inset less than 2 DIP, or the viewport is too small,
the painter does nothing. No scrollbar is overpainted: dimensions are taken from
the canvas client area.

## Exact integration

The host theme module owns opt-in, saved appearance preferences, color schemes,
stock font settings and its existing spacing mixins. It should additionally:

1. Require `frame-chrome.rkt`.
2. Define a palette thunk using these existing, color-valued entries:

   ```racket
   (define (workspace-palette)
     (make-chrome-palette
       (color-prefs:lookup-in-color-scheme 'framework:basic-canvas-background)
       (color-prefs:lookup-in-color-scheme 'framework:default-text-color)))
   ```

3. Register `(make-editor-chrome-mixin layout-enabled? workspace-palette)` through
   both `drracket:get/extend:extend-definitions-canvas` and
   `drracket:get/extend:extend-interactions-canvas`, in addition to the current
   spacing mixins. Either composition order is supported: chrome queries actual
   insets on each paint rather than replacing them.
4. Register `(make-status-chrome-mixin layout-enabled?)` through
   `drracket:get/extend:extend-unit-frame`, in addition to the current initialization
   and toolbar-spacing mixin. The status row is accessed only after `super-new`.
5. Keep registration inside the existing explicit isolated-profile opt-in.
6. Include `tool/frame-chrome-tests.rkt` in headless checks and
   `design/native-chrome-test.rkt` in the authorized native CI checks.

The canvas mixin forwards `on-paint`, `on-focus`, and
`on-superwindow-activate` to the exact superclass once, before its cosmetic work,
and preserves the return value. It adds no public method. Mouse/keyboard event
methods are inherited without interception. The painter restores every DC setting
it changes, including on exceptions, and never changes transform or clipping.

Turning off the existing appearance option stops additional canvas painting on
the next native refresh. Stock painting clears the margin. Like the existing
toolbar/canvas spacing, status geometry is set at construction, so reopen windows
to restore old geometry. `OPENRACKET_UI=stock` bypasses all theme registration.

## Why tabs and native panel colors are not replaced

The 9.3 DrRacket frame constructs its tab panel internally; the public tool frame
contract has no tab-class replacement hook. Racket GUI documents an optional
portable tab implementation, but changing to it can change which platform
features are available. It is not a harmless recoloring switch. This refinement
does not force `PLT_FLAT_PORTABLE_TAB_PANEL`, reparent tabs, draw an imitation
tab strip, or intercept tab callbacks.

The public native-panel API provides layout setters, not a general background or
CSS theme setter. We therefore preserve native chrome. Following the platform's
light/dark preference by default avoids a dark workspace beside light native
tabs/status widgets. Explicit light/dark selection can still use the installed
schemes. Cross-platform native chrome restyling requires a separately reviewed
presentation patch and native acceptance; it is not claimed here.

## Tests and remaining native checks

Headless tests cover:

- Both shipped accents and adaptive focus contrast on 225 custom RGB backgrounds
- Exact editor-interior pixel preservation for both palettes and focus states
- Exact rail location and small-viewport fallback
- DC state, transform and clipping preservation, including an injected failure
- Retained editor identity, untouched event dispatch, exact callback forwarding
- Disabled/native-inactive focus states and live paint opt-out
- Retained status parent, child identities/order, visibility and command methods

Run from the project root:

```sh
/workspace/shared/racket-toolchain/racket/bin/racket \
  -A profile/.local/share/racket -l raco -- test tool/frame-chrome-tests.rkt
```

`design/native-chrome-test.rkt` is an unrun native test candidate for the real
`canvas:color%`, `editor-canvas%`, `text%` and `frame:info%` classes. It checks class
compatibility, real painting/focus, text/selection preservation, native key input,
status hide/show and live opt-out. It does not certify full DrRacket behavior.

The authorized full-host native run must additionally inspect both color modes,
stock/custom editor fonts, keyboard focus switching, selecting text, IME, scroll
and incremental redraw, editor splitting/hiding, window activation, HiDPI,
dragging the Definitions/Interactions divider, tabs, status-row overflow and
stock restore. Full debugger, macro stepper, teaching-language, rich-snip and
runtime acceptance remain in the shared stock-parity matrix.

## Source evidence

Inspected the cached official Racket 9.3 release archives already present in the
isolated profile; no package install, native display or network access was used
for this refinement.

- `gui-doc/scribblings/gui/editor-canvas-class.scrbl:247–267`: `on-focus` caret
  behavior; overridable `on-paint` and automatic margin clearing.
- `gui-doc/scribblings/gui/window-intf.scrbl`: focus, activation and client-window
  methods used by the mixin.
- `gui-lib/framework/private/canvas.rkt:25–33,58–67`: actual Framework canvas
  background and forwarded focus/info integration.
- `gui-lib/framework/private/frame.rkt:765–878`: original information-row
  construction and public `get-info-panel`.
- `drracket-core-lib/drracket/private/unit.rkt:5066–5145`: retained toolbar,
  internal tabs, editor canvases and original `get-button-panel`.
- `gui-doc/scribblings/gui/tab-panel-class.scrbl:58–78`: supported portable-tab
  behavior and differences.

Primary docs: [editor canvas](https://docs.racket-lang.org/gui/editor-canvas_.html),
[window methods](https://docs.racket-lang.org/gui/window___.html),
[tab panel](https://docs.racket-lang.org/gui/tab-panel_.html),
[Framework frames](https://docs.racket-lang.org/framework/Frame.html).
