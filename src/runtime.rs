//! Non-blocking supervision of the real Racket bridge.
//!
//! `spawn` only starts the process and its supervisor. All pipe I/O, waits and
//! termination happen off the GUI thread. Poll `drain` from the application's
//! normal timer. A runtime is one session; after `Exited`, spawn a new runtime.
//! Input, output and individual protocol lines have independent memory limits.
//! On Unix each session has its own process group, including subprocesses made
//! by user programs; Stop and Drop terminate that group and reap the bridge.

use serde_json::{Value, json};
use std::collections::{BTreeSet, VecDeque};
use std::io::{self, Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicI64, AtomicUsize, Ordering};
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread;
use std::time::{Duration, Instant};

pub const BREAK_TIMEOUT: Duration = Duration::from_millis(1500);
pub const MAX_PROTOCOL_LINE_BYTES: usize = 1024 * 1024;
pub const MAX_REQUEST_BYTES: usize = 8 * 1024 * 1024;
pub const MAX_PENDING_INPUT_BYTES: usize = 16 * 1024 * 1024;
pub const MAX_BUFFERED_EVENT_BYTES: usize = 4 * 1024 * 1024;
pub const MAX_BUFFERED_EVENTS: usize = 512;
const SUPERVISOR_INTERVAL: Duration = Duration::from_millis(100);
const PIPE_POLL_TIMEOUT_MS: i32 = 250;
const MAX_PENDING_REQUESTS: usize = 64;

#[derive(Debug, Clone)]
pub enum RuntimeEvent {
    /// An unmodified bridge v1 object. Its discriminator is `event`.
    Protocol(Value),
    /// Host-side I/O, framing, process, or timeout failure.
    Fault(String),
    /// The process has been reaped. A signal termination has no numeric code.
    Exited { code: Option<i32>, success: bool },
    /// Queue records omitted while the UI was behind. Terminal records are
    /// prioritized over output, but any finite queue can overflow under abuse.
    DroppedOutput { count: usize },
}

impl RuntimeEvent {
    pub fn event_name(&self) -> Option<&str> {
        match self {
            Self::Protocol(value) => event_name(value),
            _ => None,
        }
    }
}

pub struct Runtime {
    input: mpsc::SyncSender<PendingRequest>,
    shared: Arc<Shared>,
    next_internal_id: AtomicI64,
}

struct Shared {
    events: Mutex<EventQueue>,
    operations: Mutex<Operations>,
    pending_input_bytes: AtomicUsize,
    running: AtomicBool,
    kill_requested: AtomicBool,
    readers_stop: AtomicBool,
    wake_lock: Mutex<()>,
    wake: Condvar,
}

#[derive(Default)]
struct Operations {
    active: BTreeSet<String>,
    interruption: Option<Interruption>,
}

struct Interruption {
    targets: BTreeSet<String>,
    deadline: Instant,
}

#[derive(Default)]
struct EventQueue {
    entries: VecDeque<(RuntimeEvent, usize)>,
    bytes: usize,
    dropped: usize,
}

struct PendingRequest {
    bytes: Vec<u8>,
    shared: Arc<Shared>,
}

impl Drop for PendingRequest {
    fn drop(&mut self) {
        self.shared
            .pending_input_bytes
            .fetch_sub(self.bytes.len(), Ordering::Relaxed);
    }
}

impl Runtime {
    pub fn spawn(racket_executable: PathBuf, bridge_path: PathBuf) -> Result<Self, String> {
        let mut command = Command::new(&racket_executable);
        command
            .arg(&bridge_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            command.process_group(0);
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            // Keep the GUI application from opening a console window.
            command.creation_flags(0x0800_0000);
        }
        let mut child = ManagedChild(command.spawn().map_err(|error| {
            format!("Could not start {}: {error}", racket_executable.display())
        })?);
        let stdin = child.0.stdin.take().ok_or("Racket stdin was not piped")?;
        let stdout = child.0.stdout.take().ok_or("Racket stdout was not piped")?;
        let stderr = child.0.stderr.take().ok_or("Racket stderr was not piped")?;
        let shared = Arc::new(Shared {
            events: Mutex::new(EventQueue::default()),
            operations: Mutex::new(Operations::default()),
            pending_input_bytes: AtomicUsize::new(0),
            running: AtomicBool::new(true),
            kill_requested: AtomicBool::new(false),
            readers_stop: AtomicBool::new(false),
            wake_lock: Mutex::new(()),
            wake: Condvar::new(),
        });
        let (input, receiver) = mpsc::sync_channel(MAX_PENDING_REQUESTS);
        let writer_wake = input.clone();
        let supervisor_shared = Arc::clone(&shared);
        thread::Builder::new()
            .name("racket-supervisor".into())
            .spawn(move || {
                supervise(
                    child,
                    stdin,
                    stdout,
                    stderr,
                    receiver,
                    writer_wake,
                    supervisor_shared,
                )
            })
            .map_err(|error| format!("Could not start the Racket supervisor: {error}"))?;
        Ok(Self {
            input,
            shared,
            next_internal_id: AtomicI64::new(i64::MIN),
        })
    }

