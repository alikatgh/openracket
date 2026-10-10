# Independent fast-path lifecycle review

The generated private stock 9.3-derived mixin passes **16 GUI-free lifecycle tests** in
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

`tests/independent-native-fastpath-test.rkt` now prepares fourteen real-editor
stock/private comparison cases for that next correctness gate. It asserts opt-in
activation, the real public interface and a counted exact-stock-string fast hit,
then checks a required native custom-string-to-rich merge, Unicode streaming ports,
foreign/detached/custom/string-subclass snips, image/nested specials, the actual pre-after-insert modified callback, reentrant
mutation and callback exceptions, undo/redo, WXME payloads and outer/generic
method dispatch. Serialization comparisons preserve text and rich bytes without
requiring incidental string-snip segmentation. The file has passed a reader check
only; none of these fourteen native cases is counted as a passing test yet.
