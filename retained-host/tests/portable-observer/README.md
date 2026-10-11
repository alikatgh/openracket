# CI-only real-launcher observer

This package is a disposable acceptance tool, not part of the shipped appearance tool or an alternate application entrypoint. Register it as `openracket-portable-observer` only in the proof-local addon after the real setup script succeeds. Use the same isolated compiled roots as the launcher. The CI owner controls installation and OS capture.

The tool is inert unless `OPENRACKET_PORTABLE_FIXTURE` is set. It does not run setup, start DrRacket, open a file, invoke an editor/control callback, change preferences/content/geometry, or set native appearance. It observes the frame produced by the actual `launch-openracket.sh` or `launch-stock.sh` invocation. Its native adapter use is read-only inspection, without capture/set/restore calls.

## Explicit launch contract

Supply these environment variables for each fresh process:

- `OPENRACKET_PORTABLE_FIXTURE`: absolute path of an existing synthetic UTF-8 `#lang racket/base` fixture, at most 20,000 characters. Pass that same path as the real launcher's file argument.
- `OPENRACKET_NATIVE_READY_FILE`: absolute, absent output path in an existing writable CI evidence directory.
- `OPENRACKET_NATIVE_CAPTURE_DONE`: absolute, absent path the capture runner creates after finishing its OS screenshot.
- `OPENRACKET_PORTABLE_EXPECT_UI`: exactly `modern` or `stock`.
- `OPENRACKET_PORTABLE_EXPECT_SAVE_GUARD`: exactly `1` or `0`, independent of the flag actually loaded by the app.
- `OPENRACKET_PORTABLE_EXPECT_MEMORY_MIB`: a decimal integer at least `8`, or exactly `unlimited`. This is a required, independent assertion input, not a launcher configuration option. Missing values, signs, fractional/exponent/radix notation, whitespace and alternate unlimited spellings fail configuration. Decimal leading zeroes are accepted.

Three intended macOS processes:

1. Real modern launcher, `OPENRACKET_THEME=dark`, expected UI `modern`, expected guard `1`, expected memory `256` for a fresh preview profile. The launcher supplies its macOS native-appearance default; actual Cocoa DarkAqua and painter blending must be observed.
2. Real modern launcher with `OPENRACKET_AUTOSAVE_GUARD=0`, the same modern profile, expected UI `modern`, expected guard `0`, expected memory `256` when the profile's value remains unchanged.
3. Real stock launcher, expected UI `stock`, expected guard `0`, expected memory `128` for a fresh stock profile. It must use its separate stock preferences, original schemes, inherited native appearance and disabled modern painter/blending. For an existing stock profile, supply its original or deliberately seeded user-chosen memory value instead of assuming `128`.

Give each process unique ready/done paths. Do not set the fixture variable for unrelated save/performance callers; they must not activate this observer. This gate is intentionally Cocoa-specific.

## Assertions and bounded capture

The observer requires the genuine registered frame, editors and canvases, exact canvas/editor identity, exact argv-opened filename and Unicode contents, unmodified buffer, original menus/tabs, retained native toolbar classes and localized Check Syntax/Debug/Macro Stepper/Run/Stop ordering. Ordering respects the stock panel orientation.

Modern mode additionally requires both OpenRacket schemes, committed dark preference, actual painter synchronization, verified native blending, the stock panel-dark predicate and actual app-local/effective DarkAqua. Stock mode verifies the corresponding appearance features are inactive without requiring a particular OS light/dark setting.

Every genuine frame inspection reads `preferences:get 'drracket:child-only-memory-limit` from the running launcher's registered preference system. The original Racket 9.3 `drracket/private/eval-helpers-and-pref-init.rkt` registers this exact key with a default of `134217728` bytes and permits `#f` or exact integer bytes at least `8388608`. `drracket:memory-limit` is not this registered key. The observer never registers a default, supplies a fallback, sets a preference, or changes a custodian limit.

The effective preference must have the original accepted type and match the independently supplied expectation exactly. The success JSON's `memory_limit` object reports `preference_key`, `expected_bytes`, `effective_bytes`, `observation` and `worker_cap_measured: false`. A `256` expectation means exactly `268435456` bytes; `unlimited` means Racket `#f`, serialized as JSON `false`, never null or a string. Mismatch diagnostics retain the actual value. This is evidence of the effective registered preference in the genuine GUI process. It does not by itself measure a background worker's live custodian cap or prove successful expansion under that cap.

Source hashes prove the original colorer (20 ms stock budget), DrRacket unit and memory preference registration module remain unchanged, the exact measured autosave guard is installed, and no snip-scan helper is installed. The live loaded guard must match the separate expected value.

After three successful 100 ms timer observations of the same frame, the tool emits `OPENRACKET_NATIVE_RESULT`, writes the ready JSON and emits `OPENRACKET_NATIVE_READY`. Failures publish bounded title/widget/editor diagnostics with `OPENRACKET_NATIVE_FAILURE_READY`; unknown dialogs are never dismissed. No content/settings mutation occurs before or after capture.

Readiness has a 60-second limit. After publication, the observer waits at most 20 seconds for the done file, then exits. Missing acknowledgment makes an otherwise successful observation fail. A 90-second process watchdog provides an additional bound; the external CI runner should also use a process-group timeout.

## Current validation

The earlier observer passed a reader check and six GUI-free contracts before this memory extension. The updated files add strict memory parsing, original-key lookup, exact/type-preserving equality, malformed/missing preference failures, JSON roundtrips, and source integration/read-only contracts. They retain the opt-in and READY/capture control tests. The new Racket tests and native extension have not been executed in the editing environment, which has no Racket executable or native GUI. Native expansion, package discovery, real launcher startup and capture require CI. This observer does not establish full DrRacket feature parity.

Run the GUI-free contracts with Racket 9.3:

    raco test tests/portable-observer-contract-test.rkt tests/portable-memory-observer-test.rkt

In CI's installed isolated addon/compiled-root environment, compile the actual tool:

    raco make tests/portable-observer/tool.rkt

Then register it in that proof-local addon and launch the real scripts using all required variables above. The observer must run inside each launcher-created process; executing the parsed GUI-free functions cannot replace this gate. Keep the existing OS screenshot, unique ready/done paths, acknowledgment and process-group timeout for every native case.

The memory acceptance matrix should cover:

- Fresh preview initialization: expected `256`; guard-on and guard-off keep the same memory expectation.
- Explicit preview `128` and another custom value such as `384`: expected values remain independent CI literals.
- Existing preview custom or unlimited setting without a new explicit override: expected existing value, including `unlimited` for `#f`.
- Stock launch after preview initialization and explicit overrides: expected original stock value (`128` only for a fresh stock profile), including a pre-existing custom or unlimited stock value.
- Preview restore: expected original preview value after the supported restore action; a later no-override launch must not silently reapply `256`.
- Wrong expected value: no success READY marker; a bounded failure must identify the observed and expected values.

The setup/restore or CI fixture harness owns any profile preparation. This observer performs none of it. CI should also compare the separate stock preference bytes before/after preview actions to establish profile isolation; reading the in-process value alone cannot establish that no other file changed.
