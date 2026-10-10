# Rust supervisor idle-performance evidence

## Scope and limitations

These measurements cover the **Rust supervisor host process only**, including
its I/O/supervisor threads and a small standalone probe. They **exclude the
Racket child process**. The busy sample deliberately gives Racket an infinite
CPU loop; the resulting Racket CPU consumption is not included in the reported
host CPU percentage.

No GUI is started or rendered. There is **no GUI-wide performance result and no
comparison with DrRacket**. The probe only mimics the application's event-drain
cadence: every 500 ms while idle, and every 33 ms while an operation is running.

Each sample lasts approximately five seconds (the loop runs for at least five
seconds and may overshoot by its last sleep). Percentages use the actual elapsed
wall time. CPU is expressed as a percentage of **one logical CPU**, rather than
as a percentage of the entire machine.

These are short, single-run before/after samples from the same Linux execution
environment using Rust 1.94.0 and Racket 9.3 CS. They are evidence of the changed
idle behavior, not statistically controlled benchmarks or guaranteed latency.
Concurrent activity, scheduler load and CPU power management affect results.

## Method

The probe waits for the bridge's `ready` event, then samples every thread in
`/proc/self/task`:

- CPU runtime: first field of each thread's `schedstat`, summed in nanoseconds.
- Context switches: `voluntary_ctxt_switches` plus
  `nonvoluntary_ctxt_switches` from each thread's `status`, summed.
- Reported metrics: the difference between start/end snapshots divided by the
  actual elapsed sample time.

It first remains idle for five seconds. It then sends the real bridge an
`eval` request containing `(let loop () (loop))` and samples for another five
seconds. Finally, it times `break_then_kill()` through receipt of the **original
operation's** `done` event, with a 1 ms result-polling interval. The separate
Break acknowledgement does not end this measurement.

The probe stops the runtime and waits for its process-exit event before exiting.
The implementation is in
[`runtime-tests/supervisor-performance.rs`](../runtime-tests/supervisor-performance.rs).

## Exact recorded before/after results

Recorded on 2026-10-10. Baseline was the initial supervisor implementation:
stdout/stderr `WouldBlock` paths slept 10 ms, the writer used
`recv_timeout(10 ms)`, and the process supervisor used a 10 ms timed wait.

Baseline raw output:

```text
idle: host_cpu=0.8154% host_cpu_ms=40.778 context_switches=1990 switches_per_sec=397.9 events=0
busy_cpu_loop: host_cpu=1.0387% host_cpu_ms=52.275 context_switches=2143 switches_per_sec=425.8 events=1
break_latency_ms=3.333
```

After the readiness-wait change:

```text
idle: host_cpu=0.0761% host_cpu_ms=3.810 context_switches=100 switches_per_sec=20.0 events=0
busy_cpu_loop: host_cpu=0.2157% host_cpu_ms=10.792 context_switches=241 switches_per_sec=48.2 events=1
break_latency_ms=1.144
```

The persisted probe was then compiled and run independently using the
reproduction method below. Its verification run returned:

```text
idle: host_cpu=0.0853% host_cpu_ms=4.265 context_switches=99 switches_per_sec=19.8 events=0
busy_cpu_loop: host_cpu=0.1646% host_cpu_ms=8.284 context_switches=243 switches_per_sec=48.3 events=1
break_latency_ms=1.174
```

In these samples, idle host CPU decreased about 91% and idle context switches
about 95%. The busy-loop result concerns only the Rust host's overhead; it does
not suggest that the Racket program became cheaper to execute.

The changed implementation:

- Uses Unix `poll` for pipe readiness, with a 250 ms timeout protecting cleanup
  if a detached descendant retains a pipe. Data, writable space and pipe closure
  wake it immediately.
- Blocks the idle stdin worker on its bounded request queue. Process exit sends
  an explicit wakeup, so no periodic stdin timeout is needed.
- Uses 100 ms supervisor waits, shortened to the remaining Break deadline.
  Break/Stop requests notify its condition variable.
- Retains the 1.5-second hard-stop fallback, memory limits and public API.

The baseline was measured before the local source change, not from a separate
named release or commit. The reproduction command below measures the checked-out
implementation; it does not recreate the historical baseline automatically.

## Reproduce the current measurement

Requirements: Linux with readable `/proc`, Cargo/Rust, and a real Racket
installation. Run from the repository root. A temporary Cargo package keeps the
probe independent of the Iced GUI build; it compiles the checked-out
`src/runtime.rs` directly.

```bash
repo="$PWD"
probe_dir="$(mktemp -d)"
cat > "$probe_dir/Cargo.toml" <<EOF_MANIFEST
[package]
name = "openracket-supervisor-performance"
version = "0.1.0"
edition = "2024"

[dependencies]
serde_json = "1.0"
libc = "0.2"

[[bin]]
name = "supervisor-performance"
path = "$repo/runtime-tests/supervisor-performance.rs"
EOF_MANIFEST

# Set this to your Racket executable, or leave it as `racket` if it is in PATH.
racket_executable="${RACKET_EXECUTABLE:-racket}"
cargo run --quiet --manifest-path "$probe_dir/Cargo.toml" \
  --bin supervisor-performance -- \
  "$racket_executable" "$repo/runtime/bridge.rkt"
```

Use your own Rust installation and set `RACKET_EXECUTABLE` to your local
Racket binary. No build-machine-specific directories are required.

## Correctness checks after the change

All 12 supervisor tests passed, including real-Racket evaluation, interruption
and reuse, input round-trip, oversized protocol framing, bounded output/input,
pending-operation limits, nonblocking Drop and hard-stop fallback. Strict
Clippy for the isolated supervisor test target also passed.
The persisted performance probe itself also passes Clippy with `-D warnings`.

From the full project, the real-Racket supervisor tests can be included with:

```bash
RACKET_EXECUTABLE=/path/to/racket cargo test runtime::tests -- --include-ignored
```
