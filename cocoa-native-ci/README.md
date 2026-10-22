# OpenRacket Cocoa source and native checks

This distribution contains the Cocoa editor, Rust/Racket engine, build inputs,
licenses, tests, and a bounded macOS CI workflow. The application has not yet
passed this native workflow. Compilation, ordinary macOS behavior, VoiceOver,
system IME, screenshots, performance, and DrRacket parity remain unverified.
No installer or DMG is included.

## Source admission

`PUBLIC-SOURCE.json` describes only the 1,159 distributed source files. Every
entry records its relative path, size, SHA-256 and read-only mode. The adapter
pins this manifest and the bundle/part descriptors by their exact SHA-256.
Nine parts reconstruct a single bounded source-only XZ frame. The decoder
requires exact member closure, paths, modes, sizes and hashes; duplicate or
case-folding paths, links, special files, trailing streams and extra data fail.
All data is validated before any member is written.

Application, engine and runtime helper source bytes are unchanged from the
reviewed source baseline. The process supervisor now handles Darwin session
lookup failure for a proved owned, unreaped zombie. It also handles a rejected
group signal only when a fresh strict inventory proves that the owned group is
already quiescent; a denied signal is never recorded as delivered. Focused
regression tests and dependent hash pins cover these fixes. Live-child identity,
permission failures without that proof, and cleanup ownership remain fail-closed. One benchmark helper's purpose docstring has been made
self-contained; its executable body is unchanged. Development
history, prior results and local provenance are not distributed. The public
source admission does not require or disclose an inventory of excluded files.

The root license, all vendored licenses, Cargo lock/checksum files, exact
Scintilla upstream source archive and extracted sources, Apple API source proof,
and public compiler/runner references are retained. Third-party code remains
unaltered. The archive is an inert test input, not a downloaded executable.
No compiled runtime, helper library or application binary is included.

## Workflow

The explicit distribution map places these files under `cocoa-native-ci/`,
except `cocoa-native.yml`, which belongs at `.github/workflows/cocoa-native.yml`.
A local prepared directory is not permission to publish or run the workflow.

1. Require the intended public repository and exact commit checkout with a
   read-only token. Require preinstalled Darwin Python 3.13 or later and its
   supported process-observation APIs. Reuse the separately hash-pinned official
   Racket installer already present in the repository.
2. Record the complete original runtime's filesystem state and root identity.
   Reconstruct and verify immutable source inputs before loading source helpers.
3. Build one inventory helper with the selected physical Xcode compiler and
   public SDK, within 90 seconds. A durable blocked lease precedes spawn; the
   direct child remains unreaped until identity and cleanup can be established.
   Only successful compilation and verified quiescence unlock later launches.
4. Use fresh source workcopies, runtime copy and private profiles. Require all
   three native supervisor prerequisites (120 seconds), compiler/runtime version
   receipts (15 seconds each), offline locked Cargo release (240 seconds),
   Cocoa build (600 seconds), and unchanged native app smoke (30 seconds).
5. Only natural zero exit and the exact all-engines-finalized marker permit
   later launches. Any failure, timeout or interruption blocks subsequent native
   work. Successful smoke is followed by the unchanged full mandatory native
   gate in another fresh workcopy/profile, within 7,200 seconds. Original child
   bounds remain in effect.
6. Independently verify original runtime, immutable source and all created
   workcopies. A failed witness revokes acceptance. The always-run finalizer
   attempts witnesses and bounded lossless evidence transport independently.

The 190-minute job uses the ordinary public macOS runner. It does not upload
artifacts, use an Actions cache, expand token permissions or configure external
services. Repository visibility is checked before native work.

## Evidence and limits

Future CI logs will contain generated compiler/SDK identities, commands,
source/application hashes, disposable runner paths, synthetic test outcomes and
raw compiler/runtime streams. Local authoring paths or historical result files
are not inputs. The complete original-runtime inventory stays runner-local for all existing
checks. Logs receive its exact raw byte count/SHA-256, entry count, tree digest
and root identity, plus every changed before/after entry from the unchanged
final comparisons. The compiled-app inventory is retained because it binds
actual built binaries and resources to their hashes. It contains only the app
built from these public inputs. No unrelated host directory is inventoried.
Generated evidence uses
an existing pinned codec with a 4 MiB compressed/512-file bound. Exceeding a bound
is incomplete evidence, never a silent omission or substitute success.

The smoke exercises a limited real application workflow; it does not validate
ordinary Stop, all file dialogs, physical input, system IME, VoiceOver or editor
latency. Screenshots are deferred in this compile-first workflow. A successful
build or smoke must not be presented as complete native UI acceptance.
