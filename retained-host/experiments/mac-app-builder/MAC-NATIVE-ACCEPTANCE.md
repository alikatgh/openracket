# Required Mac native gate

Status: **not run**. This contract prepares the next authorized test; it does not
authorize remote publication, runtime/package downloads or user-computer actions.
Keep the interval-map and other performance experiments completely outside it.

## Exact no-claim regression gate

This correction is unexecuted on macOS. It addresses run 38125605788's change
from `(dyn.age81e45y, null)` to the preview bundle ID. Those before/after samples
prove changed effective resolution; they do not establish the exact registration
moment or a stored user-preference write. The reader's `defaults_changed:false`
describes its own read-only operation, not before/after equality.

1. Use a fresh disposable native runner/session with no previous version of this
   preview registered. Retain a new output path and source/profile identity. Do
   not clear/reset Launch Services or install an artificial handler to arrange
   the baseline. Keep existing handlers, including null, exactly as found. A
   previously contaminated session cannot establish original-null preservation.
2. Before reference generation or product building, run the existing separate
   read-only `.rkt` witness. Require `status:observed`, capture the exact preferred
   UTI and default handler (JSON null is valid), and fail closed on query errors.
   Keep the existing all-roles mask 4294967295. The preferred-UTI query is bounded
   evidence, not proof for every UTI or document-role resolution.
3. Compile the changed builder and run all 20 RackUnit cases using the isolated
   roots. Case 03 must strip inherited extension/wildcard/UTI entries and require
   exact `CFBundleDocumentTypes` key absence, while retaining the app icon and
   native executable bytes. Parse the real generated plist independently and
   require the same absence; replacing `Alternate` with an empty array, another
   rank, or a different advertised type is not this candidate's contract.
4. Repeat the read-only witness immediately after native generation, before the
   first open, after cold-empty readiness, after cold-file readiness, after warm
   delivery, after duplicate reopen, and after app cleanup/relocation. Compare
   `(uti, default_handler)` to the unchanged before-build baseline every time.
   Run the final comparison from cleanup even if readiness/file assertions fail;
   retain each result and the earliest divergence independently of other errors.
5. With no preview process, dispatch only ordinary `/usr/bin/open -a` using the
   exact app path. After cold-empty, independently start cold-file with an
   absolute Unicode/apostrophe `.rkt` fixture. Require the actual editor's exact
   file path/content/hash once, generated bundle/native identity, and a real OS
   capture. Send a second file while that PID remains alive, then reopen it;
   require the existing PID and stock duplicate-window behavior. Retain dispatch
   argv/status, ready evidence, file identities and process observations. An
   `open` exit code alone does not prove delivery; no observer-created document,
   argv-only launch, direct event injection, or alternate launcher substitutes.
6. On an OS/security refusal or default change, stop additional launch cases and
   report the first failure. Do not set a default back, unregister an app, edit
   Launch Services preferences, strip quarantine, re-sign to bypass refusal, or
   change OS policy. Test a naturally pre-existing non-null `.rkt` default on a
   separate authorized session when available; one null-baseline run cannot prove
   non-null preservation. Finder Open With through explicit app selection is a
   separate UI gate; without a document claim, automatic Open With listing and
   icon-drop affordances are not promised.

CI integration must replace publication-34's `application_manifest` assertion
of every row's `LSHandlerRank == Alternate` with exact key absence. Keep the
unchanged default-handler comparison, strengthen its checkpoints as above, and
update the builder manifest pin. The 20-case RackUnit count is unchanged. This
document does not authorize a native run or a remote workflow change.

## Fixture and independent evidence

Use Apple Silicon/macOS 15 and an already-installed full official Racket 9.3.
Use a separate writable copy of the 155-file 0520 source, not the delivered/frozen
folder. Prepare its isolated profile through the already-authorized source setup
path if necessary; app building never does setup. Record the exact source-manifest
pin, wrapper hashes, runtime version/architecture and generated app file hashes.

Before any builder execution, hash the entire original runtime tree, including
every bytecode file, modes, directories and symlink targets; also retain mtime_ns
for files/directories and compare afterward (ignore access times caused by reads).
Retain a separate snapshot of official user preferences and default `.rkt` handler.
Use only disposable documents. Native UI capture must come from the OS.

Observe the real launcher-created DrRacket with a separately installed CI-only
observer, preferably the existing delivered-preview observer extended narrowly.
It must not open the test file itself, substitute the app entrypoint, install an
application file handler, rewrite preferences, or enable performance experiments.
The observer may report the actual frame/editor file/content, callback objects,
theme/guard state, memory preference, compiled roots, process PID and Cocoa bundle
identity. Its installation is distinct from product setup and must be recorded.

## Required cases and pass conditions

1. **Build only.** Invoke the recorded command with source/runtime/output paths
   containing spaces; include a Unicode/apostrophe path in a second case. The
   builder reports success, app has executable permissions, `plutil -lint`
   passes, and no GUI opens during generation/preflight. No setup/download runs.
   Record the generator's native executable before decoration and prove identical
   filename and bytes afterward. Test an existing empty directory/file/app output
   and a symlink output: all are refused without changing their contents.

2. **Finder/Launch Services cold empty start.** Start through actual Finder if
   available, and through `/usr/bin/open <app>` for the automated case. A real
   retained DrRacket window appears, without Terminal, an extra wrapper Dock app,
   or a phantom blank document from argument parsing. Capture Dock/menu/titlebar.
   The observer reports modern toolbar/host theme, native appearance, autosave
   activation, original editor/control identities and the profile's exact limit.

