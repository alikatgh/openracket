# Native normal-Quit gate design

Status: test-only activation-readiness repair candidate, 2026-10-11. See
reports/RUN47-ACTIVATION-REPAIR.md for prior Run47 evidence, exact source mechanism,
validation, and remaining native gate. The prior four Save/Don't Save workflows
passed; stock clean failed and modern clean was unrun. This repair is not yet a
native pass. No Racket process has run locally. No delivered source, application,
accepted builder or accepted app observer has been modified.

## Scope and smallest matrix

Six independent native processes on the existing free standard macos-15 target:

1. Pristine stock, named clean fixture, normal Quit.
2. Matching modern-dark generated app, named clean fixture, normal Quit.
3. Pristine stock, dirty named fixture, Quit → Cancel → Quit → Save.
4. Matching modern-dark generated app, same synthetic edit and responses.
5. Pristine stock, dirty named fixture, Quit → Cancel → Quit → Don't Save.
6. Matching modern-dark generated app, same synthetic edit and responses.

Every process gets a fresh profile, addon registration, compiled-cache root,
fixture directory and evidence/control directory. Stock must pass before its
corresponding modern case; a failed stock case does not substitute for a modern
result. Other independent stock cases may continue after owned-process cleanup.

This tests the installed application's normal Quit handling, actual stock modal
callbacks, retained live objects, file contents and natural process exit. It
does not claim Finder/menu input-device/Apple-event routing coverage. Existing
Launch Services acceptance remains a separate result. Modern-light is a later
matched mode of these same operations, not part of this change.

## Exact Quit entry

On the existing initial GUI handler, retrieve `(application-quit-handler)` and
invoke its returned zero-argument thunk. Do not install a handler, invoke
`can-close?`/`on-close`/`save-file` directly, or call `exit` on a successful path.
Read and retain the handler procedure identity; it must stay the same after
Cancel. Check the existing frame's eventspace/handler and the public
`current-eventspace-has-standard-menus?` before dispatch. Retain one real active
DrRacket frame, its current tab, definitions/interactions editors and canvases.

Official 9.3 source chain (all hashes in reports/OFFICIAL-SOURCE-PINS.json):

- drracket/private/main.rkt:65–71: installed application handler delegates to
  the original toolkit handler when an application window exists.
- mred/private/app.rkt:33–53 and 96–106: getter returns the original registered
  thunk; default queues the active native frame's exit request.
- mred/private/mrtop.rkt:302–324 and wxtop.rkt:620–659: require actual public
  focus plus edit target before initial READY and each original Quit request;
  edit target alone does not prove native activation.
- mred/private/wxtop.rkt:629–634: the native frame checks can-exit? and invokes
  on-exit only when allowed.
- framework/private/frame.rkt:168–181: can-exit? shows the stock quit
  confirmation, runs exit callbacks, and on-exit queues the stock final exit.
- framework/private/main.rkt:562 and 644–650: fresh verify-exit is true;
  registered exit callbacks call the original frame group's can-close-all?
  and on-close-all.
- framework/private/group.rkt:262–277 in the previously verified source:
  iterates actual frame can-close? and on-close/show operations.
- framework/private/frame.rkt:1475–1477 and drracket/private/unit.rkt:2897–2919,
  5839–5855: the real retained definitions/editor and other tabs participate.
- framework/private/editor-misc.rkt:625–648: dirty documents call the real
  unsaved warning; Continue allows close, Save calls real save-file, Cancel
  returns false.
- framework/gui-utils.rkt:233–275: Save/Cancel/Don't Save map to the actual
  unsaved-warning result; 279–303 creates the Quit confirmation.
- mred/private/messagebox.rkt:74–84, 133, 173–182, 208–215: actual dialog%,
  get-message, shown modal, original button callbacks and stock result value.

