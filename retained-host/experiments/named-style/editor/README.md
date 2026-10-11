# Named-style index: small native editor correctness gate

Current derivative: see [REGISTRY-REPAIR.md](REGISTRY-REPAIR.md) for the source-backed
fresh-eventspace registry repair established by run38159705157's saved bytes.
50 portable methods pass ordinarily and under an explicitly aliased TMPDIR.
The repair's native controls and complete editor/WXME gate await official Mac CI.
Failure-only observability from [RELOAD-DIAGNOSTIC.md](RELOAD-DIAGNOSTIC.md) remains.


## Search-scope repair after run38153992371

This is a separately prepared editor-test derivative of the frozen 14:02
composition. The historical native run failed in all four arms at the same
fixture assertion, `Unicode string exists at actual editor position`, after
initial token readback and before any edit or rich/WXME operations. The original
capture did not record the returned target or selection; a `#f` result follows
from the documented API contract and failed integer predicate, but is not a
raw logged value. No candidate defect or successful editor/WXME gate follows.

The pinned public `text%` documentation says that `find-string` defaults to a
forward search from the current selection and that insertion moves the selection
to the end of the inserted text. This derivative explicitly searches from
character position 0 to EOF. It requires the returned position to equal the
source-derived offset 31 and requires the actual three-character range to equal
`"λ"`. It captures bounded query, selection, length, target and range evidence
before assertions. Actual native negative controls require both the original
cursor-relative search and an explicit EOF search to miss the earlier string,
and require a whole-document absent query to return exactly `#f`.

The new `fixture_search` evidence is strictly typed and compared across all four
arms. Every earlier downstream lexer/style/parenthesis/WXME ordered comparison,
deadline, callback policy, production candidate byte and telemetry byte is
unchanged. The only other native change records the already-completed initial
snapshot before the search, so a later search failure retains it. The original
diagnostic sampling locations are preserved. No other non-vendored `find-string`
call exists in the frozen experiment. The single default-scoped call in this
derivative is intentional negative-control coverage.

This derivative passed 36 portable test methods (including delimiter lint,
synthetic typed mutation checks and mocked process checks). It has not been
compiled or executed natively. Historical evidence and exact source/doc hashes
are recorded in `SEARCH-REPAIR.json`; `reports/portable-tests.log` remains the
inherited 31-method preparation log, and `reports/search-repair-portable-tests.log`
is the derivative's 36-method log. A fresh official Mac CI run remains mandatory.

## Original fixture contract, retained below

**Prepared, source-reviewed, not natively executed.** This package is separate
from the default-off named-style candidate. No Racket installation, Racket
execution, package/archive download, remote publication, preview change, or
performance measurement was performed while preparing it.

The candidate remains a lookup-only experiment in the actual official 9.3
racket/snip/private/style module:

- stock SHA256: 2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0
- candidate SHA256: 74eb24f0d6485187c9700cca421f4299dee67ea092a811d56b737972b2204c6d
- activation: OPENRACKET_NAMED_STYLE_INDEX is enabled only by the exact 1
- diagnostics: read-only openracket-named-style-index-state on the editor's
  **actual existing style-list object**, never a replacement proof instance

## Distinct coverage

This is an actual **framework Racket editor** fixture, not a full DrRacket tool
workflow. The separate large GUI gate owns full background analysis, trace
application and six-trial native timing. Candidate owner tests cover named-style
mutation, notification/reentry, duplicate winners and cache publication faults;
this package does not replace or duplicate that style-only differential suite.

Four independent native processes are mandatory, in order:

1. Stock official runtime, flag unset.
2. Stock again in a second fresh profile.
3. Patched runtime, exact flag 0.
4. Patched runtime, exact flag 1.

Each creates a genuine eventspace, frame, editor canvas and public framework
racket:text%. That official class installs the real Racket mode, module lexer,
token-to-style mapping and parentheses. There is no hand-written colorer,
token source, substituted style implementation or synchronous tokenization
shortcut in the native harness.

The small source contains a Unicode identifier/string, definitions, a comment
and parentheses. A normal editor edit replaces the three-character "λ" token
(including quotes) with [1 2]. The gate requires actual invalidation, normal
queued recoloring, revalidation, exact source readback, every position's token
range/class/style, and the complete ordered public forward/backward navigation
graph. It asserts the real string/parenthesis/constant style names and bracket
coordinates.

The framework editor retains its existing style list. Snapshots retain **every
style in public index order**, including unused styles, exact per-position/snip
indices into that list, names, base/shift edges, all delta fields and observable
font/color/alignment attributes. These indices are not first-seen presentation
IDs. Nothing sorts or discards styles, snips, flags, positions or graph edges.
If ordinary framework startup ordering differs between the two stock processes,
acceptance stops with the exact field path; do not normalize the difference
away or call either candidate comparable.

## Rich/WXME fixture

