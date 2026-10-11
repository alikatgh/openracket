# Mac-first runnable adoption candidate

## Fresh-profile memory default candidate

This source now prepares a **256 MiB per-job limit for a genuinely fresh isolated
OpenRacket profile**. This uses the existing DrRacket preference
`drracket:child-only-memory-limit`, shared by Run and background online analysis.
It is not a whole-application RAM cap. Existing profiles, including empty profiles
or profiles without a saved memory key, keep their current behavior and choices.
The stock installation is not changed. The actual setup/launcher/effective-value,
restore and stock-fallback native gates for this change remain pending.

This is a capacity fix. In the separate native 1 MiB workload experiment, stock
128 MiB failed with out-of-memory errors in 3/3 trials; 256 and 512 MiB each
completed analysis in 3/3. 256 MiB was the smallest tested cap that completed;
512 had no clear advantage. Analysis still took about 33–39 seconds and whole-app
RSS remained about 1.5 GB. This does not promise all files fit or faster editing.
See the [nine-trial memory report](reports/PERFORMANCE-MEMORY-38107957744.md).

Close every window using this profile before setup or a command that changes
memory preferences. The stock framework caches preferences in running processes;
restart afterward. For a source tree whose `profile/` does not yet exist:

```sh
# Default fresh profile: 256 MiB
sh scripts/setup-openracket.sh --install

# Choose ONE alternative on the first setup, before profile/ exists:
OPENRACKET_MEMORY_LIMIT_MIB=128 sh scripts/setup-openracket.sh --install
OPENRACKET_MEMORY_LIMIT_MIB=384 sh scripts/setup-openracket.sh --install
```

The option is validated before creating a profile or doing package work. It is
fresh-setup-only, not a launch override. On an existing profile use these explicit
commands instead, or the original DrRacket memory-limit UI:

```sh
sh scripts/memory-profile.sh --status
sh scripts/memory-profile.sh --set-mib 128
sh scripts/memory-profile.sh --set-mib 384
sh scripts/memory-profile.sh --unlimited
sh scripts/launch-openracket.sh program.rkt
```

Custom values are integer MiB values of at least 8; `--unlimited` is an explicit
choice and is never the automatic default. The original UI's supported choices,
including unlimited, remain available. Inspect status in a new helper process
to see the saved/effective value; it does not measure a running worker's cap.

To restore only an unchanged, automatically installed preview default:

```sh
# Close the profile's windows first.
sh scripts/memory-profile.sh --restore
sh scripts/memory-profile.sh --status
sh scripts/launch-openracket.sh program.rkt
```

Restore writes explicit stock 128 MiB through the existing preference API and
preserves unrelated preferences. It refuses a missing/unrecognized ownership
record, changed/missing value, or explicit choice, including explicit 256 MiB.
If refused and you deliberately want 128, use `--set-mib 128`. Re-selecting the
same 256 MiB value in the GUI cannot be distinguished from our saved value by
disk equality: invoking restore explicitly requests 128 in that case. The CLI
setter relinquishes ownership even for a same-value choice. Launch and repeated
setup never reapply 256 after restore or after a user changes the preference.

`sh scripts/launch-stock.sh program.rkt` retains its separate stock-comparison
preference home. A fresh stock-comparison profile retains the original 128 MiB
default; a prior explicit stock-profile choice remains its own choice. The stock
launcher does not copy the modern profile's new default.

Freshness is reserved before setup creates package directories and needs that
same setup invocation's token. Any preference file appearing during setup, even
an empty one, blocks automatic adoption. Failed/repeated setup does not recover
freshness from a missing memory key or reuse a pending reservation. After a
failed setup, finish setup and use an explicit setter if desired. No cleanup or
deletion of an existing user profile is needed. Details and verification commands:
[Memory default safety and tests](reports/MEMORY-DEFAULT.md).

## Earlier appearance and autosave candidate context

This candidate extends the delivered retained DrRacket 9.3 appearance and measured
autosave preview. The actual Mac setup, three launchers, combined save/recovery
and complete runtime-immutability checks passed in
[run 38064415026](reports/PORTABLE-INSTALLATION-38064415026.md), after the recorded
wider-scope dependency repair. The new memory-default helper and observer require
the separate native gate described above; the delivered ZIP remains unchanged.

## What remains stock

The genuine DrRacket frame, definitions/interactions editors, tool registry,
evaluator, controls, callback order and placement are retained. The toolbar uses
the previously native-tested paint overlay. The lexer keeps its original 20 ms
budget. The separate all-string scan optimization is absent.

