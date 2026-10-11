# Default-off interval-map direct-set experiment

This isolated candidate tests one source-backed redundancy in Racket 9.3's documentation-range data structure. It is not part of the delivered preview, and no speed improvement has been demonstrated.

The successful genuine-GUI run [38115601310](https://github.com/alikatgh/openracket/actions/runs/38115601310) showed annotation application lasting about 22 seconds, including other interleaved GUI work. The candidate targets only part of that stage: `syncheck:add-docs-menu` calls the unchanged blue-box documentation range setter, which uses `interval-map-set!`.

## One change

The original setter checks the interval and removes its previous contents. At that point the complete half-open range is empty. It then invokes a general update operation, repeating boundary searches and building updater/default machinery, solely to insert one interval. The enabled branch directly performs that final insertion with the same start, length and exact supplied value object.

- The same initial interval checks, boundary splitting and removal remain.
- Public contracts and every other map operation are byte-identical.
- No annotation, range, duplicate, callback, trace order, tool or 20 ms scheduling rule is changed.
- The only enabling value is `OPENRACKET_INTERVAL_MAP_FAST_SET=1`. Absent, `0`, or any other value executes the original setter tail.
- `openracket-interval-map-fast-set-enabled?` is a read-only exported activation witness. Stock lacks that export.
- Xref caching, scan shortcuts, color budgets, appearance and autosave experiments are not enabled in this measurement.

This preserves the existing mutable-map concurrency contract; it does not promise identical instruction-level interleaving between concurrent mutations.

## Exact source and installation scope

`manifest.json` pins the official 9.3 `data-lib` 1.2.1 source and three unchanged supporting modules. `scripts/prepare.py` reproduces the sole overlay and `patch.diff` from the vendored exact original. The source checker reconstructs every original byte by removing the one flag/export and restoring the setter tail.

Apply only to an independently deep-copied official runtime, using canonical paths:

```sh
python3 scripts/apply.py --runtime-root "$CLONE" \
  --target "$RESOLVED_DATA_INTERVAL_MAP" --confirm-disposable-copy
```

The applier rejects a wrong preimage, altered support module, unreviewed overlay, symlink/escape or hard-linked source. It atomically replaces only the target, preserves its file mode, and verifies its new hash. The same command with `--revert` restores exact original bytes. Idempotence does not bypass path or support checks. Recompile the actual selected runtime in its isolated compiled-cache/profile before using the candidate; do not rely on stale bytecode.

## Correctness before timing

Run the actual-Racket differential gate in fresh processes with the flag unset, `0`, and `1`. The CLI is:

```sh
racket tests/interval-map-differential.rkt "$STOCK_MODULE" "$CANDIDATE_MODULE" off
OPENRACKET_INTERVAL_MAP_FAST_SET=1 racket tests/interval-map-differential.rkt \
  "$STOCK_MODULE" "$CANDIDATE_MODULE" on
```

`tests/README.md` details 1,200 deterministic mixed operations, complete bounds/order and point queries, overlap/adjacency, invalid intervals, deletion/shifts, custom contracts, mutable identity, callbacks/exceptions/reentrancy and retained iterators. The suite verifies Racket 9.3 and the actual selected module exports; any mismatch raises and exits nonzero.

The reused native monitor/go gate captures complete typed traces and genuine rename answers in stock, stock-again, candidate-off and candidate-on processes:

```sh
racket tests/native-trace.rkt --mode stock --runtime-root "$STOCK_CLONE" --output stock.json
python3 tests/compare-trace.py --help
```

All original handler/traversal/xref sources remain pinned. The bounded completed-annotation comparison preserves every duplicate, source association, documentation value, order-sensitive consumer effect and five real rename-query answers per endpoint. Raw producer order remains an explicit diagnostic because stock itself changes that order. See `tests/TRACE-SEMANTICS.md`; this gate alone does not establish GUI application behavior.

A separate genuine retained-host Check Syntax process reads the actual editor's complete documentation map through a source-pinned, read-only accessor in the already-instantiated blue-box module. It compares stock/candidate-on intervals, typed tags/paths/anchors, exact `end+1` geometry and retained editor/source identities. This uses the existing real callback and READY/screenshot handshake. The small native GUI smoke uses fresh stock 128 MiB settings; it is distinct from the 256 MiB timing workload.

## Measurement contract and current status

Only after all correctness gates pass may six interleaved fresh stock/candidate GUI trials run at the same verified 256 MiB setting. Both arms must keep the same common observation/heartbeat, fixture, settings and stock tools. Producer phase points remain off. Actual current annotation application, clean successful monitor/terminal output, final source and lexer validity are mandatory endpoints. Application elapsed time includes interleaved work; cumulative allocation counters are neither retained RAM nor per-function ownership.

The first native run passed all three actual Racket differential modes (1,280 operations and 336,852 assertions each), four real handler trace captures and the bounded semantic comparison. Both telemetry helper suites passed 82 tests with zero skips. The real documentation-map postflight stopped on the same test-only handler-identity assumption in both arms, so timing did not run. See reports/NATIVE-CORRECTNESS-38119983626.md. The reviewed repair verifies actual failed-check propagation instead. Documentation-map acceptance and measured benefit remain pending; do not enable this candidate by default or describe it as a speedup.

## Frozen local validation

The repaired complete Python/source suite passes 118 checks, including deliberate rejection cases for the actual GUI documentation-map schema and boundaries and exact two-substitution repair scope. The original native map and telemetry gates passed as recorded above. The new standalone native failed-check regression and repaired docs postflight remain unrun. Run the regression directly with `racket tests/rackunit-failure-propagation-test.rkt`; deliberate failed checks are its inputs, so do not wrap it with raco test. Its separate eventspace has a ten-second wait and custodian cleanup. All gates must pass before timing.
