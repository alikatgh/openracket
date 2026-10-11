# Fixed launcher isolation: bounded native CI adapter

This is a separate CI adapter for the reviewed source-only launcher-isolation
experiment. It does not modify the accepted product, its builder, the original
runtime, the older packaging audit, or any frozen probe bytes. The frozen README
and acceptance documents describe that source snapshot's preparation state; this
adapter is the separately reviewed execution mechanism. Native results must come
from the exact subsequently executed commit, never from portable tests.

## Exact input and execution contract

The source at `retained-host/experiments/relative-launcher-isolation-probe` has
exactly 29 files (28 manifest members plus the manifest). Its MANIFEST SHA-256 is
`25af97fe2273422c77135e999d6887c59c35a1b0c51308b6ea435b09ccb057a1`.
The adapter rejects different content, extra files and source symlinks.

1. Before allocating the standard `macos-15` runner, require a public push to
   `alikatgh/openracket`, branch `prototype/retained-drracket`. Recheck public
   repository metadata, use the existing pinned official actions with
   `contents: read`, exact-commit checkout and `persist-credentials: false`.
2. Run every frozen source, adapter and transport test in new subprocesses with
   `TMPDIR`, `TMP` and `TEMP` explicitly pointing through a symlink. The release
   gate proves that Python actually selected the alias in a fresh process.
3. Use the unchanged checksum-pinned full official Racket 9.3 CS installer.
   Its existing version, VM and setup-directory queries precede the independent
   immutability baseline; the report explicitly preserves this boundary.
4. Save independent full original-runtime and source inventories before importing
   probe code or making a probe query. Read the actual account's .rkt handler.
5. Invoke frozen `supervise.py audit-runtime` with a fresh output, then frozen
   `supervise.py build --runtime … --work … --expected-runtime-digest …`.
   Both the work parent and relocated app use spaces, Unicode and an apostrophe.
6. Validate the build receipt, protected-input witnesses and full fixed exclusion
   manifest. Compare the complete retained runtime with the original minus only
   the exact top-level `DrRacket.app` subtree. Its source directory, bytes, modes,
   modification times and links remain untouched. No nested plist is stripped.
7. Reject every remaining document/imported/exported UTI declaration key, even
   when empty, and every unresolved static loader context. Independently repeat
   the live audit and verify the generated native hash before the only app route:

       python3 supervise.py run --build-record …/build.json \
         --renamed "…/Relocated Unicode λ's Path Probe.app"

   The frozen run itself rechecks the retained tree, all plists and all static
   loader references before either location and before its pre-launch handler
   queries. It owns both observations and does not relocate after any failed or
   uncertain first observation. There is no alternate direct-launch fallback.
8. Accept only successful CLI exit plus exact two-location native receipts,
   independent process/Cocoa identities, console-child observation, active dylib
   closure, immutable bundle/source/runtime witnesses and unchanged defaults.
   The frozen validator retains the stronger live-filesystem path/module/config
   and process-owner checks; the adapter checks that raw reports match its summary.
9. In the separate always-run verification phase, native queries are possible only
   from a validated safe state and unchanged original source/runtime inputs.
   Missing or symlinked originals block queries, but do not stop the other
   independent filesystem witness. Then transport the available diagnostic files.

## Durable ownership and independent ceilings

Before any native command or read-only handler query, atomically replace the
state with `pending-*` and fsync the file and parent directory. Native admission
requires this to succeed. A remaining partial state write blocks later native
work. A failed, interrupted or nonzero native command leaves unresolved state;
CLI success alone never restores safety. No retries or security workarounds are
introduced. The original supervisor still bounds each owned process group at
120 seconds plus a separate maximum 5-second cleanup proof, with the original
1 MiB combined profile-output limit. A cleanup failure blocks every subsequent
native call; independent filesystem collection remains available.

The run phase has at most 11 sequential native commands: one independent initial
handler query, four build queries/compile/generation commands, and three commands
at each of two launch locations. `11 × (120 + 5) = 1375` seconds, leaving 725 seconds
for complete inventories, copying and static checks within its 35-minute ceiling.
The final phase has at most one 125-second handler query and 475 seconds for
filesystem witnesses/evidence within 10 minutes. No shorter wrapper timer kills
the frozen supervisor while it may own independently started process groups.

Other step ceilings are public check 2 minutes, checkout 3, all portable tests 3,
unchanged installer 15, and final summary 1. Their sum with the run/verification
ceilings is 69 minutes; the job allows 70 minutes. The installer margin covers its
existing maximum three 240-second transfer attempts plus normal local setup.
Emergency step/job cancellation never turns pending work into acceptance.

## Evidence and decoding

Native timing ends before diagnostic encoding. All selected logs, excluded-entry
rows, source inventories, audit metadata, build receipts, startup-minimal data,
full path/identity/console-child reports, post-launch/default witnesses and partial
malformed output bytes are transported losslessly through bounded ordinary CI
log lines. Nothing is truncated to obtain a pass.

Full original and retained runtime inventories remain runner-local, matching the
reviewed audit boundary. Transport includes their exact raw SHA-256, byte counts,
entry counts and canonical inventory digests, plus every changed entry. The fixed
exclusion manifest transports every excluded entry. No app/runtime binary,
arbitrary profile directory or unrelated user file is emitted.

Each raw byte wrapper carries its exact `proof/…` or `reports/…` source-relative
path, byte count, SHA-256 and base64 chunks. Thus repeated `result.json` or stdout
basenames remain unambiguous even if the separate evidence index is unavailable.
Index, error-tail and final-result emissions are independently attempted. Any
missing required file, malformed transport, oversized file or emission failure
keeps acceptance red. Use the matching strict decoder:

    python3 retained-host/scripts/ci/decode-launcher-isolation-evidence.py \
      native-job.log fresh-decoded-output

It validates chunk/document/whole-file integrity and writes
`decoded-launcher-isolation-index.json`, including each source-relative path.
Transport wrappers differ from older light-tool/packaging wrappers; do not use
those older decoders for this derivative.

## Local review and publication boundary

Run the complete release gate with:

    PYTHONDONTWRITEBYTECODE=1 python3 \
      retained-host/scripts/ci/check-launcher-isolation-release.py

This performs portable synthetic/source/transport tests only. It never installs
or starts Racket. Keep development `local-review/` files and raw local test logs
out of publication: they may contain private interpreter/workspace labels. The
publication manifest contains only explicit relative file names, sizes and
hashes. A publication is an overlay on the existing repository, not a replacement
for its unlisted files or active run.

No paid runner, artifact service, cache, deployment, Release upload, credential
expansion, default-handler reset, signing command, quarantine removal, Gatekeeper
change or rejected-app launch is included. No diagnostic screenshot process is
added after failed/uncertain native state. Original preference-file bytes are not
separately observed; the native probe uses isolated disposable profiles and keeps
the exact read-only global default-handler witnesses.

A pass means only two measured path/identity observations passed. Clean-Mac
provenance, full DrRacket startup, transferred-app security, read-only app behavior,
user-package semantics, optional-library closure, signing/notarization and full
distribution acceptance remain outside this experiment.
