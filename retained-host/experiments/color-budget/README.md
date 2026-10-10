# Isolated cooperative coloring-budget experiment

Prepared for evaluation after the separate string-snip scan experiment. It has
not been installed, natively tested, or measured. No speed benefit is established.

## Exact change

`prepare-budget.py` verifies the official Racket 9.3 gui-lib `color.rkt` SHA-256,
adds one immutable module-level budget constant with a read-only diagnostic
export, and replaces the single `20.0`
threshold in the existing deferred-yield test. Unset is exactly 20 ms. Explicit
experimental values are 4, 8, 12, or 20 via
`OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS`; other values are rejected. The first
proposed comparison is stock 20 versus experimental 8, not a sweep.

All other source bytes are preserved. The `ok-to-stop?` gate, the lexer’s
`dont-stop` continuation handling, tool overrides of `tokenizing-give-up-early`,
lexer state/token-tree reuse, classification/styles, spell checking, region
handling and event scheduling are unchanged.

This is a cooperative token-boundary budget. It cannot preempt a single lexer
call, a lexer’s don’t-stop request, an edit-sequence completion, or garbage
collection. Smaller slices can open more editor ports, perform more snip scans,
queue more callbacks, allocate more, and make total coloring slower. In the
existing diagnostic run, the median colorer callback was 21.37 ms, but the worst
5.61-second callback overlapped 5.606 seconds of major GC. An 8 ms budget cannot
be assumed to fix that worst stall.

## Local preparation and checks

```
python3 scripts/prepare-budget.py
python3 -m unittest discover -s tests -p test_source.py
racket tests/budget-test.rkt
```

Two source-preservation checks and four headless behavioral test cases pass.
They execute the actual parsed configuration and stopping predicate. They cover
exact thresholds, invalid configuration, explicit tool true/false overrides,
and preservation of the don’t-stop gate even after a long lexer call. They do
not prove native GUI or whole-lexer behavior.

The candidate is `overlay/framework/private/color.rkt`; its manifest and diff
are in `reports`. The upstream package catalog checksum is pinned as well.
Nothing in these scripts installs a package, changes a stock distribution,
launches a display, or writes a remote repository.

## Required native gate before timing

Use disposable official full-9.3 stock and candidate runtimes. Keep tools,
preferences, language settings, 128 MiB child limit and online compilation equal.
Verify pristine source hashes remain unchanged. Run the existing core/feature
preservation suite, then compare stock versus candidate final lexer validity,
per-position token classes/ranges, parentheses, and complete style spans for:

- Mixed ASCII and Unicode, comments, strings, regexp, quasiquotes and edits
- A long lexer call and a stateful lexer returning don’t-stop continuations
- Edits while a queued coloring slice is pending, including insert/delete/undo
- Rich snip/WXME and nested-editor content on the unchanged general path

Visible color completion may progress in smaller steps, but final results and
source text must agree. Failures are not acceptable tradeoffs for lower timings.

## Common measurement extension

`prepare-observability.py PATH/retained-host.rkt` retains the preparation history
for `reports/benchmark-observability.patch`. This common extension has since been
applied to both arms of the separate scan experiment; its generator remains
pinned to the older pre-extension source and must not be reapplied blindly.
It adds read-only
cumulative/peak managed allocation counters to existing snapshots, logs both
experimental flags, measures open-to-initial-lexer observation time (including
the same intervening jump/edit), and measures the 80-event warm input phase.
The generated full source is a review artifact, not a standalone launcher; its
settings/diagnostics peers still come from the common benchmark directory.

Keep full raw records. For each trial compare:

1. Synchronous open/jump/edit and initial lexer readiness, including the complete
   open-to-readiness interval. A failed 45-second lexer gate remains a failure.
2. Warm key command and queue-fence median/p95/p99/max, per-event records, and
   phase-specific heartbeat dispatch delay and callback gaps. Warm-input phase
   throughput includes the unchanged 16 ms synthetic pacing and is labeled so.
3. Total initial/final lexer settling and successful final validity, not just
   lower input fences. Same text size does not mean the whole workload finished.
4. GC CPU deltas, cumulative allocation deltas before-open → initial-ready and
   initial-ready → after-warm-input, managed live/peak memory and native peak RSS.
   Managed counters are runtime-wide estimates, not allocation ownership proof.
5. If needed, a separate logger-only or sampled attribution run for callback
   count/GC intervals. Diagnostic timings must not be mixed with ordinary trials.

Use the same harness, fixture hashes, process count and runtime/preference setup
in each pair, initially Linux 1 MiB and three fresh processes per arm. Do not
compare against old records from a different harness. Keep scan activation fixed
and explicit on both sides; the first budget-only test should leave it off.
If a validated scan optimization later becomes the common base, measure 20 versus
8 with that same scan version active on both sides. Never credit a combined
uncontrolled change to the budget alone.

Existing supervisor command, after common instrumentation/native gates:

```
python3 performance/run.py --mode MODE --racket RUNTIME \
  --output reports/budget-MODE --fixture mixed-1mib --repetitions 3 --timeout 60
```

The CI owner controls approved execution, source publication and cleanup. This
preparation does not authorize or schedule another native run.

## Separate typing-during-coloring workload

`scripts/prepare-contention.py PATH/performance` builds the isolated `contention/`
launcher from the exact frozen scan harness. It does not modify that source or
install the budget. This new workload is labelled `initial_coloring_typing` and
must be compared only against another arm running the identical new workload.

