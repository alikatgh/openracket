# OpenRacket validation report

Validated on 10 October 2026 in a Debian 13 Linux cloud executor, with Rust 1.94.0 and Racket 9.3 CS. This report separates actual execution from source inspection and untested desktop integration.

## Outcome

The plain-text Racket editor core has been exercised through independent model tests, native Iced widget-event tests, real Racket black-box tests, and an application-to-supervisor-to-Racket end-to-end flow. Actual native widgets are rendered with Iced's supported in-process tiny-skia renderer. This does **not** establish full DrRacket parity or completion of macOS/Windows desktop validation.

Final aggregate: **55 ordinary Rust tests passed** (30 library, 17 binary/widget, 8 independent file/model tests). All **3 real-Racket supervisor tests** and the **real application end-to-end test** were then enabled explicitly and passed. The **17 independent Python runtime scenarios** passed in 10.56 seconds against the final bridge. The ignored release benchmark was run separately in optimized mode. No failed checks remained in the recorded local run. Raw logs and generated screenshots are not included in this source-only repository; the reproduction commands below generate fresh evidence. This is not a GitHub CI result.

The checked source identities are recorded in `qa/tested-source-sha256.txt`; all entries were reverified after the final run.

### Independently verified

- Current unsaved Definitions execute without overwriting a file. The resulting module namespace remains available to subsequent Interactions.
- Repeated Run resets prior interaction bindings and resolves relative imports and runtime paths from the module's source path, including Unicode and space-containing paths.
- Reader completion is checked by real Racket. Incomplete input remains editable. Reader-check completion is awaited before evaluation, and edits made during a check are retained.
- Real stdin and EOF are separate from protocol traffic. Infinite loops, disabled breaks, output floods and large single writes are bounded/cancellable. Reset terminates a managed child process.
- Background-thread output remains visible after a foreground operation completes, while output from a previous Run is rejected after a new namespace starts. Force stop clears accepted output ownership.
- Stale operation output and completion cannot replace a newer run. Switching tabs preserves diagnostic ownership. Interaction errors do not jump into the wrong Definitions buffer.
- Absolute Racket source positions correctly handle tabs, CJK, emoji, CRLF and multiline spans. Stale diagnostic locations are refused after edits.
- Cancelled or failed saves retain dirty text; an unrelated async save cannot close another dirty tab. Modal shortcuts cannot silently change the close target.
- File round trips preserve UTF-8 and CRLF bytes. External disk changes are detected. Symlink opens share canonical identity. Plain text that merely mentions `WXME` is accepted, while rich files are rejected explicitly.
- An 800-step deterministic randomized edit sequence covers insert, delete, paste, multiline selections, Unicode, combining marks, indent/unindent, undo and redo. Text, cursor, selection and revision round trips are checked.
- Native widget events exercise Definitions typing and undo, save/run shortcuts, focused Interactions undo, plain Enter submission, Shift+Enter newline, and ordinary Definitions newline. Mouse-wheel events change the actual rendered output viewport.
- A real end-to-end app test covers Run, reader check, persistent evaluation, incomplete input, Break and evaluation after Break. Oversized host/bridge requests are tested for recoverable idle state.

### Defects found and fixed during acceptance

1. Reader-check/evaluation race and Run overlap during a pending check.
2. Async save completion potentially continuing the wrong dirty-close request.
3. Keyboard actions changing a document behind the dirty-close modal.
4. Diagnostics jumping to the wrong file or using stale/tab-expanded offsets.
5. Ordinary source mentioning WXME falsely rejected as rich content.
6. Upstream unindent cursor underflow when the cursor was inside indentation. OpenRacket uses a guarded line-local implementation.
7. Unfocused custom editor shortcuts stealing another pane's commands.
8. Failed runtime submissions leaving a fabricated busy state or changing session identity before Run was accepted by Racket.
9. Current-session background-thread output being incorrectly discarded after operation completion.

## Evidence and reproduction

Set up the documented Rust and Racket dependencies, then run from the repository root:

```sh
cargo test --lib --tests -- --test-threads=1
RACKET_EXECUTABLE=/path/to/racket cargo test --lib real_racket -- --ignored --test-threads=1
RACKET_EXECUTABLE=/path/to/racket cargo test --bin openracket qa_real_app -- --ignored --test-threads=1
RACKET=/path/to/racket python3 qa/test_runtime_adversarial.py
cargo test --bin openracket capture_native_ui -- --test-threads=1
cargo test --release --bin openracket qa_benchmark -- --ignored --nocapture --test-threads=1
```

- `tests/qa_document_acceptance.rs`: independent file/model acceptance, including 800 edit round trips.
- `qa/offscreen.rs`: actual native widget snapshots, app-state regressions, widget-event workflows, real app/runtime flow and release benchmark.
- `qa/test_runtime_adversarial.py`: 17 bounded black-box runtime scenarios. The final independent pass passed in 10.56 seconds. A separate additional local rerun also passed.
- The capture tests generate `qa/screenshots/` with dark/light welcome, populated editor, compact editor and error states. `editor-real-run.png` is populated by the actual app-to-Racket test; the other screenshots use explicit fixture state rendered by production widgets. These generated images are excluded from source publication.

## Release performance sample

The following measurements were recorded by the local release benchmark. Re-run the benchmark above to produce fresh raw measurements.

| Operation | Measured result | Samples |
| --- | ---: | ---: |
| Load 1,091,513-byte / 18,501-line source into the model | 393.85 ms | 1 |
| Insert Unicode character and undo it in that buffer | 0.243 ms median; 0.274 ms p95 | 200 |
| First 1280 × 860 native layout, draw and CPU raster | 392.63 ms | 1 |
| Warm unchanged-view layout, draw and CPU raster | 6.74 ms median; 7.53 ms p95 | 20 |

These measurements include model work or CPU rendering as labeled. They do not include a live OS window, compositor, input device latency or perceived responsiveness. The warm rendering sample does not edit between frames. No comparative claim against DrRacket or macOS performance is made. Initial-load costs are reported alongside warm operations.

## Still unverified or outside this MVP

- No actual OS window was launched. Native file-picker/Save As/overwrite dialogs, window focus, clipboard integration, IME, accessibility, HiDPI, installation and signing need desktop validation.
- macOS and Windows builds and behavior are not validated by these Linux results.
- Full default-DrRacket parity is not claimed: teaching-language tooling, Check Syntax, macro stepper, debugger, rich WXME editors, images/snips and plugins are outside the current plain-text MVP.
- Runtime source may use trusted local files and processes. A separate process is crash isolation, not a security sandbox for untrusted Racket programs.
- Source inspection and state-model tests verify the dirty-save flow; they do not substitute for exercising native dialogs on the target OS.

See `ACCEPTANCE.md` for the wider release acceptance matrix and official Racket behavioral references.
