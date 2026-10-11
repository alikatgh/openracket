# Independent direct-set review

## Source-only conclusion

The candidate's sole data-structure change is a sound, bounded optimization of
the setter's post-removal tail, subject to the pending actual-Racket and genuine
GUI gates. There is no demonstrated speedup yet.

Official stock `data/interval-map.rkt:99–103` checks the bounds, removes the
range, then runs the general updater with a constant-returning lambda. Removal
(`105–114`) has already split both boundaries and removed every start key in
`[start,end)`. Consequently, the general updater's second pair of splits cannot
create an interval there, and its search must reach its gap-insertion branch.
The direct `skip-list-set!` tail creates precisely that one interval.

The skipped work is two boundary searches, the initial update traversal search,
redundant argument-list/check work, and the constant-updater/delayed-default
machinery. The initial removal and final insertion are retained. This chiefly
targets `gui.rkt:658–685 → blueboxes-gui.rkt:673–677` docs-range insertion; it is
not an optimization of all arrow/tooltip cons operations.

## Preserved semantics checked by source review

- Exact supplied value object is retained as the new interval's cdr. No copies,
  deduplication, reordering, or coalescing are introduced.
- Both boundary splits and the deletion run before either branch. Existing
  surviving nodes, deleted-iterator invalidation, and next/repair behavior have
  the same mutation sequence through removal; both tails create one new start
  node. The removed redundant splits are no-ops on the logical partition.
- The public contracts are byte-identical. Setter checks and removal execute in
  the same order. The stock tail's lambda only returns the supplied value; no
  user updater/default callback is being skipped. Under valid invariants, the
  removed internal checks cannot newly reject a call already admitted here.
- Stored values have already crossed the setter's exported value contract; the
  backing skip list uses its stock default key/value contracts. This does not
  bypass the interval map's custom key or value contracts.
- All arbitrary updater/cons/remove/expand/contract implementations remain
  byte-identical. All GUI method dispatch, annotation emission, docs end+1,
  source bounds, menu callbacks and 20 ms yields are untouched.
- The only enabling value is the literal environment string `1`; absent, `0`,
  and other values leave the original setter tail active.

As with the original mutable map, this is not a new concurrent mutation safety
guarantee. Changes in instruction-level interleaving are not claimed equivalent.

## Verification performed here

- PASS: Python source gate against the exact official stock source and candidate.
- PASS: Python syntax compilation of the source checker.
- PASS: lexical matching of Racket suite delimiters (not compilation).
- NOT RUN: actual Racket differential suite, including on/off witnesses.
- NOT RUN: actual DrRacket/native GUI correctness or performance gate.

Stock SHA-256:
`1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de`

Candidate SHA-256:
`1f1636316c3ba3f307fcb33f44d68c00ee9804b775fac7d78916db01d87fec4d`

`README.md` documents executable gate commands and the minimum GUI follow-up.

## Deferred finding, outside this candidate

The general update loop also searches from the skip-list head to overwrite a
value whose iterator it already holds. A future private cursor-overwrite path
may avoid that repeated work, but arbitrary updater reentrancy needs its own
proof and tests. It is not implemented here. Default GUI map values use `any/c`;
the reviewed source does not establish deep contract scans of annotation lists.
