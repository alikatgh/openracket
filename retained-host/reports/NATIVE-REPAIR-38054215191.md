# Eighth native run and bounded repair

Source commit: `cae83d84ff54cc262a6dbea78519f95b7a88cfee`.
Run: https://github.com/alikatgh/openracket/actions/runs/38054215191

Both platforms compiled the actual retained DrRacket host and appearance tool.
Pristine, stock-fallback, modern-light and modern-dark real-host checks passed.
Both platforms passed actual input/EOF, rich WXME, and Check Syntax comparisons.
The four isolated stock break-delivery controls passed on each platform.
Paired public-API pending Run configuration records matched on both platforms;
these observations do not establish the configuration of an already-live evaluator.

The original strict Stop case passed in both Mac arms, but failed in the Linux
pristine arm; its matching modern arm was skipped and remained a failed gate.
This follows earlier pristine Stop failures on Mac and successes on Linux. The
intermittent completion problem remains unresolved; no parity claim follows.

## Cocoa capability defect

The native appearance adapter remained in safe fallback: `id->C: argument is not
'id' pointer; argument: #<cpointer>`. The dedicated lifecycle process failed its
capability check before creating a DrRacket frame. Normal modern screenshots
therefore establish editor/toolbar rendering, not coherent native chrome.

Two `respondsToSelector:` calls supplied a selector pointer through `tell`'s
default object conversion. This candidate adds explicit `#:type _SEL` at both
argument sites, matching the exact Racket 9.3 Cocoa backend convention. No cast,
capability relaxation, fallback removal, or lifecycle assertion was introduced.
Headless compilation cannot establish native correctness; the repair needs the
same actual Cocoa capability and real Preferences/multiple-window lifecycle test.

## Separate Stop discriminator

The added `stop-returning` host case retains the current diagnostic Stop fixture,
real Run and Stop callbacks, twenty-second completion bound, and failure capture.
Each action now returns before the coordinator polls state. GUI operations stay
on the same handler thread. This case is separate; the original `stop` case and
its assertions are unchanged. Thread/custodian/widget identities are recorded
before, after, and at timeout. Post-completion evaluator reuse is observational.

No performance experiment is included. There is no new speed measurement.
See `ci-eighth-run.json` for exact stage outcomes and native log hashes.
