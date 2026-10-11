# New source/navigation contract revision from committed 1021

This is a new immutable source revision, not recovery of the lost 1108 freeze.
Frozen root: `/workspace/scratch/5923f1aa2055/openracket-native-tool-gates-freeze-20261011-1125`. Its exact
baseline is the restored committed `retained-host/experiments/native-tool-gates`
from publication 41. All 37 baseline manifest members were verified against
`445e1d57732741ebb0331a88234d42540b2f2ea37897a1c5b4be5676a5edbc87` before copying.
Source/API review and Python checks do not establish Racket compilation or native
acceptance. No local Racket execution, package installation or remote action was
performed by this repair worker.

## Actual run 38133153111 evidence

The restored native log and four READY reports were reread; the two failed-tool
screenshots were inspected directly.

- Debugger log line 537 records a genuine entry-break at installed
  `racket/private/pre-base.rkt:201:40`, position 8507, span 14, PC 8507 and frame
  endpoints [8507,8520]. Both source/editor resolution booleans are false.
  The typed RackUnit failure is the original `defs-containing-pc` identity check.
  The screenshot shows enabled real Go/Step and an unresolved stack label `??`.
- Teaching fails the original editor identity check after the actual source-link
  clickback. Its screenshot shows a second `fixture.rkt` tab and cursor 1:0,
  without the expected source selection. Accepting a different editor alone
  would therefore discard actual navigation coverage.
- Real stock and modern-dark Macro Stepper pass navigation, normal close and
  ordinary Run recovery. Those passes do not certify Debugger or teaching tests.

The pre-base startup cause is observed evidence. The teaching `/var` filesystem
alias explanation remains a source-supported hypothesis: the prior run did not
record raw/canonical link-source and frame lookup results. New telemetry must
confirm or reject that hypothesis; exact navigation remains mandatory either way.

## Fresh official source verification

`official-source-provenance.json` copies the seven individually recovered,
version-pinned official source records. Their complete local bytes were checked
against those SHA-256 values before this review. DrRacket and drracket-core-lib
are pinned to `1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6`. The official GUI v9.3 tag
resolves to `6f0213fa0535d87dd4e35f56c8266d948c8c089e`.

Debugger:

- `gui-debugger/annotator.rkt:234–254` instruments eligible expanded expressions
  with source positions, without restricting them to the fixture filename.
- `gui-debugger/debug-tool.rkt:778–794` allows single-step stops even when the
  source does not resolve to an open editor. Lines 910–926 resolve actual top and
  current marks to definitions; lines 928–947 derive PC and frame endpoints from
  syntax position and span. Lines 1464–1474 implement the actual Step button by
  enabling single-step and resuming.

Teaching navigation and retained tabs:

- `framework/private/group.rkt:182` exports the actual frame list;
  lines 266–282 normalize the source filename before querying editing-this-file?.
- `drracket/private/unit.rkt:3449–3458` converts string sources to paths before
  port-name-matches?. `framework/private/text-basic.rkt:572–581` uses lexical
  simplified paths, so filesystem aliases need not compare equal.
- `framework/private/handler.rkt:97–111` forwards start/end positions only through
  already-open → make-visible. The new-file fallback drops them.
- `framework/private/srcloc-snip.rkt:20–27` invokes the real handler with
  position−1 and position+span−1. The unchanged failed form starts at position 78
  with span 25, requiring editor selection [77,102].
- `drracket/private/unit.rkt:1269–1270` exposes the retained tab's get-defs/get-ints.
  Its existing get-tabs API enumerates tabs; change-to-tab at 3158–3202 restores
  definitions/interactions and their real canvases. New-tab handling at 5906–5935
  explains how the fallback can produce the observed second tab.

## Narrow correction

Canonicalize the existing temporary parent directory before file creation/loading
for Debugger and teaching only. The already-passing Macro Stepper retains its raw
fixture path and complete case-branch bytes.

