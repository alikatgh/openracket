# Separate native gate, not executed or triggered

Authorization for this source preparation does not authorize these commands.
No workflow file, remote trigger, installer/download, cache, Actions artifact,
archive, release or upload is supplied. All detailed output remains local.

## Preconditions

This derivative preserves the existing run CLI and identity/relocation contract.
The reviewed top-level `DrRacket.app` exclusion remains unchanged; see
`ISOLATION-DESIGN.md`. This derivative adds only paired public-dyld cache/header
witnesses and their validation. Run 38164494081 remains a failed first-location
probe, with relocation withheld and no retroactive acceptance. See
`SHARED-CACHE-DIAGNOSIS.md`.


1. An explicitly authorized native Apple Silicon macOS test environment with a
   separately verified official **full** Racket 9.3 CS installation. Record the
   official installer URL/checksum and local provenance separately; do not infer
   origin or completeness from the path shape/version check/inventory digest.
2. A fresh existing parent for owned work/output, outside both original runtime
   and this source tree. Keep the original runtime/source bytes and metadata
   unchanged. All writable test state is newly created mode-0700 test directories.
3. Review the complete nested Info.plist audit before any app launch. Declaration
   keys block direct and Launch Services app execution alike. The fixed top-level stock
   launcher exclusion is the only allowed omission. Do not bypass remaining
   claims by launching ProbeNative/ProbeBootstrap directly or stripping metadata.
   Every static loader reference must resolve with an empty pending-context list.
4. Current-account .rkt-handler read-only query must succeed before generation.
   Keep actual default state unchanged. The initially-unset test is conditional;
   do not clear/reset handlers or create another account to manufacture coverage.
5. Security warnings are blockers. No manual signing, quarantine removal,
   Gatekeeper bypass, default-handler setter or security setting changes.

## Bounded CLI contract

These are templates, not already-run commands. Substitute confirmed absolute
paths; the full runtime witness digest is printed by the read-only audit.

    PYTHONDONTWRITEBYTECODE=1 python3 supervise.py audit-runtime /verified/Racket \
      --output /owned-parent/runtime-audit.json

This reads binary/source/plist metadata without executing it, rejects escaping or
absolute runtime symlinks, and records SHA-256/mode/mtime/link/type inventory,
nested declarations and Mach-O dependency/rpath rows. It writes one fresh local
report outside inputs and prints a compact summary (at most 16 KiB).

    PYTHONDONTWRITEBYTECODE=1 python3 supervise.py build \
      --runtime /verified/Racket --work /owned-parent/fresh-probe-work \
      --expected-runtime-digest THE_EXACT_AUDIT_INVENTORY_DIGEST

This native-only command:

- Takes a read-only .rkt-handler baseline before generation
- Reads and compiles all probe Racket modules through a selected console runtime
  with sanitized environment, explicit core/config/addon/compiled paths, `-U`,
  and a fresh test HOME/TMPDIR. Reader/compile failure stops before generation.
- Invokes the official generator once on an absent .app path, then copies the
  runtime except the exact top-level `DrRacket.app` directory, records a full
  `runtime-copy-plan.json` excluded-entry manifest, verifies every retained entry
  against the original inventory minus that fixed exclusion, and adds the probe. Never assemble inside the generator's destination beforehand.
- Preserves native executable bytes after generation, audits all Info.plists and
  Mach-O dependency/rpaths, and records source/runtime before/after witnesses,
  including failure paths. No nested runtime plist or binary is modified.
- Records `assembled-not-launched` and whether declarations or pending loader
  contexts block the next gate. The full original witness is kept unchanged.

Do not proceed if declarations or unresolved loader references are present.
There is no override flag or configurable exclusion option. The single fixed
copy-time exclusion never deletes anything from the original installation. Any
retained link or loader dependency into the omitted launcher is a blocker.

Only after every launch precondition is met:

    PYTHONDONTWRITEBYTECODE=1 python3 supervise.py run \
      --build-record /owned-parent/fresh-probe-work/build.json \
      --renamed "/another-owned-parent/Relocated Unicode λ's Path Probe.app"

