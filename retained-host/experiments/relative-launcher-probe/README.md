# OpenRacket bundle-relative native path probe

Source-only hypothesis, prepared 2026-10-11. This is a separate test tree. The
accepted tethered app, builder, retained DrRacket source and user profiles are
unchanged. No Racket reader/compiler, runtime, launcher, application, installer,
package manager, archive, CI job or upload has been executed for this probe.

The product-facing implementation is a 31-line Racket native-skeleton generator,
a process-preserving shell entry, and small Racket witnesses. `supervise.py` is a
test-only assembler/validator, not a new product builder or distribution runtime.
It includes conservative Mach-O parsing, input witnesses and refusal gates.

## Deliberately narrow question

Can the official Racket 9.3 CS native launcher retain the outer app's actual
Mach-O/Cocoa identity while all measured Racket/configuration/collection/package
and non-system loaded-library paths stay in a renamed/relocated complete-runtime
bundle or an explicit disposable test profile?

This does not integrate DrRacket, appearance, product state, package installation,
user programs, restarts, places, file events, or the final writable user profile.
The probe resolves DrRacket's module file but does not instantiate DrRacket.

## Proposed mechanism

1. Invoke official `create-embedding-executable` with `#:gracket? #t`,
   `#:launcher? #t`, `#:variant 'cs`, no embedded modules, and:
   - `relative? #t`
   - `forget-exe? #t`
   - `framework-root "@executable_path/../Resources/runtime/lib/"`
   - `config-dir "../Resources/runtime/etc"`
   - `#:collects-path null`
2. Generate the empty app first. The upstream generator deletes its destination.
   Only then copy the complete separately verified full runtime under
   `Contents/Resources/runtime`, preserving its files, links, modes and times.
3. Keep the generated native bytes, rename its file to `ProbeNative`, and set the
   outer plist's declared executable to `ProbeBootstrap`. Remove declaration keys
   only from the freshly generated outer skeleton; leave nested metadata intact.
4. Bootstrap computes the present bundle location, clears inherited environment
   with `env -i`, then `exec`s the native image with absolute `-E`, `-X`, `-G`,
   `-A`, `-U` and `-R` before importing the probe.
5. `-E` deliberately names the bundled console `bin/racket`. `exec-file` and
   subprocess semantics are therefore different observations from actual process
   image/`run-file`/NSBundle/NSRunningApplication identity. The report retains all.

Empty built-in collections disable collection links by documented contract.
Whether later nonempty `-X` restores them is an explicit experimental question.
`boot.rkt` saves core-only startup evidence and refuses disabled links before any
package/GUI import. A failure is a useful negative result; do not silently change
this option or claim it passed. See `API-EVIDENCE.md`.

The official generator intrinsically adds its own ad-hoc signature. This tree
does not manually sign, remove signatures, clear quarantine, change Gatekeeper,
register applications, or set default handlers. Intrinsic generator behavior
and outer-plist edits are not notarization or a downloaded-app security result.

## Files

- `make-launcher.rkt`: official native skeleton only
- `bootstrap.sh`: private test entry, no profile initialization
- `probe/boot.rkt`, `paths.rkt`, `gui.rkt`, `child.rkt`, `dyld.rkt`: raw witnesses
- `probe/cocoa-identity.rkt`, `default-handler.rkt`: byte-identical accepted
  read-only observers, with source hashes in `evidence/SOURCE-PINS.json`
- `native-read-compile.rkt`: separate future Racket reader/compile gate
- `supervise.py`: test-only copy/relocation/refusal/validation supervisor
- `tests/test_source.py`: portable synthetic and source-contract tests
- `NATIVE-ACCEPTANCE.md`, `NATIVE-OUTPUT.schema.json`: future native contract
- `evidence/`: exact input pins and current portable-only validation

## Safe portable command

From this tree:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

These tests read source, create only disposable Python fixtures, and never launch
Racket. Racket delimiter checks are lexical, not a reader or compiler result.
No workflow is supplied or triggered. Commands for separately authorized native
work are in `NATIVE-ACCEPTANCE.md`; their existence does not authorize execution.

## Hard native preconditions and unknowns

- A genuinely official full macOS Apple Silicon Racket 9.3 CS runtime must be
  independently sourced and verified. File layout, a version string and the
  supervisor's inventory digest prove neither official origin nor completeness.
- Audit **every** Info.plist, including aliases/mixed-case nested bundles. Any
  document or imported/exported UTI declaration key blocks **all** app launches,
  including direct execution. A typical full distribution is expected to hit
  this gate. Review a specific disposable-copy metadata/exclusion plan separately;
  do not strip nested declarations automatically or touch the original runtime.
- Observe the current account's .rkt default handler before generation and before
  and after each later app launch. Never force an unset state, reset defaults, or
  create accounts. Initially-unset coverage is conditional on a safely available
  state and must otherwise remain pending.
- Native parsing/compilation, `-X` precedence, Cocoa identity, FFI symbols and real
  dynamic library closure have not been tested. The dynamic-library validator is
  intentionally conservative about inherited intermediate-loader rpaths.
- `-U` excludes user packages for this no-user-packages test. It is not evidence
  that the eventual writable addon/package design works. An empty `-R` test root
  excludes shipped compiled roots and may make startup slow; the 120-second
  process bound is a test limit, not a performance claim.
- Absence of the single recorded original-installation path does not prove a
  clean Mac. `clean_destination_tested` stays false; the summary records only that
  path's presence/absence. Even a later independently established clean path probe
  is not full distribution acceptance, optional-library closure, read-only-app
  operation, licensing review, Gatekeeper acceptance, signing or notarization.
- Full runtime/framework extended attributes/resource forks are outside Python
  `copytree`'s guaranteed byte/mode/time/link witness; actual release copying must
  settle those semantics. No binary handoff/release route is established here.
