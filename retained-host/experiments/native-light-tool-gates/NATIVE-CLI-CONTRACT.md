# Future native CLI contract (preparation only; authorization still required)

Do not publish or execute these commands until the coordinator authorizes it.
Normal Quit work precedes this light-mode functional gate. This local derivative
has not been natively read, compiled, or run.

## Candidate and unchanged process limits

Integrate exactly the sixteen files in `FROZEN-NATIVE-ALLOWLIST.json` into a NEW
complete copy of the already accepted candidate. Eleven are byte-identical 1125
native files; five are new test-only files. Do not copy `reference/production/`,
modify the original freeze/preview, register another tool, change memory limits,
replace any production module, or combine other experiments into this proof.
The host's original runtime-path dependencies still require that complete
candidate and its existing prepared official runtime/addon/overlay setup.

The future runner must already have official full Racket 9.3 for macOS and the
accepted setup. Set these absolute paths; no setup or install command is included:

```sh
export RACKET=/absolute/official-9.3/bin/racket
export CANDIDATE=/absolute/new-complete-candidate
export ADDON=/absolute/prepared-addon
export COMPILED_ROOTS=/absolute/disposable-compiled-cache:
cd "$CANDIDATE"
"$RACKET" -e '(unless (equal? (version) "9.3") (error "Expected official Racket 9.3"))'
```

Preserve the accepted external native process timeout of 60 seconds, all existing
startup/basic Run 60-second waits with 25-ms polling, the one shared 20-second
Debugger startup/source-traversal budget, later separate 20-second tool awaits,
500-ms final paint settle and 20-second READY/capture acknowledgment wait with
50-ms polling. The derivative adds no wait or retry budget. Headless commands
keep the existing 30-second external supervisor.

## Reader and compilation (both mandatory)

Use the exact `.rkt` paths listed in the allowlist, including all new Racket
modules. The JSON state file must be adjacent to its validator. Reader-check all
fifteen Racket modules without loading them; then compile all fifteen with the
same prepared addon/collections. Stop on either failure. Typical command shape:

```sh
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -e '(parameterize ([read-accept-reader #t]) (for ([f (in-vector (current-command-line-arguments))]) (call-with-input-file f (lambda (in) (read-syntax f in) (unless (eof-object? (read-syntax f in)) (error "Extra form after module" f))))))' -- tests/independent-native-host.rkt tests/independent-native-stock-tools.rkt tests/native-tool-coordinator.rkt tests/native-tool-coordinator-test.rkt tests/native-tool-coordinator-standalone.rkt tests/native-tool-dispatch.rkt tests/native-tool-dispatch-standalone.rkt tests/native-tool-failure-diagnostics.rkt tests/native-tool-failure-diagnostics-standalone.rkt tests/native-tool-source-contract.rkt tests/native-tool-source-contract-standalone.rkt tests/independent-native-light-tools-host.rkt tests/native-light-state-contract.rkt tests/native-light-state-observer.rkt tests/native-light-state-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -l raco -- make tests/independent-native-host.rkt tests/independent-native-stock-tools.rkt tests/native-tool-coordinator.rkt tests/native-tool-coordinator-test.rkt tests/native-tool-coordinator-standalone.rkt tests/native-tool-dispatch.rkt tests/native-tool-dispatch-standalone.rkt tests/native-tool-failure-diagnostics.rkt tests/native-tool-failure-diagnostics-standalone.rkt tests/native-tool-source-contract.rkt tests/native-tool-source-contract-standalone.rkt tests/independent-native-light-tools-host.rkt tests/native-light-state-contract.rkt tests/native-light-state-observer.rkt tests/native-light-state-standalone.rkt
```

## Nine mandatory direct standalone invocations

Each line is a separate input to the existing 30-second headless supervisor.
Never use `raco test`, ignore an exit status, or turn intentional failures into
ordinary success steps. Preserve exact stdout, stderr, exit and timeout state.
The first seven are unchanged from accepted 1125; the final two are additive.

```sh
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-coordinator-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-coordinator-standalone.rkt --inject-outer-failure
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-dispatch-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-dispatch-standalone.rkt --inject-wrong-result
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-failure-diagnostics-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-failure-diagnostics-standalone.rkt --inject-failure
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-tool-source-contract-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-light-state-standalone.rkt
"$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/native-light-state-standalone.rkt --inject-wrong-painter
```

