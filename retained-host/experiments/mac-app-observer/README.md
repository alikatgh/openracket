# Native .app CI observer (source candidate)

This separate, test-only package observes the genuine launcher-created application
without opening a document, starting a frame, replacing a handler, calling an
editor/control callback, or changing preferences/content/theme. Product source,
appbuilder and generated bundle are not edited by the observer. Reading fixture
bytes means reading their expected text from disk; it never opens them in an editor.

**Status:** 11 portable source/lexical checks pass. Twenty-one actual Racket
contract/state tests, native module compilation, Cocoa API calls and all native
app acceptance remain **not run here**. No local Racket, package or GUI was
downloaded or executed. Delimiter checks are not compilation evidence.

The source builds on the proven 0520 preview observer, whose source SHA-256 is
`ce3d961b5c6f2b5cb42edea8c984afcd9a87c309ff8e9409901eece4ed1fc9e5`.
It preserves its genuine class/canvas/editor identity checks, localized original
toolbar order, dark theme/palette/native DarkAqua/blending assertions, exact
registered memory preference check and loaded autosave scan-guard check. This is
read-only activation evidence, not a save/recovery exercise or live worker cap
measurement. It adds all-tab enumeration, sequence/object identity, native process
and bundle readback, and bounded screenshot handshakes.

## Explicit scope

Two independent fresh native processes are intended:

1. Cold empty app launch, then one warm Unicode file, then duplicate dispatch.
2. Cold Unicode file launch, then a different warm file, then duplicate dispatch.

A third cold-file sequence can repeat after CI relocates **only the app** and
updates the expected app/native paths in a fresh configuration. Every sequence
must use real `/usr/bin/open -a "$APP"` commands externally. The CI harness owns
all launches, configuration, disposable fixtures, registration, screenshots and
process inspection. There are no shell commands or application launches here.

Coldempty expects exactly one empty genuine document. Coldfile expects exactly
one named fixture, with no blank document. At warm stages all expected file paths
must occur exactly once across every genuine frame/tab, with exact Unicode text
and unmodified buffers. An original coldempty blank may be reused or remain;
additional blanks fail. Every previously named document must retain its actual
frame/tab/definitions/interactions identities across the warm event. The duplicate
stage requires the complete before/after identity set to be identical after at
least two seconds of observation following the externally supplied dispatch
receipt. This is **observed no-duplicate behavior following dispatch**, not proof
that an instrumented Apple-event callback was called. No callback is instrumented.

The process remains alive between stages. Its final observer-triggered exit is
CI cleanup, **not normal Quit acceptance**.

## Registration and native compile/test gate

Use an already-installed full official Racket 9.3 on Apple Silicon/macOS 15, a
separate writable copy of 0520 source, and its already-prepared private profile.
Take the complete runtime and original-preferences snapshots before any setup or
compilation. `RACKET`, `PROFILE` and `OBSERVER` below are explicit absolute paths.
`OBSERVER` must be a **separate writable CI copy** of this package. Leave
`observer-config.json` absent until setup/tests/compilation have finished.

Use the same clean environment/private roots as the approved launcher:

```sh
unset PLTCOLLECTS PLTCONFIGDIR PLTLINKS PLT_COMPILED_FILE_CHECK
unset PLT_ZO_PATH PLTDRDEBUG PLTDRCM PLTDRPAR
export PLTUSERHOME="$PROFILE"
export PLTADDONDIR="$PROFILE/.local/share/racket"
export PLTCOMPILEDROOTS="$PROFILE/compiled-cache:"
export XDG_CACHE_HOME="$PROFILE/.cache"
run_raco() {
  "$RACKET" -U -A "$PLTADDONDIR" -R "$PLTCOMPILEDROOTS" -l raco -- "$@"
}
run_raco test "$OBSERVER/tests/contract-test.rkt" "$OBSERVER/tests/observer-state-test.rkt"
run_raco make "$OBSERVER/tool.rkt" "$OBSERVER/cocoa-identity.rkt" "$OBSERVER/default-handler.rkt"
run_raco pkg install --scope user --batch --no-setup --deps fail --link \
  --name openracket-mac-app-observer "$OBSERVER"
run_raco setup --avoid-main --no-docs --no-launcher --no-foreign-libs \
  --no-install --no-post-install --pkgs openracket-mac-app-observer
```

