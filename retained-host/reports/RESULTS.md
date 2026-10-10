# Verification status

## Passed locally

- Racket9.3 `raco make src/paint.rkt` succeeds using the existing racket/draw dependency.
- 103 headless Racket tests pass: rendering states, retained bitmap fallback, compact
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

## Not yet passed / not run

- All four real-host harness runs stopped at Unicode fixture equality. The queued
  stock startup callback consumed arguments after the test's temporary parameter
  scope ended. The test now starts normally and opens its fixture through the
  existing frame method; the repair needs native rerun. Run/undo/redo assertions
  after that failure have not passed, and no application screenshot was captured.
- All 12 performance trials timed out in a stock startup dialog. There are no
  valid application speed or latency results. The benchmark startup harness is
  being corrected without changing stock instrumentation, tools or limits.
- macOS failed its public-repository metadata precheck with HTTP 403 before
  checkout; no macOS native tests ran.
- Debugger, Macro Stepper, teaching languages, WXME, accessibility, IME, Retina,
  complete stock parity and comprehensive visual layout review remain open.
- Local full-package installation and its authorized retry were cancelled before
  package registry commit. The local native display cannot open sockets and was
  not retried. Native evidence above comes only from the separately authorized CI.

The portable Racket applier compiles, shell setup/launchers pass syntax and
check-mode validation, and six performance-harness Python tests pass. The full
portable setup/launch path still needs direct end-to-end validation; CI uses an
isolated disposable full distribution adapter.

`reports/NATIVE-ACCEPTANCE.md` is the explicit remaining acceptance gate.
