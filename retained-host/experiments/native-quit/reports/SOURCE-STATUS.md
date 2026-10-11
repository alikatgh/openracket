# Source preparation status

2026-10-11. Separate test-only working tree; product0520, accepted app builder,
accepted read-only observer and publication45 source inputs remain unchanged.

Passed locally without Racket:

- 20 independent protocol/configuration/report validator tests, including
  false-success refusals for bad tokens, missing screenshots, wrong PID/image,
  changed live objects, incorrect disk data, missing modal responses, focus not
  restored, changed checkbox/parent/attempt binding, nonzero/signal/late exit,
  cleanup, replayed/reordered stages, NaN/Infinity/float overflow/oversized integers and inexact IDs/counts.
- 11 source/lexical checks: preserved source inputs and unchanged identity reader,
  inert driver without configuration, zero-argument Quit getter only, genuine
  stock button callback, no direct Save/Close/modified reset/handler replacement,
  failure-only test exit, observed Cancel focus return, native supervisor bounds,
  Python parsing and lexical Racket delimiter balance.
- 5 pure plist fixture tests: removal of only document associations, exact native
  bytes, no rewrite if the key is absent, refusal of unexpected metadata and an
  already-prepared app, plus linked Contents/Info.plist/MacOS/native-component
  refusal with unchanged outside witnesses. Fixture bytes are explicitly not native executables.
- All14 retrieved GUI/DrRacket official source files in the source-review cache
  were byte-verified against their Git blob IDs before source pins were recorded.
  The exact core generator and framework signature source was separately read
  and backed up. Official source was not installed or executed.

Not run:

- Racket parsing/expansion/compilation and the8 real pure RackUnit contracts.
- Official-generator stock control creation and native metadata/identity probes.
- Private package registration and all six genuine GUI cases.
- OS screenshots, actual Save/Cancel/Don't Save effects, natural child exit0.
- New whole-runtime/preferences/default-handler preservation gate.

The driver deliberately invokes the installed public Quit thunk and real shown
stock dialog callbacks, while the independent supervisor owns acceptance. Its
passed result proves installed application Quit handling only, not a new Finder,
input-device or Apple-event route. There is no successful test-side exit path.

No remote mutation, GitHub publication/trigger, package archive download,
installation or local native execution was performed. Fresh publication approval
and parent-owned free-native workflow integration are still required. The
existing57-row tool run and114-check app run are unchanged historical results.
