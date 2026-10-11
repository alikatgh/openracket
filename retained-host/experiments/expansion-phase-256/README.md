# Completed-request phase diagnostic at 256 MiB

Separate diagnostic revision of phase replay manifest
`d7187ac4708dde9ae5de9c09ce5e369aacd1fcfd9257a16c6c827a94a7362ace`.
This is an instrumented stock Racket 9.3 copy with one explicitly varied public
preference. It is neither a production change nor a speed optimization. No runtime
installation, network write or local GUI execution is part of this package.

## Exact native commands and ownership

The CI worker supplies a new independent deep clone of pristine full Racket 9.3,
its physical executable path RACKET, the pristine resolved DrRacket private source
path PRISTINE_DRRACKET_PRIVATE, the existing deterministic mixed-1MiB FIXTURE, and
new external TEST_PROFILE/CAPTURE/RESULTS paths. PROBE is this manifest-verified
package. Capture and results must not already exist. Copy only ALLOWLIST.txt entries;
verify SHA256SUMS before execution. Never copy compiled/ or __pycache__/ caches.

    python3 "$PROBE/native_preflight.py" --racket "$RACKET" --pristine-source "$PRISTINE_DRRACKET_PRIVATE" --profile "$TEST_PROFILE"
    python3 "$PROBE/prepare_phase.py" --diagnostic-root "$DIAGNOSTIC_ROOT" --racket "$RACKET"
    python3 "$PROBE/capture.py" --racket "$RACKET" --fixture "$FIXTURE" --output "$CAPTURE"
    python3 "$PROBE/supervise.py" --racket "$RACKET" --capture "$CAPTURE/capture.rktd" --output "$RESULTS" --trials 2 --phase-probe
    python3 "$PROBE/accept_completed.py" --capture "$CAPTURE" --results "$RESULTS"

Run preflight before patching the pristine source. Its Racket gates must execute:
any skip fails. It includes actual-thread/lifetime, absent-module, bad-private-binding,
source-reader, disabled-hook, real-place success/failure/timeout/cleanup, capability
retention, monitor-schema and public-preference-helper tests. The RackUnit fixtures
run with raco test so failed checks return a failing exit status. Preparation checks
all pins before edits, then explicitly compiles all three patched modules plus
phase-probe.rkt, support.rkt, replay.rkt, capture-host.rkt and memory-profile.rkt.
Skip-compile is only for an explicitly separate bounded compilation, never a bypass.

Run the final acceptance command even after a capture/replay failure if output
exists, preserving the failing records. A successful supervisor means protocol and
cleanup completed; it does not by itself mean this diagnostic was accepted.

## Fresh profile setup, exactly once

capture.py creates an empty CAPTURE/profile and supplies a separate CAPTURE/addon
path. The byte-identical previously native-verified memory-profile.rkt and
profile_setup.py create/check the empty addon, then use the original pinned public
preference registration/API to set only drracket:child-only-memory-limit to
268435456. Setup verifies the original 128 MiB default, exactly one persisted key,
public readback, forced disk readback, store hash, absence of legacy/runtime fallback
stores, and no GUI initialization. It has its existing separate 30-second bound.

Only after successful verification does capture.py write its disposable-profile
marker and launch GUI using the exact same home/addon. Setup failure never starts
GUI. There is no second initialization or profile recreation. Actual GUI preferences,
actual request cap, captured settings/registry and replay's actual ready cap all
must show 256 MiB. Replay restores the exact captured launch environment and, if
necessary, only the marked disposable preference file to its captured bytes. It
does not rerun the helper or set preferences itself.

Helper SHA256: 9b761799e61b45388ae21461d358a819274ae1923e88959351a9f9b46337abc0
Wrapper SHA256: 9bb3dc30255a4effca1a91f2f407e0af3ae0fce298f2fc20ed823544176daddb

## Source seams and actual xref service

The original three guarded source transformations are unchanged from the prior
phase probe. Removing marked phase insertions and original readiness seam
reconstructs the original worker/monitor bytes exactly. Capture still records the
actual GUI request, settings and evaluated handler registry without synthesizing
jobs. No stock logger level or subscription is changed.

Original source pins:
- expanding-place.rkt: f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383
- module-language.rkt: e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53
- syncheck/online-comp.rkt: 1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5
- xref.rkt: acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7
- traversals.rkt: bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00

