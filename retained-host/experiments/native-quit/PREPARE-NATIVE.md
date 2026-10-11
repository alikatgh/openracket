# Native-owner integration contract (not executed)

Publication and CI triggering are currently on hold for fresh user permission.
This is a source/contract handoff, not a complete workflow integration or a native
pass. The parent-owned native checker must integrate it only after independent
review and a new exact allowlist. Do not alter the 0520 product, accepted builder,
accepted app observer or successful tool gate to make this test pass.

## Inputs and isolation

Use full official Racket 9.3 on the existing free standard macos-15 arm64 runner,
no paid runner/artifact/cache/release facility. Reuse existing exact source copy,
independent runtime copy, full tree/preferences snapshots and read-only default
handler helpers. Entire original runtime and user preference witnesses bracket
all setup/build/compile/cases, and are checked in an unconditional final phase.
Per-case exit acceptance alone does not replace those global preservation gates.

Stock is precisely an **official-generator native app running unchanged
DrRacket**, not the installed branded DrRacket launcher. Confirm the stock
control contains only the exact separate CI driver registration, no modern
appearance/gui overlay package. Its memory preference stays the stock 128 MiB.
Modern uses the unchanged exact 0520 source builder profile, whose existing
owned memory preference is 256 MiB. Neither memory value is set by the driver.
This is UI/exit behavior coverage, not a performance or matched-memory claim.

For each of clean, save, discard:

1. Make one fresh stock case root, own profile/addon/cache and own copy of the
   driver package. Use the accepted official make-native-launcher.rkt with a new
   output named exactly OpenRacketStockQuitControl.app. The official generator's
   bundle ID is derived from that leaf name; do not use spaces in this leaf.
   Its containing case directory and file fixture can have spaces/Unicode.
2. Run scripts/prepare-stock-bundle.py on that newly generated app. It removes
   only a document-association plist entry if inherited, proves native bytes are
   unchanged and retains before/after parsed metadata. Do not alter signing or
   quarantine, dismiss warnings, add metadata with permissions, or register it
   as a default handler.
3. Register that case's separate driver via the same official private-addon
   no-setup link installation, followed by --avoid-main --no-docs --no-launcher
   --no-foreign-libs --no-install --no-post-install scoped setup. Do not use -U
   for this private user-package registration/resolution; it hides user links.
4. Verify collection-file-path resolves the driver to this exact per-case copy
   and its frozen hash. Explicitly compile driver/tool.rkt, driver/contract.rkt,
   driver/cocoa-identity.rkt and tests/contract-test.rkt with that runtime and
   private cache. Config is absent during compilation. Run the actual eight-case
   pure RackUnit contract suite and require exit0 plus the exact count.
5. Create the fixture/config with make-case-config.py, then call run-case.py on
   that config with --driver pointing at this registered driver copy and
   --default-reader pointing at the unchanged accepted app observer helper.
   Only that outer supervisor starts the application. It uses the real native
   stock executable, explicit -A/-R/-l drracket flags and inherited private
   profile variables; no wrapper entrypoint simulates DrRacket.
6. Only if stock passes, create a new modern case root with its own exact155-file
   source copy, separate existing setup/profile and separate driver registration.
   Use the accepted unchanged product build-app.sh with --theme dark and the
   actual independently copied full runtime. Build the normal product .app;
   do not edit its config/bootstrap, native bytes, environment or source.
7. Register/compile/resolve this case's driver as above. Build the config with
   --mode modern-dark, the actual product app/profile/runtime, and run it with
   the same strict per-case supervisor. The real product bootstrap exec chain
   must retain the Python child PID through the actual native application.
8. If the stock case fails, mark its corresponding modern case unrun. Continue
   other independent stock cases only after bounded owned-process cleanup.

Do not copy stale preference files or addon link registries to simulate a fresh
profile. Rebuild path-sensitive registration with the official tools. Driver
configuration and fixtures are created exclusively; never reuse an earlier case
root or retry a launch there. New direct execution is the initially selected
route. An encountered startup/security rejection blocks further launch attempts
pending diagnosis; direct execution is never a fallback for that rejection.

