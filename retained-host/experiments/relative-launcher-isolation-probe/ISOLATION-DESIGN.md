# Fixed launcher-only isolation derivative

## Scope and historical evidence

This source-only tree derives from the exact 23-file
`openracket-packaging-path-fixture-freeze-20261011-1706` input. Its MANIFEST SHA-256
is `2e02a8a283b420be3d580328bce739af35ec59d5f050f8c20315156324e5c151`.
The frozen input remains unchanged. `evidence/ISOLATION-INPUTS.json` records the
base file hashes and two historical native evidence pins.

Native audit run 38159705157 belongs to the base, not this derivative. It recorded
26,838 original runtime entries, unchanged protected inputs, an unchanged null
.rkt handler, no pending static loader contexts, and zero app launches. Its
only document/UTI-claiming plist was the copied top-level stock
`DrRacket.app/Contents/Info.plist`; the generated outer probe had no claims.
Nothing here rewrites that evidence or turns it into a launch result.

## Smallest assembly change

`runtime_copy_plan` partitions the complete original lstat inventory at the exact
relative path `DrRacket.app`, including its directory entry and all descendants.
It rejects a missing entry, a symlink/file in its place, or another top-level
case-insensitive spelling. The exclusion is a code constant, not a CLI option.

`copy_isolated_runtime` uses a root-only `copytree` ignore callback. It never
deletes a runtime entry, edits a nested plist, recursively matches app names, or
shrinks any other part of the runtime. A nested `other/DrRacket.app`, PLT Games,
Slideshow, `lib/GRacket.app`, console Racket, collections, packages, documentation,
licenses and shared libraries are all retained. Every retained entry must match
the original witness exactly: path set, type, content hash, mode, modification
time and relative symlink target. Original root metadata is copied too.

An existing destination, source/original overlap, changed original witness, or a
retained symlink resolving into the omitted launcher fails closed. Symlinked
temporary-parent paths are canonicalized, as in the base. The complete original
inventory and source inventory are still written; before/after protected-input
witnesses still apply to both successful and failed assembly.

The new `runtime-copy-plan.json` contains the complete excluded-entry manifest,
the fixed exclusion path, and original/excluded/retained digests and counts. A
future run reconstructs the partition from the full original witness and demands
that this manifest match exactly. It compares the actual copy with the retained
partition, rather than accepting a declared retained digest alone. An available
original installation must still equal its assembly witness.

## No metadata workaround

Every retained nested plist stays byte-identical. The existing outer generated
probe identity/bootstrap field updates remain necessary to the original probe
contract. Its previous declaration-key stripping is removed: any declaration
key in the generated outer skeleton now stops assembly before rewriting it.
This is not permission to edit an existing app's metadata or alter native bytes.

## Unchanged CLI, stricter launch gates

The existing `run --build-record ... --renamed ...` CLI already expresses the
two-location test and stays unchanged. Its runtime equality check now uses the
fixed retained partition. It refuses a nonempty recorded static pending list,
freshly audits all plists and Mach-O dependencies before launch, and repeats
the fresh audits after relocation before any second native query or observation.
Missing dependencies, non-file loader targets, escaped dependencies and pending
`@rpath`/`@executable_path` contexts block. No pending-context override exists.

Actual ProbeNative bytes, bootstrap argv/environment, runtime/module witnesses,
console-child distinction, Cocoa identity, default-handler observations, owned
process cleanup, relocation comparison, and loaded-image closure validation are
otherwise unchanged. Security warnings remain blockers. There is no signing or
security-policy workaround, remote trigger, installation, download or upload.

## Portable verification and next gate

All current and new Python tests run normally and with an explicitly symlinked
TMPDIR. Mocked native entrypoints generate only synthetic filesystem fixtures;
no Racket, Cocoa or Mach-O image is executed. Negative cases cover original and
occupied destinations, alias/conflicting launcher paths, unexpected claims,
retained links/dependencies into the exclusion, missing loader targets, stale
manifests, mutated originals, and re-audit at the second location.

Review and backup of exact source bytes precede any freeze. A separately
authorized native run must establish actual relocation and Cocoa/process
identity; this derivative does not establish self-contained-app compatibility,
WXME correctness/timing, clean-Mac operation, licensing approval, signing,
notarization, security-warning acceptance, or binary delivery.
