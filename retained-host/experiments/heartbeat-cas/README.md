# Standalone heartbeat CAS contract repair

This is a diagnostic helper repair, not a product optimization. Native run38121983444 pair1 candidate remains failed. A false one-shot box-cas! result was treated as duplicate despite the documented possibility of spurious failure with unchanged box. The revised private claim helper retries while the box remains false and rejects actual prior ownership. Both callback and queue-error paths use it. Original heartbeat pacing, single outstanding callback, counters, stop/join and deadlines remain unchanged.

Four deterministic native regressions inject spurious failures through actual callback and queue-error paths, retain true-duplicate rejection, and check callback-then-queue-error acknowledgment ownership. The fault seam is exposed only through a test-support submodule; normal users/environment cannot activate it. The recorded native once-box value was unavailable, so this repairs a demonstrated contract defect without claiming direct hardware causation.

Native command against the approved official9.3 runtime:

    RACKET -l raco test test_heartbeat.rkt

Use a disposable profile and a30-second external bound. No GUI/display is needed. This native test must pass before reusing the helper. Local Python/static discovery:82 cases,76 pass and6 native-only skips. The actual new native regressions remain unrun locally. No repeated six-trial speed experiment is requested by this freeze.

The two runtime/test source hashes are independently reviewed; all other previous measured source bytes and original evidence remain untouched.
