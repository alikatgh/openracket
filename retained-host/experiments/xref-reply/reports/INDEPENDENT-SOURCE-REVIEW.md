# Narrow candidate: thread-free Check Syntax xref replies

Design only, 2026-10-11. No stock/production files were edited and no Racket tests were run in this review. Exact source copies and provenance are in `official-v9.3/SOURCE-MANIFEST.json`. This candidate is an internal same-place response transport change, not subprocess isolation or a new documentation cache.

## Recommendation

Test one change in a disposable copy of `drracket/private/syncheck/xref.rkt`: retain the existing serial lookup service and existing cache, but replace the fresh response-channel plus per-response thread with a private result cell and semaphore. Keep the caller's existing outer `sync`/`nack-guard-evt` shape in the first candidate to avoid broadening the break/cancellation change. Do not alter traversal, annotation callbacks, docs lookup, cache keys, flush behavior, tools or the 128 MiB job limit.

This targets allocation visible in exact source, not proven allocation ownership. Both phase trials reached monitor-build-trace-start, produced no monitor payload, and ended in stock OOM. The analysis observed `document-variable` as a first frame 6 times in trial 1 and 2 times in trial 2, plus traversal/id-table/class frames. Those counts are coarse contexts, not percentages of allocation. `document-variable` can be waiting for the separate xref service, which this probe did not sample. No speedup or OOM cure is established.

## Why this seam, rather than another cache

`traversals.rkt:801–807,809–829,843–861` calls `document-variable` for binder/reference occurrences and template references over phases and modules. `document-variable:1538–1563` obtains the full phase-sensitive binding, validates source positions, looks up xref data at 1549, and emits the text-type/docs-menu annotations. It formats the label separately at 1560/1565–1581.

`xref.rkt:15,32–36` already has an `equal?` cache keyed by the entire binding-info value. It caches both positive values and #f. Repeated bindings therefore do not necessarily repeat the underlying documentation search. Nevertheless every live-service request creates a response channel, request list and nack guard (`47–54`); after either a cache hit or miss, the service creates a new responder thread (`37–40`). Removing that thread is a smaller and more directly bounded experiment than introducing another result cache.

On actual service misses, `xref.rkt:19–23` resolves binding → definition tag → path/anchor → entry. `scribble-xref.rkt:173–180` constructs a renderer for path/anchor lookup. `setup-xref.rkt:173–190` caches the xref object and may demand-load documentation using SQLite and loaded-document tables (`98–164`). This could make misses expensive, but current samples do not distinguish these costs. Do not state that a renderer is created on every `document-variable` occurrence.

## Exact single-file candidate plan

Only change these areas of the disposable xref source:

1. Add a private reply-cell structure near `req-chan`, containing a mutable `value` field and a semaphore initialized to zero. Its initial value may be #f because readiness, not value truthiness, determines completion.
2. In the existing nack-guard maker at lines 51–54, create one cell; send the same four-field request shape `(binding-info current-directory cell nack-evt)` via the original `channel-put`; return a `wrap-evt` on the cell's semaphore whose callback retrieves its value. Keep the original outer `and` service-death check and `sync`/`nack-guard-evt`.
3. In the existing service branch at lines 32–40, compute the exact same single `resp` using the same parameterization and `hash-ref!`. Set the cell value to `resp`, then `semaphore-post` once, then loop. Delete only the responder `thread`/`sync(channel-put-evt..., nack-evt)` allocation. Never wait on a caller in the service thread.
4. The nack event remains in the private tuple for the first candidate but needs no cancellation watcher: there is no blocking response send to release. Do not poll it, synthesize a canceled value, or create another thread to watch it. Removing the now-unused guard is a separate possible simplification after validation, not part of this candidate.

Do not substitute one async-channel per request without inspecting its implementation: that is not proof of removing per-request thread machinery. Do not merely inline the old response `sync` in the service: a suspended requester could then block unrelated requests.

## Ordering, cancellation and lifetime contract