    /// Enqueue a request without waiting for Racket to consume stdin. A full
    /// queue is an explicit, recoverable error; requests are never silently lost.
    pub fn send(&self, request: Value) -> Result<(), String> {
        if !self.is_running() || self.shared.kill_requested.load(Ordering::Acquire) {
            return Err("The Racket process is no longer running".into());
        }
        if !request.is_object() {
            return Err("A Racket request must be a JSON object".into());
        }
        if request
            .get("id")
            .is_some_and(|id| !id.is_null() && id.as_i64().is_none() && id.as_u64().is_none())
        {
            return Err("A Racket request id must be an integer or null".into());
        }
        let tracked = matches!(
            request.get("op").and_then(Value::as_str),
            Some("run" | "eval" | "check")
        );
        let id = request_id(&request);
        let mut buffer = LimitedBuffer(Vec::new());
        serde_json::to_writer(&mut buffer, &request)
            .map_err(|error| format!("Could not encode Racket request (limit 8 MiB): {error}"))?;
        buffer.0.push(b'\n');
        let length = buffer.0.len();
        self.shared
            .pending_input_bytes
            .fetch_update(Ordering::AcqRel, Ordering::Relaxed, |pending| {
                pending
                    .checked_add(length)
                    .filter(|total| *total <= MAX_PENDING_INPUT_BYTES)
            })
            .map_err(
                |_| "Racket input is backed up; try again after the running command finishes",
            )?;
        let pending = PendingRequest {
            bytes: buffer.0,
            shared: Arc::clone(&self.shared),
        };
        // Keep terminal-event processing from racing registration. try_send
        // never waits on the pipe or on the receiving thread.
        let mut operations = self.shared.operations.lock().unwrap();
        if tracked {
            if operations.active.contains(&id) {
                return Err("A Racket operation with that id is still pending".into());
            }
            if operations.active.len() >= MAX_PENDING_REQUESTS {
                return Err("Too many Racket operations are waiting for completion".into());
            }
        }
        self.input.try_send(pending).map_err(|error| match error {
            mpsc::TrySendError::Full(_) => "Racket's request queue is full; try again".to_string(),
            mpsc::TrySendError::Disconnected(_) => "Racket's input pipe is closed".to_string(),
        })?;
        if tracked {
            operations.active.insert(id);
        }
        Ok(())
    }

    /// Drain a bounded batch. Output loss is surfaced once per drain rather
    /// than generating an unbounded stream of truncation notifications.
    pub fn drain(&self) -> Vec<RuntimeEvent> {
        let mut queue = self.shared.events.lock().unwrap();
        let mut events = Vec::with_capacity(queue.entries.len() + 1);
        if queue.dropped != 0 {
            events.push(RuntimeEvent::DroppedOutput {
                count: queue.dropped,
            });
            queue.dropped = 0;
        }
        events.extend(queue.entries.drain(..).map(|(event, _)| event));
        queue.bytes = 0;
        events
    }

    /// Send a cooperative break and arm a 1.5-second hard-stop fallback for
    /// the *original* operations. The bridge's separate break acknowledgement
    /// cannot cancel this timer. Repeated clicks do not extend the deadline.
    /// Even if stdin is full, the fallback stays armed.
    pub fn break_then_kill(&self) -> Result<(), String> {
        if !self.is_running() {
            return Err("The Racket process is no longer running".into());
        }
        {
            let mut operations = self.shared.operations.lock().unwrap();
            if operations.interruption.is_none() && !operations.active.is_empty() {
                operations.interruption = Some(Interruption {
                    targets: operations.active.clone(),
                    deadline: Instant::now() + BREAK_TIMEOUT,
                });
            }
        }
        self.shared.wake.notify_one();
        self.send(json!({
            "id": self.next_internal_id.fetch_add(1, Ordering::Relaxed),
            "op": "break"
        }))
    }

    /// Request process-group termination. Actual killing/reaping is performed
    /// by the supervisor, so this also works when Racket never reads stdin.
    pub fn hard_stop(&self) -> Result<(), String> {
        self.shared.kill_requested.store(true, Ordering::Release);
        self.shared.wake.notify_one();
        Ok(())
    }

    pub fn is_running(&self) -> bool {
        self.shared.running.load(Ordering::Acquire)
    }
}

impl Drop for Runtime {
    fn drop(&mut self) {
        // Do not join from the GUI's Drop path: SIGKILL and wait are background
        // work. The supervisor owns the Child until it has been reaped.
        self.shared.kill_requested.store(true, Ordering::Release);
        self.shared.wake.notify_one();
    }
}

