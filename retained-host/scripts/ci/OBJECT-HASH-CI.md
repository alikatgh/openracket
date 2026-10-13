# Physical editor object-hash eligibility CI draft

Diagnostic only. No fast path or optimization is implemented, and no timing,
allocation-byte, RSS or candidate-adoption claim is authorized. This adapter repair has not run natively. The preceding native attempt stopped
after read-only configuration inventory, before any core rebuild. The exact adapter composition is source-reviewed and its portable
release gates pass. `OBJECT-HASH-REVIEW-GATE.json` records that bounded review;
it is not a native success claim or independent authorization to publish/run.
The eligibility-only scope deliberately leaves arbitrary child-place dynamics
and the live online-handler registry unobserved.

## Exact inputs and publication scope

- Frozen source: all 59 files of `experiments/object-hash`, with
  `CONTENTS-SHA256.json` SHA-256
  `8fafd9824b2cfeffe3759253ad4e2561b937f76685e9f6c41f5d3bc8f8dfe82c`.
- The publication source package changes only the symlinked-TMPDIR proof report
  and its manifest from the original reviewed source package. Temporary root and
  generated child names are explicitly redacted with relationship-preserving
  placeholders. The report preserves the original successful alias verification
  result and raw-record SHA-256
  `bfc74fcf2664667656f310ba897d0a14e1f54bac992a7fbaeb9a2c9568d7102a`.
  All executable, native, test, generated-core and source-pin bytes are unchanged.
- Official core SHA-256:
  `1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f`.
  Exact diagnostic SHA-256:
  `808a728997c4f085a98fe5c30793c821d9a1097373431addd411370ba2d161d6`.
- Official Racket source commit:
  `bbf7dea831df95922db23aaa51e13eed17dcf881` (`v9.3`).
  The separate supported-command review has SHA-256
  `6bb4661e9e41cb5575abf0760aeab0fb7d8225a200422a0f8704adea39687da7`.
- The unchanged installer downloads the full official Racket 9.3 CS Apple Silicon
  image from
  <https://download.racket-lang.org/releases/9.3/installers/racket-9.3-aarch64-macosx-cs.dmg>,
  SHA-256 `21f4937ca0bf37c31e60c1d77f5fd20f175e3ad51f6197f27149055bc222e559`.
- Publish only the explicit new/changed-file manifest. A partial local snapshot is
  not a replacement checkout; preserve every remote-only helper and prior file.
  Inherited helpers remain byte-identical. Local verification records are not
  publication inputs.

The workflow requires public `alikatgh/openracket`, the exact prototype branch,
standard `macos-15`, checksum-pinned official Actions, a read-only token and
checkout with no credential persistence. No artifacts, actions cache, deployments,
paid compute, security changes, package registration or source-installation edit
is introduced.

## Isolation and preparation

Two newly named, independently deep-copied arms are `object-hash-stock` and
`object-hash-diagnostic`. Each has physical workspace W, runtime C=W/runtime,
source package Q=W/probe, helper source H=W/ci, sole compiled root K=W/compiled,
and clone-only quarantine W/quarantine. Profiles are fresh W/profile-CASE roots
with distinct addon, temporary, XDG config/cache/data directories.

Existing ancestor aliases such as a symlinked TMPDIR are canonicalized once.
Internal symlink components, escapes, dangling destinations, overlap, colon path
list delimiters and shared regular device/inode pairs are refused. Regular files
must have one link. The entire official original is manifested before any work
and after every outcome, including a failed or uncertain launch. Records include
all entry names, file bytes/size/mode, directory modes and link targets. Separate
independence records capture inode/link facts.

The helper composition is independently exact-manifest-pinned before copying
and verified again in each arm. The diagnostic overlay stages and reverses the frozen exact core transform. Only
C/collects/racket/private/class-internal.rkt changes. Stock uses the original
source. Config, package registrations and links are inventoried without repair.
Every source/config/link/library/metadata/write destination must stay within the
owned clone or fresh profile/cache. Unknown config keys fail closed. Initial
inventory does not force PLTCOLLECTS and therefore does not hide extra installed
collection roots; later processes inherit the complete validated list.

