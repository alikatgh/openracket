# Native retained-host benchmark

This harness measures the actual installed DrRacket 9.3 frame, editor and eventspace.
It never disables tools, changes evaluator instrumentation, changes memory limits,
replaces editors, installs packages, patches production sources, or starts a display
server. Run it only in an authorized native CI session.

## Single-mode invocation

    python3 performance/run.py --mode pristine-stock --racket /path/to/racket --output reports/performance-pristine-stock --repetitions 3 --timeout 60

Repeat with `--mode modern-dark` after the CI owner applies the guarded overlay and
sets the appearance environment. `--mode` is a reporting label only. The caller owns
source version, installation, tools, patch, display and environment settings. The
runner preserves `PLTADDONDIR` and creates a fresh `PLTUSERHOME` per trial. Run stock
before patching any stock source. This initial ordered design may favor the second
mode through OS file caches; repeat in counterbalanced order before a speed claim.

Each mode has six fresh-process trials: 100,000 ASCII characters and 1,048,576 bytes,
three trials each. Both are deterministic mixed-Racket modules with comments,
strings/escapes, regexp literals, quasiquotation, nested forms, vectors and numbers.
Exactly matching SHA-256s and file sizes are included in every record. This initial
fixture does not cover pathological long lines, WXME, Unicode shaping or all tools.

The supervisor terminates a timed-out trial's process group, records partial results
and failure, then continues remaining trials. After two consecutive pre-GUI startup failures it
stops that mode and explicitly marks the remaining trials as not run. It never quietly omits a timeout.
Each trial emits its complete JSON between `OPENRACKET_PERFORMANCE_TRIAL_JSON_BEGIN`
and `_END`; mode summaries use the analogous `SUMMARY` markers. No artifact upload
or cache upload is performed by this harness.

## What timings mean

- `fresh_process_gui_startup_ms`: start of benchmark module body through a shown real
  DrRacket frame, including dynamic GUI/DrRacket imports. Excludes interpreter and
  benchmark-module startup before its body. It is not cold disk-cache startup.
- `first_open`: first stock `change-to-file` in a fresh process; includes the editor's
  normal load callbacks. The source length is checked after loading.
- `first_jump`: caret and scroll to a previously unvisited near-end position without
  first waiting for coloring to finish. It is not guaranteed that coloring remains
  unfinished on every machine; `lexer_valid_after_first_jump` records the fact.
- `first_edit`: move to a middle-file comment and send one ordinary `key-event%` to
  the retained editor's `on-char`, checking that one character really appeared.
- `initial_lexer_settle`: wait for consecutive valid-lexer observations, bounded45s.
  This is not a promise that online expansion or every tool has become idle.
- `warm_editor_key_samples`:80 serial editor key events after lexer stabilization,
  with16ms pauses after each fence. Counts and exact inserted text are asserted.
- `warm_jump_samples`:12 alternating top/end caret-and-scroll operations.
- Every action reports synchronous `command_ms` and elapsed time through the next
  low-priority eventspace fence. A fence is not a paint/presentation completion.
- A16ms worker heartbeat has at most one queued callback. Both enqueue-to-dispatch
  delay and inter-callback gaps are retained, so a delayed enqueue/thread cannot
  conceal a long gap. These are event-loop responsiveness probes, not physical
  input, OS key dispatch, compositor latency, frame rate or input-to-photon.
- Memory snapshots distinguish Racket-managed bytes, GC time, and native process
  peak RSS from `/usr/bin/time` (Linux kilobytes are converted to bytes; macOS uses
  bytes). Explicit GC runs only after all latency measurements. Peak RSS and managed
  bytes differ and must not be substituted for one another.

All widget work runs on the actual eventspace handler thread. A failed load,
unapplied key event, invalid lexer after the limit, crash or timeout is a failed
trial, not a speedup. Raw samples are available; median/p95/p99/max are descriptive
nearest-rank statistics. Three process trials do not support robust tail/startup
claims, and the80 key events within a trial are not80 independent app startups.

## Comparability and scope

Compare the same runner job/hardware, OS, Racket release, fixture hash, display size
and scale, installed tools, memory limit, default instrumentation, coloring,
online compilation and overview settings. The report reads these preferences and the actual selected language settings but
does not change them. Instrumentation is resolved through the stock language-info
API and serialized language settings, not a nonexistent instrumentation preference. Appearance/font/layout differences are intentional; they
may affect the number of visible lines. No Run, Check Syntax, debugger, macro or
teaching-tool performance is measured here. Their correctness gate remains separate.
The pristine stock comparison is mandatory: stock-painter fallback in a patched
module is not pristine stock.

No application speed result exists until the native CI command has actually
completed. The earlier Rust/Syntect experiment has a different editor/workload and
is not a retained-DrRacket baseline.

## Headless validation

    python3 performance/test_harness.py
    raco make performance/retained-host.rkt

