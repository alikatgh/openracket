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

Three intended macOS processes:

1. Real modern launcher, `OPENRACKET_THEME=dark`, expected UI `modern`, expected guard `1`. The launcher supplies its macOS native-appearance default; actual Cocoa DarkAqua and painter blending must be observed.
2. Real modern launcher with `OPENRACKET_AUTOSAVE_GUARD=0`, the same modern profile, expected UI `modern`, expected guard `0`.
3. Real stock launcher, expected UI `stock`, expected guard `0`. It must use its separate stock preferences, original schemes, inherited native appearance and disabled modern painter/blending.

Give each process unique ready/done paths. Do not set the fixture variable for unrelated save/performance callers; they must not activate this observer. This gate is intentionally Cocoa-specific.

## Assertions and bounded capture

The observer requires the genuine registered frame, editors and canvases, exact canvas/editor identity, exact argv-opened filename and Unicode contents, unmodified buffer, original menus/tabs, retained native toolbar classes and localized Check Syntax/Debug/Macro Stepper/Run/Stop ordering. Ordering respects the stock panel orientation.

Modern mode additionally requires both OpenRacket schemes, committed dark preference, actual painter synchronization, verified native blending, the stock panel-dark predicate and actual app-local/effective DarkAqua. Stock mode verifies the corresponding appearance features are inactive without requiring a particular OS light/dark setting.

Source hashes prove the original colorer (20 ms stock budget) and DrRacket unit remain unchanged, the exact measured autosave guard is installed, and no snip-scan helper is installed. The live loaded guard must match the separate expected value.

After three successful 100 ms timer observations of the same frame, the tool emits `OPENRACKET_NATIVE_RESULT`, writes the ready JSON and emits `OPENRACKET_NATIVE_READY`. Failures publish bounded title/widget/editor diagnostics with `OPENRACKET_NATIVE_FAILURE_READY`; unknown dialogs are never dismissed. No content/settings mutation occurs before or after capture.

Readiness has a 60-second limit. After publication, the observer waits at most 20 seconds for the done file, then exits. Missing acknowledgment makes an otherwise successful observation fail. A 90-second process watchdog provides an additional bound; the external CI runner should also use a process-group timeout.

## Current validation

The module has passed a reader check. Six GUI-free tests execute its actual parsed opt-in, JSON and timer/capture control logic, and verify the absence of content/settings/appearance mutations. Native expansion, real package discovery, launcher startup and capture still require CI. This observer does not establish full DrRacket feature parity.
