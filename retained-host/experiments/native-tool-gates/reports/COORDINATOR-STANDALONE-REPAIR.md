# Standalone coordinator regression driver

## Native finding

Mac run [38125605788](https://github.com/alikatgh/openracket/actions/runs/38125605788)
reported two failures in ten checks when `raco test` loaded the coordinator test
submodule. Its separate handler intentionally executes exactly two failed
RackUnit checks, and the coordinator returns their exceptions to surrounding
`check-exn` assertions. The native aggregate did not include individual failure
details. This is consistent with aggregate accounting of the intentionally
failed checks; it does not establish a broken product or coordinator.

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
the actual RackUnit failure identifying `actual` and `deliberately-wrong`.
Its injection is after the entire unchanged regression returned. This prevents
an unrelated import/parse failure from counting as the expected negative result.

Do not invoke this regression through `raco test` for acceptance, suppress
unexpected exceptions, remove the intentional failed checks, or weaken the
native tool cases. The six independent stock/modern-dark native tool cases are
still pending. No delivered preview or runtime source is changed.

## Local validation

Three new Python source contracts and nine original source/orchestration
contracts pass. They pin the original coordinator/test hashes, enforce the
strict direct-driver boundary and marker ordering, and check lexical delimiter
integrity. This is not a local Racket execution or a native pass. Independent
source review by the performance owner found no blocking issue. Positive and
injected-negative native runs remain mandatory.