- The single existing service thread remains under its original initialization custodian. Its comment at 44–46 explains why this custodian survives caller termination. The job custodian, syntax objects, xref instance and persistent binding cache are unchanged.
- The caller still sends inside the same nack-guard maker. The same `channel-put` acceptance point and break behavior before acceptance are retained. The maker runs at most once per synchronization; the standard NACK becomes ready on caller death or escape even before the maker returns (reference `evts.scrbl:203–237`).
- After acceptance, the service performs the lookup even if the caller is later killed, just as it already does. It performs one nonblocking publication: assign value before posting the semaphore. Publication before the caller begins waiting cannot lose a wakeup; the semaphore retains the permit.
- A caller killed or broken before receipt does not leave a responder blocked in the service custodian. Its private cell becomes collectible when the service and abandoned caller release it. No cell is pooled, reused, stored in the binding cache, or shared with another request.
- A suspended caller can resume and receive the original result; meanwhile the service must process other clients. This matches the reason the current design delegates response delivery to a thread.
- Keep `wrap-evt`, rather than `handle-evt`, for the cell extraction. The wrapper runs with breaks initially disabled (`evts.scrbl:153–182`), closing the selected-readiness/extraction gap without adding callback-visible work. Do not use `sync/enable-break`, re-enable breaks inside publication, or change the caller's break parameterization in this candidate.
- Return the original result object, not a copy. #f is a valid result. The service already binds `resp` as exactly one value; keep that binding, so zero/multiple-value or lookup exceptions have the same service failure behavior. Do not turn exceptions into cache misses or add error propagation under this change.
- Calls begun after the service thread is already dead still return #f via line 48. A death during an already accepted lookup can leave a waiting caller without a response in current stock; this candidate must not claim to repair that separate race. A published reply remains available even if the service later dies.
- The response completion schedule changes by removing a scheduler hop. Exact thread scheduling, responder-thread counts and allocation counters are intentionally different; return values, one-result ownership, callback sequence within a traversal, and freedom from a canceled/suspended client blocking the service must remain equivalent.

## Cache and extension boundaries

No new invalidation policy is needed for the reply-cell candidate because the authoritative cache and lookups are untouched. In particular:

- Keep full binding-info and phase distinctions; do not key by identifier spelling, printed module path, or docs label.
- Preserve current-directory parameterization for actual lookups. The stock binding cache itself only keys on binding-info; do not silently change that behavior here.
- Do not cache `build-docs-label` or whole annotations. Custom annotation objects can observe calls, order and mutable string identities. Preserve every callback, including duplicates and template/submodule occurrences.
- A future per-traversal front cache must address service death, positive and negative entries, current-directory context, explicit invalidation, doc/package changes, and the xref generation. A job-local lifetime alone does not prove equivalence if a flush or extension acts during traversal. It must not suppress callbacks or retain syntax across jobs.
- The reviewed `flush-index-entry-cache` body at xref.rkt:56–59 creates a `channel-put-evt` in a thread but never synchronizes it. By source inspection, merely constructing that event does not deliver the #f flush request. Flag this as a separate source-level issue, not a dynamically reproduced bug; do not fix it or assume it provides a functioning invalidation epoch in this experiment. No calls were found in the extracted core source searched, which is not proof that an extension cannot call this exported function.

## Exact tests before native performance claims

Use a deterministic isolated service harness with instrumented lookup barriers and both stock/candidate versions; keep injected test hooks out of the production candidate.

1. Positive result identity, #f miss, repeated full binding cache hit, distinct binding/phase, and directory-sensitive lookup: same values, same lookup invocation count and cache keys.
2. Many concurrent requesters: each gets its own result exactly once; no cross-talk; service stays live. Suspend requester A immediately after request acceptance, complete requester B, then resume A and verify its original result.
3. Kill, break/continuation escape and caller-custodian shutdown at each barrier: before acceptance; after acceptance/before lookup completion; after publication/before sync selection; and after selection. A later independent request must complete. Test both enabled and disabled breaks without indefinite test hangs.
4. Publication-before-wait: hold the caller after request acceptance, let the service publish, then release it. The result must arrive once with no lost wakeup. Use independent cells for repeated calls by the same thread.
5. Service already dead returns #f. Inject lookup exception and zero/multiple-value return to verify unchanged failure classification; kill the service during lookup and use an external harness timeout to classify the pre-existing no-reply case rather than inventing a result.
6. Confirm no per-response thread creations in candidate, no retained reply cells after canceled/completed requests and GC, and no surviving job-owned objects caused by reply-cell references. Do not require equal scheduler traces or exact GC timings.
7. End-to-end small successful Check Syntax fixtures: exact ordered trace/datums, labels, callback counts, result/compiled-byte behavior, rename capability function and lifetime. Include reexports, multiple phases/submodules, template references, missing docs, WXME/embedded-source gating and extension annotation objects.
8. Repeat the same captured 1,048,577-character workload under both versions, same frozen stock registry/prefab/128 MiB limit, with phase outcome, process allocation/CPU/GC and terminal reported. Add bounded counters for accepted requests and underlying binding-cache hit/miss plus an optional sampled xref-service stack. Counters and service frames must be labelled diagnostic overhead; do not infer allocator ownership from sample counts.

Proceed only if correctness tests pass. A lower allocation interval with the same OOM is a limited result; success and GUI latency require their own actual evidence. No bridge, trace suppression, larger memory limit, flush fix or cache policy change should be combined with this comparison.

## Verified source locations

All paths share `/workspace/scratch/5923f1aa2055/openracket-process-isolation/review/official-v9.3/`:

- `traversals.rkt`: Git blob `2ae2e8cf161105130bf04bba6a2f8e4dae8eacb4`; SHA-256 `bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00`; [official source](https://github.com/racket/drracket/blob/v9.3/drracket-tool-text-lib/drracket/private/syncheck/traversals.rkt)
- `xref.rkt`: Git blob `3ca132d8afc9b1353e898c164ea92cf1c0fd144d`; SHA-256 `acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7`; [official source](https://github.com/racket/drracket/blob/v9.3/drracket-tool-text-lib/drracket/private/syncheck/xref.rkt)
- `setup-xref.rkt`: Git blob `2992e45d7989f524ad13c19ecdf8553434994319`; [official source](https://github.com/racket/racket/blob/v9.3/pkgs/racket-index/setup/xref.rkt)
- `scribble-xref.rkt`: Git blob `5177196e83cf8528503814ecd29bca394225b797`; [official source](https://github.com/racket/scribble/blob/v9.3/scribble-lib/scribble/xref.rkt)

Each full file was obtained independently by the authorized read-only GitHub connector at v9.3, saved byte-for-byte, and checked by computing Git's blob SHA-1 over `blob <byte-count>\0<content>`. No blocked package-archive request was retried or routed around.

## Concrete overlay review, 2026-10-11 01:43 UTC

Reviewed `/workspace/scratch/5923f1aa2055/openracket-xref-reply/overlay/xref.rkt` and its adjacent `patch.diff`. The actual implementation uses a private box plus semaphore instead of the illustrative reply-cell struct above, and reuses tuple slot four for the semaphore in enabled mode; both are appropriate for this two-branch internal protocol.

Static verdict: no source-level blocker found, subject to actual runtime tests. The environment flag is read once at module instantiation (9–10), so sender and service cannot interpret the same tuple using different live flag values. The disabled branch retains the original response-channel/NACK behavior. Enabled service publication is assign-before-post, once per accepted request (47–48), with no caller wait. Enabled caller creates independent box/semaphore (64–67), retains the original request `channel-put` inside the original nack maker (68–69), and uses `wrap-evt` for selected-readiness extraction (70–72). Lookup and cached data are unchanged (21–41); original flush is unchanged (74–77). Exporting the resolved flag allows the harness to verify it tested the intended branch. There is no new cache retention/invalidation issue in this patch.

Required documentation/annotation parity plan:

- First prove a positive documentation control, not just an all-miss fixture: installed docs for common `racket/base` bindings, plus `racket/list` imports/reexports. Compare complete `(entry-desc, path, definition-tag, anchor)` lookup results and actual emitted docs-menu labels/tags/paths, including repeated occurrences. Confirm #f behavior with a locally defined undocumented module.
- Run exact same source/path/settings through full stock go+monitor under flag off and on; collect ordered trace vectors and final responses without filtering docs vectors. Compare position/span, identifier key, label text, path type/bytes, complete definition tag and anchor, and text-type marker. Preserve docs vectors for each occurrence, rather than deduplicating them in the test oracle.
- Include `begin-for-syntax`, `for-syntax`, `for-template`, `for-label`, nested submodules, renamed/prefixed imports, and quote-syntax/template references so the same printed name with different bindings/phases is exercised. Use the same locale and collection/doc configuration for both sides.
- Because place-channel objects cannot be equal across runs, normalize only channel identities using a stable first-seen bijection and verify repeated references retain that mapping; do not drop capability fields. Also execute actual rename conflict/non-conflict queries on retained successful traces, after terminal delivery, to verify unrelated capability lifetime is unchanged.
- Keep baseline-to-baseline controls. If hash iteration yields genuine stock trace-order variation, report it and define a narrower documented comparison for that case; do not silently sort every candidate trace or erase duplicate callbacks. Lookup-cell unit tests alone are insufficient to establish full Check Syntax parity.
- Use a custom annotations object in an isolated traversal harness to record all callbacks and argument values; confirm docs callbacks and their ordering are unmodified. This tests the extension boundary without substituting the object for the stock GUI monitor in the native performance run.
- Compare the full handler registry, prefab settings, terminal kind/message, statuses and compiled bytes/#f. The large workload's pre-existing OOM cannot substitute for positive docs/rename parity on smaller successful fixtures.

This review does not claim that the candidate has compiled, passed tests, saved allocations, completed the large expansion, or improved GUI responsiveness.

License/provenance confirmation: official `drracket-tool-text-lib/info.rkt:18–19` declares `(Apache-2.0 OR MIT)`. The package LICENSE states that the user can choose either and links the full Racket Apache/MIT texts. Exact saved copies are `official-v9.3/drracket-tool-text-lib.info.rkt` (Git blob `776bdfa52848e2468febf46fb71591a4ffa5c548`) and `official-v9.3/drracket-tool-text-lib.LICENSE` (Git blob `a2147765640f9a47f52e0f911424b5c010d800f9`). Their hashes and official URLs are in SOURCE-MANIFEST.json. Preserve the package notice alongside the selected/full distribution license text and mark the candidate modification separately; do not mislabel modified xref as byte-identical upstream.