Public contract: https://docs.racket-lang.org/gui/Windowing_Functions.html
(System Menus, application-quit-handler). Calling its getter outside the initial
eventspace returns void, so an apparent successful thunk return is never proof.

## Real dialogs, not simulated answers

Keep framework:verify-exit true. Every Quit attempt first finds exactly the
shown stock Warning dialog with the localized are-you-sure-quit message,
Quit and Don't Quit buttons, and an unchecked Don't Ask Again checkbox.
Do not set preferences, toggle that checkbox or suppress the dialog. Save the
actual dialog identity, message, labels, checkbox value, geometry and screenshot
before commanding the enabled Quit button with a real control-event%.

For a dirty fixture, require the next shown stock Warning dialog to have the
exact localized file-is-not-saved message for that fixture's canonical path and
exact Save/Cancel/Don't Save buttons. It has no persistence checkbox. Require the
expected parent frame, the original GUI eventspace and effective visibility
through all widget ancestors. Find each real button by exact localized label,
type and uniqueness; dispatch its stock command callback. Never construct a
dialog, replace a callback, set a desired return value or accept a missing dialog.

Each displayed dialog must remain shown until the independent Python supervisor
captures an actual OS screenshot and writes a matching token-bound capture ACK.
Unknown, extra, native-security or unexpected save-location dialogs fail closed;
no Security & Privacy, Gatekeeper, default-handler or Accessibility change.

## Supervised executable launch and identity

Use an ordinary supervised child process from fresh locally generated test
bundles. No process may have previously encountered a launch/security refusal.
Direct execution is the initial selected test route, never a fallback after
`open`, Finder, Gatekeeper or another launch rejection.

Stock control: the already-accepted make-native-launcher.rkt produces a native
stock-control .app from the full official 9.3 runtime. It has no baked program
flags. Before launch remove only CFBundleDocumentTypes from this disposable
test-control plist, preserving its native bytes and all other metadata. Read
CFBundleExecutable/CFBundleIdentifier from that actual plist, never guess.
Invoke that native executable with `-A ADDON -R CACHE: -l drracket -- FIXTURE`.
Supply sanitized PLTUSERHOME, PLTADDONDIR and PLTCOMPILEDROOTS in its actual child
environment. Register only this separate CI driver into the fresh stock addon;
do not load a modern package, supply a fake frame, or alter stock preferences.

Modern: build the actual product app with the exact unchanged accepted builder,
exact 155-file 0520 source manifest and that case's own prepared source/profile.
Invoke its unchanged Contents/MacOS/OpenRacket-launch bootstrap with the absolute
fixture path. Preserve its exec chain and product build configuration. Do not
rewrite app configuration or use environment overrides to substitute a profile.
Read build-record.json and Info.plist for the actual expected native entry.

Reuse the accepted read-only Cocoa/dyld identity reader unchanged. Require
libc PID = Cocoa PID = Python child PID; current dyld image = expected native
executable; main/running bundle paths and IDs = the actual generated bundle.
Hash native bytes before/after and inspect OS process records. Require one
bundle process, with no unexplained child or alternate runtime. Repeat these
read-only witnesses after Cancel. Pin actual loaded stock sources in both arms;
the modern arm additionally proves its original registered appearance tool,
dark palette/native appearance and accepted save-scan guard.

Stock native-byte/runtime generation is independent of the modern overlay.
Identity must fail rather than relax if the direct generated-bundle route does
not preserve these expected Cocoa observations on the actual runner.

## File and Cancel assertions

Each file is a new small plain UTF-8 .rkt under the case's canonical temp root,
with a Unicode/apostrophe/spaced filename. Original bytes and intended edited
bytes are supplied independently by the outer supervisor, hashed before launch
and copied into immutable control data. The driver confirms the already-opened
file's original contents and unmodified state, then inserts a fixed Unicode
comment through the genuine definitions editor. The harness never writes the
expected final bytes itself and never calls save-file on behalf of the dialog.

