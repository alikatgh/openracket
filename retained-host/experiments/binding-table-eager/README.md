# Default-off eager binding read-cache

A separate, source-pinned DrRacket 9.3 experiment. The rejected lazy-index source and its evidence remain untouched. This revision keeps the real public binding hash fully current; it has no journal, getter replay, or deferred table construction. No preview adoption is authorized.

28 Python/source/applier checks pass. Native Racket execution, real GUI/full graph/navigation checks, full annotation/rename parity, and performance measurements remain pending. Source checks are not native correctness evidence.

## Exact bounded change

Only `drracket/private/syncheck/gui.rkt` changes, through five pinned substitutions. `OPENRACKET_BINDING_TABLE_EAGER=1` enables the candidate. Absent, `0`, and every other value are off. The distinct read-only export is `openracket-binding-table-eager-enabled?`; prior lazy-index flags have no effect.

The original object=?/numeric self-link check remains first, byte-for-byte. Only non-self arrows whose two objects are both eq? to the owning editor and whose four coordinates are exact integers can use the eager branch. Within that scope the object component is constant. A private equal?-hash of four-number tuples answers duplicates; a private equal?-hash of start-coordinate pairs caches the exact current immutable prior set.

For each accepted edge, the candidate creates the original fresh real key/new lists and immediately executes the original set-add and hash-set! operations. The set-add result is captured transparently inside hash-set!'s third argument, preserving evaluation of the target table before set-add. The actual public hash and its original immutable-set values are therefore complete after every successful accepted call.

Only after that real write succeeds are the two numeric caches updated. The optimization removes the original repeated object-containing hash-ref/set-member? work. It does not remove immutable-set/public-hash insertion work or postpone that work until inspection.

## Cache consistency and escape behavior

Both auxiliary hashes belong to one private state token. Cache commits require the same active token, same real target hash, and no public exposure. A dynamic-wind cleanup drops the entire matching state on an incomplete operation. It covers ordinary exceptions, arbitrary raised values, breaks, and continuation escape without intercepting or replacing the escaping value. Already-successful real writes are never rolled back: a retry uses the authoritative public hash through the original stock branch.

Every second entry into a captured insertion continuation invalidates that old token before execution resumes, even if its first call completed successfully. Completion state resets per entry. An old continuation cannot populate or disable a newer generation's caches. Its original captured public write is still allowed to do exactly what the corresponding stock continuation does.

Tiny metadata-only pre/post regions disable breaks while updating the marker/token. The original set-add/hash-set! body retains the caller's break setting. Native tests request actual thread breaks at controlled publication/cache boundaries and check that no active cache or in-flight marker is stranded.

The first public binding-table getter marks exposure, disables both caches, and returns the same already-current hash. Subsequent getters do no cache work. Tooltip-only reads remain byte-identical and do not expose bindings. Unsupported non-self inputs and reentrant mutation permanently disable the current caches before the unchanged stock branch. Reset creates a new table/token and leaves every old escaped table untouched.

External mutations, removals, clears, externally inserted invalid/mutable values, retained immutable-set snapshots, and later additions all use the original path after exposure. There is no new concurrency/interleaving guarantee for arbitrary multi-threaded editor mutation.

## Supported scope and exclusions

The enabled candidate is restricted to the retained stock built-in editor. It does not claim arbitrary extension compatibility. Custom owner equality/hash callbacks can observe fewer calls or different ordering; inspector-dependent/mutable hashing, callback reentrancy, resource/finalizer observations, and custom continuation behavior are outside general semantic parity. In particular, an equal<%> test is not a complete guard because interface* can attach prop:equal+hash directly. No invented class-property guard is used.

Unlike the rejected lazy design, genuine set-add/hash-set! failures are not deferred to a getter. The added caches can themselves allocate/fail; the consistency guarantee is fail-closed fallback with the real hash authoritative, not identical resource-exhaustion behavior to stock. Retention includes a numeric edge tuple per accepted edge and a numeric start key/current-set reference per distinct start until exposure/reset. There is no extra per-edge editor/source object retained by the numeric index.

## Read-only state contract

`openracket:get-binding-table-eager-state` returns a fresh immutable hash of 17 scalar fields:

- enabled, active, in_flight, generation
- accepted, duplicates, eager_writes, stock_calls
- pending, materializations, public_keys
- indexed_edges, cached_starts, exposed
- unsupported_fallbacks, failure_fallbacks, fallback_reason