Directory spellings in the raw inventory remain unchanged as evidence. Only
config collection/link path comparisons normalize trailing separators and safe
parent components, after checking each original component for links and escape.
The validated collection order and extra roots are preserved. Root identities,
sole-cache cardinality and the class source/hash checks remain exact.

Each clone has an initial full-runtime baseline, including the arm that has not
started preparation. The after-overlay baseline is accepted only after proving
the exact permitted class-file change and equality of every other entry. Before
quarantine, final runtime equality is exact, including original bytecode and
metadata. Quarantine records an fsynced phase/intent/completion JSONL journal;
partial failures preserve every record plus the final in-memory move state.
During partial quarantine, only recorded moves may differ, with exact target
bytes/mode/inode validation; no metadata rewrite is allowed. Once quarantine
completes, declared metadata rewrites are permitted, while installed bytecode
outside the sole rebuilt root remains forbidden. Missing, changed or unrecorded
quarantine products fail the witness. An earlier failed phase remains failed
even when the corresponding final preservation witness succeeds.

Quarantine moves every copied .zo/.dep and compiled .rktd metadata cache, plus
info-cache.rktd, from C to W/quarantine. Compiled native-extension products require
separate review. Runtime executables, CS boot images and ordinary FFI libraries
remain unchanged. K must be fresh, empty, absolute, physical and the sole
compiled root. No `same` or empty/default-splicing fallback is allowed.

The environment drops inherited experiment, Racket, Python, loader and credential
state. It sets HOME, PLTUSERHOME, PLTADDONDIR, TMPDIR, XDG paths, PLTCONFIGDIR,
PLTCOMPILEDROOTS and PLT_ZO_PATH=compiled explicitly, with clone bin first in PATH.
All Racket commands use the absolute clone executable and this prefix:

    C/bin/racket -X C/collects -G C/etc -A P/addon -U -R K

## Command phases and bounded allowances

Every command preserves exact argv/environment, raw stdout/stderr, exit status,
partial outcomes and cleanup status. The deadline starts before process spawn.
No later native command starts after failure or uncertain process cleanup. A
fsynced prelaunch lease survives uncertain spawn and reporting failures.

For each arm, in this order:

1. Read-only source inventory, 90 seconds:
   prefix -c -I racket/base -t H/config-inventory.rkt
2. Class-first kernel setup bootstrap, 600 seconds:
   prefix -l setup -- --boot H/core-first.rkt K
3. Independent core source/.zo/.dep receipt, 90 seconds:
   prefix -c -I racket/base -t H/rebuilt-receipts.rkt -- core
4. Full installed code setup, 1800 seconds:
   prefix -l setup -- --no-user --no-docs --no-launcher
   --no-foreign-libs --no-install --no-post-install --jobs 1 --fail-fast -v -r
5. Complete frozen native source compilation, 300 seconds:
   prefix -l raco -- make -v SORTED_13_NATIVE_RKT SORTED_10_VENDOR_HOST_RKT
   The two .rktd inputs are retained exact data, never passed as modules.
6. Independent CI helper compilation, 180 seconds:
   prefix -l raco -- make -v SORTED_H_RKT
7. Full source-backed known-graph receipt, 180 seconds:
   prefix -t H/rebuilt-receipts.rkt -- full

The standalone executable `--` is mandatory after `-l setup` and `-l raco`.
Supported flags and bootstrap are pinned to official
[setup/main.rkt](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/setup/main.rkt),
[setup-cmdline.rkt](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/setup/setup-cmdline.rkt)
and [CS main.sps](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/src/cs/main.sps).
No collection/package selector, trust-zos, recompile-only, avoid-main, no-zo or
error-out shortcut is used. Setup success alone never satisfies the receipt gate.

