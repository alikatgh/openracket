# Source/API evidence and native compilation boundary

Reviewed 2026-10-11. This is source evidence, not executed native acceptance.

## Unmodified retained DrRacket API

Public documentation: https://docs.racket-lang.org/tools/drracket_unit.html

The reviewed original Racket 9.3 `drracket/private/unit.rkt` has SHA-256
`535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5`.
The observer verifies that exact file at runtime. Reviewed source points:

- lines 1268–1270: public final tab `get-frame`, `get-defs`, `get-ints` readers.
- line 3117: public frame `get-current-tab` reader.
- line 5007: public final frame `get-tabs`, returning the original tab list.
- frame definitions/canvas getters are the same preserved original APIs used by
  the proven portable observer. Enumeration never selects a tab or opens a file.

The package retains the previous exact colorer, original unit, memory preference
registration and guarded text-misc pins, and also pins original autosave.rkt.
Memory functions `memory-limit-evidence` and `assert-memory-limit!` are copied
byte-identically. Expected values come only from the independent CI contract.

## Objective-C bindings

Racket's `ffi/unsafe/objc` `import-class`, `tell`, `_id`, `_BOOL`, `_SEL` and the
UTF8String conversion pattern mirror the already-reviewed 0520
`tool/native-appearance-cocoa.rkt`. The actual FFI reader is isolated in
`cocoa-identity.rkt` and must compile on the target Mac before registration.

Official Apple API sources:

- https://developer.apple.com/documentation/appkit/nsrunningapplication/current?language=objc
- https://developer.apple.com/documentation/appkit/nsrunningapplication?language=objc
- https://developer.apple.com/documentation/appkit/nsrunningapplication/processidentifier?language=objc
- https://developer.apple.com/documentation/appkit/nsrunningapplication/bundleurl?language=objc
- https://developer.apple.com/documentation/appkit/nsrunningapplication/executableurl?language=objc
- https://developer.apple.com/documentation/foundation/bundle?language=objc

The helper reads the already-running application's `currentApplication`,
`processIdentifier` (`pid_t`, bound as Darwin 32-bit `_int`), `bundleIdentifier`,
`bundleURL`, `executableURL`, and `NSBundle.mainBundle` identity/path/declared
executable metadata. Nil values remain false and fail the corresponding identity
assertion. No application object is created, registered, activated or delegated.

Apple warns that PID alone is insufficient to compare NSRunningApplication
instances; the helper also calls `isEqual:` against its original native instance.
One retain keeps that object alive across autorelease pools for this bounded
process lifetime; process exit reclaims it. UTF-8 strings are copied while native
objects remain alive. Selectors are checked before use and calls occur only on the
existing Cocoa main GUI handler thread. This is not a handler replacement.

NSBundle executable metadata describes the declared entry, potentially the shell
bootstrap. NSRunningApplication executable metadata is retained as its own raw
observation. Neither is substituted for independent process-image evidence.

## dyld and libc process evidence

Apple's archived macOS man page provides the native signature and behavior:
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dyld.3.html

`_NSGetExecutablePath(char *buf, uint32_t *bufsize)` returns int success/failure
and required size. The helper binds `_bytes`, `_pointer` and `_int`, with a
GC-managed `_uint32` size cell. It tries 4096 bytes, permits one bounded growth to
at most 1 MiB, checks return status/NUL termination and decodes UTF-8 strictly.
The result may include symlinks, so assertions canonicalize existing paths with normalize-path and reconstructed
components, including symlink aliases and trailing directory syntax. A GUI-free
contract covers a controlled alias and the macOS /var to /private/var alias.
The raw result remains in the report. Libc `getpid(void)` supplies independent
actual PID, never an environment/config value. CI must also collect OS process
and native executable/hash evidence; in-process checks alone cannot rule out
other children outside the process.

## Launch Services default handler witness

Official Apple sources:

- https://developer.apple.com/documentation/coreservices/1448939-uttypecreatepreferredidentifierf
- https://developer.apple.com/documentation/coreservices/1449868-lscopydefaultrolehandlerforconte?language=objc
- https://developer.apple.com/documentation/coreservices/lsrolesmask/klsrolesall
- https://developer.apple.com/library/archive/documentation/CoreFoundation/Conceptual/CFDesignConcepts/Articles/tollFreeBridgedTypes.html
- https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/understanding_utis/understand_utis.tasks/understand_utis_tasks.html

The separate CLI binds the documented Create UTI query taking three CFStringRef
arguments and the Copy default-handler query taking CFStringRef/UInt32. Objective-C
`NSString` is toll-free bridged with `CFStringRef`; UTF8String creates a Racket
string copy. The borrowed exported `kUTTagClassFilenameExtension` is never released.
Both Create/Copy results are owned and each non-null result gets a balanced
`CFRelease` under `dynamic-wind`, including exceptional paths. `kLSRolesAll` is
UInt32 0xffffffff. An absent default handler is explicit JSON null; missing symbols
or a failed UTI query raise a distinct error and nonzero CLI exit.

These Launch Services/UTI functions are deprecated. This source-backed bounded CI
witness still requires actual symbol resolution on the selected macOS 15 runner.
It performs no LSRegister/LSSetDefault calls, no NSApplication startup and no file
opening. It is not a product dependency. When multiple UTIs match one extension,
preferred UTI derivation can be ambiguous; compare the observed UTI as well as the
handler and retain that limitation.

## Validation boundary

Portable tests verify source contracts and lexical delimiter balance only.
`tests/contract-test.rkt` exercises the actual independent contract module.
`tests/observer-state-test.rkt` reads/evaluates actual state functions with fake
clock/window results, not a reconstructed runtime or fake application entrypoint.
The corrected suite has 32 cases (21 contracts and 11 state cases); these and all native modules still need Racket 9.3 compilation/execution.
No source-review assertion can replace the real Launch Services event sequence.


## Stock initial-language toolbar behavior (2026-10-11 correction)

The source package metadata identifies official `racket/drracket` commit
`1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6`, built for 9.3. See
DIAGNOSIS-38125605788.md for exact paths, hashes and source line references.
The existing public tool signature exports the language settings accessor,
`drracket:language:capability-registered?`, and
`drracket:module-language:module-language<%>` used by the repair. Verified in
`drracket-plugin-lib/drracket/private/drsig.rkt` lines 110–115, 342–377,
and 448–468. No private member names, preference setter, tool callback, language
selection, or extra native operation is introduced.
