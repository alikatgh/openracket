# Interval-map direct-set correctness gates

These tests cover the default-off, bounded `interval-map-set!` experiment. They
do not establish native GUI correctness, speed, responsiveness, or a complete
DrRacket test-suite pass.

## Source gate

Run from the candidate directory, with the original official source as `STOCK`:

```sh
python3 tests/check_interval_map_source.py "$STOCK" overlay/interval-map.rkt
```

This requires every byte outside the explicit flag/export and single setter
branch to remain stock, including all exported contracts and the full arbitrary
updater and cons paths. It also verifies that only the literal environment value
`1` activates the candidate.

## Actual-Racket differential gate

Run each mode in a fresh process. Both explicit module paths must resolve the
same official `data/skip-list` collection dependency. Do not substitute a Python
model, a different Racket version, or a GUI stub for this gate.

```sh
env -u OPENRACKET_INTERVAL_MAP_FAST_SET racket tests/interval-map-differential.rkt "$STOCK" "$CANDIDATE" off
OPENRACKET_INTERVAL_MAP_FAST_SET=0 racket tests/interval-map-differential.rkt "$STOCK" "$CANDIDATE" off
OPENRACKET_INTERVAL_MAP_FAST_SET=1 racket tests/interval-map-differential.rkt "$STOCK" "$CANDIDATE" on
```

The suite witnesses the exported mode flag, then compares complete interval
iteration bounds/order and every integer point query in the represented hull
after 1,200 reproducible mixed operations. It adds overlap/adjacency, invalid
bounds, negative ranges, mutable value identity, unchanged noncoalescing,
constrained contracts, callback/default ordering and exceptions, reentrant
updaters, and retained iterator survival/deletion/repair cases. Failures exit
nonzero. Exception comparison keeps the exception family, API method, and
expected/given contract details; differing module paths in blame are excluded.

The deterministic operation PRNG is separate from skip-list insertion-height
randomness. This is not a timing benchmark.

## Required genuine-GUI gate beyond these tests

- Compare the same trace/source/settings with the flag off and on. Preserve the
  complete stock annotation method dispatch, multiplicity, ordering, boundaries,
  docs end+1 behavior, and rename-capability rows.
- Check exact-prefix partial states and cancellation, editing/new-trace reset,
  menus/documentation links, tooltips/blueboxes, rename conflict handling, and
  navigation. Keep every stock tool enabled and the 20 ms yield rule unchanged.
- Measure callback-active application time separately from queued/interleaved
  elapsed time; keep terminal/lexer-to-completion timings and input/paint latency.
  A successful data-structure test alone is not evidence of a faster Mac GUI.
