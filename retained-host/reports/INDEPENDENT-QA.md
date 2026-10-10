# Independent retained-host audit

Date: 2026-10-10. Scope: local source/headless audit and authorized native CI review.
This report does not certify full DrRacket parity, complete rendering coverage, or performance.
No denied local display operation was retried. No package installation was performed
by this audit. All adverse patcher inputs were tested in temporary copies.

## Findings and disposition

1. **Exact-source provenance gap, fixed.** The Python generator originally hashed
   UTF-8 text after universal-newline decoding, accepting CRLF-transformed bytes
   against the purported exact-byte upstream SHA. It now verifies raw bytes.
2. **Apply/revert integrity gap, fixed.** The Python applier originally verified only
   the destination and would install a modified overlay or a modified vendor source
   on revert. It now verifies original, patched, and painter input digests before
   mutation. The added Racket applier verifies the same raw-byte inputs.
3. **Python profile-root symlink gap, fixed.** Resolving the profile
   root before defining the allowed boundary let a root symlink redefine that
   boundary. The independent temporary-directory regression reproduced this and now
   passes after a root-symlink refusal was added. The Python writer now atomically
   installs the helper before the patched source. The Racket applier also rejects
   the profile symlink and any target symlink ancestor.
4. **Missing-scheme rollback regression, fixed.** Calling Framework's color-scheme
   setter with a saved but temporarily absent custom scheme rewrote the light
   preference to Classic. Stock 9.3 intentionally retains unavailable saved scheme
   identifiers. The appearance helper now refreshes effective fallback schemes,
   then reinstates the exact saved identifiers.
5. **Partial transaction rollback, fixed.** Apply now also restores its saved-snapshot,
   enabled, and state bookkeeping if a late preference write fails. Independent tests
   inject failures before and after all nine writes. Restore attempts remaining
   operations despite a third-party callback exception and reports failure.
6. **Compatibility caveats still open.** Toolbar role replacement identifies known
   roles by localized label, so a third-party button reusing an exact stock label may
   receive stock-role vector artwork instead of its own bitmap. Other labels retain
   supplied primary/alternate pixels. The toolbar uses a fixed 13-pixel control font;
   system large-text/font/DPI compatibility is not yet proven. These are native and
   extension acceptance items, not evidence of complete parity.

## Independently executed checks

- `tests/independent-appearance-test.rkt`: 22 passing headless tests. These execute
  the actual transaction function datums from `tool/tool.rkt` against a controlled
  in-memory preference store with the documented stock fallback semantics. Cases
  cover success, all before/after-write failure points, reapply preserving the initial
  snapshot, absent registered schemes, and exact missing-scheme rollback.
- `tests/independent-paint-test.rkt`: 8 passing headless tests using real bitmap DCs.
  Pixel checks prove primary/alternate fallback, unknown localized labels, exact
  localized role matching and disabled dimming. State checks include origin/scale/
  rotation, clipping, text mode, backgrounds, alpha, smoothing, pen, brush, font and
  text foreground, including an exception within the actual painter. Unicode text
  measurement and drawing complete with the selected font.
- `tests/independent-patcher-test.py`: 9 temporary-copy tests, including exact apply /
  revert, altered upstream/overlay/painter/vendor, unrelated destination refusal,
  missing target, target-symlink escape and profile-root symlink refusal. All 9 pass.
- Both independent native harnesses passed reader syntax checks locally. Native
  compilation, scoped widget checks, and all four full-host modes subsequently
  passed on Linux CI. Separate follow-on workflow validation remains incomplete.

The first painter run emitted Fontconfig cache-writability warnings while its eight
assertions passed. The initial isolated-cache run passed all 30 then-existing independent Racket
tests without those warnings; nine later bridge regressions also pass. This is not a native font-availability or DPI verdict.

## Native checks prepared for authorized CI

`tests/independent-native-toolbar.rkt` runs eight cases against the real installed
`mrlib/switchable-button%`, unchanged between pristine stock, patched-stock, and modern:
repeated activation, leave/cancel/reenter, disable while pressed, programmatic command,
parent hide/deactivate, mutable Unicode labels/alternate-image widths, and real DC
restoration. Stock's unconditional programmatic `command` semantics are deliberately
preserved, as is its existing font-setting behavior. Right-click modal menus and
500 ms tooltip lifecycle are not claimed tested by this harness.

`tests/independent-native-host.rkt` launches the normal `drracket/drracket` entry point
with a small synthetic UTF-8 file. It waits for the genuine shown registered frame,
verifies native registered editor/canvas identity, menu and tab presence, toolbar
parentage, original file contents, undo/redo, and two actual Run callbacks producing
42. Modern mode additionally checks applied state, both color schemes, selected light
or dark mode, painter synchronization and retained canvas insets. It emits a JSON
result and `OPENRACKET_NATIVE_READY`, then waits at most 20 seconds for the CI
screenshot-completion file before hiding only its own created frame and exiting.

CI must use fresh preferences for each mode and the same official 9.3 runtime.
The harness does not change evaluation instrumentation, memory limits, tool discovery,
or language implementation. First native compile/widget results and the host harness
repair are recorded below. The revised host integration workflows still require a
native rerun. The separate performance owner maintains paired performance
fixtures and instrumentation, with no timing claim in this report.

## Authoritative sources inspected

- Exact vendored official 9.3 `mrlib/switchable-button.rkt` and its preserved methods.
- Official cached 9.3 `framework/private/color-prefs.rkt`, especially current-scheme
  fallback and setter behavior; `framework/private/main.rkt` preference contracts.
- Official cached 9.3 `drracket/private/main.rkt` startup ordering and low-priority
  first-frame callback; `drracket/private/unit.rkt` native toolbar construction,
  frame/editor getters and evaluator callbacks; `drracket/tool-lib.rkt` registered
  class getters; `mred/private/mrwindow.rkt` native geometry APIs.

