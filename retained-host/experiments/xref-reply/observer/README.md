# Compact native online-expansion observer

This is a separately identified, default-off observer for matched DrRacket 9.3
GUI performance arms. It is **not** the historical uninstrumented baseline or
the full expansion-replay capture harness. This directory is the only owned
workspace; recovered/frozen sources were read, never modified.

## Caller contract

Use a new disposable runtime clone, fresh per-run output directory, and these
environment variables **in both measured arms**:

- `OPENRACKET_COMPACT_OBSERVER=1`
- `OPENRACKET_COMPACT_OBSERVER_SUPPORT=/absolute/path/to/support.rkt`
- `OPENRACKET_COMPACT_OBSERVER_OUTPUT=/absolute/existing/run-directory`

The candidate flag remains independently controlled by the host:
`OPENRACKET_XREF_REPLY_CELL=1`. The observer never sets it.

In the initial GUI place, load that exact support path and call once, before
opening the fixture:

```racket
((dynamic-require support-path 'observer-register-final!)
 expected-final-string #:generation "final-81" #:source fixture-path)
```

Use an immutable `expected-final-string` if the caller retains it too, to avoid
an extra immutable copy. Registration retains one expected final snapshot and
hashes its UTF-8 representation once. The original request observer tests the
source path, string length, then exact string equality. Only exact matches reuse
the registered SHA-256. It never hashes each request or retains request payloads.
WXME bytes cannot match the plain-text fixture. No environment dump is captured.

After the existing workload timing endpoints, poll the cheap zero-argument
`observer-final-outcome`. It returns `#f` until the **newest matched final
request** has a terminal response and the original native GUI callback has
completed with `callback_current` true. It also returns `#f` after observer errors
or request-cap overflow. A new matching request invalidates an older completed
outcome until that new request completes. Stale callbacks remain in the full
summary, but cannot satisfy this completion query.

The returned immutable record has:

- `request_id`, `generation`, `source_match`, `final_match`, `snapshot_sha256`
- `actual_prefab` (original six-field request's prefab field 3, bounded
  default-writer text) and `actual_prefab_truncated`; reject truncation for an
  exact effective-settings comparison
- `request_ms`, `status`, `status_ms`, `terminal_ms`
- `terminal.tag`, `terminal.explicit_out_of_memory`, `terminal.abnormal_message`
- `callback_entered_ms`, `callback_current`, `callback_delivered_ms`
- `monitor_messages`, `monitor_pair_messages`, `monitor_empty_messages`,
  `monitor_string_errors`, `monitor_other_messages`, `monitor_errors`

Monitor metadata uses only constant-time shape tests on the original payload;
there is no trace traversal, trace-length calculation, or payload retention.
At most four 512-character monitor error prefixes are kept per request, each
with a truncation flag and bounded handler key. Counted monitor errors are never
hidden by a subsequent `handler-results` terminal. **A returned final outcome
is an observed result, not a success verdict.** For a successful final expansion,
the caller must require the intended terminal tag, zero monitor string errors,
no unexpected monitor shapes, and its other acceptance criteria. OOM/other
errors still complete the outcome query and must remain visible.

Call `observer-summary` once after timing (also on a failure path where possible)
and persist it outside the key/lexer endpoints. It returns up to 512 request
records including prior outcomes and unanswered requests. `complete_observation`
means no observer errors or overflow, **not** that every request completed or
the final expansion succeeded. `observer-final-terminals` is an optional full
list query; do not use it for repeated polling.

## Kill-safe observation

Every GUI update constructs a pure immutable successor and commits it with
`box-cas!`. There are no observer semaphores or locks. A hook killed or suspended
before commit leaves the complete old state; a hook killed after commit leaves
the complete successor. Queries unbox one immutable snapshot and cannot wait
for a killed writer. Concurrent writers retry their pure transition after a CAS
conflict. No unsafe atomic sections, callback cleanup assumptions, or new
production threads are used.

A private test submodule exposes a default-disabled commit checkpoint. Native
headless tests pause real request/status/response hooks immediately before and
after the shared CAS commit, terminate them by both `kill-thread` and custodian
shutdown, and check that summary/outcome queries and later hooks remain bounded
and responsive. These are 12 deterministic kill scenarios; they still require
execution in native CI. This design deliberately does not assume that
`call-with-semaphore` escape cleanup proves arbitrary thread-kill cleanup.

## Actual worker activation evidence

