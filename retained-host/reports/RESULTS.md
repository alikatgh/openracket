# Verification status

## Passed locally

- Racket9.3 `raco make src/paint.rkt` succeeds using the existing racket/draw dependency.
- 120 headless Racket tests pass: rendering states, retained bitmap fallback, compact
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

## Third native Linux and macOS run

Run [38049557901](https://github.com/alikatgh/openracket/actions/runs/38049557901),
commit `cbf78aa05bb911effd3b011ac1cd1492592e2d0d`, passed the complete basic
host harness on both standard Linux and macOS runners: 20 checks each for
pristine stock and stock fallback, and 28 each for modern light and modern dark.
Both live light/dark roundtrips now synchronize actual editor colors and toolbar
painter state. Native captures succeeded in all four modes on both platforms.
Actual compilation, toolbar/canvas checks and pristine runtime isolation passed.
Linux Japanese glyph coverage is now supplied by the official Noto CJK package.

The first follow-on Stop case failed in pristine stock on both systems before
pressing Stop: the harness incorrectly assumed Run must be disabled while the
program runs. Stock allows Run to restart evaluation. The repaired test observes
the real tab running state and live break thread/custodian, then checks the
public localized Stop-to-Kill label transition. Source review also removed a
candidate direct call to an unexported local member. Existing Run completion
checks now require the real tab to stop, rather than infer that from Run's state.
These are test-only repairs; the native-tested production code did not change.

## Fourth native run: Linux preservation cases pass

Run [38050213153](https://github.com/alikatgh/openracket/actions/runs/38050213153),
commit `0c8510d768483840d37c19afc4833ddc180a66a0`, kept the production code
unchanged and passed all Linux basic/native widget checks plus all eight added
preservation cases: Stop, Unicode stdin/EOF, WXME image/nested-editor round-trip,
and Check Syntax in separate pristine-stock and modern-dark processes.

Stock and modern emitted exactly equal normalized Check Syntax binding graphs.
Their observed Stop state sequences also match, including the actual Stop-to-Kill
label change and interrupted evaluation cleanup. These exact comparisons are
stored in `ci-fourth-run.json`; they do not certify the second forced-Kill action.

Benchmark runs failed before workload timing because their startup watcher was
stopped from a different custodian. The macOS job stopped at a Python supervisor
unit test that signaled an already-exited process group. The watcher now stops cooperatively without cross-custodian thread killing; the
Python supervisor verifies whether its own group still has live processes before
a repeated signal and still fails for live cleanup failures. Nine Python and five
Racket lifecycle tests pass. These are bounded harness repairs; no production
change is indicated. Earlier macOS native core passes
remain valid for unchanged code, but macOS preservation cases did not run here.

## Fifth native run: measured baseline and macOS diagnostics

Run [38050824369](https://github.com/alikatgh/openracket/actions/runs/38050824369),
commit `fcf24f95dd0196b3be4945d1eede50e91ea43846`, verified the benchmark
lifecycle/supervisor fixes. Both platforms passed all core native modes, actual
compilation, theme roundtrips, widget checks and runtime isolation. Linux passed
all eight preservation cases and all twelve performance trials.

The performance measurements reveal a substantial remaining engineering problem:
1 MiB first-workload lexer stabilization takes roughly 21–24 seconds and heartbeat
gaps reach multiple seconds in both stock and modern modes. Synchronous file-load
time is only one part of readiness. No speed improvement is established. See
`PERFORMANCE-BASELINE-38050824369.md` for measured medians, tails and limitations.

On macOS, untouched stock Stop changed to Kill but the sleeping fixture did not
finish within the strict 20-second completion bound. Remaining preservation cases
were skipped. Six 100k performance trials completed; all six 1 MiB trials exceeded
the unchanged 45-second initial lexer-readiness bound, so their warm timings are
invalid. The cause of the Stop timeout is not established. The next source adds
read-only state/stack diagnostics without relaxing the assertion, and one bounded
pristine Linux profiling trial. The production presentation code remains unchanged.

## Remaining native gates

- Diagnose macOS stock Stop completion and execute its other preservation cases.
  Attribute large-file lexer delays and event-loop stalls before proposing safe
  responsiveness changes. No speed improvement is claimed.
- Debugger, Macro Stepper, teaching languages, accessibility, IME, Retina,
  complete stock parity and comprehensive visual layout review remain open.
- Native menus/status/borders remain substantially stock. This is a first
  retained-host modernization increment, not the final desired polished design.
- Local package transactions and display remain blocked without retry; all native
  evidence comes from the separately authorized public CI.

The portable Racket applier compiles, shell setup/launchers pass syntax and
check-mode validation, and nine performance-harness Python tests and five Racket lifecycle tests pass. The full
portable setup/launch path still needs direct end-to-end validation; CI uses an
isolated disposable full distribution adapter.

`reports/NATIVE-ACCEPTANCE.md` is the explicit remaining acceptance gate.