After synchronous load, the same first jump and first comment edit, it sends 80
additional comment characters before waiting for initial lexer readiness. An
off-GUI producer queues one high-priority synthetic callback at a time, waits for
completion, and sleeps 16 ms before its next request. Each callback records:

- Queue submission to GUI-handler dispatch
- Editor `on-char` command duration and queue submission to editor completion
- Command-to-low-priority-fence and queue submission to that fence
- Producer scheduling lateness against its next 16 ms deadline, and that deadline
  to editor completion/fence, so a GC pause before enqueueing is not silently lost
- Actual lexer-valid state before and after each key

This is a closed-loop paced synthetic editor workload, not an independent
hardware input stream, OS keyboard injection or physical input-to-photon
measurement. One outstanding request avoids backlog but permits
coordinated omission beyond that one planned request; separate heartbeat gaps
remain essential. A budget cannot
preempt GC or a long individual lexer call. The callback’s lexer-valid reads and
extra timestamps add equal instrumentation overhead to both arms.

The final exact source is checked against the fixture plus the intended 81
inserted comment characters, after timed phases. Completion requires the stock
lexer to become valid within the unchanged 45-second gate after typing. Report
the whole open-to-completed-workload interval, post-typing wait, paced typing
throughput, per-key tails, number of keys starting while lexer-invalid, GC CPU
and cumulative allocation deltas, managed memory and native peak RSS. Neither
lexer validity nor this gate proves background expansion completion.

Prepared command contract (native execution remains with the CI owner):

```
python3 contention/run.py --mode BUDGET_ARM --racket RUNTIME \
  --output reports/budget-contention/BUDGET_ARM/pair-1 \
  --fixture mixed-1mib --repetitions 1 --timeout 60 --budget-activation EXPECTATION
```

Use fresh, interleaved matched processes. Both arms have identical appearance,
tools, preferences, fixture and language metadata. Start with budget unset versus
8 ms and scan unset on both sides, unless a separately validated scan version is
deliberately the common base. This workload replaces settled-input/jump sampling
for this specific comparison; it does not overwrite the ordinary records.
Set EXPECTATION to `stock` in the pristine arm and `8` in the candidate arm.
Each process checks both the environment flag and actual loaded color-module
export (absent in pristine stock, exactly 8 in the candidate); the CI installer
must separately pin the resolved module source hash. Reject a contention
comparison if any trial has zero keys starting lexer-invalid, incomplete final
coloring, unverified activation, mismatched settings or incorrect final source.

## Shared native lexer-equivalence gate (prepared, native run pending)

`tests/native-lexer-equivalence.rkt` is usable for the narrowed scan candidate and
later budget candidate. It uses the actual shown DrRacket definitions editor,
not a reconstructed class. Its separate `color:text%` stateful-lexer case is
explicitly outside the scan-only definitions substitution. It never sets an
optimization flag or changes preferences.

Each fresh process requires `OPENRACKET_LEXER_OUTPUT` for its JSON file and an
optional `OPENRACKET_LEXER_MODE` label. Pass no Racket process arguments beyond
the script path. Use the CI supervisor's 60-second outer bound; each native lexer
wait is bounded to 10 seconds and initial frame readiness to 20 seconds. Partial
cases and errors are preserved, and failures exit nonzero. Full per-case data and
summary are printed with `OPENRACKET_LEXER_CASE_JSON_BEGIN/END` and
`OPENRACKET_LEXER_SUMMARY_JSON_BEGIN/END` markers.

Eight cases cover the real definitions editor before/after Unicode comment
insertion, deletion, undo and redo; a string token invalidated into malformed
syntax and restored; and an independent Framework stateful lexer using the
stock Racket lexer with long calls and `dont-stop` groups. Every mutation awaits
fresh, stable lexer validity and expected exact text. Restoring text must restore
all previous token/parenthesis/style observations within the same process.

Snapshots retain each position's token type/range, a normalized parenthesis
matching graph, and complete resolved appearance properties in normalized style
spans. Adjacent equal styles are merged so harmless snip fragmentation does not
confound the comparison. The custom stateful lexer checks that a `dont-stop`
group keeps its input port and cannot dispatch a queued GUI callback mid-group;
its deliberate delays are correctness stimuli, never performance samples.

Run each stock/candidate arm with identical appearance, fonts, preferences and
platform. The caller independently verifies exact source hashes and activation:

```
OPENRACKET_LEXER_OUTPUT=/absolute/stock.json OPENRACKET_LEXER_MODE=stock \
  "$STOCK_RACKET" tests/native-lexer-equivalence.rkt
OPENRACKET_LEXER_OUTPUT=/absolute/candidate.json OPENRACKET_LEXER_MODE=candidate \
  "$CANDIDATE_RACKET" tests/native-lexer-equivalence.rkt
python3 tests/compare-native-lexer.py /absolute/stock.json /absolute/candidate.json
```

The comparator rejects incomplete records, missing cases, unequal appearance or
preserved preferences, any `dont-stop` violation, or any positional token/paren/
style difference. A different intentional palette is not a valid precondition
for this gate. The source compiles headlessly; three comparator tests and three
actual-fixture reader/Unicode checks pass. These local checks do not count as a
native equivalence pass. Real rich-snip/port/WXME cases remain in the scan owner's
separate native suite; this shared harness deliberately uses textual lexer cases.
