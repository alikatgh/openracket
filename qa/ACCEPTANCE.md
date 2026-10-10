# OpenRacket acceptance matrix

This is an independent acceptance plan. A checked implementation or unit test is not a claim that a graphical workflow has been exercised. Results and exact commands belong in `RESULTS.md`.

## Release gate

Core claim: a native Rust editor for plain-text Racket, with Definitions and persistent Interactions backed by an actual Racket process. It is not a full DrRacket replacement. Teaching-language tools, macro stepper, WXME, plugins, and macOS behavior require separate verification.

| ID | Priority | Scenario | Required result | Verification |
| --- | --- | --- | --- | --- |
| FILE-01 | P0 | New, open, edit, save, reopen | Bytes and path agree; dirty marker clears only after successful save | UI + disk |
| FILE-02 | P0 | Close dirty tab or quit; cancel | Tab, text, selection, and running session remain intact | UI |
| FILE-03 | P0 | Save to nonexistent/unwritable path; cancel Save As | Actionable failure; no false success or lost edits | UI + headless |
| FILE-04 | P1 | Open same file through relative/absolute or symlink path | Defined tab/path behavior; no silently conflicting saves | Headless + UI |
| FILE-05 | P1 | External modification, CRLF, final newline, UTF-8 | No unannounced destructive normalization; documented overwrite semantics | Disk + UI |
| EDIT-01 | P0 | Insert/delete/select around lambda, emoji, combining marks, CJK | Valid UTF-8; correct cursor/selection and no panic | UI + logic |
| EDIT-02 | P0 | Undo/redo across edit, paste, tab switch, save | Correct text and dirty state; independent tab history | UI + logic |
| EDIT-03 | P1 | Indent selection, newline, scrolling long buffer | Keyboard usable; no misplaced edits; responsiveness measured honestly | UI |
| RUN-01 | P0 | Run modified, unsaved Definitions | Current buffer runs without silently saving; output and origin identify the run | Bridge + UI |
| RUN-02 | P0 | Run twice after REPL definitions | New namespace each Run; prior interaction bindings disappear | Bridge + UI |
| RUN-03 | P0 | Run `(define answer 42)` then query in Interactions | Module namespace accessible and persists across submissions | Bridge + UI |
| RUN-04 | P0 | Run or switch tabs while previous evaluation finishes | Late events never overwrite newer run state/output or wrong tab | UI + logic |
| RUN-05 | P0 | Infinite loop, Break, subsequent interaction | UI remains usable; bounded recovery; explain whether namespace is retained | Bridge + UI |
| RUN-06 | P0 | Disable/handle breaks, then hard stop | Process tree terminates; no orphan or permanently busy UI; Run recovers | Bridge + UI |
| RUN-07 | P0 | Infinite output and large single output line | Bounded retained output and queues; Stop remains usable | Bridge + RSS + UI |
| RUN-08 | P1 | Repeat Run/Stop 20 times; quit during execution | No accumulating children, handles, temp files, or reader threads | Process inspection |
| REPL-01 | P0 | Two sequential definitions and expressions | State persists; values printed once; void suppressed | Bridge + UI |
| REPL-02 | P0 | Incomplete list/string and invalid syntax | Clear incomplete/error state; later valid input still works | Bridge + UI |
| REPL-03 | P0 | Program reads stdin | Separate input route or explicit supported limitation; never protocol corruption | Bridge + UI |
| REPL-04 | P1 | Multiple values, exceptions, stdout/stderr, Unicode | Useful typed output in correct operation; valid protocol | Bridge |
| LANG-01 | P0 | Missing `#lang` | Explicit explanation and opt-in fix; no silent rewriting | UI + bridge |
| LANG-02 | P0 | Reader, expansion, and runtime errors | Correct file/line/column and actionable text; next Run succeeds | Bridge + UI |
| PATH-01 | P0 | Saved buffer with `require "sibling.rkt"`; unsaved edits | Imports resolve from original file directory, not bridge/temp directory | Bridge |
| PATH-02 | P1 | Unsaved new buffer with relative require | Defined working-directory behavior; useful error when unresolved | Bridge + UI |
| PATH-03 | P1 | Runtime path, Unicode filename, spaces in path | No shell quoting bugs; module source retains useful origin | Bridge |
| ENV-01 | P0 | Racket missing or invalid configured executable | Clear install/configuration action; editor still opens | UI + logic |
| UX-01 | P1 | Resize, focus, keyboard shortcuts, contrast | Definitions, Interactions, Run/Break and file status remain legible and reachable | Native screenshots + input |
| PERF-01 | P1 | Release start, Run, REPL, large buffer | Report hardware/environment, sample count and measured metric only | Timed release tests |

## Behavioral references

- [Racket evaluation and loading](https://docs.racket-lang.org/reference/eval.html): source context and load-relative paths matter when reading and evaluating modules.
- [Racket namespaces](https://docs.racket-lang.org/reference/Namespaces.html): a module namespace must be explicitly made available to interactions.
- [Racket reading](https://docs.racket-lang.org/reference/Reading.html): reader exceptions and incomplete input are distinct from successful evaluation.
- [Racket breaks](https://docs.racket-lang.org/reference/breakhandler.html): breaks can be disabled or handled, so a separate hard-stop route is necessary.

## Scope of evidence

Target validation environment is Debian 13 Linux, cloud-hosted. No macOS responsiveness, accessibility, display scaling, IME, or end-user install claims follow from Linux/headless results. Screenshots may establish layout but not perceived latency. Benchmarks must distinguish cold process start, warm REPL, and UI frame latency.
