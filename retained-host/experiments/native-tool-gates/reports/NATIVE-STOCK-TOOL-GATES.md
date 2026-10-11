# Native stock-tool acceptance candidate

Historical original acceptance-gate design and preparation notes. The sections
below describe earlier revisions, not the current verification status or file
allowlist. Use `UI-REPAIR-API-PROOF.md` for the current stock-tool UI/diagnostics
repair and `NATIVE-CLI-CONTRACT.md` plus the root nine-file
`FROZEN-NATIVE-ALLOWLIST.json` for current integration and mandatory commands.
`TOOL-DISPATCH-REPAIR.md` records the earlier initial-handler repair.

Prepared 2026-10-11. This is a new, unpublished candidate. It does not recover or
claim results from the lost follow-on candidates.

## Verification status

- Passed locally: 9 Python source/orchestration contracts, lexical delimiter
  integrity, exact bounded host derivation, and 52 API anchors in 15 cached stock
  source files. Source hashes and exact anchor lines are in
  `stock-tool-source-audit.json`.
- Not run: Racket reader/expansion/compilation, the headless Racket coordinator
  regression, or any native GUI gate. No Racket executable is available in this
  workspace. No runtime installation, download, Xorg, GUI launch, or remote action
  was attempted.
- Native execution belongs on official full Racket 9.3 for macOS. Run pristine
  stock before attributing a failure to the appearance overlay. A failure in both
  arms can be a bad test assumption and is not evidence of an overlay regression.

## Integration owner handoff

Copy these new files into a **new** complete candidate, preserving the frozen base:

- `tests/independent-native-stock-tools.rkt`
- `tests/native-tool-coordinator.rkt`
- `tests/native-tool-coordinator-test.rkt`

Apply `stock-tool-host.patch` to `tests/independent-native-host.rkt`, or copy the
reproducibly generated host from this directory. The generated host contains only
three substitutions relative to the hash-locked frozen input: a runtime module
path, three supported case names, and a coordinator dispatch branch. Existing
host behavior, retained-class assertions, original cases, timeouts, diagnostics,
READY/capture handshake, report format, and capture cleanup are unchanged.

Portable validation uses the byte-pinned vendored base-host fixture, with no
sibling checkout dependency:

    python3 scripts/prepare-stock-tool-host.py --check
    python3 tests/stock-tool-source-test.py

Both commands accept `--base-host /absolute/base-host.rkt` for an explicit input.
See `NATIVE-CLI-CONTRACT.md` for the frozen four-file allowlist, exact headless and
native commands, fresh-process setup, startup/20-second waits, and unchanged
READY/capture protocol. The actual Racket files are unchanged by this portability
revision. `audit-stock-tool-sources.py` is local cached-source evidence only and
is not a portable CI prerequisite.

Before native execution, run on the official runtime:

    raco make tests/native-tool-coordinator.rkt tests/independent-native-stock-tools.rkt tests/independent-native-host.rkt
    raco test tests/native-tool-coordinator-test.rkt

The headless coordinator regression uses a genuinely separate handler thread
whose ambient RackUnit handler deliberately does not raise. It requires checks in
both action and wait callbacks to raise anyway, verifies exception propagation,
rejects the wrong handler, and proves each action has returned before polling.
It is an orchestration regression, not GUI evidence.

## Execution contract

Use the existing native caller/capture supervisor with exactly one value of
`OPENRACKET_NATIVE_CASE` per fresh process:

1. `debugger`
2. `macro-stepper`
3. `teaching-tests`

Run each separately in stock, modern-dark, and modern-light arms if claiming both
appearance modes. Each arm/case pair needs a newly created disposable profile and
a new process. Do not reuse a process for all three tools. Do not set the native
appearance lifecycle flag at the same time: the host already rejects that mix.
Leave tool discovery, default evaluation settings, memory limits, instrumentation,
and language preferences intact. Use the parent CI's prepared official runtime
and existing addon/collection arrangements; these files do not install anything.

Every new readiness/completion wait has the existing 20-second tool deadline.
Individual GUI actions fully return before the coordinator waits. The inherited
host's external process timeout is still required to bound a stuck native action
or modal. Preserve the parent supervisor's timeout, READY/capture behavior, stdout,
stderr, screenshots, and process exit status. Do not dismiss an unexpected modal
or raise a timeout to make the gate pass.

A native success requires exit 0, the normal host READY/result, matching selected
case, and `follow_on_result.status == "passed"`. Partial stage logs are not a pass.
On a failure, preserve the host's failure READY/diagnostic and capture before
process teardown. `OPENRACKET_STOCK_TOOL_STATE` lines provide intermediate evidence
for stopped/stepped debugger state, macro indices/text, and teaching test results.
These are recorded observations, not physical click or pixel-performance evidence.

## Debugger acceptance and stock API traps

- Ordinary Run first selects `#lang racket/base` and completes the known fixture.
- Locate exactly one actually shown localized Debug switchable-button in the live
  toolbar tree. Traverse only visible ancestors. **Do not call `get-debug-button`
  here:** stock returns a legacy control that is removed for module languages.
  The real module toolbar callback reaches a private local-member name.
