# Activation repair source status

2026-10-11. See RUN47-ACTIVATION-REPAIR.md for exact prior native evidence,
source mechanism, scope, and unresolved historical-cause caveat.

This new test-only candidate passes 41 local Python/source tests: 22 protocol,
14 source/lexical, and 5 stock-bundle fixture tests. The original 8-case Racket
contract module remains unchanged and was not run locally. Current logs are
contract-tests.log, source-tests.log, stock-bundle-tests.log, and all-tests.log.

The current candidate has not been compiled or run natively. Run47 tested the
old baseline, with four Save/Don't Save workflow passes, one stock-clean failure,
and modern clean unrun. It is not evidence that this repair passes clean Quit.
No product source, CI, original freeze, installed runtime, or user profile was
changed. No publication or CI trigger was performed by this task.

Parent and performance owner source review approved on 2026-10-11. The parent
independently reran all 41 portable checks successfully. The exact reviewed
five-file source diff is unchanged. A new full-byte/hash snapshot and session
backup were prepared after both acknowledgments; native clean Quit is pending.
