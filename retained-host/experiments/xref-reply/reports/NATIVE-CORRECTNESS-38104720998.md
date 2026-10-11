# First xref reply candidate native run

Source: `9c5c689530787e03ce5a69a15fd0b6ec1127d229`.
Run: [38104720998](https://github.com/alikatgh/openracket/actions/runs/38104720998),
standard macOS runner. The job failed its correctness phase; timing did not run.

## Verified outcomes

- Actual official 9.3 modules and native callers compiled.
- Actual-form service suite: 51 successes, three failures, zero errors. The
  same deferred-break test assertion failed in stock, patched-default-off and
  enabled modes. Each lookup returned its correct value; the immediate
  completion notification arrived before the test expected the deferred break.
- All four real `monitor`/`go` captures completed, with five fixtures each.
  Stock, stock-again, off and on each produced the same per-fixture counts:
  78/62/81/145/70 complete annotation entries, 14/11/15/19/12 documentation
  annotations, and 100/75/90/190/80 observed rename replies. Counts alone are
  not an output-equivalence proof.
- Exact ordered comparison rejected the pristine stock-to-stock control.
  Entire annotation groups and their subsequently assigned request IDs vary
  across fresh processes. Candidate equality remains blocked pending a
  source-backed comparison that preserves all observable associations.
- Both genuine stock and candidate-on DrRacket Check Syntax host cases passed
  20 assertions.
- All 26,838 entries of the original runtime, including compiled files,
  remained unchanged. No Actions artifacts were uploaded.

## Next bounded repair

Make deferred break delivery deterministic at an explicit break-enabled wait,
while retaining the successful disabled-break result assertion. Independently
review stock trace construction and GUI consumption before changing comparison.
Keep original ordered traces intact, preserve multiplicities and exact docs
values, and validate rename replies against their logical source annotations.
No production transport change is justified by these two observations alone.

## Reviewed test repair

The deferred-break test now uses an explicit `sync/enable-break` checkpoint
after recording the valid result. A missing pending break still fails its
bounded wait. The test also verifies the identical cached object and single
lookup afterward; native execution of this revision remains pending.

The new bounded comparison passes all four unchanged captured documents. It
requires a complete duplicate-bearing annotation inventory, each actual rename
answer attached to its original logical event, and exact order-sensitive docs,
menu, tooltip and navigation state. Only homogeneous require arrows sharing
the identical source range may permute. The original exact comparator remains
available and still fails on the pristine control; raw order and arrow painting
differences are always reported explicitly. See `tests/TRACE-SEMANTICS.md`.

All 44 local Python checks pass, including 22 deliberate semantic-comparator
mutation tests. This establishes the bounded completed-annotation contract for
these five fixtures, not deterministic transient rendering or full parity.

The current source has no measured speed or allocation result.

Log SHA256:
`3c29c934736583b7105a2bdea4547aa4e79d2f7ff2efd27ba85a1d136579918b`.
All four decoded trace documents were verified against lossless transport
digests before review.
