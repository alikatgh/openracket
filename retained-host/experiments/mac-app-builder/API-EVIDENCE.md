# Racket 9.3 builder API evidence

## Packaging-policy correction: no automatic document association

Reviewed 2026-10-11 against Apple's primary documentation:

- [Info.plist Core Foundation keys, CFBundleDocumentTypes and LSHandlerRank](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html#//apple_ref/doc/uid/TP40009249-SW1):
  the document-type array associates file types with an app. `Alternate` is a
  selectable rank below `Owner` and `Default`; it is not an opt-out. `None` is
  supported and prevents automatic selection while permitting drops. Do not
  confuse `LSHandlerRank=None` with `CFBundleTypeRole=None`.
- [LSOpenFromRefSpec](https://developer.apple.com/documentation/coreservices/1444466-lsopenfromrefspec?language=objc):
  a request that specifies both an application and files sends the documents to
  that application regardless of its advertised capabilities. The documentation
  distinguishes cold launch from activation of an existing process. This is a
  deprecated API's documented Launch Services behavior, not a native result for
  the current `/usr/bin/open` implementation or this Racket launcher.

For the bounded explicit-open preview, removing the whole document-type key is
the smaller policy surface: no extension, wildcard, role or UTI claim needs to
be advertised. `None` would be a valid alternative if native icon-drop support
were required, but still retains document association metadata. This candidate
does not replace claims with new imported/exported UTIs or a generic type claim.
It also removes inherited document-type dictionaries from the generated plist.
The unchanged Racket native event handler still needs the precise cold/warm
delivery and before/after default-resolution test in `MAC-NATIVE-ACCEPTANCE.md`.

Source-only review on 2026-10-11. No Racket runtime, package installer, generated launcher, or application was executed. These findings support a port of the existing Python builder; they are not native acceptance evidence.

## Exact source pin

The official `racket/racket` tag `v9.3` is annotated tag object `e87751a74c47487eed021e5605ea38dc63e47445`, pointing to commit `bbf7dea831df95922db23aaa51e13eed17dcf881`. The GitHub tag response records the tag date as 2026-08-11. All source links below use that immutable commit.

- [Tag ref](https://api.github.com/repos/racket/racket/git/ref/tags/v9.3)
- [Tag object and commit target](https://api.github.com/repos/racket/racket/git/tags/e87751a74c47487eed021e5605ea38dc63e47445)

All APIs below are in this repository's core collections or accompanying reference documentation. A separate third-party hashing, plist, or JSON package is unnecessary.

## Requires and hashing

For a `#lang racket/base` builder, the relevant additional imports are `racket/file`, `racket/path`, `racket/system`, `json`, `xml/plist`, and `(only-in file/sha1 bytes->hex-string)`. Other builder features can additionally need `racket/list`, `racket/string`, `racket/port`, `racket/cmdline`, or `racket/runtime-path`.

- `sha256-bytes` is a base-language procedure: `(sha256-bytes input [start 0] [end #f])`, accepting bytes or an input port and returning 32 digest bytes. It does not return hexadecimal text.
- `(bytes->hex-string bytes)` from `file/sha1` produces lowercase hexadecimal. The module name does not restrict this conversion to SHA-1.
- Therefore `(bytes->hex-string (sha256-bytes raw-bytes))` matches the Python builder's `hashlib.sha256(data).hexdigest()` representation.
- For the source-path-derived bundle identifier, hash `(path->bytes canonical-source)` to preserve the filesystem byte representation instead of hashing the printed `#<path:...>` representation.

Evidence: [SHA API contract](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/sha.scrbl#L9-L48), [SHA-256 implementation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/src/io/sha/main.rkt#L29-L39), [hex converter](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/file/sha1.rkt#L1-L22).

## XML plist: exact representation

`(require xml/plist)` exports `plist-dict?`, `plist-value?`, `read-plist`, and `write-plist`. Its public API is:

- `(read-plist input-port)` → a plist value
- `(write-plist plist-value output-port)` → void
- `(plist-dict? any-value)` and `(plist-value? any-value)` → Boolean

The representation is not a JSON-like hash:

- String: a Racket string, such as `"OpenRacket Preview"`
- Boolean true: `'(true)`
- Boolean false: `'(false)`
- Integer: `'(integer 1)`
- Real: `'(real 1.5)`
- Dictionary: `'(dict (assoc-pair "Name" "Example") (assoc-pair "Flag" (true)))`
- Array: `'(array "rkt" "scm")`
- Date or data: `'(date "...")` or `'(data "...")`, preserving their strings

There are no exported plist-Boolean constructors or conversion helpers. Bare `#t`, bare `#f`, hashes, and untagged lists are invalid plist values. A dictionary update helper can preserve all unrelated `(assoc-pair string value)` entries, remove matching entries, and append replacements. Preserve nested dictionaries/arrays and data/date values without converting them through JSON.

`read-plist` consumes XML, not Apple's binary plist format. That is suitable for a launcher-created XML `Info.plist`; a binary plist requires an explicit unsupported-input error or a separately justified conversion. `write-plist` generates an XML declaration, an Apple property-list DTD reference, and a `plist` element whose version attribute is `"0.9"` in this source. The writer creates this reference as text; it does not itself fetch the DTD. Do not assert byte identity with Python `plistlib.dumps` output.

Evidence: [representation predicates](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/xml/plist.rkt#L6-L31), [XML writer](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/xml/plist.rkt#L138-L150), [reader and public contracts](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/xml/plist.rkt#L175-L211).

## Filesystem canonicalization and missing leaves

- `resolve-path` is in `racket/base`: `(resolve-path path)`. It cleans the path and resolves a link at the final component by one step. Its result can be relative to that link's parent. It is not a complete all-components canonicalizer.
- `simplify-path` is in `racket/base`: `(simplify-path path [use-filesystem? #t])`. It removes redundant separators, `.` and `..`; with `#t`, Unix/macOS `..` elimination takes symlinks into account. It does not guarantee expansion of ordinary symlinks when they do not impede simplification. With `#f`, it is lexical only and therefore inappropriate by itself for runtime-boundary checks.
- `normalize-path` is from `racket/path`: `(normalize-path path [complete-base (current-directory)])`. It resolves all soft links and makes a complete path. There is no third Boolean argument, and `#f` is not an accepted explicit second argument.
- A nonexistent final ordinary path element is allowed by `normalize-path`, provided its parent can be normalized and exists as a directory. Its implementation checks each base with `directory-exists?`, then builds and resolves the next component; it does not require that final non-link component to exist. Missing intermediate directories and link cycles fail.
- For an ordinary complete path, the implementation ignores the final `split-path` directory marker and rebuilds `(build-path base name)` (lines 69–117), so `/source/` normalizes without that marker. The port also reconstructs the canonical result with `(apply build-path (explode-path canonical))` to make serialization explicit while preserving the root and components. Its native test suite covers `/source`, `/source/`, `/source/.` and dispatch argv equality.
- This is narrower than Python `Path.resolve(strict=False)`, which can retain multiple missing components. For a new output app, requiring an existing parent is appropriate: the builder must create staging beneath that parent anyway. Check `link-exists?` on the raw output before normalization, reject existing files/directories/links, canonicalize the existing parent, then append the valid `.app` leaf. Alternatively normalize the whole new-leaf path after these checks.
- For mandatory existing source/runtime/executable paths, explicitly verify existence/type in addition to normalization. `normalize-path` alone is not Python `resolve(strict=True)` because of the final-leaf allowance.
- Never fall back from a failed canonicalization to lexical simplification for a containment decision. That could turn a denied or unresolved path into a purportedly verified boundary. If multi-component missing suffix support is needed elsewhere, it needs a deliberate component-walking algorithm, not a fabricated `normalize-path ... #f` option.
- Use path components for containment instead of string prefix tests (`/runtime-other` is not inside `/runtime`). Normalization does not normalize case and is not a complete same-file identity test; case-insensitive filesystem aliases and concurrent symlink replacement remain limitations. Recheck the output with exclusive creation when publishing.

Evidence: [resolve/simplify contracts and caveats](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/paths.scrbl#L392-L474), [normalize contract](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/paths.scrbl#L772-L795), [normalize implementation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/racket/path.rkt#L24-L117), [link-exists? distinction](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/filesystem.scrbl#L341-L367).

## Permission checks and exclusive publication

`file-or-directory-permissions` is in `racket/base`:

- `(file-or-directory-permissions path)` returns a list of applicable permission symbols, including `'execute` when available to the effective user/group on Unix/macOS. Use this for the executable-access check.
- `(file-or-directory-permissions path 'bits)` returns the numeric mode.
- `(file-or-directory-permissions path #o755)` installs that mode; `#o644` is suitable for non-executable resources.
- Testing any bit in `#o111` is not identical to checking execute access for the effective user. The symbol-list form is the API closest to the intended access check.

`(copy-directory/files source destination #:keep-modify-seconds? #t)` from `racket/file` recursively copies and refuses an occupied destination. `#:preserve-links?` defaults to `#f`, so it follows source links, matching Python `copytree`'s default in this candidate. There is no `#:exists` keyword. Its source calls `make-directory` at every directory and `copy-file` without overwrite permission for each file. Do not pre-create the output directory. Never use `make-directory*` or a replace-enabled rename as the final publishing gate.

On copy failure, a partial newly created output may remain. Keep it for diagnosis and tell the caller; cleanup should target only the dedicated staging directory. An already-existing destination must not be removed.

File permission bits are preserved by `copy-file`. `#:keep-modify-seconds? #t` additionally preserves file times. Unlike Python `shutil.copytree`/`copy2`, this helper does not copy directory modes/timestamps or promise extended-attribute preservation: directories are created with default permissions filtered by umask. State this difference rather than claiming exact metadata parity. A post-copy validation can ensure the native and shell launcher files remain executable.

For staging, `(make-temporary-file ".openracket-build-~a" 'directory output-parent)` is supported; `make-temporary-directory` is also available in 9.3. This actually creates an exclusive fresh directory. Use `dynamic-wind` or an exception handler for owned staging cleanup, never for deleting the final output.

Evidence: [permission API](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/filesystem.scrbl#L483-L522), [copy implementation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/racket/file.rkt#L112-L133), [copy-file mode/existence contract](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/filesystem.scrbl#L618-L665), [directory creation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/filesystem.scrbl#L753-L765), [temporary-directory option](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/filesystem.scrbl#L1447-L1516).

## Subprocesses and isolated environment

Base-language APIs:

- `(environment-variables-copy (current-environment-variables))` produces the child-environment copy. Mutate that copy, not the process-connected original.
- `(environment-variables-names env)` returns byte-string keys.
- `(environment-variables-set! env name-bytes value-bytes-or-#f)` installs a mapping or removes it. `#f` removes; it is not the text `"#f"` or an empty string.
- `(parameterize ([current-environment-variables env] [current-directory source]) ...)` controls the environment and working directory used for child creation.

`(system*/exit-code executable arg ... #:set-pwd? #t)` from `racket/system` executes the explicit program directly, with separate arguments and no shell command interpolation, and returns its exit status. Use absolute executable paths. A nonzero result must be treated as failure explicitly; unlike Python `check=True`, this call does not by itself throw for a child exit code. `system*` returns Boolean instead. `system/exit-code` runs a shell command and should not substitute for the starred variant.

The helper uses the current input/output/error ports. To capture a runtime JSON query, parameterize output and error to separate `open-output-string` ports, then call `system*/exit-code`; retrieve the strings after it returns. The implementation pumps and drains non-file ports using threads before returning, avoiding the common deadlock from reading stdout and stderr serially. Use an empty input-string port for a noninteractive query if no input should be inherited. A lower-level `subprocess` also works, but requires concurrent output draining, port closure, waiting, and exit-status checks.

On Unix/macOS, `#:set-pwd?` defaults true and makes a further environment copy with `PWD` set to the current directory. A missing/nonexecutable child program may be reported through stderr plus nonzero status rather than an exception in the parent; check both status and query content.

The shell entrypoint must establish isolation before the Racket builder's `#lang` reader/imports can load. Changing `current-environment-variables` in the body cannot undo a poisoned collection lookup during startup. Source-verified flags: `-U` disables user-specific search paths, `-A` selects addon directory, and `-R` selects compiled roots overriding `PLTCOMPILEDROOTS`. Pass these before the builder/module argument. This evidence does not authorize executing the entrypoint or prove a particular installation is clean.

Evidence: [environment-variable contracts](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/envvars.scrbl#L17-L111), [system API](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/subprocess.scrbl#L426-L503), [system streaming/wait implementation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/racket/system.rkt#L153-L192), [PWD isolation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/racket/system.rkt#L65-L74), [startup flags](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/startup.scrbl#L326-L349), [subprocess creation failures](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/subprocess.scrbl#L32-L51).

## JSON

`(require json)` provides `(read-json [input-port])`, `(write-json value [output-port] #:indent [indent #f])`, `bytes->jsexpr`, `string->jsexpr`, and the inverse converters. In 9.3 `#:indent 2` is supported.

- Objects are immutable symbol-keyed hashes on read. Use `(hash-ref report 'version ...)`, not the string key `"version"`.
- Manifest filename keys therefore require `symbol->string` before converting to paths.
- Arrays are ordinary lists, strings are strings, and Booleans are `#t`/`#f`.
- JSON null defaults to the symbol `'null` through the `json-null` parameter. Use `(json-null)` for a null build-record field; `#f` writes JSON false.
- `write-json` expects symbol keys in object hashes; do not hand it plist dictionaries or string-keyed hashes.
- `read-json` reads one JSON value. If exact-one-document validation matters, verify only JSON whitespace and EOF remain rather than accepting extra output from a subprocess. The original manifest's fixed byte digest separately pins its exact contents.

Evidence: [public JSON contracts, types, null](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/json/main.rkt#L27-L118), [read-json object/key construction](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/json/main.rkt#L241-L250), [one-value read](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/collects/json/main.rkt#L577-L614).

## Review boundary

This research establishes API names, argument order, data representations, and source-level behavior against the pinned 9.3 source. It does not establish that a new builder parses/compiles, that a local Racket executable matches this source, that a generated native app launches, or that macOS file-event/autosave behavior passes. Those remain separate explicitly authorized runtime/native checks.
