# Future CI gate: original and patched light collapsed-caret pair

Preparation only. Native reader, compilation, headless Racket controls, launch,
actual screen capture and visual review have not run. Publication and native
execution require the parent's later authorization. This package launches
nothing; it deliberately does not duplicate or silently modify the existing CI
runner. The CI owner must wire the explicit evidence contract below into its
accepted supervisor before executing it.

## Smallest native matrix

1. Original modern-light palette, exact old RGB and original info source hash.
2. Patched modern-light palette, exact new RGB and patched info source hash.

Both run `tests/independent-native-light-caret-host.rkt` with the same accepted
Macro Stepper workflow and official full macOS Racket9.3 content identity. Keep
its genuine DrRacket frame/editor/canvas registration, editing/undo/redo, theme
switch-and-restore, two ordinary Run checks, before/after loaded light/painter/
Cocoa snapshots, real Macro Stepper Next/End/Previous/Start, normal close,
ordinary Run recovery, and failure diagnostics exact. No unrelated dark, Quit,
Debugger or teaching-language native cases are added to this focused matrix.
The inherited16-file overlay includes those sources because the unchanged host
imports them; including them is not a claim to rerun those workflows.

## Source composition, before setup

Require the complete accepted0520 155-member source with exact manifest identity
listed in README. Do not recreate missing production bytes or substitute an
approximate checkout. Use `scripts/compose-candidate.py` separately for each arm
with `--source`, a new absent `--output`, `--arm original|patched`, and a
`--receipt` path. The composer verifies all155 accepted members before any write,
then copies only those members, applies the one-entry patch only for `patched`,
then copies the exact frozen16 native overlay and the five focused test files.

The result has175 members. The original accepted product files that the native
overlay replaces are explicitly governed by that frozen overlay, not presented
as unchanged product input. The two complete output manifests must differ only
at `tool/info.rkt`. Do not copy this package's `reference/` tree into the app.
The accepted source's setup, appearance tool, GUI overlay and runtime-path
workflows remain real dependencies. In particular, preserve
`independent-native-workflows.rkt`, `independent-native-appearance-workflows.rkt`
and `independent-native-stop-returning.rkt` from the verified full input.

Use existing accepted setup and fresh private addon registration in distinct
disposable profiles. Never reuse the user's preferences, modify a baseline
runtime, increase memory limits, bypass registration, or reuse one arm's
compiled overlay for the other. The observer hashes the actually resolved
appearance info, Framework line-number renderer and Cocoa source and requires
the actual loaded palette to match the chosen arm.

## Reader, compiler and headless controls

For each prepared arm, native reader-check all22 `.rkt` modules returned by
`required_racket_modules()` in `scripts/validate-caret-result.py`, then compile
all22 through the same prepared addon/collections. The set is the frozen15 Racket
modules, four focused Racket modules, and three original runtime-path workflow
dependencies. Keep existing30-second reader and180-second compilation external
deadlines. Stop on either failure. Never call a lexical source check a reader or
compile pass.

Run the exact12 direct standalone invocations in `PREFLIGHTS` in the same
verifier. The nine frozen direct controls are unchanged; three are added:

- `native-light-caret-standalone.rkt`
- `native-light-caret-standalone.rkt --inject-wrong-state`
- `native-light-caret-standalone.rkt --inject-wrong-color`

Every invocation has the unchanged30-second external deadline. The positive
requires its unique exact OK marker and exit0. Each intentional negative must
emit its unique injection marker and typed `exn:test:check` / `check-equal?`
marker, then re-raise the original exception and exit1..123 with no OK marker.
Timeout, signal termination, wrong exception, missing marker or diagnostic
output failure is never an acceptable negative control. Preserve stdout/stderr
and actual exit status. Do not wrap these in `raco test` or ignore nonzero exits.
Synthetic Python adapter receipts in portable tests are not these native runs.

## Native invocation and unchanged absolute deadline

Each arm gets a fresh process and distinct disposable profile, initially absent
READY and capture-ack files, exact composed source and official Racket9.3.
Required environment values are:

- `OPENRACKET_UI=modern`, `OPENRACKET_HOST_THEME=1`
- `OPENRACKET_NATIVE_APPEARANCE=1`, `OPENRACKET_THEME=light`
- `OPENRACKET_NATIVE_CASE=macro-stepper`
- `OPENRACKET_CARET_ARM=original` or `patched`
- unset `OPENRACKET_NATIVE_APPEARANCE_CHECK`

