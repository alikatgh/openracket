# Independent native-appearance candidate audit

2026-10-10. This candidate is separate from the frozen baseline. No local display
operation was attempted. Native controller/FFI integration is not yet certified by
this audit; the native workflow has only source and reader validation here.

## Findings addressed before native acceptance

- Explicit native Restore originally logged a failed restoration but returned
  normally, allowing the preference state to be marked restored while the native
  checkpoint remained active. Strict explicit restoration now raises and preserves
  the checkpoint for retry before bookkeeping can claim success.
- After following the original platform appearance, a failed explicit mutation
  plus failed rollback originally reported inactive state. Any uncertain rollback
  now exposes active state for recovery.
- Framework Preferences Undo Changes and Escape restore full preference snapshots.
  Native state originally remained deactivated after cancelling Restore, or active
  after cancelling Apply. The bridge now reconciles external committed appearance
  state changes; internal transaction generations prevent stale queued callbacks
  from undoing a later explicit Restore.
- A requested-mode cache alone could miss external native appearance changes.
  Same-mode suppression now requires the adapter's read-only live verifier.
- Platform-following must not pin a resolved light/dark mode. It restores the exact
  first app appearance while retaining its checkpoint; final Restore releases it.

## Independently executed headless evidence

48 tests pass across these four suites:

- `independent-appearance-test.rkt`: 22 transaction/rollback cases.
- `independent-theme-bridge-test.rkt`: 9 before-commit callback/paint synchronization cases.
- `independent-appearance-controller-test.rkt`: 6 ownership and recovery cases.
- `independent-appearance-integration-test.rkt`: 11 cases executing the actual tool
  integration functions with the real pure controller and modeled Framework
  before-commit callbacks. They include both full-snapshot cancellation directions,
  platform/explicit transitions, failed reapply preserving the original baseline,
  failed Restore plus Undo, rapid external writes, and stale/new callback generations.

Cocoa source retains the exact explicit appearance, including nil/inheritance,
verifies pointer identity after restoration, and releases saved ownership once.
Main-thread checks agree with the stock Cocoa GUI initialization requirement.
High-contrast or unknown appearance is conservatively refused for new changes;
restoration remains available. GTK stays experimental and outside tool activation:
restoring values alone does not restore app-versus-desktop property inheritance.

## Native acceptance prepared

`tests/independent-native-appearance-workflows.rkt` uses actual DrRacket frames and
Framework Preferences controls, not reflected private tool functions. It verifies:

- Explicit light/dark and exact pre-startup native baseline restoration.
- Two genuine frames sharing app appearance; closing one preserves the other.
- Platform-following without a pinned app override.
- Real Apply, Restore, Undo Changes and Escape callback routes.
- Queued callbacks and a new frame cannot reactivate committed restored state.
- Exact original control-font identity/metrics and supplied larger fonts rendered
  on real canvas DCs. This does not claim to test OS accessibility font scaling.

The genuine-host caller is gated by `OPENRACKET_NATIVE_APPEARANCE_CHECK=1`, with
native appearance opt-in, modern theme enabled, explicit dark startup, and its own
fresh Cocoa process. It retains bounded READY/capture and failure diagnostics.
The adapter owner's standalone native smoke test remains a separate lower-level
check. No native pass or full functional-parity claim follows from these files.