Only after both arm rebuilds and all coverage gates pass:

- Sixteen diagnostic actual-form scenarios, each a fresh process/profile with a
  30-second bound. `off` uses exact flag 0; the other fifteen use exact flag 1.
- Three genuine small Check Syntax runs, each a fresh process/profile with the
  unchanged 60-second outer bound and original READY/capture/ACK protocol.
  Stock runs Q/vendor/host/tests/reference-host-0520.rkt directly.
  Diagnostic off/on run Q/native/bootstrap.rkt -- off/on C.
- Every case preloads the independent read-only H/audit-loads.rkt via `-t`, then
  loads the untouched target via `-t`; the target's existing argv is unchanged.

Racket deadlines total exactly 7140 seconds: 2×3240 seconds of rebuild work,
16×30 seconds of semantics and 3×60 seconds of genuine host work. There are 33
Racket processes. Separate conservative reserves cover up to 30 seconds cleanup
per Racket process, 30 seconds per screenshot process, 120 seconds portable
checks, 900 seconds local deep-copy/hash/quarantine/final witness work and 600
seconds evidence encoding. Combined allowance is 9840 seconds (164 minutes); the
main step has 165 minutes. This is a safety ceiling, not a runtime estimate or a
GUI timeout extension. Other step ceilings are 2 minutes public metadata,
3 minutes checkout, 20 minutes full installer, 5 minutes independent final
witness and 1 minute summary: 196 minutes total. The job ceiling is 200 minutes.

## Proof and explicit boundaries

Required pins include class, GUI, framework text/color, snip style/prefs, DrRacket
unit/tool/syncheck, interval-map and switchable-button. Receipts recursively close
actual .dep/compiled-import/runtime-module-path references and all installed tool
registration targets to exact source and K-only .zo/.dep files, with primitives
classified separately. Missing compiled-only source, omissions of a required
module, out-of-root dependencies or stale products block execution.

The pinned expanding-place/start root and its known recursive source-backed
closure are mandatory. The live ordered online-handler (module/export/monitor)
registry getter is lexical to the instantiated module-language-tools unit; it is
not a module export. Static registration cannot pretend to be this live ordered
registry. Receipts explicitly retain live_registry_observed=false and
online_handler_registry_complete=false. No additional runtime-source overlay is
introduced to observe it. The exact API/source pins are in the helper provenance.

Actual load auditing covers the initial place and inheriting threads. It rejects
source fallback or unaudited selected bytecode there. New places have independent
parameters: accepted scope must retain arbitrary_dynamic_graph_proven=false and
child_place_dynamic_audit_complete=false. A stable K is not proof of arbitrary
child-place dynamic load coverage. This known installed/static graph plus
host-place coverage supports only the eq?-bound GUI-handler scalar diagnostic.
It cannot establish a complete dynamic worker/handler graph or support a future
speed benchmark.

The standalone full receipt performs recursive reflection once per arm. After
Python verifies it, an exact raw-byte copy at W/prebuild-receipts.json is bound by
OBJECT_HASH_PREBUILD_RECEIPT_SHA256 in each case/host command. The bounded guard
uses its immutable known closure map, validates source/.zo/.dep bytes at first
actual resolution and bytecode digest on every selected load, and fails on an
unknown module. It does no recursive expansion inside the 30/60-second bounds.
Bootstrap environment is checked once; effective resolver/configuration paths
are checked on every load, allowing documented temporary getinfo environment
views. This is non-hostile-concurrency validation, not a security sandbox.

Full K before/after inventories and every observed addition are retained. Every
required prebuilt source/.zo/.dep input is revalidated after execution and must
remain identical. New owned K products are reported as observed additions,
without assuming they are fixture products or claiming K stability/child coverage.