struct LimitedBuffer(Vec<u8>);

impl Write for LimitedBuffer {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if bytes.len() > MAX_REQUEST_BYTES.saturating_sub(self.0.len() + 1) {
            return Err(io::Error::other("request exceeds the 8 MiB limit"));
        }
        self.0.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

impl Shared {
    fn push(&self, event: RuntimeEvent) {
        let size = event_memory(&event);
        let mut queue = self.events.lock().unwrap();
        if size > MAX_BUFFERED_EVENT_BYTES {
            queue.dropped = queue.dropped.saturating_add(1);
            return;
        }
        if is_output(&event)
            && (queue.bytes + size > MAX_BUFFERED_EVENT_BYTES
                || queue.entries.len() >= MAX_BUFFERED_EVENTS)
        {
            queue.dropped = queue.dropped.saturating_add(1);
            return;
        }
        while queue.bytes + size > MAX_BUFFERED_EVENT_BYTES
            || queue.entries.len() >= MAX_BUFFERED_EVENTS
        {
            let index = queue
                .entries
                .iter()
                .position(|(entry, _)| is_output(entry))
                .unwrap_or(0);
            if let Some((_, removed)) = queue.entries.remove(index) {
                queue.bytes -= removed;
                queue.dropped = queue.dropped.saturating_add(1);
            } else {
                break;
            }
        }
        queue.bytes += size;
        queue.entries.push_back((event, size));
    }

