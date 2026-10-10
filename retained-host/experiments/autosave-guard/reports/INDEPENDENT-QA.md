# Independent QA: default-off save-scan guard

Date: 2026-10-10. Scope: isolated DrRacket/Racket 9.3 source experiment. No installation, GUI/display launch, network access, remote writes, default activation, or performance measurements were performed by this review.

## Result

**Headless source/model gates pass. Native acceptance remains unrun. No speedup or unconditional extension compatibility is established.**

The generated `framework/private/text-misc.rkt` differs from the pinned stock parsed module only by the module-level default-off flag and its export, plus the two proposed predicate guards. Removing those exact additions reconstructs the full original parsed module. The original scan expressions, subsequent condition ordering, prompt logic, format mutation, and `inner` hook calls remain intact.

Candidate SHA-256: `00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d`.

Upstream source SHA-256 values independently checked:

- `text-misc-v9.3.rkt`: `7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638`
- `editor-misc-v9.3.rkt`: `3becc626874477283cdd1b9f45631f11baed586aa37a3c95d67a4a0a2b677885`
- `editor-mred-v9.3.rkt`: `1eef92a431da2c2cf40d193237d4ab9879adae9518c71b39ba5af0dc6b32f75a`

## What actually ran

`tests/independent-model-test.rkt` executes the parsed original and generated `clever-file-format-mixin` declarations against a headless, instrumented class model. It does not reimplement either mixin's branching logic. Its autosave tests execute the actual parsed upstream `do-autosave` method, placed in a small class exposing its original state names and dependencies. File I/O and actual native serialization are deliberately not modeled as successful native operations.

11 test groups pass, including:

1. Full-module parsed-source preservation, with exactly two added guards.
2. Format inputs checked against the exact pinned public `check-format` list: `guess`, `standard`, `text`, `text-force-cr`, `same`, `copy`. No additional formats are claimed as valid public modes.
3. Exact `"1"` opt-in. An absent environment variable, `"0"`, empty string, `"true"`, `"yes"`, and whitespace-padded values remain disabled.
4. 3,456 ordinary scenarios, each run as stock, candidate-off, and candidate-on. Inputs include empty buffers, one/three string snips, and rich snips at the start/middle/end; all six format symbols; original text/standard format; both verification preferences; all three binary dialog responses; both text dialog responses; autosave context on/off; and inner allow/reject.
5. 48 scenarios executing stock `do-autosave`, covering the above content layouts, both original formats, both verification preferences, and allow/reject. The required format-selection scan still runs, chooses text for all-string/empty content and standard for rich content, and restores the original format.
6. 36 injected autosave write-failure cases check original-format restoration.
7. Inner can/on/after hook exceptions retain their failures and suppress later work identically in all three variants.
8. Explicit callback counts and exception canaries expose opt-in extension differences.
9. Independent prompt-policy assertions verify conversion, keeping a format, canceling, autosave-context silent cancellation, verification-disabled conversion, and plain-text conversion accept/decline.
10. Inner can-save rejection prevents on-save, serialization, after-save, and cannot be bypassed by the guard.

Default-off event traces match stock exactly in the model. Candidate-on event traces for `same` match stock exactly. For non-`same` formats, ordinary results, format changes, prompts, and hook traces match after excluding the intentionally removed scan events. Those excluded events are tested and reported separately; this is not a claim that all observable behavior is equivalent.

The six format symbols are passed through the modeled hook pipeline. Acceptance by the pinned public checker is source-verified; real public save-file conversion, byte output, contracts, and platform newline handling require the native gate. In particular, a model `serialize` event is only a recorded intended format, not proof of native serialization.

### Honest extension canary

For a copy save of three string snips:

| Variant | `find-first-snip` callbacks | `next` callbacks |
|---|---:|---:|
| Stock | 2 | 6 |
| Candidate disabled | 2 | 6 |
| Candidate enabled | 0 | 0 |

For successful stock `do-autosave`, all-string content has three walks in the stock/off model and one in the enabled model: the required selection walk remains. Rich walks stop at the first non-string snip as stock does. A can-save rejection still leaves the required selection walk plus the stock can-save walk when disabled, and only the required selection walk when enabled.

A custom `find-first-snip` that throws causes the stock/default-off copy-save model to fail; candidate-on no longer calls it there, so that copy succeeds. A custom string snip's throwing `next` method likewise stops the stock/default-off explicit-text model while enabled avoids that callback. All variants still propagate the injected scan exception for `same`.

