# Standalone coordinator regression driver

Historical repair note. Its findings and exact negative-control outputs are retained
for provenance; this is not the current payload/integration contract. Use
`NATIVE-CLI-CONTRACT.md`, `UI-REPAIR-API-PROOF.md`, and the root nine-file
`FROZEN-NATIVE-ALLOWLIST.json` for the current revision.

## Native finding

Mac run [38125605788](https://github.com/alikatgh/openracket/actions/runs/38125605788)
reported two failures in ten checks when `raco test` loaded the coordinator test
submodule. Its separate handler intentionally executes exactly two failed
RackUnit checks, and the coordinator returns their exceptions to surrounding
`check-exn` assertions. The native aggregate did not include individual failure
details. This is consistent with aggregate accounting of the intentionally
failed checks; it does not establish a broken product or coordinator.

## Follow-on native evidence and diagnostic rendering repair

Mac run [38127332821](https://github.com/alikatgh/openracket/actions/runs/38127332821)
compiled both stock and modern drivers and passed both positive executions.
Both injected negatives printed the unique injection marker and exited 1, with
RackUnit stack locations, but the default uncaught-exception rendering omitted
the actual/expected check-info values. The CI checker correctly rejected these
as insufficient evidence. See the archived macOS log at lines 314–354. This
repair changes only the direct test driver's diagnostic rendering and source
contracts; it does not relax the CI validator.

The baseline is the 20-member `openracket-native-tool-gates-freeze-20261011-0900`
manifest, SHA-256
`753839e4a470ebf9fb33a95f4100b3954a6f55718cc14c3310cc7cc46d2bd1bc`.
All 20 baseline member hashes were verified before copying into a separate
working tree. The baseline freeze was not changed.

### Failure boundary and evidence

The outer `with-handlers` is inside the injected-negative branch and wraps only
the deliberate `(check-equal? 'actual 'deliberately-wrong)`. The original
regression's `dynamic-require` is outside that handler and still runs under
`current-check-handler` set to `raise`.

The handler accepts only `exn:test:check?`. From that exception's
`exn:test:check-stack`, it requires exactly one `name`, `actual`, and `expected`
entry. It verifies `name` is `check-equal?`, both operands have the Racket 9.3
`pretty-info` wrapper, and their unwrapped values are the exact symbols
`actual` and `deliberately-wrong`. Only then does it print a single bounded
machine-readable line using those extracted values:

```
OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong
```

All rendered fields are restricted to these fixed symbols before printing.
There is no general exception/stack dump or unbounded user-data rendering.
Missing, duplicate, different-type, or wrong-value evidence cannot emit this
line. The same original exception object is always re-raised with
`(raise failure)` after the conditional renderer. A nested catch surrounds only
check-info inspection and diagnostic output; its handler does nothing if any
value is raised while inspecting or printing. The original re-raise is outside
that nested catch. Thus a diagnostic failure, including an output-port error,
cannot replace or swallow the captured check failure. This catch never wraps
the original regression, the deliberate assertion, or the original re-raise,
and it emits no fallback evidence or success marker. The failure is never converted into
success or replaced with a synthesized RackUnit exception. Other exception
kinds bypass the handler entirely. The existing success line and `exit 0`
remain reachable only after all real checks return, and therefore cannot be
reached after the deliberately failing assertion re-raises.

### Pinned authoritative Racket 9.3 API evidence

The official [RackUnit v9.3 tag](https://api.github.com/repos/racket/rackunit/git/ref/tags/v9.3)
points to annotated tag object
[`12be79f55fa40be6de5d5495d7bce98edb5aa21f`](https://api.github.com/repos/racket/rackunit/git/tags/12be79f55fa40be6de5d5495d7bce98edb5aa21f),
which points to commit `71937593a0eacd9e6b20dbecaceb91fb13ebac42`.
The following files were read through the GitHub connector from that release
ref/commit on 2026-10-11; the immutable links pin the reviewed source.

- [`main.rkt`, lines 29–34](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/main.rkt#L29-L34)
  re-exports `private/test.rkt`. Git blob SHA:
  `cefd41efcc9280245f9d67cc1f379b6dc134f086`.
- [`private/test.rkt`, lines 12–24](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/test.rkt#L12-L24)
  exports the `exn:test:check` and `check-info` structures, including their
  predicates/accessors. It does not re-export `pretty-info`. Git blob SHA:
  `de5a12c595db9dcc1903d4554d3712452be96c06`.
- [`private/base.rkt`, lines 20–30](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/base.rkt#L20-L30)
  defines the RackUnit check exception with its `stack` field. Git blob SHA:
  `0447099367493151d1ddbfc360a615508c921064`.
- [`private/check.rkt`, lines 77–79](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/check.rkt#L77-L79)
  shows `fail-check` constructing `exn:test:check` with the current check-info
  stack and an empty default message.
  [Lines 160–170](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/check.rkt#L160-L170)
  add actual/expected info for binary checks, and
  [line 260](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/check.rkt#L260)
  defines `check-equal?` through that macro. Git blob SHA:
  `b9692f66ad37e9446c2506edf5017d5caeb74c27`.
- [`private/check-info.rkt`, lines 12–20 and 121–127](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/check-info.rkt#L12-L20)
  exports the `pretty-info` structure and wraps actual/expected operands with
  it. [Wrapper definitions](https://github.com/racket/rackunit/blob/71937593a0eacd9e6b20dbecaceb91fb13ebac42/rackunit-lib/rackunit/private/check-info.rkt#L121-L127).
  Git blob SHA: `7ccb8c074bec7030708816d291c0151128ec06fc`.

Thus comparing `check-info-value` directly with the symbol would be wrong on
this pinned version. The driver explicitly imports only `pretty-info?` and
`pretty-info-value` from `rackunit/private/check-info`. This private dependency
is confined to the version-pinned test driver and must be rechecked if the
Racket/RackUnit release changes. It is not a product/runtime dependency.
The documented public exception/stack and check-info contracts also appear in
the [RackUnit internals](https://docs.racket-lang.org/rackunit/internals.html?version=9.3)
and [API](https://docs.racket-lang.org/rackunit/api.html?version=9.3) references.

## Bounded repair

The new `tests/native-tool-coordinator-standalone.rkt` runs the same test
submodule directly under a raising outer RackUnit handler. All original test,
coordinator, host and tool source bytes remain unchanged. The original
`dynamic-wind` stops and joins the separate handler before the direct driver
can print its success marker.

Run the standalone module using each actual stock/modern runtime and its fresh,
isolated preferences/addon/compiled-root environment. Compile the driver and
existing modules first. Each direct execution retains the 30-second outer bound:

```
RACKET -A ADDON -R COMPILED_ROOTS tests/native-tool-coordinator-standalone.rkt
RACKET -A ADDON -R COMPILED_ROOTS tests/native-tool-coordinator-standalone.rkt --inject-outer-failure
```

Positive acceptance requires exit 0 and exactly one complete line:

```
OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete
```

The second command is a deliberate negative control. It must finish with a
nonzero exit other than timeout, exactly one complete line
`OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE`, no success marker, and
the exact `OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE` line above, which identifies
the real caught RackUnit check exception and its inspected operands. The same
exception must then remain uncaught and terminate the process.
Its injection is after the entire unchanged regression returned. This prevents
an unrelated import/parse failure from counting as the expected negative result.

Do not invoke this regression through `raco test` for acceptance, suppress
unexpected exceptions, remove the intentional failed checks, or weaken the
native tool cases. The six independent stock/modern-dark native tool cases are
still pending. No delivered preview or runtime source is changed.

## Local validation

Six focused Python source contracts and all nine original source/orchestration
contracts pass on the diagnostic repair. They pin the original coordinator,
regression, host, and tool hashes; enforce the strict direct-driver boundary,
typed injected-only handler, diagnostic-only catch with the original exception
re-raise outside its scope, singleton check-info
extraction, wrapper/value guards, and unique marker ordering; and check lexical
delimiter integrity.

These are source checks, not a Racket reader/compiler or runtime execution.
No local Racket download, installation, execution, or native GUI run was
performed. New stock and modern positive/injected-negative native runs remain
mandatory on the repaired driver, followed by all six independent native tool
cases. Prior positive evidence applies to the baseline bytes only. CI and
remote state were not changed. Independent review of this diagnostic repair
is pending.