    fn protocol(&self, value: Value) {
        if event_name(&value) == Some("done") {
            let id = request_id(&value);
            let mut operations = self.operations.lock().unwrap();
            operations.active.remove(&id);
            if let Some(interruption) = &mut operations.interruption {
                interruption.targets.remove(&id);
                if interruption.targets.is_empty() {
                    operations.interruption = None;
                }
            }
        }
        self.push(RuntimeEvent::Protocol(value));
    }
}

fn event_name(value: &Value) -> Option<&str> {
    value
        .get("event")
        .or_else(|| value.get("type"))
        .and_then(Value::as_str)
}

fn request_id(value: &Value) -> String {
    value.get("id").unwrap_or(&Value::Null).to_string()
}

fn is_output(event: &RuntimeEvent) -> bool {
    matches!(
        event.event_name(),
        Some("stdout" | "stderr" | "value" | "truncated")
    )
}

fn event_memory(event: &RuntimeEvent) -> usize {
    std::mem::size_of::<RuntimeEvent>()
        + match event {
            RuntimeEvent::Protocol(value) => value_memory(value),
            RuntimeEvent::Fault(text) => text.capacity(),
            _ => 0,
        }
}

fn value_memory(value: &Value) -> usize {
    std::mem::size_of::<Value>()
        + match value {
            Value::String(text) => text.capacity(),
            Value::Array(items) => {
                items.capacity() * std::mem::size_of::<Value>()
                    + items.iter().map(value_memory).sum::<usize>()
            }
            Value::Object(items) => items
                .iter()
                .map(|(key, value)| key.capacity() + 96 + value_memory(value))
                .sum(),
            _ => 0,
        }
}

/// Also covers a thread-creation failure: dropping an unstarted supervisor's
/// closure still kills the child instead of leaking a live interpreter.
struct ManagedChild(Child);
impl ManagedChild {
    fn kill_group(&mut self) -> io::Result<()> {
        #[cfg(unix)]
        unsafe {
            // The process was created with process_group(0), so this cannot
            // signal the IDE or its unrelated siblings.
            libc::kill(-(self.0.id() as i32), libc::SIGKILL);
        }
        self.0.kill()
    }
}
impl Drop for ManagedChild {
    fn drop(&mut self) {
        if matches!(self.0.try_wait(), Ok(None)) {
            let _ = self.kill_group();
            let _ = self.0.try_wait();
        }
    }
}

fn supervise(
    mut child: ManagedChild,
    stdin: ChildStdin,
    stdout: ChildStdout,
    stderr: ChildStderr,
    input: mpsc::Receiver<PendingRequest>,
    writer_wake: mpsc::SyncSender<PendingRequest>,
    shared: Arc<Shared>,
) {
    let mut workers = Vec::new();
    let state = Arc::clone(&shared);
    workers.push(
        thread::Builder::new()
            .name("racket-stdout".into())
            .spawn(move || read_stdout(stdout, state)),
    );
    let state = Arc::clone(&shared);
    workers.push(
        thread::Builder::new()
            .name("racket-stderr".into())
            .spawn(move || read_stderr(stderr, state)),
    );
    let state = Arc::clone(&shared);
    workers.push(
        thread::Builder::new()
            .name("racket-stdin".into())
            .spawn(move || write_stdin(stdin, input, state)),
    );
    for error in workers.iter().filter_map(|worker| worker.as_ref().err()) {
        shared.push(RuntimeEvent::Fault(format!(
            "Could not start a Racket I/O worker: {error}"
        )));
        shared.kill_requested.store(true, Ordering::Release);
    }
    let mut killed = false;
    let mut wait_fault_reported = false;
    let exit = loop {
        let timed_out = {
            let operations = shared.operations.lock().unwrap();
            operations
                .interruption
                .as_ref()
                .is_some_and(|interrupt| Instant::now() >= interrupt.deadline)
        };
        if timed_out && !killed {
            shared.push(RuntimeEvent::Fault(
                "Racket did not stop within 1.5 seconds; its process was terminated.".into(),
            ));
            shared.kill_requested.store(true, Ordering::Release);
        }
        if shared.kill_requested.load(Ordering::Acquire) && !killed {
            if let Err(error) = child.kill_group() {
                // A process can exit between the stop request and kill.
                if !matches!(child.0.try_wait(), Ok(Some(_))) {
                    shared.push(RuntimeEvent::Fault(format!(
                        "Could not terminate Racket: {error}"
                    )));
                }
            }
            killed = true;
        }
        match child.0.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) => {}
            Err(error) => {
                if !wait_fault_reported {
                    shared.push(RuntimeEvent::Fault(format!(
                        "Could not inspect Racket's exit status: {error}"
                    )));
                    wait_fault_reported = true;
                }
                shared.kill_requested.store(true, Ordering::Release);
                if killed {
                    // Avoid leaking a running process on an unrecoverable wait
                    // failure; wait is allowed here, never on the GUI thread.
                    let _ = child.kill_group();
                    break child.0.wait().ok();
                }
            }
        }
        let timeout = {
            let operations = shared.operations.lock().unwrap();
            operations
                .interruption
                .as_ref()
                .map_or(SUPERVISOR_INTERVAL, |interruption| {
                    SUPERVISOR_INTERVAL.min(
                        interruption
                            .deadline
                            .saturating_duration_since(Instant::now()),
                    )
                })
        };
        let guard = shared.wake_lock.lock().unwrap();
        let _ = shared.wake.wait_timeout(guard, timeout).unwrap();
    };
    shared.running.store(false, Ordering::Release);
    // Wake an idle writer blocked in recv without a periodic timeout. A full
    // queue means the writer already has work and will observe `running`.
    let _ = writer_wake.try_send(PendingRequest {
        bytes: Vec::new(),
        shared: Arc::clone(&shared),
    });
    // Kill surviving descendants even if the bridge exited successfully.
    #[cfg(unix)]
    unsafe {
        libc::kill(-(child.0.id() as i32), libc::SIGKILL);
    }
    // Give readers time to consume the tail, then stop even if a deliberately
    // detached process kept a pipe open. This is not a UI-thread wait.
    let drain_deadline = Instant::now() + Duration::from_millis(100);
    while workers
        .iter()
        .any(|worker| worker.as_ref().is_ok_and(|worker| !worker.is_finished()))
        && Instant::now() < drain_deadline
    {
        thread::sleep(Duration::from_millis(5));
    }
    shared.readers_stop.store(true, Ordering::Release);
    let finish_deadline = Instant::now() + Duration::from_millis(50);
    while workers
        .iter()
        .any(|worker| worker.as_ref().is_ok_and(|worker| !worker.is_finished()))
        && Instant::now() < finish_deadline
    {
        thread::sleep(Duration::from_millis(5));
    }
    for worker in workers.into_iter().flatten() {
        // Unix workers use nonblocking pipes and finish promptly. Do not let
        // an inherited pipe on another platform hang cleanup indefinitely.
        if worker.is_finished() && worker.join().is_err() {
            shared.push(RuntimeEvent::Fault(
                "A Racket I/O worker stopped unexpectedly".into(),
            ));
        }
    }
    shared.operations.lock().unwrap().active.clear();
    shared.push(RuntimeEvent::Exited {
        code: exit.as_ref().and_then(std::process::ExitStatus::code),
        success: exit.is_some_and(|status| status.success()),
    });
}

#[cfg(unix)]
fn nonblocking<T: std::os::fd::AsRawFd>(pipe: &T) -> io::Result<()> {
    use libc::{F_GETFL, F_SETFL, O_NONBLOCK, fcntl};
    let descriptor = pipe.as_raw_fd();
    // The descriptor is owned by this worker and remains valid for both calls.
    unsafe {
        let flags = fcntl(descriptor, F_GETFL);
        if flags == -1 || fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == -1 {
            return Err(io::Error::last_os_error());
        }
    }
    Ok(())
}
#[cfg(not(unix))]
fn nonblocking<T>(_pipe: &T) -> io::Result<()> {
    Ok(())
}

