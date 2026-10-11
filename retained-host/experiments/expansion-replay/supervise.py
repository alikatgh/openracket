#!/usr/bin/env python3
"""Bounded, external process-group supervisor for the diagnostic replay.

Only the standard library is needed. Phase boundaries are *observed* from stdout;
RSS is sampled independently and is neither a precise peak nor Racket heap usage.
The driver owns replay.json. This supervisor owns supervisor.json and raw logs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

PHASE_PREFIX = b"OPENRACKET_REPLAY_PHASE_JSON "
PHASES = {"initializing", "interval_start", "interval_end", "cleanup", "finished"}
MAX_LINE_BYTES = 64 * 1024
TAIL_BYTES_PER_POLL = 1024 * 1024
LAUNCH_ENV_KEYS = frozenset({
    "PLTUSERHOME", "PLTADDONDIR", "PLTCOLLECTS", "PLTCOMPILEDROOTS",
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
})


def load_launch_context(capture: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Restore only the explicit, complete capture allowlist; never arbitrary env."""
    path = capture.with_suffix(".launch.json")
    launch = json.loads(path.read_text(), parse_constant=reject_nonfinite_json)
    expected = {"environment", "cwd", "snapshot_sha256", "registry_sha256"}
    if not isinstance(launch, dict) or set(launch) != expected:
        raise ValueError(f"{path}: launch context must have exactly {sorted(expected)}")
    environment = launch["environment"]
    if not isinstance(environment, dict) or set(environment) != LAUNCH_ENV_KEYS:
        raise ValueError(f"{path}: environment must have exactly the fixed allowlist {sorted(LAUNCH_ENV_KEYS)}")
    restored = dict(os.environ)
    for key, value in environment.items():
        if value is False:
            restored.pop(key, None)
        elif isinstance(value, str) and "\x00" not in value:
            restored[key] = value
        else:
            raise ValueError(f"{path}: {key} must be a string without NUL, or false")
    cwd = launch["cwd"]
    if not isinstance(cwd, str) or not cwd or "\x00" in cwd or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise ValueError(f"{path}: cwd must name an existing absolute directory")
    for field in ("snapshot_sha256", "registry_sha256"):
        digest = launch[field]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError(f"{path}: {field} must be a SHA-256 hex digest")
    return launch, restored


def monotonic_ms() -> float:
    return time.monotonic_ns() / 1_000_000


class SupervisorInterrupted(BaseException):
    def __init__(self, signum: int):
        self.signum = signum


def reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_group_snapshot(pgid: int, timeout: float = 0.3) -> dict[str, Any]:
    """Return live members and their summed RSS; unknown values stay None.

    Zombies are reported separately and are not live cleanup targets. Reading a
    process list is racy, including when a process disappears during sampling.
    ps membership (not killpg(..., 0)) also handles macOS's empty-group EPERM.
    """
    members: list[dict[str, Any]] = []
    errors: list[str] = []
    snapshot_deadline = time.monotonic() + timeout
    if sys.platform.startswith("linux") and Path("/proc").is_dir():
        source = "linux_proc_stat"
        try:
            entries = list(Path("/proc").iterdir())
        except OSError as exc:
            return {"source": source, "members": None, "rss_bytes": None,
                    "complete": False, "errors": [str(exc)]}
        page_size = os.sysconf("SC_PAGE_SIZE")
        for entry in entries:
            if time.monotonic() >= snapshot_deadline:
                errors.append("Process-group snapshot deadline exhausted")
                break
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text()
                fields = raw[raw.rfind(")") + 2:].split()
                if int(fields[2]) != pgid:
                    continue
                members.append({"pid": int(entry.name), "state": fields[0],
                                "rss_bytes": int(fields[21]) * page_size})
            except (FileNotFoundError, ProcessLookupError):
                continue  # Normal exit race, not an RSS value of zero.
            except (OSError, ValueError, IndexError) as exc:
                if len(errors) < 8:
                    errors.append(f"/proc/{entry.name}/stat: {exc}")
    else:
        source = "ps"
        remaining = snapshot_deadline - time.monotonic()
        if remaining <= 0:
            return {"source": source, "members": None, "rss_bytes": None,
                    "complete": False, "errors": ["Process-group snapshot deadline exhausted"]}
        try:
            result = subprocess.run(
                ["ps", "-e", "-o", "pid=", "-o", "pgid=", "-o", "rss=", "-o", "stat="],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                text=True, timeout=remaining,
            )
            for row in result.stdout.splitlines():
                fields = row.split()
                if len(fields) < 4:
                    continue
                if int(fields[1]) == pgid:
                    members.append({"pid": int(fields[0]), "state": fields[3],
                                    "rss_bytes": int(fields[2]) * 1024})
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return {"source": source, "members": None, "rss_bytes": None,
                    "complete": False, "errors": [str(exc)]}
    live = [m for m in members if not m["state"].startswith("Z")]
    return {"source": source, "members": members,
            "rss_bytes": sum(m["rss_bytes"] for m in live) if live and not errors else None,
            "complete": not errors, "errors": errors}


