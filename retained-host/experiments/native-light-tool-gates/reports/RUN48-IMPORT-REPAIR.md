# Native light run48: explicit diagnostic import repair

Run https://github.com/alikatgh/openracket/actions/runs/38152590660, job114508922001, failed during preparation. Both stock and modern compilers reported `tests/native-light-state-standalone.rkt:71:26: pretty-info?: unbound identifier`. The reader accepted all15 modules in each arm, but reader success does not resolve imported identifiers.

The new standalone uses `pretty-info?` and `pretty-info-value` to verify exact typed operands before printing its injected-failure marker. It imported RackUnit and the diagnostic helper, but that helper does not re-export the two private accessors. The accepted coordinator, dispatcher and diagnostic helper already import them explicitly from `rackunit/private/check-info`.

This revision adds that same explicit two-name import. Every assertion, exception check, positive marker, strict injected-negative marker, tool workflow, observer, validator and native deadline is byte-for-byte unchanged. The accompanying source regression audits all four direct accessor users for that import. No production source changed.

Run48 retained34 rows,21 passing. Both runtime source trees (26,838 entries each) were unchanged, digest `adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`. Modern package registration and actual discovery proofs passed. Neither arm reached a headless contract or GUI tool case. There were no screenshots or artifacts.

Exact raw log SHA256: `0f2b45af4492c3392bc493f559f21293a71dcd805660e93d9ae9933fb6a90425`.
Compile receipts are command-011/supervisor.json and command-021/supervisor.json in the decoded evidence.

Local verification:41 portable cases pass (14 light/source/receipt,13 original tool source,6 coordinator source,8 dispatch source), exact original/light host derivations pass, all11 accepted1125 native files remain exact. An independent source review approved the narrow import. No local Racket execution occurred. Actual native compile plus the unchanged nine preflight records per runtime and six real tool cases remain mandatory. No light-mode success is claimed.

The original1347 freeze and failed native evidence are retained unchanged. Older reports in this package describe that initial preparation; this report and current manifests identify the repaired revision.