#[cfg(unix)]
fn wait_pipe<T: std::os::fd::AsRawFd>(pipe: &T, writable: bool) -> io::Result<()> {
    let mut descriptor = libc::pollfd {
        fd: pipe.as_raw_fd(),
        events: if writable {
            libc::POLLOUT
        } else {
            libc::POLLIN
        },
        revents: 0,
    };
    // poll wakes immediately on data, writable space, HUP or an error. The
    // finite timeout only protects against detached descendants retaining a
    // pipe after the session exits; ordinary idle pipes need four wakes/sec.
    let result = unsafe { libc::poll(&mut descriptor, 1, PIPE_POLL_TIMEOUT_MS) };
    if result < 0 {
        let error = io::Error::last_os_error();
        if error.kind() != io::ErrorKind::Interrupted {
            return Err(error);
        }
    }
    if descriptor.revents & libc::POLLNVAL != 0 {
        return Err(io::Error::from_raw_os_error(libc::EBADF));
    }
    Ok(())
}

#[cfg(not(unix))]
fn wait_pipe<T>(_pipe: &T, _writable: bool) -> io::Result<()> {
    // The non-Unix pipes are blocking, so this is only a defensive fallback.
    thread::sleep(Duration::from_millis(10));
    Ok(())
}

fn pipe_setup_error(shared: &Shared, error: io::Error) {
    shared.push(RuntimeEvent::Fault(format!(
        "Could not configure Racket's pipe: {error}"
    )));
    shared.kill_requested.store(true, Ordering::Release);
    shared.wake.notify_one();
}

fn write_stdin(mut stdin: ChildStdin, input: mpsc::Receiver<PendingRequest>, shared: Arc<Shared>) {
    if let Err(error) = nonblocking(&stdin) {
        pipe_setup_error(&shared, error);
        return;
    }
    while shared.running.load(Ordering::Acquire) && !shared.kill_requested.load(Ordering::Acquire) {
        let request = match input.recv() {
            Ok(request) => request,
            Err(_) => break,
        };
        let mut remaining = request.bytes.as_slice();
        while !remaining.is_empty() {
            if !shared.running.load(Ordering::Acquire)
                || shared.kill_requested.load(Ordering::Acquire)
            {
                return;
            }
            match stdin.write(remaining) {
                Ok(0) => {
                    shared.push(RuntimeEvent::Fault(
                        "Racket's stdin closed during a request".into(),
                    ));
                    return;
                }
                Ok(count) => remaining = &remaining[count..],
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                    if let Err(error) = wait_pipe(&stdin, true) {
                        pipe_setup_error(&shared, error);
                        return;
                    }
                }
                Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
                Err(error) => {
                    if shared.running.load(Ordering::Acquire)
                        && !shared.kill_requested.load(Ordering::Acquire)
                    {
                        shared.push(RuntimeEvent::Fault(format!(
                            "Could not write Racket's stdin: {error}"
                        )));
                    }
                    return;
                }
            }
        }
    }
}

fn read_stdout(mut stdout: ChildStdout, shared: Arc<Shared>) {
    if let Err(error) = nonblocking(&stdout) {
        pipe_setup_error(&shared, error);
        return;
    }
    let mut buffer = [0u8; 8192];
    let mut line = Vec::with_capacity(8192);
    let mut discarding = false;
    while !shared.readers_stop.load(Ordering::Acquire) {
        match stdout.read(&mut buffer) {
            Ok(0) => {
                if !discarding && !line.is_empty() {
                    parse_line(&line, &shared);
                }
                return;
            }
            Ok(count) => {
                for chunk in buffer[..count].split_inclusive(|byte| *byte == b'\n') {
                    let terminated = chunk.last() == Some(&b'\n');
                    let content = if terminated {
                        &chunk[..chunk.len() - 1]
                    } else {
                        chunk
                    };
                    if !discarding {
                        if line.len() + content.len() > MAX_PROTOCOL_LINE_BYTES {
                            line.clear();
                            discarding = true;
                            shared.push(RuntimeEvent::Fault(
                                "Racket emitted a protocol line larger than 1 MiB; that line was discarded.".into(),
                            ));
                        } else {
                            line.extend_from_slice(content);
                        }
                    }
                    if terminated {
                        if !discarding && !line.is_empty() {
                            parse_line(&line, &shared);
                        }
                        line.clear();
                        discarding = false;
                    }
                }
            }
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                if let Err(error) = wait_pipe(&stdout, false) {
                    pipe_setup_error(&shared, error);
                    return;
                }
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
            Err(error) => {
                shared.push(RuntimeEvent::Fault(format!(
                    "Could not read Racket's stdout: {error}"
                )));
                return;
            }
        }
    }
}

