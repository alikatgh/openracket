# Separate native gate, not executed or triggered

Authorization for this source preparation does not authorize these commands.
No workflow file, remote trigger, installer/download, cache, Actions artifact,
archive, release or upload is supplied. All detailed output remains local.

## Preconditions

1. An explicitly authorized native Apple Silicon macOS test environment with a
   separately verified official **full** Racket 9.3 CS installation. Record the
   official installer URL/checksum and local provenance separately; do not infer
   origin or completeness from the path shape/version check/inventory digest.
2. A fresh existing parent for owned work/output, outside both original runtime
   and this source tree. Keep the original runtime/source bytes and metadata
   unchanged. All writable test state is newly created mode-0700 test directories.
3. Review the complete nested Info.plist audit before any app launch. Declaration
   keys block direct and Launch Services app execution alike. A full stock runtime
   is expected to need a separately reviewed disposable-copy plan. Do not bypass
   this by launching ProbeNative/ProbeBootstrap directly or stripping metadata.
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
  complete runtime, verifies it against the original inventory, and adds the
  probe. Never assemble inside the generator's destination beforehand.
- Preserves native executable bytes after generation, audits all Info.plists and
  Mach-O dependency/rpaths, and records source/runtime before/after witnesses,
  including failure paths. No nested runtime plist or binary is modified.
- Records `assembled-not-launched` and whether declarations block the next gate.

Do not proceed if declarations are present. There is intentionally no override
flag, automatic deletion or exclusion option. Review the blocked source layout.

Only after every launch precondition is met:

    PYTHONDONTWRITEBYTECODE=1 python3 supervise.py run \
      --build-record /owned-parent/fresh-probe-work/build.json \
      --renamed "/another-owned-parent/Relocated Unicode λ's Path Probe.app"

This is a two-observation path test. It samples the first location, waits for the
owned process group to be gone, moves/renames that owned test app to a fresh path,
and samples again with a second fresh test profile. It does not hide/delete/move
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
- Separate dyld snapshots for GUI and console child. Every non-system image is in
  the bundle. Static dependency/rpath records resolve the sampled image sets;
  ambiguous inherited loader-chain rpaths fail closed. The two Apple system roots
  are canonicalized, so traversal or external symlink tricks do not qualify.
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
