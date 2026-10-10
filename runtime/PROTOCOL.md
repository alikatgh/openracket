# OpenRacket runtime bridge, protocol 1

Start `racket runtime/bridge.rkt` with piped stdin, stdout, and stderr. The bridge
uses an actual Racket process and a persistent Racket namespace. It is not an
interpreter implemented in Rust. No source file is written by Run.

The program being evaluated is **trusted local code**, with the same file,
network, process, and native-extension access as the Racket executable. A
separate process and custodian improve cancellation and crash recovery; they
are **not a security sandbox**. Do not run untrusted programs here.

## Framing and ownership

Each request and event is one UTF-8 JSON object followed by LF. JSON escapes
embedded newlines. Only the bridge's dedicated writer uses protocol stdout.
The user's current stdout, stderr, and printer use separately captured ports.
Raw process stderr is for engine startup/internal failures and must still be
read by the host. Code that deliberately opens OS file descriptor 1 or writes
through unsafe/native FFI can bypass current ports; trusted-code scope applies.

Request IDs are supplied by the host, and copied to associated events. IDs must
be unique for the lifetime of a process. Control requests use independent IDs.
The host additionally needs a process-generation token so late reader events
from an old, killed process cannot affect a restarted process.

A single run, eval, or check can be active. Concurrent ordinary operations get
an error with kind `busy` and their own terminal `done`. Break and input are
accepted concurrently. The host owns interaction history and document state.

## Requests

```json
{"id":1,"op":"run","source":"#lang racket\n(define x 1/3)","path":"/project/main.rkt","cwd":"/project"}
{"id":2,"op":"check","source":"(+ x\n"}
{"id":3,"op":"eval","source":"(values (+ x 1) 2/7)"}
{"id":4,"op":"input","text":"answer\n","eof":false}
{"id":5,"op":"break"}
{"id":6,"op":"reset"}
{"id":7,"op":"shutdown"}
```

- `run`: fresh module registry/namespace and custodian. Disposes resources from
  the prior Run and its interactions. Reads the exact unsaved `source` string
  with Racket's module reader. `path` is an absolute saved-source path, or null
  for an untitled buffer, represented internally as `cwd/untitled.rkt`.
  `cwd` is the working directory for ordinary file I/O. Relative module imports
  resolve from `path`'s directory. The module is declared under its source path
  without saving or replacing the original file. Instantiates the module and
  its `main` submodule if present; interactions use `module->namespace`, so
  private definitions are available. Run resets even if reading or compilation
  then fails. A plain definitions buffer with no module/language declaration
  yields `missing-language`; the UI can explicitly offer to prepend
  `#lang racket`. The bridge never silently changes the source or language.
- `check`: parses the entire input with the real Racket interaction reader,
  without evaluating or expanding forms. Reader EOF exceptions mean incomplete;
  other reader errors mean error. It handles comments, strings, here-strings,
  character literals, datum comments, and multiline expressions. A custom
  reader may execute its reader implementation, so this is still trusted code.
  Send this when submitting input, not on every keystroke. A check result never
  implies a syntactically complete form will expand or evaluate successfully.
- `eval`: evaluates forms sequentially in the active module namespace, or a
  fresh `racket/base` top-level namespace before the first Run. Definitions and
  mutations persist. Dynamic parameters also persist across submissions,
  including current-directory, custom parameters, readtables, reader settings,
  and current-print. A failed form stops the rest of that submission; prior
  definitions and parameter changes remain. The real printer preserves exact fractions and emits
  each non-void value, including multiple values, through `value` events.
- `input`: supplies **exactly** `text`, without appending a newline. Optional
  `eof:true` closes program input after the text. Input is for the current
  operation; it is not source code. Each operation gets a fresh stdin stream.
  `input-request` is emitted when a read needs bytes. An input request carries
  its own ID; its `done` acknowledges delivery, not evaluation completion.
- `break`: cooperatively interrupts the active worker immediately. After
  250 ms, shuts down the session custodian if the worker has not stopped.
  Cancels session-managed threads, ports, sockets, and subprocesses (the user
  parameter is initially `current-subprocess-custodian-mode = 'kill`). Pure
  namespace bindings remain, but canceled resource handles may no longer work.
  A program can catch a break or change those parameters; the Rust host must
  hard-kill the process after its deadline and restart it when needed.
- `reset`: only while idle; clears namespace and resources. Does not restart
  the engine process.
- `shutdown`: cancels managed resources, drains protocol events, and exits.

Every accepted request has a terminal `done` unless the OS process is killed,
crashes, exits through unsafe code, or cannot make progress. The host must also
handle process EOF/error and its own cancellation timeout.

## Events

