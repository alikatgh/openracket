# Default-off named-style index: source-only prototype

**Status:** local source preparation only. Python source/model checks passed; native
Racket execution, GUI/WXME equivalence, performance measurements, publication and
adoption have **not** occurred. A GitHub publication/CI authorization hold remains
in effect. This directory is separate from every existing freeze and delivered
preview. No packages were downloaded or installed, and no native runtime was run.

## Smallest compatible seam

The pinned official 9.3 `style-list%` public `find-named-style` method is the only
existing behavior changed. When `OPENRACKET_NAMED_STYLE_INDEX` is exactly `1` at
module initialization, a lookup captures `members` once. It reuses a private
cache only when that exact immutable list is `eq?` to the cache's stored list.
Otherwise it walks that captured list and constructs an immutable equal?-keyed
hash from the **original immutable stored names** to the **first style object in
list order**. An immutable `(snapshot . index)` pair is then published with one
assignment. The current call reads its local complete pair, never a potentially
replaced shared cache field.

A later add or reorder makes the cache ineligible by list identity. A completed
old build can replace a newer cache during concurrency or continuation resumption,
but cannot be mistaken for the newer list: subsequent calls reject it. The old
call answers from its captured list, just as the stock `for/or` captures that
list. No locks, publication callbacks, mutation hooks, exception handlers, query
copies, query retention or retry loops are added to the production method.

The source case is compelling enough for a **separate experiment**, not adoption:
all members are created by the module's private `style%`, published names cannot
be renamed by ordinary public methods, and only two stock sites replace the
immutable members list. Stored names are either `#f`, the Basic literal, or
`string->immutable-string` results installed before membership. Empty strings,
Unicode and case-sensitive string equality retain their ordinary meaning.
Mutable caller query strings are read normally and are never stored. There is
no new promise for a query string being concurrently mutated during its lookup;
stock offers no atomic query snapshot, and this experiment adds none.

## Exact stock behavior retained

- Unset, `0` and every unexpected flag value use the byte-identical original
  lookup expression and its original `[string? name]` contract. No diagnostic
  counter changes occur on that branch.
- `do-named-style` retains its separate linear scan. No virtual call is introduced
  in naming; subclass overrides retain the original dispatch paths in `convert`.
- Creation, replacement, conversion, copy, style mutation, batching,
  notifications, member order, stream methods and return object identity are
  untouched. Source tests compare their complete forms byte-for-byte.
- Reentrant notification before `add-member` can create duplicate names. The
  outer/inner callback observations and head-first winner are preserved.
- A reorder that mutates the list and then raises still invalidates by list
  identity. The stock `get-s-join-style` spelling and exception are not repaired.
- Diagnostic access uses an exported namespaced module function backed by a
  local-member-name method, so it does not reserve an ordinary subclass method
  name. It is read-only and never warms the cache.

## Cost and evidence limitations

Every new member, **including unnamed/anonymous styles created during coloring**,
changes list identity. Every reorder does too. A subsequent lookup therefore
rebuilds the entire map, even if only one early match was wanted or the set of
named styles did not change. Immutable hash construction allocates and diagnostic
counters add real work. These costs stay in any eventual measured workload; no
prewarming, heuristics or omitted cold start is permitted.

The cache retains one immutable name map and one old list snapshot. Names/styles
are not copied. After reordering, old list cells can remain retained until the
next rebuild or collection of the style list. An in-progress lookup can also
retain its local old snapshot. This is additional memory even if lookup improves;
it must be measured alongside allocation, GC and full completion. Flag-off still
adds a few private fields and an activation branch, so it is not a zero-overhead
replacement for stock.

Named lookup appeared in 11 sparse samples during coloring gaps. That is evidence
of presence, not exclusive cost, queue ownership or likely speedup. Previous
binding variants were rejected. There is no performance claim here.

## Files and safe local checks

- `vendor/style.rkt`: exact official pinned source; see `PROVENANCE.json`
- `vendor/prefs.rkt`: exact small official sibling dependency, separately pinned
- `overlay/style.rkt`, `patch.diff`: generated candidate and insertion-only diff
- `scripts/overlay.py`: hash-guarded generation, verification, apply and removal
- `tests/source_test.py`: source structure, exact restoration and fail-closed
  validator checks; these do not execute Racket
- `tests/snapshot_model.py`: 15,000 identity comparisons across every order of
  five model snapshot publications; this is not evidence of native behavior
- `tests/native/differential.rkt`: full stock/candidate module comparison, unrun
- `tests/native/publication.rkt`: deterministic reentry/interruption/continuation/
  thread tests using a test-only insertion into the full candidate module, unrun
- `scripts/prepare_native.py`, `scripts/run_native.py`: future explicitly
  authorized native gate preparation/runner; not part of portable checks
- `DIAGNOSTICS.md`, `NATIVE-PLAN.md`: integration contract and remaining gates

Run only portable checks for the present authorization:

```sh
python scripts/overlay.py generate
python tests/source_test.py
python tests/snapshot_model.py
```

Explicit source-only applier operations require a target path and fail closed on
any nonmatching bytes:

```sh
python scripts/overlay.py verify --runtime-root /canonical/disposable/runtime \
  --target /canonical/disposable/runtime/collects/racket/snip/private/style.rkt
python scripts/overlay.py apply --runtime-root /canonical/disposable/runtime \
  --target /canonical/disposable/runtime/collects/racket/snip/private/style.rkt \
  --confirm-disposable-copy
python scripts/overlay.py revert --runtime-root /canonical/disposable/runtime \
  --target /canonical/disposable/runtime/collects/racket/snip/private/style.rkt \
  --confirm-disposable-copy
```

Every runtime operation requires an explicit canonical root and descendant file
with the expected collection suffix and pinned sibling dependency. Writes also
require acknowledgement of an independent disposable copy. Symlinked source,
root or ancestor paths and hard-linked files are refused; atomic replacement
preserves source permissions and verifies the result. The portable tests create
and canonicalize temporary disposable fixtures, including ancestor-alias rejection.

The diff contains only insertions. Removal reconstructs the exact original bytes
and verifies the stock SHA256; it is not a generic patcher for other versions.
Do not apply to an installed runtime or execute native gates until separately
authorized. Native source preparation can use the vendored dependency, but the
native runner deliberately verifies the **resolved installed official** source
and its sibling prefs file before staging complete isolated modules.
