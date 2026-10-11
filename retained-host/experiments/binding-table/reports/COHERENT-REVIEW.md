# Current revision: 2026-10-11 10:23 UTC test-only Mac fixture repair

Run 38131119786 applied the candidate to its canonical independent runtime and verified source pins, then failed one Python source test because its TemporaryDirectory path retained the macOS /var alias. No native semantics, helper preflight or timing ran. The complete original 26,838-entry runtime witness passed.

Only executable source change from the 1007 freeze is tests/source-test.py: the fixture caller now resolves its temporary root, and a deterministic ancestor-alias test verifies root/source alias refusal, canonical apply/idempotence/revert, refusal even after application, and resolved outside-root refusal. The production applier guard is unchanged. Candidate GUI, native Racket fixtures, all 32 performance package files and trace code are byte-identical.

The owner passed 174 configured portable tests with TMPDIR intentionally routed through a symlink alias (25 production-source/applier, 89 telemetry, 25 native source/comparator and 35 trace-wrapper). Integration and performance reviews independently reran the 25 changed source tests. Neighboring identity-sensitive temporary roots are already canonical; JSON-only read/write fixtures do not invoke runtime confinement. Native execution remains required. See path-repair.diff, path-repair-delta.json and path-alias-portable-tests.log. Earlier validation below records the prior preparation, not a native pass.

Historical 1007 preparation follows:

# Coherent binding experiment review

2026-10-11. Source-only integration: 24 production/applier checks, 25 native-host source/comparator cases, 35 stock-worker wrapper cases, 37 preserved upstream comparator cases and 89 telemetry cases pass (210 total), plus exact native-host and trace-wrapper reproduction. Native Racket compilation/execution, GUI graph/navigation and measured performance remain pending.

Production GUI remains SHA256 1ba5b93e748091888e2f61b1518fe625a86d5b771e471f11204461e9ace02025. The late production-owner update adds only constant-hash state-dependent foreign equality coverage, one source assertion and documentation; actual candidate bytes are unchanged. The case establishes stock fallback before equality changes and never changes a stored key hash. Custom-owner callbacks and deferred errors remain explicitly excluded.

The native gate exports the full fixed binding graph and invokes actual registered navigation commands. The unchanged worker capture uses stock xref in all four outer arms; its derivative comparator preserves the original semantic projection and exact raw-order diagnostics, with GUI activation assessed separately. The performance owner manifest and all member hashes are verified; complete readiness and first public exposure cost remain separate. The configured portable test rerun supplies GUI_TEST_CANDIDATE_SOURCE explicitly, as mandatory native preflight also does.

All sources are default-off experiments, isolated from the delivered preview and accepted app. See CI-CONTRACT.md, native/README.md, trace/README.md and performance/README.md for the exact native prerequisites, bounds, evidence and limits.

Final assembly also includes the six byte-identical 0520 appearance runtime-path dependencies required by the inherited appearance workflow module. Their baseline pins and presence are independently checked; these helpers are not activated in the stock-appearance binding gate.