## Commands after preparation

These placeholders are explicit already-prepared paths, not shell discovery:

    python3 -B scripts/make-case-config.py --root CASE --mode stock --case save \
      --app CASE/OpenRacketStockQuitControl.app --profile CASE/profile \
      --runtime OFFICIAL_RUNTIME
    python3 -B scripts/run-case.py CASE/case-config.json --driver CASE/driver \
      --default-reader ACCEPTED_OBSERVER/default-handler.rkt

Use the same forms with --mode modern-dark and the actual product app/profile.
The generated config uses a fixed small #lang racket/base file and one appended
Unicode comment. It refuses overwrites. Never type paths into a Save As picker;
unexpected dialogs stop the gate.

The supervisor writes the driver config only immediately before the first launch
and makes it read-only. It checks that driver config/evidence/capture paths are
fresh. It does not perform any setup, package install, compilation or fallback.
The exact natural returncode of its owned exec-chain child is mandatory.

## Evidence and terminal statuses

Keep each case's case-config.json, launch.json, stage-ready/ACK JSON, actual PNGs,
transcript.json, acceptance.json or failure records, stock-control metadata proof,
product build record, process log and synthetic profile launch logs. Transport
bounded JSON/PNG evidence through the existing ordinary-log helpers only after
its capture ACK; log transport must not consume the 20-second ACK budget.

Complete the stage sequence in order. Initial and repeated Quit confirmation
are stock application-modal windows with no parent; their request-attempt and
sole active frame binding must match. Unsaved dialogs must be parented to that
same frame. Cancel must preserve exact dirty buffer/original disk bytes and
naturally return keyboard focus/edit target to that original live frame. There
is no harness-forced focus return. Preserve original unchecked persistence boxes.

Only the external supervisor can emit a passed case. It requires the actual
final stock control callback receipt, every screenshot ACK, exact post-exit disk
bytes (also recorded as hexadecimal), natural child exit0 before150 seconds,
unchanged native bytes/default handler and no bundle survivor/failure/cleanup.
The driver never calls exit on a successful path. A failed or timed-out process
cannot later become passed. Cleanup is limited to its owned process group after
failure, with an independently reported bounded diagnostic/cleanup interval.

A job-level matrix validator must require all six distinct mode/case results,
correct stock-before-modern ordering, full witnesses and no skipped row before
calling the new native Quit gate green. Do not treat an old run, unit-test fixture
or copied READY report as runtime evidence. All six cases and their dialogs are
currently NOT RUN.

## Source and local checks

Local source-only commands:

    python3 -B tests/test_contract.py
    OPENRACKET_QUIT_BASELINE_ROOT=EXACT_PUBLICATION_45_RETAINED_HOST \
      python3 -B tests/test_source.py
    python3 -B tests/test_stock_bundle.py

These currently cover20 actual validator unit tests,11 source/lexical checks and5 pure stock-control plist tests.
They do not compile Racket. The eight actual Racket contracts, Cocoa bindings,
package registration, native generation, real GUI dialogs and natural Quit exit
must still run on the authorized Mac. No new GitHub action has been authorized.

## Official generator source contract

Immutable core commit: bbf7dea831df95922db23aaa51e13eed17dcf881.
launcher/launcher.rkt:743–757 invokes the official embedding implementation for
non-script macOS GUI launchers, with the caller's empty flag list. The accepted
make-native-launcher.rkt supplies this exact route.
compiler/embed.rkt:172–295 copies the runtime native entry and creates the bundle
metadata; lines250–257 set CFBundleExecutable to the destination leaf and derive
CFBundleIdentifier as org.racket-lang.<leaf>. These facts explain the explicit
stock-control name and the runtime argv contract. Source retrieval is backed up
separately; no retrieved official module is executed or installed here.

https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/launcher/launcher.rkt#L743-L757
https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L172-L295
