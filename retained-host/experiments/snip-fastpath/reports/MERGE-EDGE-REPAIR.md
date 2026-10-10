# Conservative repair before native timing

The earlier 1335 snapshot was held before publication. Its inherited cache could
remain true after a custom string subclass merged into a rich snip through a
selection/style boundary, outside insert/delete callbacks. It must not be used
as a validated candidate.

The current private helper permanently delegates after observing a non-exact
stock string-snip interface in the existing after-insert range walk. It also
disables when a mutation starts with false/unknown cache knowledge, preventing
unexamined rich history from later becoming eligible. No extra virtual scan,
subclass callback, generic Framework patch, or broad merge-hook change is added.

The independent model now covers the silent merge/stale-cache route and rich
history. The native gate adds an actual custom merge reproducer and a lower
test-only counter requiring genuine stock-string shortcut hits, with stock
and private counts 1 and 0. Native execution remains the required next gate.

22 Racket source/model/fixture tests and 15 Python generation/identity/comparison
tests pass locally. Native files are reader-valid; the retained lexer harness
compiles. Any benefit is limited to eligible plain stock-string buffers and is
not yet measured. The source unit composition patch is unchanged.
