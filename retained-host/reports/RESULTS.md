# Verification status

## Passed locally

- Racket9.3 `raco make src/paint.rkt` succeeds using the existing racket/draw dependency.
- 115 headless Racket tests pass: rendering states, retained bitmap fallback, compact
  inputs, DC state restoration, full-module presentation-only diff, stock-method
  preservation, theme metadata/contrast/opt-in protection and mock-based mixin contracts.
  These mock checks do not count as native DrRacket tests.
- 12 Python patcher tests pass: exact pristine source pin, deterministic generation,
  refusal of unexpected upstream modifications, corrupt payloads/rollback inputs,
  root symlinks and escaping targets without overwriting the isolated runtime.
- Official cached gui-lib/drracket/drracket-core-lib/htdp-lib archive SHA1 values
  match their release catalog checksums. The stock toolbar source is byte-identical
  between the official v9.3 Git source and release package.
- The rendered component sheet was visually inspected. It uses the same Racket
  painter called by the real source patch; it contains no fabricated application
  screenshot or replacement evaluator.

## Passed in the first real native Linux run

Run [38047260644](https://github.com/alikatgh/openracket/actions/runs/38047260644),
commit `e859f18a489761cdc3f1263cb51bbc0f9d306780`, used the complete official
Racket 9.3 distribution on standard Ubuntu 24.04 CI.

- The patched GUI, appearance tool and complete `drracket/drracket` entrypoint
  compiled. Tool registration and metadata setup passed.
- 14 native toolbar tests passed in each of pristine stock, stock fallback,
  modern light and modern dark modes.
- Five native canvas/status preservation tests passed in each modern mode.
- Genuine registered DrRacket frames, definitions/interactions editors and
  canvases started in all four modes; their editor identities were preserved.

The entire CI run failed later checks. These are partial native passes, not
complete workflow parity. Exact stage results are in `ci-first-run.json`.

## Second native Linux run

Run [38048840909](https://github.com/alikatgh/openracket/actions/runs/38048840909),
commit `720699694999cbf3cf97d864666b2e48c64aadc4`, fixed the delayed-startup
fixture handling and verified separate pristine/patched runtime paths and hashes.

- Pristine stock and stock fallback each passed 20 real-host checks.
- Modern light passed 24 checks, including actual scheme activation, retained
  editor/canvas identities, exact Unicode file loading, menu/tab/toolbar presence,
  native undo/redo and two real Run callbacks producing the marker and value 42.
- Genuine OS screenshots were captured in those three passing modes. The light
  image shows the original selected 128 MB evaluation limit.
- Modern dark passed its first 17 checks, then failed the strict painter/editor
  synchronization assertion. Its failure screenshot shows a dark editor and light
  toolbar. Official preference source confirms callbacks run before storing the
  new preference; the immediate bridge reread stale mode. The bridge now coalesces post-commit synchronization, synchronizes completed
  apply/restore transactions and refreshes existing toolbar canvases. Nine new
  independent callback-order regressions and three retained-toolbar refresh tests
  pass locally; actual dark startup/live switching still require the next native run.
- Missing Japanese glyphs appear in both pristine and modern captures. Exact
  Unicode source equality passes; this is a runner font coverage limitation.

## Remaining native gates

- Rerun dark startup and live preference-mode changes after the bridge repair.
  Do not treat the diagnostic failure screenshot as a passed modern-dark state.
- The corrected performance harness was skipped after the correctness failure.
  First-run timeout records are not usable timings; no speed claim is supported.
- macOS passed the repaired public-repository guard, then failed official DMG
  checksum verification before installation. The CI digest pin is being corrected
  from official release evidence; no native macOS checks passed yet.
- Stop/EOF/WXME/Check Syntax candidates are prepared separately for the next native
  batch. Debugger, Macro Stepper, teaching languages, accessibility, IME, Retina,
  complete stock parity and comprehensive visual layout review remain open.
- Local full-package installation and its authorized retry were cancelled before
  registry commit. Local display socket creation remains blocked without retry.
  Native evidence above comes only from the separately authorized CI.

The portable Racket applier compiles, shell setup/launchers pass syntax and
check-mode validation, and six performance-harness Python tests pass. The full
portable setup/launch path still needs direct end-to-end validation; CI uses an
isolated disposable full distribution adapter.

`reports/NATIVE-ACCEPTANCE.md` is the explicit remaining acceptance gate.
