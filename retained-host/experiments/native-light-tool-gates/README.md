# Modern-light real-tool gate: local-only derivative

Prepared 2026-10-11. No publication, CI trigger, download, installation, Racket
reader/compiler, headless Racket execution or native GUI execution was performed.
Remote publication remains on the coordinator's explicit authorization hold.

## Minimal change and provenance

The exact source baseline is `openracket-native-tool-gates-freeze-20261011-1125`.
The coordinator identified native Mac run `38140896349` as acceptance of all six
stock/modern-dark Debugger, Macro Stepper and teaching-test cases. This handoff
reuses those bytes; it does not rerun or independently recertify that result.

All eleven original native files are unchanged, including the accepted stock
entrypoint `tests/independent-native-host.rkt`. `BASELINE-1125-SHA256.json` pins
all reused source/check inputs. The accepted dark freeze and delivered preview
were only read and were not modified.

Five test-only integration files are added:

1. `tests/independent-native-light-tools-host.rkt`: generated from the exact
   accepted host with six bounded insertions. Uses a separate filename so stock
   still executes the exact accepted entrypoint. Rejects any environment other
   than explicit modern/light/native-on with one of the three accepted tool cases.
2. `tests/native-light-state-observer.rkt`: read-only actual state observation on
   the existing GUI handler immediately before and after the unchanged tool
   workflow. No setter, appearance capture/restore, added wait, repaint or control
   callback. Reuses the accepted portable observer's adapter-inspection route.
3. `tests/native-light-state-contract.rkt`: strict headless validator also used on
   the real observations; missing keys, including false-valued keys, fail. Recursive normalization
   permits ordinary symbol-key hashes and JSON hasheq with identical fields;
   no value/type normalization is performed.
4. `tests/native-light-state-expected.json`: byte-pinned shared expected state.
5. `tests/native-light-state-standalone.rkt`: mandatory headless positive/refusal
   matrix and an intentional uncaught wrong-painter negative control.

`reports/light-host.diff` is the exact bounded host delta. `reports/NATIVE-REVIEW.diff`
adds the four other new files in full. These are review diffs; use the frozen
allowlist to integrate into a new complete candidate, never patch the delivered
preview, the accepted freeze, or a production source file in place.

The existing light/dark/light preference toggle, two real Runs, Debugger
launch/source traversal/Step/Go, Macro Stepper real cursor/navigation/close and
teaching failure/source-link/unsaved correction/rerun all remain unchanged.

## Actual light evidence

Both `before-tool` and `after-tool` must show:

- Framework transaction `applied`, exact boolean light preference `false`, both
  selected OpenRacket scheme names, actual background RGB `[247,248,250]` and
  actual default-text RGB `[37,48,71]` from Framework's current lookup.
- Actual retained painter mode `light`, modern renderer active, verified native
  chrome blending active, and all eleven exact light painter palette colors.
  `theme-color` is read under the observed painter mode, the same selection used
  by the retained `switchable-button%`; the observer never forces light state.
- Actual Cocoa backend, explicit and effective `NSAppearanceNameAqua`, no increased
  contrast, and a false actual `white-on-black-panel-scheme?` observation.

The state is printed before validation, retained in success READY JSON, and
validated with RackUnit's raising handler. Any failure continues through the
accepted typed host diagnostics/capture/failing-exit path. The tests inspect
native appearance and loaded palette state; they do not measure screen pixels,
prove every tool-specific style, or establish complete UI/accessibility parity.

Palette and Cocoa API evidence comes from read-only members of the already-local
`OpenRacket-Mac-preview-source.zip`. Exact archive/member hashes and full reference
copies are included under `reports/production-source-evidence.json` and
`reference/production/`. Reference copies are excluded from native integration.
All six reference members were also independently matched byte-for-byte against
`reference/accepted-0520-CONTENTS-SHA256.json`, SHA-256
`2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552`, the current
accepted candidate manifest. This is a six-member equality proof, not a claim
that the entire older ZIP is current. Use the existing accepted candidate/runtime
setup and verify the future runner separately.

## Portable checks (Python only)

From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/prepare-stock-tool-host.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/prepare-light-tool-host.py --check
PYTHONDONTWRITEBYTECODE=1 python3 tests/stock-tool-source-test.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/coordinator-standalone-source-test.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/tool-dispatch-source-test.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/light-tool-source-test.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-light-bundle.py
```

The first three test suites retain the accepted 27 source checks. The new suite
adds 13 tests (including multiple refusal subcases): unchanged source hashes,
exact derivation/CRLF rejection, lexical delimiters, unchanged tool dispatch and
deadlines, source-supported palette/native readings, all six synthetic receipt
shapes, and fail-closed native/preflight receipts. The same commands pass from a
fresh temporary copy without the baseline sibling or local source archive.

These are lexical/source and Python synthetic evidence-validation tests, not a
Racket reader, compiler, real native workflow, or native appearance pass.
`NATIVE-CLI-CONTRACT.md` defines the future authorized native run and strict
acceptance. Light-mode native acceptance remains pending.