These checks validate generation, statistics, memory units, timeout reporting and
Racket expansion only. They do not prove that native DrRacket APIs ran successfully.

## First native diagnostic run

Run38047260644 (commit e859f18) compiled the native GUI and tools but produced no
performance samples: all twelve stock/modern trials were blocked before GUI
readiness. Stock queues its initial-frame callback and only then reads launch
arguments; a temporary parameterization had already ended, exposing benchmark
arguments as filenames and opening an ordinary missing-file dialog. The repaired
harness sends configuration through OPENRACKET_BENCH_CONFIG with no process
arguments, creates the actual frame, then uses its normal change-to-file method. This
is a harness repair; the first run cannot support a speed/regression claim.

The repaired harness records actual GUI argv, the loaded filename/prefix, and any
shown startup dialog's title/child labels/editor text. It never dismisses an
unrecognized dialog. `diagnose-startup.rkt` is a separate, bounded read-only legacy
launch reproduction, not part of the latency workload or a performance sample.

Run38050213153 reached the repaired benchmark, but no workload timings were usable:
DrRacket's custodian context rejected an attempt to kill the startup monitor. Monitor
shutdown now uses a cooperative flag and a thread-death event; no stock custodian
or security setting is changed. The macOS timeout supervisor also exposed an exited
process-group signaling race. Cleanup now checks native live group membership,
still kills surviving descendants, and fails on a genuine permission/cleanup error.
Headless regressions include a different-custodian monitor and a descendant that
ignores SIGTERM. Run `raco test performance/lifecycle-test.rkt` in addition to the
Python tests. These repairs still require the next native benchmark run.


## Separate attribution probe

    python3 performance/run.py --mode pristine-stock --racket /path/to/stock/racket --output reports/stock-attribution --fixture mixed-1mib --repetitions 1 --timeout 90 --profile

This is exactly one process and one1MiB fixture. It enables the existing Racket
statistical sampler on the actual GUI eventspace handler at10ms nominal intervals,
stock framework/colorer and online-expansion loggers, GC log messages, and bounded
handler-stack observations when the heartbeat is over100ms old. It changes no tool,
lexer, evaluator, memory-limit or custodian setting. Captures are capped at20,000 log
records,100 stalled-stack observations and64,000 profile-text characters; dropped
records and truncated text are explicit. It uses the official full distribution's
profile-lib; the local minimal installation cannot execute that optional probe.
See the official Racket [statistical profiler documentation](https://docs.racket-lang.org/profile/index.html).

The report's measurement_kind is instrumented_attribution_only. Sampling and
logging add overhead, and their timings must not be used as another ordinary
stock/overlay comparison. A collector may itself be delayed by GC or a native
call; absence of a sampled stack is not proof of responsiveness. Logs are from the
main place's logger hierarchy, not a claim to observe every separate worker place.
The one-process wrapper has the normal complete/timeout/failure semantics and
prints the normal TRIAL/SUMMARY JSON markers, with a separate diagnostics object.

The instrumentation metadata reader now uses the documented simple-settings vector
and its sixth annotations field. Racket9.3's individual public annotation accessor
has a result contract that rejects the valid lang-default value; this read-only
workaround preserves that value and the complete serialized language settings.
No original paired baseline file is replaced by later diagnostic results.

## Read-only language metadata probe

Use the same bounded supervisor for a short, separate native probe:

```
python3 performance/run.py --mode pristine-stock --racket "$STOCK_RACKET" \
  --output reports/stock-metadata --fixture mixed-100k --repetitions 1 \
  --timeout 30 --metadata-only
```

Run separately with the modern runtime/environment to establish paired metadata
agreement. This opens the fixture and captures settings; it does not wait for the
full lexer or run the latency workload. Its `measurement_kind` is `metadata_only`.
Exit 0 requires complete metadata; a partial result preserves all successful fields
and errors and exits nonzero. Ordinary trial/summary JSON markers are unchanged.

`settings.rkt` uses documented `get-next-settings`, exported language/settings
accessors, and the six-element `simple-settings->vector` API. The raw annotation
setting is retained. The default is independently resolved with public
`read-language` on the immutable fixture's unchanged `#lang` declaration and its
`drracket:default-instrumentation` info key (stock fallback `debug`). This records
pending next-Run configuration and reader-default resolution, not current evaluator
instrumentation. It does not call private `get-irl` or change any settings. Failed
fields cannot discard other successful metadata.

For subsequent ordinary/profile runs, metadata imports occur after all latency
sampling and after the profiler stops. The heartbeat's initial timestamp now starts
with the heartbeat, rather than with process launch. Earlier frozen records remain
unchanged; their attribution first-open heartbeat ages included startup, and late
`initial_lexer_settle` profile samples included metadata import work.

Headless metadata checks: `racket performance/settings-test.rkt`.
