# Object-hash native rebuild helpers

Source-only implementation. Native Racket parsing, expansion, bootstrap,
compilation, GUI execution and these runtime APIs remain unrun. The portable
checks below are source contracts and delimiter checks, not native validation.

## Invocation contract

The supervisor owns deep copies, exact source hashes, per-process environment,
config validation, quarantine, timeouts, process groups, cleanup, original-tree
witnesses, screenshots and final acceptance. These helpers do not replace those
gates. For one physical arm workspace W:

- C = W/runtime, Q = W/probe, H = W/ci, K = W/compiled
- every process gets a fresh P = W/profile-CASE
- HOME and PLTUSERHOME are P; PLTADDONDIR and -A are P/addon
- PLTCONFIGDIR and -G are C/etc; -X is C/collects
- PLT_ZO_PATH is compiled; PLTCOMPILEDROOTS and the sole -R are K
- -U is mandatory; no additional/default-splicing compiled root is allowed
- before inventory, PLTCOLLECTS is unset; after validation it contains the entire
  effective, validated clone collection list without empty elements
- the supervisor rejects shared files, path overlap, internal symlinks, native
  extension cache products and unapproved external config/package/link paths

Use the arm's absolute executable. R denotes its argument vector:

    C/bin/racket -X C/collects -G C/etc -A P/addon -U -R K

