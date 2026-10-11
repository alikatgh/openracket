# Run47 evidence and test-only activation repair

Prepared 2026-10-11. Review candidate copied from the immutable 1335 Quit gate.
No product, accepted builder, CI workflow, or original freeze was edited.
This repair has not been compiled or run natively and is not a clean-Quit pass.

## Prior native evidence

Run https://github.com/alikatgh/openracket/actions/runs/38151672381 produced
98 aggregate checks, 94 passing. The six-case matrix did not pass: stock clean
reached initial READY, then timed out at quit-dialog/quit-confirm-1 after its
one original application Quit request. Its failure evidence shows the original
frame still shown and no shown modal. Modern clean was correctly left unrun.

Stock and modern-dark Save and Don't Save each passed their full original
Quit/Cancel/repeated-Quit/modal/response/natural-exit/disk acceptance. All four
acceptances record natural exit 0 and cleanup_used=false. Both original and
selected runtime full bytes/modes/mtime/symlink witnesses and original preferences
were unchanged; the .rkt default handler remained null, rather than acquiring a
handler. These four passes do not substitute for either clean case.

Exact recovered macos.log SHA256:
456c14b20654305404a569c5675f57694b6621b9fa5fca311a4e551c94f8996f

Evidence: openracket-recovery/results/run-38151672381, especially summary.json,
decoded/quit-stock-clean-failure-summary.json, the four acceptance/transcript
summaries, and images/. Reviewed clean READY shows active-looking native chrome;
that screenshot does not establish that the Racket activation state had been
updated before the Quit invocation. Reviewed positive unsaved screenshots show
the actual Save/Cancel/Don't Save controls. Original READY/request evidence did
not record actual focus/activation, so the historical cause remains unresolved.

## Independently checked source mechanism

Pinned official GUI commit 6f0213fa0535d87dd4e35f56c8266d948c8c089e:

- mred/private/mrtop.rkt:302-308 requires is-act-on? to return a focus window.
  Its edit-target function at 310-324 can select the first real frame even when
  every activation timestamp is still 0. Edit target alone is insufficient.
- mred/private/wxtop.rkt:620-622 initializes activation dates to 0 and active
  state false. Actual on-activate(true), 647-659, sets the active state and the
  main-eventspace, non-root, non-floating active-main-frame before returning.
- mred/private/app.rkt:33-53 does no default Quit dispatch without that active
  frame. Its public zero-argument getter, 96-106, returns the existing handler.
- Pinned DrRacket main.rkt:65-71 delegates to the existing toolkit handler when
  an application window exists.

This proves a missing readiness precondition in the old test source, not that
this race caused the old native failure. The new witness reads public focus;
it does not directly read or modify private active-main-frame, install an
on-activate handler, or manufacture an activation event.

The existing eleven runtime source pins are preserved; mrtop.rkt is the twelfth.
Its exact bytes and Git blob were independently recomputed against the inherited
OFFICIAL-SOURCE-PINS.json record:
SHA256 677b5a75926581973a8eb28b34a9ef46003150241460f5655245940fb9bf7e51
Git blob bcfd0f2842d39727bc7ebe4df0a54a8072b16ee3

## Repair and evidence contract

The initial timer now observes actual focus and current edit-target identities,
then publishes READY only if both are the original frame and active_focus is
true. It uses the original 60-second startup deadline and existing one-time
startup focus request. No sleep or arbitrary delay was added.

Every original application Quit call independently observes and asserts the same
actual-focus precondition in its existing GUI callback. The observations are
logged and flushed as OPENRACKET_QUIT_REQUEST with status pre-dispatch before the
unchanged single zero-argument handler invocation. This record proves the
pre-dispatch observation, not callback completion. The same request witness is
bound to its real modal reports; failure reports retain the latest activation
observation and pre-dispatch request, including when no modal appears.

The independent validator rejects missing/malformed activation objects, inactive
focus, absent or different focus/edit-target identities, booleans or floats used
as IDs, string flags, and extra keys. Both the initial READY and every Quit and
unsaved modal must carry the required original-frame witness. Source-order tests
require observation/guard before READY or dispatch, and preserve the original
single dispatch site and case-specific calls.

Unchanged: 20-second stage/ACK bounds, 150-second process bound, all stock modal
checks, exact callback responses, Cancel's natural focus return and stable live
interval, natural exit acceptance, disk bytes, independent supervisor, and all
failure-only cleanup semantics. No request retries, reissued Quit, dialog
relaxation, handler replacement, or forced post-Cancel focus was introduced.

## Verification and remaining gate

41 local Python/source tests pass: 22 protocol tests (including parameterized
activation refusal controls), 14 source/lexical tests, and 5 stock-bundle fixture
tests. Python AST and Racket lexical balance checks are not Racket compilation.
No Racket/native execution, installation, archive retrieval, publication, or CI
trigger was performed by this repair task. The unchanged eight RackUnit cases
and complete six-case native matrix remain for the authorized free CI owner.

The parent and performance owner independently approved the concrete source diff
on 2026-10-11; the parent independently reran all 41 portable checks successfully.
The source-only review diff is preserved in the full session backup. The
FROZEN-NATIVE-ALLOWLIST.json is regenerated for this exact repaired tree; it is
not the inherited baseline manifest. Full source/evidence backup and inventory
are recorded separately. Native compilation and the clean-Quit gate remain
pending; no further source edits were requested or made after source review.