The registration flags repeat the already-used separate preview observer route.
Use dependency failure, never downloads or substitutions. If the profile does not
resolve the exact source pins, stop. Install only this .app observer for these
cases; leave the older portable observer unconfigured if it is also installed.
Build the product app with explicit `--theme dark`, keeping its normal `saved`
default unchanged. The observed source launcher must actually select modern UI,
DarkAqua, enabled guard, the requested private profile/addon and private-first
compiled roots. None of those are written by this observer.

## Exact v1 configuration

Create `$OBSERVER/observer-config.json` atomically before each fresh launch. It
is absent in the deliverable and **absent means inert**. No observer environment
variables are used, and no Launch Services environment inheritance or `launchctl`
changes are required. Configuration and observations are never injected into the
product bundle/configuration or source launcher.

The JSON object has exactly these keys (example only):

```json
{
  "schema": 1,
  "run_id": "coldfile-run-20261011-01",
  "mode": "coldfile",
  "output_dir": "/ci/evidence/fresh-coldfile-output",
  "app_path": "/ci/OpenRacket λ's Preview.app",
  "native_executable_path": "/ci/OpenRacket λ's Preview.app/Contents/MacOS/ACTUAL_GENERATED_NAME",
  "bundle_id": "ACTUAL.BUNDLE.ID.FROM.BUILD",
  "profile_path": "/ci/source/profile",
  "memory_mib": "256",
  "files": ["/ci/first λ.rkt", "/ci/second's λ.rkt"],
  "step_tokens": {
    "coldfile": "coldfile-unique-token-01",
    "warmfile": "warmfile-unique-token-01",
    "duplicate": "duplicate-unique-token-01"
  }
}
```

- `schema`: exact integer 1. Unknown/missing keys are refused.
- `run_id` and each of the three distinct `step_tokens`: 8–100 ASCII letters,
  digits, underscore or hyphen. Use independently random fresh values.
- `mode`: exactly `coldempty` or `coldfile`.
- `output_dir`: existing empty directory, unique to this sequence. Put CI logs,
  commands and prelaunch screenshots outside it until observer startup; the
  observer requires it empty. It becomes the control/evidence directory afterward.
- `app_path`, `profile_path`: existing directories. Native executable: existing
  file. All path fields: absolute, 1–4096 characters, no NUL/CR/LF.
- `bundle_id`: expected actual builder identifier, ASCII letters/digits/dots/hyphen.
- `memory_mib`: decimal string >=8 or exact `unlimited`. Unlimited means Racket
  `#f` and JSON `false`. No preference fallback/default registration occurs.
- For `coldfile`, `files` is exactly two distinct absolute synthetic UTF-8 text
  file paths in dispatch order. Each is <=80,000 bytes and <=20,000 characters.
- For `coldempty`, use exactly one future warm-file path in `files`, and replace
  the `coldfile` token key with `coldempty`. No initial file is passed to `open`.
- Disk fixture hashes are captured before observation. The editor's text must
  match exactly; each inspection also checks unchanged fixture bytes on disk.

Expected app identity is only an assertion input. Actual PID, bundle identity and
process image always come from native APIs, never environment/config copies.
Use the exact generated native name from the builder, not the placeholder above.

Configuration/control JSON is bounded at 65,536 bytes and must contain one JSON
value only. Bad configuration before a safe fresh output directory is established
emits `OPENRACKET_MAC_APP_CONFIGURATION_FAILURE` and exits 1. Once output is safe,
configuration/runtime errors also produce failure READY for an OS capture. No
source compile error can be hidden by that mechanism; compile first.

