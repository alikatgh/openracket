# Default-off same-owner binding-table index

Isolated, source-pinned DrRacket 9.3 experiment. Nothing here enables or modifies the delivered preview. The Python/source checks have passed; native compilation, actual-Racket differential execution, GUI graph/arrow evidence, full annotation/rename parity and measured benefit are still pending.

## Narrow seam and activation

Native attribution observed 74,675 calls to `add-to-bindings-table`, all returning true, with 4.599 seconds inclusive time within 6.117 seconds of arrows. That identifies a bounded candidate, not a demonstrated speedup.

The sole production target is the pinned `drracket/private/syncheck/gui.rkt`. Five exact substitutions add:

1. A read-only module Boolean, enabled only by `OPENRACKET_BINDING_TABLE_INDEX=1`; absent, `0`, and every other value are off.
2. Private numeric indexing/journal state and a read-only scalar witness.
3. A guarded branch after the unchanged original self-link check.
4. Materialization immediately before the public getter returns its binding hash.
5. State reset immediately after stock replaces that hash in `syncheck:init-arrows`.

Only a link whose two source objects are both `eq?` to the owning editor and whose four positions are exact integers is indexed. The equal?-hash key is the four-number list. The common object component is constant in this branch; equality between different objects is never replaced by identity equality. Negative, reversed, zero-span and bignum positions remain valid to the same extent they were valid to this original private method. Its caller's later range handling is untouched.

Each first accepted numeric key is appended to a reverse journal and returns true; duplicates return false. Public exposure, or any unsupported non-self input, permanently disables this generation's index and replays accepted entries in original order through the original update branch. The initial public hash object is retained. Its values are still original immutable equal?-sets. Existing references, external hash edits, invalid externally inserted values, and retained set snapshots therefore use the unmodified stock path after exposure. A reset creates a new hash and leaves all escaped old hashes untouched. The tooltip-only getter does not expose the binding hash and does not materialize it.

No arrow creation, range insertion, tool callback, annotation order, scheduler, queue priority or rename logic changes. The original self-check and its short-circuit/error order stay first, even for foreign self-links and invalid objects or coordinates.

## Explicit supported-scope boundary

This experiment is restricted to the retained stock built-in editor. Enabled behavior does **not** promise arbitrary extension/custom equality/hash callback parity. A same-owner class can implement `equal<%>` or attach `prop:equal+hash` directly via `interface*`; public interface checks cannot reliably exclude the latter. There is deliberately no invented class-property guard.

The enabled path avoids the owner's original hash callbacks until materialization. Their number and timing can therefore differ. Stateful callbacks, throwing callbacks, custom mutable hashing, custom inspectors, reentrancy through such callbacks, and resource/finalizer observations can distinguish it. The native test suite explicitly demonstrates both `equal<%>` and direct-property callback-count differences and a throwing owner's deferred error. These tests document the excluded behavior; they do not turn it into a parity claim. Foreign objects and unsupported coordinates do materialize first and then execute the original branch, but that is not a universal custom-owner guarantee.

The journal/index additionally retains one immutable four-number key per accepted edge until exposure/reset, with strong references only to those numbers; it does not retain extra editor/source objects per record. Pending numerical history and the index consume extra memory, which must be included in the eventual measurement. There is no new promise of instruction-level interleaving under concurrent/reentrant mutations.

## Evidence and public API

`openracket-binding-table-index-enabled?` is the exported activation Boolean. `openracket:get-binding-table-index-state` returns a new immutable hash of scalar values and does not materialize the table:

- `enabled`, `active`
- `accepted`, `duplicates`, `pending`
- `materializations`, `stock_calls`, `unsupported_fallbacks`
- `generation`, `fallback_reason`

`accepted` is an owning-path hit count. `stock_calls` includes replayed accepted entries. Reasons are false, `public-exposure`, or `unsupported-input`. Counters reset with each `syncheck:init-arrows`; generation increments. After a normal first getter on an indexed generation, expect positive accepted count, active false, pending zero, one materialization, and public-exposure reason. Off must have zero accepted/duplicates/pending/materializations and active false.

## Reproduction and isolated installation

```
python3 scripts/prepare.py
python3 scripts/extract.py --output tests/generated
python3 tests/source-test.py
```

`manifest.json` pins official DrRacket 9.3 package 1.17 and the exact source, plus unchanged interface support. `vendor/class-internal.rkt` and `vendor/set-types.rkt` are source-only reference files fetched from official Racket release commit `bbf7dea831df95922db23aaa51e13eed17dcf881`; their Git blob pins and SHA256 hashes are checked. They are never installed or executed by this experiment.

Apply only to a deep-copied independent disposable runtime, using canonical paths:

```
python3 scripts/apply.py --runtime-root "$CLONE" --target "$EXACT_GUI_SOURCE" --confirm-disposable-copy
```

The applier rejects wrong preimages, changed support modules, symlink/escape/hardlink paths, a changed overlay, and missing disposable acknowledgement. It preserves mode, replaces atomically, and checks the resulting hash. `--revert` restores the exact original. Recompile using that selected runtime's isolated compiled cache; source replacement alone does not prove executed activation.

## Native correctness contract

`tests/bindings-differential.rkt` runs the actual extracted add/get/reset forms in small native classes. Both arms operate on the very same owner object, so complete table equality and same-process hash/set iteration order are directly comparable. The source check confirms the extracted methods are verbatim, not a Python reimplementation. Run fresh native Racket 9.3 processes:

```
env -u OPENRACKET_BINDING_TABLE_INDEX racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_INDEX=0 racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_INDEX=unexpected racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_INDEX=1 racket tests/bindings-differential.rkt on
```

Every assertion raises on failure and exits nonzero. Coverage includes 1,200 deterministic operations plus duplicates, true self-links, zero/reversed/negative/bignum ranges, live escaped mutations/removals/clear, immutable prior-set snapshots, externally inserted invalid/mutable sets, foreign sources, object/c wrappers, transparent equal-but-distinct objects, inexact/rational fallback, tooltip-only reads, resets before/after exposure and original error ordering. It also explicitly records the unsupported custom-owner callback/error boundary. A constant-hash foreign equality callback retains a toggle-dependent state, proving fallback occurs first and both arms then make the same state-dependent duplicate decisions without changing stored hash values.

The parent-owned separate real GUI postflight must run stock, candidate-off and candidate-on, load the actual selected runtime/module, show meaningful same-owner hits, then compare the complete nonempty normalized binding graph, immutable-set type, exact source/editor associations, and bounded actual arrow/UI checks after completion. The pre-existing full annotation trace and genuine rename-answer gate remains mandatory. A pure extracted-method pass or worker-side trace pass alone is insufficient.

## Measurement boundary

The public binding getter is not a core navigation consumer in this pinned source. Normal application completion can precede materialization. Keep that genuine completed-GUI endpoint, but separately measure and disclose first public exposure latency and its deferred work. Full table identity/shape/digest validation belongs outside the timed getter call. Do not claim that work eliminated from application completion vanished. Performance harness ownership remains separate.
