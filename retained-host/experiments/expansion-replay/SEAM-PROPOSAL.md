# Minimal capture and readiness seams

Historical design rationale, superseded by the runnable implementation contract in README.md.
Capture/replay are now implemented and headlessly tested; native execution remains pending.
All source line numbers below refer to the verified official 9.3 archives.

## Pinned evidence

- drracket-core-lib.zip SHA-1 `d55515fcc1d1da846555ea0b5c1b593c4af619ef`
- drracket-plugin-lib.zip SHA-1 `536a7093639c0eabc33bfb77be13a9b2a0d2ad0f`
- Source/URL and SHA-256 details: `observed-contract.json`
- Base mixed-1MiB SHA-256:
  `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`
- Base length 1,048,576; edit position 524,139, from the existing fixture generator.

The existing benchmark inserts `x` before the initial lexer wait and 80 more
characters in its warm phase. The actual expansion request may therefore contain
the original fixture or a later revision. Capture the real request bytes/string,
revision order, and terminal pairing; do not relabel a regenerated base fixture as
the exact snapshot that produced the integrated abnormal termination.

## Capture seam: a separate, diagnostic-only native capture run

The capture run requires the same full package installation, untouched tools and
preferences, source identity, stock Run configuration and 128 MiB child limit as
the integrated run. Its timings are not performance evidence. No package installs
or changes to the existing benchmark are required by this proposal.

1. `drracket/private/module-language.rkt:2509–2514`: wrap the actual second argument
   to the registry `place-channel-put` with a capture helper that returns the same
   value. Save the evaluated list in original order: module path, exported id,
   monitor boolean for every registration. This observes the frozen list actually
   sent to the child, not a fresh guess from package scanning. The getter/accessors
   are in `drsig.rkt:149–155`'s internal signature; the public signature at 139–147
   does not export them. `tools.rkt:429` freezes registration before tool phases.
2. `module-language.rkt:2533–2534`: immediately after `to-send` is constructed and
   before it is sent, copy its non-capability fields 0, 1, 3, and 5 to a record,
   plus the captured registry and monotonically increasing request id. Keep the
   original `to-send` unchanged. Fields 2 and 4 are local response/status channels;
   recreate them inside the diagnostic process, never serialize those channels.
3. Do not re-extract editor text: `module-language.rkt:1344–1354` has already made
   the authoritative string or WXME byte snapshot. Preserve which representation
   was sent. Preserve `port-name`'s actual type/path, the exact prefab settings,
   and the actual currently-open-files value even though the present worker does
   not forward that last field into `new-job`.
4. Capture environment identity, not secrets: Racket/VM/platform; collection paths
   and links; compiled-file roots/paths; source/cwd; PLTUSERHOME/PLTADDONDIR/PLTCOLLECTS
   if set; preference file identity and content hash; installed package manifest
   and checksums; worker/handler source hashes. Reuse the same isolated CI profile
   and path layout for replay and verify hashes before launch. Do not change limits
   to make a run complete. Keep source-file identity at the captured path.
5. Serialize the data-only record with Racket serialization (preserves paths,
   prefab settings, strings and bytes); never flatten through JSON. Put hashes and
   human-readable summaries in a sidecar. Exclude all live channels, callbacks,
   syntax and result capability payloads. Reject unsupported capture values.
6. For comparison, observe actual status and terminal result in `send-to-place`'s
   receive loop at 2549–2575, before passing original values to existing callbacks.
   Pair by request id. Summarize terminal tag, exact exception/abnormal-termination
   text, handler keys, compiled-byte length/hash and status sequence. Monitor data
   may contain live rename channels; count/summarize without replacing or
   serializing them. Do not infer out-of-memory from a generic GUI label.

The smallest code shape is a capture helper returning its input around the actual
registry expression, plus one observer on the already-built request and one on its
responses. The helper must be loaded only into a dedicated capture clone. This is
not an approved mutation of the active benchmark or production modules.

## Readiness seam: one diagnostic-only insertion

`drracket/private/expanding-place.rkt:43–59` performs both initialization receives:
compile-lock client, then every handler's dynamic import. `60` is the only narrow
point after those operations and before the job loop begins at 61.

`readiness-proposal.diff` inserts a ready/continue exchange there, on the existing
worker's parent channel. The driver first sends the ordinary stock compile-lock
channel and captured registry. It waits for `openracket-expansion-replay-ready`,
takes the allocation/GC/RSS baseline, then sends
`openracket-expansion-replay-continue` and the unchanged-shape six-field request.
The worker cannot begin a job before the measured baseline. The extra exchange and
support work belong to the measured workload and must be disclosed.