The last two are independently resolved, confined to the clone, pinned and never
edited. Their exact path/hash pairs join the capture/runtime identity check.

At the existing readiness seam, after actual registry imports, the helper resolves
and pins xref's source, then uses module->namespace and namespace-variable-value to
read its existing private thd. It immediately creates a weak box and discards the
namespace/strong-thread locals. It never instantiates xref, exports or changes its
binding, performs a lookup, starts another service, or changes its custodian. Missing
instance/binding, wrong type, dead thread or pin failure produces bounded unavailable
attribution while the stock request continues. Final acceptance then fails visibly.

The original working/monitor lambda-entry registrations remain. At every trial
begin, the same weak service reference joins newly generation-tagged per-trial refs.
Job refs clear at end/begin; the weak service reference also clears at stop. The
service survives jobs, so its samples are observations during an active request,
not proof it executes that request or owns any allocations. Approximate nonempty
monitor and service frames are required for accepted coarse thread context.

## Completion and lifetime acceptance

accept_completed.py requires:
- Verified one-key setup, actual 256 MiB GUI/captured/ready limits, and actual
  worker custodian-memory-accounting availability before any job
- One actual CheckSyntax monitor registry entry and nonempty clean trace schema in
  capture and both replays, including real channel-bearing rename rows for this
  fixed binding/reference-rich fixture, with zero error strings or unknown payloads;
  trace-entry and channel-bearing-row scalar counts must also match capture
- Actual handler-results in capture and both replays, matching existing terminal
  summary fields, source snapshot hash and registry hash
- All worker phase 09–13 and monitor build/return/ack points with finite nonnegative
  producer timestamps in order, correct generation/trial, zero drops/stale events,
  and usable actual monitor/service thread context
- Prior terminal/real place channels retained through replacement, last terminal/
  real place channels through cleanup, and
  accepted worker/control/custodian/process-group cleanup

The extra monitor schema/channel walks are diagnostic overhead in capture and
replay, so do not compare their timings against earlier uncounted capture as a
speed estimate. Monitor bookkeeping retains only counters and up to four 240-character error texts.
It never serializes or retains a new copy of live trace/capability payloads. Existing
rename endpoints/results remain inside the replay process, retained through the
unchanged replacement/cleanup fence with void/reference-sink. Terminal-summary
matching and monitor-schema checks do not establish full trace, handler payload or
capability equivalence. finished-expansion alone, an OOM, empty/error trace, missing
phase, missing service or failed cleanup always fails completed-request acceptance.

## Unchanged bounds and interpretation

Capture retains its 190-second outer process bound,90-second frame/terminal gates
and 5-second external cleanup. Replay remains 30-second initialization,60 seconds per
terminal,2-second cleanup and 157-second total for two trials. Source compilation
remains 240 seconds. No timeout increase is introduced to obtain success.

The observer queue is 128 entries; points cap 128, samples cap 256, period 250 ms,
frames cap 8 per thread, text fields cap 240. There are now THREE sampled roles:
working-thread, check-syntax-monitor and xref-service. The collector remains under
the original worker custodian, outside the explicitly varied job cap. It retains
immediately rendered source frames, never continuation marks. Transient capture/
conversion cost and scheduler delay are not hard-bounded by retained frame caps.

CI transport must test worst-case Unicode at 256 samples ×3 roles ×8 frames with
240-character name/source text fields, including JSON overhead. Preserve every
sample/frame/point and verify byte-count/digest parity after transport; do not
silently truncate or retain only a tail. The new maximum is larger than the prior
two-role fixture.

Counter deltas cover the isolated process interval, including handlers, compiler
manager, sink and instrumentation. Service/monitor wall-clock stack observations
cannot assign CPU/allocation ownership or establish a speedup. Do not sum place GC
counters or infer absence of GC from missing log events. Existing GC receivers and
supervise.py are byte-identical to the baseline.

## Local evidence

portable-tests-256.log and validation-256.json describe current portable coverage.
No Racket executable is available here. Local Python/source/process-supervisor
checks pass, while 13 Racket gates explicitly skip. This is not native acceptance;
the native CI worker owns the required preflight, GUI capture, two replays,
acceptance evaluation and publication. Historical files left in the source
folder are excluded from ALLOWLIST.txt and are not validation of this revision.
