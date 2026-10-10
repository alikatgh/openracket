# Separate stock break-delivery diagnostic

`stock-break-delivery-control.rkt` is an isolated stock-runtime control, not a
replacement for the original strict DrRacket Stop acceptance case.

Run each mode in a **fresh process**, with the exact pristine Racket 9.3 executable
and stock addon registry. No overlay/tool package is loaded:

```
racket stock-break-delivery-control.rkt plain-racket
racket stock-break-delivery-control.rkt gui-worker-nested
racket stock-break-delivery-control.rkt gui-eventspace-nested
racket stock-break-delivery-control.rkt gui-eventspace-returning
```

Use a 35-second external process-group bound for each mode, and collect all four
results independently. Each has a 5-second body-ready bound and the original
20-second break-completion bound. The target sleeps for 120 seconds so normal
completion cannot accidentally pass the break assertion. GUI waits use the same
20ms yielded polling pattern as the existing host workflow. No screenshots are
required because these controls create no windows.

- `plain-racket`: ordinary Racket thread, without importing GUI.
- `gui-worker-nested`: ordinary Racket thread after GUI import, interrupted and
  awaited inside a yielded GUI callback.
- `gui-eventspace-nested`: separate GUI eventspace handler, with DrRacket's public
  `#:suspend-to-kill? #t` and explicit enabled break parameterization, interrupted
  and awaited inside a yielded GUI callback.
- `gui-eventspace-returning`: same handler setup, but the interrupt callback
  returns to the dispatcher before the caller waits for completion.

Every stage emits bounded `OPENRACKET_STOCK_BREAK_CONTROL` JSON with runtime
version, mode, observed break-enabled state, eventspace-handler identities,
liveness, caught-break outcome, timing and up to twelve continuation entries.
`break-thread` targets only the control's own synthetic worker. It never targets
a DrRacket evaluator. Cleanup shuts down only the control's owned child custodian.

## Interpretation

These cases locate a layer; they do not by themselves prove an upstream bug.
If only the nested-handler mode fails while the returning variant passes, the
existing test's nested dispatch strategy becomes a concrete suspect. If all four
pass, the remaining issue is specific to the real DrRacket evaluation path or its
interaction with the host harness. In every outcome, retain the original Stop
fixture and its strict completion assertion until its behavior is understood.

Local verification: the non-GUI mode passes with the installed stock 9.3 runtime,
and `raco make` passes. GUI modes have not been run locally; the original native
display denial remains respected.
