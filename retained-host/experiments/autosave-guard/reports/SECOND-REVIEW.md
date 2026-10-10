# Independent second review: save-scan guard

Reviewed the exact generated `clever-file-format-mixin` change, native save/reload fixture and genuine DrRacket caller against pinned Racket 9.3 sources. No production edits or local native GUI execution were performed.

## Findings

- The two early predicates leave `same` saves' original scan, conversion, prompt and inner-hook order intact. For other explicit formats, enabled mode intentionally omits public `find-first-snip` and snip `next` calls. Arbitrary extension callback/exception equivalence is therefore **not** established; the existing model canaries correctly expose that difference. Default-off behavior remains the baseline.
- The actual `do-autosave` implementation still performs its required plain/rich classification, uses `copy`, and restores the original file format. The prepared native fixture verifies real plain/WXME recovery artifacts, exact Unicode/image/nested-editor payloads, and file/modified state.
- `framework:verify-change-format` is `#f` in the pinned fresh stock defaults. The caller checks that value instead of changing it. Verification-enabled conversion dialogs and crash/restart recovery UI remain separate, unrun gates.
- `still-untouched?` is a normal public definitions-editor method in `drracket/private/unit.rkt` (908–911). `get-eventspace` is public in `mred/private/mrtop.rkt` (76). No private-member-name workaround is needed.
- The real save implementation invokes `on-save-file` before opening the destination, then guarantees `after-save-file` through `dynamic-wind` (`mred/private/editor.rkt`, 273–350). A filesystem error is raised rather than converted to a false return. A format conversion already performed by a `same` save persists even when opening fails. Tests must retain that stock behavior, not invent rollback.

## Additional native failure/retry gate

`tests/review-native-save-failure.rkt` exports the zero-argument `run-review-native-save-failure-check!`, called on the GUI handler by the main native caller. It prepares four real cases: plain/rich content crossed with `copy`/`same` saves.

Each case uses an existing temporary directory as the destination, requiring a genuine filesystem exception without changing permissions. It asserts:

1. Exact `can` → `on` → `after #f` hook order.
2. Unchanged original sentinel file bytes, editor filename, modified state and full payload.
3. The exact stock post-conversion format on failure.
4. A successful retry with `after #t`, correct filename/modified behavior, and artifact reload preserving Unicode, bitmap bytes and nested-editor data.

The fixture uses a real native editor with the actual clever-file-format mixin. The companion fixture independently exercises the actual DrRacket definitions editor and `do-autosave`. The failure fixture does **not** claim to exercise the modal autosave-error handler or crash/restart UI.

The recovery metadata assertion was recommended to the primary fixture owner using exact `path-utils.rkt` lines44–47: the table stores two-element lists of original and autosave path bytes. An artifact reload alone is not proof of restart recovery.

## Execution status

- Independently reran the existing 11 parsed-source/model test groups: pass.
- Independently reran the existing 5 Python source-integrity tests: pass.
- Native failure/retry file and caller: reader checks only; native expansion/execution pending.
- No speedup is inferred from fewer model scan callbacks.

Native failure/retry SHA-256: `e8f78dcd4f81b711e674745491eb4126abf97e55c066c53972b781a7c1211f46`.