The stock `start` body after the barrier, all handlers, `new-job`, custodians,
security guard, error handling, compile manager and live capability protocols stay
unchanged. Do not introduce a dummy expansion, add an initialization handler, use
an arbitrary sleep, remove monitors, or raise limits to simulate readiness.

Implementation must apply this insertion to a dedicated copy with the same sibling
dependencies and verify original hashes and unique context. It must not overwrite
the installed stock module. Call the result an initialization-instrumented stock
worker diagnostic; do not call its source byte-identical stock.

## Bounded replay plan, subject to parent/supervisor integration

Proposed bounds for review: worker initialization 30 seconds; each requested
expansion terminal result 60 seconds; cooperative cleanup 2 seconds followed by a
process-group TERM/KILL sequence bounded by the existing supervisor. These are
diagnostic safety bounds, not replacement lexer or product-completion gates.
No native invocation is provided yet because capture/readiness gates are unpassed.

1. Start a fresh standalone Racket OS process in the captured native environment.
   Construct the genuine `compiler/cm` compile-lock manager there. Start a real
   diagnostic copy of the stock place, initialize with the actual captured registry,
   and keep manager, result/status/monitor channels and handlers inside this process.
2. After ready, collect the process's cumulative allocation baseline and monotonic
   time; record process CPU and GC counters with their documented scope. Record
   actual GC events from all participating places if verified available. A root
   place logger alone is not proof that it receives another place's GC events.
   Report absent GC visibility as missing data, not zero GC.
3. Send the captured string/WXME snapshot with unchanged source, prefab and open
   files. Consume statuses and monitor messages until an actual terminal result.
   Retain live capabilities until the next stock job/abort or explicit end-of-test
   teardown. An expansion-only sink must not pretend it executed GUI callbacks;
   count monitor payloads, retain required channels, and document sink overhead.
4. Classify `handler-results`, actual exception types/messages, stock abnormal
   termination (including its explicit out-of-memory text), worker death, supervisor
   timeout, or driver failure separately. Preserve the original terminal payload in
   process while summarizing; do not serialize it across the OS boundary. A
   `finished-expansion` status alone is not terminal: handlers and compilation
   still run afterward (`expanding-place.rkt:247–294`).
5. Take endpoint counters immediately when the driver consumes the real terminal
   result, before JSON serialization or cleanup. Include result-consumption delay
   and support-thread work in scope. Drain already-produced GC records and bound
   trace storage so measurement overhead cannot grow unchecked.
6. Label trial one `fresh-process first expansion after initialization` (not cold
   filesystem cache). Only a subsequent replay in the same worker/manager/process
   may be labeled `same-process repeated expansion`; do not force GC or erase
   retained registries/caches. Report the previous outcome because an OOM/failed
   request yields different warmth from a successful expansion.
7. Measure current and interval-peak OS RSS with an external supervisor. Lifetime
   `getrusage`/`time` peak includes initialization and must be reported separately;
   subtracting two high-water values is not an interval peak. Racket places remain
   in the same OS process. Record any genuine OS descendants and bound cleanup.
8. At the terminal boundary, retain channels/results until the defined next-job or
   close lifecycle point. Then send stock abort if applicable, bound `place-kill`
   and place death, shut down the diagnostic custodian and manager, and exit. An
   outside supervisor must reap the complete process group even on initialization
   failure, child death, handler error or report-write failure.

## Measurement interpretation and stop condition

The permitted cumulative metric is
`process_allocation_delta_during_isolated_expansion_interval`. Do not subtract
place counters or label it a per-thread/per-place allocation owner. It includes
driver and support threads plus the stock expansion workload; the original GUI
allocator ownership is not causally established by isolation.

Compare identical capture hashes/settings/registry, terminal outcome and result
summaries before drawing a churn/GC conclusion. Any mismatch, missing readiness,
unavailable GC scope evidence, changed memory limit, dropped handler or failed
cleanup is a visible diagnostic limitation. Do not silently omit failed trials.

The original proposal stopping condition has been superseded by explicit authorization
to implement the guarded diagnostic seams. Follow README.md for current commands,
guards, tests, native gates and cleanup requirements. No native allocation result
is claimed until the native capture/replay run actually completes.