3. **Identity and lifecycle.** Inspect NSRunningApplication's bundle identifier,
   bundle URL, executable URL and PID plus the process tree. They must describe
   this OpenRacket bundle and the generated native executable, not the installed
   stock app or a second GUI child. Document any permissible OS naming differences.
   Regular Quit and cancel-on-unsaved-changes behave normally; Quit leaves no
   bootstrap/dispatcher GUI process. A correct frame alone is insufficient.

4. **Cold file Apple event.** With no preview process, use
   `/usr/bin/open -a <exact-app-path> <absolute-Unicode-file.rkt>`.
   Assert that the genuine editor opens that file exactly once with exact content,
   not by the observer. Repeat with two files and a rich/WXME fixture. Test a real
   Finder “Open With” or icon drop when available; do not call a test event handler.
   Record failures/timeouts instead of using argv as a substitute.

5. **Warm file Apple event/reopen.** While open, send a different file using the
   same Launch Services command, and repeat an already-open file. Files arrive in
   the existing PID with stock duplicate-window behavior. Activate the app again
   with no file and through its Dock icon; existing windows are brought forward.
   Include an event while startup is still completing to test the pre-handler gap.

6. **Command-line file arguments.** With no preview process, directly invoke the
   app bootstrap using absolute/relative file paths with spaces, Unicode, quotes,
   shell metacharacters, and a filename `--check`. Argument boundaries and exact
   file contents match; no text is evaluated as shell code. A strict leading
   historical `-psn_123_456` is ignored, but a lookalike filename is preserved.
   This case does not stand in for the Apple-event cases.

7. **Repeat launch / forced extra instance.** Normal repeated activation uses the
   same PID. `open -n <app>` is refused without a second same-profile process or
   preference write. Two copies pointing at the same profile have the same bundle
   identifier. Launch ordinary stock DrRacket alongside it and verify different
   identity/preferences. Direct raw native/source-script invocation is not a
   supported single-instance enforcement route; do not claim an application lock.

8. **Relocation and configuration.** Move/rename only the app and repeat cold
   empty/file launch. Native code still finds its original runtime and source.
   Move the configured source or runtime out of the way in a disposable fixture:
   opening the app yields a clear alert, creates no replacement profile, and never
   falls back to some other Racket on PATH. Restore it and confirm launch recovers.

9. **Failure UX.** Exercise wrong version, missing source, missing native launcher,
   failed preflight/missing private package, profile symlink and unwritable profile.
   Each stops without opening stock/global DrRacket or running setup and reports
   the precise repair action. Check the alert is visible in a GUI launch, including
   when the private log cannot be created. Simulate one post-exec native-load/startup
   failure: a merely disappearing icon with an undiscoverable log is a blocker.
   If it fails, add a scoped native error mechanism; do not silently add a second
   GUI supervisor or launch Terminal.

10. **State retention and no mutation.** Run with a fresh previously prepared 256
    profile; then an existing explicit 128/384/unlimited profile and an existing
    no-key profile. The app never writes a new memory choice or resets ownership.
    Original source launch/stock fallback remain usable after app Quit. Include
    contaminated parent PLT path/bytecode/debug variables and verify the actual
    child process has the selected addon/cache and original compile-check policy.

11. **Settings/defaults and original runtime.** Compare the full original-runtime
    tree and original user preference snapshot after generation, all launches,
    failure paths and relaunch. Zero unexpected differences are required. Verify
    the prior `.rkt` default handler remains the same. No system appearance,
    Launch Services default, quarantine/Gatekeeper or security setting is changed.

12. **Bounded product regression.** Repeat the passing preview's real retained
    toolbar/editor, Unicode, Run, appearance roundtrip and save/recovery smoke
    checks through the `.app`. Record any GUI-runtime versus console-runtime
    behavioral difference. Packaging is not a speed claim and does not close the
    known large-file, Stop, tool-parity, accessibility/IME or crash-recovery gaps.

13. **Security/signature honesty.** Record `codesign` inspection/verification and
    Gatekeeper assessment results without changing policy or stripping quarantine.
    Ad-hoc signatures are expected from Racket generation, but no Developer ID or
    notarization is claimed. If a security block requires user approval, stop and
    report it; do not bypass it. Downloaded/transferred-app launch is a distinct
    untested scenario unless exercised under explicitly permitted conditions.

## Completion rule

Return the generated app path, exact source/wrapper/app hashes, all case results,
whole-runtime before/after evidence, process/bundle observations and real captures.
Only call it a “launchable Mac preview app” once the native generation, Finder
identity and cold/warm file-event gates pass. Any partial result must name the
remaining gate. Passing fake-executable tests alone is never app acceptance.

## Racket-only builder addendum

Use this directory's README commands instead of the earlier Python build command.
Before real app generation, compile `make-app.rkt`, `test-app.rkt` and the native
launcher helper with private-first roots, then run all 20 headless RackUnit cases.
Record their output and exact candidate source hashes. These tests use shell fake
executables and a no-op alert in temporary fixtures; they do not replace any of
the native cases above. Include trailing-directory runtime paths and real macOS
`/var`/`/private/var` aliases in query/layout checks, keeping genuine descendant
escapes refused. Verify parsed XML plist metadata, `plutil -lint`, file and
directory permissions, native executable identity/hash and generated signature.
No Python is required for these compile/test/build commands.
