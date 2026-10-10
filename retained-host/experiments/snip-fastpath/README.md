# Private retained-DrRacket snip scan experiment

This is an uninstalled, opt-in performance candidate for exactly Racket 9.3.
It has no native outcome or measured speed benefit yet. It is outside the
retained-host appearance branch and is not included in its CI snapshot.

## Intended shortcut

Framework already maintains whether an editor contains only string snips.
When this existing cache is stably true, a stock editor's
`find-next-non-string-snip` must return false. That can avoid repeated suffix
walks when the stock colorer opens another editor-backed input port.

The candidate returns false only when the cache is already true, no mutation
callback is pending, no uncertain callback exit occurred, and the argument has
the original valid shape. Unknown/false cache states and invalid arguments use
the exact inherited method. It does not rescan an unknown cache or add virtual
calls while deciding whether to use the shortcut.

## Narrow extension boundary

The public `framework/private/text-misc.rkt` and exported Framework mixin stay
unchanged. The generated private helper copies only the exact pinned stock
all-string mixin, reuses the real `text:all-string-snips<%>` interface object,
and adds the conservative guards. Its only caller replaces one known
composition in `drracket/private/unit.rkt`, underneath the existing outer tool
mixins. The exact pinned stock inner chain has no competing implementation of
`find-next-non-string-snip`.

`OPENRACKET_ALL_STRING_FAST_PATH=1` selects this helper. When it is absent, the
helper selects the exact original `text:all-string-snips-mixin` object, with no
new method or callback layer. Generic Framework clients therefore keep their
original superclass dispatch in every mode. A custom outer DrRacket tool
method still executes before this method; native tests of that route remain
required.

## Conservative eligibility

Only buffers observed through exact native `string-snip%` objects keep the
shortcut. Custom string subclasses and other string-derived snips fall back
permanently, preserving their split/merge behavior. In particular, stock text%
can splice a subclass's rich `merge-with` result during a style change without
insert/delete hooks, leaving the inherited all-string cache stale. The original
after-insert range walk now checks interface identity without adding any virtual
snip call. Mutations beginning with false/unknown cache knowledge also disable
the shortcut, preventing unexamined rich histories from becoming eligible later.
This restricts the optimization; it does not restrict what the editor accepts.

## Mutation safety

The original cache calls subclass augmentations before updating its value.
Actual editor mutation can also occur before `after-insert`, with refresh or
modified callbacks in that interval. A shortcut must not trust the stale cache
there. Before/after mutation callbacks track kind, positions, completion, and
nested identity. Queries during mutation delegate. Exceptions, nonlocal exits,
continuation reentry, unmatched/mismatched/direct callbacks, and aborted edits
fail closed. They permanently disable the shortcut for that instance rather
than guessing whether the existing stock cache recovered.

The original cache expressions and ordering are preserved. The stock on-delete
argument named `end` is left as-is; this experiment does not repair or reinterpret
it. The method still has exactly one argument and delegates invalid values to
the stock type-contract path.

## Reproduction

Run `python3 scripts/prepare-fastpath.py` to regenerate only the local overlay.
It verifies raw source bytes and never installs or contacts the network.
`reports/fastpath-manifest.json` pins both source files and generated output.
`reports/stock-all-string-fastpath.patch` contains the complete two-site unit
module diff. The private helper is the other generated overlay file.

Run the Racket test files under `tests/` with the official 9.3 `raco test`.
The source test reconstructs the original stock mixin after removing only the
listed guards, proves the unit module has only the one import and one call
change, and refuses a Framework install overlay. The independent lifecycle
suite executes the actual generated mixin against a small GUI-free mutation
model. This is evidence for guard logic, not native editor equivalence.

The Python suites `generator-integrity-test.py` and `installed-source-test.py`
verify deterministic generation, exact-byte/CRLF refusal, arm selection, helper
hashes, generic Framework preservation, and runtime-boundary/symlink refusal.
`scripts/verify-installed-candidate.py` is read-only: its JSON explicitly says
that matching source bytes do not prove native activation. It does not install,
launch a runtime, or infer correctness from the selected environment variable.

## Required before any enablement

- Compile against the full official distribution and prove private activation.
- Compare native pure text, Unicode, foreign/detached snips, string subclasses,
  images, nested editors, custom snips, undo/redo and rich WXME roundtrips.
- Exercise reentrant queries in actual mutation hooks, callback exceptions,
  cancellation, and outer tool overrides.
- Compare actual editor-backed port results, unchanged lexer/token/style output,
  and edit invalidation with candidate off and on.
- Run fresh same-harness stock/candidate measurements with identical language,
  tooling, instrumentation, memory limit and editor state. Keep this experiment
  separate from the color-budget experiment for attribution.

The profiling observation is a hypothesis, not a speed claim: seven major GC
intervals overlap about 5.6 seconds of the worst sampled colorer callback. A
stack interrupted in a snip scan does not prove the scan consumed that time.
Measure total readiness, responsiveness tails, allocations, GC and throughput,
not just synchronous file-load duration.

Original sources and their Apache 2.0/MIT licensing are preserved in `vendor/`.
