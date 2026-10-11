# OpenRacket Mac app: Racket-only builder candidate

## Status and scope

This is a source-only replacement for the reviewed Python one-time builder.
**The destination Mac needs an already-installed full official Racket 9.3, but
no Python to build or run the app.** `build-app.sh` uses the system `/bin/sh` and
the explicitly named Racket to load `make-app.rkt`. There is no PATH search,
runtime download, package installation, automatic profile setup, preference
reset, or published binary in this deliverable.

Build on the destination Mac against that Mac's actual paths. The result remains
tethered to that official installation and the separate prepared source/profile.
A CI-created app is test evidence, not a downloadable app that works on another
Mac. A self-contained product is a later, separately scoped packaging evaluation.
There is no Developer ID signature, notarization or finished Finder acceptance
claim. The official generator may ad-hoc sign native code; that is not Developer
ID signing. See `MAC-NATIVE-ACCEPTANCE.md` before calling any output launchable.

### What has and has not been checked

- PASS: 27 portable checks (`PORTABLE-TESTS.log`): the original 20 Python-reference
  tests with the byte-identical app scripts, plus seven source/shell-entry checks.
- PASS: the 155-file source pin, original script/generator byte identity, shell
  syntax, lexical Racket delimiter checks, and poisoned entry configuration with
  an explicitly fake executable that never invokes Racket.
- SOURCE-REVIEWED: official Racket 9.3 library API names and representations,
  pinned to commit `bbf7dea831df95922db23aaa51e13eed17dcf881` in `API-EVIDENCE.md`.
- NOT RUN: Racket parse/expansion/compile, the new 20-case RackUnit suite, the real
  generator, native app build, Finder/Dock/Apple events, signing/Gatekeeper checks,
  full-runtime before/after witness, or source-preview regressions through the app.

The portable tests deliberately import the untouched Python reference to exercise
its fixture generation. They **do not test the Racket decorator**. The new
`test-app.rkt` ports those 20 contracts without Python and must pass with real
Racket before the port is accepted. Delimiter balance is not a compiler result.

## One-time build command (future authorized Mac gate)

Use Apple Silicon/macOS 15, a separately prepared writable copy of the exact
0520 source, and an existing output parent. Close all instances using that
profile. Do not run the builder from inside the official runtime installation.

```sh
/bin/sh "/absolute/path/openracket-mac-app-racket/build-app.sh" \
  --source "/absolute/path/OpenRacket-native-candidate" \
  --runtime-root "/absolute/path/Racket 9.3" \
  --racket "/absolute/path/Racket 9.3/bin/racket" \
  --output "/absolute/path/OpenRacket Preview.app"
```

All four paths are explicit and absolute. Source path colons and configuration
path NUL/LF/CR are rejected. Existing output paths, including dangling symlinks,
are never replaced. `--theme saved` is the default; `--theme light` or
`--theme dark` selects an explicit initial choice. The tested autosave and native
appearance defaults stay enabled, without changing existing memory preferences.

Use the shell entry instead of invoking `make-app.rkt` directly from a possibly
contaminated environment. It clears collection/configuration/bytecode overrides
before Racket reads `#lang` or resolves imports and selects `-U`, the private
addon path and private-first compiled roots. The Racket module then clears all
`OPENRACKET_*` variables and re-establishes the bounded child environment. No
compilation manager is installed merely by importing the builder.

The module repeats the reviewed canonical runtime-layout and query checks, exact
source manifest/hash verification, profile-link checks and proven source
`--check`. It stages the official launcher under the destination parent, decorates
it, re-verifies source, then publishes using exclusive directory creation. It
always removes its own staging directory; a partial failed output is retained
for diagnosis, never silently replaced or removed on retry. Use a fresh output.

## Compile and headless test commands (NOT RUN here)

Set these to existing, reviewed locations. Take the complete original-runtime
before snapshot described in `MAC-NATIVE-ACCEPTANCE.md` before these commands,
not only before app generation. `PROFILE` must already be prepared and its managed
paths must be non-symlinks. Set `OPENRACKET_BUILDER_TEST_SOURCE` to the actual
verified proof copy for CI; the suite validates the pinned manifest and all 155
source hashes before any test fixture runs. A sibling named
`openracket-preview-memory-freeze-20261011-0520` is only the optional local
fallback. The suite reads that fixture and writes only fresh temporary test
directories. Production build source is selected separately with `--source`.

