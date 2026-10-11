# OpenRacket

An experimental project to update DrRacket’s interface while retaining its editor and tools.

## Current work and measured results

Current development is the [retained DrRacket 9.3 host](https://github.com/alikatgh/openracket/tree/prototype/retained-drracket/retained-host) on `prototype/retained-drracket`. It keeps the genuine DrRacket editors, tools and evaluator. The Rust/Iced application preserved on `main` is an earlier, separate preview; its build instructions follow below.

Verified milestones, recorded 2026-10-11:

- **Native Mac app launch passed:** all **114 app checks** in [run 38127332821](https://github.com/alikatgh/openracket/actions/runs/38127332821) passed, including nine native window/file states, cold and warm Unicode file opening, app-only relocation, and unchanged original runtime/preferences. The [Racket-only builder](https://github.com/alikatgh/openracket/tree/dae4b69d34a793404f1e8ddf35a65948d33ae980/retained-host/experiments/mac-app-builder) creates the app on the destination Mac and needs full official Racket 9.3 plus the prepared source/profile at fixed paths. It is tethered, unsigned and not notarized; transferred-app Gatekeeper behavior remains unverified. The runner’s existing Script Editor file association was preserved; an initially unset handler was not tested. The overall CI run is red because a separate tool-test negative-control diagnostic omitted required exception details; its six tool cases did not run. This is launch acceptance, not a new speed result or full tool parity.
- **Fresh-profile capacity:** a new isolated preview profile now defaults to a **256 MiB per-job memory limit**. In a separate stock-host 1 MiB workload experiment, 128 MiB ended out of memory in **3/3 trials**; 256 and 512 MiB each completed final background analysis in **3/3**. 256 MiB was the smallest tested adequate limit, not a universal guarantee. The final tool callback still took 33.222–39.155 seconds at 256 MiB, and whole-process peak RSS was 1.487–1.543 GB. This is a capacity fix, not a code-speed result. [Nine-trial report](https://github.com/alikatgh/openracket/blob/80e51d78526d718a50c45f3662058a042c3038f7/retained-host/reports/PERFORMANCE-MEMORY-38107957744.md).
- **Mac capacity-default installation passed:** [run 38114573816](https://github.com/alikatgh/openracket/actions/runs/38114573816) is fully green. Eight real launches verified the fresh 256 MiB default, autosave opt-out, restore to 128 MiB, explicit 128/384 MiB choices, repeated-setup preservation, and separate stock-launcher 128 MiB behavior. Save/recovery regression checks and both original-runtime tree comparisons passed. Existing profiles keep their settings; the preference affects Run and background analysis, not the whole application's RAM ceiling.

- **Mac autosave:** for a 1 MiB fixture, three matched replacement-save pairs measured actual synchronous autosave command medians of **266.735 → 172.400 ms**, a **35.4% reduction between arm medians**. Individual paired reductions were 19.1–42.8% (median paired reduction 24.6%). The queued GUI callback delay median fell from 268.036 to 173.187 ms. Exact source/recovery, activation and settings checks passed. [Measurement report](https://github.com/alikatgh/openracket/blob/prototype/retained-drracket/retained-host/reports/PERFORMANCE-AUTOSAVE-38061486888.md) · [test run](https://github.com/alikatgh/openracket/actions/runs/38061486888).
- **Earlier Mac source installation:** actual setup, default/guard-opt-out/stock launchers, combined appearance-plus-autosave save/recovery, and original-runtime preservation gates passed in [run 38064415026](https://github.com/alikatgh/openracket/actions/runs/38064415026). [Installation report](https://github.com/alikatgh/openracket/blob/b22ced970504e53eb1012c91f6b355e1b4d5dddd/retained-host/reports/PORTABLE-INSTALLATION-38064415026.md). The overall run failed in an independent expansion-replay preparation test; the replay did not run. This is a source installer requiring the full official Racket 9.3 distribution, not a signed or packaged Mac app.
- **Mac appearance:** the app-local appearance and exact-restoration gate passed in [the macOS job of run 38055256934](https://github.com/alikatgh/openracket/actions/runs/38055256934). The Linux job in that run failed a separate preservation gate.

These are scoped results, not full DrRacket parity or an overall editor speedup. Only three autosaves per arm were timed. In the earlier autosave experiment, initial Mac lexer-validity waits were about **34–40 seconds**, peak memory was essentially unchanged, and large GC pauses remain unresolved. Combined appearance-plus-autosave performance has not been retimed. The original 20 ms lexer budget is retained; the 8 ms experiment was rejected and the separate scan shortcut is not enabled. Windows is untested.

[Current installation and opt-outs](https://github.com/alikatgh/openracket/blob/prototype/retained-drracket/retained-host/PORTABLE-CANDIDATE.md) · [Plain project website source](website/index.html) · [Changelog](website/changelog.html) · [Technical blog: capacity and autosave measurements](website/blog.html)

## Earlier Rust editor preview

The remaining sections describe the application source on `main`: a native Rust/Iced 0.14 editor using a separate real Racket process. It is an early preview with incomplete DrRacket coverage. There is no webview, AI service, or interpreter reimplementation.

## Build and run

Requirements:

- Rust **1.94.0** (pinned in `rust-toolchain.toml`; install through [rustup](https://rustup.rs/))
- A local [Racket installation](https://download.racket-lang.org/), with Racket **9.3 CS** used for verification
- A graphical desktop session to launch the window

```sh
cargo build --release --locked
RACKET_BIN=/absolute/path/to/racket ./target/release/openracket
# Or, when racket is on PATH:
./target/release/openracket examples/welcome.rkt
```

The Racket bridge and UI fonts are embedded in the executable. The bridge is extracted into a temporary directory for a session and cleaned up afterward. The binary does not depend on this checkout or its build directory.

OpenRacket looks for `RACKET_BIN`, then `racket` on PATH, then conventional macOS Racket/Homebrew locations. You can change the executable in the gear-menu Runtime settings. Theme, font size, runtime path, wrapping and sidebar visibility are saved in your standard user configuration folder after explicit changes. `RACKET_BIN` overrides the saved runtime path on launch. Corrupt or unwritable configuration falls back gracefully with a visible warning; source buffers are never stored in this settings file.

### Linux

The default build uses the native Iced software renderer, with X11 and Wayland support. Typical Debian/Ubuntu build prerequisites are:

```sh
sudo apt install build-essential pkg-config libx11-dev libxkbcommon-dev libwayland-dev
```

Native file dialogs use the desktop's XDG portal. Ensure the portal backend for your desktop is installed and running. No GTK build dependency is required. The separately tested Linux x86_64 review binary requires glibc 2.39 or newer; this repository contains source only, so build locally for your distribution. Compilation and real-runtime checks passed on Linux and macOS in the preserved-preview CI run linked below. OS windowing, clipboard and file-dialog integration remain separate manual checks.

### macOS

Install Apple's command-line build tools and Rust, then install Racket from its official macOS download. In a terminal:

```sh
xcode-select --install
cargo build --release --locked
RACKET_BIN="/Applications/Racket v9.3/bin/racket" ./target/release/openracket
```

The source uses cross-platform Iced and native file dialogs. macOS compilation and real-runtime checks passed in [preserved-preview CI run 38050843404](https://github.com/alikatgh/openracket/actions/runs/38050843404). This does not verify native window behavior, signing, notarization or app-bundle packaging. This repository contains source only; no packaged Rust Mac app is included. The [build-only plan](docs/macos/BUILD-PLAN.md) remains background documentation.

## The workflow

1. Open a UTF-8 `.rkt` file, make a new one, or try the included example.
2. Include an explicit language declaration such as `#lang racket`.
3. **Run** evaluates the current buffer, including unsaved edits. It resets the session namespace and uses the saved file's directory for relative imports. Untitled buffers use the workspace folder.
4. Type expressions in **Interactions**. Press **Enter** to submit when the Racket reader says the input is complete; incomplete input continues onto a new line. **Shift+Enter** always inserts a newline. **Ctrl/Cmd+Enter** is an alternative submit shortcut.
5. **Break** interrupts execution without blocking editing. An independent hard-stop fallback terminates an unresponsive process group. **Force stop** is available while running.

When a buffer has no language declaration, OpenRacket offers **Add #lang racket**. It never inserts that declaration automatically or silently changes languages.

The interactions header names the file whose namespace is active. Switching tabs does not silently switch runtime sessions. A status message indicates when definitions have changed since the last Run. Run the desired tab to replace the session.

## Editing and files

- Native selection, clipboard shortcuts, Unicode text, multiline editing and word navigation
- Separate undo/redo histories per definitions tab and interactions input
- Changed-line undo deltas, grouped typing, a bounded history budget; no full-file history clone on every keystroke
- Case-sensitive literal search with wrap-around and native editor selection
- Tabs with dirty indicators; Save/Discard/Cancel guards on dirty tab/window close
- Asynchronous file operations and same-directory atomic saves; existing external file changes block overwriting
- UTF-8 plain text, preserving existing line endings
- Read-only/selectable output; reader errors and runtime diagnostics with source-aware navigation
- Collapsible workspace list, resizable vertical split, light/dark appearance and adjustable editor font size

Workspace listing currently shows Racket/Scheme files directly inside one folder. Recursive project trees, file watching, project-wide search, session persistence and crash recovery are not included.

Files up to 16 MiB can be opened. The runtime bridge accepts source up to 2,097,152 Unicode characters; serialized request frames are also capped at 8 MiB, including JSON encoding. A larger file may be editable but too large to Run in this preview. The application reports rejection and preserves the buffer. Output is bounded in the runtime, supervisor and UI to keep runaway output from exhausting memory.

### Shortcuts

| Action | Windows/Linux | macOS |
|---|---|---|
| New / Open / Save | Ctrl+N / O / S | Cmd+N / O / S |
| Save as | Ctrl+Shift+S | Cmd+Shift+S |
| Close tab | Ctrl+W | Cmd+W |
| Run | Ctrl+R or F5 | Cmd+R or F5 |
| Break | Ctrl+. | Cmd+. |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z | Cmd+Z / Cmd+Shift+Z |
| Find | Ctrl+F | Cmd+F |
| Toggle workspace | Ctrl+B | Cmd+B |
| Evaluate interaction | Enter or Ctrl+Enter | Enter or Cmd+Enter |
| Insert interaction newline | Shift+Enter | Shift+Enter |
| Interaction history | Alt+Up / Down | Option+Up / Down |

Ctrl+Y is also accepted for Redo. Clipboard and navigation use Iced's native text-editor bindings.

## Compatibility and safety

Verified baseline: ordinary plain-text `#lang racket` and `#lang racket/base`, exact arithmetic, definitions, multiple values, relative `require`, persistent interaction namespace, errors, input/EOF, repeated Run, and interruption. Installed language modules may work, but this is not a claim of DrRacket-language compatibility.

Not yet implemented:

- DrRacket teaching-language adapters, teachpacks and pedagogical stepper
- Macro stepper, Check Syntax/binding arrows, debugger, profiler and coverage
- DrRacket language configuration/tool hooks and plugins
- WXME, embedded images/snips, rich value renderers and GUI-program integration
- A language-aware Racket lexer/indenter; current syntax coloring uses a generic Lisp grammar
- A synchronized line-number gutter, structural editing or automatic parentheses matching
- Full accessibility/screen-reader validation, IME validation and OS integration QA

Rich WXME and binary files are rejected with an explanation instead of being silently flattened. Detailed runtime boundaries are in [`runtime/PROTOCOL.md`](runtime/PROTOCOL.md).

**Run executes trusted local code with your account's privileges. Process separation is for responsiveness and cancellation; it is not a security sandbox.** Do not run untrusted programs. Force stop discards the current Racket session but leaves source edits intact.

## Verification

```sh
cargo fmt --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked -- --test-threads=1
RACKET_EXECUTABLE=/path/to/racket cargo test --lib -- --ignored --test-threads=1
RACKET_BIN=/path/to/racket python3 runtime-tests/test_bridge.py
RACKET_BIN=/path/to/racket python3 qa/test_runtime_adversarial.py
```

The ignored Rust tests require a real Racket executable. See the [recorded Linux QA report](qa/RESULTS.md) for the exact commands and checks actually run. That report records pre-publication local results. Later, [preserved-preview CI run 38050843404](https://github.com/alikatgh/openracket/actions/runs/38050843404) passed Linux and macOS compilation and real-runtime checks; the run passed 59 Rust tests on each OS, plus 50 Python tests on Linux and 48 on macOS (two Linux-specific checks skipped). These are separate from native retained-host acceptance. Native-widget screenshots are rendered by the actual Iced/tiny-skia widgets without a window. They validate layout and in-process event dispatch; they do not establish OS focus, clipboard, dialogs, compositor performance or macOS support.

Performance records distinguish process-level timing, native widget/model work, and untested end-to-end OS behavior. No Rust-preview speedup against DrRacket is established. The autosave result above belongs only to the separate retained-host experiment.

## Source layout

- `src/app.rs`: Iced application, UI and session state
- `src/document.rs`: editing, changed-line history, search, source locations
- `src/files.rs`: UTF-8 validation, atomic saves, external-change protection
- `src/runtime.rs`: asynchronous process supervisor and bounded protocol transport
- `runtime/bridge.rkt`: actual Racket reader/evaluator and operation control
- `qa/`, `tests/`, `runtime-tests/`: independent checks, captures and benchmarks

## License

Original OpenRacket code is MIT licensed. Font licenses are included in `assets/FONTS-LICENSE.txt`. See `THIRD_PARTY_NOTICES.md` for the main dependencies. This project is independent of the official Racket/DrRacket project. The Rust preview does not reuse DrRacket or OpenCode UI source; the separate retained-host branch patches and uses the original DrRacket host, with its own provenance and licensing notes.
