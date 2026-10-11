# Source and consumer audit

## Official pins

- DrRacket `drracket-core-lib` 1.17, source commit `1b8a16c916eb36a43d1eb54c905e4ecfc02e99e6`, distributed for Racket 9.3.
- Exact `gui.rkt` SHA256: `5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e`.
- Racket release source commit `bbf7dea831df95922db23aaa51e13eed17dcf881`.
- `racket/collects/racket/private/class-internal.rkt` Git blob `b3134180ee93023bfc2132d67c676b8246574c66`.
- `racket/collects/racket/private/set-types.rkt` Git blob `13ed507f77382b3f94987399c500174e9d413aa9`.

The runtime references were obtained as individual source files through the GitHub source connector, never as a local runtime/package install or native execution. The original DrRacket files were copied from the already-present official package source. Source hashes are in the manifest and validated by the Python tests.

## Every binding-table reference in pinned core GUI source

| Stock lines | Role | Candidate effect |
|---|---|---|
| 462–465 | Private hash field, ordinary mutable equal?-hash | Same initial hash object retained |
| 475–491 | Sole private add method, original self-check then equal?-key lookup and immutable-set member/add | Original self-check and stock tail byte-identical; guarded numeric path inserted between |
| 498–527 | Public getter returns actual table; true argument reads only tooltips from arrow records | False branch materializes before returning same object; true branch byte-identical |
| 586 | Sole reassignment, `syncheck:init-arrows` installs fresh hash | Private state resets immediately afterward; old hash untouched |
| 1054 | Sole call, inside genuine `syncheck:add-arrow/name-dup/pxpy` | Caller byte-identical, same true/false controls exact original two range insertions |

The entire pinned `drracket-core-lib` package plus available companion tool/document sources were searched for the method/field names. `intf.rkt:12` declares the getter method. `local-member-names.rkt:22` comments that the test suite uses it; it is not renamed to a private local method. No other binding-table consumer exists in the pinned production source reviewed here. The public getter intentionally allows external callers; its escape behavior is therefore part of the contract, rather than dismissed because it is described as a testing hook.

Existing retained-host Check Syntax test consumers call the getter only after the Check Syntax button is enabled, inspect/copy its graph, invoke bounded editor canvas operations, then confirm it remains unchanged. The separate parent-owned postflight strengthens that into full graph/shape and owning-path witness checks. Native worker-side trace/rename tests are also necessary but cannot by themselves exercise this GUI consumer.

## Why the eligibility test is deliberately narrow

Racket's class implementation defines `object=?` in terms of identity after unwrapping object contracts (`class-internal.rkt:4526–4570`). The original self-check therefore cannot be replaced by `eq?`. It remains unchanged and executes before any index/fallback work.

Ordinary object hash/equality are implemented around `class-internal.rkt:3269–3311`. Object hashing attempts to form an inspectable structure vector before falling back to identity hashing. This source makes repeated editor hashing a plausible cost center, but this is an inference, not new runtime attribution.

`interface*` can attach arbitrary structure properties through `get-properties`/`add-properties` (`class-internal.rkt:2857–2887`). `equal<%>` is implemented using one such property near the end of the module. An interface-name exclusion therefore does not prove that custom equality/hash behavior is absent. The candidate uses no purported universal class guard.

Only when both text arguments are the identical owning editor and all coordinates are exact integers can endpoint equality be reduced to the immutable numeric tuple under the approved stock-built-in scope. Different objects, object/c wrappers that are not eq? to the owner, and unsupported coordinates permanently select stock behavior after materialization. Foreign self-links still short-circuit before that fallback exactly as stock did.

## Why the immutable-set shortcut was rejected

`set-types.rkt:129–134` implements set-add using immutable hash-set and `update-custom-set-table`. The latter (`340–345`) constructs a new set wrapper, so comparing old/new set wrapper identity is not a sound duplicate witness. Replacing values in the publicly escaped hash by mutable sets is also unsafe: subsequent external snapshots and set-add/error behavior would change. The chosen design keeps all public values produced by the original stock update path.

## Exact claims and limits

Source reconstruction removes exactly five substitutions and yields every original byte. The add method's original self-check prefix and original key/priors/new/set-member?/set-add tail are tested separately for byte equality. Actual native differential classes extract those method bodies unchanged; no Python value model is used as correctness evidence.

The enabled experiment defers owner hashing and original public-table allocation work, adds numeric journal/index retention, and does not preserve arbitrary owner-defined hash callback counts/timing/errors, custom mutable hashing/inspectors, callback reentrancy or finalizer/resource observations. Explicit native tests characterize those exclusions. Public exposure/fallback is one-way within a generation, with the original live hash and immutable-set behavior thereafter. This is a default-off stock-built-in experiment, not a general-purpose DrRacket extension compatibility claim.

Native execution remains pending. No passing Python test establishes Racket expansion, genuine fast-path hits, GUI annotation/arrow or rename parity, or performance benefit.
