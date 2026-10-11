# Independent xref reply-transport review

## Result and verification limit

The candidate's bounded transport change looks consistent with the upstream
serial lookup/cache design in source review. **The native Racket test suite is
prepared, not passed:** this authoring environment has no `racket` executable.
A delimiter/string/comment scan is a source check only; it is not compilation or
runtime evidence. Native execution remains a gate before claiming equivalence.

Reviewed inputs:

- Exact upstream source: `openracket-process-isolation/review/official-v9.3/xref.rkt`
- Candidate: `overlay/xref.rkt`
- Independent tests: `tests/independent-reply-test.rkt`

The tests default to `vendor/xref.rkt` and `overlay/xref.rkt`, or accept explicit
stock and candidate paths. They parse the module and evaluate its production
definitions unchanged in an isolated namespace. They omit the original
`require`/`provide` forms, inject deterministic xref primitives, and instrument
thread creation and request acceptance. An unexpected new `require` fails the
harness instead of silently replacing additional dependencies. No GUI, package
installation, collection xref loading, network, or production test hook is used.

## Source findings

- Opt-in is exactly `OPENRACKET_XREF_REPLY_CELL=1`; the value is read once at
  module initialization.
- The same persistent service accepts each request and performs the same lookup
  and cache work. In enabled mode it writes the private result box before posting
  its ready semaphore. A legitimate `#f` result is distinguished from readiness
  by that semaphore.
- The outer `sync` and `nack-guard-evt` caller structure is retained. The enabled
  request no longer needs the nack for response-helper cleanup because no helper
  is created. Canceling a caller does not cancel an accepted lookup.
- Cached values are handed back directly, without copying; `current-directory`
  still scopes only the stock lookup/cache expression.
- The upstream flush function starts a thread whose body **constructs but never
  synchronizes** a `channel-put-evt`. It therefore does not send `#f` to the
  service. The candidate preserves this behavior. Fixing flush would be a
  separate behavioral change.
- The pre-call dead-service check is preserved. An exception or service death
  after accepting a request can still strand that in-flight caller. The tests
  intentionally expect that stock behavior and clean up within a timeout.

## Native test coverage

The same checks run for stock, candidate-off, and candidate-on:

1. Successful lookup, three distinct miss exits, cached `#f`, and a gated false
   response that must not return before its lookup finishes.
2. Equal-but-distinct binding keys share the same cache entry and identical
   result object; descriptor identity is also preserved.
3. Absent collection xref skips lookup; caller directories affect misses while
   existing cache-key behavior is preserved.
4. Existing no-op flush semantics and its one short-lived thread are explicit.
5. Thirty-seven overlapping callers, including twelve sharing a key, preserve
   result routing, same-object identity, and lookup order relative to actual
   service acceptance. Cache hits do not start a second lookup.
6. Caller kill and child-custodian shutdown during a gated accepted lookup and
   after a ready-but-unconsumed response; a subsequent request proves the
   service stays usable. Accepted canceled work still populates the cache.
   Suspend/resume also recovers the exact original successful or false reply,
   proving no lost wakeup. Intermediate helper liveness is deliberately not
   asserted: a suspended caller's channel event may already have been selected.
7. A caller canceled while the service is occupied is never accepted and causes
   no lookup/cache work. This case asserts the observable outcome; its
   pre-call dispatch marker does not prove entry into the blocking primitive.
8. Enabled breaks during lookup and after ready response; disabled breaks remain
   deferred until the enclosing `parameterize-break` exits.
9. Lookup exceptions, an unexpected multiple-value backend result (arity error),
   and explicit service kill retain the stock in-flight hang and subsequent-call
   `#f` outcome, with bounded fixture cleanup.
10. Weak references show abandoned response transports can be collected after
    the service advances, while cached results remain available.
11. Production response-thread counts distinguish stock/off from on. After
    canceled callers, all response helpers must terminate; the serial service
    remains alive. A registration gate avoids counting a helper before the
    instrumentation records it and does not change the production definitions.
12. Candidate unset/empty/`0`/`true` flags remain off; exactly `1` enables it.

All fixtures have independent custodians; caller custodians are separate from
the service custodian. Expected-hang tests have five-second event bounds and
unconditional custodian shutdown. The short 50 ms negative-observation windows
are paired with deterministic lookup gates or confirmed service death.

## Native commands to preserve

From the experiment directory:

```sh
racket tests/independent-reply-test.rkt
raco test tests/independent-reply-test.rkt
```

To compare directly with the original reviewed source:

```sh
racket tests/independent-reply-test.rkt \
  ../openracket-process-isolation/review/official-v9.3/xref.rkt \
  overlay/xref.rkt
```

Run on both intended native Racket 9.3 hosts. This is headless semantic and
resource-lifetime coverage; it is not a DrRacket UI, real-document xref,
break-scheduler exhaustiveness, retained-host latency, or whole-suite benchmark.
If the unchanged stock case fails, diagnose the harness/baseline expectation
before altering the candidate to satisfy the test. No CI or published artifact
was edited by this independent test work.
