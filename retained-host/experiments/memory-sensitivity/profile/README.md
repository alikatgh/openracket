# Headless DrRacket 9.3 memory-sensitivity profile setup

This helper prepares one disposable profile for the approved 128 / 256 / 512 MiB
configuration experiment. It is not a code optimization and does not modify the
delivered application, the cloned runtime, an expansion worker, or the observer.
Worker activation and actual enforced-limit evidence remain independent checks
in the benchmark harness.

## Interface and timing boundary

Create two **existing, empty, disjoint directories**, then launch a separate
process using the cloned runtime's Racket executable:

```sh
PLTUSERHOME=/trial/profile PLTADDONDIR=/trial/addon \
  /clone/bin/racket /support/memory-profile.rkt \
  --limit-mib 256 --output /trial/memory-setup.json --runtime-root /clone
```

All paths are absolute. The output's parent must exist, and the output must not
exist or overlap either profile or runtime. The runtime root must contain the
actual executable and both resolved original sources. Symlinks are resolved in
every path component before containment checks.

Only `128`, `256`, and `512` are accepted, with no alternative spelling or units.
Finish this setup process and require exit code 0 plus `status: "verified"`
**before** starting the GUI process timer. Pass the same `PLTUSERHOME` and
`PLTADDONDIR` to that GUI process. The matched Mac experiment leaves `HOME`
unchanged; the helper explicitly refuses any actual legacy fallback store before
preference access. Never import this helper into the measured
host. Do not run setup twice in the same profile. Discard a refused trial profile;
do not launch its timed GUI process.

Success JSON includes:

- `expected_limit_bytes`, `selected_limit_bytes`, `readback_limit_bytes`,
  `persisted_limit_bytes`
- `expected_default_limit_bytes`, `original_default_limit_bytes` (134217728)
- `profile_was_empty`, `addon_was_empty`, `only_expected_preference_changed`
- physical profile/addon/runtime/executable/preference-store paths
- `sources.eval_helpers` and `sources.framework_preferences`, each with actual
  physical `path`, `sha256`, and `expected_sha256`
- `one_key_delta`: one added persisted key and its byte value
- store hash and key counts (0 before, 1 after), independent disk-read method,
  and `gui_initialized: false`

Every success arm, including 128 MiB, adds exactly one persisted key. Setting a
registered preference to its existing default still persists it in this source.
No unrelated preference is rewritten or removed. Existing profiles are refused,
preserving their bytes. Reports are bounded to 32768 characters; preference-store
reads are bounded to 1 MiB and 4096 distinct symbol/value entries, reject reader
extensions and duplicate keys, and require exactly one datum.

Failures return nonzero. Once the output has been safely opened, they emit a
bounded `status: "refused"` report with `stage`, `error`, and
`preference_write_attempted`. Invalid/unsafe/existing output paths produce only a
stderr error. A failure after a setter attempt is not rolled back: the disposable
profile must be discarded. Never treat a report's existence alone as success.

## Source-backed behavior

The pins are from the supplied official full 9.3 package sources:

| File | SHA-256 |
| --- | --- |
| `drracket/private/eval-helpers-and-pref-init.rkt` | `e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62` |
| `framework/preferences.rkt` | `59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c` |

Package metadata declares these upstream revisions:

- drracket-core-lib: `racket/drracket` commit
  `1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6`, built `9.3`
- gui-lib: `racket/gui` commit
  `6f0213fa0535d87dd4e35f56c8266d948c8c089e`, built `9.3`

Review findings:

1. Eval-helper lines 29–33 register
   `drracket:child-only-memory-limit` with default `128 * 1024 * 1024`. The helper
   dynamically loads that original module; it never reimplements registration.
2. Framework preference lines 43–45 bind the standard persistence procedures and
   add the `plt:framework-pref:` prefix. Lines 145–187 implement the registered
   setter and call the low-level writer even for a same-as-default value.
3. The normal API `preferences:get` checks the original default and validates
   in-process readback. Public `racket/file` `get-preference` with **flush mode
   `#t`** and an explicit filename forces an independent disk reread. `#f` would
   permit cache reuse and is intentionally not used. A second direct bounded
   store parse verifies the exact key addition and equality of every other entry.
4. The 9.3 `reference/filesystem.scrbl` contract says an absolute `PLTUSERHOME`
   controls `home-dir` on all platforms (lines 31–33); `pref-file` belongs under
   that home (lines 55–82), and `PLTADDONDIR` controls `addon-dir` (lines 142–159).
   The helper verifies actual resolved system paths as well as the environment.
5. The same reference documents fallback preference reads and cache modes
   (lines 1612–1661). Existing profile content and a runtime-wide
   `racket-prefs.rktd` fallback store are refused. On Unix, the legacy candidate
   `~/.plt-scheme/plt-prefs.ss` expands through `HOME`, not `PLTUSERHOME`, so the
   helper explicitly checks that actual candidate before any preference API
   access. This is supported by actual upstream v9.3
   [racket/file.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/file.rkt)
   and [rktio_fs.c](https://github.com/racket/racket/blob/v9.3/racket/src/rktio/rktio_fs.c#L2194-L2233).
   The reference's historical `defaults`-collection sentence is stale; actual
   v9.3 persistence uses the old-profile/config fallback paths. No extra
   `defaults`-collection restriction is imposed. No full native clone was
   available locally to establish fallback-store absence; CI must establish it
   for its supplied clone rather than assuming it.
6. Loading `racket/draw` is allowed by the original module's headless design.
   Its stack-checkpoint import is specifically the independent `item->srcloc`
   submodule, not the GUI parent. `racket/gui/dynamic` checks that the GUI has not
   been initialized before or after registration/persistence.

Version `9.3` and these source-byte pins are enforced; they do not constitute
cryptographic attestation of every executable/library in an installation. Use
the harness's separately verified disposable official clone.

## Tests and current verification limits

```sh
python3 test_memory_profile.py -v
python3 test_memory_profile.py --racket /clone/bin/racket --runtime-root /clone -v
```

The first command ran locally: **2 source-contract tests passed**, native suite
explicitly skipped because no Racket executable is installed. Python bytecode
compilation passed. No native helper success, Racket compilation, GUI run,
benchmark result, or speed improvement is claimed from those static checks.

The second command runs native setup for all three legitimate limits, checks
bounded schema/source hashes/one-key delta, and uses another fresh Racket process
to independently read each persisted value. It also checks invalid values,
missing/nonempty/overlapping profile paths, nonempty addon state, wrong runtime
root, out-of-runtime collection source (refused before executing it), stale
profile reuse, existing-output preservation, and a separate-HOME Unix legacy
fallback fixture that must refuse before reading or mutating preferences. Its Racket unit tests copy and
tamper both pinned files in a disposable fixture; they test source-root escape,
symlink escape, duplicate/malicious stores, and preservation of unrelated entries
in the exact-delta predicate. They never change an installed runtime source.

Native tests intentionally remove `DISPLAY` and all experimental `OPENRACKET_`
flags. Normal test cases also isolate `HOME`; the regression deliberately uses a
different `HOME` to verify the helper's refusal. This test fixture does not change
the benchmark supervisor's matched Mac environment. Tests use only an
already-provided full Racket 9.3 clone and never download,
install, launch a native GUI, or publish anything.