1. Read-only config: R -c -I racket/base -t H/config-inventory.rkt
2. Class-first: R -l setup -- --boot H/core-first.rkt K
3. Independent core receipt: R -c -I racket/base -t H/rebuilt-receipts.rkt -- core
4. Full installed setup uses the exact selector-free reviewed flags. Compile all
   13 Q/native Racket modules and 10 Q/vendor/host Racket modules, then every
   H/*.rkt helper independently in this arm. The two .rktd fixtures are data.
5. Full receipts: R -t H/rebuilt-receipts.rkt -- full. The Python supervisor
   validates the complete record, persists its exact bytes as
   W/prebuild-receipts.json, and records their SHA-256.
6. Audited target: R -t H/audit-loads.rkt -t TARGET -- ORIGINAL_ARGUMENTS, with
   OBJECT_HASH_PREBUILD_RECEIPT_SHA256 set to the validated raw-file SHA-256.

The last command leaves target arguments unchanged. With the pinned CS startup
parser, -t schedules requires in command order and -- ends executable option
parsing. Both requires run in one outer continuation prompt without a parameter
reset between them. Audit handlers set during the first require therefore remain
installed for the next require and are inherited by newly created threads.

The CI-only OBJECT_HASH_PREBUILD_RECEIPT_SHA256 handoff is recorded in each
command environment. It does not add an OPENRACKET_ variable; the frozen
bootstrap's five-name OPENRACKET_ allowlist remains unchanged. Stock leaves the
object-hash flag unset; diagnostic build receipts require exact 0. Frozen test
and host activation rules remain authoritative.

## Config inventory

config-inventory.rkt emits one object-hash-config/v1 JSON record. All effective
public setup/dirs source, library, metadata and write destinations are explicit
rows in paths. Rows contain label, role, raw_path, canonical path, exists, file and directory.
The supervisor checks raw_path components for forbidden internal symlinks before
using the canonical path; legitimate clone-local ../lib references are accepted
without hiding a symlink or a true escape. Both
ordinary and root/static-root link forms are enumerated read-only; effective
hash-table link forms and the #f collection-list splice are represented too.
Raw config/link values are losslessly typed JSON (symbols, bytes, hashes, pairs,
paths and regexps), not opaque printed structures. Public accessors supply the
effective paths; raw tables are additional evidence, not a replacement.

Unknown configuration keys make accepted false and exit nonzero. Relative
configured compiled roots other than same are rejected rather than interpreted
as ordinary collects-relative paths. They require a separately reviewed
source-directory expansion before they can be accepted. Package database and
configuration file locations are explicit; package source directories are
validated through effective registration links and recursive source receipts.
Info-domain cache locations incorporate the effective info-domain-root reroot.
The supervisor must validate every concrete path before allowing a build.

The helper installs a read-only security guard. It does not compile, repair,
relink, unregister, create directories or change configuration.

## Rebuilt receipts

receipt-lib.rkt uses public compiler/compilation-path, setup/collects and
syntax/modresolve APIs. It parses the exact pinned 9.3 .dep data format without
requiring compiler/private/dep. Both indirect and external dependency wrappers
are retained. Unknown encodings, missing source, stale source SHA-1, missing
.zo/.dep, source newer than .zo, ambiguous products or files outside C/Q/H and K
fail. Every ordinary dependency is recursively checked; external file inputs are
hashed without incorrectly requiring them to be modules.

Compiled-module import and submodule reflection is read-only. It closes static
imports and identifies predefined VM modules with module-predefined?, separately
from filesystem sources. Static reflection does not instantiate modules. Older define-runtime-module-path-index
and runtime-require registrations are handled with the public runtime-paths
macro using the pinned compiler/embed expansion-time visitation pattern in a
separate namespace. The target is not instantiated at runtime; its compile-time
portions are visited under a read-only security guard. Tagged module registrations
are recursively receipted. Ordinary runtime file/resource paths remain data even
when their filename ends in .rkt. Modern define-runtime-module-path expands to a
for-label require and is also present in compiled-import/.dep closure.
All file records carry absolute path, size and SHA-256; source SHA-1 is checked
against the actual .dep header. The source freeze's runtime SHA-256 pins are
checked, with the exact pristine class pin in stock.

Full mode includes the required runtime roots, all native/stock-host/helper
modules, both legacy tools and drracket-tools registration forms, language
module/reader providers, indirect language metadata providers and recorded
compile omissions/virtual-source metadata. Legacy tool lists are resolved using
the same tail-components-then-first-file convention as the official loader.
Missing required modules cannot be excused by omission metadata.

The exact expanding-place/start worker root and its module-language and
module-language-tools seams are source-pinned and recursively receipted.

## Honest coverage boundary

registered_and_static_closure_complete means the enumerated registration and
static/.dep closure passed. It does not mean every arbitrary dynamic load has
been discovered. The records deliberately retain:

- arbitrary_dynamic_graph_proven: false
- child_place_dynamic_audit_complete: false
- live_registry_observed: false
- online_handler_registry_complete: false
- ordered_online_handler_registry_complete: false

The accepted scope is the known installed/static/runtime-module-path graph plus
host-place coverage, for an eligibility-only diagnostic. The unobserved actual
ordered online-expansion-handler registry is an explicit limitation; it does not
make this a benchmark-ready or universally traced application. In the pinned official
DrRacket source, module-language.rkt:2507 creates expanding-place/start, and
:2511–2514 sends ordered (module-path export-id monitor?) entries. The getter and
registry live lexically inside module-language-tools@ (:815–822), whose module
exports only that unit. The getter is exposed to linked units through the
internal drracket:module-language-tools/int^ signature, not as a module export.
A read-only invocation of the public module APIs cannot retrieve that live unit
instance. No fabricated registry, new tool registration, unit re-instantiation,
private-binding mutation or additional runtime source patch is supplied here.

The bounded preload guard verifies the immutable per-arm prebuild receipt's raw
SHA-256, schema, full mode, exact C/Q/H/K roots and exact false coverage flags
before installation. It uses
immutable module/product maps, verifies source/.zo/.dep bytes on each first
actual host-place module resolution, and verifies selected bytecode SHA-256 on
every module load. Unknown file-backed modules fail closed. It does not expand,
visit or recursively traverse the graph; the standalone full receipt performs
that work once per arm. The guard rejects source fallback and emits serialized
OBJECT_HASH_LOAD_AUDIT JSON records with nominal path, verified source/.zo/.dep
path/size/SHA-256 facts and the prebuild receipt SHA-256 reference. Repeated graph
edges and reasons remain losslessly available in that one full receipt. It distinguishes predefined VM modules from observed
reflective declarations. Audit rejection logs an explicit rejected event and
uses the captured exit handler with status 96 so a plugin cannot turn it into a
nonfatal warning. The supervisor must reject that event even if later output
otherwise appears successful.

The process environment is checked once before guard installation. Effective
compiled/collection/link parameters, main config/collects directories and the
effective clone executable identity are checked on every load. This distinction
preserves setup/getinfo's documented pruned-environment scope when evaluating
complex metadata; it does not permit changing loader roots. The pinned source
is setup/getinfo.rkt's filter-environment-variables and its surrounding
current-environment-variables parameterization in API-PROVENANCE.json.

This audit is scoped to the initial place and threads inheriting its parameters.
New Racket places and deliberately replaced handler parameterizations are not
claimed to be intercepted. It is not a security boundary or a universal
whole-application trace. The known worker root and dependency receipts are
separate evidence. The receipt handoff assumes non-hostile concurrent execution;
path/hash checks are not an atomic filesystem snapshot. Python retains the
source/config/product witnesses before and after execution and verifies receipt
transport bytes. Native integration must retain this precise scope.

## Provenance and portable verification

API-PROVENANCE.json contains exact official source evidence, immutable commit
URLs, Git blob SHA-1, SHA-256 and byte lengths. Racket is pinned to
bbf7dea831df95922db23aaa51e13eed17dcf881; DrRacket v9.3 resolves to
1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6. Hash verification is not a signature claim.
The imported private implementation files are evidence only; helper imports use
public APIs.

    PYTHONDONTWRITEBYTECODE=1 python3 test_helpers.py

Run normally and with TMPDIR pointing through a symlink. No files whose names
differ only by case are created by the tests. Portable success cannot establish
that Racket reads/expands these sources or that the native loader/GUI succeeds.

## SHA-256 predicate and regexp dialect

The receipt hash predicate requires a string length of exactly 64 and matches
the ordinary-regexp pattern ^[0-9a-f]+$. It does not use brace repetition in a
#rx literal: Racket's ordinary regexp dialect treats braces as literal characters.
The pinned official regexps.scrbl and rx.rkt grammar sources are retained in
API-PROVENANCE.json; the corresponding manual is
https://docs.racket-lang.org/reference/regexp.html#%28part._regexp-syntax%29.

The existing guard initialization includes native predicate self-checks for a
valid 64-character lowercase hexadecimal value, literal braces, short, long,
nonhexadecimal, uppercase and nonstring inputs. These run before receipt
acceptance with no extra process or phase. They remain native-unrun here. A
portable source contract checks the placement and cases, and a separate portable
model checks their expected outcomes. Every new Racket regexp literal was scanned
and is covered by a reviewed common-syntax allowlist.