```sh
RACKET="/absolute/path/Racket 9.3/bin/racket"
BUILDER="/absolute/path/openracket-mac-app-racket"
SOURCE="/absolute/path/OpenRacket-native-candidate"
PROFILE="$SOURCE/profile"
(
  unset PLTCOLLECTS PLTCONFIGDIR PLTLINKS PLT_COMPILED_FILE_CHECK
  unset PLT_ZO_PATH PLTDRDEBUG PLTDRCM PLTDRPAR
  export PATH=/usr/bin:/bin:/usr/sbin:/sbin
  export PLTUSERHOME="$PROFILE"
  export PLTADDONDIR="$PROFILE/.local/share/racket"
  export PLTCOMPILEDROOTS="$PROFILE/compiled-cache:"
  export XDG_CACHE_HOME="$PROFILE/.cache"
  export OPENRACKET_BUILDER_TEST_SOURCE="$SOURCE"
  "$RACKET" -U -A "$PLTADDONDIR" -R "$PLTCOMPILEDROOTS" -l raco -- make \
    "$BUILDER/make-app.rkt" "$BUILDER/test-app.rkt" \
    "$BUILDER/make-native-launcher.rkt" &&
  "$RACKET" -U -A "$PLTADDONDIR" -R "$PLTCOMPILEDROOTS" -l raco -- test \
    "$BUILDER/test-app.rkt"
)
```

The headless tests call fake `/bin/sh` runtime/native executables, not GUI Racket.
Their alert transport is replaced only inside temporary fixtures with a no-op
AppleScript; the production error script is unchanged and its real alert remains
a native acceptance case. The suite preserves argv, final PID, poisoned config,
profile-link refusal, relocation, dispatch boundary and layout/query cases.
Runtime-directory equality compares canonical components. Canonical Unix paths
serialize without a trailing slash except `/`, so the unchanged launcher's exact
dispatch prefix remains stable. Tests include a trailing-slash source passed
through config generation and the fake native PID/argv chain, trailing runtime
directory separators, and a conditional `/var` to `/private/var` alias check.

For optional local source QA where Python already exists:

```sh
python3 -B portable-tests.py
```

That command needs the original `openracket-mac-app-plan` and frozen source as
siblings. Python is only an optional development-test tool; none of the product
entrypoints or generated app uses it.

## Preserved app execution chain

The four copied files are byte-identical to the reviewed candidate:

- `make-native-launcher.rkt`: official non-script native generator, absolute
  installation references, no baked program flags.
- `bootstrap.sh`: checks/configures the private profile, validates source preflight,
  normalizes argv files, then `exec`s the unchanged source launcher.
- `runtime-dispatch.sh`: forwards only the exact final DrRacket invocation to
  the generated native executable; all other probes go to the console runtime.
- `report-error.applescript`: receives error text as argv.

The generated native executable's name, location and bytes stay untouched;
`decorate-bundle` additionally checks its SHA-256 before/after. `CFBundleExecutable`
points at the added bootstrap. The final shell/source/dispatcher chain uses
`exec`, retaining the initial process rather than launching a second GUI child.
The original source entrypoint, profile ownership and memory behavior are not
modified. Real Cocoa/Launch Services identity and file-event retention still need
the Mac gate.

## Deliberate implementation differences and remaining risks

- XML plist is handled by the full distribution's `xml/plist`, retaining unknown
  plist values and semantic keys. Its XML bytes/DTD/version formatting differ
  from Python `plistlib`; compare parsed metadata, not plist byte identity. It
  accepts the official generator's XML plist, not arbitrary binary plist input.
- JSON and POSIX-shell configuration preserve the same values. Object key order
  and JSON whitespace are not an acceptance criterion. Runtime query parsing
  rejects non-whitespace following the one JSON object.
- Recursive publication preserves file permissions/times and explicitly copies
  directory permissions/times. It does not promise Python `copy2`'s optional
  platform-specific extended-attribute copying. The generator's native bytes
  remain identical; actual codesign/xattr behavior is a Mac gate.
- Canonical containment resolves links and existing ancestors of missing paths.
  It does not claim race-proof hostile filesystem handling or normalization of
  case-only aliases on a case-insensitive volume. No untrusted concurrent mutation
  of source/runtime/staging is supported; native tests must verify real aliases.
- The shell entry necessarily starts the explicitly selected interpreter before
  the Racket module performs full layout/version/hash checks. It starts no GUI,
  installs no compile manager, disables user-scope imports, and uses private cache
  roots. Whole-runtime immutability still requires the before/after Mac witness.
- App move alone is supported by design; moving its source/runtime requires a
  rebuild. Native error alerts, post-exec early crashes, forced extra instances,
  file-open Apple events and original default-app/preferences protection remain
  explicit acceptance conditions rather than inferred successes.

## Later self-contained evaluation

Keep the destination-built tethered app as this bounded target. For a later
self-contained app, evaluate official non-launcher `create-embedding-executable`
/ `raco exe --gui` followed by `assemble-distribution` / `raco distribute`, with
the entire DrRacket/tool/dynamic dependency closure and a separately designed
per-user profile. The distribution API excludes installation launchers; toggling
`relative?` is not sufficient. A clean Mac without Racket, offline launch,
relocation, writable-profile separation, license notices, full-tool parity and
eventual Developer ID/notarization would be new gates. No such packaging is
implemented or represented as complete here.