## Remaining acceptance scope

Remaining full-host integration execution and exact screenshots in both themes; larger system
fonts and DPI; IME/accessibility; tooltip and right-click modal lifecycle; Stop/Kill,
Check Syntax, Debug, Macro Stepper, teaching languages, snips and rich documents;
multiple windows/tabs and third-party plugins; built-in preferences restore/reapply;
paired stock-versus-overlay native responsiveness and memory measurement. Source
preservation is valuable evidence but does not substitute for these workflows.

## First authorized native CI result and harness repair

Run 38047260644, frozen commit e859f18a489761cdc3f1263cb51bbc0f9d306780:
Linux compiled the actual GUI, theme tool and DrRacket entry point. All 14 combined
native toolbar tests passed in pristine stock, patched-stock, modern light and
modern dark. All 5 native canvas/status tests passed in both modern modes. These
results came from the official full 9.3 runtime on the authorized public runner.

The full-host harness failed after its first seven class/identity assertions in
all four modes, including pristine stock, at exact fixture-content comparison.
The first harness did not print actual editor contents, so those bytes cannot be
recovered from this run. Source review identified a test-startup scope error:
stock `private/main.rkt` reads command-line arguments in a later queued first-frame
callback, after the harness's temporary parameterization had ended. The same
pattern exposed the performance harness's benchmark arguments to stock's file-open
callback, producing a missing-file dialog and no usable latency measurements.

The revised host harness uses ordinary blank startup followed by the public
`frame.change-to-file` route. It logs initial/opened filenames and bounded editor
text, checks the exact target filename, and retains the strict Unicode comparison.
Failures now publish bounded window labels/editor excerpts and geometry before
cleanup, with a screenshot-capture window explicitly marked as failure diagnostics.
This is a harness-only repair; production toolbar/theme behavior was not changed.
At this first-run stage, native confirmation was still required for file-open,
undo/redo, Run, theme activation and screenshots; later results are recorded below. No full parity or performance claim follows from the first run.

## Second native CI result and theme callback defect

Run 38048840909, commit 720699694999cbf3cf97d864666b2e48c64aadc4:
Linux pristine-stock and stock-fallback full-host checks passed (20 each), including
exact UTF-8 file opening, undo/redo, and two real Run cycles returning 42. Modern
light passed 24 checks, including actual appearance activation. Native OS screenshots
were captured. The repaired harness logged that ordinary startup initially had an
empty untitled editor, then public file-open loaded the exact 154-character fixture.

Modern dark failed the strict painter-synchronization assertion after the correct
mode preference and both selected schemes had passed. The failure screenshot shows
a dark editor and light toolbar buttons. Independent source review identified a
production callback-ordering defect: `framework/preferences.rkt` invokes preference
callbacks before writing the new value. The bridge reread that old mode during a
new dark background callback, leaving its painter light after commit.

The owner repaired this with a coalesced queued synchronization that rereads committed
mode, explicit synchronization after apply/restore, and weakly tracked retained
button repainting. Independent source-extraction tests now include nine bridge cases:
both initial modes; before-commit transitions; repeated and rapid toggles; equal
background custom schemes; explicit transaction synchronization; absent optional
painter; and repaint request. All 39 independent headless Racket tests pass after
the repair (22 transaction, 8 pixel/state, 9 bridge). The host harness now logs exact
mode/schemes/background/painter state and checks a real opposite-mode-and-back
preference round trip, using event-loop fences but no test-side forced repaint.
The third Linux run below subsequently confirmed this production fix.

Four scoped follow-on cases are integrated behind optional `OPENRACKET_NATIVE_CASE`:
`stop`, `input-eof`, `wxme`, and `check-syntax`. Each must run in a separate fresh
process/profile in pristine stock and modern dark. They retain the same failure
window/text/screenshot contract. The Check Syntax case requires exact `bump` and `x`
local binding edges and emits normalized numeric endpoints for paired comparison.
These candidate workflows have source/reader review only, not a native pass yet.

The Linux screenshots also show missing Japanese glyphs in both pristine stock and
the modern failure capture. UTF-8 buffer equality passed; font glyph availability
is a separate environment/visual acceptance item and is not claimed fixed by this
appearance change.

## Third Linux CI: theme repair confirmed, Stop harness corrected

Run 38049557901, commit c3d12f3313a95f25162a1503be624f3b0617f8c0:
all four genuine host modes passed. Pristine stock and stock-fallback each passed
20 checks; modern light and dark each passed 28, including real opposite-mode-and-back
preference transitions. The actual background, mode preference and painter agreed
at all three stages in each modern mode. OS screenshots were captured.

The first new pristine-stock Stop case timed out before invoking Stop because its
readiness predicate incorrectly assumed Run must be disabled during evaluation.
The diagnostic screenshot shows the real sleeping fixture and WAITING_TO_BREAK
output. Official stock `rep.rkt:1174–1179, 1600–1605` independently maintains tab
running state; Run enablement is not a valid evaluation-liveness proxy.

The repaired test awaits the exact marker, true tab running state and a live
registered break-thread/custodian. It logs those states before Stop, immediately
after Stop, and after cleanup. Source review also caught that `does-break-kill?`
is an unexported local-member name despite its public method declaration. The
test does not reflect into that private name: it strictly asserts the real
localized Stop-to-Kill label transition, which stock updates synchronously from
the same flag. Completion now requires tab not running in the main host's repeated
Run checks, the EOF workflow, and Check Syntax's initial Run. Reader validation
passes; the corrected Stop and remaining workflow cases still need native execution.
The baseline failure correctly prevented later workflow/performance runs.
