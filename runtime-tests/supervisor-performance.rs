//! Linux-only benchmark for the Rust supervisor, independent of the GUI.
//! Reproduction commands and measurement limitations are documented in
//! docs/SUPERVISOR-PERFORMANCE.md.

#[allow(dead_code)]
#[path = "../src/runtime.rs"]
mod runtime;

use runtime::{Runtime, RuntimeEvent};
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Default)]
struct Snapshot {
    cpu_ns: u64,
    switches: u64,
}

// Include the probe's main thread and every Rust supervisor worker. Racket is
// a separate process and is intentionally absent from /proc/self/task.
fn snapshot() -> std::io::Result<Snapshot> {
    let mut value = Snapshot::default();
    for entry in fs::read_dir("/proc/self/task")?.flatten() {
        let directory = entry.path();
        if let Ok(contents) = fs::read_to_string(directory.join("schedstat")) {
            value.cpu_ns += contents
                .split_whitespace()
                .next()
                .and_then(|value| value.parse::<u64>().ok())
                .unwrap_or(0);
        }
        if let Ok(contents) = fs::read_to_string(directory.join("status")) {
            for line in contents.lines() {
                if line.starts_with("voluntary_ctxt_switches:")
                    || line.starts_with("nonvoluntary_ctxt_switches:")
                {
                    value.switches += line
                        .split_whitespace()
                        .last()
                        .and_then(|value| value.parse::<u64>().ok())
                        .unwrap_or(0);
                }
            }
        }
    }
    Ok(value)
}

fn wait_for(runtime: &Runtime, predicate: impl Fn(&RuntimeEvent) -> bool) {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let batch = runtime.drain();
        if batch.iter().any(&predicate) {
            return;
        }
        assert!(
            Instant::now() < deadline,
            "Timed out; latest events: {batch:?}"
        );
        assert!(
            !batch
                .iter()
                .any(|event| matches!(event, RuntimeEvent::Fault(_) | RuntimeEvent::Exited { .. })),
            "Runtime failed: {batch:?}"
        );
        thread::sleep(Duration::from_millis(1));
    }
}

fn measure(runtime: &Runtime, label: &str, busy: bool) {
    let baseline = snapshot().expect("This probe requires readable Linux /proc task statistics");
    let start = Instant::now();
    let mut events = 0;
    while start.elapsed() < Duration::from_secs(5) {
        events += runtime.drain().len();
        thread::sleep(Duration::from_millis(if busy { 33 } else { 500 }));
    }
    let end = snapshot().unwrap();
    let seconds = start.elapsed().as_secs_f64();
    let cpu_ns = end
        .cpu_ns
        .checked_sub(baseline.cpu_ns)
        .expect("A measured thread exited during the sample");
    let switches = end
        .switches
        .checked_sub(baseline.switches)
        .expect("A measured thread exited during the sample");
    println!(
        "{label}: host_cpu={:.4}% host_cpu_ms={:.3} context_switches={switches} switches_per_sec={:.1} events={events}",
        cpu_ns as f64 / (seconds * 1e9) * 100.0,
        cpu_ns as f64 / 1e6,
        switches as f64 / seconds,
    );
}

fn main() {
    let args: Vec<_> = std::env::args_os().collect();
    assert_eq!(
        args.len(),
        3,
        "Usage: supervisor-performance /path/to/racket /path/to/runtime/bridge.rkt"
    );
    let runtime = Runtime::spawn(PathBuf::from(&args[1]), PathBuf::from(&args[2])).unwrap();
    wait_for(&runtime, |event| event.event_name() == Some("ready"));
    measure(&runtime, "idle", false);
    runtime
        .send(json!({"id":1,"op":"eval","source":"(let loop () (loop))"}))
        .unwrap();
    measure(&runtime, "busy_cpu_loop", true);
    let started = Instant::now();
    runtime.break_then_kill().unwrap();
    wait_for(&runtime, |event| match event {
        RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 1,
        _ => false,
    });
    println!(
        "break_latency_ms={:.3}",
        started.elapsed().as_secs_f64() * 1000.0
    );
    runtime.hard_stop().unwrap();
    wait_for(&runtime, |event| {
        matches!(event, RuntimeEvent::Exited { .. })
    });
}