def live_members(snapshot: dict[str, Any]) -> list[dict[str, Any]] | None:
    if snapshot["members"] is None or not snapshot["complete"]:
        return None
    return [m for m in snapshot["members"] if not m["state"].startswith("Z")]


class PhaseReader:
    """Incremental raw-file tailer with bounded memory even without newlines."""
    def __init__(self, stream: Any, report: dict[str, Any], started_ms: float):
        self.stream, self.report, self.started_ms = stream, report, started_ms
        self.pending = bytearray()
        self.discarding = False
        self.active: dict[str, Any] | None = None

    def error(self, detail: str) -> None:
        errors = self.report["errors"]
        if len(errors) < 100:
            errors.append({"category": "phase_protocol", "detail": detail})

    def poll(self, limit: int = TAIL_BYTES_PER_POLL) -> int:
        raw = self.stream.read(limit)
        if not raw:
            return 0
        for fragment in raw.splitlines(keepends=True):
            # splitlines treats CR as a boundary too; only LF terminates protocol lines.
            newline = fragment.endswith(b"\n")
            if not self.discarding:
                self.pending.extend(fragment)
                if len(self.pending) > MAX_LINE_BYTES:
                    if self.pending.startswith(PHASE_PREFIX):
                        self.error("Oversized phase line was ignored")
                    self.pending.clear()
                    self.discarding = True
            if newline:
                if not self.discarding:
                    self.consume(bytes(self.pending).rstrip(b"\r\n"))
                self.pending.clear()
                self.discarding = False
        return len(raw)

    def consume(self, line: bytes) -> None:
        if not line.startswith(PHASE_PREFIX):
            return
        observed = monotonic_ms()
        try:
            event = json.loads(line[len(PHASE_PREFIX):], parse_constant=reject_nonfinite_json)
            if not isinstance(event, dict) or event.get("event") not in PHASES:
                raise ValueError("unknown phase event")
            tick = event.get("monotonic_ms")
            if isinstance(tick, bool) or not isinstance(tick, (int, float)) or not math.isfinite(tick):
                raise ValueError("monotonic_ms must be a finite number")
            if "trial" not in event:
                raise ValueError("missing trial")
            # Preserve driver fields separately: driver clock origin is not assumed.
            entry = {"driver": event, "observed_monotonic_ms": observed,
                     "observed_elapsed_ms": observed - self.started_ms}
            self.report["phase_events"].append(entry)
            kind = event["event"]
            if kind == "interval_start":
                if self.active is not None:
                    self.error("interval_start arrived while another interval was active")
                    self.close(observed, "overlapping_interval_start")
                self.active = {"trial": event["trial"],
                               "start_observed_monotonic_ms": observed,
                               "start_driver_monotonic_ms": tick,
                               "end_observed_monotonic_ms": None,
                               "end_driver_monotonic_ms": None,
                               "outcome": None, "closure": None}
                self.report["intervals"].append(self.active)
            elif kind == "interval_end":
                if self.active is None or self.active["trial"] != event["trial"]:
                    self.error("interval_end has no matching active trial")
                else:
                    self.active["end_driver_monotonic_ms"] = tick
                    self.active["outcome"] = event.get("outcome")
                    self.close(observed, "interval_end")
            elif kind == "finished":
                self.report["death"]["finished_event_received"] = True
        except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
            self.error(f"Invalid phase record: {exc}")

    def close(self, observed: float, reason: str) -> None:
        if self.active is not None:
            self.active["end_observed_monotonic_ms"] = observed
            self.active["closure"] = reason
            self.active = None


