# Frozen native payload and portable CLI contract

2026-10-11: immutable new source-only revision rebuilt from exact committed 1021. This is
not recovery of the lost 1108 payload. The current eleven-file integration set
adds source/range/progress validators and their mandatory standalone gate.
SOURCE-REBUILD-API-PROOF.md records observed native causes, inferred path-alias
behavior and fresh version-pinned official API proof. Native reader, compilation, standalone execution and actual tool acceptance
of this revision remain pending. Earlier coordinator, dispatcher,
UI/diagnostics and initial-handler notes are historical evidence; their passing
source bytes and negative-control contracts remain unchanged.

## Frozen native integration allowlist

`FROZEN-NATIVE-ALLOWLIST.json` at the candidate root pins exactly:

- `tests/independent-native-host.rkt`
- `tests/independent-native-stock-tools.rkt`
- `tests/native-tool-coordinator.rkt`
- `tests/native-tool-coordinator-test.rkt`
- `tests/native-tool-coordinator-standalone.rkt`
- `tests/native-tool-dispatch.rkt`
- `tests/native-tool-dispatch-standalone.rkt`
- `tests/native-tool-failure-diagnostics.rkt`
- `tests/native-tool-failure-diagnostics-standalone.rkt`
- `tests/native-tool-source-contract.rkt`
- `tests/native-tool-source-contract-standalone.rkt`

Integrate exactly these eleven native files into a **new complete candidate** based on
the preserved tested source. This is not a standalone DrRacket distribution: the
host's unchanged existing runtime-path dependencies and the prepared official
runtime/addon setup must still be present. The vendored base fixture is input
provenance and must not replace the generated native host.

## 1. Portable preparation/source checks (no Racket or local cache needed)

From this handoff's root, on any machine with Python 3:

```sh
python3 scripts/prepare-stock-tool-host.py --check
python3 tests/stock-tool-source-test.py
python3 tests/coordinator-standalone-source-test.py
python3 tests/tool-dispatch-source-test.py
```

The preparation and stock-tool source commands default to
`tests/reference/independent-native-host-0520.rkt`, pinned to
SHA-256 `5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448`.
Neither searches for a sibling freeze. The input's exact bytes must match; CRLF
or other byte changes are rejected. To verify another explicitly supplied copy:

```sh
python3 scripts/prepare-stock-tool-host.py --base-host /absolute/base-host.rkt --check
python3 tests/stock-tool-source-test.py --base-host /absolute/base-host.rkt
```

`--check` never writes generated files. Omitting `--check` reproduces the same
host, patch, and metadata in the handoff root; do that only in an unfrozen work
copy. The old explicit positional base-directory form remains supported.

`audit-stock-tool-sources.py` is **local cached-source evidence only**. Its fixed
historical `/tmp` inputs and saved report are not portable CI prerequisites and
do not establish what is installed on another runner.

## 2. Official Racket 9.3 setup contract

On the already prepared official full Racket 9.3 macOS runner, set:

```sh
export RACKET=/absolute/path/to/official-9.3/bin/racket
export CANDIDATE=/absolute/path/to/new-complete-candidate
export ADDON=/absolute/path/to/prepared-addon-directory
export COMPILED_ROOTS=/absolute/path/to/disposable-compiled-cache:
cd "$CANDIDATE"
"$RACKET" -e '(unless (equal? (version) "9.3") (error "Expected official Racket 9.3"))'
```

Use the integration owner's actual prepared addon/collection layout. These
commands do not download, install, or alter a runtime. Preserve stock tool
registration, evaluation settings, resource limits, and accepted overlay settings.

## 3. Headless reader and mandatory standalone regressions

Reader check: it parses source without loading the native host or starting a GUI.

```sh
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -e '(parameterize ([read-accept-reader #t]) (for ([f (in-vector (current-command-line-arguments))]) (call-with-input-file f (lambda (in) (read-syntax f in) (unless (eof-object? (read-syntax f in)) (error "Extra form after module" f))))))' -- tests/native-tool-coordinator.rkt tests/native-tool-coordinator-test.rkt tests/independent-native-stock-tools.rkt tests/independent-native-host.rkt tests/native-tool-coordinator-standalone.rkt tests/native-tool-dispatch.rkt tests/native-tool-dispatch-standalone.rkt tests/native-tool-failure-diagnostics.rkt tests/native-tool-failure-diagnostics-standalone.rkt tests/native-tool-source-contract.rkt tests/native-tool-source-contract-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-coordinator-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-coordinator-standalone.rkt --inject-outer-failure
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-dispatch-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-dispatch-standalone.rkt --inject-wrong-result
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-failure-diagnostics-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-failure-diagnostics-standalone.rkt --inject-failure
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-source-contract-standalone.rkt
```

Run each direct command under the existing 30-second headless supervisor. The
injected commands must fail with their exact typed diagnostics and no success
marker; do not treat them as ordinary shell success steps or invoke these tests
through `raco test`. See `TOOL-DISPATCH-REPAIR.md` and the historical standalone
repair report for their exact accepted outputs.

The source-contract standalone is mandatory under the existing 30-second headless
supervisor. Require exit 0 and exactly one
`OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals`.
It exercises the same source/range/progress/budget validators used on actual
native observations, including wrong-file, off-by-one, no-progress, unresolved
source and real filesystem-alias refusal controls. Invoke directly, never via
`raco test`; this is headless validator proof, not a native tool pass.

