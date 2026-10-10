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

## Not yet passed / not run

- Complete stock DrRacket installation: cancelled before package registry commit.
  A newly authorized single retry was also cancelled. Subsequent local work uses
  existing headless dependencies and read-only source inspection. Public native CI
  is a separately authorized route; its results are pending.
- Full theme tool compilation was attempted and stops at missing racket/gui/base
  before GUI startup. The painter and GUI-free theme modules compile.
- Tool registration, native button event tests, full DrRacket launch, main-window
  before/after, debugger/macro/teaching workflows: not run.
- Native display: not available. A separately attempted dummy-Xorg display could
  not open local sockets. No display permission escalation or alternate route used.
- macOS behavior, Retina/IME/accessibility, native menus/dialogs, complete stock
  parity and actual application performance: not tested.

The portable Racket applier compiles, shell setup/launchers pass syntax and
check-mode validation, and four performance-harness Python tests pass. First native
CI must validate full GUI module compilation and actual DrRacket launch.

`reports/NATIVE-ACCEPTANCE.md` is the explicit remaining acceptance gate.