Exact expected marker/exit pairs are executable in `PREFLIGHTS` in
`scripts/validate-light-tool-result.py`. Every positive requires exit zero and
one exact OK marker. Every negative requires a positive, non-signal/non-timeout exit (1–123), one exact injection
marker and one exact typed failure marker, with no corresponding OK marker.
Timeout is never an acceptable negative-control result.

New positive marker:
`OPENRACKET_NATIVE_LIGHT_STATE_OK exact-palette-painter-cocoa-refusals`

New negative markers:
`OPENRACKET_NATIVE_LIGHT_STATE_INJECTING_FAILURE`
`OPENRACKET_NATIVE_LIGHT_STATE_FAILURE exception=exn:test:check check=check-equal? actual=dark expected=light`

The new positive exercises both ordinary nested hashes and read-json hasheq
snapshots through the actual shared validator, then rejects missing fields,
wrong palettes, wrong painter colors, missing/wrong Cocoa data, platform-follow,
dark RGBs and extra keys. It is headless validator proof, not a light native pass.

## Six isolated native cases

Stock uses the original, unchanged host. Modern light uses its separate derived
entrypoint. Run stock first, then light, for each case or as two separate arms.
Every command must have its own fresh process, new disposable `PLTUSERHOME` and
`XDG_CACHE_HOME`, and initially absent, distinct `OPENRACKET_READY_FILE` and
`OPENRACKET_CAPTURE_DONE` paths. Unset `OPENRACKET_NATIVE_APPEARANCE_CHECK` in every
case. Keep accepted evaluation settings, tool registration and memory limits.

Stock environment for each of the three original host invocations:

```sh
export OPENRACKET_UI=stock OPENRACKET_HOST_THEME=0 OPENRACKET_NATIVE_APPEARANCE=0 OPENRACKET_THEME=light
unset OPENRACKET_NATIVE_APPEARANCE_CHECK
OPENRACKET_NATIVE_CASE=debugger "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-host.rkt
OPENRACKET_NATIVE_CASE=macro-stepper "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-host.rkt
OPENRACKET_NATIVE_CASE=teaching-tests "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-host.rkt
```

Modern-light environment for each of the three new entrypoint invocations:

```sh
export OPENRACKET_UI=modern OPENRACKET_HOST_THEME=1 OPENRACKET_NATIVE_APPEARANCE=1 OPENRACKET_THEME=light
unset OPENRACKET_NATIVE_APPEARANCE_CHECK
OPENRACKET_NATIVE_CASE=debugger "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-light-tools-host.rkt
OPENRACKET_NATIVE_CASE=macro-stepper "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-light-tools-host.rkt
OPENRACKET_NATIVE_CASE=teaching-tests "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" tests/independent-native-light-tools-host.rkt
```

These are supervisor inputs, not an invitation to reuse one shell profile across
three processes. The existing capture supervisor must capture after READY,
acknowledge only after capturing, and wait for terminal exit. Preserve failure
windows/modals and diagnostics rather than dismissing them to obtain success.

## Read-only result acceptance

The future runner's preflight evidence JSON must contain exactly nine records.
Each record contains `entrypoint` (basename), `arguments` (array containing only
its optional injection flag), integer `exit_code`, boolean `timed_out`, integer
`timeout_seconds` equal to 30, and full `stdout` and `stderr` strings.

For each actual native result, after a recorded successful reader/compile step
and after capture + process completion, invoke the local verifier:

```sh
python3 scripts/validate-light-tool-result.py --arm modern-light --case debugger --report /absolute/ready.json --stdout /absolute/stdout.txt --stderr /absolute/stderr.txt --exit-code 0 --preflights /absolute/preflights.json
```

Supply the actual exit code; add `--timed-out` if the supervisor timed out (which
must fail). Repeat for all six distinct arm/case pairs, changing paths. Do not
claim the complete matrix from one accepted receipt. A suite is accepted only
when all six unique pairs pass on the same pinned source and setup, with fresh
profiles, screenshots, non-timeout exits, all mandatory headless controls and
successful reader/compile evidence preserved.

The verifier enforces exact native host READY/stdout agreement, exit zero, genuine
host and repeated Run proof, official version, exact chosen case/result status,
no failure marker, and the unchanged stock receipt shape. Modern-light also
requires exactly two ordered matching actual-state snapshots in both log and
report, surrounding the workflow. It rejects missing or numeric stand-ins for
boolean state. It launches nothing and cannot prove runner supervision, capture,
fresh-profile provenance, installed-source identity or reader/compiler execution;
the future CI owner must retain and check those independent records. Synthetic
unit-test receipts are never native run evidence.
