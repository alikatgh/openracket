# Source review status

Prepared 2026-10-11. Source-only; native unrun.

- Exact class and eligibility review SHA256 inputs verified before editing.
- Parent reviewed the first stable core transform. Profiling worker independently
  reviewed helper/allocation semantics and actual host seam.
- Review corrections incorporated: no global memory deltas; original vector slots
  only; actual handler denominator; separate completed helper returns; skipped=false
  renamed not-skipped; asynchronous breaks propagate; zero matches and failed
  classification unresolved; direct unittest entrypoint includes evidence tests;
  injected native fault scalar restored before JSON reporting.
- Actual source paths and private functions were inspected rather than inferred.
  The existing core default body and sentinel scan are mechanically preserved.
- The accepted host workflow retains its real Run and Check Syntax callbacks, all
  original graph/selection assertions and its existing outer READY/cleanup flow.
- Restored publication45 sources inspected are recorded by exact path/hash in
  `vendor/publication45-inspected-pins.json`. Their native tool coordinator uses the
  genuine handler plus definitions/interactions getters, and their read-only app
  observers intentionally do not own editing or callbacks. This diagnostic needs
  no change to those tools and introduces no substitute tool/observer.
- Original core byte backup was saved in session storage before generation.
- SOURCE-PINS gives source/fixture closure; report logs are verification evidence,
  not runtime measurements. Native tests and namespace/field-wrapper assumptions
  are explicitly unverified until actual Racket parsing/expansion/execution.
- No candidate fast return, native execution, software installation, remote
  mutation, paid facility, security-setting change, or delivered-preview change.

The source gate is only preparation. The real question remains unresolved until
an authorized, independently rebuilt diagnostic runtime completes the genuine
small Check Syntax process with matching source/instance proof and bounded data.

## Native fault-injection binding proof

The exact official v9.3 namespace documentation was retrieved read-only from
[racket/racket namespaces.scrbl](https://github.com/racket/racket/blob/v9.3/pkgs/racket-doc/scribblings/reference/namespaces.scrbl),
Git blob `3c7ab446849f1a411c32f95f17c1e4fab165b879`. It distinguishes a top-level
namespace variable setter from an existing module binding. Module-body namespace
mutation can affect the real module; compiler constants remain protected unless
the original declaration already assigns the binding.

The native test now evaluates a lexical `set!` lambda in the actual core namespace
for its already-mutable scalar. It verifies the variable reference is module-owned,
belongs to the same core as the exported state function and is not constant.
Immediately after both fault injection and restoration, it checks the actual
private binding and exported state field. Thus a top-level shadow cannot satisfy
the test. This API source check is complete; native behavior remains unrun.

Final evidence validation also rejects a started run marked not-armed and any
activity in a never-started run. A fault stop without a fault count is rejected.
