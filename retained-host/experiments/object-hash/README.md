# Actual editor object-hash eligibility diagnostic

SOURCE ONLY. Default off. Native parsing, compilation, semantic tests, real GUI
execution, allocation observations and editor eligibility are **unrun**. No
optimization is implemented, no speed/byte/RSS claim is made, and no delivered
preview, runtime installation, package, remote branch or CI job was changed.
The active WXME repair remains the higher priority.

## What this can establish

The exact default `object-hash-code` still executes its original body, including
its existing vector allocation, sentinel scan, recursive callback and identity
fallback. An observed plain argument with actual `struct-info` `skipped?` true,
and a completed original helper fallback, would witness the prerequisite from
`vendor/REVIEW.md`. The inspector is the call's current inspector; it is neither
replaced nor retained. The physical type returned by `struct-info` is discarded.

Two actual editor references and the actual GUI handler are registered weakly,
on that handler. Matching is `eq?`, with no unwrap, identity-hash approximation,
substitute editor, or synthetic hashing in the real host. Only default-hash calls
on that handler count. Public editor wrappers may differ from the hash argument;
other threads are outside this deliberately narrow scope. **No matching calls is
unresolved**, even if the total-attempt cap was reached. A bounded sample with no
eligible call does not establish global ineligibility or justify widening a guard.

For definitions and interactions separately, categories are:

- impersonator: no added `struct-info` call at all
- skipped: plain object; most-specific physical type skipped under this inspector
- not-skipped: plain object; this does not prove every ancestor is visible
- inspection-failed: added classification failed; no eligibility inference

Each category has scalar match count, original converted-vector count, sum and
maximum of original vector lengths, completed helper-return count, and original
helper-fallback count. Visible completed helper results are returns minus
fallbacks. Original vector length includes type/sentinel slots; it is neither
physical editor field count nor allocated bytes. No observed vector, field value,
object, inspector, trace, or caught exception is retained. No second conversion
or scan, `current-memory-use`, collection, or timing read is introduced.

The fixed whole-process caps are 20,000 registered-handler default-hash entries
and 128 matches; the earlier cap closes registration and clears weak references.
The final already-claimed call may complete scalar accounting after closure.
One registration is allowed per process. Snapshot reports exact caps/reason.
Claimed matches, completed conversions and helper returns are distinct. Faults,
abort, or incomplete observations are not actionable. `exn:break` propagates;
ordinary diagnostic faults stop observation without replacing the original body.
Original conversion/callback exceptions are never caught by core instrumentation.

## Stable private API

Only the disposable `racket/private/class-internal` module gains these exports:

- `openracket-object-hash-probe-enabled?`: exact environment value `1` enables;
  unset or `0` is off. The host requires explicit `0`/`1` and rejects other flags.
- `openracket-object-hash-probe-build-id`: content-derived diagnostic source ID.
- `openracket-object-hash-probe-instance`: unique module-instance token.
- `openracket-object-hash-probe-arm! definitions interactions handler`: once,
  enabled only, called on the supplied actual handler.
- `openracket-object-hash-probe-stop! [reason]`: disarm and clear weak references.
- `openracket-object-hash-probe-state`: bounded flat scalar snapshot.

No public `racket/class` API or custom equality/hash dispatch changes. Source
reconstruction proves the entire remainder of the original class module is
unchanged. `scripts/generate.py` puts the original body verbatim under one lexical
helper binding; the observed helper is mechanically derived from the original
helper with one vector-length notification. Reversal restores every original byte.

## Actual host seam and provenance

The accepted sources were read from
`openracket-named-style-experiment-freeze-20261011-1716/controls`. Original host
SHA256 is `5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448`;
original workflow SHA256 is
`b175a92754e8f0e8a0f524ae5947f5eae8da605b0f3274bbc098e20ce1de53bf`.
`vendor/host` keeps their complete Racket dependency closure with original layout.
The restored publication45 native tool/observer sources were also inspected;
their existing genuine frame/handler/editor getters confirm this seam. No tool
registration, native tool dispatch, app observer, or production tool is modified.

`generate_host.py` has only two exact source derivatives. The existing host calls
a narrow abort-preserving wrapper. The existing small Check Syntax workflow
registers immediately after “Check Syntax enabled”, before its real button
command, then stops immediately after the lexical-binding completion await,
before graph copy/hashing. All original source/graph/selection/error assertions,
Run-before-Check-Syntax behavior, repeated real Run checks, READY/capture handshake
and cleanup remain in place. This adds no after-Check-Syntax Run recovery claim.
All other copied dependencies are unchanged and hash-pinned.

`native/bootstrap.rkt` verifies the chosen executable, module paths, exact source
hashes, clean experiment flags, phase-zero core exports, build marker and actual
activation. It imports the adapter and requires `eq?` agreement on the actual
loaded core token before registration. Its raw source record and the observation
must agree on token/flag. This is source/activation/instance proof, not proof that
old bytecode is safe. The next section is mandatory.