## Per-stage files and exact handshake

Step names are `[mode, "warmfile", "duplicate"]`. Paths are:

- Observer output: `OUTPUT/RUN_ID.STEP.ready.json`
- CI capture acknowledgment: `OUTPUT/RUN_ID.STEP.ack.json`
- CI warm/duplicate dispatch receipt: `OUTPUT/RUN_ID.STEP.sent.json`
- Observer final output: `OUTPUT/RUN_ID.complete.json`

The initial cold stage has no `.sent.json`. The CI harness must retain the actual
cold-launch command, start state, command return code and process tree separately.

For each READY (including failed READY), CI validates `schema/run_id/step/token`,
reads `status`, captures the real OS UI using its `geometry` (also retain whole
screen/Dock/menu evidence where possible) and records the actual process tree.
Only after a successful capture does CI atomically write:

```json
{"schema":1,"run_id":"EXACT_RUN_ID","step":"EXACT_STEP","token":"EXACT_STEP_TOKEN","capture_ok":true}
```

`capture_ok` must be JSON `true`; strings/truthy substitutes fail. If capture
fails, preserve the error and do not forge an ACK. The observer fails after the
capture timeout. Retain nonzero observer exit/error even if an earlier READY
succeeded.

After prior-stage ACK, CI externally executes the next command:

- Warm: `/usr/bin/open -a "$APP" "$LAST_FILE"`.
- Duplicate: repeat `/usr/bin/open -a "$APP" "$LAST_FILE"`.

After that command returns zero, atomically create the next stage's `.sent.json`:

```json
{"schema":1,"run_id":"EXACT_RUN_ID","step":"EXACT_NEXT_STEP","token":"EXACT_NEXT_STEP_TOKEN","open_exit":0}
```

The observer never runs this command. The receipt is CI-supplied dispatch evidence;
it cannot independently authenticate whether `open` ran. Retain lossless command
argv/status/timestamps to establish that externally. Mismatched tokens fail
closed. The next stage has its own READY and screenshot ACK; acknowledgments are
never reused. A failure ACK exits with failure, never advances to another stage.

After final success ACK the completion JSON contains `schema`, `run_id`,
`status:"passed"`, `all_screenshots_acknowledged:true`, `same_pid:true`, actual
`pid`, the three `steps`, and `complete_app_acceptance:false`. Require that file,
all three successful READY records, authentic OS captures and process termination
before considering this one bounded sequence passed.

Each stage has 60 seconds to observe/receive dispatch, followed by 20 seconds for
capture. Stable readiness needs three complete successful 100 ms timer turns with
unchanged actual object identities; duplicate additionally waits >=2000 ms after
its receipt. A 270-second cooperative watchdog bounds the sequence. CI must also
use an independent process timeout, because a blocked GUI handler can defeat any
in-process timer. This cleanup timeout does not authorize killing unrelated apps.

## READY schema

Every READY includes the exact control envelope `schema/run_id/step/token`.

Successful JSON includes:

- `status:"passed"`, actual `pid`, `same_pid:true`, `identity` and `geometry`.
- `identity`: libc `pid`, Cocoa `running_pid`, `same_running_application` from
  native `isEqual:`, `same_pid`, dyld `process_image_path`, raw
  `running_bundle_identifier`, `running_bundle_path`, `running_executable_path`,
  `main_bundle_identifier`, `main_bundle_path`, `main_bundle_executable_path`.
- `frames`: retained-host evidence per frame, with `frame_id`, `checks`, `geometry`,
  `toolbar_labels`, `toolbar_horizontal`, `ui`, `theme`, `painter`, `native`,
  `native_blending`, `save_guard`, `memory_limit` and exact source pins.
- `tabs`: all genuine tabs, with stable actual `frame_id/tab_id/definitions_id/
  interactions_id`, canonical `filename` or false, exact `text`, `characters`,
  `editor_utf8_sha256`, `modified:false` and whether currently selected.