Thus arbitrary third-party subclasses can observe different callback counts, side effects, and exceptions for non-`same` formats. The experiment must not be advertised as preserving those extension semantics. It has no general cache, no unsafe cached answer, and no removal of required autosave classification, but those facts do not erase the intentional callback difference.

### Reproduction and outputs

Using the provided official runtime and existing isolated profile:

```sh
PLTUSERHOME=/workspace/shared/openracket-drracket-host/profile \
  /workspace/shared/racket-toolchain/racket/bin/racket \
  /workspace/shared/openracket-autosave-guard/tests/independent-model-test.rkt

PLTUSERHOME=/workspace/shared/openracket-drracket-host/profile \
  /workspace/shared/racket-toolchain/racket/bin/raco test \
  /workspace/shared/openracket-autosave-guard/tests/independent-model-test.rkt
```

Standalone output:

```text
CANARY copy/3 string snips: stock/off/on first calls = (2 2 0); next calls = (6 6 0)
11 success(es) 0 failure(s) 0 error(s) 11 test(s) run
Ordinary scenarios: 3456; actual stock do-autosave scenarios: 48
```

The `raco test` entry point also reports `11 tests passed`. The generator owner's five Python source-integrity tests were independently rerun and pass; they are not counted as independent test authorship.

## Separate native acceptance gate: PREPARED, UNRUN

`tests/independent-native-save-recovery.rkt` is a native-only fixture. It has been read successfully by Racket's parser only. It has not been expanded, compiled, required, or executed against GUI libraries. API binding, class composition, platform behavior, and actual assertions are consequently not yet verified.

The fixture exposes `run-independent-native-save-check!`, intended to be invoked on a fresh disposable DrRacket frame's GUI handler thread in each of three separate controlled processes: `stock`, `candidate-off`, `candidate-on`. It checks the actual loaded module's activation export, asserts the pinned fresh-stock `framework:verify-change-format = #f` default without changing any preferences, refuses a nonempty/named working buffer, and writes only to its new temporary fixture directory. It does not install or select the overlay itself.

Prepared assertions cover:

- Ordinary same-format plain save, byte fidelity, standard-to-text conversion, modified-state reset.
- Plain copy, byte fidelity, unchanged original filename and modified state.
- Rich same-format save, required text-to-standard conversion, WXME marker, exact bitmap pixels and nested-editor text on reload.
- Rich copy and reload, unchanged original filename and modified state.
- Actual `do-autosave` for plain and rich buffers with deliberately opposite original formats, resulting recovery-file format, reload payload fidelity, and restoration of original format/name/modified state.
- Native inner can-save rejection, absent later save hooks, and no destination file creation.

The artifact-reload checks are **not crash/restart recovery-dialog coverage**. The fixture explicitly prints that the latter gate remains unrun.

Further required native gates before any positive preservation/performance conclusion:

1. As a separate alternate-settings gate, exercise the real DrRacket save dialogs in all three isolated modes under identical explicitly verification-enabled preferences: rich text-to-binary convert/keep/cancel; plain binary-to-text yes/no; and autosave silent behavior. Preserve screenshots, selected choices, and resulting formats. The stock fresh-profile default is verification disabled (`#f`); do not compare differently configured preferences or describe the baseline fixture as disabling a normally enabled prompt.
2. Exercise real public save-file modes `guess`, `standard`, `text`, and `text-force-cr` in addition to the prepared `same` and `copy` paths. Compare bytes and reloads with stock, recognizing that explicitly requested text output of rich content retains stock's potentially lossy behavior rather than promising WXME preservation for that output mode.
3. In a disposable native process/profile, create plain and rich unsaved changes, force genuine autosave and its recovery metadata, then perform an explicitly authorized crash/restart flow. Use the real recovery UI to recover both files; compare Unicode text, nested editor content, and bitmap bytes. Verify original files remain untouched and canceled recovery behaves like stock. Creating recovery artifacts or calling `load-file` alone is insufficient for this gate.
4. Validate actual loaded candidate identity and activation independently of the environment string, then measure a prespecified fragmented-buffer autosave workload. Include correctness failures, baseline noise, scan counts and elapsed timings; do not call reduced model callback counts a measured latency benefit.

The candidate remains an isolated, default-off source experiment pending these gates.

## Native caller prepared for the next controlled batch

`tests/independent-native-autosave-host.rkt` now provides the actual native caller. It follows the proven retained-host startup pattern: permanent argument clearing before `drracket/drracket` is dynamically required on the GUI thread, then waits for the genuinely shown DrRacket frame and verifies the registered frame/editor identities. It never substitutes an evaluator or editor for that real-frame fixture.

