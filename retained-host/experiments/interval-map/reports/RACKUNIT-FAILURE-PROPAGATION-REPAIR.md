# RackUnit failure-propagation guard repair

## Evidence and scope

Native run 38119983626 showed the procedure-identity guard failing identically
in both docs-host arms. It establishes that this identity assumption is invalid
in those processes. Contract wrapping is a possible mechanism, not a verified
root cause. The parent-owned `NATIVE-CORRECTNESS-38119983626.md` records the exact
native run evidence and remains unchanged by this repair.

Only the working experiment tree changes. Immutable `0615` is untouched.
`interval-docs-postflight.rkt` has exactly two substitutions relative to the
frozen source SHA-256
`ec70384afcbbcf6203a3b86e7ad72cde0363d25ab50d66cde44f03c52de22696`:

1. Require `rackunit-failure-propagation.rkt`.
2. Replace `(eq? (current-check-handler) raise)` with
   `(assert-rackunit-failure-propagation!)`.

A Python source check reverses those substitutions and requires the exact frozen
hash. All other postflight bytes, actual GUI-thread parameterization, docs-map
assertions, full-map snapshots, query-boundary witnesses, source pins, JSON
schema, comparator, host, candidate implementation and dependency copies remain
unchanged. The two-insertion host retains SHA-256
`ad0ba1ec80fb8dbcec86f54e1a0088d6a938c62c052d6bcaf7cb12e251134fb8`.

## Behavioral witness

The new GUI-free helper executes one intentional failed `check-true`. It catches
only `exn:test:check?`; normal return is an error. It does not change the active
RackUnit policy. The postflight retains its original
`(parameterize ([current-check-handler raise]) ...)` on the actual GUI handler,
so successful passage through the guard now demonstrates behavior rather than
procedure identity. Unexpected exception types are not converted to success.

No cached RackUnit implementation was found in the permitted local package,
workspace or system-library searches. No source download, runtime installation
or runtime execution was attempted. This change therefore does not assert an
uninspected RackUnit contract implementation. It directly exercises RackUnit's
actual failed-check/exception API in the native acceptance process.

## Actual native regression to execute

Run with the native runtime on its existing native display:

    racket tests/rackunit-failure-propagation-test.rkt

Use this standalone command; deliberate failed checks are test inputs, so this
is not a successful-check count from a `raco test` wrapper.

The test imports the exact production helper. It creates one separate GUI
eventspace under a deliberately nonraising ambient RackUnit policy, queues one
callback, and verifies it runs on that eventspace's handler rather than the
calling thread. No window is created. The callback verifies:

1. An intentional ambient failure returns through the nonraising handler.
2. The exact production helper rejects that nonraising policy.
3. Inside the same explicit `current-check-handler=raise` parameterization used
   by the postflight, the exact helper succeeds.
4. A subsequent intentional failed check escapes as `exn:test:check?`; its next
   statement cannot run and the ambient handler is not called.
5. Leaving the protected scope restores the nonraising ambient policy.

The main thread waits at most 10 seconds for the result and shuts down the test
custodian before reporting success or re-raising failure. Success prints
`OPENRACKET_RACKUNIT_PROPAGATION_OK`.

The cached official GUI source backs the separate-handler setup:
`mred/private/mred.rkt` lines 73–77 delegates creation to the wx eventspace API;
`mred/private/wx/common/queue.rkt` lines 366–397 creates a dedicated handler thread
inside the caller's parameterization. The regression also checks that actual
behavior, rather than relying only on the source inference.

## Verification performed here

- 69 Python docs comparator/source checks pass, including exact repair-scope and
  regression/helper correspondence checks.
- Python compilation passes.
- Static delimiter/string scans pass for all three affected/new Racket modules.
- Native Racket compilation and regression execution remain pending.

The new helper and regression source are test infrastructure only. They do not
change user source, interval-map data, GUI tools, preferences, production
activation or any source-pinned runtime module.

The standalone regression explicitly flushes its success marker and exits 0 only after custodian cleanup and every behavioral assertion. This avoids relying on implicit GUI application lifetime. Errors before that point retain nonzero termination.
