# Mac light tools and Quit acceptance

The retained OpenRacket preview passed the tested light-mode Debugger, Macro Stepper and teaching-language workflows, plus clean Quit and unsaved-document Cancel, Save and Don't Save paths. All 12 genuine native cases completed against their stock controls. This run adds functional evidence for the existing preview; it introduces no performance optimization or new distributable app.

## Recorded run

- [GitHub Actions run 38154975508](https://github.com/alikatgh/openracket/actions/runs/38154975508), job `114515974625`, conclusion `success`.
- [Source commit](https://github.com/alikatgh/openracket/commit/96fe2b7f3c614f48a840881b02639f8161f96c38): `96fe2b7f3c614f48a840881b02639f8161f96c38`.
- Official Racket 9.3, native Apple Silicon, standard public macOS runner.
- 204 recorded result rows passed: 90 light/tools rows and 114 Quit rows. These include preparation, source validation, negative controls, native cases and preservation witnesses; they are not 204 distinct user workflows.
- Raw `macos.log` SHA-256: `d33aecee2346305486bf20a55b10a3ae9c298da9f97c4ad78635c079ed062e76`.
- Source freezes: light `1553` manifest `57f3f084869ee1d2907c25dce06a23885f650cc3908a49b3091de6566b404c03`; Quit `1552` allowlist `b4560ffb7831a28c51d378d78da96e5695643e01857f8753a8dda0c312a684a4`.

The accepted preview core, official native app builder and performance experiment settings were unchanged. The test-only revisions supplied a missing diagnostic import and checked actual GUI activation before calling the installed Quit handler. The combined workflow kept independent preparation/results, durable process-cleanup refusal and unconditional final preservation checks.

## Light mode with real tools

Each tool ran in a fresh stock process and a separate modern-light process. The case configuration retained the stock 128 MiB fresh-profile default, also visible in all six final tool screenshots. Light's READY schema does not include an effective-memory field, and this run does not measure an evaluator's enforced cap.

- **Debugger:** reached the fixture's real suspension, with program counter 60 and source range `[60,68]`; real Step changed the observable state to counter 36/range `[36,42]`. Resume completed, and ordinary Run worked afterward.
- **Macro Stepper:** navigation moved from Start 0 to Next 1 and End 82; Previous and Start were verified, the derivation changed, normal close completed, and ordinary Run recovered.
- **Teaching tests:** the real report showed two tests with one failure, actual 3 versus expected 4. The source link selected the exact character range `[77,102]`. Correcting the unsaved buffer and rerunning produced two passes, zero failures, and replaced the inline failure report while retaining the intended editor/focus state.

The modern cases reported the applied light appearance both immediately before and after each tool body. These observations included Framework background RGB `(247,248,250)` and foreground `(37,48,71)`, all 11 expected toolbar painter colors, modern/blended painter flags, `panel_dark=false`, and actual Cocoa explicit/effective `NSAppearanceNameAqua` with increased contrast disabled. This is direct state evidence alongside the native screenshots, rather than an inference from the requested theme.

All six complete READY records passed the frozen receipt validator. Each modern case recorded 28 host checks and each stock case 20, plus its actual tool evidence. Both runtimes also passed nine direct positive/refusal controls, including the intentionally wrong painter case that must fail.

## Quit and unsaved documents

The three cases each ran in fresh stock and modern-dark native apps. Modern apps were built using the accepted Racket-only builder against separate preview source/profile roots. The driver called the installed application Quit handler on the real GUI eventspace and invoked the actual dialog button callbacks. It did not replace that handler, replace the application entrypoint, or call a test exit to manufacture success.

- **Clean:** the unmodified document reached the real Quit confirmation and exited normally after confirmation. Disk bytes stayed unchanged.
- **Cancel then Save:** a Unicode unsaved edit reached the real unsaved-document dialog. Cancel returned to the same modified editor/tab with the edit intact. A second Quit followed by Save exited normally and wrote exactly the intended UTF-8 bytes.
- **Cancel then Don't Save:** the same cancellation/state-preservation path passed. The second Quit discarded the edit, exited normally, and retained exactly the original disk bytes.

All six cases recorded natural exit code 0, `cleanup_used=false`, the expected complete stage sequence, and unchanged default-handler observations. The clean cases completed three stages each; each dirty case completed eight. The source fixture and its paths included spaces, an apostrophe and Unicode characters.

Actual focus and edit-target identity were true for the intended frame at READY and immediately before each Quit request, and the resulting dialogs were bound to those recorded requests. The prior run's clean-Quit timeout did not record that activation evidence, so its historical cause remains unresolved; this run proves the repaired test precondition and actual successful path.

The Quit host read back 128 MiB for stock and 256 MiB for the modern fresh profile. Those are effective preference observations, not new worker-cap or speed measurements. The modern windows reported actual Cocoa Dark Aqua.

## Preservation and boundaries

Both groups compared the complete original and selected disposable runtimes, each with 26,838 entries. Light's byte/mode tree digest was `adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`; Quit's byte/mode/mtime/symlink digest was `32314105d49bee5f4d24d068782a5299f5865e729dd4da5f39f81e905276d16e`. All comparisons passed with no changed entries. The original preferences witness also passed unchanged.

The complete trees were retained on the runner and their comparison receipts were transported in the job log. The independent evidence review verified those receipts; it did not re-hash the original Mac filesystems locally.

This runner began with no preferred `.rkt` handler: UTI `dyn.age81e45y`, handler `null`. The read-only queries kept that exact state before/after each case and at the final witness. No default reset was used. This adds evidence for preserving an absent default in this direct-launch scenario; the earlier native app run separately covered an existing Script Editor default under Launch Services.

Scope remains explicit:

- Quit entered through the installed handler inside the native app. This run did not exercise Finder/Apple-event delivery, a physical Command-Q keystroke or a mouse click on the menu item.
- The confirmation preference was enabled. Other document formats, multiple dirty windows, save failures, shutdown races and arbitrary extensions are outside these fixtures.
- Light and dark tool coverage are separate accepted runs; this run does not claim every DrRacket feature or every visual/accessibility state is verified.
- The preview remains tethered to a full official Racket installation and separate source/profile locations. Self-contained packaging, signing/notarization, download-time Gatekeeper behavior, and native Windows/Linux coverage remain pending.
- No latency or speed conclusion follows from this functional run. The named-style experiment has its own correctness and measured-completion gates.

## Evidence review

The raw result rows, six light READY receipts, six Quit acceptance records, activation/request records and preservation summaries were inspected directly. All 38 extracted PNGs passed their recorded byte-size, dimension and SHA-256 checks. All six final tool images and eight representative clean-Quit, unsaved-dialog and post-Cancel images were personally inspected: the expected native light/dark frames, recovered tool output and actual modal controls are visible. `VISUAL-REVIEW.json` identifies those 14 images without implying every intermediate image was visually inspected. An independent read-only evidence check is recorded alongside this report.

Local evidence is under `openracket-recovery/results/run-38154975508/`: `summary.json`, `decoded/`, `light-decoded/`, `macos.log` and the image index. The GitHub run above is the public source for the original job output.