A source review of the pinned Framework default found `framework:verify-change-format` is already `#f`. The caller reads/logs/asserts that fresh-stock value and performs **no preference mutation**. Earlier discussion about setting this preference was corrected before the caller was prepared. Verification-enabled dialogs are an alternate-settings gate, not an omitted stock-default prompt.

Caller contract:

```text
racket tests/independent-native-autosave-host.rkt stock
racket tests/independent-native-autosave-host.rkt candidate-off
racket tests/independent-native-autosave-host.rkt candidate-on
```

Each command requires a separate process and fresh absolute `PLTUSERHOME`, with no existing preference file or caller claim file. Use the stock full official Racket 9.3 runtime for `stock`; use separate deep copies with only the save-scan overlay for the two candidate modes. Candidate-on alone must have `OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1`; that variable must be absent for stock/off. The following must be absent in every process: `OPENRACKET_ALL_STRING_FAST_PATH`, `OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS`, `OPENRACKET_HOST_THEME`, `OPENRACKET_THEME`, and `OPENRACKET_UI`. An external timeout of at least 200 seconds should bound each process; the caller has a 180-second watchdog and shorter per-stage GUI/frame bounds.

Before startup it records resolved source paths and exact SHA-256 values for the save overlay/stock source, unchanged editor-misc and native editor, and stock color, DrRacket unit, and switchable-button modules. It rejects mismatches. After startup it verifies the live module activation export and runs a separate native callback-count canary on the actually loaded mixin. These checks are correctness-only and are not part of the separate performance harness.

The fresh frame must be unnamed and `still-untouched?`. The only nonempty contents the caller will clear are the exact preferred starter text determined by the same two stock preferences used by pinned `insert-auto-text`. Unknown or edited contents fail closed with diagnostics. It then invokes the real save/artifact fixture on the frame's own handler thread, followed by the independently prepared `tests/review-native-save-failure.rkt` fixture. That additional fixture covers four actual directory-target write failures and retries (plain/rich × copy/same), hook order and failure status, original sentinel bytes, filename/modified state, stock pre-write format conversion, and successful artifact reload.

Success emits `OPENRACKET_AUTOSAVE_CORRECTNESS` JSON with mode, scope, source evidence, both temporary evidence directories, and explicit unrun verification-enabled-dialog and crash/restart-dialog fields. Failure prints actual bounded frame/editor/window/dialog labels and exits nonzero; it does not blindly dismiss dialogs. The final watchdog also exits nonzero.

`tests/independent-native-caller-contract-test.rkt` executes the actual parsed caller dispatch and frame-wait helpers with headless dispatch substitutes. Four groups pass: value/error forwarding, unresponsive-callback timeout, frame poll success/timeout, and permanent argument clearing/no preference-setting code. Combined with the model suite, `raco test` reports **15 tests passed**. These helper tests are not native GUI validation. The caller and native fixtures remain reader-checked only and were not locally required, expanded, or executed. No installation, display access, network, or remote publication was performed during preparation.

The prepared artifact gate now also reads the actual fresh-profile recovery TOC immediately after each plain/rich autosave and requires the exact two-element original-path-bytes/autosave-path-bytes mapping. This strengthens artifact/recovery-metadata coverage without claiming crash/restart UI parity. The caller additionally pins unchanged `framework/private/autosave.rkt` (`db156fe925d2372bcfadac91abe8be5568b68bea52c1cacd73264bdf548c9f9f`) and `framework/private/path-utils.rkt` (`86d73bed097739a1098ae7957c831bbdfbeee3eb2c7f82c43901b5cc50325c93`) against the exact cached 9.3 sources reviewed.

### Required native CI preparation

On the authorized native runner, after preparing each isolated full runtime and before that arm's correctness run, explicitly compile **all three** runnable modules with that arm's `raco`. The two fixture modules are dynamically required, so compiling the caller alone does not establish their compile gate:

```sh
"$RACO" make \
  "$AUTOSAVE_ROOT/tests/independent-native-autosave-host.rkt" \
  "$AUTOSAVE_ROOT/tests/independent-native-save-recovery.rkt" \
  "$AUTOSAVE_ROOT/tests/review-native-save-failure.rkt"
```

Keep this preparation profile separate from each run's empty `PLTUSERHOME`; compilation must not seed the run's preference file or caller claim. Rebuild the changed Framework source/dependencies in the selected candidate runtime using the runner's normal managed compilation preparation. At execution, source hashes plus the live loaded-module flag/callback canary remain mandatory and catch a stale or misselected implementation. The source-only environment used for preparation here has not executed this native compile command.
