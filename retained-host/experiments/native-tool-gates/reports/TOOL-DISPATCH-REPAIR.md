# Initial-handler coordinator repair

## Finding

Run [38128639264](https://github.com/alikatgh/openracket/actions/runs/38128639264)
passes both old standalone coordinator positive runs and typed negative controls,
then all three pristine-stock tool cases fail at exactly 20 retained-host checks.
The native log's lines 405, 499 and 593 and each decoded READY document say
`native-tool-gate: Coordinator must be outside the GUI handler`. There is no
tool-specific progress state before the failure. The existing real host startup,
file load, retained identities, Unicode/undo/redo, and two ordinary Runs complete.
This establishes a test dispatch defect before tool acceptance begins, not a
debugger, stepper, teaching-language, or overlay regression.

The host requires `racket/gui/base` while loading its module. Official Racket 9.3
`gui-lib/mred/private/wx/common/queue.rkt:357` constructs the initial eventspace
with `(current-thread)` as its handler. Lines 358–364 retain that eventspace and
handler-thread association. This association lasts; `on-gui` does not create a
different thread. Its `yield` temporarily dispatches queued callbacks on the
same handler, then returns on that same thread. Moving a call lexically outside
`on-gui` therefore never made the call a non-handler coordinator.

The official GUI startup documentation states this initial-thread ownership
directly (`startup.scrbl:39–41`), and `win-overview.scrbl:876–897` distinguishes it
from newly created eventspaces. DrRacket `private/init.rkt:22` retains the current
system eventspace; `private/main.rkt:966–1013` queues first-frame startup there.
This harness must keep that eventspace and its real handler.

`tool-dispatch-source-evidence.json` pins the inspected official cached source
bytes and exact anchor lines. No remote retrieval was done for this repair.

## Small repair boundary

Only the generated host's helper import and the three-case stock-tool dispatch
branch change relative to the 09:27 freeze. The new helper creates one ordinary
coordinator thread. The branch first parameterizes `current-eventspace` to the
existing frame's eventspace; the worker inherits that parameterization. There is
no `make-eventspace`, alternate frame, evaluator or tool implementation.

The original handler passes GUI `yield` to wait for the worker's death event.
While yielding it runs the existing `on-gui` callbacks on the real handler. The
worker's `on-gui`/`wait-for` yield calls merely synchronize because the worker is
not that handler. The original checked callback wrapper still asserts exact
handler identity and raises RackUnit failures there. The tool gate's distinct
coordinator assertion is unchanged.

The helper captures either the one returned value or the original raised object.
It checks that the worker terminated and supplied an outcome, then returns that
value or re-raises the same object on the original handler. A `dynamic-wind`
cleanup joins the worker and kills only that worker if the wait is interrupted or
returns early. Failure therefore reaches the host's unchanged diagnostic/capture
and exit path. Waiting for a death event, instead of an unconditionally posted
semaphore, also makes a worker that dies before producing an outcome fail.

No original tool, coordinator assertion, direct-driver diagnostic, fixture,
control, startup route, old follow-on branch, timeout, READY/capture handshake or
cleanup is relaxed. The 20-second tool waits, 60-second outer native supervisor,
and existing startup defaults remain. This patch does not edit the supervisor.

## Regression and refusal evidence

`native-tool-dispatch-standalone.rkt` models the initial-thread case with a
headless callback queue. The main thread is the handler. The actual new helper
must create a distinct coordinator; callbacks run on the original handler using
the actual unchanged `make-checked-coordinator` wrapper. It verifies inherited
context, action-return-before-poll ordering, the unchanged 20-second argument,
and returned values.

A deliberate failing RackUnit check executes on that original handler even
though its ambient check handler is non-raising. The exact typed exception must
cross both boundaries and arrive unchanged at the outer `check-exn`. The driver
checks the worker has died, callbacks are inactive and a subsequent callback
recovers. Separate checks exercise a raised non-exception value, interrupted
wait, premature wait return, and worker termination without an outcome; all
workers must be dead after return/refusal. The non-exception check catches only
the one bridge call's raised value and compares its identity with the original
gensym outside that catch. A normal-return sentinel cannot satisfy the strict
comparison. This avoids assuming RackUnit's `check-exn` behavior for non-exception
values; the actual RackUnit failure test still uses a typed exception predicate.

The `--inject-wrong-result` mode runs the same regression, obtains the real
`actual` value through the callback/coordinator bridge, and deliberately compares
it with `deliberately-wrong` under a raising outer RackUnit handler. Only verified
check-info from that exception can produce the typed diagnostic; the identical
exception is always re-raised. The success marker is unreachable in this mode.
Run directly, never through `raco test`, because the positive regression contains
intentional failures that are expected and caught by surrounding assertions.

## Verification status

Passed here, source only:

- The original immutable 09:27 baseline directory is untouched: all 20 of its manifest members still match. The candidate deliberately changes the host and listed support files; this is not a claim that every candidate file matches the baseline.
- Exact reproducible host/patch/metadata derivation from the pinned base.
- Nine original stock-tool source contracts, six retained standalone contracts,
  and eight new dispatch contracts: 23 Python tests.
- Lexical delimiter checks on all candidate Racket sources.
- Reverse the exact new import and stock dispatch branch and the whole host
  matches the original 09:27 host SHA-256. This proves all unrelated host bytes,
  original follow-on cases, timing, diagnostics and capture remain unchanged.
- Original tools, checked coordinator, old headless regression and standalone
  driver hashes remain exact.

Not run here: Racket reader/expansion/compilation, the new headless executable,
or any repaired native gate. No Racket process, runtime/package operation,
installation/download or remote action was attempted. A Python source pass is
not a Racket compilation or native pass.

## Native owner handoff

Copy the seven files pinned by `FROZEN-NATIVE-ALLOWLIST.json` into a new complete
candidate. Preserve old dependencies and stock/modern isolation. Compile all
seven on official full Racket 9.3. Keep the old direct coordinator positive and
typed-negative checks unchanged. Add these direct checks in both runtime arms,
under the existing 30-second headless supervisor:

```
RACKET -A ADDON -R COMPILED_ROOTS tests/native-tool-dispatch-standalone.rkt
RACKET -A ADDON -R COMPILED_ROOTS tests/native-tool-dispatch-standalone.rkt --inject-wrong-result
```

Positive: exit 0 and exactly one complete line:

```
OPENRACKET_NATIVE_TOOL_DISPATCH_OK distinct-thread strict-failures cleanup-complete
```

Negative: nonzero exit other than timeout, no positive marker, exactly one of
each line:

```
OPENRACKET_NATIVE_TOOL_DISPATCH_INJECTING_FAILURE
OPENRACKET_NATIVE_TOOL_DISPATCH_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong
```

After those pass, rerun pristine stock's debugger, macro-stepper, and teaching
cases independently, followed by unchanged modern-dark cases. Keep the 60-second
native supervisor, original 20-second waits, real controls, independent profiles,
failure screenshots, READY reports and typed refusal validators. A repaired
dispatcher is not itself proof that the subsequent tool assertions pass.
