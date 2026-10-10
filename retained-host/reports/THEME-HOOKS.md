# Retained DrRacket 9.3 appearance: implementation and verified hooks

## Result and status

Implemented the package in `tool/` using the real DrRacket extension points.
Paired light/dark editor schemes and roomier retained-host geometry are ready for
integration. **28 headless tests pass (13 theme/state and 15 chrome). Native GUI behavior is unvalidated.**

`info.rkt`, `layout.rkt`, `appearance-state.rkt`, `frame-chrome.rkt`, and both test
modules compile under the official 9.3 runtime.
Full `tool.rkt` compilation was attempted and is blocked at the missing installed
`racket/gui/base` module. Tool-source reader syntax passes, but full GUI module
expansion, instantiation, and native interaction have not passed. The runtime has
no usable display. This is an implementation candidate, not full stock-parity
certification or a screenshot of an operating DrRacket window.

No package installation was retried during theme validation. A later attempt used
a newly authorized installation, but its approval review was again cancelled.
The isolated registry and cached official archives were read only during theme validation. This work writes only `tool/` and this report.

## Exact retained architecture

- The stock `drracket:unit:frame%` remains the frame superclass.
- The stock definitions and interactions canvas classes remain the superclass
  of each small canvas mixin. Their actual editor objects are never replaced.
- No definitions/interactions text mixin is registered. Stock text, snips,
  read-only boundaries, lexer, undo, search, keymaps, language modes, evaluation,
  Check Syntax, debugger, Macro Stepper, teaching tools, and plugin discovery are
  left to the upstream host.
- The frame mixin uses `get-button-panel`, its existing `get-parent`, and public
  `spacing` / `border` setters. It neither reparents nor reorders children.
- There is no sidebar. Native active selection, menus, dialogs, and status hosts
  remain native. Additional canvas paint/focus/activation hooks always forward
  their superclass; status changes only public spacing/border geometry. The optional paint bridge only synchronizes the separate
  retained-button paint patch.

These are implementation boundaries, not a claim that all upstream behavior has
been exercised. Testing actual stock workflows remains a required acceptance
step.

## Changes

### Editor and interactions palette

`info.rkt` registers “OpenRacket Light” and “OpenRacket Dark” using
`framework:color-schemes`. Both have 27 existing named colors/styles. They cover
the canvas, ordinary text, the ten stock syntax token categories, REPL value /
output / error text, interactions header, current-line gutter, line numbers,
paren matching, contour location, disabled background, warning/error backgrounds,
and failed search.

The palettes match the toolbar paint implementation: dark canvas `#171C26`, text
`#ECF0F7`, blue `#86AEFF`; light canvas `#F7F8FA`, text `#253047`, blue `#245EDB`.
Every ordinary editor/syntax/REPL/header text color and line-number color checked
against its editor background meets 4.5:1 contrast. Error text also keeps
underline or italic differentiation. Stock tool-specific colors not listed in
the new schemes inherit upstream defaults; this avoids guessing at diagnostic
semantics or suppressing coverage distinctions.

Definitions and interactions intentionally share the background because that is
the single supported Framework canvas-background entry. The actual definitions /
interactions split and controls retain their familiar positions.

### Typography

Use `get-face-list 'mono` to choose the first installed face from JetBrains Mono,
SF Mono, Cascadia Code, Menlo, and DejaVu Sans Mono. If none exists, retain the
current stock face. No font is downloaded or installed.

The initial editor font size is 13 and smoothing is `smoothed`. Crucially, 9.3's
font-size preference is a vector of a per-monitor hash and default size, so the
implementation writes `(vector (hash) 13)`, not a legacy bare integer. Controls,
menus, and dialogs do not get their font changed by this tool.

### Geometry

- Definitions and interactions canvas inset: 12 horizontal, 10 vertical.
- Existing toolbar button panel spacing: 6.
- Existing toolbar top-panel spacing: 6; border: 8.
- Existing status-panel spacing: 10; border: 6.
- One-DIP pane edges and a two-DIP focused-editor rail, entirely inside the
  existing canvas margins. Colors derive from the current real color scheme;
  the focus cue meets at least 3:1 against its background.

These are public geometry setters on retained widgets. Toolbar order, command
callbacks, narrow-window behavior, stock split mechanics, and tool registration
are not replaced. New windows receive changed geometry. Existing windows are not
walked or reconstructed when the option changes.

### Activation, user control, and reversibility

The unit registers no mixins, preference panel, preference changes, or optional
paint bridge unless `OPENRACKET_HOST_THEME=1` and `OPENRACKET_UI` is not `stock`.
The launcher must restrict that opt-in to its isolated profile. Merely
discovering/installing this package exposes the named schemes for manual choice.

