# Independent fast-path lifecycle review

The generated private stock 9.3-derived mixin passes **17 GUI-free lifecycle tests** in
`tests/independent-fastpath-lifecycle-test.rkt`. These execute its actual parsed
class definition with a small mutation/contract model. They do not prove native
editor behavior or a speedup.

## Reviewed preservation hazards

- A rich snip becomes visible before `after-insert` finishes updating the stock
  cache. The guard therefore begins in `on-insert`, before inner callbacks.
- Stock insertion can reject a newly owned snip after `on-insert`, without an
  `after-insert`. An unmatched pending token conservatively disables the shortcut.
- An exception or other escape from inner `after-insert` can leave the stock cache
  at `#t` even though a rich snip was inserted. Permanent guard invalidation is
  necessary; simply balancing a counter would be unsafe.
- Callback kind/range matching and completed-on status prevent mismatched,
  repeated, and prematurely invoked after-hooks from certifying the cache.
- Continuation reentry invalidates the shortcut. Nested ordinary mutation keeps
  its outer guard until the original callback/cache sequence finishes.
- Only an existing stable `#t` is used. `#f` and `dont-know` go to the original
  method, without introducing virtual `find-first-snip` calls or extra scans.
- One-argument reflective arity remains unchanged; invalid argument values still
  reach the original contract path. String-snip subclasses match stock behavior.
- Native stock checks snip ownership with `object=?` before its empty-buffer
  check. Detached snips therefore raise a contract error, which must not become
  a false result. Argument eligibility now requires `#f` or an exact native
  string snip with a nonfalse stock `get-admin` field value. All detached,
  custom, subclass and invalid arguments use the original method. The actual
  editor-backed port starts from an owned string snip; the native counted test
  proves that argument still takes the shortcut.
- A custom string subclass can return a rich snip from `merge-with`; native
  selection/style operations can perform that merge without insertion/deletion
  hooks, leaving the original all-string cache at `#t`. The shortcut is therefore
  permanently excluded after a non-exact stock string class is encountered in
  the existing insertion walk, or after a mutation starts with rich/unknown
  cache history. Model regressions cover both silent merge and unexamined history.

The original `on-delete` callback calls its length argument `end`. This patch
preserves that body as written rather than mixing an unrelated change into the
experiment.

## Scope and remaining checks

The official definitions-editor composition places this mixin inside ordinary
DrRacket program-editor extensions (`drracket/private/unit.rkt`, lines 553–575).
Those outer extension overrides still execute. The experiment was narrowed to a
private DrRacket helper and one exact stock composition call. The public Framework
module is not an install overlay, and its generic mixin stays unchanged. Independent
tests verify exact original mixin selection when disabled, exact public interface
identity in both modes, and preservation of a custom superclass query through the
unchanged generic mixin. This removes the earlier broad-overlay compatibility
hazard rather than assuming arbitrary superclass overrides are interchangeable.

Native tests still need real editor insertion/deletion, rich and custom snips,
WXME, editor-backed input ports, and the actual lexer lifecycle. Paired native
performance trials must keep instrumentation and stock features identical.
No local native display execution was attempted.

`tests/independent-native-fastpath-test.rkt` now prepares fifteen real-editor
stock/private comparison cases for that next correctness gate. It asserts opt-in
activation, the real public interface and a counted exact-stock-string fast hit,
then checks a required native custom-string-to-rich merge, Unicode streaming ports,
foreign/detached/custom/string-subclass snips, image/nested specials, the actual pre-after-insert modified callback, reentrant
mutation and callback exceptions, undo/redo, WXME payloads and outer/generic
method dispatch. Serialization comparisons preserve text and rich bytes without
requiring incidental string-snip segmentation. The first Linux native run
(38057531854) compiled the complete private helper/DrRacket and passed 13 of 14
cases, including the actual custom merge and fast-hit checks. The detached-snip
case exposed both the initial test assumption and the shortcut contract defect
above; timing was skipped. Revised assertions compare original/candidate return
values and contract/arity exception categories for owned, foreign, detached and
released snips, including empty editors. The repaired native file has passed a
reader check and awaits its new native run.


## Staged contract-wrapper guard

An `object/c` wrapper can preserve exact native class-interface identity while
adding a public `get-admin` range callback. A GUI-free regression reproduced one
extra callback from the unguarded candidate versus zero from stock's internal
admin-field read. Blanket `impersonator?` exclusion is unsuitable because ordinary
public-field objects can also be internal chaperones. The next revision therefore
conservatively excludes `has-contract?` snips both as query arguments and during
the existing insertion scan. Seventeen independent model tests plus three source
preservation tests pass against this staged revision.

The fifteenth native case compares actual wrapped-argument behavior; the existing
fast-hit case now additionally requires editor-created ordinary strings to lack
the contract marker and retains strict stock/private delegate counts of 2/0 for
`#f` and the real owned starting string. These new wrapper checks have passed a
reader check only. They do not alter the currently published plain-fixture run,
and its timings cannot establish performance of the staged guard.
