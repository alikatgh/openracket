# Exact API and path evidence

All Racket references below use commit
`bbf7dea831df95922db23aaa51e13eed17dcf881` (official 9.3 source). The adjacent
`evidence/SOURCE-PINS.json` preserves all 34 source-file SHA-256/Git-blob pins
from the reviewed vendor manifest, plus the reused accepted observer pins.

## Official native generator

- [Public executable API, 229–337](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/raco/exe-api.scrbl#L229-L337): explicit config/framework roots, `forget-exe?`, `relative?`, collections and launcher semantics.
- [macOS launcher dispatch, 741–758](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/launcher/launcher.rkt#L741-L758): the non-script GRacket launcher uses the same official embedding generator. Calling its documented public API directly supplies the explicit collections option that `make-gracket-launcher` does not expose.
- [Skeleton construction, 172–217](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L172-L217): output is removed/recreated, then native executable copied into Contents/MacOS. Payload assembly before this call would be destroyed.
- [Native behavior, 1548–1564](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L1548-L1564): `forget-exe?` disables retention of the build executable; relative GRacket collections are adjusted by the macOS helper.
- [Explicit framework prefix, 1612–1631](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L1612-L1631) and [prefix application, 24–44](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/private/macfw.rkt#L24-L44): a provided prefix is used literally and the Racket framework/version suffix appended. The chosen prefix resolves from Contents/MacOS directly to Resources/runtime/lib; there is no additional automatic ../../../ on this explicit framework prefix.
- [Config handling, 1661–1697](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L1661-L1697): an explicit config path is written directly. The generated relative fallback would become wrong when `-E` changes the effective executable anchor, so bootstrap always supplies absolute `-G` with `-E`.
- [Collects adjustment, 1981–1985](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L1981-L1985): nonempty relative `#:collects-path` is prepended with ../../../ for GRacket. Naively including the original .app filename would break rename portability.
- [Intrinsic signature, near 1976](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/compiler/embed.rkt#L1976): the generator itself calls its ad-hoc-signature helper. No separate signature/security tool is part of this probe.

## Startup and actual path observations

- [Empty collects contract, 324–328](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/raco/exe-api.scrbl#L324-L328) disables collection links. [Startup -X, 310–318](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/startup.scrbl#L310-L318) does not explicitly promise restoration after this embedded default. The staged sources omit the CS startup implementation needed to resolve precedence statically. The early witness tests it, and disabled links fail.
- [Startup overrides, 326–372](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/startup.scrbl#L326-L372): `-G`, `-A`, `-U`, `-R`, `-N`, and `-E` have distinct effects. No `-N` is supplied: actual `run-file` remains a separate observation.
- [Effective executable anchoring, 46–64](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/racket/private/config.rkt#L46-L64) establishes why absolute startup paths matter.
- [macOS find-dll-dir, 194–233](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/setup/dirs.rkt#L194-L233): this reader inspects the executable selected by `exec-file`, including its actual Racket framework reference. `-E` therefore deliberately makes it inspect bundled bin/racket. A false result is recorded, not replaced with a guessed framework path.
- [Configuration conversion, 23–52](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/setup/private/dirs.rkt#L23-L52): relative config paths use main collects as base; absolute values remain absolute. [Installation package relocation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/pkg/scribblings/implementation.scrbl#L73-L106) documents different collection-link path bases. This probe preserves all metadata and measures its resolved paths rather than rewriting configuration heuristically.

## Independent identity and dependency evidence

The reused `cocoa-identity.rkt` and `default-handler.rkt` are byte-identical to
the accepted publication-45 observer. Their existing API evidence is recorded
by path and SHA-256 in `evidence/SOURCE-PINS.json`; they are local accepted source,
not falsely labeled official upstream files.

- [Apple dyld APIs](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dyld.3.html): `_NSGetExecutablePath`, `_dyld_image_count`, `_dyld_get_image_name` are read-only process observations. The count is bounded; the snapshot assumes the probe is not concurrently loading/unloading libraries.
- [NSRunningApplication](https://developer.apple.com/documentation/appkit/nsrunningapplication?language=objc) and [NSBundle](https://developer.apple.com/documentation/foundation/bundle?language=objc): native process/bundle identity is read independently from startup path settings. A declared bootstrap executable is not substituted for actual dyld process-image evidence.
- [Mach-O loader definitions](https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/loader.h): the test-only parser recognizes 64-bit/fat32 headers, dependency commands and LC_RPATH; unknown 32-bit/fat64 forms refuse. Runtime Mach-O bytes remain separately inventoried. This primary reference is explanatory, not an immutable local source pin.

The Python validator independently resolves reported paths, checks file existence
and hashes, rejects symlink/prefix/parent escapes, and requires measured closure
for active non-system GUI and console-child images. It does not claim closure of
unloaded optional libraries, nested stock launchers, or processes not invoked.

## Explicit core-import/export check

`boot.rkt` requires `racket/path`; the exact 9.3 `racket/collects/racket/path.rkt`
exports `normalize-path` at lines 3–14. Its one-argument use is supported by
lines 57–63. This file and eight additional exact-commit core sources are
preserved in `evidence/ADDITIONAL-SOURCE-TEXTS.json`, with verified Git-blob and
SHA-256 pins in `ADDITIONAL-SOURCE-PINS.json`.

Every `setup/dirs` procedure used by `paths.rkt` was checked in exact source:

- `find-config-dir`: private/dirs.rkt:11–14
- `find-collects-dir`: private/dirs.rkt:138–143
- `find-doc-dir`, `get-doc-search-dirs`: private/dirs.rkt:241–247
- `find-lib-dir`: private/dirs.rkt:265–271
- `find-share-dir`: private/dirs.rkt:278–282
- `find-links-file`, `get-links-search-files`: private/dirs.rkt:335–348
- `find-pkgs-dir`, `get-pkgs-search-dirs`: private/dirs.rkt:358–365
- Those generated accessors are explicitly provided by the `define-finder`
  clauses at private/dirs.rkt:180–232 and re-exported by dirs.rkt:9–25.
- `find-console-bin-dir`, `find-gui-bin-dir`: dirs.rkt:34–48
- `find-dll-dir`, `get-lib-search-dirs`: dirs.rkt:26–29,251–262

`json/main.rkt`, `file/sha1.rkt`, `racket/path.rkt`, `racket/file.rkt`,
`racket/list.rkt`, `racket/promise.rkt`, `setup/cross-system.rkt`, and
compiler/private `{winutf16,mach-o}.rkt` were fetched at the exact commit and
confirmed under core collects. Their require forms include further core modules
such as racket/contract/base, syntax/readerr and setup/path-to-relative; this is
not a recursively complete import-closure execution proof. The minimal early
receipt now precedes json/setup/dirs loading, so a link-restoration failure is
diagnosable without those imports. Native reader/compile/startup gates remain.

## Source-only review corrections

Independent review found and corrected: unbounded in-memory child output (now
monitored capped files), report-trusted canonical paths (now independently
resolved), missing metadata hash rechecks, aliased/mixed-case bundle declarations,
raw system-prefix traversal, and relocation into source. The GUI observation now
runs directly on its handler thread or queues and waits on a non-handler thread.
These corrections and passing portable tests do not establish native validity.
