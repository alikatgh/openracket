# Independent retained-host audit

Date: 2026-10-10. Scope: local source/headless audit plus native test preparation.
This report does not certify full DrRacket parity, native rendering, or performance.
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
- Both independent native harnesses passed reader syntax checks only locally.

The first painter run emitted Fontconfig cache-writability warnings while its eight
assertions passed. The final isolated-cache run passes all 30 independent Racket
tests without those warnings. This is not a native font-availability or DPI verdict.

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
or language implementation. Native execution is pending; a harness existing or parsing
is not a native pass. The separate performance owner maintains paired performance
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

Native compilation and execution; exact screenshots in both themes; larger system
fonts and DPI; IME/accessibility; tooltip and right-click modal lifecycle; Stop/Kill,
Check Syntax, Debug, Macro Stepper, teaching languages, snips and rich documents;
multiple windows/tabs and third-party plugins; built-in preferences restore/reapply;
paired stock-versus-overlay native responsiveness and memory measurement. Source
preservation is valuable evidence but does not substitute for these workflows.
