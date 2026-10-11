# Stock Mac memory-limit sensitivity

This is a configuration experiment on pristine Racket 9.3, not a code-speed
optimization or a change to the delivered preview. The prior xref reply-cell
candidate showed no reliable GUI speed improvement and is absent here.

## Fixed workload, varied setting

Only the registered `drracket:child-only-memory-limit` preference varies:
128, 256, or 512 MiB (134217728, 268435456, or 536870912 bytes). It governs the
accounted background job and the Run evaluator; it is not an app-wide RSS cap or
a cumulative-allocation limit. Memory accounting must be available in the actual
worker. All tools, actual online prefab, pending-next-Run instrumentation,
coloring, stock 20 ms budget and appearance remain identical.

Use the existing 1 MiB fixture, middle-comment `x` + 80 paced `a` keys, 1000×700
window and complete final-source checks. The GUI workload is byte-identical to
the verified xref measurement after removing only its measurement label and new
requested-limit metadata line. The common observer helper/generator and inserted
stock-module bytes are unchanged. A regression pins these facts.

Run nine fresh trials in these rotations:

1. 128, 256, 512 MiB
2. 256, 512, 128 MiB
3. 512, 128, 256 MiB

Use one independently deep-cloned pristine runtime, with only the common observer
inserted. No xref, scan, autosave, appearance or smaller-budget candidate is
installed. Each invocation needs its own new `PLTADDONDIR`; the supervisor creates
a new `PLTUSERHOME` beneath its unique output directory. Read actual runner RAM;
CI requires at least 4 GiB. Do not change host swap or system memory settings.

## Legitimate preference setup before timing

The supervisor invokes `profile/memory-profile.rkt` as a separate headless
process. It resolves and hashes the actual original preference-registration
module and Framework preference API before importing them. It requires a fresh,
empty, nonoverlapping home/addon profile and refuses outside/fallback preference
stores. After confirming the original default is 128 MiB, it uses the registered
public `preferences:set` to persist exactly one key. It verifies public cached
readback, a forced disk reread and a bounded direct parse of the store; every
other entry must be unchanged. Python independently verifies the actual store
hash before the GUI launches.

This happens for all three values, including explicit 128 MiB. The setup record
exists before the measured process timer starts. The timed GUI receives the same
home/addon profile, without importing the setup helper or setting any preference
itself. Native tests also perform an independent second-process persisted read.
A setup refusal produces a retained `setup_failed` trial and never launches GUI.

Setup has a separate 30-second bound. The measured process remains bounded at
60 seconds; its lexer and later final-tool observation gates remain 45 and
15 seconds. A larger outer CI supervisor envelope includes setup plus process
cleanup and does not extend any GUI measurement deadline. Preserve every failure,
partial record and timeout; do not lengthen limits to obtain a desired result.

## Native gates and commands

Before any trial, run all helper tests with explicit native arguments:

```sh
python3 profile/test_memory_profile.py \
  --racket "$RACKET" --runtime-root "$RUNTIME_ROOT" -v
python3 observer/test_source.py
"$RACKET" observer/test_support.rkt
(cd performance && python3 -m unittest -v test_harness test_observation test_profile_setup)
```

For observer source tests, set `OPENRACKET_TEST_STOCK_PRIVATE` to the unmodified
clone's resolved DrRacket private source directory. These tests and native
profile/helper execution must not silently skip. Apply the observer with its
existing pin-checked `prepare.py`, explicitly compile the actual caller/helper
modules, verify original xref and all excluded-candidate sources, and run the
stock real-host Check Syntax smoke before timing. Preserve the untouched
reference runtime full-tree comparison.

Example single trial (repeat with new output/addon paths for every matrix cell):

```sh
PLTADDONDIR="$FRESH_ADDON" python3 performance/run.py \
  --mode memory-256 --racket "$RACKET" \
  --output reports/memory/round-1-limit-256 \
  --repetitions 1 --fixture mixed-1mib --timeout 60 \
  --memory-limit-mib 256 \
  --profile-helper "$ABSOLUTE_ROOT/profile/memory-profile.rkt" \
  --observer-support "$ABSOLUTE_ROOT/observer/support.rkt"
```

No `OPENRACKET_XREF_REPLY_CELL` variable may be present. The CLI accepts only
stock xref and verifies its exact source hash/export absence in the real worker.
It clears inherited experimental controls before starting setup and GUI.

## Required records and interpretation

Every trial retains:

- `expected_memory_limit_bytes`: requested experimental value
- `memory_profile_setup`: bounded setup process status, helper hash, errors and
  elapsed time explicitly outside the timed process
- `memory_limit_configuration`: exact selected/readback/persisted bytes, source
  pins, real home/addon/store paths, store hash and one-key delta
- Actual GUI `preserved_settings["drracket:child-only-memory-limit"]` as a decimal
  string, and worker `child_memory_limit` as an integer plus
  `memory_accounting_available: true`
- Original complete settings/prefab/handler/source association and final terminal,
  monitor message/error counts, actual current callback and lexer completion
- Planned/queued/editor/fence key samples, phase heartbeat gaps, GC/allocation
  counters, managed memory and external maximum RSS
- Common-observer registration/hook and worker one-shot costs

Compare metadata exactly across the nine cells except the explicitly selected
memory value and per-trial path identities. Normalize verified runtime/profile
paths, never drop unrelated settings. All three independent views (setup disk,
GUI preference and actual worker) must equal that cell's exact requested value.

A valid OOM remains an unsuccessful background-tool outcome. A successful
analysis requires `handler-results`, at least one actual monitor message, zero
string/unknown-shape monitor errors, exact final source and the completed current
GUI callback. `finished-expansion` or a valid lexer alone is insufficient.
Different success/OOM outcomes preclude an equal-work throughput ratio, while
capacity changes are reported separately. Typing comparisons additionally retain
whether coloring was actually pending at each key. Counters are cumulative
churn, not RAM or per-thread allocator ownership. Larger limits may trade fewer
capacity failures for longer pauses/higher RSS; no improvement is assumed.

Transport full measurements, summary, raw `memory-profile.json`, and both worker
JSON files using the existing lossless byte-chunked/digest-checked log encoder.
Retain round/limit labels, native helper failures, all raw observations and the
original failed xref experiment. No payload dump or artifact upload is needed.

Local Python checks are available. New profile helper native validation remains
pending CI; the unchanged common observer was native-verified in run38106066111.