`pending` and `materializations` are always zero: there is no corresponding deferred structure or operation. `public_keys` is actual hash-count of the real public table. `indexed_edges`/`cached_starts` are hash-counts of the private hashes while active and zero after disable. These are constant-time reads, with no traversal, hashing of editor objects, table exposure, or getter call.

`accepted` counts successful eager returns; `eager_writes` counts successful eager real writes. A synthetic failure after publication can leave writes greater than accepts, as intended. `stock_calls` counts only invocations that use the original fallback branch. Ordinary successful eligible workloads must have accepted=eager_writes=indexed_edges>0, cached_starts=public_keys>0, and no pending/materialization/in-flight/fallback state before exposure.

The enabled first getter sets exposed=true, active=false, fallback_reason=public-exposure and drops indexed_edges/cached_starts to zero. It preserves accepted/eager_writes/stock_calls/public_keys. A second getter leaves the witness unchanged. Off retains exposed=false/fallback_reason=false and has zero eager activity, with stock_calls recording the original branch. Other first-disable reasons are unsupported-input, reentrant-call, and interrupted; later public exposure does not replace an existing reason. Counters reset with each generation.

## Reproduction and disposable installation

```
python3 scripts/prepare.py
python3 scripts/extract.py --output tests/generated
python3 tests/source-test.py
```

The manifest pins DrRacket 9.3 package 1.17, the exact target and unchanged interface support. Individual source-only Racket class/set references are pinned by Git blob and SHA256. They are not installed or executed locally.

```
python3 scripts/apply.py --runtime-root "$CLONE" --target "$EXACT_GUI_SOURCE" --confirm-disposable-copy
```

Use a deep-copied disposable runtime and fully canonical paths. The applier rejects a changed overlay/preimage/support file, alias/escape/hardlink, and missing acknowledgement; it preserves mode, replaces atomically, and verifies the result. `--revert` restores exact stock bytes. The test fixture resolves macOS temporary-directory aliases while the production canonical-path refusal remains strict; an explicit synthetic alias regression checks refusal, successful canonical apply/idempotence/revert, and escape rejection. Recompile with the selected isolated native runtime/cache before claiming executed activation.

## Native correctness gates

Normal generated stock/candidate classes contain the exact actual add/get/reset bodies and state/witness forms. Both arms operate on the same owner object, permitting complete equality and same-process hash/set-order comparison. A test-only direct peek verifies the real table is current before exposure; that peek does not exist in production.

The separate generated fault classes add only declared test hooks immediately after set-add, after successful publication, and between auxiliary commits. Source checks strip those exact substitutions back to the original extracted methods. Production contains no fault hooks or writable diagnostic API. These fault tests verify consistency on the newly added state, not a claim that stock has the same artificial failure sites.

Run fresh native Racket 9.3 processes:

```
env -u OPENRACKET_BINDING_TABLE_EAGER racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_EAGER=0 racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_EAGER=unexpected racket tests/bindings-differential.rkt off
OPENRACKET_BINDING_TABLE_EAGER=1 racket tests/bindings-differential.rkt on
```

All assertions raise on failure. Coverage retains 1,200 deterministic operations/duplicates, complete current/final tables and iteration order, zero/reversed/negative/bignum positions, live escaped mutation/invalid values/set snapshots, object/c and transparent/equal-but-distinct foreign sources, state-dependent foreign equality with constant hashes, unsupported coordinates, tooltip-only reads, reset before/after exposure, and original self-check errors. Custom equal<%>/direct-property tests explicitly demonstrate the excluded callback-count boundary while real writes remain eager.

Additional enabled tests cover exact exception/arbitrary-value/break/escape propagation at three controlled seams, actual requested thread breaks, exposure during writes/commits, reset inside the third hash-set! argument, and paired original/candidate continuations resumed after intervening writes, exposure, and reset. No failed partial cache may suppress a retry or lose an already-published edge on a later insertion.

The parent-owned real GUI gate must independently prove actual eager hits and writes, exact nonempty full binding graph/immutable-set shape/editor associations, the same bounded navigation/arrow behavior, and unchanged source. Full annotation trace/genuine rename parity remains mandatory. The performance owner separately measures the original completed-GUI endpoint and first getter latency/allocations, with postflight outside the timed getter. Near-stock getter behavior is an acceptance requirement to measure, not a result asserted from source.