On the first opted-in stock frame, select the paired schemes, installed font,
font size, and smoothing. Keep the stock current light/dark/platform mode unless
`OPENRACKET_THEME=light` or `dark` explicitly selects one; this avoids a forced
dark editor beside light platform-native chrome.
Keep a snapshot of exactly the six changed preferences. A successful state flag
prevents subsequent launches from resetting user customization. The optional
OpenRacket Preferences panel can reapply or restore that snapshot. Restoring
disables the spacing for newly opened windows. No general reset is used.

Rollback caveat: `OPENRACKET_UI=stock` skips this tool and allows restoring
stock toolbar paint/metrics, but does not undo editor font/scheme preferences
already saved by the proof. Restore the prior appearance first while this tool
is active and reopen the windows, or use a fresh isolated profile. Uninstalling
the tool alone is not a full preference rollback. Never discard a real user's
profile as a workaround.

Scheme activation is deliberately delayed until stock frame construction:
DrRacket loads tool phases before registering info-based schemes. Framework
silently falls back to Classic for an unknown scheme, so the tool verifies both
selected names, rolls back on failure, and logs a nonfatal warning. Missing info
metadata therefore does not silently count as successful initialization.

### Optional painter bridge

If the bundled `mrlib/private/openracket-paint` module exists, call its
`set-modern-host-theme!` and `set-modern-role-labels!` exports. Follow Framework's
canvas-color change callback to synchronize dark/light mode. Do not intercept
preference events or button events.

Role names come from the actual `string-constants` bindings: `check-syntax`,
`debug-tool-button-name`, `macro-stepper`, `execute-button-label`,
`break-button-label`, and `break-button-kill-label`. Both Stop and Kill use the
stop artwork role. A missing optional painter module is harmless; the tool is
standalone.

## Authoritative 9.3 source findings

Read directly from the already-downloaded official release archives:

- `gui-lib`: cache `cached17916276841791627684251`, release catalog checksum
  `31187c9593c5eaabcb1850c0120408d7d9734496`.
- `drracket-core-lib`: cache `cached17916276701791627670591`, release checksum
  `d55515fcc1d1da846555ea0b5c1b593c4af619ef`.
- `drracket-plugin-lib`: cache `cached17916276731791627673914`, release checksum
  `536a7093639c0eabc33bfb77be13a9b2a0d2ad0f`; this package provides `drracket/tool`
  and is a direct dependency in the theme package.

Verified hooks and sequencing:

1. `framework/private/main.rkt:312,325–377,578–608` registers the background,
   font shape/callbacks, contour, gutter, default-text, and warning/search colors.
2. `framework/private/racket.rkt:298–351` defines the ten syntax-token categories
   and derives their `framework:syntax-color:scheme:*` keys.
3. `framework/private/canvas.rkt:25–33` applies the named background to the real
   canvas and keeps it synchronized via a weak color-scheme callback.
4. `framework/private/text-line-numbers.rkt:213–241` uses the registered line
   number/current-line foreground/background colors in the existing gutter.
5. `mred/private/mrcanvas.rkt:291,400–413` provides the public canvas inset
   constructor arguments and getter/setters used by the mixin.
6. `drracket/private/main.rkt:548–561` loads tool phases then freezes extension;
   `:676–717` adds the interactions/REPL/error colors; `:911` registers schemes;
   `:923` begins ordinary stock frame creation.
7. `drracket/tool-lib.rkt:1299–1316,1400–1426` specifies the public frame and
   canvas extension contracts.
8. `drracket/private/unit.rkt:5066–5071,5139–5145` constructs the unchanged top
   panel/button panel and exposes `get-button-panel`.
9. `framework/private/color-prefs.rkt:1056–1068` demonstrates unknown-scheme
   fallback and the separate light/dark preference slots.

Primary documentation:

- [DrRacket color schemes](https://docs.racket-lang.org/drracket/color-scheme.html)
- [Framework color preferences](https://docs.racket-lang.org/framework/Color_Prefs.html)
- [DrRacket plugin API](https://docs.racket-lang.org/tools/index.html)
- [Editor canvas](https://docs.racket-lang.org/gui/editor-canvas_.html)

Selection is deliberately retained: upstream `mred/private/wxme/text.rkt:90–91`
gets its selection/highlight brush from the platform's
`get-highlight-background-color`; the supported framework color-scheme mechanism
does not expose a selected-text palette override. Painting a fake selection would
risk native selection semantics, accessibility, and editor behavior. Native
status/chrome likewise has no general CSS-style theme surface, so this tool does
not claim that all platform chrome becomes the custom palette.

## Validation performed

Command prefix used to resolve the isolated installed packages without writing
their registry:

    /workspace/shared/racket-toolchain/racket/bin/racket \
      -A /workspace/shared/openracket-drracket-host/profile/.local/share/racket \
      -l raco --

Passed `make` on all six GUI-free implementation/metadata/test modules.
Passed `test --direct tool/tests.rkt tool/frame-chrome-tests.rkt`: **28 tests**.
The 13 tests in `tool/tests.rkt` cover:

1. Explicit profile-mutation opt-in, including stock bypass.
2. Paired scheme metadata and valid unique RGB/RGBA entries.
3. Normal/syntax/REPL/gutter text contrast.
4. Installed font choice and fallback.
5. Canvas superclass/editor identity, events, method set, and insets (test double).
6. Disabled canvas keeps stock insets (test double).
7. Frame superclass, lifecycle, toolbar identity/parent and callbacks (test double).
8. Disabled frame keeps stock toolbar geometry (test double).
9. GUI module reader syntax.
10. Snapshot validation for all six preference value types.
11. Missing-scheme rollback preserves exact saved names and refreshes the proper
    effective light/dark fallbacks.
12. Rollback continues with remaining settings after a preference callback fails.
13. Initial appearance preserves the stock mode unless explicitly selected.

The 15 tests in `tool/frame-chrome-tests.rkt` cover real off-screen pixel bounds,
focus contrast on 225 custom backgrounds, DC preservation/recovery, small-view
opt-out, forwarded stock paint/focus/activation hooks, active/inactive/disabled
state, preserved editor identity, and unchanged status-row parent/children/order.
Canvas/frame behavior is tested with test doubles; this is not real GUI execution.

For multi-file tests under an explicit `-A` add-on path, use `--direct`; Racket
otherwise starts child processes that do not inherit that command-line path.
The first default multi-file invocation failed with an unknown test-driver
submodule because of that runner environment, not a test assertion. Both the
corrected direct invocation and inherited isolated XDG environment pass.

Full `make tool/tool.rkt` returned exit 1: missing `racket/gui/base` at the runtime
collection path. Complete output is in `tool/validation.log`. No dependency
download, registry update, display workaround, native launch, or native screenshot
was attempted during these checks.

## Resumed audit fixes and upstream smoke support

The source audit identified and fixed a real rollback edge case. Calling
`color-prefs:set-current-color-scheme` with an old scheme name that is temporarily
absent always chooses Classic and changes the light preference. The new
GUI-free `appearance-state.rkt` first restores the six saved values, asks the
Framework getter for each effective light/dark scheme, refreshes those known
schemes, and finally reasserts the exact two saved identifiers. Absent custom
scheme identifiers therefore survive until their packages reappear.

Snapshots now validate the actual six preference value types, including the
per-monitor font-size hash/vector. Rollback attempts remaining preferences after
a callback exception and reports its first failure. Applying appearance also
restores the prior snapshot/enabled/state bookkeeping if a late operation fails.
The explicit Restore button catches failure and does not falsely mark the
appearance as restored. These source changes have headless regression coverage;
real Framework callbacks still require the pending native checks.

Two real upstream test facilities were inspected in the official 9.3 gui-lib:

- `racket/gui/private/distro-test.rkt` runs `gracket-text -e 'hello` and explicitly
  skips graphical GRacket on Unix. It is a lightweight distribution smoke test,
  not editor/DrRacket parity validation. It was not run here because the
  installation remained incomplete.
- `framework/test.rkt` requires `racket/gui/base` and drives real GUI eventspaces,
  focus, shown windows, controls, keyboard and mouse events. It cannot serve as a
  display-free native test. It was inspected only; no GUI was launched.

Full tool compilation is being handed to the separately authorized full-9.3 CI
route. Local package or display work is frozen. No cache-based installation or
substitute GUI runtime was used after the cancellation.

## Remaining acceptance work

With an authorized complete 9.3 installation and a permitted working GUI:
compile and load the package; verify both real editor classes and tool host;
inspect light/dark appearance at normal and high DPI; exercise keyboard focus,
native selection, IME, snips/images, undo, language changes, repeated Run / Stop /
Kill, Check Syntax, Debug, Macro Stepper, teaching languages, tabs, multiple
windows, split resizing, error/test panes, built-in font/color preference changes,
restore/reapply, and third-party toolbar additions. Compare against stock in the
same environment. Verify missing optional paint module and missing scheme setup
fail safely. Strict stock parity must not be declared before those checks pass.