- `frame_count`, `tab_count`, `blank_count`, `expected_files`, `sources`, read-only
  actual `profile` environment/compiled-root observations, `checks`.
- `duplicate`: false before the duplicate stage; then `observed_no_duplicate:true`,
  `handler_receipt_proven:false`, exact `before/after` identity sets and `settle_ms`.
- `external_dispatch`: the CI receipt or false initially.
- `entrypoint_replaced:false`, `fixture_opened_by_observer:false`,
  `handler_replaced:false`, `content_or_preferences_changed:false`,
  `complete_app_acceptance:false`.

Failure JSON includes `status:"failed"`, readable `error`, `checks`, `last_state`,
`windows` (shown/title/dialog/geometry/widget-label/editor excerpt diagnostics) and
capture `geometry`. Failure READY may lack successful identity/top-level PID if
identity could not be verified; do not interpret that as a pass. Diagnostics do
not dismiss unknown dialogs.

Both Cocoa bundle IDs/paths must match the expected app. The actual dyld process
image must be the generated native executable. Cocoa executable metadata can name
either that executable or the bundle's declared `Contents/MacOS/OpenRacket-launch`
entry; raw values are preserved separately. Native `isEqual:` guards the ongoing
NSRunningApplication identity, and libc/Cocoa PID cross-check on every stage.
External OS process-tree evidence remains required to rule out extra GUI children.

## Read-only default .rkt handler witness

`default-handler.rkt` is a separate optional CLI with no GUI import/startup. Run it
under the same private roots **before app build/registration** and after all app
cases (including relocation), capturing stdout and exit code:

```sh
"$RACKET" -U -A "$PLTADDONDIR" -R "$PLTCOMPILEDROOTS" "$OBSERVER/default-handler.rkt"
```

Success is `{schema:1,status:"observed",extension:"rkt",uti:STRING,
role_mask:4294967295,default_handler:STRING_OR_NULL,handler_available:BOOLEAN,
query:STRING,defaults_changed:false}`. Compare **both actual UTI and handler**
before/after. Null means the supported query found no handler. An unavailable API,
invalid UTI result or other error is `status:"error"`, diagnostic `error`, exit 1;
it is never substituted with null. APIs are deprecated but source-documented;
native symbol availability must be tested. A UTI derivation can be ambiguous when
multiple types claim an extension, so this is a bounded extension-to-preferred-UTI
witness, not proof of every file-specific Finder override. It never sets/registers
anything. Only owned Create/Copy results are CFReleased.

## Remaining native app gates

Even passing all these sequences is not complete product acceptance. Still pending
unless separately tested: actual Finder Open With/icon drop, Dock/menu naming and
activation, normal Quit/cancel-unsaved, richer/multifile/WXME cold event, startup-gap
event, command-line argument cases, forced extra-instance refusal, stock app
coexistence, source/runtime relocation failure dialogs and post-exec crash UX,
existing custom/unlimited/no-key profiles, full source launcher Run/appearance/
save/recovery parity, runtime/preferences/default-handler before/after witness,
signature/Gatekeeper reporting, accessibility/IME and all other gates in the
appbuilder's MAC-NATIVE-ACCEPTANCE.md. No Developer ID/notarization or transferable
self-contained app is claimed.

Portable source checks (Python is only a QA convenience, not a product or native
observer prerequisite) require an explicit baseline path, so the same test works
in a relocated publication checkout without a sibling frozen directory:

```sh
OPENRACKET_OBSERVER_BASELINE_TOOL="$SOURCE/tests/portable-observer/tool.rkt" \
  python3 -B "$OBSERVER/tests/source-test.py"
```

`SOURCE` is the exact verified 0520 source/proof copy. The baseline path must be
absolute and its bytes must hash to the existing pinned
`ce3d961b5c6f2b5cb42edea8c984afcd9a87c309ff8e9409901eece4ed1fc9e5`.
Missing/relative paths or altered baseline bytes fail; no path is auto-discovered.
This test-only variable is not read by the runtime observer or product app.