The frozen diagnostic proves its actual core source, build marker, module token,
flag and genuine handler/editor identity. Original Check Syntax and repeated Run
assertions, exact typed eight-edge graph including four zero spans, successful
native exit, valid screenshot and capture handshake remain required. Synthetic
semantic fixtures are not real-editor eligibility evidence. Zero matches,
incomplete accounting, diagnostic faults or inspection failures remain unresolved.
Even a completed eligible match establishes only the reviewed prerequisite.

## Evidence and portable verification

Complete original, clone and compiled-root inventories remain local. For each,
transport preserves exact raw SHA-256/bytes, entry count/tree digest and every
changed before/after entry without truncation. Required source/.zo/.dep closure
receipts, command outcomes, actual eligibility states, screenshots and raw
streams remain lossless in one bounded .xz bundle. Its canonical manifest gives
safe relative paths, exact original byte lengths and SHA-256; original file bytes
follow in order. This is not a general archive or executable artifact.

The main compressed cap is 4 MiB; base64 is about 5.34 MiB before bounded wrapper
headers. The independent final witness has a separate 512 KiB compressed reserve. Limits also cover each file (128 MiB), aggregate raw files (256 MiB),
file count (512), manifest (1 MiB) and decoder memory. The unchanged bounded JSON
emitter carries the envelope once. Decoder checks exact compressed and original
hashes, rejects duplicate/case-colliding/unsafe paths, links, truncation, trailing
or concatenated XZ, and oversized output. Oversize or partial emission explicitly
blocks interpretation; every original byte remains local, no file is silently
dropped, and an emitted document is never retried or recompressed. These are
conservative limits below observed connector log volume, not a guarantee about
connector recovery. See OBJECT-HASH-TRANSPORT.md for exact schema and tests.

The raw stream ceiling is 128 MiB per process and is checked while running and
again after exit. Exceeding it rejects the process and preserves observed bytes.
PNG acceptance checks bounded decompressed scanline data, not only container
CRCs. Final witness collection is read-only and cannot start native processes.

Run all source generators/pins, both source test entrypoints, new adapter tests,
helper provenance/static checks and existing transport tests in fresh Python
processes, normally and with TMPDIR explicitly pointing to a symlink. Ordinary
fixtures canonicalize centrally; explicit alias/escape refusal tests remain.
Case-fold duplicate inventory cases are simulated rather than creating names that
cannot coexist on a default Mac filesystem. Portable tests do not prove Racket
syntax, bootstrapping, relocation, live private APIs or native GUI behavior.

## Configuration/witness repair provenance

The prior native configuration receipt is 399,864 exact bytes with SHA-256
`cec4dee6e99dd034935f1be2b76be7bd5db0adf2367c21250d9f5ab096c2bc1d`.
It contains 931 path rows, a trailing-separator main collection directory, and
raw parent-relative link-file paths. A complete relocated fixture replay preserves
all receipt fields and spellings while replacing only the arm-root prefix; it
passes the repaired guard. Portable regressions cover those representations,
link/escape refusals, unprocessed arms, failed inventory, interrupted quarantine,
metadata timing, completed-quarantine build failure, and preserved final original
runtime evidence. No frozen source, native helper, timing bound or workflow byte
changes are part of this adapter-only repair.

The full 931-row native-receipt replay is a separate local provenance check,
not a required CI fixture or a dependency on a sibling results directory. The
published portable suite uses self-contained synthetic fixtures preserving the
observed directory/link representations and refusal cases.

The supplemental `test-object-hash-adapter.py --estimate-quarantine` command adds
8,192 synthetic quarantine moves per arm to the prior transport model: full
intent/completion journals, both final-state copies and every removal-witness
entry. All 79 files (88,376,969 raw bytes) round-trip exactly in 3,105,936 XZ bytes
and 4,157,640 emitted bytes. These counts are synthetic, not observed native
product counts or a guarantee that the real run fits. Per-move fsyncs consume the existing local preparation allowance; their native
filesystem cost is unmeasured. No native bound increases.
The unchanged 4 MiB compressed cap reports incomplete evidence on overflow and
never drops journal rows or falls back to unbounded raw output.