This is a two-observation path test. It samples the first location, waits for the
owned process group to be gone, moves/renames that owned test app to a fresh path,
and samples again with a second fresh test profile. Before either observation,
it rechecks the exact retained tree, every Info.plist and every Mach-O dependency;
these checks precede the read-only pre-launch handler query too. It does not hide/delete/move
the original installation. A path-only JSON acceptance is insufficient unless
the actual process/Cocoa identity and active dylib closure also pass.

Every native command has a 120-second wall limit and 1 MiB combined profile-log
limit, including GUI child stdout/stderr. Commands run with direct argv and no
shell interpolation. A bound violation stops only its owned process group, with
a separate five-second maximum wait to prove leader reaping and group death.
Signal, wait or group-recheck errors all become cleanup uncertainty and block
further native queries and relocation. A group surviving its leader invalidates
the observation even if the bounded stop proves death. Cleanup uncertainty is
never success. No retries are automatic; partial output remains for review.

## Required native observations

`NATIVE-OUTPUT.schema.json` describes the successful in-process JSON shape. The
supervisor applies stricter live-filesystem checks in addition to the schema:

- Actual version 9.3, macOS, CS; separate console-child version/GC/PID
- Base+racket/path early `startup-minimal.rktd`, recording collection-link/user
  switches and executable/collects/config paths before json/setup/dirs imports
- Restored collection links and disabled user-specific search paths; rich startup
  and later path records, including exec-file/run-file/config/collects/addons,
  HOME/preferences/temp, compiled roots, package/lib/doc/links roots/searches
- Current bundle .app, `ProbeNative` actual process image, unchanged PID through
  bootstrap exec, independent NSRunningApplication and NSBundle identity
- `exec-file` exactly the bundled console runtime; actual run-file separately the
  outer native binary. The console child is started by the GUI using exec-file.
- Independently resolved/hash-checked source files for racket/base, setup/dirs,
  pkg/lib, racket/gui/base and drracket/main. No DrRacket module instantiation.
- Config/collection-link/package-database files and content hashes. Links/database
  must exist for this full-runtime target. An absent default config.rktd is recorded
  as absent, never assigned a fictitious hash. Actual effective config remains
  inside the bundle and all resolved setup paths must stay confined.
- Separate dyld snapshots for GUI and console child preserve raw image strings.
  Every image is paired by exact native index and raw name with its non-null
  header address, magic, CPU type, file type, flags and exact Boolean public
  `_dyld_shared_cache_contains_path` result. Counts/names/header pointers must
  remain equal in checks before and after collection. An unavailable API or any
  mismatch fails the observation. Public enumeration is not an atomic lock;
  this bounded probe performs no intentional concurrent load/unload operations.
- A cache exception requires BOTH the same loaded header's `MH_DYLIB_IN_CACHE`
  bit and affirmative cache-path query, a 64-bit arm64 dylib header, and a raw
  normalized `/System/Library/` or `/usr/lib/` name without traversal. Such a
  virtual cache name is preserved, not resolved to a nonexistent disk file.
  No Cryptex prefix is allowlisted. All other images need real files canonically
  inside the bundle or existing system roots; missing runtime files still fail.
  Static dependency/rpath gates are unchanged. Active closure uses the same
  classifications; ambiguous inherited loader-chain rpaths still fail closed.
- Before/after full bundle bytes/modes/mtime/link inventory equals; original
  source/runtime witnesses equal; .rkt-handler baseline equals across generation
  and both launches. A failed native operation also preserves available witnesses.
- Resolved module/config/link/database contents remain equal after rename; their
  raw/canonical absolute locations update to the relocated bundle.

## Strict interpretation and remaining acceptance

`bounded-path-probe-passed` means only that these two measured path/identity
observations passed. It never means the app is ready for distribution. The
summary always sets `full_distribution_acceptance` and `clean_destination_tested`
false. `recorded_original_runtime_absent` reports just that single path's absence;
it is not proof that no other Racket installation exists on the Mac.

The following remain outside this experiment: full clean-destination provenance,
all optional or not-yet-loaded native libraries, nested-launcher functionality,
Racket places, arbitrary language readers/user programs, actual DrRacket startup,
tool discovery, product relaunch behavior, Help Desk/search, read-only application
operation, writable-user-package semantics, preferences/restart persistence,
file opens/default-association scenarios beyond the read-only witness, exact
runtime metadata/xattr copying, licensing, size, delivery, signing/notarization
and Gatekeeper. No user-profile initializer or accepted-product refactor is here.