The only worker insertion is immediately **after all actual native handler
imports** and before the original receive loop. It obtains the actual imported
handler key/monitor-flag pairs, calls `module->namespace` to prove xref was already instantiated,
then reads `openracket-xref-reply-cell-enabled?`. The `dynamic-require` missing
export failure thunk classifies pristine stock's absent export. Lookup/load
errors are printed as explicit observer failures and return false without a
successful init file; they never become stock missing-export evidence. Native
handler-import failures occur before the observer and are unchanged.

The worker writes `worker-init.json` once, with:

- `worker_context: true`, event `worker-init-after-handler-imports`
- `actual_handler_registry` from the real imported handler objects, preserving
  order; each row has resolved `module`, original `module_spec`, `export`,
  and `monitor`; registry paths and module specifications are not truncated
- `xref_already_instantiated`, `xref_path`, source `xref_sha256`
- `xref_export_status` (`missing`, `boolean`, or invalid `non-boolean`)
- `xref_reply_cell_enabled`, original `xref_flag`, actual child memory limit
- `memory_accounting_available`, read in the actual worker

The caller must check the expected real Check Syntax registry keys, frozen
source path/hash, flag/export state, and runtime version. Require
`child_memory_limit` equal to 134217728 and
`memory_accounting_available` true together, because the unchanged
stock worker applies its 128 MiB limit only when accounting is available.
The native helper test asserts both prerequisites. No evolving production xref
hash is hardcoded into this helper.
The file is one-shot evidence from this specific worker seam, not GUI-side
dynamic-require activation evidence. Existing evidence files are not overwritten.

## Honest observer-cost accounting

All instrumentation is identical in both arms. It adds:

- Source checks/equality and small settings formatting per actual request
- Constant-size counters per original monitor response; no trace walks
- Compact status/terminal/callback records in bounded immutable in-memory state
- Atomic box CAS commits and clock samples around observer helpers
- One retained final expected string, up to 512 metadata records, bounded errors
- One-time support module loading, xref source hash, and worker output

`registration_ms` measures registration. `hook_self_ms` is the **sum of elapsed
hook intervals**, including cached dynamic-require, CAS retries, and any scheduling
wait inside those intervals. It is not CPU self-time or a causal latency delta;
concurrent intervals may overlap. It excludes the small guard/dispatch seams
outside the timers and summary serialization done by the caller.

`worker-init.json` contains `observer_before_write_ms`. The separate one-shot
`worker-init-overhead.json` measures the primary evidence file's serialization,
write, and close as `primary_write_and_close_ms`, plus
`observer_through_primary_write_ms`. It explicitly excludes its own timing-file
write. These measurements do not quantify indirect GC/scheduling effects, heap
retention effects, or a complete causal observer overhead. Do not subtract them
from latency metrics or present them as zero-impact proof. Worker and GUI
durations use their own monotonic clock differences, not cross-place timestamps.

No settings, handlers, custodian ownership, logger levels/receivers, native
request or response fields, debounce timers, compilation policy, or original
state-machine code are changed. Disabling the opt-in flag skips helper loading
through all inserted native hooks. The caller should separately retain an
uninstrumented baseline when making historical comparisons.

## Generator and verification

`prepare.py` verifies both exact official source SHA-256 pins before editing.
Every source change is a delimited insertion. Removing those inserted blocks
recovers the original files byte-for-byte. Reapplication and unpinned sources
are rejected. The generator does not carry or apply the xref candidate patch.

Offline staging, with no stock-source edits:

```sh
python3 prepare.py --source-private /path/to/pinned/drracket/private --emit /new/output/directory
```

Application to an independently deep-cloned disposable runtime:

```sh
python3 prepare.py --diagnostic-root /disposable/runtime --racket /disposable/runtime/bin/racket
```

The executable and resolved caller/worker must be inside the clone. Source
hardlinks/symlinks and an external/symlinked compiled directory are rejected.
The generator invalidates only caller/worker bytecode in that clone, compiles
the helper and instrumented files, and emits a provenance/compile manifest.
`--skip-compile` is only for a separate explicit native CI compile step.

Checks:

```sh
python3 test_source.py
OPENRACKET_TEST_STOCK_PRIVATE=/exact/stock/private python3 test_source.py
/already/available/racket test_support.rkt
```

Python source tests pass locally. The Racket helper tests cover exact final
association, source mismatch, same-length mismatch, WXME exclusion, stale and
repeated final callbacks, OOM/other errors, monitor error/shape metadata, bounded
settings, record overflow, disabled/single-shot registration, already-loaded worker export detection, and 12 kill/custodian-shutdown
scenarios. They exit nonzero on failures. **They have not run in
this workspace because no Racket executable is installed.** Native CI must
compile/run them before GUI trials. Their mock worker modules and synthetic
response vectors test the helper contract; they do not establish native GUI
activation, successful online expansion, or performance.