The guard's source bytes are exactly those measured in native run
[38061486888](https://github.com/alikatgh/openracket/actions/runs/38061486888).
Mac stock/off/on save checks passed, including plain/rich data, copy/same formats,
actual autosave artifacts and TOC mappings, real filesystem failures and retry.
All three Mac timing pairs had matching replacement-save state. Median actual
autosave command time was 266.735 ms stock and 172.400 ms enabled, a 35.4% reduction
between arm medians. The median paired reduction was 24.6%. See
[the measurement report](reports/PERFORMANCE-AUTOSAVE-38061486888.md).
These measurements used the stock appearance. Combined appearance plus autosave
save/recovery behavior passed the installation gate; combined-build speed was
not separately measured there.

This change avoids two unnecessary format-conversion scans for non-`same` saves.
The separate stock autosave format-selection scan, callbacks, writing, timer and
recovery metadata remain. Custom extensions that count or throw from virtual
`find-first-snip`/`next` traversal callbacks can observe fewer calls. That extension
boundary is explicit, covered by a canary, and is not arbitrary plugin parity.
Verification-enabled conversion dialogs and crash/restart recovery UI remain
outside the completed save proof. Large-file first-coloring stalls are unresolved.

## Prerequisite and local launch

Use a complete official Racket 9.3 installation. No administrator access or system
settings change is needed. Keep this source directory writable; its `profile/`
stores the isolated packages, preferences and compiled cache. Paths with spaces
are supported. A colon in this Unix path is refused because it is ambiguous in
Racket's compiled-root search-path syntax. Symbolic links at the profile boundary
or its managed intermediate directories are refused.

Run from this directory, supplying the actual executable from your installation:

```sh
export RACKET="/absolute/path/to/Racket 9.3/bin/racket"
sh scripts/setup-openracket.sh --install
sh scripts/launch-openracket.sh --check
sh scripts/launch-openracket.sh /absolute/path/to/program.rkt
```

Setup may fetch missing official 9.3 dependencies from the release catalog. With
the full distribution already present, it copies the installed GUI package into
this profile and patches only that copy. The appearance tool remains a local
package link. New compiled files go to `profile/compiled-cache`; shipped compiled
files remain a read fallback. The delivered baseline passed whole-runtime immutability checks across all
26,838 entries. This new memory candidate must repeat that native check.

On macOS the launcher enables the previously validated reversible app-local Cocoa
appearance adapter. It follows the saved theme by default. Set `OPENRACKET_THEME`
to `dark` or `light` to choose explicitly for the initial application. High-contrast
or unsupported native appearances retain the safe fallback. Linux native parent
chrome is unchanged. Windows installation and native behavior are untested.

```sh
OPENRACKET_THEME=dark sh scripts/launch-openracket.sh program.rkt
OPENRACKET_AUTOSAVE_GUARD=0 sh scripts/launch-openracket.sh program.rkt
OPENRACKET_NATIVE_APPEARANCE=0 sh scripts/launch-openracket.sh program.rkt
sh scripts/launch-stock.sh program.rkt
```

The stock launcher selects the original toolbar behavior, clears both activation
flags and uses separate stock-comparison preferences. It shares the isolated
package copy; it is not a second pristine runtime. Preferences → OpenRacket →
Restore previous appearance remains the supported live theme rollback.
The native autosave and toolbar source appliers each also support `--revert` for
byte-exact source restoration inside the profile. Close running instances before
changing installed source. Rerun setup to prepare the modern source again.

## Baseline verification and new native gate

- Eight launch-profile tests include spaces, inherited environment isolation,
  symbolic-link refusal, child-process addon/cache inheritance, mocked launcher
  flag/opt-out handling, failing preflight exit status and actual Racket 9.3
  recompilation into the first cache root without changing the fixture's original
  shipped bytecode.
- Five autosave installer tests cover exact apply/reapply/revert, unrelated target
  refusal, root/intermediate links, outside-profile targets and tampered inputs.
- Eleven generated stock-save model groups and five exact-source checks pass.
- The original toolbar provenance and transaction tests are retained. The
  earlier combined local run passed 214 Racket tests and 34 Python checks.
  The subsequent actual Mac installation and launch gates passed as linked above.
- The new memory helper has eleven local source/shell checks, 20 native helper
  cases, and 15 observer contracts. Only the source/shell checks have run locally;
  the native helper, observer and real-launch capacity checks remain pending.

The new Mac gate must rerun actual setup and launch, observe the genuine
launcher-opened file/frame and theme/guard/memory state, verify explicit choices,
restore and repeated setup, retain the independent save/recovery checks, and
compare every original runtime file before and after. The
observer used for that gate is a CI-only tool and is not part of ordinary setup.