A separate plain text% fixture uses the documented set-style-list operation
to install a small controlled list. This is explicitly different from the
framework editor's existing list. It includes:

- repeated aliases of fixture:深蓝λ, a second named underline style and a join
  style, with explicit foreground, font-size and weight attributes;
- ordered string content, one 3 by 2 bitmap with all 24 exact ARGB bytes, one
  embedded editor with "nested λ café", and trailing text;
- a shared outer/nested style-list identity, explicit border margins/insets and
  width/height constraints.

The fixture is displayed, saved with the public 'standard format and loaded
into a fresh editor/list. The file must actually contain a WXME header and stay
below 256 KiB. The complete file is retained. Saving must preserve the existing
snip, style, bitmap and nested-editor objects by eq?. Reload necessarily creates
new objects: the typed comparator instead preserves the complete ordered
style-index/alias graph, snip kinds/order/content, nested shared-list
relationship, attributes and pixel/geometry values. It never claims that
reload objects are the pre-save objects.

The only numeric equivalence allowed is equal finite real values in documented
real-valued fields, such as a serialized 40 becoming 40.0. Integer identity,
position, size-count and pixel fields remain typed integers. A boolean can never
stand in for index zero or one. JSON object key order is not semantic; all
ordered arrays are compared position by position.

## Runtime identity, cold work and scheduling

native/bootstrap.rkt resolves and hashes the real installed style module
within an explicitly supplied runtime root **before GUI import**. It initially
loads that module with compiled paths disabled, so stale .zo bytes cannot
stand in for the pinned candidate source. This source-first startup is solely
a correctness measure, never ordinary-startup performance evidence.

The GUI must reuse the already-loaded phase-zero module namespace. The actual
editor list must be is-a? compatible with both public and private style-list
classes; public contracted class exports are not required to be eq?. Candidate
diagnostics must work on that same list. Missing stock exports are distinguished
only by dynamic-require's explicit missing-export thunk; source, loading and
namespace failures remain failures. Five official GUI dependency sources are
also pinned and must already be instantiated after framework import.

Diagnostics are sampled before insertion, after initial lexing, after the edit
and after the final normal GUI yield. Initial and edit work must each increase
real lookup/hit counters in enabled mode. Rebuild/member-visit totals are kept.
There is no synthetic named lookup or prewarming for this evidence. A final
cache-valid value of false is retained, **not rejected**: a last anonymous
style insertion can legitimately make the cache stale. Disabled mode must
perform no index work.

The normal GUI dispatcher and stock callback priorities are preserved. A fresh
eventspace retains and reports asynchronous callback errors through its normal
error-display handler. All callback errors fail acceptance. Polling yields
normally and has one 30-second absolute workload deadline, with a 40-second
handler-completion bound and a 180-second outer process bound including startup.
The last yield is followed by fresh source/lexer/rich-document readbacks.
No further grace period, busy loop, freeze/thaw or worker policy change is used.

## Files and explicit future execution

- native/bootstrap.rkt: source/namespace/activation check, full failure report.
- native/editor-gate.rkt: genuine GUI edit and rich save/reload operations.
- native/snapshot.rkt: ordered public-API graph/content snapshots.
- scripts/compare.py: typed schema and exact meaningful four-way comparison.
- scripts/run_native.py: authorized-only process runner, never an installer.
- PROVENANCE.json, vendor/: exact individual official source/document bytes.
- tests/: Python static checks, synthetic comparator records, mocked process
  tests. These neither run nor emulate the native GUI/lexer.
- reports/portable-tests.log: completed portable checks only.

After fresh native authorization and independently preparing separate disposable
official stock/candidate runtime trees using the candidate owner's applier:

    python scripts/run_native.py --stock-racket /canonical/stock-runtime/bin/racket --stock-root /canonical/stock-runtime --candidate-racket /canonical/candidate-runtime/bin/racket --candidate-root /canonical/candidate-runtime --output /new/empty/evidence-directory --authorize-native-execution

Paths must name existing canonical native executables and disjoint runtime
roots. A real native GUI display is required. The runner makes fresh disposable
profiles and refuses inherited experiment flags, alternate collection/compiled
resolution, debug resolver and profile/XDG overrides. It never patches a runtime,
downloads/installs a package, modifies an existing evidence directory or
publishes anything. The command-line interlock is not a substitute for user
authorization.

Every process retains full binary stdout/stderr, process/command/timeout/exit
metadata, partial or complete native JSON and its complete WXME file when
created. A timeout, launch refusal, failed arm, missing evidence or comparison
mismatch blocks acceptance. Independent arms continue so their failure details
are not lost. All failure tracebacks are retained; there is no successful
fallback for an unrecognized exception. No speed claim follows from this gate.

Portable validation:

    python -m unittest discover -s tests -v

Racket delimiter lint is **not** compilation, expansion, native execution or GUI
correctness. Actual native stock/stock-again/off/on reports are still required.
