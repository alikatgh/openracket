# Run 38104720998: actual Check Syntax trace review

## Conclusion and scope

The original exact-order comparator correctly fails on pristine stock versus a
second pristine stock process. This result remains explicitly non-passing.
It is not a candidate-only regression, and it is not corrected by sorting the
trace. The raw capture files remain unchanged.

A separate bounded contract passes on all four captures: completed annotation,
binding/navigation and the five tested rename-query semantics. Each capture has
436 trace entries, 71 documentation annotations and 535 successful actual rename
answers across five fixtures. The comparator preserves complete typed payloads
and duplicate counts, plus exact order-sensitive consumer projections.

This contract does **not** certify transient replay or arrow-paint ordering,
rendered pixels, arbitrary source programs, all possible rename strings, or
performance. Native source modules and native capture code are unchanged.

## Concrete nondeterminism

In repeated-base, stock trace entry 4 is an arrow from `existing` at [26,34) to
[124,132). Stock-again entry 4 is instead an arrow from `second` at [77,83) to
[140,146). Complete identifier-annotation groups move, not only record indexes.
The first exact comparator diagnostic happens to be rename answer entry_index
10 versus 6, because that field is encountered first during JSON comparison.

Upstream traversals enumerates hash tables and identifier dictionaries when
producing these groups: `traversals.rkt` 801-829, 843-879; `get-idss` at 1641-1644.
Bound-occurrence tooltips also follow hash enumeration at 1173-1206. The trace
builder preserves emission order at 1688-1690.

`online-comp.rkt` 83-100 assigns each arrow's request ID from the current rename
table size. Its channel/ID therefore names a process-local callback registration;
the same logical arrow acquires a different ID when preceding groups move. The
actual answerer invokes that callback at 25-30. Alpha-renaming these handles is
valid only after validating the table bijection and attaching every actual answer
to its original full logical event. Merely dropping IDs or comparing answer bags
would lose that association.

All four captures have identical full event inventories after this validated
handle association. Per-character checks show remaining local arrow-order
variation only at shared require/#lang binder ranges: 11 character positions each
in repeated-base and unicode, and 22 each in the remaining three fixtures. All
non-arrow consumer sequences and states below match exactly.

## Source-backed acceptance definition

The implementation recognizes only the nine methods present in these captures.
Unknown methods, unexpected signatures, unreviewed text types, malformed paths,
out-of-source ranges, noninteger phases, heterogeneous require groups, broken
documentation pairing or nonbijective rename tables fail closed. It validates
native completion, module source pins, actual flag/export activation, fixture
positive controls and identical timeout bounds using the original strict
validator. Fixtures are bounded to 10,000 characters and 10,000 entries.

1. Keep every full event occurrence in a duplicate-preserving inventory. Arrow
   records retain endpoint geometry, phase, actual/require flags and their exact
   ordered five-query response vector. Validate one real channel per fixture and
   consecutive unique request IDs, with each response tied to its entry index.

2. Require exact docs/text-type adjacency from the real producer
   (`traversals.rkt` 1550-1563). Keep all labels, paths, tags, anchors, positions,
   types and source text. No further path normalization is performed.

3. Preserve documentation's exact last-write map on [start,end+1), including the
   stored start/end, definition tag, path and URL tag. Also preserve every
   overlap-local docs sequence. `blueboxes-gui.rkt` 673-677 uses interval-map-set!
   with that extra endpoint; apparently adjacent ranges can conflict.

4. Replay keyed documentation/require menus with the actual half-open range and
   zero-width expansion. Keep first-key-wins callbacks and exact per-character
   menu order. `gui.rkt` 658-685, 1002-1005, 1107-1150 and 1410-1474 establish
   these rules. Preserve global require-open event order because it also feeds
   blue-box fallback candidates (`blueboxes-gui.rkt` 657-679, 540-580).

5. Preserve exact per-character definition-link, text-type/color and tooltip
   sequences. The first def-link determines navigation (`gui.rkt` 1425-1435,
   1913-1921); the first colored record determines highlighted range (1756-1769).
   Tooltip order is conservatively retained although successful tooltip display
   sorts a set of strings and aggregates bounds (1685-1709).

6. Preserve definition-target sequences by their actual (id,mods) key and the
   final target. The GUI deliberately ignores phase when overwriting that hash
   (`gui.rkt` 687-697). Preserve prefix-reference sequences per require range.

7. Preserve complete arrow occurrence sequences per source/destination range
   pair, and the exact first retained arrow. The actual binding table deduplicates
   using endpoint ranges alone (`gui.rkt` 475-491, 1045-1063), so later differing
   metadata or predicates cannot silently replace the first one in this model.

8. Keep every overlap-local local-binding arrow and tail-arrow ordered. Keep
   source-choice order and the first jump-to-binding destination at each
   character. Allow only permutations of require arrows with identical binder
   range, source geometry, phase, actual/require type and tested response vector.
   Different destinations remain fully represented in the inventory and graph.
   Different binder ranges, mixed metadata, local/tail interleavings or different
   surviving predicates cannot be normalized by this rule.

The final allowance has a narrow functional justification. Rename and identifier
highlighting exclude require arrows (`gui.rkt` 1562-1569, 1604-1609). Next-bound
occurrence navigation sorts the identifier graph (1855-1866). Jump-to-binding
uses the first arrow's source range (1902-1911), which is explicitly compared.
Require-prefix candidate handling sorts by source position and shared binder
ties refer to the same range. No different logical edge or tested answer is
removed by this allowance.

It does not prove pixel or timing equivalence. Mouse-over arrow drawing retains
list order (1229-1248) and draws sequentially with a 15 ms budget (2094-2153).
Replay itself yields after about 20 ms (2478-2505). The diagnostic preserves
`exact_raw_order_equal: false`, each first exact difference and every character
position with changed require-arrow paint order. This is observed stock
nondeterminism, not a functional difference asserted to have been eliminated by
the experiment.

## Reproduction

Integrated implementation: `compare-trace.py`; original exact validator:
`compare-trace-exact.py` in this tests directory. The separate review implementation
and native diagnostic remain in the review directory. Both read inputs only.

```sh
python3 compare-trace.py --manifest ../manifest.json \
  ../../openracket-recovery/results/run-38104720998/decoded/trace-stock-trace.json \
  ../../openracket-recovery/results/run-38104720998/decoded/trace-stock-again-trace.json \
  ../../openracket-recovery/results/run-38104720998/decoded/trace-off-trace.json \
  ../../openracket-recovery/results/run-38104720998/decoded/trace-on-trace.json
python3 -m unittest test_compare_trace -v
```

Native review output: `native-diagnostic.json`, including SHA-256 of each
unchanged input. Twenty-two synthetic mutation tests pass. They verify that
changed/lost/duplicated events, moved or changed answers, changed edge/phase/
geometry, broken handles, overlap-sensitive docs/menu/tooltip/navigation state,
first retained duplicate-edge metadata, and local/tail/different-binder ordering
and source-only corruption are rejected. Synthetic fixtures test the comparator; only the actual CI
captures support native-result claims.

## Reuse for interval-map direct-set experiment

The bounded semantic projection and all deliberate mutation tests are reused unchanged. Native activation/source evidence now selects `data/interval-map`; xref, traversal and handler sources must remain original9.3. This direct handler gate establishes actual producer/rename outputs, not GUI map application by itself. The separate actual-map differential and genuine GUI gates cover the changed consumer data structure. Raw trace order remains diagnostic under the same source-backed limitations above.
