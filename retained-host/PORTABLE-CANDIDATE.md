# Mac-first runnable adoption candidate

This candidate combines the tested retained DrRacket 9.3 appearance with the exact
measured autosave guard. It is being prepared for a fresh native setup/launcher
acceptance run. That installation route has not yet passed its native gate.

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
behavior is a new native gate; its speed has not been measured.

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
files remain a read fallback. Actual whole-runtime immutability is still a native
installation acceptance condition, not inferred from these scripts alone.

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

## Completed local checks and next gate

- Eight launch-profile tests include spaces, inherited environment isolation,
  symbolic-link refusal, child-process addon/cache inheritance, mocked launcher
  flag/opt-out handling, failing preflight exit status and actual Racket 9.3
  recompilation into the first cache root without changing the fixture's original
  shipped bytecode.
- Five autosave installer tests cover exact apply/reapply/revert, unrelated target
  refusal, root/intermediate links, outside-profile targets and tampered inputs.
- Eleven generated stock-save model groups and five exact-source checks pass.
- The original toolbar provenance and transaction tests are retained. The
  combined local run passed 214 Racket tests and 29 Python checks. Native observer
  expansion and real installation are still pending.

The Mac native gate must run the real setup and launcher, observe the genuine
launcher-opened file/frame and theme/guard state, exercise save/recovery on that
combined host, and compare every original runtime file before and after. The
observer used for that gate is a CI-only tool and is not part of ordinary setup.
