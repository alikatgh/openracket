# Experimental one-shot Check Syntax documentation replies

This default-off Racket 9.3 experiment changes only the private reply transport in
`drracket/private/syncheck/xref.rkt`. It is separate from the delivered Mac preview.
No native compilation, output equivalence, allocation reduction or speedup is
claimed by the current local source checks.

## Why test this

The Mac phase probe in run [38102050130](https://github.com/alikatgh/openracket/actions/runs/38102050130)
reached Check Syntax's real traversal and stopped with the existing 128 MiB
out-of-memory terminal. The last live monitor samples were in `document-variable`.
Those are approximate contexts, not proof of allocator ownership. That function
can also be waiting for the unsampled documentation service.

Exact source shows that the service already caches documentation lookup results,
including misses, but starts a fresh reply thread for every request, including a
cache hit. The experiment replaces each reply channel/thread with a private box
and one readiness semaphore. The same persistent service performs the same
lookup and cache operation, stores the original result object and posts once.
No caller wait is introduced in the service.

The original caller `sync` and `nack-guard-evt` remain. Accepted requests still do
their original lookup even if the caller is canceled. An abandoned result cell
can be collected after the caller/service release it. No syntax, trace, docs-menu
callback, label, rename capability or cache entry is suppressed or duplicated.

`OPENRACKET_XREF_REPLY_CELL=1` enables the candidate at module initialization.
Other values and an unset flag retain the original branch. The additional
read-only export `openracket-xref-reply-cell-enabled?` exposes the selected branch
for tests. Both caller and service share that one immutable selection.

The existing `flush-index-entry-cache` body is byte-identical. It constructs a
channel-put event without synchronizing it; this experiment does not silently
repair that separate source-level issue. Service-death and lookup-exception
behavior are also unchanged, including stock's possible mid-request wait.

## Reproduce and apply only to a disposable copy

Use a full official [Racket 9.3 distribution](https://download.racket-lang.org/releases/9.3/).
Keep the original installed runtime unchanged. CI makes independent deep copies
and verifies the full original runtime tree before and after all work.

    python3 scripts/prepare.py
    python3 -m unittest discover -v -s tests -p 'test_*.py'

Resolve the target from the selected copy's actual collection search path. Supply
canonical absolute paths, including resolving macOS temporary-directory aliases.

    python3 scripts/apply.py --runtime-root "$COPY" --target "$XREF" --confirm-disposable-copy

The applier checks exact original and replacement byte hashes, the collection
suffix, containment, and absence of symlinks/hard links before an atomic write.
Use the same command with `--revert` to restore the pinned upstream bytes. Rebuild
the actual affected modules with the copied runtime before native execution.
This source applier does not install packages or run setup implicitly.

## Acceptance before measurement

- Stock, patched-default-off and enabled actual-form service tests must preserve
  result identity, cache misses/hits, serial lookup and directory context.
- Concurrent, suspended, killed and broken callers must not block the service or
  retain reply objects. Native tests must prove responder-thread elimination.
- Real exported Check Syntax `monitor` and `go` must produce equivalent complete
  traces on successful documented-binding fixtures. Positive docs-menu controls,
  repeated occurrences and actual rename-channel replies are required.
- Exact source pins, actual worker activation, settings, registry and terminal
  outcomes must be observed in the matched GUI workload. Lexer readiness alone
  cannot stand in for successful background expansion.
- Keep the stock 128 MiB job limit, 20 ms coloring budget, appearance and tools in
  both arms. Do not activate the scan, autosave or color-budget experiments.

Native test commands, using the executable of each selected disposable runtime:

    "$RACKET" -l raco make tests/independent-reply-test.rkt tests/native-trace.rkt
    "$RACKET" tests/independent-reply-test.rkt

The service suite executes 54 named cases over the actual stock/off/on source
forms with deterministic injected lookup primitives. It is headless. The real
documentation/handler gate runs four fresh processes and profiles:

    "$STOCK_RACKET" tests/native-trace.rkt --mode stock --runtime-root "$STOCK_COPY" --output stock.json
    "$STOCK_RACKET" tests/native-trace.rkt --mode stock --runtime-root "$STOCK_COPY" --output stock-again.json
    "$CANDIDATE_RACKET" tests/native-trace.rkt --mode off --runtime-root "$CANDIDATE_COPY" --output off.json
    OPENRACKET_XREF_REPLY_CELL=1 "$CANDIDATE_RACKET" tests/native-trace.rkt --mode on --runtime-root "$CANDIDATE_COPY" --output on.json
    python3 tests/compare-trace.py stock.json stock-again.json off.json on.json

Unset the experiment flag for the first three captures. The actual trace gate
requires installed official documentation, positive repeated documentation
annotations, complete ordered traces and live rename-channel answers. Only
path-valued descendants of verified installation/fixture roots and genuine
channel identities are normalized. Labels, definition tags, anchors, all other
values and duplicate entries remain. A differing stock-to-stock control blocks
candidate interpretation rather than silently sorting the trace. Default bounds
are 30 seconds per fixture and 180 seconds for the suite; CI supplies an outer
process bound and unconditional cleanup. Actual native compilation/execution is
still unrun at this local freeze.

CI also exercises the existing real-host Check Syntax case in stock/on modes.
All native gates precede Mac timing. An allocation or latency change that
still ends in OOM must be reported with that limitation; this is not yet adopted.

## Provenance and local scope

The unmodified source, upstream notice, package license declaration and full
distribution license texts are in `vendor/`. `manifest.json` pins exact source
and candidate bytes; `patch.diff` contains every modification. The independent
source review is in `reports/INDEPENDENT-SOURCE-REVIEW.md`.

This local environment has no Racket executable or permitted graphical display.
The Python source/integrity checks are runnable here; Racket/native checks require
the separately authorized standard public CI environment. Source-only success
must not be described as a running application or completed parity proof.
