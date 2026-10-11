# Matched xref reply-cell GUI measurement

This is a new, equally observed comparison of pristine xref and the isolated,
default-off reply-cell candidate on official Racket 9.3. It is not directly
comparable to previous uninstrumented, larger-window, or settled-key workloads.
The retained editor, online expansion, Check Syntax handlers, syntax coloring,
stock 20 ms cooperative budget, and stock 128 MiB child limit remain enabled.
No scan, autosave, appearance, or other optimization is enabled in either arm.

## Preparation and correctness gates

CI owns fresh independent deep clones and verifies collection resolution/source
hashes. Install only the reviewed xref patch in the candidate clone. Apply the
same sibling `observer/prepare.py` to both clones. Do not modify the pristine
reference runtime. Use fresh `PLTUSERHOME` and `PLTADDONDIR` for each purpose/arm;
the supervisor also creates a new per-trial user profile.

Before timing, require the native xref cancellation/concurrency tests, actual
Check Syntax/documentation/rename trace equivalence against stock and a
stock-again control, the observer's native `test_support.rkt` (including 12
kill/custodian scenarios), and compilation of this `retained-host.rkt` and its
helpers. The local Python suite passes; a local Racket runtime is unavailable.
These files are not claimed native-validated until those CI gates pass.

## Exact commands

First run local/source checks with:

```sh
python3 -m unittest -v test_harness test_observation
```

Each fresh trial uses the same command, changing only arm label, executable,
output path, expected xref hash, and the independently asserted candidate flag:

```sh
python3 performance/run.py --mode xref-stock \
  --racket "$STOCK_RACKET" --output reports/xref/stock/pair-1 \
  --repetitions 1 --fixture mixed-1mib --timeout 60 \
  --xref-activation stock \
  --xref-source-sha256 acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7 \
  --observer-support "$ABSOLUTE_OBSERVER/support.rkt"

OPENRACKET_XREF_REPLY_CELL=1 python3 performance/run.py --mode xref-candidate \
  --racket "$CANDIDATE_RACKET" --output reports/xref/candidate/pair-1 \
  --repetitions 1 --fixture mixed-1mib --timeout 60 \
  --xref-activation candidate \
  --xref-source-sha256 d2db0c6860040909c31c8fa9f7945ad5b94da3a03e751791447faeee7c27105f \
  --observer-support "$ABSOLUTE_OBSERVER/support.rkt"
```

Stock must have `OPENRACKET_XREF_REPLY_CELL` absent, not an empty or zero value.
Use three interleaved pairs: stock/candidate, candidate/stock, stock/candidate.
Every output directory is new. The CLI clears inherited `OPENRACKET_` variables
and then sets only its reviewed observer/config controls and the expected xref
flag. It never activates an optimization based on the mode label.

## Workload and endpoints

Each fresh process opens the same generated 1 MiB ASCII Racket fixture through
the genuine frame/editor route. The window is 1000 x 700 to fit the verified
1024 x 768 Mac runner desktop. After the synchronous open and near-end jump,
it inserts `x` at the fixed middle comment target and then exactly 80 `a` keys.
One off-GUI producer has at most one pending request. Its next planned deadline
is 16 ms after the previous fence, so this is closed-loop pacing, not a hardware
input stream. Each sample retains planned-to-submit delay, queue-to-handler,
queue-to-editor completion, command, and low-priority fence timing. Exact full
resulting source is checked after the latency intervals.

The unchanged post-typing lexer gate is 45 seconds. `open_to_completed_workload_ms`
is the open-to-observed lexer endpoint. A separate final-tool observation waits
up to 15 seconds afterward, still inside the same 60-second whole-process bound.
It requires the newest exact final-source request's original current GUI
callback to return. `open_to_terminal_callback_ms` uses that callback timestamp;
`open_to_terminal_callback_observed_ms` includes later polling/lexer observation.
Neither is physical input-to-photon. Original autosave cadence and other stock
background work remain active.

A one-outstanding-request heartbeat retains both dispatch delay and callback gap
by phase. It can be delayed alongside the producer by process GC. Scheduled key
deadlines and callback gaps expose delays that queue-to-handler alone can miss.
All partial trials and timeouts remain in the result set. The supervisor kills
and checks the entire timed-out process group, including a time-wrapper child.

## Acceptance and outcome interpretation

`observer_validation.verified` requires actual-worker initialization after real
handler imports, already-instantiated xref with the exact source hash and loaded
activation, clone-local resolved modules, ordered go/monitor registry, actual
128 MiB child limit and available memory accounting. It requires complete
pending-next-Run language metadata (`lang-default` resolves to debug), preserved
preferences, unchanged online request prefab, complete exact final source,
finished lexer and current callback, no observer errors/drops, and 80 keys.
Both one-shot worker evidence files must be present.

The online request's actual stock prefab is
`#s(prefab-module-settings #() (default) #t #t none #t)`.
That separate online setting is not a change to pending-next-Run instrumentation.
Require exact selected-language/preserved-settings equality across all arms,
and equal normalized handler identities/helper bytes. Module paths differ only
by the independently pinned runtime root.

A valid observed OOM or other abnormal terminal is retained as a valid
measurement, with `tool_succeeded` false. `handler-results` counts as a successful
tool outcome only with at least one monitor message and zero string/unknown-shape
monitor errors. Never silently treat OOM as successful Check Syntax. Different
actual terminal outcomes block an equal-work speed ratio; an improvement from
OOM to success is reported separately. Require `contention_observed` true in
both arms for typing-during-coloring comparisons; fast trials without contention
remain visible but do not establish that claim.

## Allocation and observer costs

Snapshots retain Racket managed memory, cumulative allocation, peak allocation,
process CPU/GC counters, plus external native maximum RSS. Allocation is churn,
not retained RAM. Global/place counter scope does not establish allocator
ownership, and counters from different places must not be summed or differenced
as ownership evidence. No forced collection occurs until latency work finishes.
Repeated JSON persistence is inherited and applied equally; phase-wide deltas
include this reporting overhead and other stock work.

Both arms use the same compact observer. It adds one immutable final source,
exact request matching, bounded metadata/CAS updates, clock samples, one worker
source hash and two one-shot evidence files. Reports preserve registration time,
GUI hook elapsed intervals and `worker_observer_overhead`. These are partial
self-cost observations, not a causal overhead estimate; the second timing-file
write and indirect GC/heap/scheduling effects are unmeasured. Do not subtract
those fields or call this equivalent to an uninstrumented run.

## Evidence transport and ownership

Each trial writes `measurements.json`, stdout/stderr, native resource data and
`observer/worker-init{,-overhead}.json`. A mode `summary.json` retains aggregate
statistics and raw outcomes. The CLI also prints complete JSON between
`OPENRACKET_PERFORMANCE_TRIAL_JSON_BEGIN/END` and summary markers. CI may capture
stdout locally and publish the complete JSON with the existing lossless,
byte-chunked, digest-checked log encoder. Never rely on a potentially truncated
single long runner-log line. Preserve outer pair/arm labels and every failed
trial. No source payload dump or artifact upload is required.

The source delta and baseline hashes are recorded in `provenance.json` and
`source-changes.diff`; `SHA256SUMS` identifies the final allowed files. Existing
frozen historical sources and reports were not edited.