The diagnostics standalone is mandatory in both modes:

- Positive: require exit 0 and exactly one
  `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained`.
  Neither injection nor typed-failure marker may appear.
- `--inject-failure`: require nonzero exit, exactly one
  `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE`, exactly one
  `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong`,
  and no `OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK` marker.

The positive run verifies typed check payload, source/expression information,
exact original failure identity and containment of closed-output-port and
non-exception reporter failures. The negative reporter writes verified typed
proof, encounters a closed output port, then rethrows the same original failed
check outside the diagnostic boundary. No ordinary source/reader pass substitutes
for either supervised standalone mode.

The original coordinator regression is genuinely headless: it uses a separate ordinary
handler thread to verify RackUnit failures propagate from action/readiness
callbacks, reject wrong-thread use, and return actions before polling. It does
not establish any native GUI behavior. The unchanged dispatch regression instead
models the initial thread as handler and uses the real new bridge to create the
separate coordinator, exercising value/exception handoff and worker cleanup.

## 4. Compile on the native runner

```sh
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -l raco -- make tests/native-tool-coordinator.rkt tests/native-tool-coordinator-test.rkt tests/independent-native-stock-tools.rkt tests/independent-native-host.rkt tests/native-tool-coordinator-standalone.rkt tests/native-tool-dispatch.rkt tests/native-tool-dispatch-standalone.rkt tests/native-tool-failure-diagnostics.rkt tests/native-tool-failure-diagnostics-standalone.rkt tests/native-tool-source-contract.rkt tests/native-tool-source-contract-standalone.rkt
```

A reader pass does not replace compilation; compilation does not replace native
execution. Preserve failures rather than proceeding to a misleading partial pass.

## 5. Three independent native case commands

The existing native CI capture supervisor must invoke each command below in its
own fresh process and newly created disposable `PLTUSERHOME`/`XDG_CACHE_HOME`.
Supply new, initially absent `OPENRACKET_READY_FILE` and
`OPENRACKET_CAPTURE_DONE` paths for every process. Do not pre-create the capture
acknowledgment, reuse profile state, or run multiple cases inside one host.

Set the selected arm before **each** supervised invocation:

- Stock: `OPENRACKET_UI=stock`, `OPENRACKET_HOST_THEME=0`,
  `OPENRACKET_NATIVE_APPEARANCE=0`, `OPENRACKET_THEME=light`
- Modern dark: `OPENRACKET_UI=modern`, `OPENRACKET_HOST_THEME=1`,
  `OPENRACKET_NATIVE_APPEARANCE=1`, `OPENRACKET_THEME=dark`
- Modern light: same modern values, with `OPENRACKET_THEME=light`

Unset `OPENRACKET_NATIVE_APPEARANCE_CHECK`; it is a different isolated host gate.
Use pristine stock first, then the unchanged candidate source in each claimed
modern arm. The full source remains the same across case selections.

```sh
OPENRACKET_NATIVE_CASE=debugger "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" "$CANDIDATE/tests/independent-native-host.rkt"
OPENRACKET_NATIVE_CASE=macro-stepper "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" "$CANDIDATE/tests/independent-native-host.rkt"
OPENRACKET_NATIVE_CASE=teaching-tests "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" "$CANDIDATE/tests/independent-native-host.rkt"
```

These are three supervisor inputs, not a shell sequence to run with a reused
profile. The caller owns independent profile/READY paths and all captures.

### Unchanged timing and startup

- The host clears command-line arguments on the actual GUI handler before loading
  `drracket/drracket`, then waits for the stock first shown frame.
- Existing host startup/basic Run `wait-for` calls retain their 60-second default
  and 25-ms poll interval.
- Debugger startup shares one 20-second budget from before Debug launch through
  every generated-source Step/wait. Subsequent original Step/Go and other
  tool/coordinator `await` gates retain separate 20-second deadlines. GUI actions
  fully return before polling; RackUnit's raising handler is parameterized inside
  the actual GUI callback, including predicates.
- The inherited host has no added per-callback timeout. Preserve the integration
  owner's existing 60-second external process timeout for stuck GUI actions/modals. This
  handoff neither increases nor substitutes that bound.
- Existing final paint settling remains 500 ms.

### Unchanged READY/capture success contract

The host writes its JSON report to `OPENRACKET_READY_FILE`, prints
`OPENRACKET_NATIVE_READY` on success (or failure READY diagnostics), and then waits
for `OPENRACKET_CAPTURE_DONE` for at most 20 seconds, polling every 50 ms. Without
a configured capture acknowledgment path it waits only 1 second; production CI
must configure the handshake. The supervisor captures first, then creates the
acknowledgment, then waits for the process to terminate.

Accept only exit 0 plus the normal successful host result, exact selected
`follow_on_case`, and `follow_on_result.status == "passed"`. A READY file alone,
intermediate `OPENRACKET_STOCK_TOOL_STATE` lines, or a screenshot does not establish
a pass. Preserve stdout, stderr, report, screenshots, and exit status. Unexpected
modal/failure state must be captured rather than dismissed to obtain success.
