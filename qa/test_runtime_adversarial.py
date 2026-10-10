#!/usr/bin/env python3
"""Independent, bounded black-box tests of the real NDJSON Racket bridge.

Only project-owned code and small test programs written here are executed.
No window, network service, user files, or third-party test code is involved.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RACKET = (os.environ.get("RACKET") or os.environ.get("RACKET_BIN")
          or os.environ.get("RACKET_EXECUTABLE") or "racket")


class Bridge:
    def __init__(self):
        self.events = queue.Queue()
        self.errors = []
        self.trace = []
        self.next_id = 1
        self.p = subprocess.Popen(
            [RACKET, str(ROOT / "runtime/bridge.rkt")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", start_new_session=True, bufsize=1,
        )
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()
        self.ready = self.until(lambda e: e.get("event") == "ready", timeout=10)[-1]

    def _read(self):
        try:
            for line in self.p.stdout:
                self.events.put(json.loads(line))
        except Exception as e:
            self.events.put({"event": "harness-error", "message": repr(e)})
        self.events.put({"event": "bridge-eof"})

    def _stderr(self):
        for line in self.p.stderr:
            if len(self.errors) < 100:
                self.errors.append(line)

    def send(self, op, **fields):
        ident = self.next_id
        self.next_id += 1
        self.p.stdin.write(json.dumps(dict(id=ident, op=op, **fields), ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        return ident

    def until(self, predicate, timeout=5):
        result = []
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                e = self.events.get(timeout=max(.001, end - time.monotonic()))
            except queue.Empty:
                break
            result.append(e)
            self.trace.append(e)
            if e.get("event") in ("bridge-eof", "harness-error"):
                raise AssertionError(f"Bridge failed: {e}; stderr={''.join(self.errors)}")
            if predicate(e):
                return result
        raise AssertionError(f"Timed out. Last events={result[-8:]}; stderr={''.join(self.errors)}")

    def done(self, ident, timeout=5):
        return self.until(lambda e: e.get("event") == "done" and e.get("id") == ident, timeout)

    def request(self, op, **fields):
        return self.done(self.send(op, **fields))

    def close(self):
        try:
            if self.p.poll() is None:
                self.send("shutdown")
                self.p.wait(timeout=1)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            pass
        finally:
            # A whole private test process group is the safety net for a failed
            # subprocess-cleanup test, including a child surviving bridge exit.
            try:
                os.killpg(self.p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.p.wait(timeout=2)
            for port in (self.p.stdin, self.p.stdout, self.p.stderr):
                port.close()


def output(events):
    return "".join(e.get("text", "") for e in events
                   if e.get("event") in ("stdout", "stderr", "value"))


class RuntimeAcceptance(unittest.TestCase):
    def setUp(self):
        self.b = Bridge()

    def tearDown(self):
        self.b.close()

    def assert_ok(self, events):
        self.assertEqual(events[-1].get("status"), "ok", events)
        self.assertFalse([e for e in events if e.get("event") == "error"], events)

    def test_persistent_repl_and_multiple_values(self):
        self.assert_ok(self.b.request("eval", source="(define λ 1/3)"))
        events = self.b.request("eval", source='(values (+ λ 2) "你好 🌱")')
        self.assert_ok(events)
        self.assertIn("7/3", output(events))
        self.assertIn("你好 🌱", output(events))
        self.assertEqual(output(events).count("7/3"), 1)
        self.assertEqual(output(self.b.request("eval", source="(void)")), "")

    def test_unsaved_run_relative_import_and_namespace_reset(self):
        with tempfile.TemporaryDirectory(prefix="racket qa λ ") as directory:
            folder = Path(directory)
            main = folder / "main λ.rkt"
            main.write_text("#lang racket\n(error \"saved copy must not run\")\n")
            (folder / "sibling.rkt").write_text("#lang racket/base\n(provide n)\n(define n 40)\n")
            source = '#lang racket\n(require "sibling.rkt")\n(define result (+ n 2))\nresult\n'
            events = self.b.request("run", source=source, path=str(main), cwd=directory)
            self.assert_ok(events)
            self.assertIn("42", output(events))
            self.assert_ok(self.b.request("eval", source="(define repl-only 9)"))
            self.assertIn("42", output(self.b.request("eval", source="result")))
            self.assert_ok(self.b.request("run", source=source, path=str(main), cwd=directory))
            self.assertEqual(self.b.request("eval", source="repl-only")[-1]["status"], "error")
            self.assertIn("saved copy must not run", main.read_text())

    def test_module_directory_differs_from_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="racket qa cwd ") as directory:
            root = Path(directory)
            module_dir = root / "source λ"
            module_dir.mkdir()
            (module_dir / "sibling.rkt").write_text("#lang racket/base\n(provide n)\n(define n 42)\n")
            (module_dir / "asset.txt").write_text("relative asset λ\n")
            source = '''#lang racket
(require "sibling.rkt" racket/runtime-path)
(define-runtime-path asset "asset.txt")
(displayln (file->string asset))
n
'''
            events = self.b.request("run", source=source,
                                    path=str(module_dir / "unsaved.rkt"), cwd=str(root))
            self.assert_ok(events)
            self.assertIn("42", output(events))
            self.assertIn("relative asset λ", output(events))
            self.assertFalse((module_dir / "unsaved.rkt").exists())

    def test_reader_incomplete_and_invalid_recover(self):
        for source in ["(+ 1", '"unfinished', "#| unfinished"]:
            events = self.b.request("check", source=source)
            self.assertTrue(any(e.get("status") == "incomplete" for e in events), events)
        events = self.b.request("eval", source="(+ 1")
        self.assertEqual(events[-1]["status"], "error")
        self.assertTrue(any(e.get("kind") == "incomplete" for e in events), events)
        events = self.b.request("check", source=")")
        self.assertTrue(any(e.get("event") == "error" for e in events), events)
        self.assertIn("3", output(self.b.request("eval", source="(+ 1 2)")))

    def test_errors_keep_location_and_recover(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "broken.rkt")
            events = self.b.request("run", source="#lang racket\n(define λ 1)\n(missing λ)\n", path=path, cwd=directory)
            self.assertEqual(events[-1]["status"], "error")
            locations = [loc for e in events for loc in e.get("locations", [])]
            self.assertTrue(any(l.get("source") == path and l.get("line") == 3 for l in locations), events)
            events = self.b.request("run", source="(+ 1 2)", path=path, cwd=directory)
            self.assertTrue(any("#lang" in e.get("message", "") for e in events), events)
            self.assert_ok(self.b.request("run", source="#lang racket\n42\n", path=path, cwd=directory))

    def test_stdin_is_separate_from_protocol(self):
        ident = self.b.send("eval", source='(display "Name? ") (define name (read-line)) (string-append "Hi " name)')
        events = self.b.until(lambda e: e.get("event") == "input-request")
        self.assertEqual(events[-1]["id"], ident)
        ack = self.b.send("input", text="你好 🌱\n")
        # The acknowledgement and evaluation may finish in either valid order.
        done_ids = set()
        while done_ids != {ident, ack}:
            more = self.b.until(lambda e: e.get("event") == "done")
            events += more
            done_ids.add(more[-1]["id"])
        self.assertIn("Hi 你好 🌱", output(events))
        self.assert_ok(self.b.request("eval", source="(+ 2 3)"))

    def test_stdin_eof_and_break_while_waiting(self):
        ident = self.b.send("eval", source="(read-line)")
        self.b.until(lambda e: e.get("event") == "input-request")
        ack = self.b.send("input", text="", eof=True)
        events, completed = [], set()
        while completed != {ident, ack}:
            more = self.b.until(lambda e: e.get("event") == "done")
            events += more
            completed.add(more[-1]["id"])
        self.assertIn("#<eof>", output(events))
        self._break_loop("(read-line)")

    def _break_loop(self, source):
        ident = self.b.send("eval", source=source)
        self.b.until(lambda e: e.get("event") == "started" and e.get("id") == ident)
        time.sleep(.08)
        start = time.monotonic()
        interrupt = self.b.send("break")
        done_ids = set()
        events = []
        while ident not in done_ids or interrupt not in done_ids:
            more = self.b.until(lambda e: e.get("event") == "done", timeout=2)
            events += more
            done_ids.add(more[-1]["id"])
        self.assertLess(time.monotonic() - start, 1.5, events)
        self.assertTrue(any(e.get("id") == ident and e.get("status") == "interrupted" for e in events), events)
        self.assert_ok(self.b.request("eval", source="(+ 2 3)"))
        return events

    def test_infinite_loop_break_recovers(self):
        self._break_loop("(let loop () (loop))")

    def test_disabled_break_is_forcibly_stopped(self):
        self._break_loop("(parameterize-break #f (let loop () (loop)))")

    def test_output_flood_is_bounded_and_breakable(self):
        events = self._break_loop('(let loop () (displayln "λ🌱 flood") (loop))')
        user_output = [e for e in events if e.get("event") in ("stdout", "stderr", "value")]
        self.assertLessEqual(len(user_output), 256, len(user_output))
        self.assertLessEqual(sum(len(e["text"].encode("utf-8")) for e in user_output), 262148)
        self.assertTrue(any(e.get("event") == "truncated" for e in events), events[-5:])

    def test_utf8_split_across_byte_writes(self):
        source = '(for ([b (in-bytes (string->bytes/utf-8 "λ你好🌱"))]) (write-byte b) (flush-output))'
        events = self.b.request("eval", source=source)
        self.assert_ok(events)
        self.assertEqual(output(events), "λ你好🌱")

    def test_very_large_single_write_is_bounded(self):
        events = self.b.request("eval", source='(display (make-string 1000000 #\\λ))')
        self.assert_ok(events)
        self.assertTrue(any(e.get("event") == "truncated" for e in events), events[-5:])
        self.assertLessEqual(len(output(events).encode("utf-8")), 262148)
        self.assert_ok(self.b.request("eval", source="1"))

    def test_busy_rejection_does_not_corrupt_original(self):
        ident = self.b.send("eval", source="(sleep 0.25) 42")
        self.b.until(lambda e: e.get("event") == "started")
        later = self.b.send("eval", source="100")
        events = self.b.done(later)
        self.assertEqual(events[-1]["status"], "error")
        self.assertTrue(any(e.get("kind") == "busy" for e in events), events)
        events = self.b.done(ident)
        self.assertIn("42", output(events))
        self.assertNotIn("100", output(events))

    def test_repeated_runs_clear_prior_definitions(self):
        for i in range(20):
            events = self.b.request("run", source=f"#lang racket/base\n(define count {i})\n", path=None, cwd=str(ROOT))
            self.assert_ok(events)
            self.assertEqual(output(self.b.request("eval", source="count")).strip(), str(i))

    def test_background_output_keeps_its_origin_and_stops_on_run(self):
        events = self.b.request("eval", source='(thread (lambda () (sleep 0.15) (displayln "old origin")))')
        old_id = events[-1]["id"]
        more = self.b.until(lambda e: e.get("event") == "stdout", timeout=2)
        self.assertEqual(more[-1]["id"], old_id)
        self.assertIn("old origin", output(more))
        events = self.b.request("eval", source='(thread (lambda () (sleep 0.5) (displayln "must be stopped")))')
        self.assert_ok(events)
        self.assert_ok(self.b.request("run", source="#lang racket/base\n42", path=None, cwd=str(ROOT)))
        time.sleep(.6)
        self.assertFalse(any("must be stopped" in e.get("text", "") for e in list(self.b.events.queue)))

    @unittest.skipUnless(Path("/proc").exists(), "Linux memory observation")
    def test_slow_protocol_consumer_does_not_grow_without_bound(self):
        # Separate bridge intentionally has no stdout reader during the flood.
        # No deadlock may remain once its consumer resumes. OS pipes apply the
        # same backpressure the app's reader would create if temporarily stalled.
        p = subprocess.Popen([RACKET, str(ROOT / "runtime/bridge.rkt")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.assertEqual(json.loads(p.stdout.readline())["event"], "ready")
            def rss():
                lines = Path(f"/proc/{p.pid}/status").read_text().splitlines()
                return int(next(x for x in lines if x.startswith("VmRSS:")).split()[1])
            before = rss()
            p.stdin.write(json.dumps({"id": 1, "op": "eval", "source": '(let loop () (display (make-string 4096 #\\x)) (loop))'}) + "\n")
            p.stdin.flush()
            time.sleep(.35)
            after = rss()
            self.assertLess(after - before, 64 * 1024, "over 64 MiB retained during capped flood")
            p.stdin.write('{"id":2,"op":"break"}\n')
            p.stdin.flush()
            time.sleep(.35)
            received = queue.Queue()
            def read():
                for line in p.stdout:
                    received.put(json.loads(line))
            threading.Thread(target=read, daemon=True).start()
            terminal = set()
            end = time.monotonic() + 2
            while terminal != {1, 2} and time.monotonic() < end:
                e = received.get(timeout=max(.01, end - time.monotonic()))
                if e.get("event") == "done":
                    terminal.add(e["id"])
            self.assertEqual(terminal, {1, 2})
        finally:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=2)
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()

    @unittest.skipUnless(Path("/proc").exists() and Path("/usr/bin/sleep").exists(), "Linux subprocess fixture")
    def test_reset_cleans_spawned_subprocess(self):
        events = self.b.request("eval", source='(define-values (p o i e) (subprocess #f #f #f "/usr/bin/sleep" "30")) (subprocess-pid p)')
        self.assert_ok(events)
        pid = int(output(events).strip())
        self.assertTrue(Path(f"/proc/{pid}").exists())
        self.assert_ok(self.b.request("reset"))
        end = time.monotonic() + 1
        while time.monotonic() < end and Path(f"/proc/{pid}/stat").exists():
            if Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z":
                break
            time.sleep(.01)
        running = Path(f"/proc/{pid}/stat").exists() and Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
        self.assertFalse(running, f"Spawned process {pid} survived namespace reset")


if __name__ == "__main__":
    unittest.main(verbosity=2)