fn parse_line(line: &[u8], shared: &Shared) {
    match serde_json::from_slice::<Value>(line) {
        Ok(value) if value.is_object() && event_name(&value).is_some() => shared.protocol(value),
        Ok(_) => shared.push(RuntimeEvent::Fault(
            "Racket emitted a JSON record without an event name".into(),
        )),
        Err(error) => shared.push(RuntimeEvent::Fault(format!(
            "Invalid Racket protocol record: {error}"
        ))),
    }
}

fn read_stderr(mut stderr: ChildStderr, shared: Arc<Shared>) {
    if let Err(error) = nonblocking(&stderr) {
        pipe_setup_error(&shared, error);
        return;
    }
    let mut buffer = [0u8; 8192];
    while !shared.readers_stop.load(Ordering::Acquire) {
        match stderr.read(&mut buffer) {
            Ok(0) => return,
            Ok(count) => shared.push(RuntimeEvent::Protocol(json!({
                "event": "stderr", "id": null,
                "text": String::from_utf8_lossy(&buffer[..count]),
                "origin": "process"
            }))),
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                if let Err(error) = wait_pipe(&stderr, false) {
                    pipe_setup_error(&shared, error);
                    return;
                }
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
            Err(error) => {
                shared.push(RuntimeEvent::Fault(format!(
                    "Could not read Racket's stderr: {error}"
                )));
                return;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[cfg(unix)]
    fn mock(script: &str) -> (Runtime, tempfile::TempDir) {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("mock-bridge.sh");
        fs::write(&path, script).unwrap();
        (
            Runtime::spawn(PathBuf::from("/bin/sh"), path).unwrap(),
            directory,
        )
    }

    fn wait_for(
        runtime: &Runtime,
        timeout: Duration,
        predicate: impl Fn(&RuntimeEvent) -> bool,
    ) -> Vec<RuntimeEvent> {
        let deadline = Instant::now() + timeout;
        let mut all = Vec::new();
        loop {
            let batch = runtime.drain();
            let found = batch.iter().any(&predicate);
            all.extend(batch);
            if found {
                return all;
            }
            assert!(Instant::now() < deadline, "Timed out; events: {all:?}");
            thread::sleep(Duration::from_millis(10));
        }
    }

    #[test]
    fn missing_executable_is_actionable() {
        let result = Runtime::spawn(
            PathBuf::from("/definitely/missing/racket"),
            PathBuf::from("bridge.rkt"),
        );
        assert!(result.err().unwrap().contains("Could not start"));
    }

    #[test]
    #[cfg(unix)]
    fn communicates_and_preserves_structured_diagnostics() {
        let (runtime, _directory) = mock(
            r#"
            printf '%s\n' '{"event":"ready","protocol":1}'
            IFS= read -r request
            printf '%s\n' '{"event":"stdout","id":1,"text":"hello\n"}'
            printf '%s\n' '{"event":"error","id":1,"kind":"syntax","message":"bad syntax","locations":[{"source":"untitled.rkt","line":2,"column":3,"position":4,"span":1}]}'
            printf '%s\n' '{"event":"done","id":1,"status":"error"}'
        "#,
        );
        runtime
            .send(json!({"id":1,"op":"eval","source":"(+ 1 2)"}))
            .unwrap();
        let events = wait_for(&runtime, Duration::from_secs(3), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
        assert!(
            events
                .iter()
                .any(|event| event.event_name() == Some("stdout"))
        );
        let diagnostic = events
            .iter()
            .find_map(|event| match event {
                RuntimeEvent::Protocol(value) if event.event_name() == Some("error") => Some(value),
                _ => None,
            })
            .unwrap();
        assert_eq!(diagnostic["locations"][0]["line"], 2);
        assert!(matches!(
            events.last(),
            Some(RuntimeEvent::Exited { success: true, .. })
        ));
        assert!(!runtime.is_running());
        assert!(runtime.send(json!({"op":"eval"})).is_err());
    }

    #[test]
    #[cfg(unix)]
    fn break_ack_does_not_disable_hard_stop() {
        let (runtime, _directory) = mock(
            r#"
            while IFS= read -r request; do
                case "$request" in
                    *'"op":"run"'*) printf '%s\n' '{"event":"started","id":1,"op":"run"}' ;;
                    *'"op":"break"'*) printf '%s\n' '{"event":"done","id":-9223372036854775808,"status":"ok"}' ;;
                esac
            done
        "#,
        );
        runtime
            .send(json!({"id":1,"op":"run","source":"loop"}))
            .unwrap();
        wait_for(&runtime, Duration::from_secs(2), |event| {
            event.event_name() == Some("started")
        });
        let start = Instant::now();
        runtime.break_then_kill().unwrap();
        let events = wait_for(&runtime, Duration::from_secs(4), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
        assert!(start.elapsed() >= BREAK_TIMEOUT);
        assert!(events.iter().any(
            |event| matches!(event, RuntimeEvent::Fault(message) if message.contains("1.5 seconds"))
        ));
        assert!(matches!(
            events.last(),
            Some(RuntimeEvent::Exited { success: false, .. })
        ));
    }

    #[test]
    #[cfg(unix)]
    fn cooperative_break_preserves_the_session() {
        let (runtime, _directory) = mock(
            r#"
            while IFS= read -r request; do
                case "$request" in
                    *'"op":"run"'*) printf '%s\n' '{"event":"started","id":1,"op":"run"}' ;;
                    *'"op":"break"'*) printf '%s\n' '{"event":"done","id":1,"status":"interrupted"}' ;;
                    *'"op":"shutdown"'*) exit 0 ;;
                esac
            done
        "#,
        );
        runtime.send(json!({"id":1,"op":"run"})).unwrap();
        wait_for(&runtime, Duration::from_secs(2), |event| {
            event.event_name() == Some("started")
        });
        runtime.break_then_kill().unwrap();
        wait_for(&runtime, Duration::from_secs(2), |event| {
            event.event_name() == Some("done")
        });
        thread::sleep(BREAK_TIMEOUT + Duration::from_millis(100));
        assert!(runtime.is_running());
        runtime.send(json!({"id":2,"op":"shutdown"})).unwrap();
        wait_for(&runtime, Duration::from_secs(2), |event| {
            matches!(event, RuntimeEvent::Exited { success: true, .. })
        });
    }

    #[test]
    #[cfg(unix)]
    fn oversized_unterminated_line_recovers_at_newline() {
        let (runtime, _directory) = mock(
            r#"
            head -c 2097152 /dev/zero | tr '\000' x
            printf '\n%s\n' '{"event":"done","id":5,"status":"ok"}'
        "#,
        );
        let events = wait_for(&runtime, Duration::from_secs(4), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
        assert_eq!(events.iter().filter(|event| matches!(event, RuntimeEvent::Fault(message) if message.contains("1 MiB"))).count(), 1);
        assert!(
            events
                .iter()
                .any(|event| event.event_name() == Some("done"))
        );
    }

    #[test]
    #[cfg(unix)]
    fn bounded_output_keeps_terminal_event() {
        let (runtime, _directory) = mock(
            r#"
            i=0
            while [ "$i" -lt 5000 ]; do
                printf '%s\n' '{"event":"stdout","id":1,"text":"a line of output"}'
                i=$((i+1))
            done
            printf '%s\n' '{"event":"done","id":1,"status":"ok"}'
        "#,
        );
        let deadline = Instant::now() + Duration::from_secs(5);
        while runtime.is_running() {
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(10));
        }
        thread::sleep(Duration::from_millis(150));
        {
            let queue = runtime.shared.events.lock().unwrap();
            assert!(queue.entries.len() <= MAX_BUFFERED_EVENTS);
            assert!(queue.bytes <= MAX_BUFFERED_EVENT_BYTES);
        }
        let events = runtime.drain();
        assert!(
            events
                .iter()
                .any(|event| matches!(event, RuntimeEvent::DroppedOutput { count } if *count > 0))
        );
        assert!(
            events
                .iter()
                .any(|event| event.event_name() == Some("done"))
        );
    }

    #[test]
    #[cfg(unix)]
    fn input_backpressure_and_drop_do_not_block() {
        let (runtime, _directory) = mock("sleep 30\n");
        let payload = "x".repeat(1024 * 1024);
        let mut rejected = false;
        for id in 0..32 {
            if runtime
                .send(json!({"id":id,"op":"eval","source":payload}))
                .is_err()
            {
                rejected = true;
                break;
            }
        }
        assert!(rejected);
        assert!(
            runtime.shared.pending_input_bytes.load(Ordering::Relaxed) <= MAX_PENDING_INPUT_BYTES
        );
        let state = Arc::clone(&runtime.shared);
        let start = Instant::now();
        drop(runtime);
        assert!(start.elapsed() < Duration::from_millis(100));
        let deadline = Instant::now() + Duration::from_secs(2);
        while state.running.load(Ordering::Acquire) {
            assert!(
                Instant::now() < deadline,
                "Drop failed to terminate the child"
            );
            thread::sleep(Duration::from_millis(10));
        }
    }

    #[test]
    fn encoding_is_bounded() {
        let mut buffer = LimitedBuffer(Vec::new());
        assert!(buffer.write_all(&vec![0; MAX_REQUEST_BYTES]).is_err());
        assert!(buffer.0.is_empty());
    }

    #[test]
    #[cfg(unix)]
    fn pending_operations_and_request_ids_are_bounded() {
        let (runtime, _directory) = mock("while IFS= read -r request; do :; done\n");
        assert!(runtime.send(json!({"id":[], "op":"eval"})).is_err());
        runtime.send(json!({"id":0,"op":"eval"})).unwrap();
        assert!(runtime.send(json!({"id":0,"op":"eval"})).is_err());
        for id in 1..MAX_PENDING_REQUESTS {
            runtime.send(json!({"id":id,"op":"eval"})).unwrap();
            thread::sleep(Duration::from_millis(1));
        }
        assert!(runtime.send(json!({"id":1000,"op":"eval"})).is_err());
        assert_eq!(
            runtime.shared.operations.lock().unwrap().active.len(),
            MAX_PENDING_REQUESTS
        );
        runtime.hard_stop().unwrap();
        wait_for(&runtime, Duration::from_secs(2), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
    }

    fn real_runtime() -> Runtime {
        let executable = std::env::var_os("RACKET_EXECUTABLE")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("racket"));
        let bridge = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("runtime/bridge.rkt");
        let runtime = Runtime::spawn(executable, bridge).unwrap();
        wait_for(&runtime, Duration::from_secs(10), |event| {
            event.event_name() == Some("ready")
        });
        runtime
    }

    /// Run explicitly with RACKET_EXECUTABLE=/path/to/racket. Kept ignored so
    /// cargo test also works on machines that have not installed Racket yet.
    #[test]
    #[ignore = "requires Racket; set RACKET_EXECUTABLE and run --ignored"]
    fn real_racket_bridge_smoke() {
        let runtime = real_runtime();
        runtime
            .send(json!({"id":1,"op":"eval","source":"(+ 40 2)"}))
            .unwrap();
        let events = wait_for(&runtime, Duration::from_secs(10), |event| match event {
            RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 1,
            _ => false,
        });
        assert!(
            events.iter().any(|event| match event {
                RuntimeEvent::Protocol(value) =>
                    value["event"] == "value"
                        && value["text"]
                            .as_str()
                            .is_some_and(|text| text.contains("42")),
                _ => false,
            }),
            "{events:?}"
        );
        runtime.send(json!({"id":2,"op":"shutdown"})).unwrap();
        wait_for(&runtime, Duration::from_secs(5), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
    }

    #[test]
    #[ignore = "requires Racket; set RACKET_EXECUTABLE and run --ignored"]
    fn real_racket_break_and_reuse() {
        let runtime = real_runtime();
        runtime
            .send(json!({"id":1,"op":"eval","source":"(let loop () (loop))"}))
            .unwrap();
        wait_for(&runtime, Duration::from_secs(5), |event| {
            event.event_name() == Some("started")
        });
        runtime.break_then_kill().unwrap();
        let events = wait_for(&runtime, Duration::from_secs(5), |event| match event {
            RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 1,
            _ => false,
        });
        assert!(events.iter().any(|event| match event {
            RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 1 && value["status"] == "interrupted",
            _ => false,
        }), "{events:?}");
        assert!(runtime.is_running());
        runtime
            .send(json!({"id":2,"op":"eval","source":"(+ 6 7)"}))
            .unwrap();
        let events = wait_for(&runtime, Duration::from_secs(5), |event| match event {
            RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 2,
            _ => false,
        });
        assert!(
            events.iter().any(|event| match event {
                RuntimeEvent::Protocol(value) =>
                    value["event"] == "value"
                        && value["text"]
                            .as_str()
                            .is_some_and(|text| text.trim() == "13"),
                _ => false,
            }),
            "{events:?}"
        );
        runtime.hard_stop().unwrap();
        wait_for(&runtime, Duration::from_secs(5), |event| {
            matches!(event, RuntimeEvent::Exited { .. })
        });
    }

    #[test]
    #[ignore = "requires Racket; set RACKET_EXECUTABLE and run --ignored"]
    fn real_racket_input_round_trip() {
        let runtime = real_runtime();
        runtime
            .send(json!({"id":1,"op":"eval","source":"(read-line)"}))
            .unwrap();
        wait_for(&runtime, Duration::from_secs(5), |event| {
            event.event_name() == Some("input-request")
        });
        runtime
            .send(json!({"id":2,"op":"input","text":"hello from Rust\n","eof":false}))
            .unwrap();
        let events = wait_for(&runtime, Duration::from_secs(5), |event| match event {
            RuntimeEvent::Protocol(value) => value["event"] == "done" && value["id"] == 1,
            _ => false,
        });
        assert!(
            events.iter().any(|event| match event {
                RuntimeEvent::Protocol(value) =>
                    value["event"] == "value"
                        && value["text"]
                            .as_str()
                            .is_some_and(|text| text.contains("hello from Rust")),
                _ => false,
            }),
            "{events:?}"
        );
    }
}