def cleanup_group(proc: subprocess.Popen[bytes], deadline: float) -> dict[str, Any]:
    """Reserve TERM, KILL/reap and verification phases inside one hard deadline."""
    started = time.monotonic()
    budget = max(0.0, deadline - started)
    term_deadline = started + budget / 3
    reap_deadline = started + 2 * budget / 3
    result: dict[str, Any] = {"attempted": True, "signals": [], "errors": [],
                              "child_reaped": False, "remaining_live_pids": None,
                              "membership_verified": False, "complete": False,
                              "timing": {"budget_seconds": budget,
                                         "term_phase_end_seconds": budget / 3,
                                         "reap_phase_end_seconds": 2 * budget / 3,
                                         "stages": [], "dropped_stages": 0}}
    timing = result["timing"]
    pgid = proc.pid

    def note(stage: str, **extra: Any) -> None:
        now = time.monotonic()
        if len(timing["stages"]) < 32:
            timing["stages"].append({"stage": stage, "elapsed_seconds": now - started,
                                      "remaining_seconds": max(0.0, deadline - now), **extra})
        else:
            timing["dropped_stages"] += 1

    if pgid == os.getpgrp():
        result["errors"].append("Refusing to signal supervisor's own process group")
        note("refused_own_group")
        return result

    last: dict[str, Any] = {"members": None, "complete": False,
                           "errors": ["Membership was not observed before the cleanup deadline"]}
    pending_permission_errors: list[str] = []

    def snapshot(stage: str, phase_deadline: float) -> None:
        nonlocal last
        remaining = min(deadline, phase_deadline) - time.monotonic()
        if remaining <= 0:
            note(stage + "_skipped_deadline")
            return
        timeout = min(0.2, remaining)
        note(stage + "_start", timeout_seconds=timeout)
        last = process_group_snapshot(pgid, timeout=timeout)
        timing["last_membership_observed_seconds"] = time.monotonic() - started
        # A child can exit during ps. Always reap again after this slow operation.
        proc.poll()
        note(stage + "_end", membership_known=live_members(last) is not None,
             child_returncode=proc.returncode)

    def send(sig: int) -> None:
        # A live direct child proves the group is occupied. Do not delay signaling
        # for ps; an exited leader's descendants use the last membership evidence.
        proc.poll()
        if proc.returncode is not None and live_members(last) == []:
            note("skip_" + signal.Signals(sig).name + "_empty_group")
            return
        try:
            os.killpg(pgid, sig)
            result["signals"].append(signal.Signals(sig).name)
            note(signal.Signals(sig).name)
        except ProcessLookupError:
            note(signal.Signals(sig).name + "_group_missing")
        except PermissionError as exc:
            # macOS may return EPERM for an empty group. Only later verified-empty
            # membership can clear this error; unknown membership still fails.
            pending_permission_errors.append(f"{signal.Signals(sig).name}: {exc}")
            note(signal.Signals(sig).name + "_permission_error")
        except OSError as exc:
            result["errors"].append(f"{signal.Signals(sig).name}: {exc}")
            note(signal.Signals(sig).name + "_error")

    def reap_until(stage: str, phase_deadline: float) -> None:
        proc.poll()
        remaining = min(deadline, phase_deadline) - time.monotonic()
        if proc.returncode is None and remaining > 0:
            note(stage + "_start", timeout_seconds=remaining)
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                note(stage + "_timeout")
        # A timed-out wait is provisional: a later snapshot/final poll may reap.
        proc.poll()
        note(stage + "_end", child_returncode=proc.returncode)

    proc.poll()
    if proc.returncode is not None:
        snapshot("initial_membership", term_deadline)
    send(signal.SIGTERM)
    reap_until("term_wait", term_deadline)
    if proc.returncode is not None and live_members(last) != []:
        snapshot("term_membership", term_deadline)
    if proc.returncode is None or live_members(last) != []:
        # Descendants get the remainder of the TERM phase, without repeated scans.
        remaining = term_deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        send(signal.SIGKILL)
    reap_until("kill_reap", reap_deadline)

    # Only now spend the remaining time on group verification. An earlier verified
    # empty group remains empty, but a reaped leader alone never establishes this.
    while live_members(last) != [] and time.monotonic() < deadline:
        snapshot("final_membership", deadline)
        if live_members(last) == []:
            break
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(0.025, remaining))
    proc.poll()  # No blocking operation follows the final membership observation.
    result["child_reaped"] = proc.returncode is not None
    timing["final_poll_seconds"] = time.monotonic() - started
    note("final_poll", child_returncode=proc.returncode)
    if not result["child_reaped"]:
        result["errors"].append("Direct child was not reaped within the cleanup deadline")
    live = live_members(last)
    result["membership_verified"] = live is not None
    result["remaining_live_pids"] = None if live is None else [m["pid"] for m in live]
    result["remaining_zombie_pids"] = (None if last["members"] is None else
        [m["pid"] for m in last["members"] if m["state"].startswith("Z")])
    if live != []:
        result["errors"].extend(pending_permission_errors)
    if live is None:
        result["errors"].extend(last["errors"] or ["Could not establish process-group membership"])
    timing["elapsed_seconds"] = time.monotonic() - started
    timing["deadline_overrun_seconds"] = max(0.0, time.monotonic() - deadline)
    result["complete"] = result["child_reaped"] and live == [] and not result["errors"]
    return result