```json
{"event":"ready","protocol":1,"racket_version":"9.3","max_source_chars":2097152,"max_output_bytes":262144}
{"event":"started","id":1,"op":"run"}
{"event":"stdout","id":1,"text":"hello\n"}
{"event":"stderr","id":1,"text":"warning\n"}
{"event":"value","id":3,"text":"4/3\n"}
{"event":"check","id":2,"status":"incomplete"}
{"event":"input-request","id":3}
{"event":"error","id":3,"kind":"runtime","message":"/: division by zero","locations":[{"source":"/project/main.rkt","line":2,"column":0,"position":14,"span":26}]}
{"event":"truncated","id":3,"stream":"stdout","limit":262144,"event_limit":256,"message":"Output limit reached; further output from this operation is discarded."}
{"event":"done","id":3,"status":"ok"}
```

`ready` occurs only on process startup. `check.status` is `complete`,
`incomplete`, or `error`. `done.status` is `ok`, `error`, or `interrupted`.
Incomplete check is a successful operation and has `done.status = ok`; a
malformed-reader check has `done.status = error`. Error kinds include `read`,
`incomplete`, `syntax`, `runtime`, `interrupted`, `missing-language`, `busy`, and
`protocol`. The bridge provides bounded, structured exception context.

Locations: line is 1-based; column is 0-based; position is a 1-based **Unicode
character** offset, not a UTF-8 byte offset; span counts characters. Unknown
fields are JSON null. Tab columns follow Racket's port line-counting rules.
`source` is the original path, or `interactions`. Runtime stack locations can
cover a whole function rather than the exact failing expression. Syntax/read
exceptions often provide more precise spans. Filter matching source before
highlighting; dependency errors must not highlight the current buffer.

A Break acknowledgement is `done` for the **Break request's ID**. The active
operation separately ends with `done.status = interrupted` and its original ID.
Do not clear the hard-kill deadline on the acknowledgement. There is no second
`ready` after Break or reset. Background threads may emit bounded output after
an ordinary operation's `done`, until Run/reset/Break cancels them.

## Resource and cancellation limits

- Protocol line: 8 MiB before JSON parsing. Source: 2,097,152 characters.
- Program stdin: 64 KiB bounded pipe; one input chunk at most 64 KiB UTF-8.
  Supplying data without a pending read can fill the buffer. Overflow is an
  explicit error including the number of accepted bytes; do not blindly retry.
- Output per operation, shared across stdout/stderr/value: 256 KiB or 256
  events, whichever occurs first. UTF-8 output chunks are at most 4 KiB before
  JSON encoding. Partial code points are retained between writes. Invalid
  byte sequences are shown using U+FFFD. Reaching a limit emits one explicit
  truncation notice, and later output for that operation is discarded.
- Protocol event queue: 512 bounded entries. User-output enqueue is
  non-blocking. Reserved capacity relative to the per-operation event limit
  leaves room for terminal/control events under the supported one-operation
  request flow. The host must continually drain both process output pipes,
  keep bounded transcript storage, and prevent unbounded command queuing.
- Output is periodically flushed at about 30 ms during execution, and before
  `done`. Per-stream buffering means stdout/stderr interleaving is approximate.
- Graceful cancellation has a 250 ms custodian fallback; the native supervisor
  uses an independent hard-kill deadline for a stuck VM/FFI call. Restart loses
  the namespace and requires Run again.

This bounds bridge buffering, not memory allocated by the user's program.
There is no memory quota, security isolation, debugger, or execution time limit
other than a requested Break.

## Supported scope and limits

The tested baseline is plain-text `#lang racket` and `#lang racket/base`, using
Racket CS 9.3. Ordinary installed languages may work, but DrRacket-specific
language settings, GUI snips/WXME, teaching-language adapters, language-specific
submit predicates/configure-runtime integration, stepper/debugger/coverage,
Check Syntax, images and rich values, and package installation are not
implemented. Values are textual. Evaluator parameterizations and preserved thread-cell
values are captured together and restored only inside the next user worker.
The control/writer threads never receive user parameter state. The bridge
always overlays fresh operation stdin/stdout/stderr/value ports, its session
custodian, namespace, and exit handler, so redirecting a port in one submission
does not lose or misattribute the next submission’s output. Run/reset clear
the parameter snapshot. Abrupt thread death or forced cancellation retains
the last completed snapshot; code interrupted in the middle of mutation can
leave namespace state uncertain. Standard input is line-oriented in the UI
but the bridge supplies bytes and EOF; reading input from background threads after the active
submission has finished is not supported. Run does not automatically run the `test`
submodule; tests can be invoked explicitly. Programs that require the full
Racket distribution need it installed separately.

## Verification

```sh
RACKET_BIN=/path/to/racket python3 runtime-tests/test_bridge.py
RACKET_BIN=/path/to/racket python3 runtime-tests/benchmark_bridge.py
```

The integration suite starts real Racket processes; it does not substitute a
mock interpreter. Additional independent adversarial tests live under `qa/`.
