# Cheap protocol edge checks

Run from the repository root with the installed Python; no packages, Racket,
network access, or Rust/GUI build are needed for the offline tests:

```sh
python3 -B runtime-tests/test_bridge.py BridgeHarnessTests
python3 -B runtime-tests/test_evidence_edges.py
```

These tests use in-memory streams, queues, a mocked monotonic clock, and the real
replay-evidence emitter/decoder with mocked file I/O. They write no test files.
`-B` prevents Python bytecode caches. Coverage includes malformed/trailing JSON
events and recovery, CRLF/escaped Unicode output, final frames at EOF, missing
completion, null/duplicate terminal IDs, a shared shrinking timeout, and zero
timeout without consuming a queued event. Evidence cases cover explicit null
versus missing/falsy payloads, mixed duplicate payloads, truncated documents,
digest mismatch, orphan array chunks, repeated begin, and corrupt/trailing data.
The stream tests establish Python harness behavior; they do not execute Racket
or the Rust supervisor.

The additional request-frame checks require a real Racket executable and use the
existing `RuntimeTests` skip marker when it is unavailable. Albert can run only
the new cases with an existing installation:

```sh
RACKET_BIN=/absolute/path/to/racket python3 -B runtime-tests/test_bridge.py \
  RuntimeTests.test_malformed_string_escapes_and_nested_json_recover \
  RuntimeTests.test_trailing_data_cannot_dispatch_reset_or_shutdown
```

These exercise the real bridge, checking malformed escapes/nested JSON and
atomic rejection of reset/shutdown prefixes with trailing data. The session
binding must survive and the process must remain usable after every rejection.
They use the existing harness's shutdown/cleanup behavior. No Racket packages
or toolchains are installed by these tests. A skip is not runtime validation.

If pytest is already installed, run the two runtime test files and the existing
independent adversarial checks without bytecode, pytest cache, or plugin loading:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -B -m pytest -p no:cacheprovider -q -rs \
  runtime-tests/test_bridge.py runtime-tests/test_evidence_edges.py \
  qa/test_runtime_adversarial.py
```

When Racket is available, that last command also selects the existing full
integration suites, including their temporary-file and process-cleanup tests.
Use the two offline commands above for strictly memory-only checks.
