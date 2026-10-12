# Source-only shared-cache witness repair

## Exact failed run and cause

The input is the 29-file `openracket-relative-launcher-case-fixture-freeze-20261011-1830`
with MANIFEST SHA-256 `25af97fe2273422c77135e999d6887c59c35a1b0c51308b6ea435b09ccb057a1`
and supervisor SHA-256 `366783356095b8badd9ac1deb49c532e4cf1a2125b01b29307896f0f37ea94d0`.
Every input manifest entry and all 55 decoded raw evidence files from native run
38164494081 were byte/hash verified before preparing this separate derivative.

That run passed construction, retained-runtime and declaration/static-loader
preconditions. Its first native launch produced raw startup/result/child evidence:
967 GUI image names and 305 console-child image names, without duplicate names.
The raw GUI list includes
`/System/Library/Frameworks/WebKit.framework/Versions/A/WebKit`.
It does not substitute the Cryptex path for that raw name.

The previous supervisor's `is_system_path` resolves aliases with `strict=False`.
On that Mac the WebKit name resolves outside its two system roots, to
`/System/Volumes/Preboot/Cryptexes/OS/System/Library/Frameworks/WebKit.framework/Versions/A/WebKit`.
The subsequent `existing(image)` uses `strict=True` and raises because the
standalone dylib file is absent. The original raw evidence contains no native
cache-membership/header witness, so the suspected cache-backed image cannot be
proved retrospectively. The original run remains failed, with its second
relocation launch correctly withheld. Cleanup was certain, the bundle was
unchanged, and the observed `.rkt` handler remained null before/after.

## Official source contract

- Apple public `mach-o/dyld.h`, pinned at dyld commit
  `fd8d0c4d52320ebf64db34f3cb280310d905c5ae`, declares
  `_dyld_get_image_header`, `_dyld_get_image_name`, and `_dyld_image_count`.
  It warns that enumeration is not thread-safe. The same public header provides
  `_dyld_shared_cache_contains_path` from macOS 11.0, expressly for identifying
  cache-incorporated dylibs that have no standalone filesystem entry.
  [Header](https://github.com/apple-oss-distributions/dyld/blob/fd8d0c4d52320ebf64db34f3cb280310d905c5ae/include/mach-o/dyld.h#L47-L122)
- Apple's dyld implementation calls `canonicalDylibPathInCache` for that query.
  The process configuration first queries the cache's name map and only then
  attempts filesystem realpath fallback. This supports using the original
  dyld name directly without manufacturing a resolved file.
  [API](https://github.com/apple-oss-distributions/dyld/blob/fd8d0c4d52320ebf64db34f3cb280310d905c5ae/dyld/DyldAPIs.cpp#L3303-L3310),
  [lookup](https://github.com/apple-oss-distributions/dyld/blob/fd8d0c4d52320ebf64db34f3cb280310d905c5ae/dyld/DyldProcessConfig.cpp#L2798-L2810)
- Apple public `mach-o/loader.h`, pinned at xnu commit
  `f6217f891ac0bb64f3d375211650a4c1ff8ca1ea`, specifies the fixed 64-bit Mach-O
  header layout. Its `MH_DYLIB_IN_CACHE` bit (`0x80000000`) distinguishes a loaded
  cache dylib from an ordinary filesystem dylib. A name query alone does not
  establish that a loaded instance was not an on-disk override; this derivative
  also reads the flag on the exact same enumerated image's in-memory header.
  [Header layout](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/EXTERNAL_HEADERS/mach-o/loader.h#L72-L85),
  [flag](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/EXTERNAL_HEADERS/mach-o/loader.h#L225-L228)
- Racket 9.3 exports `ptr-ref`, `ptr-equal?`, `cast`, `_uint32`, `_uintptr`, and
  `_stdbool` from `ffi/unsafe`. The latter is specifically the C99 `bool` ABI;
  `_bool` instead uses C `int`. Raw fixed-header words are read at indexes
  0 (magic), 1 (CPU type), 3 (file type), and 6 (flags), matching Apple's layout.
  [Exports/types](https://github.com/racket/racket/blob/v9.3/racket/collects/ffi/unsafe.rkt#L10-L24),
  [Boolean ABI](https://github.com/racket/racket/blob/v9.3/pkgs/racket-doc/scribblings/foreign/types.scrbl#L265-L280)

Fetched source texts/excerpts and file blob SHAs are retained in `evidence/`.
Only official individual source files were retrieved read-only through the
connected GitHub tool. No dependency, package, installer, archive, private dyld
API, shell network request, or native runtime was installed or invoked.

## Narrow acceptance change

Raw `loaded_images` strings are preserved. GUI and child each add a
`loaded_image_snapshot` with exact native index, raw name, non-null header
address, fixed-header fields, and an exact Boolean cache query result for every
image. Counts, names, and header addresses are checked before and after gathering
records. The native observer fails on unavailable symbols or visible changes;
the supervisor rejects missing, malformed, duplicate, mismatched or unstable
witnesses. The report/schema version stays 1 with a newly required witness;
old reports fail closed rather than being silently upgraded.

An image gets `os-shared-cache` classification only if all hold:

1. The same indexed in-memory header has 64-bit Mach-O magic, arm64 CPU type,
   dylib file type, and the cache flag.
2. The public dyld cache-path query for that exact raw name is true.
3. The raw path is already normalized under `/System/Library/` or `/usr/lib/`,
   with no traversal, embedded NUL, redundant separators, or alias spelling
   supplied by the supervisor. Prefix lookalikes and Cryptex-only names fail.

A proved cache image is not resolved or assigned a fake existing path/hash.
Every other loaded image must be a real file canonically within the test bundle
or existing system roots. A cache-path query without the loaded-header flag is
insufficient to waive filesystem checks. App/runtime or arbitrary external
paths cannot become OS-cache images, even with forged affirmative fields.
The active closure uses these same validated classifications; bundle images
still require actual files and matching Mach-O inventory/dependency evidence.
The prelaunch declaration/static-loader gates and all cleanup/relocation guards
are unchanged. There is no new filesystem root, configurable exemption,
security-setting change, or executable/bootstrap/identity alteration.

## Evidence boundary and next gate

Portable tests are synthetic. They cover the exact failing alias behavior,
a genuine dangling symlink, correct and malformed paired witnesses, missing
app/runtime dependencies, external symlink escapes, retained case-collision
checks, and normal/genuinely symlinked TMPDIR execution. They do not execute
Racket or prove the API/ABI works on the target Mac.

The public enumeration API does not provide an atomic snapshot lock. Repeated
count/name/header checks detect visible drift, but cannot mathematically exclude
an undetectable remove/re-add between checks. The bounded probe performs no
intentional concurrent loading/unloading. This is not hostile-process attestation.
Native reader/compile, FFI observation and both relocation locations remain
pending a separately authorized run; any new disagreement must fail closed.
Full distribution/clean-Mac/signing/notarization acceptance remains false.