After first Cancel, require a bounded stable live interval (at least 1 second,
multiple independent GUI turns) proving:

- Original child PID and Cocoa application still live; same frame/tab/editor
  object identities, all relevant widgets still shown and wired together.
- Modal gone; framework:exiting? reset false; installed Quit handler unchanged.
- Exact dirty text and modified flag preserved; disk bytes remain original.
- Quit confirmation preference stays true and initial checkbox was untouched.
- A fresh queued GUI callback completes, proving the loop is responsive.

Repeat Quit with the same initial confirmation, then Save or Don't Save.
For Save require exact final UTF-8 bytes; for Don't Save require exact original
bytes. For clean Quit require no unsaved prompt and unchanged fixture bytes.
Final checks happen in the independent supervisor after real process exit.
Backups/autosave files can be created by stock behavior only inside disposable
fixture/profile/temp roots; report their hashes and paths rather than disabling
stock autosave/backup preferences. No existing user document is a fixture.

## Success cannot be supplied by cleanup

The driver writes ordered stage evidence and a final-response receipt only for
the original shown button's command. The external supervisor requires every
case-specific receipt and screenshot ACK, correct final disk bytes, no failure
marker, natural child exit status exactly 0, and no surviving bundle process.
Process absence alone, `open` exit 0, a READY file or a test-side exit call is
insufficient. No success marker is written until all external checks pass.

The success path contains no exit, process signal, custodian shutdown, frame
hide/close or editor-modified reset. A test-side failure first records a durable
failed terminal state. Only then may bounded owned-process cleanup send TERM
and KILL. That path retains its timeout/failure outcome even if cleanup succeeds
or a child later reports 0. Cleanup records cannot satisfy success validators.

Use one fixed 150-second process acceptance deadline including startup and
captures; 20-second GUI/dialog awaits and 20-second capture ACK waits remain
bounded by that deadline. Allow at most 15 seconds after failure for diagnostics
and owned-process cleanup, never for late acceptance. Preparation/compilation
have independent existing setup bounds. Exact deadlines must be frozen before
native execution; no timeout extension based on observed failures.

## Isolation and audit

All source preparation, package registration and compilation write only separate
test roots. Retain full before/after runtime bytes/modes/mtime/symlink witnesses,
the user's original preference file witness and read-only .rkt handler witness.
Check canonical containment and refuse symlinked managed roots, pre-existing
fixtures, occupied output directories, malformed/oversized config, replayed or
wrong-stage control tokens and unexpected package/source resolution.

The CI driver is explicitly a test actor, unlike the accepted read-only app
observer. Place it in its own package and working tree. Do not repurpose that
observer's read-only schema or claim content_or_preferences_changed=false after
editing a fixture. No test code or driver registration is shipped with the app.

## Required pre-native checks

1. Exact input hashes and verified official Git blobs; source-backed symbol
   and callback-chain audit, no locally installed runtime.
2. Pure configuration/transition/report validators and refusal tests: wrong
   PID/path/token/stage/bytes, missing screenshot ACK, exit-by-signal, missing
   final callback receipt, late exit, cleanup-used, duplicate success and
   unknown shown dialog must all fail.
3. The test actor uses timer callbacks in the original GUI eventspace, including
   during stock modal yields. All callback failures latch a failed result before
   the only explicit test-side exit (exit2). No alternate eventspace or tool
   coordinator is used. Actual GUI behavior must still execute on the Mac.
4. Actual native compilation of all new Racket modules, on the authorized free
   runner after a frozen allowlist and fresh publication permission.
5. All six real cases, screenshots and independent result validation; full
   original-runtime/preferences/default-handler preservation checked finally
   even after case failures.

Do not infer this gate passed from Python source checks, lexical delimiters,
stock tests alone or the prior app/tool run. No remote mutation, CI trigger,
downloaded package archive, local installation or local native Racket execution
is authorized by this source-preparation task.
