# OpenRacket: retained DrRacket9.3 host proof

This is an isolated, reversible modernization experiment. It keeps the real
DrRacket GUI host, editors, canvases, callbacks, tools and evaluator. It is not a
new editor or a working replacement application, and it makes no speed/parity
claim yet.

## What is implemented

- A version-pinned patch to the actual stock `mrlib/switchable-button%` class.
  Only its paint and two font-measurement methods, four spacing constants and
  one drawing-module import change. Original event handling, callbacks, tooltips,
  right-click menus, enable/disable logic, labels, registration and ordering remain.
- A shared `racket/draw` painter: restrained light/dark palettes, consistent type,
  vector icons with stock meanings, hover/pressed/disabled states and compact
  layouts. Unknown buttons retain their supplied stock bitmaps.
- The untouched original painter remains in the same class. Launching with
  `OPENRACKET_UI=stock` restores its original paint and measurement settings.
- `artifacts/toolbar-paint-proof.png` is generated with the same drawing code the
  patch calls. It is a component proof, **not a DrRacket window screenshot**.
- A conventional theme tool under `tool/` uses supported color-scheme, font,
  gutter, output/error-style and canvas-spacing APIs. It requires the explicit
  `OPENRACKET_HOST_THEME=1` opt-in. It adds adaptive pane edges, an inset focus
  rail, and spacing on the existing status row. See its README and THEME-HOOKS report.

## Evidence so far

The source matches both the official Git v9.3 source and the exact official9.3
release-catalog gui-lib package archive. 115 headless Racket tests and 12 Python patcher tests
pass. Theme mixin tests use focused mock contracts and source inspection,
not a native DrRacket instance. The preservation test compares the entire module and allows only the
explicitly declared presentation edits; it also checks every original button
method and original painter fallback.

Native Linux CI compiled the patched GUI, actual appearance tool and complete
DrRacket entrypoint. All 14 toolbar tests passed in each of four modes; five native
canvas/status tests passed in both modern modes. The second run passed 20 complete
host-harness checks in pristine stock/fallback and 24 in modern light, including
Unicode file loading, undo/redo and two real Run callbacks. Genuine screenshots
were captured. Modern dark exposed a painter synchronization defect under repair;
performance and macOS validation remain incomplete. See
[the latest recorded run](https://github.com/alikatgh/openracket/actions/runs/38048840909)
and `reports/RESULTS.md` for exact passes and remaining gates.

Local package installation and its authorized retry were cancelled, and the
local display is unavailable. The original shared runtime and package profile,
frozen Rust core, `openracket-next`, and GPUI spike were not modified.

## Prepare and run the actual retained host

Use an official Racket 9.3 installation, and set RACKET to its executable if it
is not on PATH. The setup command downloads missing official9.3 dependencies,
creates an isolated package/preferences profile, verifies and applies the exact
paint patch, registers the appearance tool, and compiles the real modules:

    scripts/setup-openracket.sh --install
    scripts/launch-openracket.sh

If a full official distribution supplies gui-lib outside the proof profile,
setup copies that complete installed package into the private profile first.
It never patches the original distribution. An unavailable native display is
still a blocker for launch. These launch/setup paths are implemented and locally
syntax/compile-checked. Native CI compiled the real modules with a disposable
full-distribution adapter; the portable setup/launch path itself still needs an
end-to-end run.

The launcher calls the original DrRacket entry point. There is no alternate
interpreter, editor buffer, or replacement Run/Stop action. Pass file paths to
the launcher just as for DrRacket. Select OPENRACKET_THEME=light or dark to choose
an initial scheme explicitly; otherwise the existing platform mode is retained.

`scripts/launch-openracket.sh --check` reports dependencies/display without
launching GUI. `scripts/launch-stock.sh` selects the original painter/metrics
branch with separate stock-comparison preferences; both share the same complete
stock package installation. The toolbar source itself can be reverted with
`scripts/apply-overlay.rkt --revert` under the isolated addon environment.

## Run the safe local proof


Use Racket9.3 with existing racket/draw and rackunit dependencies:

    scripts/check-local.sh

Set `RACKET`/`RACO` if using another local official9.3 installation. This command
only prepares the isolated source overlay, runs headless tests and renders the
component proof. It does not download packages or launch a GUI.

Key files:

- `src/paint.rkt`: real shared painter
- `scripts/prepare-overlay.py`: exact-SHA guarded patch generator
- `artifacts/stock-toolbar-9.3.patch`: readable source diff
- `scripts/apply-overlay.rkt`: portable, hash-guarded isolated-profile apply/revert
- `scripts/apply-overlay.py`: equivalent development helper with independent integrity tests
- `scripts/setup-openracket.sh` / `launch-openracket.sh`: real retained-host setup and launch
- `tests/source-preservation.rkt`: full module/behavior preservation checks
- `tests/paint-test.rkt`: renderer state, fallback, compact and DC-state checks
- `tests/native-toolbar-test.rkt`: real-widget test, passed in native Linux CI
- `reports/NATIVE-ACCEPTANCE.md`: open dynamic and performance gates
- `performance/`: reproducible identical-instrumentation native comparison harness
- `design/WORKSPACE-DESIGN.md`: supported retained-canvas/status refinements
- `reports/native-preflight.json`: actual dependency/display availability
- `vendor/PROVENANCE.md`: exact official source and license records

Do not put only the partial `overlay/mrlib` directory on PLTCOLLECTS: it would
shadow other mrlib files. Apply the guarded patch solely inside the completed
isolated official package profile. No original/global installation is patched.

## Limits

Stock-painter mode does not undo saved theme/font preferences. Use the tool’s
Restore Previous Appearance action and reopen windows, or discard the disposable
profile, to restore those settings.

This is an initial toolbar/editor-presentation seam, not the full desired design.
Native titlebars/menus/dialogs and stock tool windows need separate visual review.
Stock host reuse preserves the architecture for rich documents, teaching tools,
debugger and macro-stepper; their dynamic parity still requires the native gate.
The extra sidebar is deliberately not implemented in this proof. Performance
must be measured on the actual application without removing instrumentation,
limits, tools or output behavior.