Use the accepted official Racket executable plus private `-A` addon and `-R`
compiled-root options, then the focused host. Do not change evaluation settings.
Keep the single outer60-second native-process deadline, fixed at original
process start. Existing60-second host waits,25-ms polling, tool budgets,
500-ms final paint settle and20-second READY/capture wait stay byte-identical.
No new wait, retry, timeout extension, thread, renderer override or repaint call
is introduced. The outer deadline still dominates every nested wait.

Immediately before the existing final normal paint/capture path, the test sets
the genuine retained definitions editor's selection to the start of source
paragraph3 (offset68 in the exact accepted Macro Stepper source). After the
unchanged500-ms settle it verifies exact registered editor/canvas identity,
unchanged source, native focus, visible line-number interface, collapsed
selection, current paragraph2 (zero-based), and full vertical containment in
the current canvas viewport. It reads current palette colors and actual source
hashes. Failure is a typed assertion handled by the original host diagnostics;
ordinary state-output errors are best effort and cannot replace that assertion.
A dedicated emitter propagates `exn:break?` unchanged rather than swallowing an
asynchronous break during output. The standalone positive includes ordinary
output-error, raised-value, preserved-break-identity and subsequent typed-state
validation regressions; missing exact native state output still fails acceptance.

## Capture and terminal acceptance

The actual accepted supervisor must capture the real visible macOS window after
its successful READY, using `screencapture`. Preserve original pixels. No pixel
recoloring, synthesized gutter, replacement editor, private painter call or
substitute reference image. A capture must precede its acknowledgment, both
within the original20-second wait, and the process must terminate successfully
before the original outer60-second deadline. Preserve failure captures as
failures. A missing, obscured or clipped current-line marker is not acceptance;
PNG validation checks signature, chunk structure and CRCs only; it does not
decode or certify the pixels. The CI reviewer must inspect each actual image for the fully visible line3
marker. The programmatic state checks are evidence of state, not proof that an
arbitrary PNG depicts it. Record visual review separately and do not claim a
rendered-state pass before it.

Per arm, preserve these files (raw files remain in controlled CI evidence; do
not publish workspace, temporary or interpreter paths unnecessarily):

- `composition.json`: exact source-only composition receipt
- `build.json`: reader and compiler records, each with `stage`, actual integer
  `exit_code`, boolean `timed_out`, original `timeout_seconds`, sorted exact22
  `modules`, and SHA-256 of raw `composition.json` as `composition_sha256`
- `preflights.json`: exact12 records in the inherited strict receipt format
- `ready.json`, `stdout.txt`, `stderr.txt`, and original `capture.png`
- `supervisor.json`: actual `arm`, `composition_sha256`, `timeout_seconds:60`,
  `timed_out:false`, `exit_code:0`, `process_group_alive_after_cleanup:false`;
  actual finite monotonic-second timestamps `started_monotonic`,
  `deadline_monotonic`, `ready_monotonic`, `capture_completed_monotonic`,
  `ack_monotonic`, `exited_monotonic`; `capture_tool:"screencapture"`,
  `capture_after_ready:true`, raw-byte `ready_sha256` and `png_sha256`;
  verified `fresh_process`, `fresh_profile`, `initial_ready_absent`,
  `initial_ack_absent`; non-path unique `profile_id`, a fresh non-path `launch_id` bound by the real
  supervisor to that launch, real positive `process_id`,
  and `official_runtime_sha256` of the shared official runtime content witness.

`validate-caret-result.py` accepts one arm only with every requested evidence
file. `validate-caret-pair.py --original <evidence-directory> --patched
<evidence-directory>` repeats both full validations and requires distinct
profiles, launch receipts and recorded `(process_id, started_monotonic)` identities,
plus identical official runtime identity. Sequential OS PID reuse is permitted
when the recorded process start and launch receipt are distinct. A self-reported
boolean or hash cannot establish its own truth: the real supervisor, exact
setup/runtime witness and preserved raw artifacts must substantiate them.

Native output distinguishes original exact baseline from patched >=4.5 intended
colors. It never asserts full accessibility, overall parity, anti-aliased pixel
contrast, latency, or behavior outside this focused inherited workflow.