def run_supervised(command: list[str], output: Path, config: dict[str, Any], *,
                   env: dict[str, str] | None = None,
                   cwd: str | None = None,
                   launch_context: dict[str, Any] | None = None,
                   startup_cushion_seconds: float = 5.0,
                   sample_seconds: float = 0.1,
                   poll_seconds: float = 0.02) -> dict[str, Any]:
    """Internal command-taking seam for headless tests; CLI always runs replay.rkt."""
    if os.name != "posix":
        raise RuntimeError("This process-group supervisor requires Linux or macOS")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("stdout.log", "stderr.log", "supervisor.json", "replay.json"):
        if (output / name).exists():
            raise ValueError(f"Use a fresh output directory; {name} already exists")
    trials = config["trials"]
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer")
    init = float(config["init_timeout_seconds"])
    terminal = float(config["terminal_timeout_seconds"])
    cleanup = float(config["cleanup_timeout_seconds"])
    if any(not math.isfinite(v) or v <= 0 for v in (init, terminal, cleanup, sample_seconds, poll_seconds)):
        raise ValueError("timeouts and polling intervals must be finite and positive")
    if not math.isfinite(startup_cushion_seconds) or startup_cushion_seconds < 0:
        raise ValueError("startup cushion must be finite and nonnegative")
    budget = init + terminal * trials + cleanup + startup_cushion_seconds
    started = time.monotonic()
    started_ms = monotonic_ms()
    hard_deadline = started + budget
    run_deadline = hard_deadline - cleanup  # Reserve cleanup inside the wall budget.
    # Experiment flags must not leak from a prior capture, UI run, or benchmark.
    # Only these three freshly constructed diagnostic controls reach the driver.
    child_env = {key: value for key, value in (os.environ if env is None else env).items()
                 if not key.startswith("OPENRACKET_")}
    child_env["OPENRACKET_REPLAY_CONFIG"] = json.dumps(config)
    child_env["OPENRACKET_EXPANSION_REPLAY"] = "1"
    child_env["OPENRACKET_REPLAY_SUPPORT"] = str(Path(__file__).resolve().with_name("support.rkt"))
    report: dict[str, Any] = {
        "schema_version": 1, "command": command, "config": config,
        "cwd": cwd or str(Path.cwd()), "launch_context": launch_context,
        "started_utc": utc_now(), "started_monotonic_ms": started_ms,
        "hard_wall_budget_seconds": budget,
        "startup_cushion_seconds": startup_cushion_seconds,
        "cleanup_reserve_seconds": cleanup, "sample_period_seconds": sample_seconds,
        "pid": None, "pgid": None, "status": "starting", "errors": [],
        "timeout": {"triggered": False, "kind": None},
        "death": {"returncode": None, "signal": None, "unexpected": None,
                  "finished_event_received": False, "observed_elapsed_ms": None},
        "cleanup": {"attempted": False, "complete": None},
        "phase_events": [], "intervals": [], "rss_samples": [],
        "measurement_notes": [
            "RSS is external summed live process-group resident memory; shared pages may be counted more than once.",
            "RSS is sampled, not an exact peak or Racket heap/allocation measurement; unavailable RSS is null.",
            "Interval membership uses supervisor observation times, not synchronized driver clocks. Stdout buffering, polling, and snapshot duration introduce boundary uncertainty.",
            "Driver phase monotonic_ms is preserved without assuming the same clock origin as Python.",
            "Process groups contain ordinary descendants; a descendant that starts a new session/group escapes this mechanism.",
            "Only the direct child is wait-reaped; orphan descendant zombies are reported but are not live processes.",
        ],
    }
    proc: subprocess.Popen[bytes] | None = None
    reader: PhaseReader | None = None
    # Regular files avoid stdout/stderr pipe deadlock, including inherited descriptors.
    with (output / "stdout.log").open("xb", buffering=0) as stdout, \
         (output / "stderr.log").open("xb", buffering=0) as stderr, \
         (output / "stdout.log").open("rb", buffering=0) as tail:
        reader = PhaseReader(tail, report, started_ms)
        old_handlers = {}
        if threading.current_thread() is threading.main_thread():
            def interrupted(signum: int, _frame: Any) -> None:
                raise SupervisorInterrupted(signum)
            for signum in (signal.SIGINT, signal.SIGTERM):
                old_handlers[signum] = signal.signal(signum, interrupted)
        try:
            proc = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                    stdin=subprocess.DEVNULL, env=child_env, cwd=cwd,
                                    start_new_session=True, close_fds=True)
            report["pid"] = report["pgid"] = proc.pid
            next_sample = started
            while True:
                reader.poll()
                now = time.monotonic()
                if now >= next_sample:
                    sample_start = monotonic_ms()
                    snap = process_group_snapshot(proc.pid, timeout=min(0.2, max(0.01, run_deadline - now)))
                    sample_end = monotonic_ms()
                    report["rss_samples"].append({
                        "monotonic_ms": sample_start,
                        "elapsed_ms": sample_start - started_ms,
                        "snapshot_finished_monotonic_ms": sample_end,
                        "trial_observed": None if reader.active is None else reader.active["trial"],
                        **snap,
                    })
                    next_sample = time.monotonic() + sample_seconds
                code = proc.poll()
                if code is not None:
                    report["death"]["observed_elapsed_ms"] = monotonic_ms() - started_ms
                    report["status"] = "exited"
                    break
                if time.monotonic() >= run_deadline:
                    report["timeout"] = {"triggered": True, "kind": "hard_wall_budget",
                                         "observed_elapsed_ms": monotonic_ms() - started_ms}
                    report["status"] = "timeout"
                    break
                time.sleep(min(poll_seconds, max(0, run_deadline - time.monotonic())))
        except SupervisorInterrupted as exc:
            report["status"] = "interrupted"
            report["errors"].append({"category": "interruption", "detail": signal.Signals(exc.signum).name})
        except KeyboardInterrupt:
            report["status"] = "interrupted"
            report["errors"].append({"category": "interruption", "detail": "KeyboardInterrupt"})
        except Exception as exc:
            report["status"] = "supervisor_error"
            report["errors"].append({"category": "supervisor", "detail": f"{type(exc).__name__}: {exc}"})
        finally:
            # Repeated cancellation must not interrupt the bounded cleanup itself.
            for signum in old_handlers:
                signal.signal(signum, signal.SIG_IGN)
            if proc is not None:
                cleanup_started = time.monotonic()
                report["cleanup"] = cleanup_group(proc, min(hard_deadline, cleanup_started + cleanup))
                report["cleanup"]["elapsed_seconds"] = time.monotonic() - cleanup_started
                report["death"]["returncode"] = proc.returncode
                report["death"]["signal"] = -proc.returncode if proc.returncode is not None and proc.returncode < 0 else None
                if not report["cleanup"]["complete"]:
                    print("OPENRACKET_REPLAY_CLEANUP_FAILURE " + json.dumps(report["cleanup"], allow_nan=False),
                          file=sys.stderr, flush=True)
            # Drain finite captured output after cleanup without holding a pipe open.
            # Parsing is bounded by time and bytes; all bytes remain in the raw log.
            drain_deadline = min(hard_deadline, time.monotonic() + 0.25)
            while time.monotonic() < drain_deadline and reader.poll():
                pass
            report["stdout_unparsed_bytes"] = max(0, os.fstat(tail.fileno()).st_size - tail.tell())
            if reader.pending and reader.pending.startswith(PHASE_PREFIX):
                reader.error("Unterminated phase line was ignored")
            reader.close(monotonic_ms(), "supervisor_stop")
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
    report["death"]["unexpected"] = (None if proc is None else
        not report["death"]["finished_event_received"] or proc.returncode != 0)
    replay = output / "replay.json"
    report["driver_result"] = {"path": str(replay), "exists": replay.is_file()}
    if report["status"] == "exited":
        report["status"] = "ok" if not report["death"]["unexpected"] else "driver_failed"
        if not replay.is_file():
            report["errors"].append({"category": "driver_result", "detail": "Driver did not write replay.json"})
            report["status"] = "driver_failed"
    if proc is not None and not report["cleanup"]["complete"] and report["status"] == "ok":
        report["status"] = "cleanup_failed"
    for interval in report["intervals"]:
        lo, hi = interval["start_observed_monotonic_ms"], interval["end_observed_monotonic_ms"]
        samples = [s for s in report["rss_samples"] if lo <= s["monotonic_ms"] <= hi]
        values = [s["rss_bytes"] for s in samples if s["rss_bytes"] is not None]
        interval["rss_sample_count"] = len(samples)
        interval["rss_available_sample_count"] = len(values)
        interval["rss_observed_peak_bytes"] = max(values) if values else None
    report["finished_utc"] = utc_now()
    report["elapsed_seconds"] = time.monotonic() - started
    temporary = output / f".supervisor-{os.getpid()}.tmp"
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, output / "supervisor.json")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racket", required=True, help="Racket executable path")
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Fresh run output directory")
    parser.add_argument("--trials", type=int, default=2)
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be positive")
    capture = args.capture.resolve()
    if not capture.is_file():
        parser.error("--capture must name an existing capture file")
    output = args.output.resolve()
    config = {"capture": str(capture), "output": str(output), "trials": args.trials,
              "init_timeout_seconds": 30, "terminal_timeout_seconds": 60,
              "cleanup_timeout_seconds": 2}
    try:
        launch_context, env = load_launch_context(capture)
        # Resolve relative executable paths before restoring the captured cwd.
        racket = shutil.which(args.racket) or args.racket
        if os.sep in racket:
            racket = str(Path(racket).resolve())
        report = run_supervised(
            [racket, str(Path(__file__).resolve().with_name("replay.rkt"))], output, config,
            env=env, cwd=launch_context["cwd"], launch_context=launch_context)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"supervise: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "supervisor": str(output / "supervisor.json"),
                      "replay": str(output / "replay.json")}))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
