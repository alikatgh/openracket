# OpenRacket

A focused native Racket editor, written in Rust. Familiar Definitions above, Interactions below, with quieter chrome and the **real Racket runtime** underneath.

This is an early working preview, not a full DrRacket replacement. It uses Iced 0.14, native text editing, and a separate Racket process. There is no webview, AI service, or interpreter reimplementation.

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

Native file dialogs use the desktop's XDG portal. Ensure the portal backend for your desktop is installed and running. No GTK build dependency is required. The separately tested Linux x86_64 review binary requires glibc 2.39 or newer; this repository contains source only, so build locally for your distribution. Release builds were compiled and inspected on Linux x86_64; the verification environment has no desktop session, so OS windowing, clipboard and file-dialog integration remain manual checks.

### macOS

Install Apple's command-line build tools and Rust, then install Racket from its official macOS download. In a terminal:

```sh
xcode-select --install
cargo build --release --locked
RACKET_BIN="/Applications/Racket v9.3/bin/racket" ./target/release/openracket
```

The source uses cross-platform Iced and native file dialogs. **macOS compilation, native window behavior, signing, notarization and app-bundle packaging have not been tested.** This repository contains source only; no downloadable Mac app or release is included. A [manual build-only workflow](docs/macos/BUILD-PLAN.md) is prepared for Apple Silicon macOS, but it has not been run and does not retain a downloadable app.

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

The ignored Rust tests require a real Racket executable. See the [recorded Linux QA report](qa/RESULTS.md) for the exact commands and checks actually run. These are pre-publication local results, not a GitHub CI pass. Native-widget screenshots are rendered by the actual Iced/tiny-skia widgets without a window. They validate layout and in-process event dispatch; they do not establish OS focus, clipboard, dialogs, compositor performance or macOS support.

Performance records distinguish process-level timing, native widget/model work, and untested end-to-end OS behavior. There is no measured speedup claim against DrRacket.

## Source layout

- `src/app.rs`: Iced application, UI and session state
- `src/document.rs`: editing, changed-line history, search, source locations
- `src/files.rs`: UTF-8 validation, atomic saves, external-change protection
- `src/runtime.rs`: asynchronous process supervisor and bounded protocol transport
- `runtime/bridge.rkt`: actual Racket reader/evaluator and operation control
- `qa/`, `tests/`, `runtime-tests/`: independent checks, captures and benchmarks

## License

Original OpenRacket code is MIT licensed. Font licenses are included in `assets/FONTS-LICENSE.txt`. See `THIRD_PARTY_NOTICES.md` for the main dependencies. This project is independent of the official Racket/DrRacket project and does not reuse DrRacket or OpenCode UI source.
