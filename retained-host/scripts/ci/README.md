# Native validation on free standard public runners

The repository's `retained-native.yml` workflow runs only on pushes that change
this retained-host prototype or its workflow on `prototype/retained-drracket`.
It never runs on `main`, arbitrary branches, pull requests, forks, or a private
repository. Job-level owner, branch, visibility and event guards are evaluated
before runner allocation; a live public-repository check is also
made before checkout using the official GitHub client and the job’s existing read-only authentication. No custom credentials are created or saved.

Only `ubuntu-24.04` and `macos-15` standard hosted runners are selected. GitHub
states that standard hosted runners are free and unlimited for public repos;
larger runners are not free. This workflow never uses larger runners. Correctness phases are separate, fail-fast workflow steps. Runtime
is bounded by a 30-minute job timeout, subprocess timeouts and one concurrency
group. There is no schedule, recursion, workflow dispatch, paid service or AI API.

Source is checked out at the exact event SHA with the official GitHub action
pinned to its reviewed v6.1.0 commit. Checkout credentials are not persisted and
the generated job token has only contents-read permissions. No repository or
user secrets are requested. No cache, Actions artifact, package, or release is
uploaded; logs and job summaries do not count toward GitHub artifact storage.

## Genuine native checks

1. Install the full official Racket 9.3 CS distribution into runner temporary
   storage, verified against the official release page's SHA-256. This includes
   DrRacket and its normal GUI, rich editor, evaluator and bundled tools.
2. Run source-preservation, patch-integrity, renderer and theme tests.
3. Observe the previous launch-argument failure once, without clicking or dismissing a dialog, and record actual native window labels and editor contents. Then run actual stock `switchable-button%` behavior tests and genuine DrRacket
   frame/editor startup checks before modifying the disposable distribution.
4. Keep the pristine runtime untouched and create a distinct local copy (no hardlinks) for the overlay. Verify actual mrlib, framework and drracket paths resolve inside their respective copies and verify pristine source hashes before/after. Apply the exact-SHA presentation overlay only to the modern copy;
   register and compile the retained appearance tool with existing dependencies.
5. Repeat native widget/host checks with the stock-painter fallback and modern
   light/dark appearances, using fresh preference directories.
6. In fresh processes and preferences, first pristine stock and then modern dark,
   run strict Stop-state, Unicode input/EOF, WXME rich-document and actual Check
   Syntax preservation tests. Each case has a 60-second outer bound and failure
   diagnostics. Independent cases continue in fresh processes after a failure;
   only matching successful stock baselines allow the modern comparison. A
   failed or skipped comparison remains explicit and the overall job fails.
7. On Cocoa only, opt modern light/dark host processes into app-local native
   appearance. Pristine stock, stock fallback and Linux remain unopted. Run the
   adapter lifecycle test and a separate real two-frame DrRacket/Preferences
   Apply/Restore/Undo test. Its final screenshot is explicitly labeled restored.
   These checks do not change the operating system's appearance preference.
8. After successful core gates, run two bounded 30-second metadata-only probes
   with identical 100k synthetic fixtures and separate fresh preferences/addon
   registries. Compare complete pending-next-Run language settings and fixture
   reader defaults through documented APIs. This is not a measurement of live
   evaluator instrumentation. Failures remain explicit and fail the job.
9. Independently of the appearance gate, run four fresh pristine-stock break
   controls after a successful stock core gate. Each has a 35-second outer
   process bound and the original 20-second break-completion requirement.
   These isolate ordinary threads, GUI import, eventspace handlers and nested
   versus returning callbacks. They never inject a break into DrRacket, replace
   its original strict Stop case, or change its evaluator. See
   `STOCK-BREAK-CONTROL.md` for exact interpretation limits.

This appearance follow-up retains the previous ordinary paired performance
baseline and single instrumented Linux attribution trial without repeating
either workload. Command/event-loop timing is not input-to-photon timing, and
CI runner numbers are not representative hardware benchmarks. Independent
appearance and metadata checks can run after a preservation failure; that
failure still remains in the report and fails the overall job. No diagnostic
data can turn an unverified workflow into an acceptance pass.

Linux uses official Ubuntu Xvfb and Noto CJK font packages on the GitHub runner,
with equal font coverage for pristine and retained modes. macOS uses
its native window system. No local/cloud display restriction is bypassed. A
real GUI failure is a failed test and must be diagnosed; functionality is not
removed to make the tests pass.

When the OS can capture the synthetic test window, bounded lossless PNG data
(up to 300 KiB per image) is written between explicitly indexed job-log markers.
The receiver verifies all chunks, byte count and SHA-256 before decoding. These
are OS screenshots, never component drawings. Failures can produce separately
labeled failure/timeout diagnostic screenshots; those never count as passing
visual validation. If capture is denied/unavailable,
that limitation is reported without changing OS privacy settings. Successful
behavioral checks alone do not imply visual review or full feature parity.

Full parity remains a separate acceptance matrix: evaluator/run/stop details,
teaching languages, debugger, macro stepper, stepper, image/snip persistence,
menus/dialogs/shortcuts, focus/accessibility, and real-workload latency still
need their own evidence. See the prototype's acceptance and parity reports.

## Official sources checked 2026-10-10

- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://download.racket-lang.org/releases/9.3/
- https://github.com/actions/checkout/releases/tag/v6.1.0

The Racket distributions are downloaded from the official release site, not
redistributed as repository files. Original upstream license notices included
with the presentation overlay are retained.