Debugger starts one monotonic 20-second deadline before real Debug launch. Each
initial actual suspension is recorded, including raw/canonical fixture path,
actual mark source and canonical source, line/column/position/span, PC/status,
frame endpoints and source/editor resolution. Until both top and current marks
identify valid fixture spans, use the shown/enabled real Step control and await
an actual changed stop with only the remaining budget. Diagnostic-only changes
cannot count as progress. Unresolvable/non-path generated sources normalize to
#f and cannot be accepted as fixture source. At the accepted fixture stop, the
original assert-source! block runs unchanged, including both definitions identity
checks. The original subsequent meaningful Step, focus, Go and ordinary Run
recovery keep their separate 20-second waits. External 60-second process bounds
remain unchanged.

Teaching records the actual link-source type, raw and canonical filename,
registered frame, raw/normalized port-name matches and actual locate-file result.
The guarded string-to-path conversion follows stock unit.rkt. Require lookup to
the already-open frame before invoking the unchanged nested srcloc-snip clickback.
Record the actual destination's filename, canonical filename, full contents,
selection, visibility, canvas/editor match, identity and tab count. Require exact
fixture file, complete fixture contents and [77,102], then verify the selected
form. Editor object identity alone is not the navigation criterion. Only after
those checks, restore the original retained tab and run all original unsaved
one-character correction, real Run, evaluator 2/2/0 and stale failure/link rejection
checks.

## Refusal controls, preservation and limits

`native-tool-source-contract.rkt` is GUI-independent validation shared by actual
observations and the mandatory direct standalone regression. Explicit synthetic
records appear only in refusal tests, never as native-tool evidence. They reject
wrong canonical source, line, column, position, span, PC, frame endpoints,
unchanged stop and diagnostic-only changes; wrong destination file/full contents,
[0,0] or off-by-one selection, hidden frame or mismatched canvas; malformed, negative, empty, reversed or
out-of-range expected selection bounds; exhausted budget;
and unresolvable/non-path sources. A real temporary-directory symlink tests path
alias normalization. A first-character span tests line/column boundary handling.

Complete Macro Stepper branch SHA-256 remains
`0cf56eac6c88e29d530c21fa8cafacb1ece3d453e12fcab4a44545242548d83d`.
Original Debugger assert-source! SHA-256 remains
`172b71fbec2ff99f285eea1d68bf9be97dd1bb77726e9e0b89eb377e54aca882`.
Thirteen source files, including host/derivation, all coordinator/dispatcher
modules and both typed-diagnostics modules, are byte-identical to1021. Only the
stock-tool driver, two new source-contract modules and its Python source checks
changed. No product/runtime source changed.

Typed diagnostics retain their existing limitation: the 2,000-character value cap
truncates after format, so arbitrary custom-writer work is bounded only by the
existing external native timeout.

Current review diff: `SOURCE-REBUILD-REVIEW.diff`. Exact source pins and unchanged
members: `source-rebuild-evidence.json`. Local validation:
`final-source-checks.log`, 27 Python checks (13 stock, 8 dispatcher, 6 coordinator)
and exact host derivation. These include lexical delimiter checks, not Racket
compilation. Current eleven-file reader/compile/native handoff is
`NATIVE-CLI-CONTRACT.md`.

The new direct standalone command is
`racket tests/native-tool-source-contract-standalone.rkt`, mandatory under the
existing 30-second headless supervisor. Require exit 0 and exactly one
`OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals`.
Retain every existing coordinator/dispatcher/diagnostics positive and injected
negative gate. No standalone/source pass substitutes for a genuine native pass.

Final source/API review approved the exact source pins in
`source-rebuild-evidence.json`, including strict expected-selection bounds and
their refusal tests. Root `FROZEN-NATIVE-ALLOWLIST.json` is the current eleven-file
native integration allowlist. Reader, compilation, standalone execution and
actual native tool acceptance remain pending.