Exact original core SHA256:
`1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f`.
Exact review SHA256:
`430bbd3c3f2b4b0cc8867fa8d69cfbc2b9572e7b0e3a6db4983365abcd2a2e16`.
`SOURCE-PINS.json` and `RUNTIME-PINS.json` identify the resulting package and
actual runtime source seams. The original bytes also have a session backup.

## Mandatory future native preparation (not authorized or executed here)

1. Obtain separate review/permission for native execution. Use the existing free,
   disposable full official Racket 9.3 facility and accepted native outer harness.
   Do not use a delivered app, prior experiment clone, paid facility, or a user
   installation. Preserve full original-installation before/after witnesses.
2. Make independent full deep-copy stock and diagnostic runtime roots. Resolve
   their physical paths; ensure no overlap, symlink escape or shared writable
   artifacts. Keep package registrations/configuration within each root and use
   disjoint fresh user/addon/XDG profiles. Do not modify source installation links.
3. Use `overlay.py stage` against the exact pristine source tree. It creates only
   a new source overlay plus original bytes and a strict manifest; it does not
   install or execute anything. Verify the manifest before a separately authorized
   copy of its single candidate file into the disposable diagnostic clone. The
   stock clone stays byte-for-byte unchanged. Reversal must reproduce the pin.
4. Recompile **both core and the complete actual GUI/DrRacket dependency graph**
   against each selected clone, before native testing. Reusing the original `.zo`
   or compiling only the patched file is forbidden. Inventory and isolate/remove
   old compiled products in disposable clones only, including package/addon caches;
   ensure package links cannot resolve a writable/shared external cache. First
   rebuild the changed actual `racket/private/class-internal.rkt` and its core
   dependency chain, then a full installation setup/compile pass for installed
   GUI/framework/DrRacket/tools dependencies, then every package `native/**/*.rkt`
   file and its `.rktd` runtime inputs. Confirm the selected runtime's supported
   setup flags before forming that command; no guessed setup command is supplied.
   Keep compiler command lines, exit codes, exact source/cache/root inventories,
   rebuilt dependency paths and full logs. Required modules include `racket/class`,
   racket/snip/private/style and prefs, GUI editor classes, framework text/color,
   DrRacket unit/tool/syncheck GUI/xref/traversals/online-comp, interval-map,
   switchable-button and retained OpenRacket host/tool modules. Stop if complete
   rebuild/isolation or actual source identity cannot be proved.
5. Execute each native actual-form scenario in a separate fresh process. Off mode
   must have flag `0`; every other scenario has `1`. RackUnit failures are fatal.
   The checked list is in `native/SCENARIOS.json`. These are synthetic semantics
   fixtures using the installed core private forms and exact original reference;
   they are not real-editor eligibility evidence. Observer-break uses an exact
   source-derived observer handler with one test-only injected raise, not a new
   production fault hook. Native parsing/API/namespace mutation assumptions remain
   unverified until this step runs successfully.
6. Run pristine stock, diagnostic-off and diagnostic-on genuine small Check Syntax
   processes independently. The two diagnostic command shapes are:

   `CLONE/bin/racket native/bootstrap.rkt off CLONE`

   `CLONE/bin/racket native/bootstrap.rkt on CLONE`

   These are not permission or a standalone runner. The outer accepted harness
   still supplies exact environment, distinct profiles, 60-second process bound,
   native screen capture/ACK, raw streams, exit acceptance and original-installation
   preservation. Retain source proof before observation before completed host result.
   This package adds no new native launcher or CI workflow. Do not run it by simply
   changing the existing named-style runner's experiment flag or reusing its `.zo`.
7. `compare_observation.py RAW_LOG` checks exact source/instance/activation, scalar
   accounting, caps, completed original host/workflow and exact eight-edge graph,
   including zero spans. It preserves raw bytes. This assessment does not replace
   the outer process/screenshot gate or dependency-recompile evidence. A failed
   off control, native semantics test, source proof, diagnostic fault, or incomplete
   run blocks interpretation. Even a valid witness does not establish speed.

## Safe portable checks

From this tree, with no Racket installation:

```
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_host.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_native_forms.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/pins.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_probe.py -v
```

Portable tests verify transformation/reversal, unchanged custom dispatch, scalar
shape/accounting, exact source and instance evidence, host window, weak registry,
symlink/overlap/path refusals, source/manifest tampering and raw-byte preservation.
Lexical bracket checks are explicitly not native parsing or expansion. Run the
whole suite normally and with TMPDIR set to an explicitly symlinked directory;
canonical ancestor aliases are supported, internal leaf/escape links refused.
