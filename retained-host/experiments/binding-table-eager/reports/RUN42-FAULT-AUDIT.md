# Run 42 differential timeout: test-only repair and full fault audit

## Result and limits

The three disabled actual-form processes in native run `38137618373`, job `114464630392`, reached the deliberately throwing owner test and then waited in `openracket:get-binding-table-eager-state`. They did not time out in the deterministic workload or enabled-only fault loops. The flag-on process passed 3,216 assertions. This repair changes the differential test, source checks and documentation only. Production remains SHA256 `80a32b3ebebbe741fe35a6c47f834cf35c0ea708c505961d0d98ce36ea37d6e3`; all four generated actual-form modules remain identical.

The repaired tests have passed Python/source checks only. They require native execution. The external 180-second differential bound, fatal assertions, activation modes, 1,200-operation coverage, graph and rename gates are unchanged. The independent candidate-off GUI postflight failure is parent-owned and is not claimed repaired here.

## Exact mechanism

The recovered `step7-correctness.log` records all three timeout stacks at generated `candidate.rkt:53` (the state method) from differential line 297 (the throwing owner block). Both `CUSTOM_CALLBACK_BOUNDARY` lines completed first. The state method computes `public_keys` using `hash-count bindings-table`.

Official Racket 9.3 release commit: `bbf7dea831df95922db23aaa51e13eed17dcf881`.

- [CS hash implementation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/src/cs/rumble/hash.ss), Git blob `3095838e20b4e363b81a9996f3e56fbab2a18ec5`: `hash-ref/none`, lines 402–405, acquires the mutable hash lock, calls `hashtable-ref`, and releases the lock only after that call returns. `hash-count`, lines 597–603, acquires the same lock. There is no dynamic-wind or exception release around that callback invocation.
- [CS lock routing](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/src/cs/rumble/lock.ss), Git blob `25d9bbe03675b6bd451278689b578aa061c715b6`: scheduler-backed locks delegate directly to their acquire/release callbacks.
- [CS scheduler lock installation](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/racket/src/cs/thread.sls), Git blob `9d4088be8c74ef0cd00c263043ce9aa5fdd61595`, lines 273–275: mutable equal-hash locks use a semaphore initialized to 1, `unsafe-semaphore-wait`, and `unsafe-semaphore-post`.
- [Hash reference](https://github.com/racket/racket/blob/bbf7dea831df95922db23aaa51e13eed17dcf881/pkgs/racket-doc/scribblings/reference/hashes.scrbl), Git blob `937a41d07e8fa4c468a5d01c49b8fa1303747c65`, documents table-specific semaphores and indefinite-block caveats. Its constant-time hash-count claim does not imply nonblocking behavior on an abandoned lock. The specific custom-callback exception attribution here follows the pinned implementation and native stack, rather than claiming the documentation explicitly specifies it.

Stock and candidate-off invoke the deliberately throwing owner hash during the original mutable `hash-ref`. That callback exits before semaphore release. Candidate-on omits that read and throws during immutable `set-add`, before its real public `hash-set!` begins. This is the already excluded custom-owner callback ordering boundary; changing production to unlock or substitute the public hash would not preserve stock behavior.

## Repaired observation

Every mode still requires the same original stock/candidate insertion exception signature. The original public getter is tested for returning the identical hash without performing a hash operation. Each poisoned count is observed on its own custodian-owned thread, with an entry handshake, a one-second bounded result observation, a live-thread check, custodian shutdown, and a required thread-dead event. A returned value, an exception signature, and an arbitrary raised value are distinct typed outcomes and fail the expected blocked observation. The result means blocked within the one-second observation window; the timeout alone does not prove permanent deadlock. The pinned source establishes the retained-lock mechanism. This is not a speed comparison or an accepted missing test result.

Stock is observed in every mode; candidate-off must show the same blocked result. Candidate-on retains all original failure cleanup, zero writes, and immediate getter-count assertions. Only after recording the outcomes are the test tables reset. Neither poisoned table is then queried on the main test thread. Fresh generation, empty table, reset diagnostics, successful ordinary stock insertion and final table parity are asserted. Flushed `BINDINGS_EAGER_STAGE` and `CUSTOM_HASH_LOCK_BOUNDARY` lines identify the exact last stage if any unexpected wait occurs.

## Audit of every introduced fault/error family

| Family | Lock state at failure/capture | Cleanup and subsequent observation |
| --- | --- | --- |
| Owner hash always throws | Stock/off mutable public hash lock is held; enabled fails during immutable set-add before public lock | Explicit owned blocked observations; no main-thread table/witness reads until reset. Original insertion error parity retained. |
| Foreign endpoint hash throws | Public start-key lookup finishes with the ordinary owner; foreign callback occurs in immutable set-member?/set-add | Public lock is released; complete prefix table comparison is safe. |
| Invalid object or numeric self-check | Original self-check precedes all table operations | Original error comparison and active-cache checks remain safe. |
| External invalid value or mutable-set new entry | Original public hash-ref returns before set-member?/set-add raises | Public lock is released; unchanged external value/snapshot/error checks remain safe. |
| Counter-mutating/custom-property hash callbacks | Callbacks return normally with constant hashes | No abandoned lock; original and candidate callback counts remain visible, final table checks retained. |
| Toggle-dependent foreign equality | Constant hashes; equality callback always returns; candidate already permanently stock | No abandoned lock; retained state, duplicate decisions and final graph checks remain safe. |
| 3 seams × exception/arbitrary raise/raised break/escape | Before-public hook is after immutable set-add but before hash-set!; after-public hook follows completed hash-set!; between-cache hook follows completed first auxiliary hash-set! | No hook runs while a mutable hash lock is held. Dynamic-wind drops partial state. Exact payload identity, public-write count, retries and later-edge preservation remain mandatory. |
| Requested thread break at each of 3 seams | Same completed/outside-lock hook locations; self-break requested only inside the hook | Break delivery remains bounded; original break exception must escape. No worker thread or custom key callback holds a public/cache lock at injection. Cache/in-flight cleanup and retry checks retained. |
| Caller break-enabled probe | Observation after immutable set-add, before real publication | Probe returns normally; original write and caller break state remain checked. |
| Exposure at each of 3 seams | Same outside-lock hook locations; getter only drops metadata and returns existing hash | Returned hash identity/live update and no cache revival remain checked. An obsolete numeric cache can finish its already-entered second write, but it is unreachable and cannot become active again. |
| Reset inside third hash-set! argument | Hook after immutable set-add, before mutable public write | Original captured old table receives the write; new generation metadata remains untouched. Both stock/candidate tables are safe to inspect afterward. |
| Captured continuations after write/exposure/reset | Capture inside third argument after set-add, before hash-set!, outside every mutable table operation | Re-entry preserves stock's old-target overwrite behavior and discards stale metadata. All original table, generation, no-revival and later-edge checks retained. |

This audit applies to the declared deterministic hook sites. It does not promise safe arbitrary exceptions, asynchronous breaks, or reentrant callbacks inside the runtime's own mutable hash operations. Those remain stock/runtime limitations within the documented extension/resource caveat.