- Invoke the real button's `command`; wait for running/debug state, a nonempty real
  stack, positive PC, and enabled Step/Go.
- Capture `(PC, break status, current frame endpoints)` before focus/paint. Check
  source ownership through `defs-containing-pc` and
  `defs-containing-current-frame`, retained identities, and exact source text.
- Invoke real Step; require a new observable tuple. Comparing PC alone would
  incorrectly reject valid entry/exit steps at the same source position.
- Invoke real Go; require the tab no longer running, Run enabled, the expected
  marker and value 42, cleared stack/break state, and disabled Step/Go. A final
  ordinary Run must recover and leave the tab outside debug mode.

Relevant stock sources: `gui-debugger/debug-tool.rkt` lines 39–58 (private callback
and real opt-out button), 853–945 (tab state and source getters), 1020–1107
(suspend/resume lifecycle), 1429–1540 (controls), 1560–1576 (hidden legacy button).

## Macro Stepper acceptance and stock API traps

- Launch via the uniquely shown localized Macro Stepper switchable-button. The
  `run-macro-stepper` identifier is a private local-member name even though its
  definition uses `define/public-final`; an external ordinary send is invalid.
- Discover a newly shown stock tool frame; verify its widget is a real
  `macro-stepper-widget%`.
- Wait for expansion completion, a valid nonnegative public
  `get-current-step-index`, visible fixture syntax, and enabled Next. The generated
  getter is created by `notify:define-notify`; it becomes valid only after the
  focused term's reductions exist. An empty or merely shown window cannot pass.
- Fixture contains two user macro invocations so the real sequence supports both
  Next and a subsequent enabled End even with default macro hiding.
- Use actual native button callbacks selected by their stock bitmap/text/side
  tuple: Start/left, Step/left, Step/right, End/right. The two Step controls have
  the same text and must be distinguished by side.
- Require Next index increase, End index increase and disabled forward buttons,
  different initial/final text, Previous exactly one index back, and Start restoring
  the original index/text. No derivations, preferences, or cursor values are injected.
- Close using the inherited `frame:basic%.close`, which runs
  `can-close?`, `on-close`, and `show #f` in order. Merely hiding a window would skip
  close semantics. Verify host remains shown, retained focus/source, and another
  real Run completes with 42.

Relevant sources: `macro-debugger/tool.rkt` lines 24–25, 96–106, 193–230;
`macro-debugger/view/stepper.rkt` lines 89, 137–141, 230–245, 310–358, 401–425,
446–460; `term-record.rkt` lines 197–224; `framework/private/notify.rkt` lines 22–44;
`framework/private/frame.rkt` lines 220–224.

## Teaching-runtime acceptance and stock API traps

- Run a genuine `#lang htdp/bsl` module containing value 42, one passing test and
  one failing `(check-expect (bump 2) 4)` on line 5, column 0.
- Read the already-instantiated `test-engine/test-engine` in the real evaluator's
  namespace, using `interactions.run-in-evaluation-thread`. Return a bounded
  snapshot through a response box; evaluator errors are raised by the wait
  predicate, never converted to not-ready.
- Require exactly 2 tests / 1 pass / 1 failure, reason `unequal`, actual 3,
  expected 4, and exact filename, line, column, one-based position, and span.
  Reading a test engine instantiated in the harness namespace would be invalid.
- Check the actual report's localized failure count and source label. Invoke its
  installed `call-clickback` using offsets in the **unflattened** report text so
  nested value snips do not shift positions. The resulting
  `interactions.get-error-ranges` must name the retained definitions editor and
  have the exact same numeric location. Stock normalizes error-range sources from
  paths to editor objects, so comparing those source objects to the original
  filename would be an incorrect assertion.
- Pin editor/tab/canvas/Run identities and source before focus/paint; require real
  definitions canvas focus and unchanged selection/text.
- Replace only the expected `4` with `3` in that same unsaved buffer through its
  real editor operation. Run again; require stopped tab, value 42, localized
  both-tests-passed output, 2 real passes / 0 failures, and the **original** report
  editor's text/length cleared to empty. Do not manually clear the report.

Relevant sources: `test-engine/syntax.rkt` lines 30–40; `racket-tests.rkt` lines
103–124; `test-engine.rkt` exported state/readers; `test-markup.rkt` lines 68–110,
146–170; `markup-gui.rkt` lines 16–38, 51–65; `test-display-gui.rkt` lines 35–80,
157–164; `test-tool.rkt` lines 195–208; `drracket/private/rep.rkt` lines 624–628,
754–785, 904–905, 1349–1353.

## Explicit remaining scope

These cases do not verify the graphical teaching Stepper, Language dialog,
Debugger Pause/Over/Out or user-created breakpoints, Macro Stepper preferences or
obsolete-session warnings, physical pointer hit-testing, OS accessibility/IME,
all plugins, or complete stock feature parity. Screenshot capture after the
normal READY gate proves final state only; intermediate assertions and stage logs
are the evidence for the paused debugger and navigated derivation.
