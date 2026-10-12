# Actual autosave guard experiment: run 38061486888

Status: macOS and Linux complete. All 12 trials are valid. macOS is the user's
priority; the result is a verified localized autosave improvement, while the
larger initial-coloring/GC responsiveness goal remains unmet.

## Result

On macOS, actual synchronous 1 MiB autosave command medians fell from
266.735 to 172.400 ms (35.4%). All three matched replacement-save pairs improved,
by 19.1–42.8%; the directly prequeued GUI callback delay fell from a median
268.036 to 173.187 ms. All six macOS trials passed exact source, recovery
artifact/table, activation, settings and lexer-validity checks.

Linux's two matched first-save pairs reduced the same call by 24.7% and 32.6%.
Its third pair is retained but confounded: stock replaced an existing recovery
file while candidate made its first one. Three observations per arm are not
statistical significance. This experiment does not establish improved initial
coloring, expansion completion, physical input-to-photon latency or elimination
of major GC pauses.

## Reproducible scope

- [Native CI run](https://github.com/alikatgh/openracket/actions/runs/38061486888),
  commit `edcaa78c2cb0a5922f0ff0f946c065d8f952cf5c`.
- Official full Racket 9.3 CS, pristine stock and independently copied runtime;
  three fresh interleaved pairs: stock/candidate, candidate/stock,
  stock/candidate. Linux uses the standard Ubuntu runner and Xvfb; macOS uses the standard
  macos-15 ARM64 runner and its native GUI. Compare within each OS only.
- Only the two guarded redundant format-classification traversals change.
  The required `do-autosave` classification, native copy serialization/write,
  save hooks, recovery table and previous-artifact cleanup remain in the call.
- Pinned candidate `framework/private/text-misc.rkt` SHA-256:
  `00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d`;
  stock `7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638`.
- Timing harness SHA-256:
  `a7a0a7636660284ad6a85342c2b9e1fe41d46f4dd355e4434f7f17591773a015`.
  Performance freeze manifest:
  `a35241e4c454c6eddd03b85456ebabb9b234b7ab5785057427315fe452512301`.
- Scan shortcut, experimental color budget and appearance changes are absent.
  Native stock/off/on save, Unicode, rich-snip/WXME, hook and recovery gates run
  before timing. This does not prove arbitrary third-party virtual-method
  callback counts unchanged: the candidate's documented extension boundary is
  still relevant to integration.

The fixture is the same mixed ASCII Racket source of 1,048,576 characters,
SHA-256 `766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e`.
The actual definitions editor opens it, makes a real single-character comment
edit, and reaches lexer validity. On the same GUI callback immediately before
the timed method, both arms call `set-modified #t` to mark any prior autosave out
of date. This explicit benchmark precondition does not change normal autosave
cadence. A prequeued callback measures GUI blocking across the dirty precondition,
actual save and small local memory snapshots. It is separate from the subsequent
low-priority fence.

## macOS paired observations

All three pairs started with one existing fixture artifact and one matching
recovery-table entry. These are genuine replacement autosaves, with the same
prior-state counts in both arms. Every result is complete and valid.

| Pair | Actual command stock / candidate (ms) | Candidate change | Queued GUI probe stock / candidate (ms) | Command + fence stock / candidate (ms) |
|---|---:|---:|---:|---:|
| 1 | 228.559 / 172.400 | −24.6% | 229.329 / 173.187 | 231.530 / 172.559 |
| 2 | 284.354 / 162.689 | −42.8% | 285.878 / 163.603 | 287.919 / 167.468 |
| 3 | 266.735 / 215.792 | −19.1% | 268.036 / 217.305 | 315.762 / 216.569 |

The 35.4% median-to-median command reduction is descriptive, not the same
statistic as the median paired reduction (24.6%). Both describe these three
pairs only. The operation still blocks the GUI for roughly 163–216 ms in the
candidate; it has not become imperceptible.

Command-only allocation was 23.116 / 22.767 MB, 23.202 / 22.736 MB, and
23.360 / 22.846 MB by pair (decimal MB, stock / candidate), reductions of
1.5–2.2%. Command GC CPU was 1 / 1, 1 / 1 and 22 / 3 ms. Most of the elapsed
savings in the first two pairs occurred without a measured GC CPU difference.
The third pair includes a GC difference; these runtime-wide counters do not
identify allocation ownership or justify a general GC improvement claim.

Whole-process peak RSS medians were 1,253,277,696 / 1,256,554,496 bytes, essentially
unchanged. Stock pair 3 reached 1,496,743,936 bytes, but this peak includes the
whole process, not only autosave. No retained-memory saving is established.

All six native reloads recovered exactly the original fixture plus one comment
character, and verified unchanged original bytes, filename/format restoration,
new artifact path and exact recovery-table entry. All gates passed without
extending the 45-second lexer gate or 60-second process bound. Initial lexer
waits still lasted 34.373–39.619 seconds. Large-file readiness therefore remains
a substantially larger problem than the reduced autosave stall.

The benchmark requested a 1200×820 window on the standard 1024×768 native runner
desktop. These are event-loop measurements, not full-viewport presentation or
physical input-to-photon measurements. No Linux-versus-Mac speed comparison is
made.

## Linux paired observations

All values below are milliseconds. Prior state is recorded before the call.

| Pair | Prior save state stock / candidate | Actual command stock / candidate | Candidate change | Queued GUI probe stock / candidate | Command + fence stock / candidate |
|---|---|---:|---:|---:|---:|
| 1 | first / first | 255.241 / 192.110 | −24.7% | 255.638 / 192.522 | 256.748 / 194.238 |
| 2 | replacement / first | 254.527 / 160.851 | −36.8%, confounded | 254.883 / 161.271 | 284.008 / 160.952 |
| 3 | first / first | 242.747 / 163.696 | −32.6% | 243.087 / 164.049 | 242.801 / 165.220 |

Descriptive all-trial arm medians are 254.527 → 163.696 ms for the command and
254.883 → 164.049 ms for the queued probe. These medians include pair 2's unlike
prior state and should not replace the two matched-pair observations above.

Stock pair 2 had one existing fixture artifact and one original-to-artifact
recovery-table entry; all other trials had zero. Every timed call produced a
new path in the enumerated fixture directory. Each actual native reload recovered
exactly 1,048,577 characters, the full fixture plus the intended edit; original
file bytes, editor filename and format were preserved. Every new recovery-table
entry matched the original and returned artifact paths exactly.

### Allocation, GC and heartbeat limits

Command-only cumulative allocations were 22.431 / 22.214 MB in pair 1,
22.417 / 22.292 MB in pair 2 and 22.419 / 22.214 MB in pair 3
(decimal MB, stock / candidate). Thus the measured reduction is mainly elapsed
command work rather than a large allocation reduction. Command GC CPU was
2 / 5, 1 / 1 and 1 / 2 ms respectively. Runtime counters include any concurrent
background activity, so these are not allocation-ownership measurements.

Whole-process peak RSS medians were 1,159,733,248 / 1,160,105,984 bytes, essentially
unchanged. Stock pair 2 reached 1,510,019,072 bytes over its lifetime. This peak
includes startup, coloring, background activity and verification, not solely
the timed save. Managed-memory deltas cross collection boundaries and cannot
be interpreted as retained-memory savings.

The direct queued probe is the reliable operation-specific GUI observation.
Periodic heartbeat labels alone do not confine a sample to the measured call:
candidate pair 1 has a phase-labelled 611.899 ms gap whose callback occurred at
30,312.274 ms, after the timed command/fence ended at 29,701.503 ms, while recovery
verification still used that phase label. It must not be called a 612 ms
autosave-command stall or hidden as a nonexistent post-save pause. The raw
heartbeat records remain available.

Initial lexer waits still ranged from 20.769 to 30.753 seconds in this Linux
batch. The autosave improvement does not resolve that larger readiness problem.
Online-expansion terminal state remains unobserved by this timing harness.

## Equal configuration and validation

All six trials within each OS report the same complete pending-next-Run language
configuration: raw annotations `lang-default`, source reader default/effective
annotations `debug`, and no metadata errors. This is not a measurement of the
live evaluator or background worker's effective instrumentation.

Both arms retain online compilation and coloring enabled, a 134,217,728-byte
child limit, autosaving enabled with a 30-second delay, backup files enabled,
and the stock `verify-change-format` default false. Actual loaded autosave
activation is verified in every process, with the stock extra export absent and
candidate export true. Scan activation is verified absent. Both initial and
final lexer gates complete; all trials exit zero without an outer timeout.

Raw evidence is in `openracket-native-ci/results/run-38061486888/`, with
`macos.log`, `macos-performance-records.json`, `linux.log` and
`linux-performance-records.json`. The strict offline analyzer is
`performance/analyze_autosave_pair.py`; its synthetic acceptance tests cover
missing recovery checks, unequal settings, wrong activation, incomplete trials
and first/replacement state differences. The analyzer reports
`valid_end_to_end_pairs` on both OSes, with the explicit Linux pair 2 confound.
