# Eager source review

## Pins and source consumers

The exact stock gui.rkt SHA256 is `5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e`, from DrRacket core-lib 1.17 commit `1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6`. Read-only source references come from Racket release commit `bbf7dea831df95922db23aaa51e13eed17dcf881`: class-internal Git blob `b3134180ee93023bfc2132d67c676b8246574c66`, set-types Git blob `13ed507f77382b3f94987399c500174e9d413aa9`.

Every binding-table reference in the pinned production core GUI source was reviewed: private initialization at stock462–465; sole add method475–491; public getter498–527; sole reset586; sole caller1054. The interface declaration is intf.rkt:12; local-member-names.rkt:22 notes the public test getter. No other production consumer/mutator exists in the searched pinned core/available companion sources. External getter callers remain a supported live-hash escape boundary.

The only production source changes are five exact substitutions: activation, private state/witness, one branch after the original self-check, getter disable, and reset state. Undoing them reconstructs every stock byte. The self-check prefix and complete fallback key/priors/new/set-member?/set-add tail are separately checked byte-for-byte. Arrow construction/range insertion/scheduling/navigation/rename sources are untouched.

## Immediate publication invariant

Before public exposure, private numeric duplicate/prior caches are trustworthy only for the exact owning editor and exact integer coordinates. Each accepted edge creates fresh real lists, calls stock set-add, and stores that immutable set in the real hash immediately. Set-add remains inside hash-set!'s third argument, so the actual target is selected before any set-add callback. The cached immutable set is exactly the value published, not a mutable replacement.

Only after successful publication may both auxiliary hashes commit. The active state token and actual real-hash identity must still match. An incomplete operation discards the entire state, with no public rollback. Getter exposure, unsupported/reentrant input, and reset cannot cause old state to be re-enabled. A reset establishes a fresh token; old escaped hashes remain live and untouched by the reset itself.

A resumed dynamic-wind entry invalidates its old token before resuming previously captured locals. Every entry resets completion state. This matters even after a previously successful call: replaying an old cache commit could otherwise install stale priors after intervening edges. Actual repeated public writes remain those of the original stock continuation, including its overwrite behavior; only unsafe private metadata is discarded.

The exact 9.3 dynamic-wind documentation distinguishes normal calls from continuation-jump pre/post calls, with break disabling explicit for jumps. The candidate therefore protects only its tiny metadata pre/post changes with parameterize-break #f. The original write body keeps caller break state. Native fault tests verify direct breaks, arbitrary raises, escapes, and resumed continuations; these are prepared, not locally executed.

## Equality and error boundary

Pinned object=? unwraps object/c contracts, so the original self-check is never replaced by eq?. Eq? is used only as the eligibility gate that requires both source objects to be the owner. Unsupported object/coordinate forms permanently choose the untouched stock branch before any public read/write in that branch.

Pinned class source permits interface* to attach prop:equal+hash without implementing equal<%>. There is no universal custom-class exclusion guard. The approved stock-built-in scope explicitly excludes custom owner hash/equality callback count/order parity. Eager publication eliminates the lazy deferred-error boundary, but removing read hashes/member checks can still change which custom callback invocation raises. Mutable/inspector-dependent hashing and arbitrary extension/continuation behavior remain outside universal compatibility claims.

Private-cache allocation/failure also cannot promise identical resource behavior to stock. The enforceable invariant is that every successful real write remains authoritative and any incomplete private update selects permanent stock fallback. Tests deliberately fail before/after publication and between cache commits, check exact escaping values, then retry and insert another edge to detect suppression or lost data.

## Validation status

28 source/applier checks pass, including the macOS-style ancestor-alias regression, pinned byte reconstruction, exact normal-form extraction, declared-only fault-module transformations, lexical checks, guarded publication order, state-token/table identity checks, reentry invalidation, and absence of journal/materialization/fault hooks in production. Native execution, actual full GUI graph/navigation, complete annotation/rename parity and performance are pending. The rejected lazy experiment and every delivered/frozen preview remain unchanged.
