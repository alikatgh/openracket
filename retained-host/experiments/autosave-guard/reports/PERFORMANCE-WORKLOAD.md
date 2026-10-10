# Actual settled-editor autosave measurements

Prepared for isolated stock versus save-scan-guard native trials. Nothing here
installs a runtime or launches a display. Local checks are headless only; native
results are pending.

## Workload

The generator pins the ordinary scan harness and preserves its real DrRacket
launch, zero GUI command-line arguments, file-open route, original definitions
editor, tools and preferences. It replaces the warm typing/jump phase with one
actual public `do-autosave` call after the real first comment edit and initial
lexer validity. Initial readiness remains bounded to 45 seconds; every process
has the unchanged 60-second outer supervisor bound and real child cleanup.

The stock autosave timer can fire during that lexer wait. The harness therefore
calls the documented `set-modified #t` immediately before the timed method, on
the same GUI callback with no intervening GUI yield. Stock editor-misc.rkt
704–709 marks an existing autosave out-of-date on this setter. This explicit,
identical dirty-document precondition ensures a real write rather than an
already-saved fast return. Normal timer cadence and preferences remain enabled.

The measured call retains the required format-selection scan, both original
save hooks, `save-file 'copy`, actual serialization/write, original format
restoration and previous-artifact cleanup. It uses no observer mixin or fake
save implementation. The modified candidate's extension callback-count boundary
is documented by its separate source/correctness owner, not erased by this test.

Record command duration separately from the subsequent low-priority GUI fence.
A one-shot high-priority callback queued before the operation measures its GUI
blocking even if a periodic heartbeat would miss a short save; it includes the
small dirty-precondition overhead. Periodic heartbeat samples, GC CPU and
cumulative allocation snapshots, and native peak RSS remain present. Local
snapshots bracket the actual command separately from its later fence; neither
interval includes JSON persistence. The post-command snapshot itself adds a
small common overhead before the fence, outside the command duration. These are
event-loop observations, not physical input-to-photon. Counters include other
runtime activity, and lexer readiness does not prove expansion completion.

After timing, require an actual returned artifact, unchanged original file
bytes, unchanged editor filename and restored file format, a still-modified
document, and the exact original fixture plus the one intended comment edit.
Reload the artifact using a fresh actual native text% and compare its full
source. Snapshot the fixture directory before the same-callback operation and
require that the returned artifact path was absent, so an old valid recovery
file cannot make a no-op look successful. This fresh-editor verification is
outside the timing/memory interval.
Also preserve the actual prior TOC entries, total/fixture entry counts and
existing fixture-artifact count, and verify the new original→artifact TOC entry.
Initial coloring may span the normal 30-second autosave tick. A first save and
a replacement save have different cleanup/TOC work; do not present unlike pairs
as a pure scan-cost comparison. This first workload is end-to-end settled-editor
autosave with the real timer still active.
The normal end-of-test modified-state cleanup may remove the recovery artifact;
the report records verification while it existed, not an artifact upload.
Rich image/nested-editor/WXME and Unicode preservation are separately gated by
the genuine-host correctness suite before timing; this timing fixture is ASCII.

## Caller contract

Use fresh stock and independent candidate official 9.3 copies, same native
runner/display and appearance, scan absent, stock 20 ms color budget, default
tools and preferences. Candidate source hashes are verified independently.

```
python3 performance/run.py --mode autosave-stock --racket STOCK_RACKET \
  --output reports/autosave-ci/performance-stock/pair-1 --fixture mixed-1mib \
  --repetitions 1 --timeout 60 --scan-activation stock --autosave-activation stock

OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1 \
python3 performance/run.py --mode autosave-candidate --racket CANDIDATE_RACKET \
  --output reports/autosave-ci/performance-candidate/pair-1 --fixture mixed-1mib \
  --repetitions 1 --timeout 60 --scan-activation stock --autosave-activation candidate
```

All other experiment/appearance flags are unset. The read-only activation check
requires stock's extra export absent or candidate's loaded export exactly #t.
Use three interleaved pairs: stock/candidate, candidate/stock, stock/candidate.
Keep each full trial and summary between the existing performance JSON markers.

Valid comparisons require all six trials complete with zero exit/no timeout,
measurement_kind `settled_editor_autosave`, initial and final lexer complete,
verified scan-off and save-guard activation, equal complete language settings and
preferences, all `autosave_recovery` booleans true, artifact size positive and
recovered character count exactly fixture size plus one. Also require original
preconditions lexer-valid/dirty/autosave-enabled, `new_artifact_path_verified`,
`recovery_toc_entry_verified`, recorded prior artifact/TOC state,
and a numeric one-shot GUI probe.
In particular, compare the unchanged autosaving-on, 30-second autosave-delay,
backup-files and verify-change-format preferences; never set them to gain speed.

Do not call three observations statistical significance or general disk
throughput. Do not split scan versus extraction/write cost from this total-call
measurement without a separately labelled instrumented diagnostic.

## Headless checks

```
python3 scripts/prepare-performance.py PATH/ordinary-performance
python3 -m unittest discover -s performance -p test_harness.py
python3 -m unittest discover -s tests -p test_workload.py
raco test tests/activation-test.rkt
raco make performance/retained-host.rkt
```
